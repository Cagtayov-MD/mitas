# -*- coding: utf-8 -*-
"""testas_rerender.py — testas XML_ONAYLI PDF'i (kaynak XML silinmiş) PDF'TEN-VERİ + düzeltme ile yeniden render.

testas hattının kalıcı per-film kaynağı yok; veriyi PDF'in kendisinden (fitz) çıkarır,
corrections (ozet/tur/original/yapimci/cast) uygular, testas _make_pdf ile yeniden basar.
Casing: name_normalize (tr_upper/upper_names/upper_crew). Poster: output/_posters/<trt>_*.jpg.

KULLANIM:
  No-op test:  python testas_rerender.py --selftest "<pdf>"
  Uygula:      python testas_rerender.py --results <corr.json> --apply
"""
import argparse, glob, json, os, re, sys, datetime, importlib.util
sys.stdout.reconfigure(encoding="utf-8")

TESTAS = r"D:\testas\pdf-mitas"
OUTDIR = r"D:\testas\output"
POSTERS = os.path.join(OUTDIR, "_posters")

def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
mp = _load("mp_testas", os.path.join(TESTAS, "_make_pdf.py"))
nn = _load("nn_testas", os.path.join(TESTAS, "name_normalize.py"))
import fitz

def key(s): return re.sub(r"\s+", "", s or "").upper()

def up_o(s):
    s = s or ""
    return nn.tr_upper(s) if any(c in nn._TR_STRONG for c in s) else nn.ascii_fold(s).upper()

def title_from_filename(pdf):
    b = os.path.basename(pdf)
    b = re.sub(r"\.pdf$", "", b, flags=re.I)
    b = re.sub(r"_XML_ONAYLI.*$", "", b)
    b = re.sub(r"^[0-9][0-9\-]+[_ ]+", "", b)  # trt önekini at
    return b.replace("_", " ").strip()

def fold(s):
    return re.sub(r"[^a-z0-9]", "", nn.ascii_fold(s or "").lower())

def parse_pdf(pdf):
    doc = fitz.open(pdf); lines = [l.strip() for l in doc[0].get_text("text").splitlines() if l.strip()]; doc.close()
    K = [key(l) for l in lines]
    def after(marker):
        for i, k in enumerate(K):
            if k == marker and i + 1 < len(lines): return lines[i + 1]
        return ""
    d = {"lines": lines}
    d["ana_dil"] = after("ANADİL") or after("ANADIL") or "—"
    d["altyazi"] = after("ALTYAZI") or "HAYIR"
    d["tur"] = after("TÜR") or after("TUR") or "—"
    d["sure"] = after("TOPLAMSÜRE") or after("TOPLAMSURE") or "—"
    d["trt"] = after("TRTKİMLİK") or after("TRTKIMLIK") or "—"
    # ses kanalları: "N. KANAL" -> sonraki satır dil
    ses = []
    for i, k in enumerate(K):
        if re.match(r"^\d+\.KANAL$", k) and i + 1 < len(lines):
            ses.append(lines[i + 1].strip())
    d["ses_kanallari"] = ses
    # film/dizi + başlık bloğu
    fi = next((i for i, k in enumerate(K) if k in ("FİLM", "FILM", "DİZİ", "DIZI")), None)
    ai = next((i for i, k in enumerate(K) if k.startswith("ANAHTARSÖZCÜKLER") or k.startswith("ANAHTARSOZCUKLER")), None)
    d["profile"] = "DİZİ" if (fi is not None and K[fi] in ("DİZİ", "DIZI")) else "FİLM"
    title = title_from_filename(pdf)
    subtitle = ""
    if fi is not None and ai is not None:
        block = lines[fi + 1:ai]
        tf = fold(title); acc = ""; idx = 0
        for l in block:
            if tf and (fold(acc + l) in tf or tf.startswith(fold(acc + l))):
                acc += fold(l); idx += 1
            else: break
        subtitle = " ".join(block[idx:]).strip()
    d["title"] = title
    d["subtitle"] = subtitle
    # oyuncular
    oi = next((i for i, k in enumerate(K) if k == "OYUNCULAR"), None)
    yi = next((i for i, k in enumerate(K) if k.startswith("YAPIMEKİBİ") or k.startswith("YAPIMEKIBI")), None)
    oz = next((i for i, k in enumerate(K) if k == "ÖZET" or k == "OZET"), None)
    d["cast"] = [l for l in lines[(oi + 1):yi]] if (oi is not None and yi is not None) else []
    # crew
    yon, yap = [], []
    if yi is not None:
        end = oz if oz is not None else len(lines)
        cur = None
        for l in lines[yi + 1:end]:
            kk = key(l)
            if kk in ("YÖNETMEN", "YONETMEN"): cur = "yon"; continue
            if kk in ("YAPIMCI",): cur = "yap"; continue
            if cur == "yon": yon.append(l)
            elif cur == "yap": yap.append(l)
    d["yonetmen"] = [x for x in yon if x and x != "—"]
    d["yapimci"] = [x for x in yap if x and x != "—"]
    # özet
    d["ozet"] = " ".join(lines[oz + 1:]).strip() if oz is not None else ""
    return d

