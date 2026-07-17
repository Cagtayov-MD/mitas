"""DEMO: production mode-seciminin (stitch.pick_best) vs hayali per-karakter coğunluk-oylamasinin
ayni satir-kumesinde kiyasi. Production stitch.py fonksiyonlarini AYNEN import eder (sadik).
Kullanim: python perchar_vote_demo.py [film_substr] [giris|cikis]
"""
import sys, json, importlib.util, difflib
from collections import Counter
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

# --- production stitch.py'yi AYNEN yukle ---
spec = importlib.util.spec_from_file_location("st", r"E:\MITAS\OCR-worktree\py\20260601_stitch.py")
st = importlib.util.module_from_spec(spec); sys.modules["st"] = st; spec.loader.exec_module(st)

def per_char_vote(readings):
    """Star-alignment per-karakter coğunluk: en temiz okumayi referans al, difflib ile her okumayi
    referansa hizala, pozisyon-pozisyon coğunluk-oyu. Hicbir karenin tek basina dogru okumadigi
    bir satiri parcalardan kurabilir."""
    rs = [r for r in readings if r.strip()]
    if not rs: return ""
    if len(rs) == 1: return rs[0]
    ref = min(rs, key=lambda r: (st.garble(r), -len(r)))
    cols = [Counter() for _ in range(len(ref))]
    ins  = [Counter() for _ in range(len(ref)+1)]
    for r in rs:
        sm = difflib.SequenceMatcher(None, ref, r, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                for k in range(i1, i2): cols[k][ref[k]] += 1
            elif tag == 'replace':
                span = r[j1:j2]
                for n, k in enumerate(range(i1, i2)):
                    cols[k][span[n] if n < len(span) else ''] += 1
                if len(span) > (i2 - i1):
                    ins[i2][span[i2-i1:]] += 1
            elif tag == 'delete':
                for k in range(i1, i2): cols[k][''] += 1
            elif tag == 'insert':
                ins[i1][r[j1:j2]] += 1
    half = len(rs) / 2.0
    out = []
    for k in range(len(ref)):
        if ins[k]:
            ch, cnt = ins[k].most_common(1)[0]
            if cnt > half: out.append(ch)
        ch, cnt = cols[k].most_common(1)[0]
        out.append(ch)
    if ins[len(ref)]:
        ch, cnt = ins[len(ref)].most_common(1)[0]
        if cnt > half: out.append(ch)
    return ''.join(out)

def clusters_of_run(run_obs):
    """stitch_run'in KUME adimini AYNEN tekrarla, ama kume okumalarini yakala (best'e indirmeden)."""
    nf = len(run_obs)
    deltas = [st.est_delta(run_obs[k], run_obs[k+1]) for k in range(nf-1)]
    valid = [d for d in deltas if d is not None and abs(d) < 200]
    gmed = sorted(valid)[len(valid)//2] if valid else 0.0
    deltas = [d if (d is not None and abs(d) < 200) else gmed for d in deltas]
    S = [0.0]*nf
    for k in range(1, nf): S[k] = S[k-1] + deltas[k-1]
    L = st.line_spacing(run_obs)
    items = []
    for k in range(nf):
        for o in run_obs[k]:
            if o[0]: items.append((st.cy(o)+S[k], o[1]))
    if not items: return [], gmed, L
    items.sort(key=lambda x: x[0])
    tol = max(8.0, L*0.45)
    clusters = [[items[0]]]
    for it in items[1:]:
        (clusters[-1].append(it) if it[0]-clusters[-1][0][0] <= tol else clusters.append([it]))
    return clusters, gmed, L

CACHE = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_CACHE")
target = (sys.argv[1] if len(sys.argv) > 1 else "BRONX").lower()
seg    = (sys.argv[2] if len(sys.argv) > 2 else "cikis").lower()
f = next(p for p in CACHE.glob("*.json") if target in p.stem.lower() and seg in p.stem.lower())
c = json.loads(f.read_text(encoding="utf-8"))
idx = c["idx"]; op = {int(k): v for k, v in c["ocr_pos"].items()}
runs = st.runs_of(idx)
print(f"FILM: {f.stem}  | idx={len(idx)} kare, {len(runs)} run\n")

rows = []   # (N, conf, mode_best, perchar, g_mode, g_pc, readings)
for run in runs:
    run_obs = [op[i] for i in run]
    if len(run) < 8: continue
    clusters, gmed, L = clusters_of_run(run_obs)
    if abs(gmed) <= max(3, L*0.3): continue   # akan degil -> atla
    for cl in clusters:
        readings = [x[1] for x in cl]
        if len(readings) < 3: continue
        mb, conf = st.pick_best(readings)
        pc = per_char_vote(readings)
        rows.append((len(readings), conf, mb, pc, st.garble(mb), st.garble(pc), readings))

diff   = [r for r in rows if st.norm(r[2]) != st.norm(r[3])]
better = [r for r in diff if r[5] < r[4] - 1e-9]
worse  = [r for r in diff if r[5] > r[4] + 1e-9]
print(f"AKAN satir-kumesi (N>=3): {len(rows)}")
print(f"  mode == per-char (AYNI)         : {len(rows)-len(diff)}")
print(f"  mode != per-char (FARKLI)       : {len(diff)}")
print(f"    -> per-char DAHA TEMIZ (garble dustu): {len(better)}")
print(f"    -> per-char DAHA KOTU                 : {len(worse)}")
print(f"    -> esit garble, farkli yazim         : {len(diff)-len(better)-len(worse)}")

diff.sort(key=lambda r: r[4]-r[5], reverse=True)
print("\n========== EN CARPICI FARKLAR (mode garble dususune gore) ==========")
for n, conf, mb, pc, gm, gp, rd in diff[:14]:
    print(f"\n  N={n}  conf={conf:.2f}  garble: mode={gm:.2f} -> perchar={gp:.2f}")
    print(f"    MODE    : '{mb}'")
    print(f"    PERCHAR : '{pc}'")
    uniq = list(dict.fromkeys(rd))
    print(f"    ham okumalar ({len(rd)} kare, {len(uniq)} benzersiz): " + " | ".join(repr(u) for u in uniq[:8]))

print("\n========== AYNI CIKAN (kolay vakalar — sistem zaten dogru) ilk 6 ==========")
same = [r for r in rows if st.norm(r[2]) == st.norm(r[3])][:6]
for n, conf, mb, pc, gm, gp, rd in same:
    print(f"  N={n} conf={conf:.2f}  '{mb}'")
