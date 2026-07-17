#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gece_qc.py — GECE KOŞUSU TAKİP/DENETİM: her klip çıktısını tek tek QC et → rapor.

"Çıktı üretti" YETMEZ — KONTROL: isim doğru mu? yönetmen/yapımcı/cast/özet/TÜR/afiş tam mı?
eksik gedik var mı? sistem gerçekten çalıştı mı? nerede sorun var? (Çağatay 2026-06-04)

Her klip için kunye.pdf (metin+afiş) + _DURUM.json okunur, deterministik kontroller koşulur.
ASLA müdahale etmez — sadece denetler + raporlar (outputs/gece_rapor.md + .tsv).

Kullanım:
  python scripts/gece_qc.py                 # tüm Database klipleri
  python scripts/gece_qc.py --since 2026-06-04   # bu tarihten sonra üretilenler
  python scripts/gece_qc.py --clip <dir>    # tek klip
"""
import argparse, base64, glob, json, os, re, sys, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
VISUAL_MODEL = "gemma4:26b"
# Linux geçişi 2026-07-17: env-aware kök (elle koşuşta betik konumundan türet).
_ROOT = os.environ.get("MITAS_PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(_ROOT, "Database")
REPORT_MD = os.path.join(_ROOT, "outputs", "gece_rapor.md")
REPORT_TSV = os.path.join(_ROOT, "outputs", "gece_rapor.tsv")

ROLE_WORDS = {"YÖNETMEN", "YAPIMCI", "OYUNCU", "KAMERA", "GÖRÜNTÜ", "SENARYO", "MÜZİK", "KURGU",
              "YAPIM", "SES", "IŞIK", "MONTAJ", "DEKOR", "KOSTÜM", "MAKYAJ", "EFEKT"}
PLACEHOLDER = ("ADIMDA ÜRETİLECEK", "HAM TRANSCR", "KALIP ÖZET")

def visual_check(png, model=VISUAL_MODEL):
    """gemma4 görsel QC (önizleme PNG): afiş/Türkçe-glyph/özet/altyazı-kaçmış/düzen. GPU gerektirir."""
    prompt = ("Bu bir film künye sayfasının önizlemesi. SADECE şu kontrolleri yap ve JSON döndür:\n"
              '{"afis_var": true/false, "turkce_harf_bozuk": true/false, "ozet_tutarli": true/false, '
              '"altyazi_kacmis": true/false, "duzen_ok": true/false}\n'
              "afis_var: gerçek afiş görseli var mı. turkce_harf_bozuk: İ Ğ Ü Ş Ö Ç kutu/bozuk mu. "
              "ozet_tutarli: özet anlamlı paragraf mı. altyazi_kacmis: künyeye film altyazısı/diyalog "
              "karışmış mı. duzen_ok: genel düzen düzgün mü. Sadece JSON.")
    try:
        with open(png, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        payload = {"model": model, "messages": [{"role": "user", "content": prompt, "images": [b64]}],
                   "stream": False, "think": False, "keep_alive": "10m",
                   "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 200}}
        req = urllib.request.Request(OLLAMA_CHAT, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            content = (json.loads(r.read().decode()).get("message", {}).get("content") or "")
        m = re.search(r"\{.*\}", content, re.S)
        j = json.loads(m.group(0)) if m else {}
    except Exception as e:
        return [("GORSEL_HATA", f"görsel QC çalışmadı: {type(e).__name__}")]
    fl = []
    if j.get("afis_var") is False: fl.append("GÖRSEL: afiş yok")
    if j.get("turkce_harf_bozuk") is True: fl.append("GÖRSEL: Türkçe harf glyph BOZUK")
    if j.get("ozet_tutarli") is False: fl.append("GÖRSEL: özet tutarsız")
    if j.get("altyazi_kacmis") is True: fl.append("GÖRSEL: künyeye altyazı karışmış")
    if j.get("duzen_ok") is False: fl.append("GÖRSEL: düzen bozuk")
    return fl

def pdf_text(p):
    try:
        import fitz
        d = fitz.open(p)
        return d[0].get_text(), len(d[0].get_images())
    except Exception:
        return "", 0

def section(txt, head):
    """PDF metninden bir bölümü çek (head ile bir sonraki büyük-harf-aralıklı başlık arası)."""
    # PDF harfleri 'Y A P I M  E K İ B İ' gibi aralıklı; head'i aralıklı da dene
    spaced = " ".join(head)
    for h in (head, spaced):
        i = txt.find(h)
        if i >= 0:
            rest = txt[i + len(h):]
            m = re.search(r"\n[A-ZÇĞİÖŞÜ](?: [A-ZÇĞİÖŞÜ]){3,}", rest)  # sonraki aralıklı başlık
            return rest[: m.start()] if m else rest
    return ""

def qc_clip(clipdir, do_visual=False):
    name = os.path.basename(clipdir)
    pdf = os.path.join(clipdir, "pdf", "kunye.pdf")
    durum = os.path.join(clipdir, "_DURUM.json")
    issues = []
    info = {"klip": name, "durum": "?", "sorunlar": issues}

    if not os.path.exists(pdf):
        issues.append("PDF YOK")
        info["durum"] = "ÇIKTI_YOK"
        return info

    t, nimg = pdf_text(pdf)
    tim = {}
    if os.path.exists(durum):
        try: tim = (json.load(open(durum, encoding="utf-8")).get("timings_sec") or {})
        except Exception: pass
    info["v4_calisti"] = "v4_final" in tim
    info["video_okuma"] = "video_kunye" in tim

    # 1) BAŞLIK — kunye_teslim.md header'dan (güvenilir) + İ-kaybı kontrolü (tek-harf kelime)
    title = ""
    md = os.path.join(clipdir, "pdf", "kunye_teslim.md")
    if os.path.exists(md):
        try:
            mtxt = open(md, encoding="utf-8").read()
            mm = re.search(r"#\s*M[İI]TAS\s*[•·]\s*\S+\s*[•·]\s*(.+)", mtxt)
            if mm:
                title = mm.group(1).strip()
        except Exception:
            pass
    lone = [w for w in title.split() if len(w) == 1]
    if not title:
        issues.append("BAŞLIK okunamadı")
    elif lone:
        issues.append(f"BAŞLIK İ-KAYBI? tek-harf {lone} → '{title}'")
    info["baslik"] = title

    # 2) YÖNETMEN
    crew = section(t, "YAPIM EKİBİ")
    yon_blok = section(t, "YAPIM EKİBİ")
    has_yon = "Yönetmen" in t
    has_yap = "Yapımcı" in t
    if not has_yon:
        issues.append("YÖNETMEN satırı yok")
    if not has_yap:
        issues.append("YAPIMCI satırı yok")

    # 3) OYUNCULAR — boş mu / dublaj-karışması (yabancı+TR ad bir arada şüphesi)
    oy = section(t, "OYUNCULAR")
    oy_lines = [l.strip() for l in oy.splitlines() if l.strip() and l.strip() == l.strip().upper() and len(l.strip()) > 2][:12]
    if not oy_lines:
        issues.append("OYUNCULAR boş")

    # 4) ÖZET — placeholder / kısa / küçük-harf
    if any(p in t for p in PLACEHOLDER):
        issues.append("ÖZET placeholder (ASR/key sorunu)")
    oz = section(t, "ÖZET")
    ozw = len(oz.split())
    if 0 < ozw < 25:
        issues.append(f"ÖZET kısa ({ozw} kel)")
    if re.search(r"[a-zçğıiöşü]", oz):
        issues.append("ÖZET küçük-harf (v4 değil)")

    # 5) TÜR / KARE / afiş / v4
    if "T Ü R" in t or "TÜR" in t:
        tur_blok = section(t, "TÜR")
        if "—" in tur_blok[:6] or not tur_blok.strip():
            issues.append("TÜR boş")
    else:
        issues.append("TÜR alanı yok")
    if "KARE HIZI" in t or "KARE" in t.replace("KARE KİMLİK", ""):
        issues.append("KARE HIZI var (pre-v4)")
    if nimg == 0:
        issues.append("AFİŞ yok")

    # 6) SES mantığı (ana_dil != TR + altyazı HAYIR = mantıksız)
    adil = re.search(r"A N A  D İ L\s*\n([A-Z]+)", t)
    alt = re.search(r"A L T Y A Z I\s*\n([A-ZÇĞİÖŞÜ]+)", t)
    if adil and alt and adil.group(1) != "TR" and alt.group(1) == "HAYIR":
        issues.append(f"SES MANTIKSIZ (ana_dil={adil.group(1)} + altyazı=HAYIR)")

    # 7) GÖRSEL QC (opsiyonel, GPU) — önizleme PNG'yi gemma4 ile dene (sabah/koşu-sonrası)
    if do_visual:
        png = os.path.join(clipdir, "pdf", "kunye_onizleme.png")
        if os.path.exists(png):
            issues += visual_check(png)
    info["afis"] = nimg > 0
    info["durum"] = "TEMİZ" if not issues else "SORUNLU"
    return info

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", default=None)
    ap.add_argument("--source", default=DB)
    ap.add_argument("--since", default=None, help="YYYY-MM-DD (klip mtime sonrası)")
    ap.add_argument("--visual", action="store_true", help="gemma4 görsel QC de ekle (GPU; koşu BİTTİKTEN sonra)")
    a = ap.parse_args()

    if a.clip:
        clips = [a.clip]
    else:
        clips = [d for d in sorted(glob.glob(os.path.join(a.source, "*"))) if os.path.isdir(d)
                 and os.path.exists(os.path.join(d, "pdf", "kunye.pdf"))]
        if a.since:
            import datetime
            try:
                thr = datetime.datetime.strptime(a.since, "%Y-%m-%d").timestamp()
                clips = [c for c in clips if os.path.getmtime(os.path.join(c, "pdf", "kunye.pdf")) >= thr]
            except Exception:
                pass

    rows = [qc_clip(c, a.visual) for c in clips]
    temiz = [r for r in rows if r["durum"] == "TEMİZ"]
    sorunlu = [r for r in rows if r["durum"] == "SORUNLU"]
    yok = [r for r in rows if r["durum"] in ("ÇIKTI_YOK",)]

    os.makedirs(os.path.dirname(REPORT_MD), exist_ok=True)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(f"# GECE KOŞUSU QC RAPORU\n\n")
        f.write(f"**Toplam {len(rows)} klip** · TEMİZ {len(temiz)} · SORUNLU {len(sorunlu)} · ÇIKTI_YOK {len(yok)}\n\n")
        # sorun dağılımı
        cat = {}
        for r in sorunlu + yok:
            for s in r["sorunlar"]:
                k = re.split(r"[\(:]", s)[0].strip()
                cat[k] = cat.get(k, 0) + 1
        if cat:
            f.write("## Sorun dağılımı\n")
            for k, n in sorted(cat.items(), key=lambda x: -x[1]):
                f.write(f"- {n:3}  {k}\n")
            f.write("\n")
        f.write("## SORUNLU klipler (öncelik)\n")
        for r in sorunlu + yok:
            f.write(f"- **{r['klip'][:60]}** [{r.get('baslik','?')}]\n")
            for s in r["sorunlar"]:
                f.write(f"    - {s}\n")
        f.write("\n## TEMİZ klipler\n")
        for r in temiz:
            f.write(f"- {r['klip'][:60]} [{r.get('baslik','?')}] · afiş={r.get('afis')}\n")
    with open(REPORT_TSV, "w", encoding="utf-8") as f:
        f.write("klip\tdurum\tbaslik\tv4\tafis\tsorunlar\n")
        for r in rows:
            f.write(f"{r['klip']}\t{r['durum']}\t{r.get('baslik','')}\t{r.get('v4_calisti')}\t{r.get('afis')}\t{' | '.join(r['sorunlar'])}\n")

    print(f"=== QC BİTTİ: {len(rows)} klip | TEMİZ {len(temiz)} | SORUNLU {len(sorunlu)} | ÇIKTI_YOK {len(yok)} ===")
    print(f"Rapor: {REPORT_MD}")
    for r in (sorunlu + yok)[:15]:
        print(f"  [{r['durum']:8}] {r['klip'][:48]:48} {'; '.join(r['sorunlar'])[:80]}")

if __name__ == "__main__":
    main()
