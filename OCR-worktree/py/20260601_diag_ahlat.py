"""AHLAT cikis medconf=0.36 neden? Scroll run kümelerini üyeleriyle döker."""
import sys, json, importlib.util, statistics, collections
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
def load(m, p):
    s = importlib.util.spec_from_file_location(m, p); mod = importlib.util.module_from_spec(s); sys.modules[m] = mod; s.loader.exec_module(mod); return mod
stx = load("stx", r"E:\MITAS\OCR-worktree\py\20260601_stitch.py")
cj = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_CACHE\AHLAT_AĞACI_2018_9024_1_0000_90_1__cikis.json")
c = json.loads(cj.read_text(encoding="utf-8")); idx = c["idx"]; op = {int(k): v for k, v in c["ocr_pos"].items()}
run = max(stx.runs_of(idx), key=len)
run_obs = [op[i] for i in run]; nf = len(run_obs)
deltas = [stx.est_delta(run_obs[k], run_obs[k+1]) for k in range(nf-1)]
valid = [d for d in deltas if d is not None and abs(d) < 200]
gmed = sorted(valid)[len(valid)//2] if valid else 0
deltas = [d if (d is not None and abs(d) < 200) else gmed for d in deltas]
S = [0.0]*nf
for k in range(1, nf): S[k] = S[k-1]+deltas[k-1]
L = stx.line_spacing(run_obs)
items = []
for k in range(nf):
    for o in run_obs[k]:
        if o[0]: items.append((stx.cy(o)+S[k], o[1]))
items.sort(key=lambda x: x[0])
tol = max(8.0, L*0.45)
clusters = [[items[0]]]
for it in items[1:]:
    (clusters[-1].append(it) if it[0]-clusters[-1][-1][0] <= tol else clusters.append([it]))
confs = [stx.pick_best([x[1] for x in cl])[1] for cl in clusters]
print(f"run {run[0]}-{run[-1]} nf={nf} | gmed(scroll hızı)={gmed:.1f}px L(satır aralığı)={L:.1f}px tol={tol:.1f}px")
print(f"küme sayısı={len(clusters)} medconf={statistics.median(confs):.2f}")
gspreads = [max(x[0] for x in cl)-min(x[0] for x in cl) for cl in clusters if len(cl) > 1]
print(f"küme g-yayılımı medyan={statistics.median(gspreads):.0f}px (L={L:.0f} -> yayılım>>L ise SATIRLAR BİRLEŞMİŞ demek)")
print("\n=== EN KALABALIK 10 KÜME (üyeler) ===")
for cl in sorted(clusters, key=lambda c: -len(c))[:10]:
    gs = [x[0] for x in cl]; reads = [x[1] for x in cl]
    best, conf = stx.pick_best(reads)
    print(f"\n[n={len(cl)} g-yayılım={max(gs)-min(gs):.0f}px conf={conf:.2f}] -> '{best}'")
    for r, f in collections.Counter(reads).most_common(6): print(f"    {f}x  {r}")
