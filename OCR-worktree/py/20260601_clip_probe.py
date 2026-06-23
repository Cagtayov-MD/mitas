"""ZERO-SHOT CLIP kare-yargıcı PROTOTİP — jenerik mi footage mi?
Her kareyi CLIP ile göm -> 'jenerik' vs 'sahne/altyazı/footage' prompt-kümelerine kosinüs benzerliği -> softmax -> credit_prob.
Zaman-yumuşatma (medyan) + bitişik kredi-koşuları (runs) bul. EĞİTİM YOK, ETİKET YOK.
Teşhis görselleri: (1) zaman-şeridi (yeşil=kredi/kırmızı=footage), (2) CLIP-kredi dediği 16 kare, (3) CLIP-footage dediği 16 kare.
PIL kullanır (cv2 Türkçe-İ path tuzağı YOK). Çıktı ASCII-güvenli klasöre.
"""
import sys, glob, argparse
from pathlib import Path
import numpy as np, torch, open_clip
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding="utf-8")

DEV = "cuda" if torch.cuda.is_available() else "cpu"
DB = Path(r"F:\REPO_GitHub\DATABASE")
OUT = Path(r"E:\MITAS\OCR-worktree\clip_probe")

# --- prompt kümeleri (İngilizce; görsel kavram dile bağlı değil) ---
CREDIT_PROMPTS = [
    "scrolling end credits of a film",
    "the closing credits of a movie listing cast and crew",
    "opening title credits with actor names",
    "a plain title card with names and text",
    "white text on a dark background, movie credits",
    "a list of names, film credits rolling on screen",
]
SCENE_PROMPTS = [
    "a scene from a film",
    "a movie still showing people",
    "an outdoor landscape in a movie",
    "actors performing in a film scene",
    "a film frame with a subtitle dialogue line at the bottom",
    "a movie scene with no credits",
]

def load_clip():
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-16-SigLIP", pretrained="webli")
    tok = open_clip.get_tokenizer("ViT-B-16-SigLIP")
    model = model.to(DEV).eval()
    return model, preprocess, tok

@torch.no_grad()
def class_embed(model, tok, prompts):
    t = tok(prompts).to(DEV)
    e = model.encode_text(t).float()
    e = e / e.norm(dim=-1, keepdim=True)
    m = e.mean(0); m = m / m.norm()
    return m

@torch.no_grad()
def score_frames(model, preprocess, frames, cred_e, scene_e, logit_scale):
    probs = []
    B = 64
    for i in range(0, len(frames), B):
        batch = frames[i:i+B]
        imgs = torch.stack([preprocess(Image.open(f).convert("RGB")) for f in batch]).to(DEV)
        ie = model.encode_image(imgs).float()
        ie = ie / ie.norm(dim=-1, keepdim=True)
        sc = torch.stack([ie @ cred_e, ie @ scene_e], dim=1) * logit_scale  # [B,2]
        p = sc.softmax(dim=1)[:, 0].cpu().numpy()                            # kredi olasılığı
        probs.extend(p.tolist())
    return np.array(probs)

def med_smooth(p, k=5):
    h = k // 2; out = p.copy()
    for i in range(len(p)):
        out[i] = np.median(p[max(0, i-h):i+h+1])
    return out

def runs_of(mask, gap=3, minlen=3):
    idx = np.where(mask)[0]
    if len(idx) == 0: return []
    runs = []; cur = [idx[0]]
    for j in idx[1:]:
        if j - cur[-1] <= gap: cur.append(j)
        else: runs.append((cur[0], cur[-1])); cur = [j]
    runs.append((cur[0], cur[-1]))
    return [(a, b) for a, b in runs if b - a + 1 >= minlen]

def timeline_strip(probs, path, h=60):
    n = len(probs); strip = np.zeros((h, n, 3), np.uint8)
    for x, p in enumerate(probs):
        # yeşil=kredi, kırmızı=footage; parlaklık güvene göre
        strip[:, x] = (int(255*(1-p)), int(200*p), 0)
    Image.fromarray(strip).resize((max(n, 400), h), Image.NEAREST).save(path)

def montage(frames, scores, idxs, path, cols=4, tw=192, th=108):
    rows = (len(idxs)+cols-1)//cols
    canvas = Image.new("RGB", (cols*tw, rows*th), (20, 20, 20))
    d = ImageDraw.Draw(canvas)
    for k, fi in enumerate(idxs):
        im = Image.open(frames[fi]).convert("RGB").resize((tw, th))
        r, c = divmod(k, cols); canvas.paste(im, (c*tw, r*th))
        d.text((c*tw+3, r*th+2), f"#{fi} {scores[fi]:.2f}", fill=(255, 255, 0))
    canvas.save(path)

def probe_seg(model, preprocess, cred_e, scene_e, ls, film_dir, sub, seg, outdir, thr):
    frames = sorted(glob.glob(str(film_dir/sub/"*.png")))
    if not frames:
        print(f"  {seg}: kare yok"); return
    p = score_frames(model, preprocess, frames, cred_e, scene_e, ls)
    ps = med_smooth(p, 5)
    mask = ps >= thr
    runs = runs_of(mask)
    od = outdir/seg; od.mkdir(parents=True, exist_ok=True)
    timeline_strip(ps, od/"timeline.png")
    order = np.argsort(-ps)
    montage(frames, ps, list(order[:16]), od/"CLIP_KREDI_dedigi.png")
    montage(frames, ps, list(order[-16:]), od/"CLIP_FOOTAGE_dedigi.png")
    print(f"  {seg}: {len(frames)} kare | kredi-skoru>= {thr}: {int(mask.sum())} kare ({100*mask.mean():.0f}%)")
    print(f"     skor dağ.: min={ps.min():.2f} medyan={np.median(ps):.2f} max={ps.max():.2f}")
    print(f"     KREDİ KOŞULARI (frame aralıkları): {[(int(a),int(b)) for a,b in runs] or 'yok'}")
    np.save(od/"credit_prob.npy", ps)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--film", default="ACEMİLER")
    ap.add_argument("--thr", type=float, default=0.5)
    a = ap.parse_args()
    fd = [d for d in DB.iterdir() if a.film.lower() in d.name.lower()]
    if not fd: print("film yok:", a.film); return
    fd = fd[0]
    safe = "".join(c if c.isalnum() else "_" for c in fd.name)[:40]
    outdir = OUT/safe; outdir.mkdir(parents=True, exist_ok=True)
    print(f"### {fd.name}  (dev={DEV}, thr={a.thr})")
    print("CLIP yükleniyor (ilk sefer model indirir)...")
    model, preprocess, tok = load_clip()
    ls = model.logit_scale.exp().item()
    cred_e = class_embed(model, tok, CREDIT_PROMPTS)
    scene_e = class_embed(model, tok, SCENE_PROMPTS)
    for seg, sub in [("giris", "entry_frames"), ("cikis", "exit_frames")]:
        probe_seg(model, preprocess, cred_e, scene_e, ls, fd, sub, seg, outdir, a.thr)
    print(f"\n-> görseller: {outdir}")

if __name__ == "__main__":
    main()
