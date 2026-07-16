# -*- coding: utf-8 -*-
"""repool_all_hybrid.py — 51 filmin cikis havuzunu HİBRİT ile yeniden kur (tek process, Paddle 1 kez).
Hibrit = CV detector + footage-trim + VLM-rescue (not_found/şüpheli). KKF Aşama-1 max.
"""
import sys, os, glob, json
sys.path.insert(0, "/opt/mitas"); sys.path.insert(0, "/opt/mitas/scripts")
from pathlib import Path
import _jenerik_pool as jp

RUN = os.environ["MITAS_RUN_ROOT"]
cfg = jp.DetectorConfig(ocr_mode="paddle", ocr_stride=8)
res = {}
clips = sorted(glob.glob(f"{RUN}/Database/*"))
for k, cd in enumerate(clips, 1):
    fid = os.path.basename(cd)
    frames = Path(cd) / "frames" / "cikis"
    if not frames.is_dir():
        continue
    try:
        m = jp.create_pool(frames_dir=frames, pool_dir=Path(cd) / "frames" / "cikis_jenerik",
                           debug_root=Path(cd) / "jenerik_debug", cfg=cfg, debug_sheet=False)
    except Exception as exc:
        print(f"[{k}/{len(clips)}] ERR {fid[-28:]}: {exc}", flush=True)
        res[fid] = {"error": str(exc)}
        continue
    res[fid] = {"engine": m.get("engine"), "start": m.get("start_pos"), "pool": m.get("pool_frames"),
                "trim": m.get("footage_head_trimmed"), "vlm": m.get("vlm_rescued"), "status": m.get("status")}
    tag = "VLM" if m.get("vlm_rescued") else ("nf " if not m.get("pool_frames") else "   ")
    print(f"[{k}/{len(clips)}] {tag} {str(m.get('engine')):11} pool={str(m.get('pool_frames')):4} {fid[-30:]}", flush=True)

json.dump(res, open(f"{RUN}/reports/stage1_hybrid.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
nv = sum(1 for v in res.values() if v.get("vlm"))
nf = sum(1 for v in res.values() if not v.get("pool"))
print(f"DONE — {len(res)} film | VLM-rescue: {nv} | boş(not_found): {nf}")
