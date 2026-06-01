"""20260530_1703 — ROBINSON çıkış: NORMAL vs LUMAKEY (qwen+lumakey fikrinin demosu).

normal  = ham karelerde maskeli-hız slit-scan (YOL 2)
lumakey = önce zemini siyaha al (luma-key), sonra AYNI slit-scan
+ ffmpeg lumakey ile gerçek 'temiz-zemin video' + 2 örnek kare (göstermek için).
"""
import sys, glob, subprocess
from pathlib import Path
import cv2, numpy as np

FRAMES = r"E:\MITAS\OCR-worktree\out\yol_test_20260530_1645\39_robinson_crusoe_cikis\frames"
VIDEO  = r"E:\filmtest\aaaa\evoArcadmin_SİNEMA FİLM4_2025-1011-1-0000-50-1-ROBINSON_CRUSOE.mp4"
FFMPEG = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
TC0, DUR = 4995, 210
OUT = Path(r"E:\MITAS\OCR-worktree\out\robinson_lumakey_20260530_1703"); OUT.mkdir(parents=True, exist_ok=True)
SLIT_FRAC, VMIN, VMAX, THK, THT, LUMA_THR = 0.55, 1, 40, 15, 22, 150

def rd(p): return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
def wr(p, i):
    ok, b = cv2.imencode(".png", i)
    if ok: b.tofile(str(p))

def tophat(g):
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (THK, 5))
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k)
    _, m = cv2.threshold(th, THT, 255, cv2.THRESH_BINARY); return m

def luma_key(img):
    """ffmpeg lumakey'in cv2 karşılığı: parlak pikselleri tut, koyuyu siyaha al."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    out = np.zeros_like(img); out[g > LUMA_THR] = img[g > LUMA_THR]
    return out

def slitscan(frames, keyed):
    H=W=hann=prev=None; prev_any=False; strips=[]; vs=[]
    for f in frames:
        img = rd(f)
        if img is None: continue
        if keyed: img = luma_key(img)
        if H is None:
            H, W = img.shape[:2]; hann = cv2.createHanningWindow((W, H), cv2.CV_32F); ref = round(SLIT_FRAC*H)
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); gf = g.astype(np.float32)
        m = tophat(g); md = cv2.dilate(m, np.ones((11,11), np.uint8))
        mg = gf.copy(); mg[md == 0] = 0.0
        dy = 0.0
        if prev is not None and bool(md.any()) and prev_any:
            (_, dy), _ = cv2.phaseCorrelate(prev*hann, mg*hann)
        prev = mg; prev_any = bool(md.any())
        v = int(round(abs(dy)))
        if v < VMIN or v > VMAX: continue
        s = img[ref:ref+v, :].copy()
        if s.shape[0] > 0: strips.append(s); vs.append(v)
    if not strips: return None, 0, 0
    return np.vstack(strips), len(strips), int(np.median(vs))

def main():
    frames = sorted(glob.glob(FRAMES + r"\f_*.png"))
    print(f"frames={len(frames)}")
    for keyed, name in [(False, "normal"), (True, "lumakey")]:
        m, n, v = slitscan(frames, keyed)
        if m is not None:
            wr(OUT/f"master_{name}.png", m)
            print(f"{name}: {m.shape[1]}x{m.shape[0]}  strips={n} medv={v}")
        else:
            print(f"{name}: EMPTY")
    # gerçek ffmpeg lumakey -> temiz-zemin video
    vid = str(OUT/"robinson_cikis_lumakey.mp4")
    fc = ("color=c=black:s=854x480:r=25[bg];"
          "[0:v]scale=854:480,lumakey=threshold=0.0:tolerance=0.45:softness=0.05[fg];"
          "[bg][fg]overlay=shortest=1,format=yuv420p[v]")
    r = subprocess.run([FFMPEG,"-y","-ss",str(TC0),"-t",str(DUR),"-i",VIDEO,
                        "-filter_complex",fc,"-map","[v]","-an",vid],
                       capture_output=True, text=True)
    print("ffmpeg lumakey video:", "OK" if r.returncode==0 else f"ERR {r.stderr[-300:]}")
    if r.returncode == 0:
        for t, tag in [(30,"intro_30s"),(150,"scroll_150s")]:
            subprocess.run([FFMPEG,"-y","-ss",str(t),"-i",vid,"-frames:v","1",
                            str(OUT/f"vidsample_{tag}.png")], capture_output=True)
    print("OUT ->", OUT)

if __name__ == "__main__":
    main()
