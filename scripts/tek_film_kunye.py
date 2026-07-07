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
import argparse, datetime, importlib.util, json, os, re, subprocess, sys, time
import debug_trace as dbg

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY_OCR = os.path.join(ROOT, "venvs", "ocr", "Scripts", "python.exe")
PDFMITAS = r"E:\MITAS\OCR-worktree\pdf-mitas"
AFIS_CACHE = r"E:\MITAS\_102_afis_cache"
OUT_DEFAULT = r"E:\MITAS\Mitas Output\GUNCEL_ORNEK"
# KB cast-ekleme kaldırıldı: KB yalnız OCR'da okunan ismin yazımını düzeltir, sıfırdan kişi eklemez.
_ADD_ON = False
# OCR-OTORİTE KANUNU: bu kapı IMDb/Wiki'de bulunmayan OCR-okunan gerçek ismi DÜŞÜRÜR/KIRPAR (kanun ihlali).
# Varsayılan KAPALI (opt-in). Deney için MITAS_GLOBAL_PERSON_GATE=1 ile açılabilir. (codex "1" yapmıştı = regresyon)
_GLOBAL_PERSON_GATE_ON = os.environ.get("MITAS_GLOBAL_PERSON_GATE", "0").strip().lower() not in ("0", "false", "off", "no")
# DEFERANS KANUNU (2026-06-28): Yönetmen ve Yapımcı YALNIZCA yapısal hattan (LLM-extractor) gelir.
# KB/web doldurma (OCR boşken eşlenen film/KB'den isim yazma) bu flag açıkken YAPILMAZ.
# YAZIM-DÜZELTME (name_match/name_close ile kanonikleştirme) KORUNUR — sadece DOLDURMA kesilir.
# "0"/"false"/"off" ile ESKİ DAVRANIŞA DÜŞ (fail-safe). Default AÇIK = "1".
_CREDIT_DEFERENCE = os.environ.get("MITAS_CREDIT_DEFERENCE", "1").strip().lower() \
    not in ("0", "false", "off", "no")
# OCR-TEYİTLİ YAPIMCI KB-FILL (2026-07-07, PARDAYYAN / Georges Campana):
# DEFERANS "OCR boş → boş kalır" der; AMA burada premis yanlış olabiliyor. Extraction (LLM/VL)
# yapımcıyı DÜŞÜRDÜYSE (ör. LLM model:null düştü + VL Fransızca "Producteur délégué" etiketini
# kaçırdı) ama KB-yapımcı adı HAM OCR metninde AÇIKÇA VARSA → bu FABRİKASYON DEĞİL; OCR-otorite
# geri-kazanımıdır (KB yalnız kanonik yazımı verir). Yönetmen "OCR~KB → kanonik yazım" ile SİMETRİK.
# Sadece yap-boş + KB-dolu + kimlik-teyitli dalını etkiler; OCR'da isim yoksa deferans AYNEN korunur.
# Default AÇIK; "0"/"false"/"off" ile ESKİ SAF-DEFERANS davranışına düş (fail-safe).
_YAPIMCI_OCR_CORROB = os.environ.get("MITAS_YAPIMCI_OCR_CORROB", "1").strip().lower() \
    not in ("0", "false", "off", "no")

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
    """pdf/kunye_teslim.md → {title, trt_id, res, dur, tur, ses_kanallari, ana_dil, altyazi, ozet, film_notu}"""
    d = {"title": None, "trt_id": None, "res": "—", "dur": "—", "tur": "",
         "ses_kanallari": [], "ana_dil": "—", "altyazi": "—", "ozet": "", "film_notu": []}
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
    # TÜR (2026-07-07, promote-denetimi ADDITIVE fix): res/dur regex'i "Tür:" kısmını atlıyordu →
    # meta hiç tür taşımıyordu; fix_kunye.build_fixed gibi tüketiciler tür-baseline'ı KAYBEDİYORDU.
    m = re.search(r"Tür:\s*([^·\n]+?)\s*(?:·\s*Süre:|\n|$)", txt)
    if m:
        d["tur"] = m.group(1).strip()
    # FİLM NOTU (2026-07-07, ADDITIVE): "## Film Notu" bölümündeki '- ' maddeleri (KİŞİ-TEYİT vb.)
    # eskiden hiç parse edilmiyordu → tüketiciler bu kutuyu baseline'dan devralamıyordu.
    m = re.search(r"##\s*Film Notu\s*\n(.*?)(?=\n##|\Z)", txt, re.S)
    if m:
        d["film_notu"] = [x.strip() for x in re.findall(r"-\s+(.+)", m.group(1)) if x.strip()]
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

def _parse_xml_roles_arg(raw):
    if not raw:
        return {}
    try:
        d = json.loads(raw)
        if not isinstance(d, dict):
            return {}
        return {
            "oyuncu": [str(x).strip() for x in (d.get("oyuncu") or []) if str(x).strip()],
            "yonetmen": [str(x).strip() for x in (d.get("yonetmen") or []) if str(x).strip()],
            "yapimci": [str(x).strip() for x in (d.get("yapimci") or []) if str(x).strip()],
        }
    except Exception:
        return {}

def _xml_pool(xml_roles, role):
    if role == "cast":
        return xml_roles.get("oyuncu") or []
    if role == "director":
        return xml_roles.get("yonetmen") or []
    if role == "producer":
        return xml_roles.get("yapimci") or []
    return []

def _strict_pool_hit(name, pool):
    if not name or not pool or _cc is None:
        return None
    for p in pool:
        if _cc.name_match(name, p):
            return {"name": p, "match": "exact", "distance": 0}
        if _cc.strict_name_close(name, p):
            return {"name": p, "match": "fuzzy", "distance": _cc.strict_name_distance(name, p)}
        if _cc.name_close(name, p):
            return {"name": p, "match": "fuzzy2", "distance": 2}
    return None

def _suffix_person_candidates(name):
    """Cast kartı bazen 'KARAKTER ADI + OYUNCU ADI' gelir: MAURA SALLY HAWKINS.
    Resmi kişi alanında karakter adı atılır, kişi adı suffix'ten çözülür."""
    toks = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿÇĞİıŞÖÜçğşöü']+", str(name or ""))
    toks = [t.strip("'") for t in toks if t.strip("'")]
    out = []
    if len(toks) < 3:
        return out
    # En kısa olası kişi adı önce: SALLY HAWKINS, sonra gerekirse uzun suffix.
    for i in range(len(toks) - 2, 0, -1):
        cand = " ".join(toks[i:])
        if cand and cand.lower() != str(name or "").strip().lower():
            out.append(cand)
    return out

def _person_gate_hit(name, role, *, xml_pool, film_pool, kb):
    hit = _strict_pool_hit(name, xml_pool)
    if hit:
        return hit, "xml"
    hit = _strict_pool_hit(name, film_pool)
    if hit:
        return hit, "film_pool"
    if kb is not None:
        try:
            m = kb.global_person_match(name, role=role, max_edits=1)
        except Exception:
            m = None
        if m:
            return ({
                "name": m.get("name"),
                "match": "fuzzy" if (m.get("distance") or 0) > 0 else "exact",
                "distance": m.get("distance") or 0,
            }, m.get("source") or "global")
    return None, None

