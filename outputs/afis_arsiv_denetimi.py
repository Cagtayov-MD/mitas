# -*- coding: utf-8 -*-
"""afis_arsiv_denetimi.py — ONAYLI arşivindeki TÜM afişlerin VL-görsel-tutarlılık taraması.

2026-07-09 REKABET/Challengers yanlış-afiş kökünden sonra: bu mekanizma (poster_fetch id-zinciri,
şimdi düzeltildi — bkz. commit) başka ONAYLI filmlerde de SESSİZCE yanlış afiş üretmiş olabilir mi
taraması. Her PDF'in gömülü afiş görseli (varsa) çıkarılıp gerçek başlıkla birlikte yerel VL modele
(qwen3-vl:30b, Ollama) "bu afiş bu filme mi ait görünüyor" diye sorulur.

SADECE RAPORLAR — silme/taşıma/otomatik-düzeltme YOK (SİLME YASAK ilkesi).

Not: Ollama'nın `format` (JSON-schema) parametresi bu VL modelde çok yavaş/boş-yanıt üretti
(ölçüldü, 2026-07-09) → düz-metin prompt + regex JSON-çıkarma (bu kod tabanındaki diğer VL
çağrılarıyla aynı desen, ör. outputs/vl_speed_test.py) kullanılıyor.
"""
import base64
import fitz
import glob
import json
import os
import re
import sys
import time
import urllib.request

ONAYLI = r"E:\MITAS\Mitas Output\export\ONAYLI"
OLLAMA = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434")
MODEL = os.environ.get("MITAS_AFIS_QC_MODEL", "qwen3-vl:30b")
OUT_JSON = r"E:\MITAS\outputs\AFIS_ARSIV_DENETIMI_2026-07-09.json"
TMP_JPG = os.path.join(os.environ.get("TEMP", r"E:\MITAS\.tmp"), "_afis_denetim_poster.jpg")

PROMPT_TMPL = (
    "Bu görsel bir film afişidir. Filmin gerçek bilgileri: BAŞLIK=\"{title}\" ({original}), "
    "TÜR={genre}. GÖREVİN: bu afiş görselinin bu film ile tutarlı olup olmadığını değerlendirmek. "
    "Özellikle: (1) afişte YAZILI başka bir film adı görüyor musun (yukarıdaki başlıktan FARKLI)? "
    "(2) afişin tür/dönem/estetiği (kostüm, yazı fontu, renk paleti, oyuncu görünümü) yukarıdaki "
    "TÜR ile BARİZ uyumsuz mu (örn. çok modern bir afiş çok eski bir filme, ya da açıkça yanlış "
    "bir türün afişi — örn. spor draması filmine bilim-kurgu/animasyon afişi)? "
    "(3) bu bir gerçek afiş mi, yoksa video kare-yakalaması/rastgele bir fotoğraf mı? "
    "Emin olmadığın İNCE zevk farklarını DEĞİL, YALNIZ AÇIK/BARİZ uyumsuzlukları işaretle. "
    "SADECE şu JSON formatında cevap ver, başka hiçbir şey yazma: "
    '{{"tutarli": true veya false, "supheli_sebep": "kısa açıklama (tutarlıysa boş string)", '
    '"guven": "yuksek" veya "orta" veya "dusuk"}} /no_think'
)


def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()


def extract_title_from_filename(fn):
    m = re.match(r"^\d{4}-\d{4}-\d-\d{4}-\d{2}-\d\s+(.+?)_onayl[iı]\.pdf$", fn, re.I)
    return m.group(1).strip() if m else os.path.splitext(fn)[0]


def extract_field_after_label(lines, label_variants):
    for i, l in enumerate(lines):
        compact = re.sub(r"\s+", "", l).upper()
        if compact in label_variants and i + 1 < len(lines):
            return lines[i + 1]
    return None


def extract_original_title(lines, title):
    """'FİLM' etiketinden 2 satır sonrası (varsa) orijinal/uluslararası ad — afişte YAZILI olması
    beklenen alternatif ad (ör. 'LES DIABLIQUES'), VL'nin yanlış-pozitif vermemesi için ŞART."""
    for i, l in enumerate(lines):
        compact = re.sub(r"\s+", "", l).upper()
        if compact in ("FİLM", "FILM") and i + 2 < len(lines):
            cand = lines[i + 2].strip()
            if cand and cand.upper() != title.strip().upper() and len(cand) <= 80:
                return cand
    return None


