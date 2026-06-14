"""TEMİZLİK KATMANI: CLIP-seçili kredi karelerinin HAM OCR satırları -> temiz oyuncular+ekip.
Eler: junk(©®™/url/numerik) · logo(dağıtımcı) · legal(telif/MPAA) · sentence(diegetik/diyalog/manşet 'MY BIRD IS DEAD') · sponsor.
Korur: isim + rol satırları. Çok-kare KONSENSÜS dedup (WAEL MIRISCH≈WALTER MIRISCH -> en iyi yazım). KB-yazım + Türkçe-BÜYÜK.
Opsiyonel: ASR transcript'iyle eşleşen satır = diyalog -> at.
"""
import sys, glob, re, difflib, importlib.util, argparse
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location("rw", r"E:\MITAS\OCR-worktree\py\20260531_2330_read_3way.py")
rw = importlib.util.module_from_spec(spec); sys.modules["rw"] = rw; spec.loader.exec_module(rw)
fold = rw.fold; read_oneocr = rw.read_oneocr; cr = rw.cr; fp = rw.fp
import duckdb

def tr_upper(s): return s.replace("i", "İ").upper()
def diac(s): return sum(c in "şŞğĞıİçÇöÖüÜ" for c in s)

DISTRIB = {"metro goldwyn mayer", "mgm", "united artists", "warner bros", "warner bros pictures", "columbia",
           "paramount", "universal", "twentieth century fox", "20th century fox", "de luxe", "deluxe",
           "technicolor", "fotofilm", "an mgm company", "a time warner company", "eastmancolor"}
DISTRIB_F = {fold(x) for x in DISTRIB}
LEGAL = ["fictional", "coincidental", "rights reserved", "copyright", "all events", "photoplay", "mcmlx",
         "mcmxc", "mcmlxx", "association of america", "distributed by", "negative processed", "color by",
         "presents", "in association with", "all rights", "any similarity", "any persons", "uninten"]
ROLE_KW = {"by", "directed", "produced", "producer", "director", "music", "photography", "cinematography",
           "editor", "edited", "screenplay", "story", "written", "cast", "starring", "co-starring", "with",
           "production", "art", "sound", "costume", "wardrobe", "makeup", "gaffer", "grip", "script",
           "supervisor", "manager", "decorator", "effects", "camera", "operator", "casting", "based",
           "yönetmen", "yapımcı", "yapım", "müzik", "görüntü", "kurgu", "senaryo", "oyuncu", "kostüm",
           "makyaj", "ışık", "ses", "sanat", "yardımcı", "yöneten"}
FUNC = {"the", "of", "and", "in", "is", "a", "an", "to", "with", "for", "on", "as", "from", "are", "was",
        "were", "this", "all", "any", "or", "at", "that", "be", "been", "novel", "ve", "bir", "bu", "ile",
        "için", "da", "de", "ki", "ama", "çok", "daha", "olan", "gibi", "ya", "the"}
VERBS = {"is", "are", "was", "were", "has", "have", "will", "dead", "living", "killed", "said"}
# Gap-1 (Çağatay 2026-06-14): isimde/rolde ASLA geçmeyen net Türkçe diyalog/söylem belirteçleri.
# Kısa altyazı ("Çünkü çok geç", "Evet tamam") VERBS(İngilizce) + FUNC eşiğini geçemeyince kaçıyordu.
# Bu set GÜVENLİ: hiçbiri "Ad Soyad" parçası değil (Ben/Sen/Kim gibi isim-riskli olanlar KASTEN dışarıda).
DIALOG = {"çünkü", "fakat", "ancak", "yani", "zaten", "belki", "değil", "nasıl", "neden",
          "niçin", "evet", "hayır", "tabii", "galiba", "sanki", "şey", "hadi", "lütfen",
          "asla", "tamam", "elbette", "üzgünüm", "merhaba", "teşekkür", "günaydın"}
COMPANY = {"corporation", "productions", "company", "pictures", "studios", "inc", "ltd", "enterprises", "entertainment"}
MPAA = ["motion picture association of america", "approved", "trade mark"]
FUZZ_TARGETS = list(DISTRIB_F) + [fold(x) for x in MPAA]

def atok(t): return [w for w in re.split(r"\s+", t.strip()) if any(c.isalpha() for c in w)]
def has_role(low): return bool(set(re.sub(r"[.,]", " ", low).split()) & ROLE_KW)

def classify(t):
    low = t.lower().strip(); fl = fold(t); toks = atok(t); n = len(toks)
    a = sum(c.isalpha() for c in t); d = sum(c.isdigit() for c in t)
    if a < 2 or d > a: return "junk"
    if any(x in low for x in ["www.", "http", ".com", ".tr", ".net", "®", "™", "©"]): return "junk"
    if fl in DISTRIB_F: return "logo"
    if max((difflib.SequenceMatcher(None, fl, x).ratio() for x in FUZZ_TARGETS), default=0) >= 0.62: return "logo"
    if (set(low.split()) & COMPANY) or low.rstrip().endswith("-"): return "company"
    if any(m in low for m in LEGAL): return "legal"
    if n == 1: return "frag"                                # tek-kelime satır kredi olamaz (isimler >=2 kelime)
    if not has_role(low):
        bare = set(re.sub(r"[.,!?\"]", " ", low).split())
        if "?" in t: return "sentence"                      # soru işareti = diyalog/altyazı (künyede soru olmaz; isim/rol asla elenmez)
        if n >= 7: return "sentence"
        if (bare & VERBS) and n >= 3: return "sentence"
        if n >= 4 and sum(1 for w in bare if w in FUNC) >= 2: return "sentence"
        if bare & DIALOG: return "sentence"             # net diyalog-belirteci (kısa altyazı; isimde asla geçmez)
        if "!" in t or "..." in t: return "sentence"    # ünlem/elips = diyalog/disclaimer (künyede olmaz)
    return "credit"

