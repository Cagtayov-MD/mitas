# -*- coding: utf-8 -*-
"""stage2_batch.py — Aşama-2: 51 filmin temiz havuzlarından master PNG üret (KKF sıra, Aşama-1 sonrası).
master_png_monitor --once <TAM YOL> ile (folder-adı production'da arıyor → tam yol şart).
Manifest'leri toplar, kalite bayraklarını çıkarır.
"""
import sys, os, glob, json, subprocess
from pathlib import Path

RUN = os.environ["MITAS_RUN_ROOT"]
MON = "/opt/mitas/OCR-worktree/master_png_monitor.py"
PY = "/opt/mitas/venvs/ocr/bin/python"
env = dict(os.environ, MITAS_PROJECT_ROOT="/opt/mitas", MITAS_RUN_ROOT=RUN)

clips = sorted(glob.glob(f"{RUN}/Database/*"))
res = {}
for k, cd in enumerate(clips, 1):
    fid = os.path.basename(cd)
    if not Path(cd, "frames", "cikis_jenerik").is_dir():
        continue
    try:
        p = subprocess.run([PY, MON, "--once", cd], env=env, cwd="/opt/mitas",
                           capture_output=True, text=True, timeout=360)
        out = p.stdout.strip()
        j = json.loads(out) if out.startswith("{") else {"err": "no_json", "stderr": p.stderr[-200:]}
    except subprocess.TimeoutExpired:
        j = {"err": "timeout"}
    except Exception as e:
        j = {"err": f"{type(e).__name__}: {e}"}
    # özet çıkar
    cikis = j.get("reading_master_runaware", {}) or {}
    giris = j.get("giris_reading_master_runaware", {}) or {}
    row = {"produced": j.get("produced"),
           "cikis_frames": cikis.get("frames"), "cikis_status": cikis.get("status"),
           "cikis_blocks": cikis.get("kept_blocks"),
           "giris_frames": giris.get("frames"), "giris_status": giris.get("status"),
           "err": j.get("err")}
    res[fid] = row
    short = fid.split("-1-0000")[0].split("_")[-1][:24]
    tag = "✓" if j.get("produced") else "✗"
    print(f"[{k}/{len(clips)}] {tag} {short:>24} çıkış={row['cikis_frames']}f/{row['cikis_blocks']}blk giriş={row['giris_frames']}f {row['err'] or ''}", flush=True)

json.dump(res, open(f"{RUN}/reports/stage2_masters.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
prod = sum(1 for v in res.values() if v.get("produced"))
noc = sum(1 for v in res.values() if not v.get("cikis_frames"))
print(f"DONE — {prod}/{len(res)} master üretti | çıkış-boş: {noc}")
