#!/usr/bin/env python3
"""Sheriff kabul koşusundan LeBron/Nash/Jordan karşılaştırma raporu üret."""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sqlite3
import statistics
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path


ROLLER = ("reader_master", "reader_frame", "reader_video")
ETIKET = {
    "reader_master": "lebron",
    "reader_frame": "nash",
    "reader_video": "jordan",
}
ROL_SOZCUKLERI = {
    "director", "directed", "producer", "produced", "production", "music",
    "editor", "editing", "camera", "casting", "cast", "screenplay", "writer",
    "art", "sound", "costume", "makeup", "yapimci", "yonetmen", "senaryo",
    "muzik", "kurgu", "oyuncular", "goruntu", "ses", "rejissor", "operator",
}


def _json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _fold(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text)).casefold()
    value = "".join(c for c in value if c.isalnum() or c.isspace())
    return " ".join(value.split())


def _name_like(text: str) -> bool:
    fold = _fold(text)
    words = fold.split()
    if not 2 <= len(words) <= 6:
        return False
    if any(word in ROL_SOZCUKLERI for word in words):
        return False
    letters = sum(c.isalpha() for c in fold)
    return letters >= 5 and letters / max(1, len(fold.replace(" ", ""))) >= 0.75


def _satirlar(doc: dict) -> list[str]:
    return [str(row.get("raw_text") or row.get("normalized_text") or "").strip()
            for row in (doc.get("lines") or [])
            if str(row.get("raw_text") or row.get("normalized_text") or "").strip()]


def _eslestir(a: list[str], b: list[str], esik: float = 0.86
              ) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    """Tek-kullanımlı fuzzy eşleme; kronoloji yerine en güçlü benzerlik."""
    fa, fb = [_fold(x) for x in a], [_fold(x) for x in b]
    adaylar = []
    for i, left in enumerate(fa):
        if not left:
            continue
        for j, right in enumerate(fb):
            if not right:
                continue
            score = (1.0 if left == right else
                     difflib.SequenceMatcher(None, left, right).ratio())
            if score >= esik:
                adaylar.append((score, i, j))
    kullanilan_a, kullanilan_b, eslesme = set(), set(), []
    for score, i, j in sorted(adaylar, reverse=True):
        if i in kullanilan_a or j in kullanilan_b:
            continue
        kullanilan_a.add(i)
        kullanilan_b.add(j)
        eslesme.append((i, j, round(score, 4)))
    return (eslesme,
            [i for i in range(len(a)) if i not in kullanilan_a],
            [j for j in range(len(b)) if j not in kullanilan_b])


def _paket(result: dict) -> dict:
    doc = result.get("document")
    if isinstance(doc, dict):
        return doc
    raw_path = result.get("packet_path") or result.get("tower_packet_path")
    if raw_path:
        path = Path(str(raw_path))
        if path.is_file():
            return _json(path.read_text(encoding="utf-8"))
    return {}


def _motor_ozeti(row: sqlite3.Row) -> dict:
    result = _json(row["result_json"])
    doc = _paket(result)
    lines = _satirlar(doc)
    resources = result.get("resource_usage") or doc.get("resource_usage") or {}
    proof_n = sum(bool(item.get("evidence")) for item in (doc.get("lines") or []))
    assets = doc.get("assets") or []
    master = next((x for x in assets if x.get("kind") == "master_png"), None)
    if master is None and row["logical_role"] == "reader_master":
        master = next((x for x in assets if str(x.get("path", "")).endswith(
            "master.png")), None)
    return {
        "status": row["status"],
        "attempt_count": row["attempt_count"],
        "duration_s": resources.get("duration_s"),
        "peak_vram_mb": resources.get("peak_vram_mb"),
        "peak_rss_mb": resources.get("peak_rss_mb"),
        "content": (doc.get("status") or {}).get("content"),
        "proof_status": (doc.get("status") or {}).get("proof"),
        "line_count": len(lines),
        "proof_line_count": proof_n,
        "proof_coverage": round(proof_n / len(lines), 4) if lines else None,
        "name_like_count": sum(_name_like(x) for x in lines),
        "master": ({k: master.get(k) for k in
                    ("path", "bytes", "width", "height", "sha256")}
                   if master else None),
        "lines": lines,
        "error": result.get("reason") or result.get("error"),
    }


