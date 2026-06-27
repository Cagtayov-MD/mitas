# -*- coding: utf-8 -*-
"""JENERİK BAŞLANGIÇ-SEÇME ÖLÇÜM HARNESS'İ (etiketli, puanlı).

Goal-mode'un eksiği olan KÖR SINAV: yeni frame-pool detektörünün seçtiği çıkış-jeneriği
BAŞLANGICINI, insan-doğrulanmış altın-set ile karşılaştırıp tek bir kalite-tablosu çıkarır.

ALTIN SET: OCR-worktree/jenerik_verify_full60.csv
  her cikis satırı: gt (CORRECT/GENUINE_NORUN/FALSE_POSITIVE/WEAK) + region=[a-b] | RED
  a,b = sorted(frames/cikis/*.png) içindeki 0-tabanlı POZİSYON (detektörün start_pos'u ile AYNI uzay).

KARŞILAŞTIRMA (tolerans ±K kare):
  gt=CORRECT (region=[a-b], gerçek_başlangıç=a):
    bulundu & |pred-a|<=K  -> DOGRU
    bulundu & pred < a-K   -> ERKEN   (footage havuza girer: master-bloat / GLM footage okur)
    bulundu & pred > a+K   -> GEC     (kredi karesi düşer: oyuncu/yönetmen kaybı)
    bulunamadi (not_found) -> KACIRDI (false-negative; boş havuz → master yok = "hiç"; EN KÖTÜSÜ)
  gt=GENUINE_NORUN | region=RED (gerçekte kredi YOK):
    bulunamadi -> DOGRU       ;  bulundu -> YANLIS_POZ (footage'ı kredi sandı)
  gt=FALSE_POSITIVE (eski dedektör FP — bölge aslında footage):
    bulunamadi -> FP_KACINDI  ;  bulundu -> YANLIS_POZ
  gt=WEAK -> WEAK_ATLA (ayrı raporlanır, puanlamaya girmez)

Detektör ÜRETİM ayarıyla çalışır (ocr-mode=paddle, stride=8) — _jenerik_pool.py ile birebir.
Tek süreçte koşar (PaddleOCR modeli bir kez yüklenir, _PADDLE_CACHE).

Koşum (venvs/ocr):
  E:\\MITAS\\venvs\\ocr\\Scripts\\python.exe scripts\\jenerik_start_eval.py
  ... --ocr-mode none        # hızlı sezgisel (paddle yok) — paddle ile A/B için
  ... --tol 3 --limit 0      # tolerans / film sınırı
  ... --holdout-second-half  # altın setin 2. yarısını ayır (overfit ölçümü)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, r"E:\MITAS")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from core.pipelines.ocr.jenerik_frame_pool_detector import (  # noqa: E402
    DetectorConfig,
    detect_frame_dir,
)

DB_DEFAULT = Path(r"E:\MITAS\Database")
CSV_DEFAULT = Path(r"E:\MITAS\OCR-worktree\jenerik_verify_full60.csv")
OUT_DEFAULT = Path(r"E:\MITAS\outputs\jenerik_start_eval")

NORUN_GT = {"GENUINE_NORUN"}


def _accepted(status: str) -> bool:
    """Pool runner ile birebir: status kabul-edilir (havuz dolar) mı?"""
    return status == "already_in_credit" or status.startswith("found")


def _find_film_dir(db: Path, name: str) -> Path | None:
    d = db / name
    if d.is_dir():
        return d
    cand = [x for x in db.iterdir() if x.is_dir() and x.name == name]
    return cand[0] if cand else None


def _classify(gt: str, region: str, pred_found: bool, pred_pos: int | None, tol: int) -> tuple[str, int | None, int | None]:
    """(verdict, true_start, delta) döndürür. true_start None = not_found beklenir."""
    m = re.match(r"\[(\d+)-(\d+)\]", region.strip())
    region_is_norun = (region.strip() == "RED") or (gt in NORUN_GT)

    if gt == "WEAK":
        return "WEAK_ATLA", (int(m.group(1)) if m else None), None

    if region_is_norun:
        # gerçekte kredi yok → detektör de bulmamalı
        if not pred_found:
            return "DOGRU", None, None
        return "YANLIS_POZ", None, None

    if gt == "FALSE_POSITIVE":
        # eski FP: bölge footage; detektör bulmamalı. AMA başka, GERÇEK bir bölge bulmuş olabilir →
        # bulduğu yer eski FP bölgesine YAKINSA FP'yi tekrarladı (YANLIS_POZ), UZAKSA ayrı incele.
        fp_start = int(m.group(1)) if m else None
        if not pred_found:
            return "FP_KACINDI", fp_start, None
        if fp_start is not None and pred_pos is not None and abs(pred_pos - fp_start) <= 30:
            return "YANLIS_POZ", fp_start, pred_pos - fp_start
        return "FP_BASKA_YER_INCELE", fp_start, (None if (pred_pos is None or fp_start is None) else pred_pos - fp_start)

    # gt=CORRECT (veya region var, kredi gerçek)
    if not m:
        return "VERI_EKSIK", None, None
    true_start = int(m.group(1))
    if not pred_found or pred_pos is None:
        return "KACIRDI", true_start, None
    delta = pred_pos - true_start
    if abs(delta) <= tol:
        return "DOGRU", true_start, delta
    if delta < 0:
        return "ERKEN", true_start, delta
    return "GEC", true_start, delta


def build_cfg(ocr_mode: str) -> DetectorConfig:
    # _jenerik_pool.py argparse default'larıyla birebir (üretim davranışı).
    return DetectorConfig(
        max_width=640, text_threshold=0.34, soft_threshold=0.23,
        lookahead=8, min_hits=3, preroll_frames=2,
        ocr_mode=ocr_mode, ocr_stride=8, ocr_lang="en",
        sustain_window=18, sustain_hits=6,
        already_credit_frames=5, bottom_only_y=0.69,  # _jenerik_pool ile birebir: dataclass default'a güvenme
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Jenerik başlangıç-seçme ölçüm harness'i")
    ap.add_argument("--csv", default=str(CSV_DEFAULT))
    ap.add_argument("--db", default=str(DB_DEFAULT))
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--ocr-mode", choices=["none", "paddle"], default="paddle")
    ap.add_argument("--tol", type=int, default=3, help="±tolerans (kare)")
    ap.add_argument("--limit", type=int, default=0, help="0=hepsi")
    ap.add_argument("--holdout-second-half", action="store_true",
                    help="altın setin 2. yarısını ayrı raporla (overfit ölçümü)")
    args = ap.parse_args(argv)

    db = Path(args.db)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = build_cfg(args.ocr_mode)

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
    cikis = [r for r in rows if r.get("seg") == "cikis"]
    if args.limit:
        cikis = cikis[: args.limit]

    results: list[dict] = []
    skipped_no_frames = 0
    t0 = time.time()
    n_films = len(cikis)
    for i, r in enumerate(cikis):
        film = r["film"]
        gt = (r.get("gt") or "").strip()
        region = (r.get("region") or "").strip()
        quad = (r.get("quad") or "").strip()
        row_db = Path(r.get("db_root") or args.db)
        frel = (r.get("frames_rel") or "frames/cikis").replace("\\", "/")
        fd = _find_film_dir(row_db, film)
        cdir = fd
        if cdir is not None:
            for _part in frel.split("/"):
                cdir = cdir / _part
        if not cdir or not cdir.is_dir() or not any(cdir.glob("*.png")):
            skipped_no_frames += 1
            continue
        try:
            det = detect_frame_dir(cdir, None, cfg, False)
            pred_found = _accepted(det.status)
            pred_pos = det.start_pos if pred_found else None
            verdict, true_start, delta = _classify(gt, region, pred_found, pred_pos, args.tol)
            results.append({
                "film": film, "gt": gt, "quad": quad, "region": region,
                "true_start": true_start,
                "pred_status": det.status, "pred_start_pos": det.start_pos,
                "pred_start_file": det.start_file, "confidence": det.confidence,
                "credit_type": det.credit_type, "delta": delta, "verdict": verdict, "half": "",
                "reason": (det.reason or "")[:200],
            })
            print(f"  [{len(results):3d}] {film[:38]:38s} gt={gt:14s} "
                  f"pred={det.status:28s} pos={det.start_pos} v={verdict}", flush=True)
        except Exception as exc:  # noqa: BLE001
            results.append({"film": film, "gt": gt, "quad": quad, "region": region,
                            "verdict": "HATA", "error": f"{type(exc).__name__}: {exc}"})
            print(f"  [HATA] {film[:38]} : {exc}", flush=True)

    # half: PUANLANAN filmleri ikiye böl (atlananlar sayılmaz). BUG FIX — eskiden ham CSV indeksine
    # bakıyordu; atlananlar yüzünden puanlananların hepsi "ikinci" çıkıyordu (holdout işlevsizdi).
    # NOT: gerçek overfit ölçümü için goal-mode'un TUNE ettiği film listesi gerekir; alfabetik yarı kaba vekil.
    _scored_seq = [r for r in results if r["verdict"] not in ("WEAK_ATLA", "VERI_EKSIK", "HATA")]
    for _k, _r in enumerate(_scored_seq):
        _r["half"] = "ilk" if _k < len(_scored_seq) // 2 else "ikinci"

    # --- rapor ---
    detail_csv = out_dir / f"eval_detail_{args.ocr_mode}.csv"
    if results:
        cols = ["film", "gt", "quad", "region", "true_start", "pred_status",
                "pred_start_pos", "pred_start_file", "confidence", "credit_type",
                "delta", "verdict", "half", "reason", "error"]
        with detail_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for row in results:
                w.writerow(row)

    verdicts = Counter(r["verdict"] for r in results)
    scored = [r for r in results if r["verdict"] not in ("WEAK_ATLA", "VERI_EKSIK", "HATA")]
    n_dogru = sum(1 for r in scored if r["verdict"] in ("DOGRU", "FP_KACINDI"))
    acc = (n_dogru / len(scored)) if scored else 0.0
    kacirdi = verdicts.get("KACIRDI", 0)
    by_quad = defaultdict(Counter)
    for r in scored:
        by_quad[r.get("quad") or "?"][r["verdict"]] += 1

    summary = {
        "ocr_mode": args.ocr_mode,
        "tol": args.tol,
        "csv": args.csv,
        "cikis_rows": len(cikis),
        "scored_films": len(scored),
        "skipped_no_frames": skipped_no_frames,
        "verdicts": dict(verdicts),
        "accuracy": round(acc, 4),
        "kacirdi_count": kacirdi,
        "kacirdi_rate": round(kacirdi / len(scored), 4) if scored else None,
        "duration_sec": round(time.time() - t0, 1),
    }
    if args.holdout_second_half:
        for half in ("ilk", "ikinci"):
            hs = [r for r in scored if r.get("half") == half]
            hd = sum(1 for r in hs if r["verdict"] in ("DOGRU", "FP_KACINDI"))
            summary[f"acc_{half}_yari"] = round(hd / len(hs), 4) if hs else None
    (out_dir / f"eval_summary_{args.ocr_mode}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 64)
    print(f"JENERİK BAŞLANGIÇ ÖLÇÜMÜ  (ocr-mode={args.ocr_mode}, tol=±{args.tol})")
    print("=" * 64)
    print(f"altın-set cikis satırı : {len(cikis)}")
    print(f"kare-yok (atlandı)     : {skipped_no_frames}")
    print(f"puanlanan film         : {len(scored)}")
    print(f"hüküm dağılımı         : {dict(verdicts)}")
    print(f"DOĞRULUK               : {acc*100:.1f}%  ({n_dogru}/{len(scored)})")
    print(f"KAÇIRDI (false-neg)    : {kacirdi}"
          + (f"  (%{summary['kacirdi_rate']*100:.1f})" if summary["kacirdi_rate"] is not None else ""))
    if by_quad:
        print("quad kırılımı:")
        for q, c in sorted(by_quad.items()):
            tot = sum(c.values()); ok = c.get("DOGRU", 0) + c.get("FP_KACINDI", 0)
            print(f"   {q:28s} {ok}/{tot}  {dict(c)}")
    print(f"\n-> detay: {detail_csv}")
    print(f"-> özet : {out_dir / ('eval_summary_' + args.ocr_mode + '.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
