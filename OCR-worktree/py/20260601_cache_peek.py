"""CACHE PEEK — bir filmin cache'inde NE VAR? idx (CLIP kredi kare sayısı) + toplam OCR satırı + örnek.
Boş/zor segmentlerin sebebini görmek için (CLIP mi bulamadı, OCR mu boş, clean mı sildi?). Salt-okuma, stdlib.
Kullanım: python 20260601_cache_peek.py <alt-dize ...>
"""
import sys, json, unicodedata
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
CACHE = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_CACHE")
KUN = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100\_KUNYE")
def norm(s): return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))
for sub in sys.argv[1:]:
    s = norm(sub)
    for cj in sorted(CACHE.glob("*.json")):
        if s not in norm(cj.stem): continue
        try:
            c = json.loads(cj.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"\n{cj.stem}: BOZUK ({e})"); continue
        idx = c.get("idx", []); op = c.get("ocr_pos", {})
        tot = sum(len(v) for v in op.values())
        texts = [o[1] for v in op.values() for o in v if o and o[0]]
        kp = KUN/f"{cj.stem}.txt"
        kn = len([l for l in kp.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]) if kp.exists() else 0
        print(f"\n===== {cj.stem} =====")
        print(f"  CLIP-kredi kare(idx)={len(idx)} | toplam OCR satırı={tot} | benzersiz~={len(set(texts))} | son künye={kn}")
        if texts:
            print("  örnek OCR (ilk 14):")
            seen = []
            for t in texts:
                if t not in seen: seen.append(t)
                if len(seen) >= 14: break
            for t in seen: print("    ", t)
        else:
            print("  (OCR hiç metin bulmadı -> footage/karanlık kareler)")