def near(a, b):
    fa, fb = fold(a), fold(b)
    if not fa or not fb: return False
    if abs(len(fa.split())-len(fb.split())) > 1: return False
    return difflib.SequenceMatcher(None, fa, fb).ratio() >= 0.82

def consensus(credits, kb):
    """credits: [(text,count)] -> gruplara böl, grup başına en iyi yazımı seç (KB>diakritik>uzun>sık)."""
    groups = []
    for t, c in credits:
        g = next((g for g in groups if any(near(m[0], t) for m in g)), None)
        if g is None: groups.append([(t, c)])
        else: g.append((t, c))
    out = []
    for g in groups:
        # KB kanonik varsa onu
        best = None
        for t, c in g:
            ntok = len(atok(t))
            if fold(t) in kb and ntok >= 2: best = (kb[fold(t)], "KB"); break
        if not best:
            t = max(g, key=lambda x: (diac(x[0]), x[1], len(x[0])))[0]; best = (t, "literal")
        votes = sum(c for _, c in g)
        out.append((best[0], best[1], votes))
    return out

def clean(raw_multi, con, asr_fold=""):
    cnt = {}
    for t in raw_multi:
        t = t.strip()
        if t: cnt[t] = cnt.get(t, 0) + 1
    buckets = {"credit": [], "logo": [], "legal": [], "sentence": [], "junk": [], "company": [], "frag": []}
    for t, c in cnt.items():
        buckets[classify(t)].append((t, c))
    # ASR diyalog ele (güçlü eşleşme)
    asr_dropped = []
    creds = []
    for t, c in buckets["credit"]:
        fl = fold(t)
        if len(fl) >= 10 and asr_fold and fl in asr_fold: asr_dropped.append(t); continue
        creds.append((t, c))
    folds = list({fold(t) for t, _ in creds})
    kb = cr.kb_exact_batch(con, folds) if folds else {}
    merged = consensus(creds, kb)
    merged.sort(key=lambda x: -x[2])
    nc, ns = len(buckets["credit"]), len(buckets["sentence"])
    dieg = ns/(nc+ns) if (nc+ns) else 0.0      # cümle oranı yüksekse bölge diegetik prose (kitap/gazete)
    return merged, buckets, asr_dropped, dieg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default="ACEMİLER"); ap.add_argument("--seg", default="giris")
    ap.add_argument("--sub", default="entry_frames"); ap.add_argument("--thr", type=float, default=0.4)
    a = ap.parse_args()
    DB = Path(r"F:\REPO_GitHub\DATABASE"); PROBE = Path(r"E:\MITAS\OCR-worktree\clip_probe")
    fd = [d for d in DB.iterdir() if a.film.lower() in d.name.lower()][0]
    safe = "".join(c if c.isalnum() else "_" for c in fd.name)[:40]
    frames = sorted(glob.glob(str(fd/a.sub/"*.png")))
    cand = [PROBE/safe/a.seg/"credit_prob.npy", PROBE/"_REVIEW15"/f"{safe}__{a.seg}.npy"]
    npy = next((p for p in cand if p.exists()), None)
    if npy is None: print("credit_prob.npy yok:", cand); return
    probs = np.load(npy)
    idx = [i for i in range(len(probs)) if probs[i] >= a.thr]
    asr = ""
    ap_ = list(fd.glob("audio_transcript.txt"))
    if ap_: asr = fold(ap_[0].read_text(encoding="utf-8", errors="ignore"))
    print(f"{fd.name}/{a.seg}: {len(idx)} kredi-karesi okunuyor...")
    raw = []
    for i in idx: raw.extend(read_oneocr(fp.rd(frames[i])))
    con = duckdb.connect(cr.DB, read_only=True)
    merged, buckets, asr_drop, dieg = clean(raw, con, asr); con.close()
    if dieg > 0.30:
        print(f"\n⚠️  DİEGETİK-PROSE BÖLGESİ (cümle oranı %{dieg*100:.0f}) — burada gerçek kredi YOK olabilir (kitap/gazete sayfası, çıkarma hatası).")
    print(f"\nHam farklı satır: {sum(len(v) for v in buckets.values())} | "
          f"kredi={len(buckets['credit'])} logo={len(buckets['logo'])} legal={len(buckets['legal'])} "
          f"company={len(buckets['company'])} sentence={len(buckets['sentence'])} frag={len(buckets['frag'])} "
          f"junk={len(buckets['junk'])} | ASR-diyalog atılan={len(asr_drop)}")
    print(f"\n=== TEMİZ KÜNYE ({len(merged)} kayıt, oy=kaç karede görüldü) ===")
    for t, how, votes in merged:
        print(f"  {tr_upper(t):42} [{how} ×{votes}]")
    for cls in ["logo", "company", "legal", "sentence", "frag", "junk"]:
        ex = [t for t, _ in buckets[cls]][:8]
        if ex: print(f"\n--- ATILAN [{cls}] ({len(buckets[cls])}): " + " | ".join(ex))
    od = PROBE/safe/a.seg; od.mkdir(parents=True, exist_ok=True)
    (od/"KUNYE_temiz.txt").write_text("\n".join(tr_upper(t) for t, _, _ in merged), encoding="utf-8")
    print(f"\n-> {od/'KUNYE_temiz.txt'}")

if __name__ == "__main__":
    main()