def build_d(parsed, corr):
    corr = corr or {}
    cast = corr.get("cast") or parsed["cast"]
    cast = [c for c in cast if str(c).strip()][:8]
    castU = nn.upper_names(cast) if (corr.get("cast")) else cast  # değiştiyse cased üret, yoksa zaten cased
    yon = parsed["yonetmen"]
    # BOŞ yapimci düzeltmesi = "değişiklik yok" (mevcudu KORU, SİLME). Yalnız dolu liste uygulanır.
    yap_changed = bool(corr.get("yapimci"))
    yap = corr.get("yapimci") or parsed["yapimci"]
    yap = [c for c in (yap or []) if str(c).strip()]
    if yap_changed and yap:
        yap = [r2 for _, r2 in nn.upper_crew([("Yapımcı", yap)])][0]
    if not yap: yap = ["—"]
    if not yon: yon = ["—"]
    sub = corr.get("original") or parsed["subtitle"]
    sub = up_o(sub) if (corr.get("original")) else sub
    if sub and fold(sub) == fold(parsed["title"]): sub = ""
    tur = corr.get("tur") or parsed["tur"]
    tur = nn.tr_upper(tur) if corr.get("tur") else tur
    ozet = corr.get("ozet") or parsed["ozet"]
    ozet = nn.tr_upper(ozet) if corr.get("ozet") else ozet
    now = datetime.datetime.now().strftime("%d.%m.%Y  ·  %H:%M")
    return {
        "profile": parsed["profile"], "date": now, "title": nn.tr_upper(parsed["title"]),
        "subtitle": sub or None, "poster": parsed.get("poster") or "",
        "specs": [("TÜR", tur), ("TOPLAM SÜRE", parsed["sure"]), ("TRT KİMLİK", parsed["trt"])],
        "keywords": " ; ".join(castU), "cast": castU,
        "crew": [("Yönetmen", yon[:2]), ("Yapımcı", yap[:4])],
        "ozet": ozet, "ses_kanallari": parsed["ses_kanallari"],
        "ana_dil": parsed["ana_dil"], "altyazi": parsed["altyazi"], "sesler_ic_ice": False,
    }

def find_poster(trt):
    g = glob.glob(os.path.join(POSTERS, f"{trt}_*.jpg"))
    for p in g:
        if os.path.getsize(p) > 5000: return p
    return ""

def render(pdf, corr):
    parsed = parse_pdf(pdf)
    parsed["poster"] = find_poster(parsed["trt"])
    d = build_d(parsed, corr)
    tmp = pdf + ".tmp.pdf"
    mp.build(tmp, d)
    if os.path.exists(tmp) and os.path.getsize(tmp) > 10000:
        os.replace(tmp, pdf); return True, parsed["trt"]
    if os.path.exists(tmp): os.remove(tmp)
    return False, parsed["trt"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", default=None, help="bir PDF'i düzeltmesiz yeniden render (round-trip test)")
    ap.add_argument("--results", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    if a.selftest:
        parsed = parse_pdf(a.selftest); parsed["poster"] = find_poster(parsed["trt"])
        print(json.dumps({k: v for k, v in parsed.items() if k != "lines"}, ensure_ascii=False, indent=1))
        d = build_d(parsed, {})
        tmp = a.selftest + ".selftest.pdf"; mp.build(tmp, d)
        print("RENDER OK:", os.path.exists(tmp) and os.path.getsize(tmp) > 10000, "->", tmp)
        return
    data = json.load(open(a.results, encoding="utf-8"))
    recs = data.get("results") if isinstance(data, dict) else data
    fl = json.load(open(r"E:\MITAS\.qc_testas_filelist.json", encoding="utf-8"))["testas"]
    bytrt = {}
    for p in fl:
        m = re.match(r"([0-9][0-9\-]+)", os.path.basename(p)); bytrt[m.group(1)] = p if m else None
    only = set(x.strip() for x in a.only.split(",") if x.strip())
    done = failed = skip = 0
    for r in recs:
        trt = r.get("trt", "").strip(); corr = r.get("corrections") or {}
        if only and trt not in only: continue
        if r.get("status") != "DUZELT" or not corr: skip += 1; continue
        pdf = bytrt.get(trt)
        if not pdf or not os.path.exists(pdf): failed += 1; print(f"  ✗ {trt}: PDF yok"); continue
        if not a.apply:
            print(f"  [DRY] {trt} {r.get('title')}: {sorted(corr.keys())}"); continue
        try:
            ok, _ = render(pdf, corr)
            if ok: done += 1; print(f"  ✓ {trt} {r.get('title')}: {sorted(corr.keys())}")
            else: failed += 1; print(f"  ✗ {trt}: render boş")
        except Exception as e:
            failed += 1; print(f"  ✗ {trt}: {type(e).__name__}: {e}")
    print(f"\nUYGULANDI:{done} ATLANDI:{skip} BAŞARISIZ:{failed}" + ("" if a.apply else "  (DRY)"))

if __name__ == "__main__":
    main()
