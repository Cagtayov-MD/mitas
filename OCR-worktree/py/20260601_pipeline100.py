"""100-FİLM — BİRLEŞİK SATIR-MOZAİĞİ. CLIP-tespit -> kareleri OCR-konumlu oku -> her kareden YALNIZ görülmemiş satırları kırpıp ekle.
Scroll / yavaş-drift / ayrık-kart / footage -> HEPSİ tek mantık (her satır bir kez). Footage'da yazı yok -> hiç eklenmez (otomatik elenir).
Bonus: text-bandına kırpıldığı için footage arka planı azalır; ve mozaik metni = temiz künye (895-garble biter).
Çıktı: clip_pipeline100/_MASTERS|_KUNYE|_CACHE  + _SUMMARY.json
"""
import sys, glob, importlib.util, json, argparse, difflib
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
def load(m, p):
    s = importlib.util.spec_from_file_location(m, p); mod = importlib.util.module_from_spec(s); sys.modules[m] = mod; s.loader.exec_module(mod); return mod
cp = load("cp", r"E:\MITAS\OCR-worktree\py\20260601_clip_probe.py")
cl = load("cl", r"E:\MITAS\OCR-worktree\py\20260601_clean.py")
sl = load("sl", r"E:\MITAS\OCR-worktree\py\20260601_slitscan2.py")   # piksel-mozaiği (hareketli scroll için)
stx = load("stx", r"E:\MITAS\OCR-worktree\py\20260601_stitch.py")    # OCR-uzayında dikme (künye METNİ)
fp = cl.fp; fold = cl.fold; tr_upper = cl.tr_upper; cr = cl.cr
import duckdb

DB = Path(r"F:\REPO_GitHub\DATABASE")
OUT = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100")
MAST = OUT/"_MASTERS"; KUN = OUT/"_KUNYE"; CACHE = OUT/"_CACHE"
THR = 0.5; SEGS = [("giris", "entry_frames"), ("cikis", "exit_frames")]

def safe_of(n): return "".join(c if c.isalnum() else "_" for c in n)[:40]
def near(a, b):
    if not a or not b: return a == b
    if abs(len(a.split())-len(b.split())) > 1: return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.82

def read_pos(img):
    """OCR -> [(fold, raw, y0, y1)] y'ye göre sıralı. Uzun görüntü (mozaik) için dikey tile."""
    eng = cl.rw.get_oneocr(); H = img.shape[0]; TILE, OV = 1400, 150; out = []; y = 0
    while y < H:
        tile = img[y:min(y+TILE, H), :]
        if tile.shape[0] < 40: break
        res = eng.recognize_cv2(np.ascontiguousarray(tile))
        for ln in (res.get("lines") or []):
            t = (ln.get("text") or "").strip()
            if not t: continue
            br = ln.get("bounding_rect") or {}
            ys = [float(br.get(k, 0) or 0) for k in ("y1", "y2", "y3", "y4")]
            out.append((fold(t), t, int(min(ys))+y, int(max(ys))+y))
        if y+TILE >= H: break
        y += TILE-OV
    out.sort(key=lambda L: L[2])
    return out

def is_placed(f, placed):
    """zaten yerleştirildi mi: fuzzy YA DA içerme (OCR satır birleştirme/bölme varyasyonu için)."""
    return any(near(f, p) or (len(f) >= 6 and f in p) or (len(p) >= 6 and p in f) for p in placed)

def is_scroll(run, imgs):
    """hareket VAR mı: row-profil tutarlı dikey kayma. Piksel-mozaiği bunda temiz; hareketsizde line-mozaiği."""
    if len(run) < 8: return False
    sigs = [sl.row_sig(imgs[i]) for i in run]
    sh = [sl.best_shift(sigs[k], sigs[k+1]) for k in range(len(sigs)-1)]
    if not sh: return False
    return float(np.median([s for s, c in sh])) >= 3 and float(np.median([c for s, c in sh])) >= 0.4

def line_mosaic_run(run, imgs, ocr_pos, placed, W, pad=4):
    """hareketsiz run: her kareden GÖRÜLMEMİŞ satırların bandını kırp (drift/kart/footage sınırlı)."""
    bands = []; lines = []
    for i in run:
        H = imgs[i].shape[0]
        new = [L for L in ocr_pos[i] if L[0] and not is_placed(L[0], placed)]
        if not new: continue
        y0 = max(0, min(L[2] for L in new)-pad); y1 = min(H, max(L[3] for L in new)+pad)
        if y1 <= y0: continue
        b = imgs[i][y0:y1, :]
        if b.shape[1] < W: b = cv2.copyMakeBorder(b, 0, 0, 0, W-b.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0))
        bands.append(b)
        for L in new: placed.append(L[0]); lines.append(L[1])
    return bands, lines

