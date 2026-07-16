# -*- coding: utf-8 -*-
"""adaptive_dense.py — AŞAMA-2 KÖK-FİX: master için ADAPTİF yoğun-kare.

Sorun: compositor'ün scroll-tespiti kare-arası dikey kayma (dy) ile çalışır:
   dy < static_dy(~1.9px) → STATİK ;  dy > cut(~50px) → SAHNE-KESİĞİ (→ statiğe düşer)
1.5 fps'te kayan kredi dy≈75px → 'cut' sanılıp statik → kart-yığma → smear/collapse/kayıp.

Sabit 25fps de YANLIŞ: yavaş scroll'lu filmde dy 25fps'te <1.9px'e düşer → yine statik sanılır.
ÇÖZÜM: seyrek havuzdan gerçek dy'yi ÖLÇ → dy'yi hedef banda (≈8px) oturtacak fps'i HESAPLA
        → kredi zaman-aralığını o fps ile yeniden çıkar. Statik-kartlı filmde (dy≈0) seyrek kalır.
"""
import sys, os, glob, json, shutil, subprocess
from pathlib import Path
import numpy as np, cv2

RUN = os.environ["MITAS_RUN_ROOT"]
SRC = "/opt/mitas/filmtest/aaaa"
FPS_SPARSE = 1.5
CIKIS_TAIL_S = 600.0
TARGET_DY = 8.0        # hedef kare-arası kayma (static_dy~1.9 ile cut~50 arası güvenli bant)
STATIC_DY_MAX = 4.0    # seyrek dy bunun altındaysa → gerçekten STATİK kart → yoğunlaştırma
MAX_DENSE_FPS = 25.0

def probe(v):
    r = subprocess.run(["/usr/bin/ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","format=duration:stream=r_frame_rate","-of","json",v],
        capture_output=True, text=True)
    j = json.loads(r.stdout); dur = float(j["format"]["duration"])
    a,b = j["streams"][0]["r_frame_rate"].split("/"); return dur, float(a)/float(b or 1)

def find_src(fid):
    for ext in (".mp4",".mxf",".MP4",".MXF"):
        p = Path(SRC, fid+ext)
        if p.exists(): return str(p)
    c=[f for f in glob.glob(f"{SRC}/*") if Path(f).stem==fid]
    return c[0] if c else None

def measure_dy(frames):
    """seyrek havuzda medyan |dy| (phaseCorrelate) — compositor'ün gördüğü sinyalin aynısı."""
    if len(frames) < 3: return 0.0
    im0 = cv2.imread(str(frames[0]))
    if im0 is None: return 0.0
    H,W = im0.shape[:2]
    hann = cv2.createHanningWindow((W,H), cv2.CV_32F)
    prev=None; dys=[]
    for f in frames[:60]:
        im = cv2.imread(str(f))
        if im is None: continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None:
            (_,dy),_ = cv2.phaseCorrelate(prev*hann, g*hann); dys.append(abs(dy))
        prev = g
    return float(np.median(dys)) if dys else 0.0

def densify(cd: Path, seg="cikis", verbose=True):
    """havuzu ADAPTİF yoğun kare ile değiştir. döner: dict(rapor)"""
    fid = cd.name
    src = find_src(fid)
    pdir = cd/"frames"/f"{seg}_jenerik"
    pool = sorted(pdir.glob("*.png"))
    if not src or not pool:
        return {"film": fid, "seg": seg, "skip": "kaynak/havuz yok"}
    dur, native = probe(src)
    dy = measure_dy(pool)
    if dy < STATIC_DY_MAX:
        return {"film": fid, "seg": seg, "dy_sparse": round(dy,1), "mode": "STATIK-kart",
                "dense_fps": None, "frames": len(pool), "note": "yoğunlaştırma gereksiz"}
    dense_fps = min(MAX_DENSE_FPS, max(FPS_SPARSE, FPS_SPARSE * dy / TARGET_DY))
    i0 = int(pool[0].stem.split("_")[1]) - 1
    i1 = int(pool[-1].stem.split("_")[1]) - 1
    base = max(0.0, dur - CIKIS_TAIL_S) if seg=="cikis" else 0.0
    t0 = base + i0/FPS_SPARSE
    t1 = base + i1/FPS_SPARSE + 1.0/FPS_SPARSE
    bak = cd/"frames"/f"{seg}_jenerik_sparse"
    if not bak.exists(): shutil.copytree(pdir, bak)
    shutil.rmtree(pdir); pdir.mkdir(parents=True)
    pre = "c" if seg=="cikis" else "g"
    subprocess.run(["/usr/bin/ffmpeg","-y","-hide_banner","-loglevel","error","-ss",f"{t0:.3f}",
        "-i",src,"-t",f"{t1-t0:.3f}","-vf",f"fps={dense_fps:.3f}","-start_number","1",
        str(pdir/f"{pre}_%05d.png")], capture_output=True)
    n = len(list(pdir.glob("*.png")))
    exp_dy = dy / (dense_fps/FPS_SPARSE)
    r = {"film": fid, "seg": seg, "dy_sparse": round(dy,1), "mode": "SCROLL",
         "dense_fps": round(dense_fps,2), "beklenen_dy": round(exp_dy,1),
         "sparse_frames": len(pool), "dense_frames": n,
         "aralik": [round(t0,1), round(t1,1)]}
    if verbose: print(f"  {fid[-24:]:26} {seg} dy={dy:5.1f}px → fps={dense_fps:5.2f} "
                      f"({len(pool)}→{n} kare, beklenen dy={exp_dy:.1f}px)", flush=True)
    return r

if __name__ == "__main__":
    only = sys.argv[1:] or None
    out=[]
    for cdp in sorted(glob.glob(f"{RUN}/Database/*")):
        cd = Path(cdp)
        if only and not any(o in cd.name for o in only): continue
        for seg in ("cikis","giris"):
            if (cd/"frames"/f"{seg}_jenerik").is_dir():
                out.append(densify(cd, seg))
    json.dump(out, open(f"{RUN}/reports/adaptive_dense.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    sc = sum(1 for r in out if r.get("mode")=="SCROLL"); st = sum(1 for r in out if r.get("mode")=="STATIK-kart")
    print(f"\nDONE — {sc} SCROLL (yoğunlaştırıldı), {st} STATİK-kart (seyrek kaldı)")
