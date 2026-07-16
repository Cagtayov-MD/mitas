# -*- coding: utf-8 -*-
"""phase2_vlm_rescue.py — FAZ2: bayrak-lı (not_found / şüpheli-dev-havuz) filmlere SADECE VLM.
Paddle YOK (tam VRAM, çakışma yok). VLM detector gerçek kredi başlangıcını bulur → havuzu oradan
yeniden kurar. FAZ1 (stage1_hybrid.json) çıktısından bayrakları seçer.
"""
import sys, os, glob, json, shutil
sys.path.insert(0, "/opt/mitas"); sys.path.insert(0, "/opt/mitas/scripts")
from pathlib import Path
import credit_start_vlm as cvlm

RUN = os.environ["MITAS_RUN_ROOT"]
h = json.load(open(f"{RUN}/reports/stage1_hybrid.json", encoding="utf-8"))
N = 900  # pencere kare sayısı ~ (start eşiği için)

# BAYRAK: pool==0 (not_found) VEYA pool>400 & start çok erken (footage-bloat/diegetik-erken-anchor)
flagged = []
for fid, v in h.items():
    pool = v.get("pool") or 0
    start = v.get("start") or 0
    if pool == 0 or (pool > 400 and start < 0.15 * N):
        flagged.append(fid)
print(f"BAYRAK-LI film: {len(flagged)} → VLM-rescue", flush=True)

res = {}
for k, fid in enumerate(flagged, 1):
    cd = Path(RUN) / "Database" / fid
    frames_dir = cd / "frames" / "cikis"
    pool_dir = cd / "frames" / "cikis_jenerik"
    if not frames_dir.is_dir():
        continue
    vr = cvlm.detect(frames_dir)
    old = h[fid].get("pool")
    if vr.get("status") in ("found", "left_censored") and vr.get("start_frame") is not None:
        frames = sorted(frames_dir.glob("*.png"))
        st = int(vr["start_frame"])
        # havuzu VLM-start'tan yeniden kur
        if pool_dir.exists():
            shutil.rmtree(pool_dir)
        pool_dir.mkdir(parents=True, exist_ok=True)
        for f in frames[st:]:
            shutil.copy2(f, pool_dir / f.name)
        newpool = len(frames) - st
        res[fid] = {"old_pool": old, "vlm_start": st, "new_pool": newpool, "status": "found",
                    "sustained": vr.get("sustained"), "first": frames[st].name}
        print(f"[{k}/{len(flagged)}] ✅ {old}→{newpool} start={st} {fid[-30:]}", flush=True)
    else:
        # VLM de bulamadı → CV havuzuna DOKUNMA (belki gerçek uzun künye; KKF: çalışanı bozma).
        # Sadece kaydet; re-audit'te bu filmler ayrıca gözle bakılır.
        res[fid] = {"old_pool": old, "status": "not_found_kept", "reason": vr.get("reason")}
        print(f"[{k}/{len(flagged)}] ⚠ {old} KORUNDU (VLM not_found) {fid[-30:]}", flush=True)

json.dump(res, open(f"{RUN}/reports/stage1_phase2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"DONE — {sum(1 for v in res.values() if v.get('status')=='found')} kurtarıldı, "
      f"{sum(1 for v in res.values() if v.get('status')=='not_found')} not_found")
