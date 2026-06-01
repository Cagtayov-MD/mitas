"""50-FİLM ENTEGRE: CLIP-tespit -> kredi karelerini OCR -> temiz künye -> master PNG -> tek klasöre topla.
Master dedup = OCR-metin Jaccard (kart = aynı satır-kümesi; scroll = satırlar sürekli akıyor -> slitscan).
Çıktı: clip_pipeline50/_MASTERS/<film>__<seg>.png  +  _KUNYE/<film>__<seg>.txt  +  _SUMMARY.json
"""
import sys, glob, importlib.util, json, argparse
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
def load(mod, path):
    s = importlib.util.spec_from_file_location(mod, path); m = importlib.util.module_from_spec(s)
    sys.modules[mod] = m; s.loader.exec_module(m); return m
cp = load("cp", r"E:\MITAS\OCR-worktree\py\20260601_clip_probe.py")
cl = load("cl", r"E:\MITAS\OCR-worktree\py\20260601_clean.py")
sl = load("sl", r"E:\MITAS\OCR-worktree\py\20260601_slitscan2.py")   # hizalama-mozaiği (dikiş glitch fix)
fp = cl.fp; read_oneocr = cl.read_oneocr; fold = cl.fold; cr = cl.cr; tr_upper = cl.tr_upper
import duckdb

DB = Path(r"F:\REPO_GitHub\DATABASE")
OUT = Path(r"E:\MITAS\OCR-worktree\clip_pipeline50")
MAST = OUT/"_MASTERS"; KUN = OUT/"_KUNYE"; CACHE = OUT/"_CACHE"
THR = 0.5; W = 720
SEGS = [("giris", "entry_frames"), ("cikis", "exit_frames")]

def safe_of(n): return "".join(c if c.isalnum() else "_" for c in n)[:40]
def jac(a, b):
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return len(a & b)/len(a | b)

def row_proj(img):
    """tophat(yazı maskesi) satır-yoğunluğu profili — dikey hareket ölçmek için (zemin-agnostik)."""
    return fp.tophat(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)).sum(axis=1).astype(np.float32)
def vshift(pa, pb, maxd=40):
    """pa->pb arası en iyi dikey kayma (px). Scroll => tutarlı işaretli kayma."""
    a0, b0 = pa-pa.mean(), pb-pb.mean(); n = len(pa); best, bv = 0, -2.0
    for d in range(-maxd, maxd+1):
        x, y = (a0[d:], b0[:n-d]) if d >= 0 else (a0[:n+d], b0[-d:])
        if len(x) < 20: continue
        v = float(np.dot(x, y)/(np.linalg.norm(x)*np.linalg.norm(y)+1e-6))
        if v > bv: bv, best = v, d
    return best
def is_scroll(run, imgs):
    """GERÇEK scroll = metnin tutarlı dikey hareketi (yavaş scroll'u OCR-Jaccard kart sanıyordu)."""
    if len(run) < 10: return False
    projs = [row_proj(imgs[i]) for i in run]
    dys = [vshift(projs[k], projs[k+1], 150) for k in range(len(projs)-1)]   # seyrek-örnekli büyük sıçrama (~60px) için geniş menzil
    if not dys: return False
    md = float(np.median(np.abs(dys)))
    ss = max(np.mean([d > 0 for d in dys]), np.mean([d < 0 for d in dys]))
    return md >= 2.0 and ss >= 0.7

