"""100-FİLM KÜNYE METNİ. CLIP-tespit -> kareleri OCR-konumlu oku -> stx.stitch_kunye (OCR-uzayında dikme: her satırın EN TEMİZ okuması; garble tufanı biter).
Görsel master dalı (compose_hybrid + line-mozaik + slitscan) 2026-07-30 tek-motor temizliğinde söküldü — görsel master artık YALNIZ İbrahimovic (harness/master_dup/ibrahimovic.py).
Bu dosya üretim metin zincirinin (scripts/_pipe_ocr.py: pl.read_pos/cl/stx) modül deposudur.
Çıktı: clip_pipeline100/_KUNYE|_CACHE  + _SUMMARY.json
"""
import sys, os, glob, importlib.util, json, argparse
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
def load(m, p):
    s = importlib.util.spec_from_file_location(m, p); mod = importlib.util.module_from_spec(s); sys.modules[m] = mod; s.loader.exec_module(mod); return mod
# Linux fix (2026-07-30): _pipe_ocr 07-16'da env-aware yapılmış ama BU dosyanın
# kendi load'ları ham E:\MITAS kalmıştı — köprü dizin OCR-worktree içermeyince
# import patlıyor, üretim sessizce eski-OneOCR fallback'ine düşüyordu.
# Aynı sınıf: crop-stack'in yarım Linux fix'i (bounding_rect eklendi, words unutuldu).
_PY_KOK = str(Path(os.environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS") / "OCR-worktree" / "py")
cp = load("cp", _PY_KOK + os.sep + "20260601_clip_probe.py")
cl = load("cl", _PY_KOK + os.sep + "20260601_clean.py")
stx = load("stx", _PY_KOK + os.sep + "20260601_stitch.py")    # OCR-uzayında dikme (künye METNİ)
fp = cl.fp; fold = cl.fold; tr_upper = cl.tr_upper; cr = cl.cr
import duckdb

DB = Path(r"F:\REPO_GitHub\DATABASE")
OUT = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100")
KUN = OUT/"_KUNYE"; CACHE = OUT/"_CACHE"
THR = 0.5; SEGS = [("giris", "entry_frames"), ("cikis", "exit_frames")]

def safe_of(n): return "".join(c if c.isalnum() else "_" for c in n)[:40]
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

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=100); ap.add_argument("--only", default="")
    a = ap.parse_args()
    for d in (KUN, CACHE): d.mkdir(parents=True, exist_ok=True)
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
                (KUN/f"{safe}__{seg}.txt").write_text("", encoding="utf-8"); rec[seg] = {"frames": len(frames), "credit": 0, "kunye": 0}; continue
            imgs = {i: fp.rd(frames[i]) for i in idx}
            ocr_pos = {i: read_pos(imgs[i]) for i in idx}
            placed_raw, _lowconf, _medconf = stx.stitch_kunye(stx.runs_of(idx), ocr_pos)
            merged, buckets, asr_drop, dieg = cl.clean(placed_raw, con, asr)
            (KUN/f"{safe}__{seg}.txt").write_text(("# DIEGETIK %{:.0f}\n".format(dieg*100) if dieg > 0.30 else "") + "\n".join(tr_upper(t) for t, _, _ in merged), encoding="utf-8")
            (CACHE/f"{safe}__{seg}.json").write_text(json.dumps({"idx": idx, "ocr_pos": {str(i): ocr_pos[i] for i in idx}}, ensure_ascii=False), encoding="utf-8")
            rec[seg] = {"frames": len(frames), "credit": len(idx), "kunye": len(merged), "diegetik": round(dieg, 2)}
        summary.append(rec)
        g = rec.get("giris", {}); c = rec.get("cikis", {})
        print(f"  [{n}/{len(films)}] {d.name[:32]:34} G:k={g.get('credit')} künye={g.get('kunye')} | Ç:k={c.get('credit')} künye={c.get('kunye')}", flush=True)
    con.close()
    (OUT/"_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {KUN}", flush=True)

if __name__ == "__main__":
    main()
