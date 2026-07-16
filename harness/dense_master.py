# -*- coding: utf-8 -*-
"""dense_master.py — KÖK-FİX: master kompozisyonu için kredi bölgesini YOĞUN (native fps) yeniden çıkar.
Sorun: 1.5fps seyrek kareler → scroll kare-arası 75px zıplıyor → compositor 'cut' sanıp statik'e düşüyor
       → kart-yığma → smear/collapse/kayıp.
Fix:   havuzdan kredi ZAMAN aralığını al → kaynak videodan native-fps ile yeniden çıkar → compositor'e ver.
       (1.5fps sadece TESPİT için kalır; master YOĞUN kare ister.)
Kullanım: python dense_master.py <film_parça> [seg=cikis|giris] [--fps N] [--keep]
"""
import sys, os, glob, json, shutil, subprocess
from pathlib import Path

RUN = os.environ["MITAS_RUN_ROOT"]
SRC = "/opt/mitas/filmtest/aaaa"
FPS_SPARSE = 1.5
CIKIS_TAIL_S = 600.0
GIRIS_HEAD_S = 240.0
SC = "/opt/mitas/harness/scratch"

def probe(v):
    r = subprocess.run(["/usr/bin/ffprobe","-v","error","-select_streams","v:0",
        "-show_entries","format=duration:stream=r_frame_rate","-of","json",v],
        capture_output=True,text=True)
    j = json.loads(r.stdout)
    dur = float(j["format"]["duration"])
    rf = j["streams"][0]["r_frame_rate"]; a,b = rf.split("/")
    fps = float(a)/float(b or 1)
    return dur, fps

def find_src(fid):
    for ext in (".mp4",".mxf",".MP4",".MXF"):
        p = Path(SRC, fid+ext)
        if p.exists(): return str(p)
    c = [f for f in glob.glob(f"{SRC}/*") if Path(f).stem == fid]
    return c[0] if c else None

def main():
    part = sys.argv[1]
    seg = sys.argv[2] if len(sys.argv)>2 and not sys.argv[2].startswith("-") else "cikis"
    dense_fps = None
    if "--fps" in sys.argv: dense_fps = float(sys.argv[sys.argv.index("--fps")+1])

    cd = [d for d in glob.glob(f"{RUN}/Database/*") if part in os.path.basename(d)][0]
    fid = os.path.basename(cd)
    src = find_src(fid)
    assert src, f"kaynak video yok: {fid}"
    dur, native = probe(src)
    if dense_fps is None: dense_fps = native
    pool = sorted(Path(cd,"frames",f"{seg}_jenerik").glob("*.png"))
    assert pool, f"{seg} havuzu boş"
    i0 = int(pool[0].stem.split("_")[1]) - 1        # 0-based kare index
    i1 = int(pool[-1].stem.split("_")[1]) - 1
    base = max(0.0, dur - CIKIS_TAIL_S) if seg=="cikis" else 0.0
    t0 = base + i0/FPS_SPARSE
    t1 = base + i1/FPS_SPARSE + (1.0/FPS_SPARSE)    # son kareyi kapsa
    print(f"{fid[-28:]} | video {dur:.0f}s @{native:.2f}fps")
    print(f"  havuz {pool[0].name}→{pool[-1].name} ({len(pool)} seyrek kare)")
    print(f"  kredi ZAMAN aralığı: {t0:.1f}s → {t1:.1f}s ({t1-t0:.1f}s)")
    print(f"  YOĞUN çıkarım: fps={dense_fps:.2f} → ~{int((t1-t0)*dense_fps)} kare")

    pdir = Path(cd,"frames",f"{seg}_jenerik")
    sparse_bak = Path(cd,"frames",f"{seg}_jenerik_sparse")
    # eski master'ı sakla (kıyas için)
    oldm = Path(cd, "reading_master_runaware.png" if seg=="cikis" else "giris_reading_master_runaware.png")
    if oldm.exists(): shutil.copy2(oldm, f"{SC}/OLD_{part[:12]}_{seg}.png")
    # sparse havuzu yedekle, yoğun kareleri yerine koy
    if not sparse_bak.exists(): shutil.copytree(pdir, sparse_bak)
    shutil.rmtree(pdir); pdir.mkdir(parents=True)
    pre = "c" if seg=="cikis" else "g"
    cmd = ["/usr/bin/ffmpeg","-y","-hide_banner","-loglevel","error","-ss",f"{t0:.3f}",
           "-i",src,"-t",f"{t1-t0:.3f}","-vf",f"fps={dense_fps}",
           "-start_number","1",str(pdir / f"{pre}_%05d.png")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    n = len(list(pdir.glob("*.png")))
    print(f"  → {n} YOĞUN kare çıkarıldı {'✓' if n>0 else '✗ '+r.stderr[:150]}")
    return cd, fid, seg, n

if __name__ == "__main__":
    main()
