# -*- coding: utf-8 -*-
"""phase3_verify_fix.py — KKF görsel-audit'te bulunan 5 şüpheliyi VLM ile KESİNLEŞTİR + gerekirse re-anchor.
VLM = kredi/footage hakemi. VLM start, mevcut havuz-başından ANLAMLI geç ise (>25 kare) → havuzda öndeki
footage'ı at, VLM start'tan yeniden kur. VLM aynı/erken derse → havuz gerçek (dokunma). VLM not_found derse
→ havuz muhtemelen tümü footage (açılış-kredili) → boşalt + işaretle (giriş havuzu okunacak).
"""
import sys, os, json, shutil
sys.path.insert(0, "/opt/mitas"); sys.path.insert(0, "/opt/mitas/scripts")
from pathlib import Path
import credit_start_vlm as cvlm

RUN = os.environ["MITAS_RUN_ROOT"]
DB = Path(RUN) / "Database"
GATE = 25  # VLM start mevcut baştan bu kadar geç ise re-anchor

SUSPECTS = [
    "evoArcadmin_SİNEMA FİLM4_2013-1015-1-0000-70-1-ATTİLA_MARCEL_",
    "evoArcadmin_COZUMLEMEV2S27_1980-0218-1-0000-00-1-DÜNYANIN_EN_MÜTHİŞ_ADAMI",
    "evoArcadmin_SİNEMA FİLM4_2025-1011-1-0000-50-1-ROBINSON_CRUSOE",
    "evoArcadmin_COZUMLEMEV2S25_1980-0190-1-0000-90-1-DAĞ_ADAMLARI",
    "evoArcadmin_SİNEMA FİLM4_2024-0017-1-0000-91-1-BEN_VE_BABAM_VATAN_(O_GECE_BERABER_BÜYÜDÜK)",
]

res = {}
for k, fid in enumerate(SUSPECTS, 1):
    cd = DB / fid
    fdir = cd / "frames" / "cikis"
    pdir = cd / "frames" / "cikis_jenerik"
    if not fdir.is_dir():
        print(f"[{k}/5] YOK {fid[-30:]}", flush=True); continue
    full = sorted(fdir.glob("*.png"))
    pool = sorted(pdir.glob("*.png"))
    names = [p.name for p in full]
    cur_start = names.index(pool[0].name) if pool and pool[0].name in names else None
    vr = cvlm.detect(fdir)
    st = vr.get("start_frame")
    status = vr.get("status")
    entry = {"cur_start": cur_start, "cur_pool": len(pool), "vlm_status": status,
             "vlm_start": st, "sustained": vr.get("sustained"), "reason": vr.get("reason")}
    if status in ("found", "left_censored") and st is not None and cur_start is not None and st > cur_start + GATE:
        # öndeki footage'ı at
        shutil.rmtree(pdir); pdir.mkdir(parents=True, exist_ok=True)
        for f in full[st:]:
            shutil.copy2(f, pdir / f.name)
        entry["action"] = "reanchor"
        entry["new_pool"] = len(full) - st
        print(f"[{k}/5] ✂ REANCHOR {cur_start}→{st} pool {len(pool)}→{len(full)-st} sust={vr.get('sustained')} {fid[-28:]}", flush=True)
    elif status not in ("found", "left_censored"):
        entry["action"] = "vlm_notfound_keep"  # KKF: emin değilsek çalışanı bozma; boşaltmıyoruz
        print(f"[{k}/5] ⚫ VLM-notfound (havuz KORUNDU) cur_start={cur_start} {fid[-28:]}", flush=True)
    else:
        entry["action"] = "keep_genuine"
        print(f"[{k}/5] ✓ GERÇEK (VLM start={st} ≈ cur={cur_start}) {fid[-28:]}", flush=True)
    res[fid] = entry

json.dump(res, open(f"{RUN}/reports/stage1_phase3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
na = sum(1 for v in res.values() if v.get("action") == "reanchor")
print(f"DONE — {na} re-anchor, {len(res)-na} korundu/gerçek")
