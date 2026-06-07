#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tek_film_kunye.py — TEK KOMUT: bir klip → TEMİZ v4 künye PDF (uçtan uca otomatik zincir).

"Sen de koşabilesin" — bu script 4 adımı doğru python'larla KENDİ çağırır:
  1) video-okuma   (venvs/ocr)  _pipe_credit_video.py  → yönetmen + cast
  2) cross-check   (venvs/ocr)  credit_kb_lookup.py    → doğrula + yapımcı + TÜR + afiş
  3) meta          klibin pdf/kunye_teslim.md'sinden    → başlık, özet, kanal, süre
  4) v4 render     (bu python)  _make_pdf.build         → temiz v4 PDF

ÇALIŞTIR: GLOBAL python ile (reportlab burada). venvs/ocr alt-süreçlerini kendi çağırır.
  python scripts/tek_film_kunye.py --clip "Database/<klip>" [--out <pdf>] [--original "..."] [--year 2019]

Hiç çökmez; bir adım başarısızsa eldeki en iyi veriyle devam eder, neyin eksik olduğunu yazar.
"""
import argparse, datetime, importlib.util, json, os, re, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY_OCR = os.path.join(ROOT, "venvs", "ocr", "Scripts", "python.exe")
PDFMITAS = r"E:\MITAS\OCR-worktree\pdf-mitas"
AFIS_CACHE = r"E:\MITAS\_102_afis_cache"
OUT_DEFAULT = r"E:\MITAS\Mitas Output\GUNCEL_ORNEK"

def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

mp = _load("mp", os.path.join(PDFMITAS, "_make_pdf.py"))
nn = _load("nn", os.path.join(PDFMITAS, "name_normalize.py"))

# OCR cast LİSTESİ otorite; KB yalnız OKUNAN ismin YAZIMINI düzeltir → name_match gerekir.
# credit_crosscheck top-level'da duckdb import etmez (sadece CreditKB.__init__'te) → global python'da güvenli.
sys.path.insert(0, HERE)
try:
    import credit_crosscheck as _cc
except Exception as _e:                              # import edilemezse cast'a DOKUNMA (graceful)
    _cc = None
    sys.stderr.write(f"[uyari] credit_crosscheck import edilemedi (cast yazım düzeltme atlandı): {_e}\n")

def run_ocr_json(script, args, timeout=1800):
    """venvs/ocr alt-süreci koş, stdout'tan son JSON satırını çöz."""
    cmd = [PY_OCR, os.path.join(HERE, script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except Exception as e:
        sys.stderr.write(f"[uyari] {script} koşulamadı: {e}\n")
        return None, ""
    obj = None
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
            except Exception:
                pass
    return obj, (r.stderr or "")

def parse_teslim_md(path):
    """pdf/kunye_teslim.md → {title, trt_id, res, dur, ses_kanallari, ana_dil, altyazi, ozet}"""
    d = {"title": None, "trt_id": None, "res": "—", "dur": "—",
         "ses_kanallari": [], "ana_dil": "—", "altyazi": "—", "ozet": ""}
    if not (path and os.path.exists(path)):
        return d
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"#\s*M[İI]TAS\s*•\s*\w+\s*•\s*(.+)", txt)
    if m:
        d["title"] = m.group(1).strip()
    m = re.search(r"-\s*ID:\s*(\S+)", txt)
    if m:
        d["trt_id"] = m.group(1).strip()
    m = re.search(r"Çözünürlük:\s*([^\s·]+).*?Süre:\s*([0-9:]+)", txt)
    if m:
        d["res"], d["dur"] = m.group(1).strip(), m.group(2).strip()
    for ln in re.findall(r"-\s*\d+\.\s*kanal:\s*(.+)", txt):
        d["ses_kanallari"].append(ln.strip())
    m = re.search(r"-\s*Ana dil:\s*(.+)", txt)
    if m:
        d["ana_dil"] = m.group(1).strip().upper()
    m = re.search(r"-\s*Altyazı:\s*(.+)", txt)
    if m:
        d["altyazi"] = m.group(1).strip().upper()
    m = re.search(r"##\s*Özet\s*\n(.+)", txt, re.S)
    if m:
        d["ozet"] = re.sub(r"\s+", " ", m.group(1)).strip()
    return d

def ozet_v4(ozet):
    """v4 özet: kurulum cümleleri + SON cümle (spoiler) korunur, ≤~64 kelime, TR-BÜYÜK.
    Yabancı özel adda i→İ olabilir (prozada kabul)."""
    if not ozet:
        return "—"
    ozet = re.sub(r'[?!"\[\]]', "", ozet)
    cumleler = [c.strip() for c in re.split(r"(?<=[.])\s+", ozet) if c.strip()]
    if len(cumleler) <= 1:
        return nn.tr_upper(ozet)
    son = cumleler[-1]                              # final/spoiler cümlesi (v4: spoiler şart)
    son_w = len(son.split())
    out, n = [], 0
    for c in cumleler[:-1]:
        w = len(c.split())
        if out and n + w + son_w > 64:              # son cümleye yer bırak
            break
        out.append(c)
        n += w
    if son not in out:
        out.append(son)                             # spoiler finalini garanti ekle
    return nn.tr_upper(" ".join(out))

def up_o(s):
    s = s or ""
    return nn.tr_upper(s) if any(c in nn._TR_STRONG for c in s) else nn.ascii_fold(s).upper()

def _split_dedup_names(lst):
    """KB'den gelen yapimci/cast birlesik satirlarini ('&'/'ve'/'/'/',') bol + fold-bazli tekrar ele."""
    out = []
    for item in lst or []:
        for part in re.split(r"\s*&\s*|\s+ve\s+|\s*/\s*|\s*,\s*|\s+-\s+", str(item), flags=re.I):
            part = part.strip()
            if not part:
                continue
            kf = nn.ascii_fold(part).upper()
            if kf and all(nn.ascii_fold(o).upper() != kf for o in out):
                out.append(part)
    return out

def main():
    ap = argparse.ArgumentParser(description="Tek klip → temiz v4 künye PDF (uçtan uca)")
    ap.add_argument("--clip", required=True, help="klip klasörü (frames/ ve pdf/kunye_teslim.md içerir)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--original", default=None, help="orijinal ad (opsiyonel; cross-check'e yardım)")
    ap.add_argument("--year", default=None)
    ap.add_argument("--title", default=None, help="TR başlık override")
    ap.add_argument("--video-credits", default=None, help="önceden hesaplanmış video-okuma JSON (verilirse 1. adım atlanır)")
    ap.add_argument("--profile", default="film", choices=["film", "dizi"])    # Fix 3a
    ap.add_argument("--bolum", default=None)                                   # Fix 3a
    a = ap.parse_args()

    clip = a.clip
    giris = os.path.join(clip, "frames", "giris")
    cikis = os.path.join(clip, "frames", "cikis")
    md = os.path.join(clip, "pdf", "kunye_teslim.md")
    meta = parse_teslim_md(md)
    title = a.title or meta.get("title") or os.path.basename(clip.rstrip("/\\"))
    trt = meta.get("trt_id") or "—"
    rapor = {"adimlar": {}}

    # 1) VIDEO-OKUMA (pipeline önceden hesapladıysa onu kullan, tekrar GPU'ya gitme)
    if a.video_credits:
        try:
            vc = json.loads(a.video_credits)
        except Exception:
            vc = None
    else:
        vc, _ = run_ocr_json("_pipe_credit_video.py", ["--giris", giris, "--cikis", cikis])
    vc = vc or {}
    yon = vc.get("yonetmen") or []
    cast = vc.get("cast") or []
    yap = vc.get("yapimci") or []
    rapor["adimlar"]["video_okuma"] = {"yon": yon, "cast_okunan": cast, "guven": vc.get("guven")}

    # 2) CROSS-CHECK + YAPIMCI + TÜR + AFİŞ
    afis_out = os.path.join(AFIS_CACHE, (trt if trt != "—" else re.sub(r"\W+", "_", title)) + ".jpg")
    cc_args = ["--baslik", title, "--yonetmen", (yon[0] if yon else ""),
               "--cast", ",".join(cast), "--afis-out", afis_out]
    if a.original:
        cc_args += ["--orijinal", a.original]
    if a.year:
        cc_args += ["--yil", str(a.year)]
    cc, _ = run_ocr_json("credit_kb_lookup.py", cc_args)
    cc = cc or {}
    cast_ov = cc.get("cast_ortusme") or 0
    verdict = cc.get("verdict")
    auth_yon = cc.get("otoriter_yonetmen") or []
    # KİMLİK DOĞRULANDI mı: read yönetmeni TEYİT aldı YA DA okunan cast otoriteyle >=2 örtüştü
    kimlik_dogru = (verdict == "TEYİT") or (cast_ov >= 2)
    yon_kaynak = "kareler"
    if kimlik_dogru and auth_yon:
        if not yon:
            # kareden OKUNAMADI → KB'den DOLDUR (uydurma değil, kimlik cast ile doğrulandı)
            yon = auth_yon
            yon_kaynak = "KB (kareden okunamadı; kimlik cast ile doğrulandı)"
        # ÇELİŞKİ: OCR yönetmeni OTORİTE — KB ile EZİLMEZ (KESİN İLKE 3). Çelişki zaten
        # mitas_pipeline'da Kontrol'e düşürür; burada OKUNAN yönetmeni KORU.
        # else TEYİT → kareden okunan otoriteyle eşleşti, KALSIN
    # cast: OCR/jenerik kadrosu MUTLAK OTORİTE — liste (uzunluk+sıra) OCR'dan, KB ile EZİLMEZ.
    # KB yalnız OKUNAN ismin YAZIMINI düzeltir (Ahmet Cimcir→Cemcir): her OCR ismi için
    # otoriter_cast'ta name_match ile eş ara; eşleşirse SADECE o ismi kanonik haliyle değiştir,
    # eşleşmezse OCR ismini AYNEN koru. KB'de olup OCR'da olmayan ismi EKLEME.
    auth = cc.get("otoriter_cast") or []
    if kimlik_dogru and auth and _cc is not None:
        duz = []
        for nm in cast:
            # önce SIKI eşitlik (aynı kişi kesin), tutmazsa OCR-misread yazım düzeltmesi (Cimcir→Cemcir)
            es = next((a for a in auth if _cc.name_match(nm, a)), None) \
                 or next((a for a in auth if _cc.name_close(nm, a)), None)
            duz.append(es if es else nm)
        cast = duz
    if not yap and cc.get("yapimci"):
        yap = cc["yapimci"]
    yap = _split_dedup_names(yap)[:3]               # "&"/"ve" birlesik bol + tekrar ele, sonra en fazla 3 yapimci
    tur = cc.get("tur") or "—"
    afis = cc.get("afis")
    rapor["adimlar"]["cross_check"] = {"verdict": verdict, "kimlik_dogru": kimlik_dogru,
                                       "yonetmen_kaynak": yon_kaynak, "yapimci": yap, "tur": tur,
                                       "cast_ortusme": cast_ov, "afis": bool(afis)}

    # 3) v4 d kur + render
    cast = _split_dedup_names(cast)           # Fix 1: "&"/tekrar böl+ele (GUILLAUME GOUIX ×2 vb.)
    castU = nn.upper_names(cast[:8])
    crew = [("Yönetmen", yon), ("Yapımcı", yap)]
    crew = [(r, x) for r, x in crew if x]
    crewU = nn.upper_crew(crew) if crew else [("Yönetmen", ["—"])]
    sk = [x for x in meta.get("ses_kanallari", []) if x and str(x).strip().upper() not in ("EFEKT", "EF")]  # Fix 4
    poster = afis if (afis and os.path.exists(afis) and os.path.getsize(afis) > 5000) else None
    now = datetime.datetime.now().strftime("%d.%m.%Y · %H:%M")
    # Altyazı/orijinal: YALNIZ gerçek XML orijinal-ad (a.original). KB'nin "eslesen_film"i
    # (yanlış olabilen KB başlığı) altyazı olarak KULLANILMAZ — KÖK SEBEP: title-only yanlış
    # çakışmada "Red Flag" gibi alakasız KB adı altyazıya sızıyordu. Orijinal yoksa altyazı YOK.
    _orig_raw = a.original or None
    _sub = up_o(_orig_raw) if _orig_raw else None
    if _sub and nn.ascii_fold(_sub).upper() == nn.ascii_fold(title).upper() \
            and meta.get("ana_dil", "—").upper() in ("TR", "—", ""):
        _sub = None                                 # Türkçe/bilinmeyen içerikte başlıkla aynı orijinal = gereksiz altyazı
    d = dict(profile=("DİZİ" if a.profile == "dizi" else "FİLM"), date=now,   # Fix 3a: profile hardcode → argparse
             title=nn.tr_upper(title), subtitle=_sub,  # Fix 2/3: foreign'da orijinal, Türkçe'de gereksizi gizle
             specs=[("ÇÖZÜNÜRLÜK", meta.get("res", "—")), ("TÜR", nn.tr_upper(tur)),
                    ("TOPLAM SÜRE", meta.get("dur", "—")), ("TRT KİMLİK", trt)],
             keywords=" ; ".join(castU) if castU else "—", cast=castU or ["—"], crew=crewU,
             ozet=ozet_v4(meta.get("ozet", "")), ses_kanallari=sk,
             ana_dil=meta.get("ana_dil", "—"), altyazi=meta.get("altyazi", "—"), poster=poster)
    d["bolum"] = a.bolum                                                       # Fix 3a: _make_pdf None ise basmaz

    out_pdf = a.out or os.path.join(OUT_DEFAULT, f"{trt} {nn.tr_upper(title)} (v4).pdf")
    os.makedirs(os.path.dirname(os.path.abspath(out_pdf)), exist_ok=True)
    mp.build(out_pdf, d)

    # önizleme + rapor
    try:
        import fitz
        fitz.open(out_pdf)[0].get_pixmap(dpi=130).save(out_pdf.replace(".pdf", "_onizleme.png"))
    except Exception:
        pass
    rapor["pdf"] = out_pdf
    rapor["v4"] = {"yonetmen": [n for _, ns in crewU for n in ns if _ == "Yönetmen"],
                   "yapimci_var": any(r == "Yapımcı" for r, _ in crewU), "cast": len(castU),
                   "tur": d["specs"][1][1], "afis": bool(poster),
                   "ozet_kelime": len(d["ozet"].split()), "kanal": sk}
    print(json.dumps(rapor, ensure_ascii=False, indent=2))
    print("PDF:", out_pdf)

if __name__ == "__main__":
    main()
