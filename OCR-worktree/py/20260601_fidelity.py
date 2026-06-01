"""SADAKAT ANALİZÖRÜ — clip_pipeline100/_KUNYE/*.txt içindeki HER satırı sınıflar.
Objektif metrik: name/role = sağlam künye; frag/garble/sentence = gürültü.
Çıktı: dağılım + en gürültülü 25 + _FIDELITY.json. Stdlib-only.
"""
import sys, re, json, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
KUN = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_KUNYE")
OUT = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100")
VOWELS = set("aeıioöuüâîû")
ROLE = set(("yönetmen yöneten yönetimi senaryo senaryist oyuncular oyuncu cast müzik görüntü kurgu "
            "yapımcı yapım yapimi directed produced written music editor camera kamera ses ışık dekor "
            "kostüm montaj fotoğraf production director screenplay starring featuring presents prodüksiyon "
            "sanat yardımcısı yönetmeni özgün the end son cinema film genel yapımcılar ortak distribütör "
            "seslendirme çeviri yapımevi stüdyo laboratuvar negatif kurgusu yönetmeni").split())
def fold(s): return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))
def classify(t):
    t = t.strip()
    if not t: return "empty"
    nonsp = sum(not c.isspace() for c in t); letters = sum(c.isalpha() for c in t)
    if letters == 0: return "junk"
    toks = t.split()
    if (t.endswith((".", "?", "!")) and len(toks) >= 4) or len(toks) >= 6: return "sentence"
    if letters/nonsp < 0.6: return "garble"
    if any(len(tk) >= 4 and not any(c in VOWELS for c in fold(tk)) for tk in toks): return "garble"
    if any(fold(tk).strip(".,:;-") in ROLE for tk in toks): return "role"
    if len(toks) == 1 and len(toks[0]) <= 3: return "frag"
    return "name"

rows = []; agg = {}
for f in sorted(KUN.glob("*.txt")):
    lines = [l for l in f.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]
    if not lines:
        rows.append({"film": f.stem, "n": 0, "clean": 0, "noise": 0, "fid": 0.0, "cls": {}}); continue
    cls = {}
    for l in lines:
        c = classify(l); cls[c] = cls.get(c, 0)+1; agg[c] = agg.get(c, 0)+1
    n = len(lines); clean = cls.get("name", 0)+cls.get("role", 0)
    noise = cls.get("garble", 0)+cls.get("frag", 0)+cls.get("sentence", 0)+cls.get("junk", 0)
    rows.append({"film": f.stem, "n": n, "clean": clean, "noise": noise, "fid": round(clean/n, 2), "cls": cls})

rows.sort(key=lambda r: (r["fid"], -r["noise"]))
(OUT/"_FIDELITY.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
big = [r for r in rows if r["n"] >= 15]
import statistics as st
print(f"{len(rows)} künye | toplam satır={sum(r['n'] for r in rows)}")
print(f"GENEL DAĞILIM: " + " ".join(f"{k}={v}" for k, v in sorted(agg.items(), key=lambda x:-x[1])))
tot = sum(agg.values()); clean_t = agg.get('name', 0)+agg.get('role', 0)
print(f"GENEL SADAKAT (name+role)/toplam = {clean_t}/{tot} = %{clean_t*100//max(1,tot)}")
print(f"\nfid medyan (n>=15 film) = {st.median([r['fid'] for r in big]):.2f}  | film sayısı={len(big)}")
print(f"\n--- EN GÜRÜLTÜLÜ 25 (n>=15) ---")
print(f"{'film':46}{'n':>4}{'fid':>5}  sınıflar")
for r in [x for x in rows if x['n'] >= 15][:25]:
    print(f"{r['film'][:46]:46}{r['n']:>4}{r['fid']:>5}  " + " ".join(f"{k}:{v}" for k, v in sorted(r['cls'].items(), key=lambda x:-x[1])))
print(f"\n--- EN TEMİZ 8 (n>=20) ---")
for r in [x for x in rows if x['n'] >= 20][::-1][:8]:
    print(f"{r['film'][:46]:46}{r['n']:>4}{r['fid']:>5}  " + " ".join(f"{k}:{v}" for k, v in sorted(r['cls'].items(), key=lambda x:-x[1])))
print(f"-> {OUT/'_FIDELITY.json'}")
