# -*- coding: utf-8 -*-
"""test_gt.py — GPT'nin insan-doğrulanmış GT'sine karşı detektörü ölç (havuza DOKUNMADAN).
GT (0-tabanlı start_pos): ATTILA 539, KULUBE 887, DRAKULA 859, BABAM 415,
CENNETIN 726, DON_KISOT 379, MARIE 585, DIRILIS 804.
"""
import sys, os, glob
sys.path.insert(0, "/opt/mitas"); sys.path.insert(0, "/opt/mitas/scripts")
from pathlib import Path
import _jenerik_pool as jp
from core.pipelines.ocr.jenerik_frame_pool_detector import detect_frame_dir, list_images

RUN = os.environ["MITAS_RUN_ROOT"]
GT = {"ATTİLA_MARCEL":539, "KULÜBE":887, "DRAKULA":859, "2015-2248":415,
      "CENNETİN":726, "DON_KİŞOT":379, "MARIE_CURRIE":585, "ERTUĞRUL":804}
NAMES = {"2015-2248":"BABAM"}
cfg = jp.DetectorConfig(ocr_mode="paddle", ocr_stride=8)

print(f"{'film':>14} {'GT':>5} {'CV':>5} {'+ileri':>7} {'-geri':>6} {'YENİ':>5} {'hata':>5}")
print("-"*56)
errs_cv=[]; errs_new=[]
for part, gt in GT.items():
    cd=[d for d in glob.glob(f"{RUN}/Database/*") if part in os.path.basename(d)]
    if not cd: print(f"{part[:14]:>14}  YOK"); continue
    fdir=Path(cd[0],"frames","cikis")
    res=detect_frame_dir(fdir, Path(cd[0],"jenerik_debug_test","detector"), cfg, False)
    images=list_images(fdir)
    cv=res.start_pos
    new=cv; fwd=0; back=0
    if cv is not None:
        # create_pool ile AYNI sıra: 1) ileri footage-trim  2) geriye-genişletme
        fwd = jp._trim_footage_head_v2(images[int(cv):], cfg)
        new = int(cv) + fwd
        ext = jp._backward_extend_credits(images, new, cfg)
        back = new - ext
        new = ext
    e_cv=(cv-gt) if cv is not None else None
    e_new=(new-gt) if new is not None else None
    ok="✅" if e_new is not None and abs(e_new)<=3 else ("⚠" if e_new is not None and abs(e_new)<=10 else "❌")
    nm=NAMES.get(part,part)[:14]
    print(f"{nm:>14} {gt:>5} {str(cv):>5} {'+'+str(fwd) if fwd else '0':>7} {'-'+str(back) if back else '0':>6} {str(new):>5} {str(e_new):>5}  {ok}", flush=True)
    if e_cv is not None: errs_cv.append(abs(e_cv))
    if e_new is not None: errs_new.append(abs(e_new))
if errs_new:
    print(f"\nESKİ (CV)  ort|hata|={sum(errs_cv)/len(errs_cv):.1f}  ≤3kare: {sum(1 for e in errs_cv if e<=3)}/{len(errs_cv)}")
    print(f"YENİ (+geri) ort|hata|={sum(errs_new)/len(errs_new):.1f}  ≤3kare: {sum(1 for e in errs_new if e<=3)}/{len(errs_new)}")