def _kiyas(a_ad: str, a: dict, b_ad: str, b: dict) -> dict:
    aa, bb = a.get("lines") or [], b.get("lines") or []
    matches, only_a, only_b = _eslestir(aa, bb)
    return {
        "left": a_ad,
        "right": b_ad,
        "matched": len(matches),
        "left_coverage": round(len(matches) / len(aa), 4) if aa else None,
        "right_coverage": round(len(matches) / len(bb), 4) if bb else None,
        "left_unique_count": len(only_a),
        "right_unique_count": len(only_b),
        "left_name_like_gain_count": sum(_name_like(aa[i]) for i in only_a),
        "right_name_like_gain_count": sum(_name_like(bb[i]) for i in only_b),
        "left_unique": [aa[i] for i in only_a],
        "right_unique": [bb[i] for i in only_b],
    }


def _median(values: list[float | int | None]) -> float | None:
    clean = [float(x) for x in values if x is not None]
    return round(statistics.median(clean), 3) if clean else None


def _dis_kapilar(parity_path: Path | None, lebron_probe_path: Path | None,
                 nash_gate_paths: list[Path]) -> dict:
    result: dict = {}
    if parity_path and parity_path.is_file():
        parity = _json(parity_path.read_text(encoding="utf-8"))
        result["lebron_parity"] = {
            key: parity.get(key) for key in (
                "film_count", "pixel_identical_count", "lebron_mode_count",
                "summary_equal_count", "failed_films")
        }
    if lebron_probe_path and lebron_probe_path.is_file():
        probe = _json(lebron_probe_path.read_text(encoding="utf-8"))
        evidence = probe.get("kanit") or {}
        produced = next((x for x in (probe.get("uretilen") or [])
                         if x.get("tip") == "master"), {})
        result["lebron_gpu_probe"] = {
            "durum": probe.get("durum"), "sure_sn": probe.get("sure_sn"),
            "paddle_release_vram_mb": evidence.get("paddle_release_vram_mb"),
            "model": evidence.get("model_olcum"), "master": produced,
        }
    gates = {}
    for path in nash_gate_paths:
        if not path.is_file():
            continue
        doc = _json(path.read_text(encoding="utf-8"))
        rows = doc.get("satirlar") or []
        cyrillic = sum(any("CYRILLIC" in unicodedata.name(c, "") for c in
                           str(row.get("text", ""))) for row in rows)
        arabic = sum(any("ARABIC" in unicodedata.name(c, "") for c in
                         str(row.get("text", ""))) for row in rows)
        gates[str(doc.get("film_id") or path.parent.parent.name)] = {
            "path": str(path.resolve()), "durum": doc.get("durum"),
            "sure_sn": doc.get("sure_sn"), "line_count": len(rows),
            "cyrillic_line_count": cyrillic,
            "arabic_line_count": arabic,
            "latin_preserved": [row.get("text") for row in rows
                                if row.get("motor") == "paddle_latin_preserved"],
        }
    if gates:
        result["nash_multiscript"] = gates
    return result


def _ozet(kayitlar: list[dict]) -> dict:
    result = {}
    for role, label in ETIKET.items():
        motors = [x["engines"][label] for x in kayitlar]
        result[label] = {
            "status_counts": dict(Counter(x["status"] for x in motors)),
            "duration_median_s": _median([x["duration_s"] for x in motors]),
            "duration_total_s": round(sum(float(x["duration_s"] or 0)
                                           for x in motors), 3),
            "peak_vram_max_mb": max(
                [float(x["peak_vram_mb"]) for x in motors
                 if x["peak_vram_mb"] is not None], default=None),
            "line_total": sum(x["line_count"] for x in motors),
            "name_like_total": sum(x["name_like_count"] for x in motors),
            "proof_line_total": sum(x["proof_line_count"] for x in motors),
            "proof_coverage": round(
                sum(x["proof_line_count"] for x in motors)
                / max(1, sum(x["line_count"] for x in motors)), 4),
        }
    result["nash_independence"] = {
        "section_count": len(kayitlar),
        "nash_terminal_count": sum(
            x["engines"]["nash"]["status"] in {"SUCCEEDED", "NO_CONTENT"}
            for x in kayitlar),
        "kobe_no_content_or_failed_count": sum(
            x["boundary_status"] in {"NO_CONTENT", "FAILED"} for x in kayitlar),
        "nash_ran_when_kobe_no_content_or_failed": sum(
            x["boundary_status"] in {"NO_CONTENT", "FAILED"}
            and x["engines"]["nash"]["attempt_count"] > 0 for x in kayitlar),
    }
    return result


