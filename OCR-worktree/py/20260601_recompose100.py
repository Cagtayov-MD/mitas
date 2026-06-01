"""pipeline100 cache'inden HIZLI RECOMPOSE — CLIP/OCR YOK. Düzeltilmiş compose_hybrid'i yeniden uygular.
Cache'de idx + per-frame ocr_pos zaten var; sadece kareleri okuyup yeniden diziyoruz.
Kullanım: python 20260601_recompose100.py [alt-dize]   (alt-dize verilmezse TÜM cache'ler)
"""
import sys, glob, importlib.util, json, unicodedata
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")
def load(m, p):
    s = importlib.util.spec_from_file_location(m, p); mod = importlib.util.module_from_spec(s); sys.modules[m] = mod; s.loader.exec_module(mod); return mod
pl = load("pl", r"E:\MITAS\OCR-worktree\py\20260601_pipeline100.py")
import duckdb

def norm(s): return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))
filts = [norm(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else None

dirs = {pl.safe_of(d.name): d for d in pl.DB.iterdir() if d.is_dir()}
con = duckdb.connect(pl.cr.DB, read_only=True)
caches = sorted(pl.CACHE.glob("*.json"))
n = 0; changed = []
for cj in caches:
    stem = cj.stem
    if filts and not any(f in norm(stem) for f in filts): continue
    safe, seg = stem.rsplit("__", 1)
    sub = "entry_frames" if seg == "giris" else "exit_frames"
    d = dirs.get(safe)
    if not d: print(f"  {stem}: DB yok"); continue
    frames = sorted(glob.glob(str(d/sub/"*.png")))
    try:
        c = json.loads(cj.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  {stem}: BOZUK cache, atla ({e})"); continue
    idx = c["idx"]; ocr_pos = {int(k): v for k, v in c["ocr_pos"].items()}
    if not idx: continue
    # eski künye satır sayısı (kıyas için)
    kp = pl.KUN/f"{stem}.txt"
    old_k = len([l for l in kp.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]) if kp.exists() else 0
    imgs = {i: pl.fp.rd(frames[i]) for i in idx}
    master, placed_raw = pl.compose_hybrid(frames, idx, imgs, ocr_pos)
    asr = ""
    ap_ = list(d.glob("audio_transcript.txt"))
    if ap_: asr = pl.fold(ap_[0].read_text(encoding="utf-8", errors="ignore"))
    merged, buckets, asr_drop, dieg = pl.cl.clean(placed_raw, con, asr)
    if master is not None: pl.fp.wr(pl.MAST/f"{stem}.png", master)
    kp.write_text(("# DIEGETIK %{:.0f}\n".format(dieg*100) if dieg > 0.30 else "") +
                  "\n".join(pl.tr_upper(t) for t, _, _ in merged), encoding="utf-8")
    h = int(master.shape[0]) if master is not None else 0
    n += 1
    delta = len(merged) - old_k
    flag = "  <== DEGISTI" if abs(delta) >= 5 else ""
    if abs(delta) >= 5: changed.append((stem, old_k, len(merged)))
    print(f"  {stem[:48]:48} künye {old_k:>4}->{len(merged):>4} h={h:>6}{flag}")
con.close()
print(f"\n{n} segment recompose edildi. Belirgin degisen: {len(changed)}")
