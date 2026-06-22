"""C — OCR-UZAYINDA DİKME + GÜVEN-KAPISI + BULANIK-MODE. Salt cache/ocr_pos üstünde (CLIP/OCR yok).
Birikimli kayma S_k ile global koordinat g=cy+S_k -> akanda fiziksel satır için g sabit -> g'ye göre kümele.
Küme içinde BULANIK-MODE: yakın okumaları grupla, en büyük grup=consensus, conf=grup/küme; en temiz üye=best.
GÜVEN-KAPISI: conf<thr olan satır (tekrarı yok=garble) ana künyeden düşer, 'düşük güven'e gider.
API: stitch_kunye(runs, ocr_pos, conf_thr) -> (main, low, medconf)
"""
import sys, json, unicodedata, difflib, os
from collections import Counter
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
VOWELS = set("aeıioöuüâîû")
# FIX 1 (2026-06-22): pick_best temsilcisini ÖNCE temiz okumalar arasında FREKANSLA seç.
# Tekrarlı-temiz (JAMES DARREN ×7) tek-seferlik garble'ı (DAMES DARREN ×1) yenmeli; eski
# kod garble()=0.0 beraberliğinde ilk-geleni alıp garble seçiyordu. AKTİF (default ON; AYI YOGİ
# canlı-kanıtlı + non-regresyon audit PASS). MITAS_STITCH_FREQVOTE=0 ile eski davranışa dönülür (kill-switch).
_FREQVOTE = os.environ.get("MITAS_STITCH_FREQVOTE", "1").strip().lower() in ("1", "true", "on", "yes")
def norm(s): return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))
def tsim(a, b): return difflib.SequenceMatcher(None, a, b).ratio()
def cy(o): return (o[2]+o[3])/2.0
def garble(raw):
    t = raw.strip(); nonsp = sum(not c.isspace() for c in t); letters = sum(c.isalpha() for c in t)
    if nonsp == 0: return 9.0
    s = (1-letters/nonsp)*2.0
    for tk in t.split():
        ft = norm(tk)
        if len(ft) >= 4 and not any(c in VOWELS for c in ft): s += 1.0
    return s

def pick_best(readings):
    """bulanık-mode: yakın okumaları grupla; en büyük grup consensus; conf=grup/toplam; best=en temiz üye."""
    groups = []
    for raw in readings:
        f = norm(raw)
        hit = next((g for g in groups if tsim(f, g["rep"]) >= 0.80), None)
        if hit: hit["m"].append(raw)
        else: groups.append({"rep": f, "m": [raw]})
    groups.sort(key=lambda g: -len(g["m"]))
    top = groups[0]
    if _FREQVOTE:
        # FIX 1: ÖNCE temiz okumalar (garble==0.0) arasında en sık geçen yazımı seç →
        # garble bir temizi ASLA oylamada geçemez (clean-pool). Hata → eski davranışa düş.
        try:
            cnt = Counter(top["m"])
            clean = [r for r in top["m"] if garble(r) == 0.0]
            pool = clean or top["m"]
            best = min(pool, key=lambda r: (-cnt[r], garble(r), -len(r)))
        except Exception:
            best = min(top["m"], key=lambda r: (garble(r), -len(r)))
    else:
        best = min(top["m"], key=lambda r: (garble(r), -len(r)))
    return best, len(top["m"])/len(readings)

