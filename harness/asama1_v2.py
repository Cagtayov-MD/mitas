# -*- coding: utf-8 -*-
"""asama1_v2.py — AŞAMA-1 SIFIRDAN (fixli detektör).

Fixler (GT-kalibre, GPT prensipleriyle):
  · ileri footage-trim v2   (stride'lı tam-menzil → ATTİLA/MARIE gibi erken-anchor footage'ını atlar)
  · geriye-genişletme       (siyah kart-boşluklarını köprüleyip en-erken krediye iner → BABAM)
  · blank-veto              (mean+MAX piksel → soluk-yazı ≠ boş-siyah)
  · VLM-rescue v2           (dev havuz + başı PARLAK-SAHNE → semantik hakem)
  · çıkış TAIL-trim         (post-credit footage: ATTİLA plaj / MAKSİM oda / PİNOKYO heykel)
  · giriş TRAILING-trim     (açılış kredisi bitince footage'ı kes)
Tek process → paddle 1 kez yüklenir.
"""
import sys, os, glob, json, shutil, subprocess, time
sys.path.insert(0, "/opt/mitas"); sys.path.insert(0, "/opt/mitas/scripts")
from pathlib import Path
import numpy as np
from PIL import Image
import _jenerik_pool as jp
import core.pipelines.ocr.jenerik_frame_pool_detector as _det

RUN = os.environ["MITAS_RUN_ROOT"]
SRC = "/opt/mitas/filmtest/aaaa"
FPS = 1.5
CIKIS_TAIL_S = 600.0
GIRIS_HEAD_S = 240.0
cfg = jp.DetectorConfig(ocr_mode="paddle", ocr_stride=8)

def probe(v):
    r = subprocess.run(["/usr/bin/ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",v],
                       capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except Exception: return 0.0

def extract(film, out_dir, start, length, prefix):
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["/usr/bin/ffmpeg","-y","-hide_banner","-loglevel","error"]
    if start > 0: cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(film), "-t", f"{length:.3f}", "-vf", f"fps={FPS}",
            "-start_number","1", str(out_dir / f"{prefix}_%04d.png")]
    subprocess.run(cmd, capture_output=True)
    return len(list(out_dir.glob("*.png")))

def tail_trim_cikis(pool_dir: Path, ocr):
    """post-credit FOOTAGE kuyruğunu kes (sondan geriye: son kredi karesinden sonrasını at)."""
    pool = sorted(pool_dir.glob("*.png"))
    if len(pool) < 10: return 0
    last_credit = None
    for i in range(len(pool)-1, max(-1, len(pool)-60), -1):   # son 60 kareye bak
        f = pool[i]
        if jp._blackish(f): continue
        if jp._is_credit_frame(ocr, f, cfg):
            last_credit = i; break
    if last_credit is None or last_credit >= len(pool)-3: return 0
    rem = pool[last_credit+3:]
    for p in rem: p.unlink()
    return len(rem)

def trailing_trim_giris(pool_dir: Path, ocr, gap=7, buf=2, min_keep=10):
    """açılış kredisi bitince footage'ı kes (baştan ileri: son kredi karesinde dur)."""
    pool = sorted(pool_dir.glob("*.png"))
    if len(pool) <= min_keep: return 0
    last_credit=None; nc=0; seen=False
    for i in range(0, len(pool), 2):
        f = pool[i]
        if jp._blackish(f): continue
        c = jp._is_credit_frame(ocr, f, cfg)
        if c: last_credit=i; nc=0; seen=True
        elif seen:
            nc += 1
            if nc >= gap: break
    if last_credit is None: return 0
    cut = max(min_keep, min(len(pool), last_credit+1+buf))
    if cut >= len(pool)-1: return 0
    rem = pool[cut:]
    for p in rem: p.unlink()
    return len(rem)

films = sorted(glob.glob(f"{SRC}/*.mp4") + glob.glob(f"{SRC}/*.mxf"))
print(f"AŞAMA-1 v2 — {len(films)} film, sıfırdan\n", flush=True)
res = {}
t0 = time.time()
for k, fv in enumerate(films, 1):
    fid = Path(fv).stem
    cd = Path(RUN, "Database", fid)
    st = time.time()
    dur = probe(fv)
    if dur < 300:
        res[fid] = {"err": "kısa/bozuk video"}; print(f"[{k}/51] ✗ {fid[-24:]} kısa"); continue
    # 1) ekstraksiyon
    cs = max(0.0, dur - CIKIS_TAIL_S)
    nc = extract(fv, cd/"frames"/"cikis", cs, min(CIKIS_TAIL_S, dur), "c")
    ng = extract(fv, cd/"frames"/"giris", 0.0, min(GIRIS_HEAD_S, dur), "g")
    # 2) havuzlar (fixli create_pool)
    mc = jp.create_pool(frames_dir=cd/"frames"/"cikis", pool_dir=cd/"frames"/"cikis_jenerik",
                        debug_root=cd/"jenerik_debug", cfg=cfg, debug_sheet=False)
    mg = jp.create_pool(frames_dir=cd/"frames"/"giris", pool_dir=cd/"frames"/"giris_jenerik",
                        debug_root=cd/"jenerik_debug_giris", cfg=cfg, debug_sheet=False)
    # 3) trim'ler
    ocr = _det._PADDLE_CACHE.get(cfg.ocr_lang)
    tt = tail_trim_cikis(cd/"frames"/"cikis_jenerik", ocr) if ocr else 0
    gt_ = trailing_trim_giris(cd/"frames"/"giris_jenerik", ocr) if ocr else 0
    cp = len(list((cd/"frames"/"cikis_jenerik").glob("*.png")))
    gp = len(list((cd/"frames"/"giris_jenerik").glob("*.png")))
    res[fid] = {"dur": round(dur), "cikis_frames": nc, "giris_frames": ng,
                "cikis_start": mc.get("start_pos"), "cv_start": mc.get("cv_start_pos"),
                "fwd_trim": mc.get("footage_head_trimmed"), "back_ext": mc.get("back_extended"),
                "vlm": mc.get("vlm_rescued"), "cikis_pool": cp, "tail_trim": tt,
                "giris_start": mg.get("start_pos"), "giris_pool": gp, "giris_trail_trim": gt_,
                "engine": mc.get("engine"), "status": mc.get("status")}
    short = fid.split("-")[-1][:20]
    print(f"[{k}/51] {short:22} çık:{cp:4} (cv={mc.get('cv_start_pos')}→{mc.get('start_pos')}"
          f" f+{mc.get('footage_head_trimmed')} b-{mc.get('back_extended')}"
          f"{' VLM' if mc.get('vlm_rescued') else ''} kuyruk-{tt}) | giriş:{gp:4} (-{gt_})"
          f"  {time.time()-st:.0f}s", flush=True)
json.dump(res, open(f"{RUN}/reports/asama1_v2.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nDONE — {len(res)} film, {(time.time()-t0)/60:.0f} dk")
