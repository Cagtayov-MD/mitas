"""KREDİ KARELERİNİ x-KOORDİNATIYLA YENİDEN OCR'LA (CLIP tespiti idx cache'den -> yeniden tespit YOK).
Cache'i x'li ocr_pos ile günceller (6'lı: fold,raw,y0,y1,x0,x1). 2-kolon sütun-ayrımı için x şart.
Kullanım: python 20260601_reocr_x.py [alt-dize ...]   (yoksa TÜM cache'ler)
"""
import sys, glob, importlib.util, json, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
def load(m, p):
    s = importlib.util.spec_from_file_location(m, p); mod = importlib.util.module_from_spec(s); sys.modules[m] = mod; s.loader.exec_module(mod); return mod
pl = load("pl", r"E:\MITAS\OCR-worktree\py\20260601_pipeline100.py")
def norm(s): return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))
filts = [norm(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else None

dirs = {pl.safe_of(d.name): d for d in pl.DB.iterdir() if d.is_dir()}
caches = sorted(pl.CACHE.glob("*.json"))
n = 0
for cj in caches:
    stem = cj.stem
    if filts and not any(f in norm(stem) for f in filts): continue
    safe, seg = stem.rsplit("__", 1); sub = "entry_frames" if seg == "giris" else "exit_frames"
    d = dirs.get(safe)
    if not d: print(f"  {stem}: DB yok"); continue
    frames = sorted(glob.glob(str(d/sub/"*.png")))
    c = json.loads(cj.read_text(encoding="utf-8")); idx = c["idx"]
    if not idx: continue
    has_x = any(len(o) >= 6 for v in c.get("ocr_pos", {}).values() for o in (v or []))
    if has_x: print(f"  {stem[:50]:50} zaten x'li, atla"); continue
    ocr_pos = {i: pl.read_pos(pl.fp.rd(frames[i])) for i in idx}
    cj.write_text(json.dumps({"idx": idx, "ocr_pos": {str(i): ocr_pos[i] for i in idx}}, ensure_ascii=False), encoding="utf-8")
    n += 1
    print(f"  {stem[:50]:50} idx={len(idx)} -> x'li OCR ✓", flush=True)
print(f"\n{n} cache x ile yeniden OCR'landı.")
