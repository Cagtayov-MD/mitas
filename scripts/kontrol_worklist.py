# -*- coding: utf-8 -*-
"""kontrol_worklist.py — KONTROL kuyruğu ÇALIŞMA-ANINDA worklist üretici (İP-8, 2026-07-11).

NEDEN: plana SABİT sayı girmez (GPT tur-2 dersi: 47/48 payda-tartışması anlamsız; sayılar
hareketli). Bu araç KONTROL export'unu + Database _DURUM'larını CANLI tarayıp kovalar üretir:
  • TEKNIK_ARIZA_OCR   : OCR hiç-koşmamış/motor-yok (frame var, kunye yok) → OCR-stage retry
  • TEKNIK_ARIZA_ASR   : ASR failed → ASR-stage retry (özet-yok blokeri)
  • HUB_YOK            : export'ta PDF var ama Database hub yok
  • EXTRACTION_TF      : _DURUM.extraction_status=TECHNICAL_FAILURE (İP-2 sonrası dolu)
  • DRIFT             : karar.pipeline.json vs _DURUM uyuşmazlığı (İP-4 check_drift)
  • CIFT_PDF          : aynı TRT birden fazla PDF (bayat-duplicate; alan-çapraz-kontrol şart)
  • TRIAJ_HAZIR       : karar=Kontrol & yönetmen+≥2 oyuncu+özet DOLU ama hard-gate-bloke
                        (36-film sınıfı — otomatik ONAYLI adayı DEĞİL, öncelikli insan-triajı)

READ-ONLY: hiçbir hub'a dokunmaz. Çıktı JSON + insan-özet. Kovalar İP-8 korumalı re-run'ın girdisi."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mitas_roots  # noqa: E402

TRT_RE = re.compile(r"\d{4}-\d{3,4}-\d-\d{3,4}-\d{2}-\d")


def _trt(name: str) -> str | None:
    m = TRT_RE.search(name)
    return m.group(0) if m else None


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def build_worklist() -> dict:
    roots = mitas_roots.resolve(None)
    db_root, kontrol_dir = roots["DB_ROOT"], roots["KONTROL"]

    # 1) KONTROL export PDF'leri → TRT + çift-PDF tespiti
    pdfs = sorted(kontrol_dir.glob("*.pdf")) if kontrol_dir.exists() else []
    trt_to_pdfs: dict[str, list[str]] = defaultdict(list)
    for p in pdfs:
        t = _trt(p.name)
        if t:
            trt_to_pdfs[t].append(p.name)
    benzersiz = sorted(trt_to_pdfs)
    cift_pdf = {t: v for t, v in trt_to_pdfs.items() if len(v) > 1}

    # 2) TRT → Database hub eşleme (NFC, çoklu-eşleşme AMBIGUOUS işareti)
    import unicodedata
    def _nfc(s): return unicodedata.normalize("NFC", s or "")
    hub_index: dict[str, list[Path]] = defaultdict(list)
    if db_root.exists():
        for d in db_root.iterdir():
            if d.is_dir() and (d / "_DURUM.json").exists():
                t = _trt(_nfc(d.name))
                if t:
                    hub_index[t].append(d)

    kovalar: dict[str, list] = defaultdict(list)
    for t in benzersiz:
        hubs = hub_index.get(t, [])
        if not hubs:
            kovalar["HUB_YOK"].append({"trt": t, "pdf": trt_to_pdfs[t]})
            continue
        if len(hubs) > 1:
            kovalar["AMBIGUOUS_HUB"].append({"trt": t, "hubs": [h.name for h in hubs]})
        hub = hubs[0]
        d = _load(hub / "_DURUM.json")
        clip = _load(hub / "clip.json")
        mods = clip.get("modules") or {}
        ocr_st = (mods.get("ocr") or {}).get("status")
        asr_st = (mods.get("asr") or {}).get("status")
        ext = d.get("extraction_status")
        q = d.get("qwen_qc") or {}
        kayit = {"trt": t, "hub": hub.name}

        if ocr_st in ("partial", None) and (hub / "frames").exists():
            # OCR job var mı / kunye üretilmiş mi?
            kunye_var = any((hub / "ocr").glob("ocr-*/kunye.txt")) if (hub / "ocr").exists() else False
            if not kunye_var:
                kovalar["TEKNIK_ARIZA_OCR"].append({**kayit, "ocr_status": ocr_st})
                continue
        if asr_st not in ("done", "ATLANDI", "skipped_unsupported_lang", None):
            kovalar["TEKNIK_ARIZA_ASR"].append({**kayit, "asr_status": asr_st})
        if str(ext).upper() == "TECHNICAL_FAILURE":
            kovalar["EXTRACTION_TF"].append({**kayit, "extraction_detail": d.get("extraction_detail")})
        # DRIFT
        try:
            import credit_severity_router as _r
            drift = _r.check_drift(hub)
            if drift:
                kovalar["DRIFT"].append({**kayit, "drift": drift})
        except Exception:  # noqa: BLE001
            pass
        # TRIAJ_HAZIR (36-film sınıfı): temel-alan dolu ama karar=Kontrol
        if (d.get("karar") == "Kontrol" and q.get("yonetmen_var")
                and (q.get("oyuncu_sayisi") or 0) >= 2 and q.get("ozet_var")):
            kovalar["TRIAJ_HAZIR"].append({
                **kayit, "neden": d.get("neden"), "ocr_bucket": d.get("ocr_bucket")})

    for t, v in cift_pdf.items():
        kovalar["CIFT_PDF"].append({"trt": t, "pdf": v})

    ozet = {k: len(v) for k, v in sorted(kovalar.items())}
    return {
        "kontrol_pdf": len(pdfs),
        "benzersiz_trt": len(benzersiz),
        "hub_eslesen": sum(1 for t in benzersiz if hub_index.get(t)),
        "kovalar": {k: v for k, v in kovalar.items()},
        "ozet": ozet,
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="JSON çıktı yolu")
    ap.add_argument("--kova", default=None, help="yalnız bu kovayı listele (ör. TRIAJ_HAZIR)")
    a = ap.parse_args()
    wl = build_worklist()
    print("=== KONTROL WORKLIST (canlı) ===")
    print(f"KONTROL PDF: {wl['kontrol_pdf']} | benzersiz TRT: {wl['benzersiz_trt']} | "
          f"hub-eşleşen: {wl['hub_eslesen']}")
    print("\nKOVALAR:")
    for k, n in wl["ozet"].items():
        print(f"  {k:22s} {n}")
    if a.kova and a.kova in wl["kovalar"]:
        print(f"\n=== {a.kova} ({len(wl['kovalar'][a.kova])}) ===")
        for r in wl["kovalar"][a.kova]:
            print(f"  {r.get('trt')}  {r.get('hub', '')[:50]}  {r.get('neden') or r.get('drift') or ''}")
    if a.out:
        Path(a.out).write_text(json.dumps(wl, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n[yazıldı] {a.out}")
