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
# KB cast-ekleme (eksik isim TAMAMLAMA, asla ezme) — default KAPALI. Açıkken bile kimlik GERÇEKTEN
# emin olmalı (OCR-teyitli yönetmen + ≥3 SIKI cast → GÜÇLÜ/Hazır; ≥4 SIKI cast → ORTA/Kontrol).
_ADD_ON = os.environ.get("MITAS_KB_CAST_ADD", "").strip().lower() in ("1", "true", "on", "yes")

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
        _oz = re.sub(r"\s+", " ", m.group(1)).strip()
        # KESKİN KAPI: "(HAM TRANSCRİPT ÖNİZLEME — KALIP ÖZET SONRA)" = gerçek özet DEĞİL,
        # ham ASR önizleme placeholder'ı. Orijinal pipeline gerçek özeti üretmediğinde kalır.
        # Bu çöp ASLA özet olarak kullanılmamalı → boşalt (üretici gerçek özet sağlamalı).
        if re.search(r"HAM\s*TRANSCR|KAL[İIı]P\s*[ÖO]ZET", _oz, re.I):
            _oz = ""
        d["ozet"] = _oz
    return d

def ozet_v4(ozet, names=(), cap=72):
    """v5 özet: SON cümle (spoiler) HER ZAMAN korunur; toplam ~cap (72) kelimeyi aşarsa
    yalnızca ortadaki kurulum cümleleri kırpılır. Yeni ozet_film.txt promptu zaten ≤70 sıkı
    yazdığı için bu fonksiyon ÇOĞU özette HİÇ kırpmaz (anlam kaybı yok) — yalnız güvenlik ağı.
    Büyük harf nn.tr_upper_prose ile (isim-FARKINDA): yabancı cast/crew adları ASCII (MASSIMO),
    Türkçe isimler İ. names = filmin cast+yönetmen+yapımcı ham adları. DETERMİNİSTİK — LLM YOK."""
    if not ozet:
        return "—"
    # KESKİN KAPI (2. katman): ham-transcript/placeholder özet asla biçimlenip geçmesin.
    if re.search(r"HAM\s*TRANSCR|KAL[İIı]P\s*[ÖO]ZET", ozet, re.I):
        return "—"
    ozet = re.sub(r'[?!"\[\]]', "", ozet)
    cumleler = [c.strip() for c in re.split(r"(?<=[.])\s+", ozet) if c.strip()]
    if len(cumleler) <= 1:
        return nn.tr_upper_prose(ozet, names)
    toplam = sum(len(c.split()) for c in cumleler)
    if toplam <= cap:                               # zaten sığıyor → HİÇ kırpma (cümle düşürme yok)
        return nn.tr_upper_prose(" ".join(cumleler), names)
    son = cumleler[-1]                              # final/spoiler cümlesi (v5: spoiler şart)
    son_w = len(son.split())
    out, n = [], 0
    for c in cumleler[:-1]:
        w = len(c.split())
        if out and n + w + son_w > cap:             # son cümleye yer bırak (üst eşik ~72 kelime)
            break
        out.append(c)
        n += w
    if son not in out:
        out.append(son)                             # spoiler finalini garanti ekle
    return nn.tr_upper_prose(" ".join(out), names)

def up_o(s):
    s = s or ""
    return nn.tr_upper(s) if any(c in nn._TR_STRONG for c in s) else nn.ascii_fold(s).upper()

