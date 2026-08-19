#!/usr/bin/env python3
"""Ayni okuma paketlerinde mevcut Shaq ile HAKEEM'i kosar ve tarafsiz olcer."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KULE = Path(__file__).resolve().parent
sys.path.insert(0, str(KULE))

import hakeem_main  # noqa: E402
import main as shaq_main  # noqa: E402
from sozlesme import atomic_json  # noqa: E402
from src.normalizasyon import normalize  # noqa: E402


SECTIONS = ("giris", "cikis")
DEFAULT_REPORTS = KULE / "olcum" / "raporlar"


def on_kontrol(input_root: str | Path) -> dict[str, Any]:
    root = Path(input_root)
    if not root.is_dir():
        raise ValueError(f"input dizini yok: {root}")
    eligible: list[str] = []
    rejected: list[dict[str, Any]] = []
    for film_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        counts = {bolum: len(list((film_dir / bolum).glob("*.okuma.json"))) for bolum in SECTIONS}
        if all(counts[bolum] == 2 for bolum in SECTIONS):
            eligible.append(film_dir.name)
        else:
            rejected.append({"film_id": film_dir.name, "paket_sayilari": counts})
    return {"input": str(root), "uygun_film_sayisi": len(eligible),
            "uygun_filmler": eligible, "reddedilen": rejected}


def _packet_snapshot(film_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for bolum in SECTIONS:
        for path in sorted((film_dir / bolum).glob("*.okuma.json")):
            result[str(path.relative_to(film_dir))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _read_engine(engine: str, film_id: str, bolum: str) -> dict[str, Any]:
    if engine == "shaq":
        root, name = shaq_main.OUT, "shaq.json"
    else:
        root, name = hakeem_main.OUT, "hakeem.json"
    folder = root / film_id / bolum
    path = folder / name
    if not path.exists() or not (folder / "_TAMAM").exists():
        return {"durum": "EKSIK", "lines": [], "path": str(path)}
    value = json.loads(path.read_text(encoding="utf-8"))
    if engine == "shaq":
        lines = [record.get("accepted_text") for record in value.get("records", [])
                 if record.get("accepted_text")]
        control = sum(len(record.get("control_request_ids", [])) for record in value.get("records", []))
    else:
        lines = [text for group in value.get("groups", []) for text in group.get("accepted_lines", []) if text]
        control = sum(len(group.get("control_request_ids", [])) for group in value.get("groups", []))
    return {"durum": value.get("durum", "BOZUK"), "lines": lines,
            "normalized_lines": [normalize(line) for line in lines],
            "control_request_count": control, "path": str(path),
            "run_id": value.get("run_id")}


def _load_gt(path: str | Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if not path:
        return {}
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema_version") != "mitas.shaq.gt/v1" or not isinstance(value.get("items"), list):
        raise ValueError("GT schema_version mitas.shaq.gt/v1 ve items listesi tasimali")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for item in value["items"]:
        if item.get("bolum") not in SECTIONS or item.get("durum") not in ("GECTI", "METIN_YOK"):
            raise ValueError("GT item film_id, bolum ve GECTI/METIN_YOK durum tasimali")
        lines = item.get("lines", [])
        if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
            raise ValueError("GT item lines metin listesi olmali")
        key = (item["film_id"], item["bolum"])
        if key in result:
            raise ValueError(f"yinelenen GT item: {key}")
        result[key] = {**item, "normalized_lines": [normalize(line) for line in lines]}
    return result


def calistir(input_root: str | Path, *, limit: int = 100, kimlik_json: str | None = None,
             force_hakeem: bool = False) -> list[str]:
    root = Path(input_root)
    preflight = on_kontrol(root)
    films = [root / film_id for film_id in preflight["uygun_filmler"][:limit]]
    if not films:
        raise ValueError("dort paketli uygun film yok; once okuyucu adaptorleri mitas.okuma/v1 uretmeli")
    completed: list[str] = []
    for film_dir in films:
        before = _packet_snapshot(film_dir)
        for bolum in SECTIONS:
            shaq_main.tek(film_dir, film_dir.name, bolum, kimlik_json)
        hakeem_main.film(film_dir, film_dir.name, kimlik_json, force=force_hakeem)
        after = _packet_snapshot(film_dir)
        if before != after:
            raise RuntimeError(f"karsilastirma sirasinda girdi paketleri degisti: {film_dir.name}")
        completed.append(film_dir.name)
    return completed


def _correct(prediction: dict[str, Any], truth: dict[str, Any]) -> bool:
    if prediction["durum"] != truth["durum"]:
        return False
    return truth["durum"] == "METIN_YOK" or prediction["normalized_lines"] == truth["normalized_lines"]


def rapor(film_ids: list[str], *, gt_path: str | Path | None = None) -> dict[str, Any]:
    gt = _load_gt(gt_path)
    rows: list[dict[str, Any]] = []
    counts = {engine: Counter() for engine in ("shaq", "hakeem")}
    quality = {engine: Counter() for engine in ("shaq", "hakeem")}
    for film_id in film_ids:
        for bolum in SECTIONS:
            engines = {engine: _read_engine(engine, film_id, bolum) for engine in ("shaq", "hakeem")}
            for engine, value in engines.items():
                counts[engine][value["durum"]] += 1
                counts[engine]["control_requests"] += value.get("control_request_count", 0)
            agree = (engines["shaq"]["durum"] == engines["hakeem"]["durum"] and
                     engines["shaq"].get("normalized_lines") == engines["hakeem"].get("normalized_lines"))
            row: dict[str, Any] = {"film_id": film_id, "bolum": bolum,
                                   "engines": engines, "motors_agree": agree}
            truth = gt.get((film_id, bolum))
            if truth:
                row["ground_truth"] = {"durum": truth["durum"], "lines": truth["lines"]}
                for engine, prediction in engines.items():
                    is_correct = _correct(prediction, truth)
                    quality[engine]["dogru"] += int(is_correct)
                    quality[engine]["yanlis"] += int(not is_correct)
                    if prediction["durum"] == "GECTI" and not is_correct:
                        quality[engine]["yanlis_gecis"] += 1
                    if prediction["durum"] in ("KONTROL_BEKLIYOR", "COZUMSUZ", "ARIZA", "EKSIK"):
                        quality[engine]["blok"] += 1
                    row["engines"][engine]["gt_correct"] = is_correct
            rows.append(row)
    gt_count = sum(1 for row in rows if "ground_truth" in row)
    pending = any(row["engines"][engine]["durum"] == "KONTROL_BEKLIYOR"
                  for row in rows for engine in ("shaq", "hakeem"))
    if not gt_count:
        conclusion = "GT_YOK_KAZANAN_BELIRLENEMEZ"
    elif gt_count != len(rows):
        conclusion = "GT_EKSIK_KAZANAN_BELIRLENEMEZ"
    elif pending:
        conclusion = "KONTROL_BEKLIYOR_KAZANAN_BELIRLENEMEZ"
    else:
        s, h = quality["shaq"], quality["hakeem"]
        shaq_key = (s["yanlis_gecis"], -s["dogru"], s["blok"])
        hakeem_key = (h["yanlis_gecis"], -h["dogru"], h["blok"])
        conclusion = "HAKEEM" if hakeem_key < shaq_key else "SHAQ" if shaq_key < hakeem_key else "ESIT"
    return {
        "schema_version": "mitas.shaq.karsilastirma/v1",
        "uretim_zamani": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "film_sayisi": len(film_ids), "bolum_sayisi": len(rows), "gt_bolum_sayisi": gt_count,
        "oncelik": ["en_az_yanlis_gecis", "en_cok_tam_dogru", "en_az_blok"],
        "kazanan": conclusion,
        "tam_gt": gt_count == len(rows), "bekleyen_kontrol_var": pending,
        "ozet": {engine: {
            "durumlar": {key: value for key, value in counts[engine].items() if key != "control_requests"},
            "control_request_count": counts[engine]["control_requests"],
            "kalite": dict(quality[engine])}
                 for engine in ("shaq", "hakeem")},
        "motor_anlasmazligi": sum(not row["motors_agree"] for row in rows),
        "items": rows,
    }


def _film_ids_from_outputs(limit: int | None = None) -> list[str]:
    values = sorted({path.name for root in (shaq_main.OUT, hakeem_main.OUT)
                     if root.exists() for path in root.iterdir() if path.is_dir()})
    return values[:limit] if limit is not None else values


def _write_report(value: dict[str, Any], path: str | Path | None) -> Path:
    if path:
        target = Path(path)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = DEFAULT_REPORTS / f"shaq_vs_hakeem_{stamp}.json"
    atomic_json(target, value)
    return target


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subs = root.add_subparsers(dest="command", required=True)
    run = subs.add_parser("calistir")
    run.add_argument("--input", required=True); run.add_argument("--limit", type=int, default=100)
    run.add_argument("--kimlik-json"); run.add_argument("--gt"); run.add_argument("--rapor")
    run.add_argument("--force-hakeem", action="store_true")
    report = subs.add_parser("rapor")
    report.add_argument("--limit", type=int); report.add_argument("--gt"); report.add_argument("--rapor")
    preflight = subs.add_parser("on-kontrol")
    preflight.add_argument("--input", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "on-kontrol":
        print(json.dumps(on_kontrol(args.input), ensure_ascii=False, indent=2)); return 0
    if args.command == "calistir":
        film_ids = calistir(args.input, limit=args.limit, kimlik_json=args.kimlik_json,
                            force_hakeem=args.force_hakeem)
    else:
        film_ids = _film_ids_from_outputs(args.limit)
    result = rapor(film_ids, gt_path=args.gt)
    path = _write_report(result, args.rapor)
    print(json.dumps({"rapor": str(path), "film_sayisi": len(film_ids),
                      "gt_bolum_sayisi": result["gt_bolum_sayisi"],
                      "kazanan": result["kazanan"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
