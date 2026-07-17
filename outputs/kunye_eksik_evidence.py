#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHASE A — flagli filmler icin KOK-NEDEN KANIT PAKETI.
Her flagli film icin: frames, ham-OCR'da gercek-isim varligi, garble/yabanci sinyali,
ground-truth (corrections json) capraz-kontrol, ve OTOMATIK kok-neden onerisi.
Cikti: outputs/kunye_eksik_evidence.json  (ajanlar bunu dogrulayip rafine edecek).
"""
import os, re, json, glob

DB = r"E:\MITAS\Database"
AUDIT = r"E:\MITAS\outputs\kunye_eksik_audit.json"
CORR = r"E:\MITAS\outputs\kunye_fix\corrections"
OUT = r"E:\MITAS\outputs\kunye_eksik_evidence.json"

TR_MAP = str.maketrans("İıŞşĞğÜüÖöÇçÂâÎîÛû", "IISSGGUUOOCCAAIIUU")
def norm(s):
    if not s: return ""
    s = s.translate(TR_MAP).upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def norm_compact(s):
    return re.sub(r"[^A-Z0-9]", "", norm(s))

FOREIGN_TOK = ["FILMS","FILM PRODUCTION","PRODUCTION","PRODUCCION","PRODUCTIONS","PRESENTS","PRESENTAN",
    "ENTERTAINMENT","PICTURES","STUDIO","STUDIOS","FOUNDATION","INSTITUTE","INSTITUT","GALLERY","COORDINAD",
    "ASOCIO","APOYO","ASISTENTE","SUPERVISOR","OFICINA","PRODUCTORA","MUSICA DE","ALL RIGHTS","RESERVED",
    "DIRECTED BY","PRODUCED BY","SCREENPLAY","DISTRIBUTED","COPYRIGHT","IN ASSOCIATION","EN COPRODUCCION",
    "AUXILIAR","CONTABILIDAD","ASESORIA","CASTING","EXECUTIVE","COMPANY","CINEMA","CINEMAS"]
TR_CREDIT_TOK = ["YONETMEN","YONETEN","REJISOR","YAPIMCI","YAPIM","OYUNCULAR","OYNAYANLAR","SENARYO",
    "GORUNTU","MUZIK","KURGU","YAPIMCILIGI","FILMI","FILMINDEN"]

GARBLE_RX = re.compile(r"(" + "|".join([re.escape(t) for t in FOREIGN_TOK]) + r")")

def looks_garble_name(entry):
    """Bir kadro/ekip satiri kisi-adi GIBI gorunmuyor mu? (kaba)"""
    n = norm(entry)
    if not n: return True
    if GARBLE_RX.search(n): return True
    if re.search(r"\d", n): return True
    words = n.split()
    if not words: return True
    # >3 kelime cogu kez sirket/cumle
    if len(words) > 4: return True
    # sesli-harfsiz uzun parca (OCR cop)
    for w in words:
        if len(w) >= 4 and not re.search(r"[AEIOU]", w):
            return True
    # cok kisa tek-harf parcalar
    return False

def build_pos(text):
    """norm edilmis metni KELIME listesi + pozisyon-index'ine cevir (tam-kelime eslesme icin)."""
    words = norm(text).split()
    pos = {}
    for i, w in enumerate(words):
        pos.setdefault(w, []).append(i)
    return words, pos

def name_in_text(name, words, pos):
    """Ad+soyad BITISIK mi? (ad ve soyad TAM-KELIME olarak <=3 kelime arayla yan yana).
    DUZELTME: eski versiyon substring + ayri-token ariyordu -> 'Yilmaz Erdogan'i grip
    'Erdogan Gundogdu' + 'Ercan Yilmaz' ile yanlis-pozitif eslestiriyordu. Artik BITISIKLIK sart."""
    toks = [t for t in norm(name).split() if len(t) >= 3]
    if not toks:
        return False
    if len(toks) == 1:
        # tek kelimelik isim: en az 5 harf + TAM kelime (substring degil)
        return len(toks[0]) >= 5 and toks[0] in pos
    first, last = toks[0], toks[-1]
    if first not in pos or last not in pos:
        return False
    for i in pos[first]:
        for j in pos[last]:
            if 0 <= (j - i) <= 3:   # ad -> soyad ardisik/yakin
                return True
    return False

def read_text(p, cap=600000):
    try:
        return open(p, encoding="utf-8", errors="replace").read()[:cap]
    except Exception:
        return ""