def poster_ok(path):
    """AFİŞ KAPISI (QC2-sistemik): geçerli afiş = dosya var + >5KB + PORTRE (dikey, w<h).
    poster_fetch gerçek afiş bulamayınca videodan YATAY (16:9) frame-grab/backdrop döndürebilir →
    'afiş yerine foto' tuzağı (çocuk yüzü vb.). Yatay/kare RED. PIL yoksa eski boyut-kontrolüne düş (fail-safe)."""
    try:
        if not (path and os.path.exists(path) and os.path.getsize(path) > 5000):
            return False
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        if w >= h:
            sys.stderr.write(f"[afiş-reddet] yatay görsel {w}x{h} afiş değil → atıldı\n")
            return False
        return True
    except Exception:
        try:
            return bool(path and os.path.exists(path) and os.path.getsize(path) > 5000)
        except Exception:
            return False

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

    # 1) KÜNYE-OKUMA (pipeline önceden hesapladıysa onu kullan; yoksa OneOCR+GLM METNİNDEN rol-eşle)
    #    VLM (credit_video_read) ÇIKARILDI — okuma OneOCR+GLM, isim kaynağı ocr/kunye.txt (Çağatay 2026-06-08).
    if a.video_credits:
        try:
            vc = json.loads(a.video_credits)
        except Exception:
            vc = None
    else:
        vc = None
        try:
            import glob as _glob
            _ocrtxt = sorted(_glob.glob(os.path.join(clip, "ocr", "*", "kunye.txt")),
                             key=os.path.getmtime)
            if _ocrtxt:
                sys.path.insert(0, HERE)
                import credit_text_read as _ctr
                _lines = open(_ocrtxt[-1], encoding="utf-8", errors="ignore").read().splitlines()
                vc = _ctr.read_credits_auto(_lines, title, dizi=(a.profile == "dizi"))
        except Exception as _e:  # noqa: BLE001
            sys.stderr.write(f"[uyari] OneOCR+GLM metin-okuma hata: {_e}\n")
    vc = vc or {}
    yon = vc.get("yonetmen") or []
    cast = vc.get("cast") or []
    yap = vc.get("yapimci") or []

    # FIX-1: Credit-cümle filtresi — "BASED ON THE POPEYE CHARACTERS..." gibi OCR jenerik
    # metinleri yönetmen olarak geçmesin. Kapı: uzun (>60 karakter) veya bilinen credit ifadesi.
    _CREDIT_STARTS = (
        "BASED ON", "CREATED BY", "CHARACTERS CREATED", "CHARACTERS BY",
        "ADAPTED FROM", "ADAPTED BY", "WRITTEN BY", "SCREENPLAY BY",
        "STORY BY", "ORIGINAL STORY", "FROM THE NOVEL", "FROM THE BOOK",
        "PRODUCED BY", "EXECUTIVE PRODUCER", "A FILM BY",
    )
    def _is_credit_phrase(name: str) -> bool:
        n = name.strip().upper()
        if len(n) > 60:
            return True
        return any(n.startswith(p) for p in _CREDIT_STARTS)

    yon_filtered = [d for d in yon if not _is_credit_phrase(d)]
    if len(yon_filtered) < len(yon):
        _dropped = [d for d in yon if _is_credit_phrase(d)]
        sys.stderr.write(f"[fix1] credit-cümle filtre: {_dropped} → yönetmen dışı bırakıldı\n")
    yon = yon_filtered

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
    # FUZZY-DBQC (flag MITAS_FUZZY_DBQC, default KAPALI; Çağatay 2026-06-14): garble OCR cast'i DB-otoriteye
    # GÖMÜLÜ-PENCERE ile eşle. name_match/name_close GARBLE'da (karakter-adı karışık: 'VAHAP EFE NARAMAN'
    # = karakter VAHAP + aktör Efe Karaman) token-sayısı farkı yüzünden FİRE ETMEZ → kimlik kapısı açılmaz
    # → düzeltme hiç çalışmaz (BEYAZ BALİNA 6 garble isimle kaldı). Pencere-overlap kapıyı açar; yanlış-film
    # OCR'a uymadığından fuzzy_ov<2 kalır → açılmaz (güvenli, validation'da kanıtlandı). Fail-safe.
    _FUZZY_DBQC = os.environ.get("MITAS_FUZZY_DBQC", "").strip().lower() in ("1", "true", "on", "yes")
    _auth_cast = cc.get("otoriter_cast") or []
    # credit_kb_lookup garble cast'le crosscheck'i çağırınca VERIFICATION başarısız → KAYNAK_YOK → otoriter_cast
    # NULL döner (film DB'de title+year ile VAR olsa bile; BEYAZ BALİNA imdb_id=tt7377934 bulundu ama cast=null).
    # Flag açıkken cast'i title+year ile DOĞRUDAN çek (cast-verification BYPASS). Wrong-film koruması = aşağıdaki
    # ≥2 window-overlap gate'i: yanlış filmin kadrosu OCR'a uymaz → fuzzy_ov<2 → kimlik açılmaz. Fail-safe.
    if _FUZZY_DBQC and not _auth_cast and title:
        try:
            # NOT: run_ocr_json TEK-SATIR JSON arar; credit_crosscheck PRETTY-PRINT (çok-satır) basar →
            # run_ocr_json parse edemez. Kendi çok-satır regex parse'ımızla doğrudan çağır (PY_OCR=duckdb'li).
            _r = subprocess.run([PY_OCR, os.path.join(HERE, "credit_crosscheck.py"),
                                 "--baslik", title, "--yonetmen", "", "--yil", str(a.year or "")],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            _m = re.search(r"\{.*\}", _r.stdout or "", re.S)
            if _m:
                _auth_cast = (json.loads(_m.group(0)).get("otoriter_cast") or [])
        except Exception:
            _auth_cast = []
    _fuzzy_ov = 0
    if _FUZZY_DBQC and _cc is not None and hasattr(_cc, "cast_overlap_fuzzy"):
        try:
            _fuzzy_ov = _cc.cast_overlap_fuzzy(cast, _auth_cast)
        except Exception:
            _fuzzy_ov = 0
    # KİMLİK DOĞRULANDI mı: read yönetmeni TEYİT aldı YA DA okunan cast otoriteyle >=2 örtüştü (fuzzy dahil)
    kimlik_dogru = (verdict == "TEYİT") or (cast_ov >= 2) or (_fuzzy_ov >= 2)
    # YÖNETMEN — KIRMIZI ÇİZGİ (2026-06-07, Çağatay): KB-fill YOK. Yönetmen OCR-otorite.
    #   • OCR boş → "okunamadı" (KB'den DOLDURMA — "her şeyi okuyacağız" diye bir şey yok).
    #   • OCR var + kimlik doğrulandı + KB yönetmeni var:
    #       OCR ~ KB (name_match/name_close) → KANONİK KB yazımı (fuzzy YAZIM düzelt). ✅
    #       eşleşmezse (ör. "ABRURRAK ROROSKO" garble) → fuzzy hiçbir yere koyamaz → "okunamadı".
    #   • OCR var + (KB yok / kimlik yok) → OCR'ı AYNEN koru (doğrulayacak şey yok).
    yon_kaynak = "kareler"
    yon_ocr_teyit = False                       # OCR yönetmeni KB ile BAĞIMSIZ teyit edildi mi (cast-ADD çapası)
    if yon and _cc is not None and kimlik_dogru and auth_yon:
        _yeni = []
        for _d in yon:
            _m = next((a for a in auth_yon if _cc.name_match(_d, a)), None) \
                 or next((a for a in auth_yon if _cc.name_close(_d, a)), None)
            if _m and _m not in _yeni:
                _yeni.append(_m)
        if _yeni:
            yon = _yeni; yon_kaynak = "kareler (KB yazım teyitli)"; yon_ocr_teyit = True
        else:
            yon = []; yon_kaynak = "okunamadı (OCR yönetmen KB ile eşleşmedi; zorlanmadı)"
    elif not yon:
        yon_kaynak = "okunamadı (kareden okunmadı; KB-fill YOK)"
    # else: OCR var ama KB yok/kimlik yok → OCR korunur (kaynak=kareler)
    # cast: OCR/jenerik kadrosu MUTLAK OTORİTE — liste (uzunluk+sıra) OCR'dan, KB ile EZİLMEZ.
    # KB yalnız OKUNAN ismin YAZIMINI düzeltir (Ahmet Cimcir→Cemcir): her OCR ismi için
    # otoriter_cast'ta name_match ile eş ara; eşleşirse SADECE o ismi kanonik haliyle değiştir,
    # eşleşmezse OCR ismini AYNEN koru. KB'de olup OCR'da olmayan ismi EKLEME.
    auth = cc.get("otoriter_cast") or _auth_cast   # FUZZY-DBQC: title+year fallback cast dahil (flag-kapılı)
    cast_add_tier = None                        # KB cast-ekleme kademesi (rapora yazılır; ORTA→Kontrol)
    if kimlik_dogru and auth and _cc is not None:
        duz = []
        strict_hits = 0                         # OCR isminin KB'de SIKI tam-ad karşılığı (kimlik gücü)
        for nm in cast:
            # önce SIKI eşitlik (aynı kişi kesin), tutmazsa OCR-misread yazım düzeltmesi (Cimcir→Cemcir)
            _se = next((a for a in auth if _cc.name_match(nm, a)), None)
            if _se:
                strict_hits += 1
            es = _se or next((a for a in auth if _cc.name_close(nm, a)), None)
            # FUZZY-DBQC: name_match/name_close tutmadıysa GÖMÜLÜ-PENCERE ile dene (garble+karakter-adı:
            # 'VAHAP EFE NARAMAN'→'Efe Karaman'). Flag-kapılı; yüksek eşik (0.80) yanlış-snap'i keser.
            if not es and _FUZZY_DBQC and hasattr(_cc, "name_close_window"):
                es = next((a for a in auth if _cc.name_close_window(nm, a)), None)
            duz.append(es if es else nm)
        cast = duz
        # CAST-ADD (flag MITAS_KB_CAST_ADD, default KAPALI): KB'nin OCR'da OLMAYAN kadrosunu EKLE.
        # ASLA ezme/yeniden sırala — OCR isimleri ÖNDE kalır, eklenenler SONRA. Kimlik GERÇEKTEN
        # emin olmalı (iki bağımsız çapa). GÜÇLÜ: OCR-teyitli yönetmen + ≥3 SIKI cast → Hazır.
        # ORTA: yönetmen yok ama ≥4 SIKI cast ve OCR-cast'ın ÇOĞUNLUĞU → Kontrol (insan göz atsın).
        if _ADD_ON:
            _ocr_n = max(1, len([c for c in cast if str(c).strip()]))
            if yon_ocr_teyit and strict_hits >= 3:
                cast_add_tier = "GUCLU"
            elif strict_hits >= 4 and strict_hits >= (_ocr_n + 1) // 2:
                cast_add_tier = "ORTA"
            if cast_add_tier:
                for _an in auth:                # NOT: 'a' argparse namespace'i — döngüde EZME (bug)
                    if not any(_cc.name_match(_an, x) or _cc.name_close(_an, x) for x in cast):
                        cast.append(_an)        # OCR'dan SONRA ekle (otorite sırası korunur)
    # ── QC2 (flag MITAS_QC2, default KAPALI): kimlik-önce yönetmen-fill + cast garble "imza-yokluğu" temizleme ──
    #    credit_qc_gates İZOLE modül (saf name_match, duckdb yok). YALNIZ kimlik KİLİTLİ (verdict==TEYİT veya
    #    cast_ov>=2) iken çalışır. Fail-safe: herhangi hata → mevcut yon/cast AYNEN (pipeline ASLA bozulmaz).
    _web_afis = None   # QC2-web afişi line 357'deki cc.get("afis") yeniden-atamasında KAYBOLMASIN
    _cast_garble = []  # OCR-otorite (A+A): KB-imzasız (garble şüpheli) OCR cast isimleri → SİLİNMEZ, KONTROL bayrağı
    if os.environ.get("MITAS_QC2", "").strip().lower() in ("1", "true", "on", "yes"):
        try:
            import credit_qc_gates as _qc2
            # ── QC2 katman-b: WEB/KÖPRÜ KİMLİK KATMANI ──
            # Kimlik cast-örtüşmesiyle KURULAMAZSA (cast boş/çöp → cast_ov<2 → kimlik_dogru=False)
            # ÇAPA-1 (yönetmen-çapası, KB) veya ÇAPA-2 (TMDB) ile kimlik kur.
            # Flag: MITAS_QC2_WEB — default AÇIK (MITAS_QC2'ye bağlı).
            # Yanlış>boş kuralı: çapalardan hiçbiri GÜVENLE kilitlenemezse → BOŞ bırak (KONTROL).
            _qc2_web_on = os.environ.get("MITAS_QC2_WEB", "1").strip().lower() not in ("0", "false", "off", "no")
            if _qc2_web_on and not kimlik_dogru:
                try:
                    _afis_now = cc.get("afis")  # afis henüz atanmamış — cc'den al
                    _kb2 = _cc.CreditKB() if _cc is not None else None
                    if _kb2 is not None:
                        _web = _qc2.web_identity(
                            title, a.original, a.year,
                            ocr_director=(yon[0] if yon else None),
                            summary=None, kb=_kb2
                        )
                        _kb2.close()
                        if _web.get("locked"):
                            # kimlik web-çapasıyla kilitlendi → KB verilerini uygula
                            _web_dir = _web.get("director") or []
                            _web_cast = _web.get("cast") or []
                            _web_imdb = _web.get("imdb_id")
                            _web_tmdb = _web.get("tmdb_id")
                            # Yönetmen: OCR boşsa veya eşleşme yoksa web'den doldur (KIRMIZI ÇİZGİ: OCR+çapa)
                            if not yon and _web_dir:
                                yon = [_web_dir[0]]
                                yon_kaynak = f"QC2-web: yönetmen-doldur ({_web.get('method')})"
                            # cast: web'den gelen gerçek cast'i kimlik referansı olarak kullan
                            # identity_first_cast mantığıyla: OCR cast'i boşsa doğrudan web cast'ini al
                            if not cast and _web_cast:
                                cast = _web_cast[:8]
                                rapor["adimlar"]["qc2_web_cast_kaynak"] = "web"
                            elif cast and _web_cast:
                                # OCR-OTORİTE KANUNU (2026-06-13): OCR cast OKUDUYSA (garble olsa bile),
                                # versiyon-belirsiz web cast'iyle EZME YOK — ne değiştir, ne at, ne kanonikle.
                                # (Web title+year kilidi yanlış-versiyon olabilir; OCR'ı ezmek = Ahmet→Mehmet.)
                                # Web cast yalnız ÖNERİ olarak rapora yazılır; film zaten KONTROL'e gider
                                # (versiyon cast-teyitsiz) → insan OCR'ı görür, web önerisini değerlendirir.
                                rapor["adimlar"]["qc2_web_cast_oneri"] = _web_cast[:8]
                            # afiş: web kimlik ID'siyle çek
                            if not _afis_now and (_web_imdb or _web_tmdb):
                                try:
                                    _pf2 = _load("pf2", os.path.join(PDFMITAS, "poster_fetch.py"))
                                    _pp2 = _pf2.fetch_poster(
                                        title, afis_out,
                                        original=a.original, year=a.year,
                                        cast=(_web_cast or []),
                                        crew=([("Yönetmen", [_web_dir[0]])] if _web_dir else None),
                                        imdb_id=_web_imdb, tmdb_id=_web_tmdb
                                    )
                                    if poster_ok(_pp2):
                                        afis = _pp2
                                        _web_afis = _pp2   # line 357 cc.get("afis") EZMESİN
                                except Exception as _pfe:
                                    sys.stderr.write(f"[uyari] QC2-web afiş hatası: {_pfe}\n")
                            # auth_yon güncellenir (boş-yönetmen web'den DOLDURULABİLİR = destek).
                            # auth (cast) web'den GÜNCELLENMEZ: katman-a identity_first_cast OCR cast'i
                            # web ile EZMESİN (OCR-otorite kanunu). Web cast yalnız öneri (yukarıda raporda).
                            auth_yon = _web_dir[:3] if _web_dir else auth_yon
                            kimlik_dogru = True  # web-çapası kilitledi
                            rapor["adimlar"]["qc2_web"] = {
                                "method": _web.get("method"),
                                "kaynak_izi": _web.get("kaynak_izi"),
                                "imdb_id": _web_imdb, "tmdb_id": _web_tmdb,
                                "web_yonetmen": _web_dir, "web_cast_n": len(_web_cast),
                            }
                        else:
                            rapor["adimlar"]["qc2_web"] = {
                                "method": None, "kaynak_izi": _web.get("kaynak_izi"),
                                "neden": "çapa kilitlenemedi → KONTROL (yanlış>boş)"
                            }
                except Exception as _we:  # noqa: BLE001
                    sys.stderr.write(f"[uyari] QC2-web atlandı: {_we}\n")
                    rapor["adimlar"]["qc2_web"] = {"method": None, "kaynak_izi": f"hata: {_we}"}
            # ── QC2 katman-a: mevcut graftlar (kimlik kilitliyse) ──
            if (not yon) and kimlik_dogru and auth_yon:     # boş/çelişki-temizlenmiş yönetmen + kimlik kilitli → KB-fill
                yon = [auth_yon[0]]
                yon_kaynak = "QC2: KB-fill (kimlik-kilitli)"
            # cast: OCR-OTORİTE KANUNU (A+A 2026-06-13) — KB ile DÜŞÜRME/EKLEME YOK. Cast ana-blokta
            # (yukarıda) KB-kanonik yazıma çevrildi + okunan KORUNDU; burada DOKUNULMAZ.
            # (Eski identity_first_cast drop+add KALDIRILDI → Ahmet→Mehmet + non-OCR-ekleme önlendi.)
            # NOT: "garble→KONTROL" otomatik bayrağı DEVRE DIŞI — KB-imza sinyali GÜVENİLMEZ: KB'de yalnız
            # top-billed cast var, GERÇEK yan-oyuncuyu (Marvin J. McIntyre / John Santucci) da garble
            # işaretliyor → kütlesel yanlış-KONTROL. Güvenilir garble tespiti (KB-dışı sinyal) AYRI İŞ.
            # _cast_garble [] kalır → cross_check.cast_garble=False (plumbing hazır, detektör gelince açılır).
            # yapımcı: OCR-OTORİTE — KB ile DÜŞÜRME/EKLEME YOK (eski identity_first_producer KALDIRILDI).
            # OCR yapımcısı korunur; boşsa alt-satırda KB'den DOLDURULUR (destek).
        except Exception as _qe:  # noqa: BLE001 — QC2 fail-safe: pipeline'ı ASLA bozma
            sys.stderr.write(f"[uyari] QC2 atlandı: {_qe}\n")
    if not yap and cc.get("yapimci"):
        yap = cc["yapimci"]
    yap = _split_dedup_names(yap)[:3]               # "&"/"ve" birlesik bol + tekrar ele, sonra en fazla 3 yapimci
    tur = cc.get("tur") or "—"
    afis = _web_afis or cc.get("afis")   # QC2-web afişi ÖNCELİKLİ (KB'de afiş yok ama web bulduysa korunur)
    rapor["adimlar"]["cross_check"] = {"verdict": verdict, "kimlik_dogru": kimlik_dogru,
                                       "yonetmen_kaynak": yon_kaynak, "yon_ocr_teyit": yon_ocr_teyit,
                                       "yapimci": yap, "tur": tur, "cast_ortusme": cast_ov,
                                       "cast_add_tier": cast_add_tier, "afis": bool(afis),
                                       "cast_garble": bool(_cast_garble)}

    # 3) v4 d kur + render
    cast = _split_dedup_names(cast)           # Fix 1: "&"/tekrar böl+ele (GUILLAUME GOUIX ×2 vb.)
    castU = nn.upper_names(cast[:8])
    # özet büyük-harfi için isim-farkındalık: cast+yön+yap HAM adları (yabancı→ASCII, Türkçe→İ)
    _ozet_names = [n for n in (list(cast)
                               + (yon if isinstance(yon, (list, tuple)) else [yon])
                               + (yap if isinstance(yap, (list, tuple)) else [yap]))
                   if n and str(n).strip() and str(n).strip() != "—"]
    crew = [("Yönetmen", yon), ("Yapımcı", yap)]
    crew = [(r, x) for r, x in crew if x]
    crewU = nn.upper_crew(crew) if crew else [("Yönetmen", ["—"])]
    sk = [x for x in meta.get("ses_kanallari", []) if x and str(x).strip().upper() not in ("EFEKT", "EF")]  # Fix 4
    poster = afis if poster_ok(afis) else None
    now = datetime.datetime.now().strftime("%d.%m.%Y · %H:%M")
    # Altyazı/orijinal: XML orijinal-ad (a.original) BİRİNCİL; yoksa KB'nin doğrulanmış orijinal
    # adı (eslesen_film) — AMA YALNIZ kimlik GÜÇLÜ doğrulanmışsa (verdict TEYİT veya ≥3 SIKI cast,
    # AFİŞ kapısıyla AYNI eşik). Böylece "Cheaper by the Dozen" gibi DOĞRU orijinal ad gösterilir;
    # "Red Flag" gibi YANLIŞ title-only çakışma (kimlik doğrulanmaz → afiş de yok) altyazıya GİREMEZ.
    _kimlik_guclu = (verdict == "TEYİT") or (cast_ov >= 3)
    _orig_raw = a.original or (cc.get("eslesen_film") if _kimlik_guclu else None)
    # XML <TITLE> yok + yerel-KB kimlik de zayıf → KADRO-KONSENSÜS fallback (credit_identity:
    # BAŞLIK değil KADRODAN keşfeder; başlık yokken yerel-KB bulamadığında tek çare). 3. kademe
    # (öncelik XML > yerel-IMDb KB > TMDB-kadro). Çağatay 2026-06-08: XML her zaman olmayabilir,
    # çalışsın. SADECE KESİN; afiş çift-teyitli (id + poster_fetch cast-doğrulaması); exception-safe.
    if not _orig_raw:
        try:
            import credit_identity as _ci
            _id2 = _ci.resolve(cast, (yon[0] if yon else None), max_year=(a.year or None))
            if _id2 and _id2.get("status") == "KESIN":
                _orig_raw = _id2.get("original_title") or None
                if not poster and _id2.get("tmdb_id"):
                    try:
                        _pf = _load("pf", os.path.join(PDFMITAS, "poster_fetch.py"))
                        _pp = _pf.fetch_poster(title, afis_out, original=(_orig_raw or None),
                                               year=(a.year or None), cast=cast,
                                               crew=([("Yönetmen", yon)] if yon else None),
                                               tmdb_id=_id2.get("tmdb_id"))
                        if poster_ok(_pp):
                            poster = _pp
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001 — fallback PDF'i ASLA bozmaz
            pass
    _sub = up_o(_orig_raw) if _orig_raw else None
    if _sub and nn.ascii_fold(_sub).upper() == nn.ascii_fold(title).upper() \
            and meta.get("ana_dil", "—").upper() in ("TR", "—", ""):
        _sub = None                                 # Türkçe/bilinmeyen içerikte başlıkla aynı orijinal = gereksiz altyazı
    d = dict(profile=("DİZİ" if a.profile == "dizi" else "FİLM"), date=now,   # Fix 3a: profile hardcode → argparse
             title=nn.tr_upper(title), subtitle=_sub,  # Fix 2/3: foreign'da orijinal, Türkçe'de gereksizi gizle
             specs=[("ÇÖZÜNÜRLÜK", meta.get("res", "—")), ("TÜR", nn.tr_upper(tur)),
                    ("TOPLAM SÜRE", meta.get("dur", "—")), ("TRT KİMLİK", trt)],
             keywords=" ; ".join(castU) if castU else "—", cast=castU or ["—"], crew=crewU,
             ozet=ozet_v4(meta.get("ozet", ""), names=_ozet_names), ses_kanallari=sk,
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