def extract_poster(pdf_path, title):
    """Sayfa-0'daki en büyük PORTRE gömülü rasteri çıkar → TMP_JPG. Yoksa (None, genre, original)."""
    doc = fitz.open(pdf_path)
    try:
        pg = doc[0]
        page_text = pg.get_text()
        lines = [l.strip() for l in page_text.splitlines() if l.strip()]
        genre = extract_field_after_label(lines, ("TÜR", "TUR")) or "bilinmiyor"
        original = extract_original_title(lines, title)
        recs = []
        for im in pg.get_images(full=True):
            xref = im[0]
            try:
                px = fitz.Pixmap(doc, xref)
                recs.append((xref, px.width, px.height))
            except Exception:
                continue
        cands = [r for r in recs if r[2] > r[1] and r[1] * r[2] > 20000]
        cands.sort(key=lambda r: -(r[1] * r[2]))
        if not cands:
            return None, genre, original
        px = fitz.Pixmap(doc, cands[0][0])
        if px.n - px.alpha >= 4:
            px = fitz.Pixmap(fitz.csRGB, px)
        px.save(TMP_JPG)
        return TMP_JPG, genre, original
    finally:
        doc.close()


def ask_vl(poster_path, title, original, genre, timeout=240):
    prompt = PROMPT_TMPL.format(title=title, original=(original or "—"), genre=genre)
    body = {
        "model": MODEL, "prompt": prompt, "images": [b64(poster_path)],
        "stream": False, "think": False,
        "keep_alive": os.environ.get("MITAS_OLLAMA_KEEP_ALIVE", "10m"),
        "options": {"temperature": 0, "num_ctx": 8192},
    }
    req = urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read().decode("utf-8"))
    txt = resp.get("response", "")
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"tutarli": None, "supheli_sebep": f"parse-hata: {txt[:200]}", "guven": "dusuk"}


def warm_up(timeout=400):
    """qwen3-vl:30b soğuk-start yüklemesi ~200sn sürüyor (ölçüldü) — döngü-içi ilk çağrının
    timeout'a takılmaması için ayrı, cömert-timeout'lu bir ısınma çağrısı."""
    body = {"model": MODEL, "prompt": "merhaba /no_think", "stream": False, "think": False,
            "keep_alive": os.environ.get("MITAS_OLLAMA_KEEP_ALIVE", "10m"),
            "options": {"num_predict": 8}}
    req = urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        json.loads(r.read().decode("utf-8"))
    print(f"[ısınma] model yüklendi ({round(time.time() - t0, 1)}s)\n", flush=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    only_n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    pdfs = sorted(glob.glob(os.path.join(ONAYLI, "*.pdf")))
    if only_n:
        pdfs = pdfs[:only_n]
    print(f"{len(pdfs)} ONAYLI PDF taranacak (model={MODEL}).\n", flush=True)
    warm_up()
    results = []
    for i, p in enumerate(pdfs):
        fn = os.path.basename(p)
        title = extract_title_from_filename(fn)
        rec = {"file": fn, "title": title}
        try:
            poster_path, genre, original = extract_poster(p, title)
            rec["genre"] = genre
            rec["original"] = original
            if not poster_path:
                rec.update({"tutarli": True, "supheli_sebep": "afis yok (PDF'te gömülü portre görsel yok)",
                            "guven": "yuksek"})
            else:
                t0 = time.time()
                verdict = ask_vl(poster_path, title, original, genre)
                rec.update(verdict)
                rec["sure_sn"] = round(time.time() - t0, 1)
        except Exception as e:
            rec["hata"] = f"{type(e).__name__}: {e}"
        results.append(rec)
        tag = "ŞÜPHELİ" if rec.get("tutarli") is False else ("HATA" if "hata" in rec else "temiz")
        print(f"[{i+1}/{len(pdfs)}] {tag:8s} {fn}  ({rec.get('supheli_sebep', rec.get('hata', ''))})",
              flush=True)
        json.dump(results, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    supheli = [r for r in results if r.get("tutarli") is False]
    hatali = [r for r in results if "hata" in r]
    print(f"\n=== ÖZET: {len(results)} film, {len(supheli)} şüpheli, {len(hatali)} hata ===")
    for r in supheli:
        print(f"  - {r['file']}: {r.get('supheli_sebep')} (güven={r.get('guven')})")
    print(f"\n[yazıldı] {OUT_JSON}")


if __name__ == "__main__":
    main()