def _markdown(report: dict) -> str:
    s = report["summary"]
    acceptance = report["acceptance"]
    lines = [
        "# LeBron–Nash–Jordan Sheriff kabul raporu",
        "",
        f"Pipeline: `{report['pipeline_version']}` · "
        f"{report['film_count']} film · {report['section_count']} bölüm",
        "",
        f"Üretim terfi kapısı: **{'GEÇTİ' if acceptance['promotion_pass'] else 'GEÇMEDİ'}** "
        f"(terminal={acceptance['all_runs_terminal']}, "
        f"failed run={acceptance['failed_run_count']}, "
        f"failed task={acceptance['failed_task_count']}).",
        "",
        "## Sonuç özeti",
        "",
        "| Motor | Durumlar | Medyan süre | Tepe VRAM | Satır | Name-like | Proof |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ("lebron", "nash", "jordan"):
        x = s[label]
        lines.append(
            f"| {label.title()} | `{json.dumps(x['status_counts'], ensure_ascii=False)}` "
            f"| {x['duration_median_s']} sn | {x['peak_vram_max_mb']} MiB "
            f"| {x['line_total']} | {x['name_like_total']} "
            f"| {x['proof_line_total']}/{x['line_total']} ({x['proof_coverage']:.1%}) |")
    ni = s["nash_independence"]
    lines.extend([
        "",
        "## Bağımsızlık kapısı",
        "",
        f"Nash terminal bölüm: **{ni['nash_terminal_count']}/{ni['section_count']}**. "
        f"Kobe FAILED/NO_CONTENT bölüm: **{ni['kobe_no_content_or_failed_count']}**; "
        f"bunların içinde Nash'in gerçekten denendiği bölüm: "
        f"**{ni['nash_ran_when_kobe_no_content_or_failed']}**.",
    ])
    external = report.get("external_gates") or {}
    if external:
        lines.extend(["", "## Ayrı gerçek GPU/alfabe kapıları", ""])
        if external.get("lebron_parity"):
            x = external["lebron_parity"]
            lines.append(
                f"LeBron terfi paritesi: **{x.get('pixel_identical_count')}/"
                f"{x.get('film_count')} piksel-birebir**, mode "
                f"{x.get('lebron_mode_count')}/{x.get('film_count')}, manifest "
                f"özeti {x.get('summary_equal_count')}/{x.get('film_count')}.")
        if external.get("lebron_gpu_probe"):
            x = external["lebron_gpu_probe"]
            model = x.get("model") or {}
            lines.append(
                f"LeBron gerçek GPU probu: Paddle kalıntı "
                f"**{x.get('paddle_release_vram_mb')} MiB**, GGUF tepe "
                f"**{model.get('vram_peak_mb')} MiB**, en uzun bant "
                f"**{model.get('max_call_seconds')} sn**, toplam "
                f"**{x.get('sure_sn')} sn**.")
        for film, x in (external.get("nash_multiscript") or {}).items():
            lines.append(
                f"Nash `{film}`: {x['cyrillic_line_count']} Kiril, "
                f"{x['arabic_line_count']} Arabic/Farsi, "
                f"korunan Latin `{x['latin_preserved']}`.")
    lines.extend([
        "",
        "## Film/bölüm tablosu",
        "",
        "| Film | Bölüm | Kobe | LeBron durum/satır/sn/VRAM | "
        "Nash durum/satır/sn/VRAM | Jordan durum/satır/sn/VRAM |",
        "|---|---|---|---|---|---|",
    ])
    for row in report["records"]:
        cells = []
        for label in ("lebron", "nash", "jordan"):
            x = row["engines"][label]
            cells.append(f"{x['status']}/{x['line_count']}/"
                         f"{x['duration_s']}/{x['peak_vram_mb']}")
        lines.append(f"| {row['film_id']} | {row['section']} | "
                     f"{row['boundary_status']} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines.extend([
        "",
        "## Yöntem",
        "",
        "Satırlar NFKC+casefold uygulanıp noktalama kaldırılarak normalize edildi. "
        "Tek-kullanımlı en güçlü `SequenceMatcher ≥0.86` eşleşmeleri örtüşme "
        "sayıldı. JSON raporunda her motor çifti için bütün benzersiz, kazanılan "
        "ve kaybedilen satırlar bulunur; Markdown yalnız özeti gösterir.",
        "",
        "Name-like sayımı bir kalite hükmü değil, 2–6 sözcüklü ve rol sözlüğü "
        "içermeyen satırlar için karşılaştırmalı sezgiseldir.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--pipeline")
    ap.add_argument("--out-json", type=Path, required=True)
    ap.add_argument("--out-md", type=Path, required=True)
    ap.add_argument("--lebron-parity", type=Path)
    ap.add_argument("--lebron-probe", type=Path)
    ap.add_argument("--nash-gate", action="append", default=[], type=Path)
    args = ap.parse_args()
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    pipeline = args.pipeline or connection.execute(
        "SELECT pipeline_version FROM runs ORDER BY created_at DESC LIMIT 1"
    ).fetchone()[0]
    runs = connection.execute(
        "SELECT * FROM runs WHERE pipeline_version=? ORDER BY film_id", (pipeline,)
    ).fetchall()
    records = []
    for run in runs:
        tasks = connection.execute(
            "SELECT * FROM tasks WHERE run_id=?", (run["run_id"],)).fetchall()
        by_key = {(x["logical_role"], x["section"]): x for x in tasks}
        for section in ("giris", "cikis"):
            engines = {}
            for role, label in ETIKET.items():
                row = by_key.get((role, section))
                engines[label] = (_motor_ozeti(row) if row else {
                    "status": "MISSING", "attempt_count": 0,
                    "duration_s": None, "peak_vram_mb": None,
                    "peak_rss_mb": None, "content": None,
                    "proof_status": None, "line_count": 0,
                    "proof_line_count": 0, "proof_coverage": None,
                    "name_like_count": 0, "master": None, "lines": [],
                    "error": "task missing"})
            boundary = by_key.get(("boundary", section))
            comparisons = [
                _kiyas("lebron", engines["lebron"], "nash", engines["nash"]),
                _kiyas("lebron", engines["lebron"], "jordan", engines["jordan"]),
                _kiyas("nash", engines["nash"], "jordan", engines["jordan"]),
            ]
            records.append({
                "film_id": run["film_id"], "run_id": run["run_id"],
                "run_status": run["status"], "section": section,
                "boundary_status": boundary["status"] if boundary else "MISSING",
                "engines": engines, "comparisons": comparisons,
            })
    report = {
        "schema": "mitas.sheriff-reader-acceptance/v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pipeline_version": pipeline,
        "film_count": len(runs), "section_count": len(records),
        "summary": _ozet(records), "records": records,
        "external_gates": _dis_kapilar(
            args.lebron_parity, args.lebron_probe, args.nash_gate),
    }
    all_terminal = all(run["status"] in {"SUCCEEDED", "FAILED"} for run in runs)
    failed_runs = sum(run["status"] == "FAILED" for run in runs)
    failed_tasks = sum(
        engine["status"] == "FAILED"
        for record in records for engine in record["engines"].values())
    nash_terminal = report["summary"]["nash_independence"]["nash_terminal_count"]
    promotion_pass = (all_terminal and failed_runs == 0 and failed_tasks == 0
                      and nash_terminal == len(records))
    report["acceptance"] = {
        "all_runs_terminal": all_terminal,
        "failed_run_count": failed_runs,
        "failed_task_count": failed_tasks,
        "nash_all_sections_terminal": nash_terminal == len(records),
        "promotion_pass": promotion_pass,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    args.out_md.write_text(_markdown(report), encoding="utf-8")
    return 0 if promotion_pass else 3


if __name__ == "__main__":
    raise SystemExit(main())
