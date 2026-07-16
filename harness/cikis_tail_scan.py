# -*- coding: utf-8 -*-
"""cikis_tail_scan.py — ÇIKIŞ havuzlarında post-credit FOOTAGE kuyruğu tespit et (ATTİLA sınıfı).
Havuz sonundan geriye bak: son kredi karesinden SONRA footage (siyah DEĞİL, içerikli) var mı?
Sadece TESPİT — gözle doğrulama sonrası trim. Siyah-kuyruk (mean düşük) zararsız, footage (içerikli) sorun.
"""
import sys, os, glob, json
sys.path.insert(0, "/opt/mitas"); sys.path.insert(0, "/opt/mitas/scripts")
from pathlib import Path
import numpy as np
from PIL import Image
import _jenerik_pool as jp
import core.pipelines.ocr.jenerik_frame_pool_detector as det
from paddleocr import PaddleOCR

RUN = os.environ["MITAS_RUN_ROOT"]; DB = Path(RUN) / "Database"
cfg = jp.DetectorConfig(ocr_mode="paddle", ocr_stride=8)
TAIL = 22   # sondan bu kadar kareye bak

def ensure_paddle():
    lang = cfg.ocr_lang
    if lang in det._PADDLE_CACHE: return
    mr = Path(os.environ.get("MITAS_JENERIK_PADDLE_MODEL_ROOT") or os.environ.get(
        "JENERIK_PADDLE_MODEL_ROOT", "/opt/mitas/models/ocr/paddle/official_models"))
    rec = "latin_PP-OCRv5_mobile_rec" if lang.lower()=="latin" else "en_PP-OCRv5_mobile_rec"
    kw={"lang":lang}
    if os.environ.get("JENERIK_PADDLE_FAST_NO_DOC")=="1":
        kw.update(use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False)
    dd=mr/"PP-OCRv5_server_det"; rd=mr/rec
    if dd.exists(): kw.update(text_detection_model_name="PP-OCRv5_server_det",text_detection_model_dir=str(dd))
    if rd.exists(): kw.update(text_recognition_model_name=rec,text_recognition_model_dir=str(rd))
    det._PADDLE_CACHE[lang]=PaddleOCR(**kw)

def is_footage(path):
    """içerikli mi (siyah değil, kredi değil) = footage şüphesi."""
    g=np.asarray(Image.open(path).convert("L"))
    if g.mean()<18: return "black"           # siyah/fade → zararsız
    ocr=det._PADDLE_CACHE[cfg.ocr_lang]
    c=jp._is_credit_frame(ocr,path,cfg)
    return "credit" if c else "footage"

ensure_paddle()
res={}
for cd in sorted(glob.glob(f"{RUN}/Database/*")):
    fid=os.path.basename(cd)
    pool=sorted(Path(cd,"frames","cikis_jenerik").glob("*.png"))
    if len(pool)<8: continue
    tail=pool[-TAIL:]
    kinds=[is_footage(p) for p in tail]
    # sondan geriye: son CREDIT'e kadar kaç footage var
    foot_tail=0
    for k in reversed(kinds):
        if k=="footage": foot_tail+=1
        elif k=="credit": break
        else: continue  # black köprü
    n_foot=kinds.count("footage")
    short=fid.split("-1-0000")[0].split("_")[-1][:22]
    if foot_tail>=4 or n_foot>=8:
        res[fid]={"pool":len(pool),"foot_tail":foot_tail,"n_footage_in_tail":n_foot,"kinds":kinds}
        print(f"⚠ {short:>22} pool={len(pool)} kuyruk-footage={foot_tail} (son{TAIL}'de {n_foot} footage)",flush=True)
json.dump(res,open(f"{RUN}/reports/cikis_tail_scan.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"DONE — {len(res)} filmde şüpheli footage-kuyruk")
