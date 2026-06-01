"""15 FİLM — zero-shot CLIP kredi-tespiti DOĞRULAMA (ölçek testi).
Her film için tek 'kanıt kartı': giriş+çıkış, CLIP'in KREDİ vs FOOTAGE dediği kareler yan yana.
Amaç: tespit her filmde tutarlı mı? Footage'ı krediden ayırıyor mu?
Çıktı: clip_probe/_REVIEW15/<film>.png  +  _SUMMARY.json/.txt
"""
import sys, glob, importlib.util, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location("cp", r"E:\MITAS\OCR-worktree\py\20260601_clip_probe.py")
cp = importlib.util.module_from_spec(spec); sys.modules["cp"] = cp; spec.loader.exec_module(cp)

DB = Path(r"F:\REPO_GitHub\DATABASE")
REV = Path(r"E:\MITAS\OCR-worktree\clip_probe\_REVIEW15"); REV.mkdir(parents=True, exist_ok=True)
N, THR = 15, 0.5

films = []
for d in sorted(DB.iterdir(), key=lambda p: p.name.lower()):
    if not d.is_dir(): continue
    if glob.glob(str(d/"entry_frames"/"*.png")) or glob.glob(str(d/"exit_frames"/"*.png")):
        films.append(d)
    if len(films) >= N: break
print(f"{len(films)} film:")
for d in films: print("   ", d.name)

print("CLIP yükleniyor...")
model, preprocess, tok = cp.load_clip()
ls = model.logit_scale.exp().item()
cred = cp.class_embed(model, tok, cp.CREDIT_PROMPTS)
scene = cp.class_embed(model, tok, cp.SCENE_PROMPTS)

def grid(frames, idxs, scores, label, tw=160, th=90, cols=8):
    canvas = Image.new("RGB", (cols*tw, th+16), (22, 22, 22))
    d = ImageDraw.Draw(canvas); d.text((3, 2), label, fill=(255, 255, 0))
    for k, fi in enumerate(list(idxs)[:cols]):
        im = Image.open(frames[fi]).convert("RGB").resize((tw, th)); canvas.paste(im, (k*tw, 16))
        d.text((k*tw+2, 16), f"#{fi} {scores[fi]:.2f}", fill=(60, 255, 60) if scores[fi] >= THR else (255, 80, 80))
    return canvas

summary = []
for d in films:
    safe = "".join(c if c.isalnum() else "_" for c in d.name)[:40]
    blocks = []; row = {"film": d.name}
    for seg, sub in [("giris", "entry_frames"), ("cikis", "exit_frames")]:
        frames = sorted(glob.glob(str(d/sub/"*.png")))
        if not frames: continue
        p = cp.score_frames(model, preprocess, frames, cred, scene, ls); ps = cp.med_smooth(p, 5)
        mask = ps >= THR; runs = cp.runs_of(mask); order = list(np.argsort(-ps))
        np.save(REV/f"{safe}__{seg}.npy", ps)
        blocks.append(grid(frames, order[:8], ps, f"{seg.upper()}  KREDİ  (n={len(frames)}  kredi={int(mask.sum())} %{round(100*mask.mean())})"))
        blocks.append(grid(frames, order[-8:][::-1], ps, f"{seg.upper()}  FOOTAGE"))
        row[seg] = {"frames": len(frames), "credit": int(mask.sum()), "pct": round(100*float(mask.mean())),
                    "runs": [(int(a), int(b)) for a, b in runs]}
    if not blocks: continue
    W = max(b.width for b in blocks); H = sum(b.height for b in blocks)+6*len(blocks)
    canvas = Image.new("RGB", (W, H), (0, 0, 0)); y = 0
    for b in blocks: canvas.paste(b, (0, y)); y += b.height+6
    canvas.save(REV/f"{safe}.png")
    summary.append(row)
    g = row.get("giris", {}); c = row.get("cikis", {})
    print(f"  ✓ {d.name[:36]:38} giriş={g.get('credit')}/{g.get('frames')} (%{g.get('pct')}) | çıkış={c.get('credit')}/{c.get('frames')} (%{c.get('pct')})")

(REV/"_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
L = ["=== 15 FİLM CLIP KREDİ-TESPİT ÖZETİ ===", f"{'film':40} {'giriş kredi/n':>16} {'çıkış kredi/n':>16}"]
for r in summary:
    g = r.get("giris", {}); c = r.get("cikis", {})
    L.append(f"{r['film'][:38]:40} {str(g.get('credit'))+'/'+str(g.get('frames')):>16} {str(c.get('credit'))+'/'+str(c.get('frames')):>16}")
(REV/"_SUMMARY.txt").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
print(f"\n-> kanıt kartları: {REV}")