def _gate_role_names(names, role, *, xml_roles=None, film_pool=None, kb=None):
    """Resmi kişi alanı kapısı: XML → film rol havuzu → global IMDb/Wiki kişi doğrulama."""
    names = [n for n in (names or []) if str(n).strip()]
    report = {"enabled": bool(_GLOBAL_PERSON_GATE_ON), "role": role, "kept": [], "dropped": []}
    if not _GLOBAL_PERSON_GATE_ON or _cc is None:
        return names, report
    xml_pool = _xml_pool(xml_roles or {}, role)
    film_pool = [x for x in (film_pool or []) if str(x).strip()]
    gate_available = bool(xml_pool or film_pool or (kb is not None and (getattr(kb, "imdb", None) or getattr(kb, "wd", None))))
    if not gate_available:
        report["unavailable"] = True
        return names, report
    out = []
    for nm in names:
        candidate_used = None
        hit, src = _person_gate_hit(nm, role, xml_pool=xml_pool, film_pool=film_pool, kb=kb)
        if not hit and role == "cast":
            for cand in _suffix_person_candidates(nm):
                hit, src = _person_gate_hit(cand, role, xml_pool=xml_pool, film_pool=film_pool, kb=kb)
                if hit:
                    candidate_used = cand
                    break
            if not hit:
                candidates = _suffix_person_candidates(nm)
                if candidates:
                    candidate_used = candidates[0]
                    hit = {"name": candidate_used, "match": "ocr_suffix", "distance": 0}
                    src = "ocr_suffix"
        if hit and hit.get("name"):
            canon = hit["name"]
            if not any(_cc.name_match(canon, x) or _cc.strict_name_close(canon, x) for x in out):
                out.append(canon)
            action = "KARAKTER_ADI_ATILDI" if candidate_used else ("FUZZY_DUZELDI" if (hit.get("distance") or 0) > 0 else "GECTI")
            report["kept"].append({"in": nm, "out": canon, "source": src,
                                   "match": hit.get("match"), "distance": hit.get("distance") or 0,
                                   "action": action, "candidate": candidate_used})
        else:
            report["dropped"].append({"in": nm, "action": "DUSTU", "reason": "tek-kelime veya global/rol eşleşmesi yok"})
    return out, report

def _yapimci_ocr_corroborated(kb_names, clip):
    """KB'den gelen yapımcı ad(lar)ını HAM OCR metniyle teyit et (OCR-otorite).

    DÖNÜŞ: ham OCR'da TÜM anlamlı token'ları (ascii-fold, >=3 harf) SÖZCÜK olarak geçen
    ad(lar)ın alt-listesi. Boş dönerse teyit YOK → deferans korunur (fabrikasyon önlenir).

    Neden: DEFERANS kapısı yalnız extraction çıktısına bakıyor; extraction yapımcıyı
    düşürdüğünde (LLM düştü / VL yabancı-etiket kaçırdı) ham OCR'da isim dururken KB-fill'i
    yanlışlıkla fabrikasyon sayıyordu. Bu yardımcı, ismin OCR'da FİZİKSEL varlığını doğrular:
    var ise KB yalnız kanonik yazımı sağlar (yönetmen "OCR~KB → kanonik" mantığıyla simetrik)."""
    if not _YAPIMCI_OCR_CORROB or not kb_names or not clip:
        return []
    blob = ""
    try:
        import glob as _g
        for _pat in ("ocr_ham.txt", "ocr_raw_all.txt"):   # ocr_ham önce (temiz), yoksa ham-hepsi
            _files = sorted(_g.glob(os.path.join(clip, "ocr", "*", _pat)), key=os.path.getmtime)
            if _files:
                with open(_files[-1], "r", encoding="utf-8", errors="ignore") as _f:
                    blob += "\n" + _f.read()
    except Exception:  # noqa: BLE001 — OCR okunamazsa teyit yok; akış ASLA bozulmaz
        return []
    if not blob.strip():
        return []
    _words = set(re.findall(r"[A-Z]{3,}", nn.ascii_fold(blob).upper()))   # sözcük-düzeyi (substring değil)
    out = []
    for nm in kb_names:
        _toks = [t for t in re.findall(r"[A-Z]{3,}", nn.ascii_fold(str(nm or "")).upper())]
        if _toks and all(t in _words for t in _toks):   # ismin TÜM parçaları OCR'da → teyitli
            out.append(nm)
    return out

