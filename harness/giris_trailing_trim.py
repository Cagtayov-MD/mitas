# -*- coding: utf-8 -*-
"""giris_trailing_trim.py — GİRİŞ havuzu TRAILING footage-trim (KKF Aşama-1, giriş yolu).
Sorun: giriş detektörü kredi BAŞINI bulup [baş..pencere_sonu] alıyor → açılış kredisi ~180'de bitse de
359'a kadar footage topluyor (SİSTEMATİK, tüm eski açılış-kredili filmler). Çözüm: havuz-başından İLERİ
tara (paddle _is_credit_frame), kredi→footage sınırını bul, havuzu kredi-sonunda kes.

Tolerans: açılış kredisi kart-arası boşluk/kısa-sahne içerir → GAP kadar ardışık non-credit görülünce
kredi bitti say (son kredi karesi + buffer'a kes). Paddle kredi bulamazsa (non-Latin kaçan) → DOKUNMA.
Sadece cikis-analogu: KANITA dayalı, per-film hack değil.
"""
import sys, os, glob, json, shutil
sys.path.insert(0, "/opt/mitas"); sys.path.insert(0, "/opt/mitas/scripts")
from pathlib import Path
import _jenerik_pool as jp
import core.pipelines.ocr.jenerik_frame_pool_detector as det
from paddleocr import PaddleOCR

RUN = os.environ["MITAS_RUN_ROOT"]
DB = Path(RUN) / "Database"
cfg = jp.DetectorConfig(ocr_mode="paddle", ocr_stride=8)

STRIDE = 2      # havuz içi ileri-tarama adımı (~1.3s aralık)
GAP = 7         # bu kadar ardışık non-credit stride-adımı = kredi bitti (~14 kare boşluk toleransı)
BUFFER = 2      # son kredi karesinden sonra bu kadar kare bırak
MIN_KEEP = 12   # havuzu bundan aşağı kırpma (fail-safe)

# --- paddle yükle (detect_frame_dir init'i replik) ---
def ensure_paddle():
    lang = cfg.ocr_lang
    if lang in det._PADDLE_CACHE:
        return
    model_root = Path(os.environ.get("MITAS_JENERIK_PADDLE_MODEL_ROOT")
                      or os.environ.get("JENERIK_PADDLE_MODEL_ROOT",
                                        "/opt/mitas/models/ocr/paddle/official_models"))
    rec_name = "latin_PP-OCRv5_mobile_rec" if lang.lower() == "latin" else "en_PP-OCRv5_mobile_rec"
    kwargs = {"lang": lang}
    if os.environ.get("JENERIK_PADDLE_FAST_NO_DOC") == "1":
        kwargs["use_doc_orientation_classify"] = False
        kwargs["use_doc_unwarping"] = False
        kwargs["use_textline_orientation"] = False
    det_dir = model_root / "PP-OCRv5_server_det"; rec_dir = model_root / rec_name
    if det_dir.exists():
        kwargs["text_detection_model_name"] = "PP-OCRv5_server_det"
        kwargs["text_detection_model_dir"] = str(det_dir)
    if rec_dir.exists():
        kwargs["text_recognition_model_name"] = rec_name
        kwargs["text_recognition_model_dir"] = str(rec_dir)
    det._PADDLE_CACHE[lang] = PaddleOCR(**kwargs)

def find_credit_end(pool, ocr):
    """havuz-başından ileri tara; son kredi karesi index'ini döndür (None=hiç kredi bulunamadı)."""
    last_credit = None
    nc_run = 0
    seen_credit = False
    scan_to = len(pool)
    for i in range(0, scan_to, STRIDE):
        c = jp._is_credit_frame(ocr, pool[i], cfg)
        if c:
            last_credit = i; nc_run = 0; seen_credit = True
        elif c is False:
            if seen_credit:
                nc_run += 1
                if nc_run >= GAP and last_credit is not None:
                    return last_credit
        # c is None (ocr hata) → say ma
    return last_credit

def main():
    ensure_paddle()
    ocr = det._PADDLE_CACHE[cfg.ocr_lang]
    only = sys.argv[1:] or None
    clips = sorted(glob.glob(f"{RUN}/Database/*"))
    res = {}
    for cd in clips:
        fid = os.path.basename(cd)
        if only and not any(o in fid for o in only):
            continue
        pdir = Path(cd) / "frames" / "giris_jenerik"
        pool = sorted(pdir.glob("*.png"))
        if len(pool) <= MIN_KEEP:
            continue
        ce = find_credit_end(pool, ocr)
        if ce is None:
            res[fid] = {"pool": len(pool), "action": "no_credit_found_keep"}
            print(f"⚫ {len(pool):3} kredi-yok KORUNDU {fid[-26:]}", flush=True)
            continue
        cut = min(len(pool), ce + 1 + BUFFER)
        if cut >= len(pool) - 1:
            res[fid] = {"pool": len(pool), "credit_end": ce, "action": "already_tight"}
            print(f"✓ {len(pool):3} zaten sıkı (son={ce}) {fid[-26:]}", flush=True)
            continue
        cut = max(cut, MIN_KEEP)
        removed = [p for p in pool[cut:]]
        for p in removed:
            p.unlink()
        res[fid] = {"pool_old": len(pool), "credit_end": ce, "pool_new": cut,
                    "removed": len(removed), "action": "trimmed"}
        print(f"✂ {len(pool):3}→{cut:3} (kredi-sonu #{ce}, {len(removed)} footage atıldı) {fid[-26:]}", flush=True)
    json.dump(res, open(f"{RUN}/reports/stage1_giris_trim.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    nt = sum(1 for v in res.values() if v.get("action") == "trimmed")
    print(f"DONE — {nt} trimlendi / {len(res)} bakıldı")

if __name__ == "__main__":
    main()
