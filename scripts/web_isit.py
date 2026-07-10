# -*- coding: utf-8 -*-
"""WEB-ISITICI (hız #2+#3, 2026-07-05): film kimliği/afişi için gidilecek TMDB/OMDb/
Wikipedia/IMDb-suggestion URL'lerini OCR∥ASR boş penceresinde ÖN-ISITIR (web_cache doldurur).

KARAR VERMEZ, film klasörüne ASLA dosya yazmaz — yalnız HTTP yanıtlarını cache'e indirir.
Gerçek tüketiciler (poster_fetch, credit_qc_gates.web_identity, credit_identity) aynı
URL'leri diskten ~0 sn'de okur; kimlik/afiş karar mantıkları DEĞİŞMEZ.

Fail-safe: her adım try/except; çıkış kodu her zaman 0 (pipeline'ı asla bozamaz).
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--original", default="")
    ap.add_argument("--year", default="")
    a = ap.parse_args()
    t0 = time.time()
    warmed = []

    # 1) Afiş/kimlik hattı (poster_fetch): TMDB arama+meta+afiş, OMDb, Wikipedia, IMDb-suggestion.
    #    cast'siz çağrı gerçek koşunun URL'lerinin çoğunu aynen ısıtır; çıktı scratch'e gider, silinir.
    try:
        import importlib.util as ilu
        pf_path = os.path.join(os.path.dirname(HERE), "OCR-worktree", "pdf-mitas", "poster_fetch.py")
        spec = ilu.spec_from_file_location("pf_warm", pf_path)
        pf = ilu.module_from_spec(spec)
        spec.loader.exec_module(pf)
        scratch = os.path.join(os.environ.get("MITAS_WEB_CACHE_DIR", r"E:\MITAS\cache\web"), "_isit_scratch")
        os.makedirs(scratch, exist_ok=True)
        out = os.path.join(scratch, f"afis_{os.getpid()}.jpg")
        pf.fetch_poster(a.title, out, original=(a.original or None), year=(a.year or None))
        warmed.append("poster_fetch")
        try:
            if os.path.exists(out):
                os.remove(out)
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        warmed.append(f"poster_fetch:HATA:{type(e).__name__}")

    # 2) QC2-web kimlik hattı: ocr_director=None → ÇAPA-1 (KB) atlanır, doğrudan ÇAPA-2 TMDB
    #    aramaları (title+original+year'lı URL'ler) ısınır. kb=None güvenli (fail-safe fonksiyon).
    try:
        import credit_qc_gates as qg
        qg.web_identity(a.title, a.original or None, a.year or None,
                        ocr_director=None, summary=None, kb=None)
        warmed.append("qc2_web")
    except Exception as e:  # noqa: BLE001
        warmed.append(f"qc2_web:HATA:{type(e).__name__}")

    print(json.dumps({"status": "done", "warmed": warmed, "sn": round(time.time() - t0, 1)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