def main():
    started = time.perf_counter()
    ap = argparse.ArgumentParser(description="Tek klip → temiz v4 künye PDF (uçtan uca)")
    ap.add_argument("--clip", required=True, help="klip klasörü (frames/ ve pdf/kunye_teslim.md içerir)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--original", default=None, help="orijinal ad (opsiyonel; cross-check'e yardım)")
    ap.add_argument("--year", default=None)
    ap.add_argument("--title", default=None, help="TR başlık override")
    ap.add_argument("--video-credits", default=None, help="önceden hesaplanmış video-okuma JSON (verilirse 1. adım atlanır)")
    ap.add_argument("--xml-roles", default="", help="XML rol ankrajı JSON: {oyuncu,yonetmen,yapimci}")
    ap.add_argument("--profile", default="film", choices=["film", "dizi"])    # Fix 3a
    ap.add_argument("--bolum", default=None)                                   # Fix 3a
    ap.add_argument("--tur", default=None, help="XML'den gelen tür (DRAMA vb.)")
    ap.add_argument("--notlar", default=None,
                    help="Film Notu listesi (JSON dizi veya ';' ayraçlı) — PDF'te FİLM NOTU kutusuna basılır")
    a = ap.parse_args()

    clip = a.clip
    giris = os.path.join(clip, "frames", "giris")
    cikis = os.path.join(clip, "frames", "cikis")
    md = os.path.join(clip, "pdf", "kunye_teslim.md")
    meta = parse_teslim_md(md)
    title = a.title or meta.get("title") or os.path.basename(clip.rstrip("/\\"))
    trt = meta.get("trt_id") or "—"
    xml_roles = _parse_xml_roles_arg(a.xml_roles)
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
                _lines, _ocr_source = _ctr.load_llm_lines_for_ocr(_ocrtxt[-1])
                _raw_context = _ctr.load_raw_context_for_ocr(_ocrtxt[-1])
                # ÜRETİM-SADAKAT fix (2026-07-07, Çağatay KONTROL-loop denetimi): _pipe_credit_text.py
                # (gerçek pipeline) 2026-07-03'ten beri dilim-OneOCR satırlarını (K1-PRIMARY, master_dilim/)
                # BİRİNCİL okuma girdisine katıyor (İHTİRAS/Norton tipi kayıpları önler + çift-ekran-imza
                # kapısını AÇAR). Bu inline blok o fix'ten HABERSİZ kalmıştı → tek_film_kunye ile re-run,
                # üretimden DAHA AZ bilgiyle okuyup üretimin yakaladığını kaçırıyordu (ör. H.G. Clouzot).
                # ADDITIVE (yalnız ek bağlam; read_credits_auto mantığı değişmez); aynı kill-switch miras.
                try:
                    import _pipe_credit_text as _pct
                    _dl = _pct._dilim_lines(_ocrtxt[-1])
                    if _dl:
                        _lines = list(_lines) + ["### MASTER-DILIM OKUMASI ###"] + _dl
                except Exception:  # noqa: BLE001 — dilim katkısı ASLA okuma akışını bozmaz
                    pass
                vc = _ctr.read_credits_auto(
                    _lines, title, dizi=(a.profile == "dizi"), raw_context_lines=_raw_context
                )
        except Exception as _e:  # noqa: BLE001
            sys.stderr.write(f"[uyari] OneOCR+GLM metin-okuma hata: {_e}\n")
    vc = vc or {}
    yon = vc.get("yonetmen") or []
    cast = vc.get("cast") or []
    yap = vc.get("yapimci") or []
    _yon_ocr_original = list(yon)
    dbg.emit("v4", "candidate_read",
             subject={"field": "video_okuma", "after": {
                 "yonetmen": yon, "cast": cast, "yapimci": yap,
                 "guven": vc.get("guven"),
             }, "reason": "v4 input credit extraction"},
             evidence={"video_credits_arg": bool(a.video_credits),
                       "nonlatin_source": bool(vc.get("nonlatin_source")),
                       "translit_method": vc.get("translit_method")},
             source={"module": "scripts/tek_film_kunye.py", "input_paths": [clip]})

    # FIX-1: Credit-cümle filtresi — "BASED ON THE POPEYE CHARACTERS..." gibi OCR jenerik
    # metinleri yönetmen olarak geçmesin. Kapı: uzun (>60 karakter) veya bilinen credit ifadesi.
    _CREDIT_STARTS = (
        "BASED ON", "CREATED BY", "CHARACTERS CREATED", "CHARACTERS BY",
        "ADAPTED FROM", "ADAPTED BY", "WRITTEN BY", "SCREENPLAY BY",
        "STORY BY", "ORIGINAL STORY", "FROM THE NOVEL", "FROM THE BOOK",
        "PRODUCED BY", "EXECUTIVE PRODUCER", "A FILM BY",
        # müzik/kurgu/foto/sunum kredisi — gerçek yönetmen adı bunlarla BAŞLAMAZ (2026-06-15)
        "ARRANGED BY", "SONGS BY", "SONGS ARRANGED", "MUSIC BY", "SCORE BY",
        "ORIGINAL SCORE", "ORIGINAL MUSIC", "SUPERVISED BY", "PRESENTED BY",
        "EDITED BY", "EDITING BY", "PHOTOGRAPHY BY", "CINEMATOGRAPHY BY",
        "LYRICS BY", "NARRATED BY", "DESIGNED BY", "PRODUCTION DESIGN",
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

    rapor["adimlar"]["video_okuma"] = {"yon": yon, "cast_okunan": cast, "guven": vc.get("guven"),
                                       "nonlatin_source": bool(vc.get("nonlatin_source")),
                                       "translit_method": vc.get("translit_method")}

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
    dbg.emit("kb", "external_lookup",
             subject={"field": "credit_kb_lookup", "before": {
                 "yonetmen": yon, "cast": cast, "yapimci": yap,
             }, "after": cc, "reason": "KB cross-check, producer/genre/poster lookup"},
             evidence={"args": cc_args, "verdict": cc.get("verdict"),
                       "cast_ortusme": cc.get("cast_ortusme"),
                       "otoriter_yonetmen": cc.get("otoriter_yonetmen"),
                       "otoriter_cast_count": len(cc.get("otoriter_cast") or []),
                       "afis": cc.get("afis")},
             source={"module": "scripts/tek_film_kunye.py",
                     "input_paths": [clip], "output_paths": [afis_out]})
    cast_ov = cc.get("cast_ortusme") or 0
    verdict = cc.get("verdict")
    auth_yon = cc.get("otoriter_yonetmen") or []
    # FUZZY-DBQC: garble/karakter-karışık OCR cast'i DB-otoriteye GÖMÜLÜ-PENCERE ile eşle. name_match/
    # name_close GARBLE'da (karakter-adı karışık: 'MAURA SALLY HAWKINS' = karakter MAURA + aktör Sally
    # Hawkins) token-sayısı farkı yüzünden FİRE ETMEZ → kimlik kapısı açılmaz → düzeltme çalışmaz. Pencere-
    # overlap kapıyı açar; yanlış-film OCR'a uymadığından fuzzy_ov<2 kalır → açılmaz (kimlik-kilidi same-title
    # koruması). DEFAULT AÇIK (2026-06-20): 11-film ölçümü SIFIR yanlış-snap + 2 film doğru temizlik
    # (SONSUZA KADAR MUTLULAR karakter-prefiks, SUNDOWN garble→kanonik); MITAS_FUZZY_DBQC=0 kapatır. Fail-safe.
    _FUZZY_DBQC = os.environ.get("MITAS_FUZZY_DBQC", "1").strip().lower() not in ("0", "false", "off", "no")
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
    #       eşleşmezse VE OCR okuması garble ise (ör. "ABRURRAK ROROSKO") → "okunamadı".
    #       eşleşmezse AMA OCR okuması TEMİZ/geçerli isimse → KB'yi güvenme, OCR'ı KORU
    #       (credit_validate.py DEMİR KURAL#3 "SESSİZ EZME YOK...OCR korunur" ile aynı ilke;
    #       İKİNCİ ŞANS/"Reuben Rose" kökü 2026-07-07: kare temiz "directed by REUBEN ROSE"
    #       diyor, KB başka-film/mahlas yüzünden "John Blanchard" diyor — eski kod OCR'ı
    #       KÖRLEMESİNE siliyordu, "yanlış > boş" kanununu TERSİNE çeviriyordu).
    #   • OCR var + (KB yok / kimlik yok) → OCR'ı AYNEN koru (doğrulayacak şey yok).
    yon_kaynak = "kareler"
    yon_ocr_teyit = False                       # OCR yönetmeni KB ile BAĞIMSIZ teyit edildi mi (cast-ADD çapası)
    _yon_before_kb = list(yon)
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
            # _valid_person_name TEK BAŞINA yetmez — yapısal kontrol ("iki büyük-harfli token")
            # "ABRURRAK ROROSKO" gibi anlamsız-ama-isim-şekilli OCR gürültüsünü de geçirir (ölçüldü).
            # İKİNCİ kapı: isim GENİŞ KB'de (imdb.names, bu filme özel değil) GERÇEK biri olarak
            # var mı? Gerçek-ama-bu-filme-KB'siz kişi (Reuben Rose) bulunur; saf gürültü bulunmaz.
            import credit_text_read as _ctr_vp
            _yon_kb_hit = False
            if all(_ctr_vp._valid_person_name(_d) for _d in yon):
                try:
                    _kb3 = _cc.CreditKB()
                    _yon_kb_hit = all(_kb3._imdb_people_by_folds([_cc.fold(_d)]) for _d in yon)
                except Exception:
                    _yon_kb_hit = False
            if _yon_kb_hit:
                yon_kaynak = "kareler (KB eşleşmedi ama OCR temiz + KB'de gerçek kişi → okunan korundu)"
            else:
                yon = []; yon_kaynak = "okunamadı (OCR yönetmen KB ile eşleşmedi; zorlanmadı)"
    elif not yon:
        yon_kaynak = "okunamadı (kareden okunmadı; KB-fill YOK)"
    if _yon_before_kb != yon:
        dbg.emit("fuzzy", "candidate_changed" if yon else "candidate_dropped",
                 status="ok" if yon else "warn",
                 subject={"field": "yonetmen", "before": _yon_before_kb, "after": yon,
                          "reason": yon_kaynak},
                 evidence={"kimlik_dogru": kimlik_dogru, "auth_yon": auth_yon,
                           "verdict": verdict, "cast_ortusme": cast_ov,
                           "fuzzy_cast_overlap": _fuzzy_ov},
                 source={"module": "scripts/tek_film_kunye.py"})
    # else: OCR var ama KB yok/kimlik yok → OCR korunur (kaynak=kareler)
    # cast: OCR/jenerik kadrosu MUTLAK OTORİTE — liste (uzunluk+sıra) OCR'dan, KB ile EZİLMEZ.
    # KB yalnız OKUNAN ismin YAZIMINI düzeltir (Ahmet Cimcir→Cemcir): her OCR ismi için
    # otoriter_cast'ta name_match ile eş ara; eşleşirse SADECE o ismi kanonik haliyle değiştir,
    # eşleşmezse OCR ismini AYNEN koru. KB'de olup OCR'da olmayan ismi EKLEME.
    auth = cc.get("otoriter_cast") or _auth_cast   # FUZZY-DBQC: title+year fallback cast dahil (flag-kapılı)
    cast_add_tier = None                        # geriye dönük şema alanı; KB cast-ekleme artık yapılmaz
    _cast_before_kb = list(cast)
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
        # Sıfırdan KB cast ekleme yok. strict_hits yalnız kimlik gücü/rapor için tutulur;
        # cast listesi OCR'da okunan isimlerin yazım düzeltmeli halidir.
    if _cast_before_kb != cast:
        dbg.emit("fuzzy", "candidate_changed",
                 subject={"field": "cast", "before": _cast_before_kb, "after": cast,
                          "reason": "OCR cast names canonicalized with KB name_match/name_close/window fuzzy"},
                 evidence={"kimlik_dogru": kimlik_dogru, "auth_cast_count": len(auth),
                           "verdict": verdict, "cast_ortusme": cast_ov,
                           "fuzzy_cast_overlap": _fuzzy_ov},
                 source={"module": "scripts/tek_film_kunye.py"})
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
                            # Yönetmen: DEFERANS açıkken OCR boş dahi olsa web'den DOLDURMA YAPILMAZ.
                            # (Yönetmen yalnız LLM-extractor yapısal hattından gelir.)
                            # Eski davranış (MITAS_CREDIT_DEFERENCE=0): OCR boşsa web'den doldur.
                            if not yon and _web_dir:
                                if _CREDIT_DEFERENCE:
                                    yon_kaynak = (f"deferans: QC2-web yönetmen-doldur atlandı "
                                                  f"({_web.get('method')}); OCR boş → alan boş kalır")
                                    sys.stderr.write(f"[deferans] yönetmen KB/web fill atlandı: {_web_dir}\n")
                                else:
                                    yon = [_web_dir[0]]
                                    yon_kaynak = f"QC2-web: yönetmen-doldur ({_web.get('method')})"
                            # cast: web'den gelen gerçek cast'i kimlik referansı olarak kullan.
                            # DEFERANS açıkken OCR cast boşsa web cast'i YAZILMAZ (OCR-otorite).
                            # Eski davranış: OCR cast boşsa web cast'ini doğrudan al.
                            if not cast and _web_cast:
                                if _CREDIT_DEFERENCE:
                                    rapor["adimlar"]["qc2_web_cast_kaynak"] = "deferans: web fill atlandı"
                                    sys.stderr.write(f"[deferans] cast KB/web fill atlandı (OCR boş)\n")
                                else:
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
                            dbg.emit("kb", "external_lookup",
                                     subject={"field": "qc2_web", "after": rapor["adimlar"]["qc2_web"],
                                              "reason": "QC2 web identity locked"},
                                     evidence={"locked": True, "director": _web_dir,
                                               "cast_count": len(_web_cast), "afis": _web_afis},
                                     source={"module": "scripts/tek_film_kunye.py",
                                             "input_paths": [clip], "output_paths": [afis_out]})
                        else:
                            rapor["adimlar"]["qc2_web"] = {
                                "method": None, "kaynak_izi": _web.get("kaynak_izi"),
                                "neden": "çapa kilitlenemedi → KONTROL (yanlış>boş)"
                            }
                            dbg.emit("kb", "external_lookup", status="warn",
                                     subject={"field": "qc2_web", "after": rapor["adimlar"]["qc2_web"],
                                              "reason": "QC2 web identity could not lock"},
                                     evidence={"locked": False},
                                     source={"module": "scripts/tek_film_kunye.py",
                                             "input_paths": [clip]})
                except Exception as _we:  # noqa: BLE001
                    sys.stderr.write(f"[uyari] QC2-web atlandı: {_we}\n")
                    rapor["adimlar"]["qc2_web"] = {"method": None, "kaynak_izi": f"hata: {_we}"}
            # ── QC2 katman-a: mevcut graftlar (kimlik kilitliyse) ──
            if (not yon) and kimlik_dogru and auth_yon:     # boş/çelişki-temizlenmiş yönetmen + kimlik kilitli → KB-fill
                # DEFERANS açıkken KB-fill YAPILMAZ: yönetmen yalnız LLM yapısal hattından gelir.
                # Eski davranış (MITAS_CREDIT_DEFERENCE=0): kimlik kilitliyse KB'den doldur.
                if _CREDIT_DEFERENCE:
                    yon_kaynak = "deferans: KB-fill atlandı (kimlik-kilitli ama OCR boş → alan boş kalır)"
                    sys.stderr.write(f"[deferans] QC2 KB-fill yönetmen atlandı: {auth_yon}\n")
                else:
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
    # KİMLİK KAPISI (2026-06-22, BEKARLIK→Norman Lear): producer-fill director-fill (yukarıda 'kimlik-kilitli')
    # ile SİMETRİK olsun — kimlik kilitlenmemişse KB-yapımcı yazma. Savunma-derinliği: kaynak (credit_kb_lookup)
    # zaten kimlik kapılı, ama cc["yapimci"] başka yoldan dolsa bile burada da kapanır. Bayrak default-ON.
    # DEFERANS (2026-06-28): MITAS_CREDIT_DEFERENCE açıkken yapımcı KB-fill de YAPILMAZ.
    # Yapımcı da yalnız LLM yapısal hattından gelir; OCR boşsa boş kalır.
    # Eski davranış (MITAS_CREDIT_DEFERENCE=0): kimlik-kapılı KB fill devreye girer.
    _producer_gate = os.environ.get("MITAS_PRODUCER_IDENTITY_GATE", "1").strip().lower() not in ("0", "false", "off", "no")
    if not yap and cc.get("yapimci") and (kimlik_dogru or not _producer_gate):
        _kb_yap = cc["yapimci"]
        if not _CREDIT_DEFERENCE:
            yap = _kb_yap                                 # deferans KAPALI → eski davranış (tam KB-fill)
        else:
            # OCR-TEYİT (2026-07-07, PARDAYYAN/Campana): ham OCR'da KB-yapımcı adı VARSA fill FABRİKASYON
            # DEĞİL — OCR-otorite geri-kazanım (KB yalnız kanonik yazım). Yoksa saf-deferans (boş kalır).
            _yap_corrob = _yapimci_ocr_corroborated(_kb_yap, clip)
            if _yap_corrob:
                yap = _yap_corrob
                rapor["adimlar"]["yapimci_fill"] = f"OCR-teyitli KB-fill (ham OCR'da ad var → kanonik yazım): {_yap_corrob}"
                sys.stderr.write(f"[ocr-teyit] yapımcı KB-fill (OCR corroborated): {_yap_corrob}\n")
            else:
                rapor["adimlar"]["yapimci_fill"] = "deferans: KB-fill atlandı (ham OCR'da yapımcı adı yok → boş kalır)"
                sys.stderr.write(f"[deferans] yapımcı KB-fill atlandı (OCR-teyitsiz): {_kb_yap}\n")
    cast = _split_dedup_names(cast)
    yap = _split_dedup_names(yap)[:3]               # "&"/"ve" birlesik bol + tekrar ele, sonra en fazla 3 yapimci

    # GLOBAL KİŞİ KAPISI (2026-06-16): XML aynı rolde ilk ankraj; yoksa film havuzu; yoksa
    # global IMDb/Wiki kişi doğrulama. Tek kelime ve 1 harften fazla fuzzy resmi PDF alanına girmez.
    _gate_reports = {}
    if _GLOBAL_PERSON_GATE_ON and _cc is not None:
        _kb_gate = None
        try:
            _kb_gate = _cc.CreditKB()
            _yon_gate_in = yon or _yon_ocr_original
            yon, _gate_reports["director"] = _gate_role_names(
                _yon_gate_in, "director", xml_roles=xml_roles, film_pool=auth_yon, kb=_kb_gate
            )
            cast, _gate_reports["cast"] = _gate_role_names(
                cast, "cast", xml_roles=xml_roles, film_pool=auth, kb=_kb_gate
            )
            yap, _gate_reports["producer"] = _gate_role_names(
                yap, "producer", xml_roles=xml_roles, film_pool=(cc.get("yapimci") or []), kb=_kb_gate
            )
            _cast_garble = list((_gate_reports.get("cast") or {}).get("dropped") or [])
            if not yon and _yon_gate_in:
                yon_kaynak = "okunamadı (XML/film/global kişi kapısından geçmedi)"
        except Exception as _ge:  # noqa: BLE001
            sys.stderr.write(f"[uyari] global kişi kapısı atlandı: {_ge}\n")
        finally:
            try:
                if _kb_gate is not None:
                    _kb_gate.close()
            except Exception:
                pass
    tur = cc.get("tur") or a.tur or "—"
    # ── ANİMASYON TESPİTİ (2026-07-04, Çağatay): animasyonda oyuncu OLMAZ — jenerikteki isimler
    # seslendirme kadrosudur → OYUNCULAR + ANAHTAR SÖZCÜKLER boş bırakılır, FİLM NOTU açıklar.
    # ÇOK-NET çekim: XML türü (a.tur: "ÇİZGİ/ANİMASYON") + KB-TR türü (cc.tur: "Animasyon") +
    # HAM IMDb genre CSV'si (cc.tur_imdb: "Adventure,Animation,..." — TR-eşlemede ilk-2'ye
    # düşerken Animation kaybolsa bile HAM listede yakalanır; FERDİNAND/SİMBA tipi kaçaklar
    # bunun için). Tek kaynağın demesi YETER (kaçırma > yanlış-alarm; not salt-görsel, karar-dışı).
    def _is_animasyon(*vals):
        for _v in vals:
            _f = nn.ascii_fold(str(_v or "")).upper()
            if any(k in _f for k in ("ANIMASYON", "ANIMATION", "ANIMATED", "CIZGI")):
                return True
        return False
    # ÇOĞUNLUK-VETOSU (2026-07-05, NİNJA KAPLUMBAĞALAR kanıtı): tek-kaynak-yeter kuralı canlı-aksiyon
    # filmde (IMDb genre listesinde 'Animation' geçiyor diye) OKUNMUŞ gerçek cast'i gizledi. Yeni kural:
    # DOLU kaynaklar oylanır (xml / KB-TR / ham-IMDb); animasyon ancak anim-oyu > değil-oyu ise tetiklenir.
    # DEFİNE korunur (xml=ÇİZGİ/ANİMASYON + imdb=Animation → 2>1); NİNJA düzelir (yalnız imdb → 1<2).
    _anim_oy = _degil_oy = 0
    for _src in (cc.get("tur"), cc.get("tur_imdb"), a.tur):
        if not str(_src or "").strip() or str(_src).strip() == "—":
            continue
        if _is_animasyon(_src):
            _anim_oy += 1
        else:
            _degil_oy += 1
    anim = _anim_oy > _degil_oy
    # FİLM NOTU listesi: pipeline'dan gelen (--notlar: sessiz/jenerik-yok/XML-uyarı) + animasyon notu.
    film_notu = []
    if a.notlar:
        try:
            _nl = json.loads(a.notlar)
            film_notu = [str(x).strip() for x in _nl if str(x).strip()] if isinstance(_nl, list) else []
        except Exception:  # noqa: BLE001 — JSON değilse ';' ayraçlı düz metin kabul et
            film_notu = [s.strip() for s in str(a.notlar).split(";") if s.strip()]
    if anim:
        film_notu.insert(0, "ANİMASYON — oyuncu alanı kullanılmaz; jenerikteki isimler seslendirme kadrosudur.")
        rapor["adimlar"]["animasyon"] = {"tur": tur, "tur_imdb": cc.get("tur_imdb"), "xml_tur": a.tur,
                                         "cast_gizlendi": True}
    afis = _web_afis or cc.get("afis")   # QC2-web afişi ÖNCELİKLİ (KB'de afiş yok ama web bulduysa korunur)
    rapor["adimlar"]["cross_check"] = {"verdict": verdict, "kimlik_dogru": kimlik_dogru,
                                       "yonetmen_kaynak": yon_kaynak, "yon_ocr_teyit": yon_ocr_teyit,
                                       "yapimci": yap, "tur": tur, "cast_ortusme": cast_ov,
                                       "cast_add_tier": cast_add_tier, "afis": bool(afis),
                                       "cast_garble": bool(_cast_garble),
                                       "global_person_gate": _gate_reports,
                                       "xml_roles": {k: len(v) for k, v in xml_roles.items()}}

    # ── BİRLEŞİK QC BLOĞU (flag MITAS_QC_BLOCK, default KAPALI): HAM OCR'dan temizle+doldur+karar ──
    #    Açıkken cast/yön/yap OTORİTESİ credit_qc_block'tan (çöp ele + yazım düzelt + Latin-çevir +
    #    İ-politikası); kararı rapora yazılır (mitas_pipeline tüketir). Default kapalı → mevcut yol AYNEN
    #    (sıfır regresyon). Fail-safe: blok hata verirse mevcut cast/yön/yap AYNEN kalır.
    _qcb_res = None
    if os.environ.get("MITAS_QC_BLOCK", "").strip().lower() in ("1", "true", "on", "yes"):
        try:
            import credit_qc_block as _qcb
            # OCR-OTORİTE DENETİM groundtruth (flag MITAS_QC_OTORITE_AUDIT; SIFIR-ROUTE) — ham-OCR
            # (ocr_raw_all.txt, clean ÖNCESİ) isim-kümesi; clean'in sildiği başrolü (KEDİ GÖZÜ: ELEANOR
            # PARKER) tespit için. YENİ local var; mevcut _raw_context'e DOKUNMAZ (video_credits dalı onu
            # atamaz → NameError tuzağından kaçınılır). Flag kapalıyken yüklenmez → mevcut davranış AYNEN.
            _raw_gt = None
            if any(os.environ.get(_f, "").strip().lower() in ("1", "true", "on", "yes")
                   for _f in ("MITAS_QC_OTORITE_AUDIT", "MITAS_QC_FLOORFILL_OCRGUARD")):
                try:
                    import glob as _glob_gt
                    _rawf = sorted(_glob_gt.glob(os.path.join(clip, "ocr", "*", "ocr_raw_all.txt")),
                                   key=os.path.getmtime)
                    if _rawf:
                        with open(_rawf[-1], "r", encoding="utf-8", errors="ignore") as _rf:
                            _raw_gt = [ln.strip() for ln in _rf if ln.strip()]
                except Exception:  # noqa: BLE001 — groundtruth yüklenemezse sinyal boş, akış bozulmaz
                    _raw_gt = None
            _nc_on = (os.environ.get("MITAS_QC_NONCAST_FILTER", "").strip().lower()
                      in ("1", "true", "on", "yes"))
            _rcl = (_raw_context if (_nc_on and "_raw_context" in locals()) else None)
            _qcb_res = _qcb.qc_credit_block(
                _yon_ocr_original, (vc.get("cast") or []), (vc.get("yapimci") or []),
                title=title, original=a.original, year=a.year,
                ozet=meta.get("ozet", ""), afis_yolu=(afis if poster_ok(afis) else None),
                xml_roles=xml_roles, raw_names_groundtruth=_raw_gt,
                nonlatin_source=bool(vc.get("nonlatin_source")),   # Latin-dışı kaynak → KONTROL (erken-translit, 2026-06-22)
                raw_context_lines=_rcl,)   # C5a: non-cast filtre bağlamı (MITAS_QC_NONCAST_FILTER, default-OFF)
            if _qcb_res.get("temiz_cast"):           # OCR-otorite: temiz alanları kullan (boşsa eskiyi koru)
                cast = list(_qcb_res["temiz_cast"])
            # GUARD-EZME FIX (117-film taraması 2026-07-03; JERICO APARTMANI ×2 + TILSIMLI DÜNYA kanıtı):
            # qc_block'a girdi olarak _yon_ocr_original veriliyor (otorite-audit için bilinçli). Ama
            # üst-akış kapıları (kimlik/global-kişi/credit-cümle) yon'u BOŞALTTIYSA, qc_block'un o ham
            # adaydan dirilttiği "temiz_yon" kapı kararını EZİYORDU → yanlış yönetmen PDF'e geri geliyordu.
            # Kural: kapı kararı NİHAİ ("okunamadı > yanlış oku") — qc_block yalnız yon DOLUYKEN
            # yazım-düzeltme uygular; boş yon'u dirilten aday rapora yazılır ama alana YAZILMAZ.
            _qcb_yon = list(_qcb_res.get("temiz_yon") or [])
            _yon_resurrect_blocked = []
            if yon:
                yon = list(_qcb_yon or yon)
            elif _qcb_yon:
                _yon_resurrect_blocked = _qcb_yon
            if _qcb_res.get("temiz_yap"):
                yap = list(_qcb_res["temiz_yap"])
            rapor["adimlar"]["qc_block"] = {
                "karar": _qcb_res["karar"], "kontrol_tip": _qcb_res["kontrol_tip"],
                "gerekceler": _qcb_res["gerekceler"], "kimlik": _qcb_res["kimlik"],
                "floor": _qcb_res["floor"], "kaynak_izi": _qcb_res.get("kaynak_izi", []),
                "yon_resurrect_blocked": _yon_resurrect_blocked or None,
                "otorite_audit": _qcb_res.get("otorite_audit")}
        except Exception as _qbe:  # noqa: BLE001 — fail-safe: bloğu atla, mevcut yol devam
            sys.stderr.write(f"[uyari] qc_block atlandı: {_qbe}\n")

    # 3) v4 d kur + render
    cast = _split_dedup_names(cast)           # Fix 1: "&"/tekrar böl+ele (GUILLAUME GOUIX ×2 vb.)
    try:
        _cap = int(os.environ.get("MITAS_CAST_CAP", "10") or 10)  # C-fix-canli 2026-06-29: default 8→10
        if not (1 <= _cap <= 50):
            _cap = 10
    except Exception:  # noqa: BLE001 — bozuk değer → varsayılan 10
        _cap = 10
    # ── İSİM-DÜZEYİ TEYİT SÜZGECİ (2026-07-05, Çağatay kuralı): "teyitsiz tek isim PDF'i rehin
    #    almaz — güvendiğini ver, 8 değil 7 kişiyle gitsin." Kişi KB-ONAY değilse İSİM düşer
    #    (rapor+Film-Notu'na yazılır, kaybolmaz); PDF teyitli çekirdekle ONAYLI'ya gider.
    #    Garble-klonlar (KIEN) otomatik temizlenir. MITAS_TEYITSIZ_DUS=0 kill-switch.
    _teyitsiz_cast, _teyitsiz_yon = [], []
    if (not anim) and (a.profile != "dizi") and cast and os.environ.get("MITAS_TEYITSIZ_DUS", "1").strip().lower() not in ("0", "false", "off", "no"):
        try:
            import credit_video_read as _cvx
            _kbx = _cvx.KB()
            # ÇİFT-OKUMA imzası (basamak-2): KB'de olmayan isim, FRAME-kunye VE master-DİLİM'de
            # bağımsız okunmuşsa 'ekran-çift-imzalı' sayılır ve KURTULUR (KB-kapsam-dışı yerel
            # oyuncular için — Çağatay: 'doğru okuduğumu kaçırma').
            import glob as _gx
            def _fold_tx(t): return nn.ascii_fold(t).upper()
            _fr_txt = ""
            # "-fb" SUFFIX kontrolü (2026-07-07 fix): eski "-fb" not in q TAM-YOL substring'iydi —
            # rastgele job-hash "fb" ile başlarsa (ör. "ocr-fb9fa3e4", ANGOLA'DAN KAÇIŞ) o filmin
            # TEK ocr klasörünü yanlışlıkla dışlıyordu. Doğru desen: yalnız klasör-ADI "-fb" ile
            # BİTİYORSA fallback-kardeş say (bkz _pipe_credit_text.py:46 aynı doğru desen).
            _ks = sorted([q for q in _gx.glob(os.path.join(clip, "ocr", "ocr-*", "kunye.txt"))
                          if not os.path.basename(os.path.dirname(q)).endswith("-fb")], key=os.path.getmtime)
            if _ks: _fr_txt = _fold_tx(open(_ks[-1], encoding="utf-8", errors="ignore").read())
            _dl_txt = ""
            _dp = os.path.join(clip, "master_dilim", "dilim_oneocr.txt")
            if os.path.isfile(_dp): _dl_txt = _fold_tx(open(_dp, encoding="utf-8", errors="ignore").read())
            _cift_imza = []
            _fuzzy_onay = []
            def _fz_kb(_nm, _role):
                # FUZZY-TEYIT basamak-1.5 (dünya-pratiği: JW+prefix-blok+tek-güçlü-aday; DuckDB jw).
                try:
                    if not getattr(_kbx, "con", None): return False
                    _t = nn.ascii_fold(_nm).lower().split()
                    if len(_t) < 2: return False
                    _q = " ".join(_t)
                    rows = _kbx.con.execute(
                        "SELECT primaryProfession, jaro_winkler_similarity(strip_accents(lower(primaryName)), ?) AS jw "
                        "FROM names WHERE strip_accents(lower(primaryName)) LIKE ? "
                        "AND length(primaryName) BETWEEN ? AND ? ORDER BY jw DESC LIMIT 5",
                        [_q, _t[0][0] + "%", len(_q) - 3, len(_q) + 3]).fetchall()
                    if not rows: return False
                    _esik = 0.92 if _role == "director" else 0.90
                    _best = rows[0][1] or 0
                    _snd = rows[1][1] if len(rows) > 1 else 0
                    if _best < _esik or (_best - (_snd or 0)) < 0.03: return False   # kararsız → abstain
                    _pr = set(x.strip() for x in str(rows[0][0] or "").split(","))
                    _ok = {"actor", "actress"} if _role != "director" else {"director"}
                    return bool(_pr & _ok)
                except Exception:
                    return False
            _kept = []
            for _n in cast:
                _v = _kbx.verify(_n, "actor")
                if _v == "ONAY" or _v == "meslek-bos":   # hakim-fix: KB'de kişi VAR ama meslek-alanı boş → KALIR
                    _kept.append(_n)
                elif _fz_kb(_n, "actor"):
                    _kept.append(_n); _fuzzy_onay.append(_n)   # garble-toleranslı KB-teyit (yazım OCR'da kalır)
                elif _fr_txt and _dl_txt and _fold_tx(_n) in _fr_txt and _fold_tx(_n) in _dl_txt:
                    _kept.append(_n); _cift_imza.append(_n)   # KB'siz ama çift-kaynak-ekran-teyitli
                else:
                    _teyitsiz_cast.append(_n)
            if _cift_imza:
                rapor["adimlar"].setdefault("teyit", {})["cift_imza"] = _cift_imza[:12]
            if _fuzzy_onay:
                rapor["adimlar"].setdefault("teyit", {})["fuzzy_kb"] = _fuzzy_onay[:12]
            if len(_kept) >= 3:
                cast = _kept
            else:
                # ÇAĞATAY-DÜZELTMESİ (2026-07-05): süzgeç cast'i <3'e düşürüyorsa BOŞ/GÜDÜK ONAYLI
                # OLMAZ — süzme İPTAL, liste AYNEN kalır, film KONTROL'e gider (mevcut reasons korunur).
                _teyitsiz_cast = []
                rapor["adimlar"]["teyit_iptal"] = "çekirdek<3 → süzgeç uygulanmadı, KONTROL-yolu"
            if yon:
                _yk = [_n for _n in yon if _kbx.verify(_n, "director") in ("ONAY", "meslek-bos")]
                _teyitsiz_yon = [_n for _n in yon if _n not in _yk]
                # hakim-fix (çok-yönetmen): KISMİ teyitte SİLME YOK — ekran-okuma aynen kalır (kimlik-çapası);
                # yalnız HİÇBİRİ teyitli değilse boş bırakılır (meşru-boş yolu).
                if _yk:
                    _teyitsiz_yon = []          # kısmi/tam teyit → yon AYNEN (silme yok)
                else:
                    yon = []
            if _teyitsiz_cast or _teyitsiz_yon:
                film_notu.append("KİŞİ-TEYİT — KB'de doğrulanamayan %d isim listeden çıkarıldı (raporda saklı)."
                                 % (len(_teyitsiz_cast) + len(_teyitsiz_yon)))
                rapor["adimlar"]["teyitsiz_dusen"] = {"cast": _teyitsiz_cast[:12], "yon": _teyitsiz_yon}
        except Exception:  # noqa: BLE001 — süzgeç hatası akışı ASLA bozmaz (cast AYNEN kalır)
            pass

    # ── FIX-A: EKRAN-TEYİTLİ KB-YÖNETMEN DOLUMU (2026-07-06, AYAK TAKIMI/Ken Loach kanıtı) ──
    # Kök: İngiliz-usulü ETİKETSİZ yönetmen-kartı ("Ken Loach" yalın satır; filmde 'DIRECTED'
    # kelimesi HİÇ yok) → LLM rol atayamıyor (doğru) → alan boş kalıyordu. Çağatay anayasası:
    # "ekranda okuduysam PDF'te görmeliyim". KIRMIZI-ÇİZGİ ("KB-fill yok") KÖR dolumu yasaklar;
    # burası KÖR DEĞİL: isim EKRANDA HARFİYEN okunmuş (kunye/ham/dilim), KB yalnız ROL atıyor.
    # 4 ŞART: yön-boş + film-kimliği güçlü (verdict TEYİT ya da cast_ortusme>=2) + KB-otoriter-
    # yönetmen tekil + isim ekran-verbatim. Kill-switch: MITAS_EKRAN_KB_YON=0.
    if (not yon and os.environ.get("MITAS_EKRAN_KB_YON", "1").strip().lower() not in ("0", "false", "off", "no")):
        try:
            _oy = [str(x) for x in (cc.get("otoriter_yonetmen") or []) if str(x).strip()]
            _kim_ok = (cc.get("verdict") == "TEYİT") or ((cc.get("cast_ortusme") or 0) >= 2)
            if _oy and len(_oy) <= 2 and _kim_ok:
                import unicodedata as _ud

                def _ekfold(_s):
                    _s = _ud.normalize("NFKD", str(_s or ""))
                    _s = "".join(ch for ch in _s if not _ud.combining(ch)).casefold()
                    return " ".join("".join(c if c.isalnum() else " " for c in _s).split())
                _ekran = ""
                try:
                    _kts = sorted([q for q in glob.glob(os.path.join(clip, "ocr", "ocr-*", "kunye.txt"))
                                   if not os.path.basename(os.path.dirname(q)).endswith("-fb")], key=os.path.getmtime)
                    if _kts:
                        _ekran += open(_kts[-1], encoding="utf-8", errors="ignore").read() + chr(10)
                    _hms = sorted(glob.glob(os.path.join(clip, "ocr", "ocr-*", "ocr_ham", "*.txt"))
                                  + glob.glob(os.path.join(clip, "ocr", "ocr-*", "*raw*.txt")),
                                  key=os.path.getmtime)
                    if _hms:
                        _ekran += open(_hms[-1], encoding="utf-8", errors="ignore").read() + chr(10)
                    _dlp = os.path.join(clip, "master_dilim", "dilim_oneocr.txt")
                    if os.path.exists(_dlp):
                        _ekran += open(_dlp, encoding="utf-8", errors="ignore").read()
                except Exception:  # noqa: BLE001
                    pass
                _ekf = " " + _ekfold(_ekran) + " "
                _hit = [n for n in _oy if len(_ekfold(n)) >= 7 and (" " + _ekfold(n) + " ") in _ekf]
                if len(_hit) == 1:
                    yon = [_hit[0]]
                    yon_kaynak = "ekran-teyitli KB-yönetmen (etiketsiz kart — AYAK TAKIMI sınıfı)"
                    rapor["adimlar"]["ekran_kb_yon"] = {"isim": _hit[0], "kimlik": cc.get("eslesen_film")}
        except Exception:  # noqa: BLE001 — dolum ASLA akışı bozmaz; boş kalır
            pass
    castU = ([] if anim else nn.upper_names(cast[:_cap]))   # ANİMASYON: oyuncu alanı boş (seslendirme kadrosu basılmaz)
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
             ana_dil=meta.get("ana_dil", "—"), altyazi=meta.get("altyazi", "—"), poster=poster,
             film_notu=film_notu)
    dbg.emit("v4", "pdf_field_written",
             subject={"field": "v4_pdf_fields", "after": {
                 "title": d.get("title"), "subtitle": d.get("subtitle"),
                 "cast": d.get("cast"), "crew": d.get("crew"),
                 "poster": poster, "tur": tur,
             }, "reason": "final v4 fields passed to _make_pdf"},
             evidence={"yon_kaynak": yon_kaynak, "yon_ocr_teyit": yon_ocr_teyit,
                       "kimlik_dogru": kimlik_dogru, "verdict": verdict,
                       "afis": afis, "poster_ok": bool(poster)},
             source={"module": "scripts/tek_film_kunye.py",
                     "input_paths": [clip], "output_paths": [a.out or ""]})
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
    # GARBLE SİNYALİ (routing için, SİLME DEĞİL — "okunamadı>yanlış"): nihai cast/yön'de LEKSİKAL garble
    # (rol/kurum token 'CRAFT SERVICES', cümle-eki, garbled rol-etiketi) kalmış mı? KB-bağımsız (KB-tanımayan
    # filmde de çalışır), yüksek-isabet. mitas_pipeline bunu okuyup garble→KONTROL yönlendirir (ONAYLI'ya düşürmez).
    _cast_garble_lex, _yon_garble_lex = [], False
    try:
        from credit_text_read import _looks_garble as _lg
        _final_cast = d.get("cast") or []
        _cast_garble_lex = [c for c in _final_cast if c and str(c).strip() != "—" and _lg(c)]
        _final_yon = [n for r, ns in d.get("crew", []) for n in ns if r == "Yönetmen"]
        _yon_garble_lex = bool(_final_yon and _final_yon[0] != "—" and _lg(_final_yon[0]))
    except Exception:  # noqa: BLE001 — sinyal hesabı PDF/raporu ASLA bozmaz
        _cast_garble_lex, _yon_garble_lex = [], False
    # FIX 4 (2026-06-22): KB-BAĞIMSIZ n-gram leksikal garble (well-formed-ASCII: JJAME SBENREET/
    # JEJULIEA — _looks_garble bunlara kör). MITAS_GARBLE_NGRAM=gözlem (rapora yaz, route ETME);
    # MITAS_GARBLE_NGRAM_ROUTE=route (cast_garble_lex'e union → garble→KONTROL, SİLME YOK). FAIL-SAFE.
    _cast_garble_ngram, _cast_ngram_scores = [], {}
    try:
        _ng_on = os.environ.get("MITAS_GARBLE_NGRAM", "0").strip().lower() in ("1", "true", "on", "yes")
        _ng_route = os.environ.get("MITAS_GARBLE_NGRAM_ROUTE", "0").strip().lower() in ("1", "true", "on", "yes")
        if _ng_on or _ng_route:
            import _name_ngram_garble as _ngm
            _fc = [c for c in (d.get("cast") or []) if c and str(c).strip() != "—"]
            _cast_ngram_scores = {c: round(_ngm.score_name(c) or 0.0, 2) for c in _fc}
            _cast_garble_ngram = [c for c in _fc if _ngm.looks_garble_ngram(c)]
            if _ng_route:  # route-kolu: n-gram suspect'leri leksikal-garble'a EKLE (union; silme yok)
                _seen = {str(x) for x in _cast_garble_lex}
                _cast_garble_lex = list(_cast_garble_lex) + [c for c in _cast_garble_ngram if str(c) not in _seen]
    except Exception:  # noqa: BLE001 — gözlem/route sinyali PDF'i ASLA bozmaz
        _cast_garble_ngram, _cast_ngram_scores = [], {}
    rapor["v4"] = {"yonetmen": [n for _, ns in crewU for n in ns if _ == "Yönetmen"],
                   "yapimci_var": any(r == "Yapımcı" for r, _ in crewU), "cast": len(castU),
                   "tur": d["specs"][1][1], "afis": bool(poster),
                   "ozet_kelime": len(d["ozet"].split()), "kanal": sk,
                   # GARBLE-ROUTING sinyali (2026-06-20): nihai cast/yön leksikal-garble
                   "cast_garble_lex": _cast_garble_lex,
                   "cast_garble_lex_count": len(_cast_garble_lex),
                   # FIX 4 GÖZLEM (2026-06-22): n-gram leksikal garble + skorlar (kalibrasyon için)
                   "cast_garble_ngram": _cast_garble_ngram,
                   "cast_ngram_scores": _cast_ngram_scores,
                   "yon_garble_lex": _yon_garble_lex,
                   # OTORİTER yüzey-değerler (PROPAGATION fix 2026-06-20): yüzey .txt'yi V4 PDF ile
                   # HİZALA — mitas_pipeline surface_deliverables bunlarla kunye_teslim.md'yi yamalar.
                   # d["cast"]/d["crew"]/d["keywords"] = PDF'e basılan AYNI değerler (birebir eşleşir).
                   "cast_list": ([] if anim else list(d.get("cast") or [])),   # animasyonda md-patch "—" bassın
                   "keywords": d.get("keywords") or "",
                   # FİLM NOTU (2026-07-04): md-patch + pipeline tüketimi (animasyonda QC 'oyuncu yok' bastırılır)
                   "film_notu": film_notu,
                   "animasyon": bool(anim),
                   "teyitsiz_dusen_cast": _teyitsiz_cast[:12],
                   "teyitsiz_dusen_yon": _teyitsiz_yon,
                   "yonetmen_list": [n for r, ns in d.get("crew", []) for n in ns if r == "Yönetmen"],
                   "yapimci_list": [n for r, ns in d.get("crew", []) for n in ns if r == "Yapımcı"],
                   # BİRLEŞİK QC BLOĞU kararı (flag MITAS_QC_BLOCK): mitas_pipeline NEW kapıları
                   # (floor-8 / Latin-dışı kalıntı / kimlik-kurulamadı) buradan reasons'a katar.
                   "qc_block_karar": (_qcb_res or {}).get("karar"),
                   "qc_block_tip": (_qcb_res or {}).get("kontrol_tip"),
                   "qc_block_gerekceler": (_qcb_res or {}).get("gerekceler") or [],
                   "qc_block_floor": (_qcb_res or {}).get("floor") or {},
                   # OCR-OTORİTE DENETİM (flag MITAS_QC_OTORITE_AUDIT; SIFIR-ROUTE) — A/B ölçümü +
                   # ileride ENFORCE için _DURUM'a taşınır; mitas_pipeline route'u DEĞİŞTİRMEZ.
                   "qc_block_otorite_audit": (_qcb_res or {}).get("otorite_audit"),
                   # fix3-A 2026-06-29 — hafif sinyaller (CAST_CAP_DUSEN vb.) pipeline köprüsü için
                   "qc_block_hafif": (_qcb_res or {}).get("hafif") or []}
    dbg.emit("v4", "stage_completed",
             duration_ms=(time.perf_counter() - started) * 1000,
             subject={"field": "v4", "after": rapor.get("v4"),
                      "reason": "v4 render report completed"},
             evidence={"adimlar": rapor.get("adimlar"), "pdf": out_pdf},
             source={"module": "scripts/tek_film_kunye.py",
                     "input_paths": [clip], "output_paths": [out_pdf]})
    print(json.dumps(rapor, ensure_ascii=False, indent=2))
    print("PDF:", out_pdf)

if __name__ == "__main__":
    main()