def trt_from_folder(folder):
    m = re.search(r"(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)", folder)
    return m.group(1) if m else None

# corrections index
corr_idx = {}
for f in glob.glob(os.path.join(CORR, "*.json")):
    try:
        d = json.load(open(f, encoding="utf-8", errors="replace"))
        tid = d.get("trt_id") or os.path.splitext(os.path.basename(f))[0]
        corr_idx[tid] = d
    except Exception:
        pass

audit = json.load(open(AUDIT, encoding="utf-8"))
flagged = [r for r in audit["rows"] if r["flag"]]

out = []
for r in flagged:
    folder = os.path.join(DB, r["folder"])
    trt = None
    cj = os.path.join(folder, "clip.json")
    if os.path.isfile(cj):
        try: trt = json.load(open(cj, encoding="utf-8", errors="replace")).get("trt_id")
        except Exception: pass
    trt = trt or trt_from_folder(r["folder"])

    ev = {
        "folder": r["folder"], "trt": trt, "baslik": r.get("baslik",""),
        "flag_reasons": r["flag_reasons"],
        "final_yonetmen": r.get("yonetmen",""), "final_yapimci": r.get("yapimci",""),
        "final_cast": r.get("oyuncular",[]), "final_cast_n": r.get("real_cast",0),
        "ana_dil": r.get("ana_dil",""), "tur": r.get("tur",""),
        "frames_giris": r.get("frames_giris",-1), "frames_cikis": r.get("frames_cikis",-1),
        "has_fixed_pdf": r.get("has_fixed_pdf",False),
        "ocr_job": r.get("ocr_job"), "ocr_kunye_txt": r.get("ocr_kunye_txt",False),
        "ocr_kunye_lines": r.get("ocr_kunye_lines",0), "ocr_bucket": r.get("ocr_bucket"),
        "no_output": r.get("no_output",False),
    }

    # OCR metinleri
    kunye_txt = ham = raw_all = ""
    if ev["ocr_job"]:
        jobdir = os.path.join(folder, "ocr", ev["ocr_job"])
        kunye_txt = read_text(os.path.join(jobdir, "kunye.txt"))
        ham = read_text(os.path.join(jobdir, "ocr_ham.txt"))
        raw_all = read_text(os.path.join(jobdir, "ocr_raw_all.txt"))
    raw_concat = ham + "\n" + raw_all
    nraw = norm(raw_concat)
    raw_words, raw_pos = build_pos(raw_concat)
    kunye_words, kunye_pos = build_pos(kunye_txt)

    ev["ocr_kunye_empty"] = (len(kunye_txt.strip()) == 0)
    ev["ocr_raw_chars"] = len(raw_concat.strip())
    ev["ocr_kunye_chars"] = len(kunye_txt.strip())

    # dil sinyali (ham OCR)
    fcnt = sum(len(re.findall(re.escape(norm(t)), nraw)) for t in FOREIGN_TOK)
    tcnt = sum(len(re.findall(re.escape(t), nraw)) for t in TR_CREDIT_TOK)
    ev["raw_foreign_hits"] = fcnt
    ev["raw_tr_credit_hits"] = tcnt

    # final garble orani
    allfinal = list(ev["final_cast"])
    if ev["final_yonetmen"]: allfinal += re.split(r",|/|;", ev["final_yonetmen"])
    if ev["final_yapimci"]: allfinal += re.split(r",|/|;", ev["final_yapimci"])
    allfinal = [x.strip() for x in allfinal if x.strip()]
    g = sum(1 for x in allfinal if looks_garble_name(x))
    ev["final_entries"] = len(allfinal)
    ev["final_garble_n"] = g
    ev["final_garble_ratio"] = round(g / len(allfinal), 2) if allfinal else None

    # ground truth
    c = corr_idx.get(trt)
    ev["has_correction"] = bool(c)
    if c:
        gt_dir = c.get("director") or []
        gt_prod = c.get("producers") or []
        gt_cast = c.get("cast") or []
        ev["gt_director"] = gt_dir
        ev["gt_producers"] = gt_prod
        ev["gt_cast"] = gt_cast
        ev["gt_original_title"] = c.get("original_title")
        ev["gt_notes"] = c.get("notes")
        ev["gt_tier"] = c.get("tier")
        # gercek isimler ham-OCR'da var mi?
        def presence(names):
            res = []
            for nm in names:
                res.append({"name": nm,
                            "in_raw": name_in_text(nm, raw_words, raw_pos),
                            "in_kunye": name_in_text(nm, kunye_words, kunye_pos)})
            return res
        ev["dir_presence"] = presence(gt_dir)
        ev["cast_presence"] = presence(gt_cast)
        dir_raw = sum(1 for x in ev["dir_presence"] if x["in_raw"])
        cast_raw = sum(1 for x in ev["cast_presence"] if x["in_raw"])
        ev["gt_dir_in_raw_n"] = dir_raw
        ev["gt_dir_total"] = len(gt_dir)
        ev["gt_cast_in_raw_n"] = cast_raw
        ev["gt_cast_total"] = len(gt_cast)

    # ---- OTOMATIK KOK-NEDEN ONERISI ----
    cause = None; conf = "dusuk"; note = ""
    gi, ck = ev["frames_giris"], ev["frames_cikis"]
    if ev["no_output"]:
        cause = "S0_CIKTI_YOK"; conf="kesin"; note="kunye_teslim.md/pdf hic uretilmemis (pipeline cokmesi/calismadi)."
    elif (gi in (0,-1)) and (ck in (0,-1)):
        cause = "S1_FRAME_YOK"; conf="yuksek"; note="giris+cikis frame yok -> jenerik karesi yakalanmamis."
    elif ev["ocr_raw_chars"] < 30:
        cause = "S1_OCR_BOS"; conf="yuksek"; note="frame var ama ham OCR ~bos -> OCR motoru okuyamadi / jenerik karede yazi yok."
    elif c and (ev.get("gt_dir_total",0)+ev.get("gt_cast_total",0) > 0):
        gt_n = ev.get("gt_dir_total",0)+ev.get("gt_cast_total",0)
        gt_in_raw = ev.get("gt_dir_in_raw_n",0)+ev.get("gt_cast_in_raw_n",0)
        ratio = gt_in_raw/gt_n if gt_n else 0
        if ratio >= 0.5:
            cause = "S2-4_FILTRE_ROL_KAYBI"; conf="yuksek"
            note=f"gercek isimlerin ~%{int(ratio*100)}'i HAM OCR'da VAR ama final'de yok -> filtre/rol/QC adimi dusurdu/yanlis-atadi."
        elif gt_in_raw == 0 and ev["ocr_raw_chars"] >= 30:
            if ev["raw_foreign_hits"] >= 5 and ev["raw_tr_credit_hits"] == 0:
                cause = "S1_YABANCI_JENERIK"; conf="orta"
                note=f"ham OCR yogun yabanci-yapim metni ({ev['raw_foreign_hits']} hit), gercek isimler okunamamis -> yabanci-dil jenerik OCR'da kayip."
            else:
                cause = "S1_OCR_YANLIS_OKUDU"; conf="orta"
                note="gercek isimler ham OCR'da YOK ama OCR cop-dolu -> yanlis-okuma/jenerik-kare-kacti (frame kapsami)."
        else:
            cause = "S1-4_KARISIK"; conf="dusuk"
            note=f"kismi: gercek isim {gt_in_raw}/{gt_n} ham OCR'da."
    else:
        # ground truth yok -> sinyallere gore
        if ev["final_garble_ratio"] is not None and ev["final_garble_ratio"] >= 0.5:
            cause = "GARBLE_KONTAMINASYON"; conf="orta"
            note="final kadro/ekip cogunlukla garble/sirket-adi -> filtre+rol garble'i gecirdi (ground-truth yok)."
        elif ev["raw_foreign_hits"] >= 5 and ev["raw_tr_credit_hits"] == 0:
            cause = "S1_YABANCI_JENERIK?"; conf="dusuk"
            note="yabanci-yapim metni baskin; ground-truth yok -> ajan dogrulasin."
        else:
            cause = "BELIRSIZ"; conf="dusuk"; note="ground-truth yok, sinyaller net degil -> ajan incelesin."
    ev["auto_cause"] = cause; ev["auto_conf"] = conf; ev["auto_note"] = note
    out.append(ev)

json.dump(out, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

from collections import Counter
cc = Counter(e["auto_cause"] for e in out)
print(f"flagli film: {len(out)}")
print(f"correction(ground-truth) olan: {sum(1 for e in out if e['has_correction'])}")
print("\n--- OTOMATIK KOK-NEDEN DAGILIMI ---")
for k,v in cc.most_common():
    print(f"  {v:4d}  {k}")
print(f"\nJSON -> {OUT}")