def compose(frames, idx, imgs, linesets):
    """idx: kredi kare indeksleri; imgs: {i:bgr}; linesets: {i:set(fold satır)}."""
    # FOOTAGE-FP FİLTRESİ: yazısı olmayan kareleri (savaş sahnesi/manzara — CLIP yanlış-pozitif) DİZME.
    # Yazı var = >=2 OCR satırı VEYA >=2 kelimeli bir satır (LEE MARVIN gibi tek-satır kart korunur).
    idx = [i for i in idx if len(linesets.get(i, set())) >= 2 or any(len(l.split()) >= 2 for l in linesets.get(i, set()))]
    if not idx: return None, []
    runs = [[idx[0]]]
    for j in idx[1:]:
        (runs[-1].append(j) if j-runs[-1][-1] <= 3 else runs.append([j]))
    blocks, man = [], []
    for run in runs:
        if is_scroll(run, imgs):                                  # akan -> tek panorama (hizalama-mozaiği)
            blk = sl.slitscan2([frames[i] for i in run])
            if blk is not None and getattr(blk, "size", 0) and blk.shape[0] >= 60:
                blocks.append(blk); man.append({"run": [run[0], run[-1]], "kind": "scroll"}); continue
        cards = [[run[0]]]                                        # statik -> kart-dedup (Jaccard)
        for i in run[1:]:
            (cards[-1].append(i) if jac(linesets[i], linesets[cards[-1][-1]]) >= 0.5 else cards.append([i]))
        for card in cards:
            rep = max(card, key=lambda i: len(linesets[i]))
            blocks.append(imgs[rep]); man.append({"card": [card[0], card[-1]], "rep": rep, "kind": "card"})
    if not blocks: return None, man
    norm = [cv2.resize(b, (W, int(b.shape[0]*W/b.shape[1]))) for b in blocks]
    sep = np.full((6, W, 3), 40, np.uint8); stack = []
    for b in norm: stack += [b, sep]
    return np.vstack(stack[:-1]), man

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=50); ap.add_argument("--only", default="")
    a = ap.parse_args()
    MAST.mkdir(parents=True, exist_ok=True); KUN.mkdir(parents=True, exist_ok=True); CACHE.mkdir(parents=True, exist_ok=True)
    films = []
    for d in sorted(DB.iterdir(), key=lambda p: p.name.lower()):
        if not d.is_dir(): continue
        if a.only and a.only.lower() not in d.name.lower(): continue
        if glob.glob(str(d/"entry_frames"/"*.png")) or glob.glob(str(d/"exit_frames"/"*.png")):
            films.append(d)
        if not a.only and len(films) >= a.n: break
    print(f"{len(films)} film. CLIP yükleniyor...", flush=True)
    model, preprocess, tok = cp.load_clip(); ls = model.logit_scale.exp().item()
    cred = cp.class_embed(model, tok, cp.CREDIT_PROMPTS); scene = cp.class_embed(model, tok, cp.SCENE_PROMPTS)
    con = duckdb.connect(cr.DB, read_only=True)
    summary = []
    for n, d in enumerate(films, 1):
        safe = safe_of(d.name); asr = ""
        ap_ = list(d.glob("audio_transcript.txt"))
        if ap_: asr = fold(ap_[0].read_text(encoding="utf-8", errors="ignore"))
        rec = {"film": d.name}
        for seg, sub in SEGS:
            frames = sorted(glob.glob(str(d/sub/"*.png")))
            if not frames: continue
            if (KUN/f"{safe}__{seg}.txt").exists():           # resume: bu seg zaten yapıldı
                print(f"  [{n}/{len(films)}] {d.name[:34]:36} {seg}: atlandı (var)", flush=True); continue
            ps = cp.med_smooth(cp.score_frames(model, preprocess, frames, cred, scene, ls), 5)
            idx = [i for i in range(len(ps)) if ps[i] >= THR]
            imgs = {i: fp.rd(frames[i]) for i in idx}
            linesets = {}; raw = []
            for i in idx:
                lines = read_oneocr(imgs[i]); linesets[i] = set(fold(x) for x in lines if x.strip()); raw += lines
            (CACHE/f"{safe}__{seg}.json").write_text(json.dumps(
                {"idx": idx, "linesets": {str(i): sorted(linesets[i]) for i in idx}}, ensure_ascii=False), encoding="utf-8")
            merged, buckets, asr_drop, dieg = cl.clean(raw, con, asr)
            master, man = compose(frames, idx, imgs, linesets)
            if master is not None: fp.wr(MAST/f"{safe}__{seg}.png", master)
            (KUN/f"{safe}__{seg}.txt").write_text(
                (f"# ⚠ DİEGETİK-PROSE %{dieg*100:.0f}\n" if dieg > 0.30 else "") +
                "\n".join(tr_upper(t) for t, _, _ in merged), encoding="utf-8")
            rec[seg] = {"frames": len(frames), "credit": len(idx), "kunye": len(merged),
                        "master_h": int(master.shape[0]) if master is not None else 0,
                        "blocks": len(man), "diegetik": round(dieg, 2)}
        summary.append(rec)
        g = rec.get("giris", {}); c = rec.get("cikis", {})
        print(f"  [{n}/{len(films)}] {d.name[:34]:36} G:kredi={g.get('credit')} künye={g.get('kunye')} | "
              f"Ç:kredi={c.get('credit')} künye={c.get('kunye')} dieg={c.get('diegetik')}", flush=True)
    con.close()
    (OUT/"_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> MASTER'lar: {MAST}\n-> künyeler: {KUN}", flush=True)

if __name__ == "__main__":
    main()