def compose_hybrid(frames, idx, imgs, ocr_pos):
    """KÜNYE METNİ = OCR-uzayında dikme (stx.stitch_kunye: her satırın EN TEMİZ okuması; garble tufanı biter).
    GÖRSEL MASTER = panorama metin taşıyorsa o (slitscan2); yoksa line-mozaiği bantları (asla siyah)."""
    runs = [[idx[0]]]
    for j in idx[1:]:
        (runs[-1].append(j) if j-runs[-1][-1] <= 3 else runs.append([j]))
    W = max(imgs[i].shape[1] for i in idx)
    # --- KÜNYE METNİ: OCR-uzayı dikme (per-frame garble -> tek temiz okuma; isim DROP yok) ---
    text, low_conf, medconf = stx.stitch_kunye(runs, ocr_pos)
    # --- GÖRSEL MASTER: temiz panorama varsa onu, yoksa line-mozaiği bantları ---
    blocks = []; vplaced = []
    for run in runs:
        if is_scroll(run, imgs):
            blk = sl.slitscan2([frames[i] for i in run])
            if blk is not None and getattr(blk, "size", 0) and blk.shape[0] >= 60:
                if len([L for L in read_pos(blk) if L[0]]) >= 5:
                    blocks.append(blk); continue
        bands, _ = line_mosaic_run(run, imgs, ocr_pos, vplaced, W)
        blocks += bands
    if not blocks: return None, text
    norm = [cv2.copyMakeBorder(b, 0, 0, 0, W-b.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0)) if b.shape[1] < W else b for b in blocks]
    return np.vstack(norm), text

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=100); ap.add_argument("--only", default="")
    a = ap.parse_args()
    for d in (MAST, KUN, CACHE): d.mkdir(parents=True, exist_ok=True)
    films = []
    for d in sorted(DB.iterdir(), key=lambda p: p.name.lower()):
        if not d.is_dir(): continue
        if a.only and a.only.lower() not in d.name.lower(): continue
        if glob.glob(str(d/"entry_frames"/"*.png")) or glob.glob(str(d/"exit_frames"/"*.png")): films.append(d)
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
            if (KUN/f"{safe}__{seg}.txt").exists(): continue       # resume
            frames = sorted(glob.glob(str(d/sub/"*.png")))
            if not frames: continue
            ps = cp.med_smooth(cp.score_frames(model, preprocess, frames, cred, scene, ls), 5)
            idx = [i for i in range(len(ps)) if ps[i] >= THR]
            if not idx:
                (KUN/f"{safe}__{seg}.txt").write_text("", encoding="utf-8"); rec[seg] = {"frames": len(frames), "credit": 0, "kunye": 0, "master_h": 0}; continue
            imgs = {i: fp.rd(frames[i]) for i in idx}
            ocr_pos = {i: read_pos(imgs[i]) for i in idx}
            master, placed_raw = compose_hybrid(frames, idx, imgs, ocr_pos)
            merged, buckets, asr_drop, dieg = cl.clean(placed_raw, con, asr)
            if master is not None: fp.wr(MAST/f"{safe}__{seg}.png", master)
            (KUN/f"{safe}__{seg}.txt").write_text(("# DIEGETIK %{:.0f}\n".format(dieg*100) if dieg > 0.30 else "") + "\n".join(tr_upper(t) for t, _, _ in merged), encoding="utf-8")
            (CACHE/f"{safe}__{seg}.json").write_text(json.dumps({"idx": idx, "ocr_pos": {str(i): ocr_pos[i] for i in idx}}, ensure_ascii=False), encoding="utf-8")
            rec[seg] = {"frames": len(frames), "credit": len(idx), "kunye": len(merged), "master_h": int(master.shape[0]) if master is not None else 0, "diegetik": round(dieg, 2)}
        summary.append(rec)
        g = rec.get("giris", {}); c = rec.get("cikis", {})
        print(f"  [{n}/{len(films)}] {d.name[:32]:34} G:k={g.get('credit')} künye={g.get('kunye')} h={g.get('master_h')} | Ç:k={c.get('credit')} künye={c.get('kunye')} h={c.get('master_h')}", flush=True)
    con.close()
    (OUT/"_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {MAST}", flush=True)

if __name__ == "__main__":
    main()
