"""CACHE'den HIZLI RECOMPOSE — CLIP/OCR YOK. Sadece compose'u (yeni slitscan2 ile) yeniden çalıştırır.
Master ayarı değişince 1 saat beklemeden cache'li filmleri saniyede tazeler.
"""
import sys, glob, json, importlib.util
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
pl = importlib.util.module_from_spec(importlib.util.spec_from_file_location("pl", r"E:\MITAS\OCR-worktree\py\20260601_pipeline50.py"))
sys.modules["pl"] = pl; pl.__spec__.loader.exec_module(pl)
fp = pl.fp

dirs = {pl.safe_of(d.name): d for d in pl.DB.iterdir() if d.is_dir()}
caches = sorted(pl.CACHE.glob("*.json"))
print(f"{len(caches)} cache dosyası recompose ediliyor...")
for cj in caches:
    stem = cj.stem; safe, seg = stem.rsplit("__", 1)
    sub = "entry_frames" if seg == "giris" else "exit_frames"
    d = dirs.get(safe)
    if not d: print(f"  {stem}: DB dizini yok"); continue
    frames = sorted(glob.glob(str(d/sub/"*.png")))
    c = json.loads(cj.read_text(encoding="utf-8"))
    idx = c["idx"]; linesets = {int(k): set(v) for k, v in c["linesets"].items()}
    imgs = {i: fp.rd(frames[i]) for i in idx}
    master, man = pl.compose(frames, idx, imgs, linesets)
    if master is not None:
        fp.wr(pl.MAST/f"{stem}.png", master)
        kinds = [m.get("kind") for m in man]
        print(f"  {stem}: {master.shape[1]}x{master.shape[0]}  bloklar={len(man)} scroll={kinds.count('scroll')} kart={kinds.count('card')}")
    else:
        print(f"  {stem}: master yok")
print("bitti.")
