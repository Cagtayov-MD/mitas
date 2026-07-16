# -*- coding: utf-8 -*-
"""apply_trim.py — footage-baş trim'ini MEVCUT havuzlara uygula (Paddle bir kez yüklenir).
KKF Aşama-1: cikis_jenerik havuzlarının baştaki footage karelerini OCR ile kırp (in-place).
Yeniden-tespit YOK (start_pos değişmiyor); sadece trim. Sonuç: reports/footage_trim.json.
"""
import sys, os, glob, json
sys.path.insert(0, "/opt/mitas")
from pathlib import Path
import core.pipelines.ocr.jenerik_frame_pool_detector as det
from paddleocr import PaddleOCR

RUN = os.environ["MITAS_RUN_ROOT"]
mr = os.environ["MITAS_JENERIK_PADDLE_MODEL_ROOT"]
ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
                text_detection_model_name="PP-OCRv5_server_det", text_detection_model_dir=mr + "/PP-OCRv5_server_det",
                text_recognition_model_name="en_PP-OCRv5_mobile_rec", text_recognition_model_dir=mr + "/en_PP-OCRv5_mobile_rec")
cfg = det.DetectorConfig(ocr_mode="paddle")


def is_credit(f):
    try:
        _, feat = det.paddle_frame_score(ocr, f, cfg)
    except Exception:
        return None
    if not feat:
        return False
    cr = (int(feat.get("name_like_count", 0) or 0) >= 2
          or int(feat.get("credit_keyword_count", 0) or 0) >= 1
          or bool(feat.get("two_column_layout")))
    ns = bool(feat.get("subtitle_like") or feat.get("scene_sign_like") or feat.get("prose_like"))
    return bool(cr and not ns)


def trim_amt(frames, max_scan=60):
    hits = 0
    for i, f in enumerate(frames[:max_scan]):
        c = is_credit(f)
        if c:
            hits += 1
            if hits >= 2:
                return max(0, i - 1)
        elif c is False:
            hits = 0
    return 0


res = {}
pools = sorted(glob.glob(f"{RUN}/Database/*/frames/cikis_jenerik"))
for k, pd in enumerate(pools, 1):
    frames = sorted(glob.glob(f"{pd}/*.png"))
    fid = Path(pd).parent.parent.name
    if not frames:
        res[fid] = {"trim": 0, "pool_before": 0}
        continue
    t = trim_amt([Path(x) for x in frames])
    if t > 0:
        for x in frames[:t]:
            try:
                os.remove(x)
            except OSError:
                pass
    res[fid] = {"trim": t, "pool_before": len(frames), "pool_after": len(frames) - t}
    print(f"[{k}/{len(pools)}] trim={t:3} {fid[-30:]}", flush=True)

json.dump(res, open(f"{RUN}/reports/footage_trim.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
tot = sum(1 for v in res.values() if v.get("trim", 0) > 0)
print(f"DONE — {tot}/{len(res)} filmde footage-baş kırpıldı")