def est_delta(A, B):
    cand = []
    for a in A:
        if not a[0]: continue
        for b in B:
            if b[0] and abs(len(a[0])-len(b[0])) <= 2 and tsim(a[0], b[0]) >= 0.80:
                cand.append(cy(a)-cy(b))
    if not cand: return None
    cand.sort(); return cand[len(cand)//2]

def line_spacing(run_obs):
    gaps = []
    for obs in run_obs:
        ys = sorted(cy(o) for o in obs)
        gaps += [ys[i+1]-ys[i] for i in range(len(ys)-1) if 5 < ys[i+1]-ys[i] < 200]
    if not gaps: return 40.0
    gaps.sort(); return gaps[len(gaps)//2]

def stitch_run(run_obs):
    nf = len(run_obs)
    deltas = [est_delta(run_obs[k], run_obs[k+1]) for k in range(nf-1)]
    valid = [d for d in deltas if d is not None and abs(d) < 200]
    gmed = sorted(valid)[len(valid)//2] if valid else 0.0
    deltas = [d if (d is not None and abs(d) < 200) else gmed for d in deltas]
    S = [0.0]*nf
    for k in range(1, nf): S[k] = S[k-1]+deltas[k-1]
    L = line_spacing(run_obs)
    items = []
    for k in range(nf):
        for o in run_obs[k]:
            if o[0]: items.append((cy(o)+S[k], o[1]))
    if not items: return [], gmed, L, 0.0
    items.sort(key=lambda x: x[0])
    tol = max(8.0, L*0.45)
    clusters = [[items[0]]]
    for it in items[1:]:                                          # KÜME-GENİŞLİĞİ sınırı (baştan <=tol) — tek-bağ zincirini önler
        (clusters[-1].append(it) if it[0]-clusters[-1][0][0] <= tol else clusters.append([it]))
    out = []
    for cl in clusters:
        best, conf = pick_best([c[1] for c in cl])
        out.append([cl[0][0], best, len(cl), conf])
    out.sort(key=lambda x: x[0])
    merged = []
    for o in out:
        if merged and tsim(norm(o[1]), norm(merged[-1][1])) >= 0.88:
            merged[-1][2] += o[2]; merged[-1][3] = max(merged[-1][3], o[3]); continue
        merged.append(o)
    confs = [o[3] for o in merged]
    return merged, gmed, L, (sorted(confs)[len(confs)//2] if confs else 0.0)

def dedup_static(run_obs):
    groups = []
    for obs in run_obs:
        for o in obs:
            if not o[0]: continue
            hit = next((g for g in groups if tsim(o[0], g["f"]) >= 0.82), None)
            (hit["r"].append(o[1]) if hit else groups.append({"f": o[0], "r": [o[1]]}))
    return [pick_best(g["r"])[0] for g in groups]

def runs_of(idx):
    runs = [[idx[0]]]
    for j in idx[1:]:
        (runs[-1].append(j) if j-runs[-1][-1] <= 3 else runs.append([j]))
    return runs

def stitch_kunye(runs, ocr_pos, conf_thr=0.34):
    """KEEP-ALL: tüm dikilen satırları SIRAYLA döndür (hiç DROP yok -> gerçek isim kaybolmaz).
    low = sadece düşük-güven ALT KÜMESİ (işaretleme/rapor için); ana künyeden ÇIKARILMAZ."""
    lines = []; low = []; confs = []
    for run in runs:
        run_obs = [ocr_pos[i] for i in run]
        if len(run) >= 8:
            st, gmed, L, mc = stitch_run(run_obs)
            if abs(gmed) > max(3, L*0.3):                 # AKAN -> dik (per-frame garble -> tek temiz okuma)
                confs.append(mc)
                for o in st:                               # o = [g, best, n, conf, x]
                    lines.append(o[1])                     # HEPSİ ana künyede (DROP yok)
                    if o[3] < conf_thr: low.append(o[1])   # düşük-güven sadece işaretlenir
                continue
        lines += dedup_static(run_obs)                     # statik -> güvenilir
    return lines, low, (sorted(confs)[len(confs)//2] if confs else 1.0)

if __name__ == "__main__":
    CACHE = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_CACHE")
    KUN = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_KUNYE")
    for sub in sys.argv[1:]:
        s = norm(sub)
        for cj in sorted(CACHE.glob("*.json")):
            if s not in norm(cj.stem): continue
            c = json.loads(cj.read_text(encoding="utf-8")); idx = c["idx"]
            if not idx: continue
            op = {int(k): v for k, v in c["ocr_pos"].items()}
            kp = KUN/f"{cj.stem}.txt"
            old = len([l for l in kp.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]) if kp.exists() else 0
            main, low, mc = stitch_kunye(runs_of(idx), op)
            print(f"\n===== {cj.stem} =====")
            print(f"  ESKİ={old}  ->  GATE ana={len(main)}  düşük-güven={len(low)}  | medconf={mc:.2f}")
            print("  --- ana künye (ilk 28) ---")
            for l in main[:28]: print("    ", l)
            if low:
                print("  --- atılan düşük-güven (ilk 8) ---")
                for l in low[:8]: print("    ✗", l)
