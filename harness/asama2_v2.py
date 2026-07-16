# -*- coding: utf-8 -*-
"""asama2_v2.py — AŞAMA-2 SIFIRDAN: ADAPTİF YOĞUN-KARE + master PNG.

KÖK-FİX: compositor'ün scroll-tespiti kare-arası dikey kaymayla (dy) çalışır:
   dy < ~1.9px → STATİK ; dy > ~50px → SAHNE-KESİĞİ (→ statiğe düşer, kart-yığma → SMEAR)
1.5fps'te kayan kredi dy≈75px → 'cut' sanılır → HALLERİ smear, MAVZER collapse, ZENGİN tekrar.
Sabit 25fps de yanlış (yavaş scroll'da dy<1.9 → yine statik).
ÇÖZÜM: her filmde gerçek dy'yi ÖLÇ → hedef banda (≈8px) oturtacak fps'i HESAPLA → o aralığı
        yeniden çıkar. Statik-kartlı filmde (dy<4px) seyrek bırak (kart-modu zaten doğru).
"""
import sys, os, glob, json, shutil, subprocess, time
sys.path.insert(0, "/opt/mitas")
from pathlib import Path
import numpy as np, cv2

RUN = os.environ["MITAS_RUN_ROOT"]
SRC = "/opt/mitas/filmtest/aaaa"
MON = "/opt/mitas/OCR-worktree/master_png_monitor.py"
PY = "/opt/mitas/venvs/ocr/bin/python"
FPS_SPARSE = 1.5
CIKIS_TAIL_S = 600.0
TARGET_DY = 8.0
STATIC_DY_MAX = 4.0
MAX_DENSE_FPS = 25.0
env = dict(os.environ, MITAS_PROJECT_ROOT="/opt/mitas", MITAS_RUN_ROOT=RUN)

def probe(v):
    r = subprocess.run(["/usr/bin/ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",v],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except Exception: return 0.0

def find_src(fid):
    for ext in (".mp4",".mxf"):
        p = Path(SRC, fid+ext)
        if p.exists(): return str(p)
    c=[f for f in glob.glob(f"{SRC}/*") if Path(f).stem==fid]
    return c[0] if c else None

def measure_dy(frames):
    if len(frames) < 3: return 0.0
    im0 = cv2.imread(str(frames[0]))
    if im0 is None: return 0.0
    H,W = im0.shape[:2]
    hann = cv2.createHanningWindow((W,H), cv2.CV_32F)
    prev=None; dys=[]
    for f in frames[:50]:
        im = cv2.imread(str(f))
        if im is None: continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None:
            (_,dy),_ = cv2.phaseCorrelate(prev*hann, g*hann); dys.append(abs(dy))
        prev = g
    return float(np.median(dys)) if dys else 0.0

def densify(cd: Path, seg):
    fid = cd.name; src = find_src(fid)
    pdir = cd/"frames"/f"{seg}_jenerik"
    pool = sorted(pdir.glob("*.png"))
    if not src or len(pool) < 5: return {"mode":"skip","frames":len(pool)}
    dy = measure_dy(pool)
    if dy < STATIC_DY_MAX:
        return {"mode":"STATIK","dy":round(dy,1),"frames":len(pool)}
    dur = probe(src)
    dense_fps = min(MAX_DENSE_FPS, max(FPS_SPARSE, FPS_SPARSE*dy/TARGET_DY))
    i0 = int(pool[0].stem.split("_")[1])-1
    i1 = int(pool[-1].stem.split("_")[1])-1
    base = max(0.0, dur-CIKIS_TAIL_S) if seg=="cikis" else 0.0
    t0 = base + i0/FPS_SPARSE; t1 = base + i1/FPS_SPARSE + 1.0/FPS_SPARSE
    bak = cd/"frames"/f"{seg}_jenerik_sparse"
    if not bak.exists(): shutil.copytree(pdir, bak)
    shutil.rmtree(pdir); pdir.mkdir(parents=True)
    pre = "c" if seg=="cikis" else "g"
    subprocess.run(["/usr/bin/ffmpeg","-y","-hide_banner","-loglevel","error","-ss",f"{t0:.3f}",
        "-i",src,"-t",f"{t1-t0:.3f}","-vf",f"fps={dense_fps:.3f}","-start_number","1",
        str(pdir/f"{pre}_%05d.png")], capture_output=True)
    n = len(list(pdir.glob("*.png")))
    return {"mode":"SCROLL","dy":round(dy,1),"fps":round(dense_fps,2),
            "sparse":len(pool),"dense":n,"beklenen_dy":round(dy/(dense_fps/FPS_SPARSE),1)}

def master(cd: Path):
    p = subprocess.run([PY, MON, "--once", str(cd)], env=env, cwd="/opt/mitas",
                       capture_output=True, text=True, timeout=1800)
    try:
        j = json.loads(p.stdout.strip())
    except Exception:
        return {"err": p.stderr[-120:] if p.stderr else "no_json"}
    c = j.get("reading_master_runaware",{}) or {}
    g = j.get("giris_reading_master_runaware",{}) or {}
    return {"c_size": c.get("size"), "c_scroll": c.get("strict_scroll_frac"), "c_blocks": c.get("kept_blocks"),
            "g_size": g.get("size"), "g_scroll": g.get("strict_scroll_frac")}

clips = sorted(glob.glob(f"{RUN}/Database/*"))
print(f"AŞAMA-2 v2 — {len(clips)} film (adaptif yoğun-kare + master)\n", flush=True)
out={}; t0=time.time()
for k, cdp in enumerate(clips, 1):
    cd = Path(cdp); st=time.time()
    dc = densify(cd, "cikis")
    dg = densify(cd, "giris")
    m = master(cd)
    out[cd.name] = {"cikis_dense": dc, "giris_dense": dg, "master": m}
    short = cd.name.split("-")[-1][:20]
    cs = m.get("c_scroll"); sz = m.get("c_size")
    tag = f"dy={dc.get('dy')}→fps={dc.get('fps')}" if dc.get("mode")=="SCROLL" else dc.get("mode")
    print(f"[{k}/{len(clips)}] {short:22} {str(tag):22} → master {sz} scroll={cs}  {time.time()-st:.0f}s", flush=True)
json.dump(out, open(f"{RUN}/reports/asama2_v2.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
sc=sum(1 for v in out.values() if v["cikis_dense"].get("mode")=="SCROLL")
print(f"\nDONE — {sc} film SCROLL (yoğunlaştırıldı), {len(out)-sc} statik. {(time.time()-t0)/60:.0f} dk")
