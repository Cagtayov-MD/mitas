#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independent credit-structure regression harness.

This does not touch the production pipeline. It tests the layers separately:
frame OCR -> temporal card segmentation -> role parsing -> strict person gate.

Run:
  E:\MITAS\venvs\ocr\Scripts\python.exe -B outputs\credit_structure_regression_harness.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(r"E:\MITAS")
DEFAULT_CASES = ROOT / "outputs" / "credit_structure_regression_cases.json"
DEFAULT_OUT = ROOT / "outputs" / "credit_structure_regression"
TEMPORAL_PROBE = ROOT / "outputs" / "temporal_credit_structure_probe.py"
CREDIT_CROSSCHECK = ROOT / "scripts" / "credit_crosscheck.py"


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def folded(tp: Any, text: str) -> str:
    return tp.fold(text or "")


def contains_fold(tp: Any, haystack: list[str], needle: str) -> bool:
    fn = folded(tp, needle)
    return any(fn == folded(tp, x) or fn in folded(tp, x) for x in haystack)


def dedupe_fold(tp: Any, values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = folded(tp, value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def role_key(role: str) -> str:
    return {
        "yonetmen": "director",
        "yapimci": "producer",
        "senaryo_yazar": "writer",
        "oyuncular": "cast",
    }.get(role, role)


def official_role_values(roles: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for key in ("yonetmen", "yapimci", "senaryo_yazar", "oyuncular"):
        out.extend(roles.get(key) or [])
    return out


def import_credit_crosscheck() -> Any | None:
    try:
        return load_module("credit_crosscheck_regression", CREDIT_CROSSCHECK)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] credit_crosscheck import failed: {exc}", flush=True)
        return None


def strict_pool_gate(cc: Any | None, name: str, pool: list[str]) -> dict[str, Any]:
    """Offline person gate: exact or strict 1-edit full-name match against a role pool."""
    if not name or not str(name).strip():
        return {"input": name, "output": None, "action": "DUSTU", "distance": None, "reason": "empty"}
    if cc is None:
        return {"input": name, "output": None, "action": "DUSTU", "distance": None, "reason": "cc_unavailable"}
    if not cc._name_tokens_strict(name):
        return {
            "input": name,
            "output": None,
            "action": "DUSTU",
            "distance": None,
            "reason": "single_token_or_invalid_full_name",
        }
    for cand in pool:
        if cc.name_match(name, cand):
            return {"input": name, "output": cand, "action": "GECTI", "distance": 0, "reason": "pool_exact"}
    for cand in pool:
        if cc.strict_name_close(name, cand, max_edits=1):
            return {
                "input": name,
                "output": cand,
                "action": "FUZZY_DUZELDI",
                "distance": cc.strict_name_distance(name, cand, max_edits=1),
                "reason": "pool_strict_fuzzy",
            }
    return {
        "input": name,
        "output": None,
        "action": "DUSTU",
        "distance": None,
        "reason": "no_same_role_pool_match",
    }


def run_case(tp: Any, cc: Any | None, pl: Any, case: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    case_id = case["id"]
    case_out = out_dir / case_id
    temporal_out = case_out / "temporal"
    frames_dir = Path(case["frames_dir"])
    frames = [
        p
        for p in sorted(frames_dir.glob("*.png"), key=tp.frame_number)
        if int(case["start"]) <= tp.frame_number(p) <= int(case["end"])
    ]
    if not frames:
        return {
            "case_id": case_id,
            "ok": False,
            "stage": "frame_selection",
            "error": f"No frames found: {frames_dir}",
        }

    frame_rows = tp.ocr_frames(pl, frames)
    events = tp.segment_frames(frame_rows)
    roles = tp.parse_roles(events)
    tp.write_outputs(temporal_out, frame_rows, events, roles)

    role_checks: list[dict[str, Any]] = []
    missing_total = 0
    extra_total = 0
    for role, expected_values in (case.get("expected_roles") or {}).items():
        actual_values = roles.get(role) or []
        expected_keys = {folded(tp, x) for x in expected_values}
        actual_keys = {folded(tp, x) for x in actual_values}
        missing = [x for x in expected_values if folded(tp, x) not in actual_keys]
        extra = [x for x in actual_values if folded(tp, x) not in expected_keys]
        missing_total += len(missing)
        extra_total += len(extra)
        role_checks.append(
            {
                "case_id": case_id,
                "role": role,
                "status": "PASS" if not missing and not extra else "FAIL",
                "expected": expected_values,
                "actual": actual_values,
                "missing": missing,
                "extra": extra,
            }
        )

    official_values = official_role_values(roles)
    forbidden_hits = [
        value for value in (case.get("must_not_include") or []) if contains_fold(tp, official_values, value)
    ]
    role_stage_ok = missing_total == 0 and extra_total == 0 and not forbidden_hits

    event_checks: list[dict[str, Any]] = []
    for expected in case.get("expected_events") or []:
        candidates = [
            event
            for event in events
            if all(contains_fold(tp, event.get("lines") or [], needle) for needle in expected.get("must_contain") or [])
        ]
        typed = [event for event in candidates if not expected.get("type") or event.get("type") == expected.get("type")]
        framed = [
            event
            for event in typed
            if (not expected.get("frame_start") or event.get("frame_start") == expected.get("frame_start"))
            and (not expected.get("frame_end") or event.get("frame_end") == expected.get("frame_end"))
        ]
        match = (framed or typed or candidates or [None])[0]
        if not match:
            event_checks.append(
                {
                    "case_id": case_id,
                    "event_id": expected.get("id"),
                    "status": "FAIL",
                    "reason": "event_not_found",
                    "expected": expected,
                    "actual": None,
                }
            )
            continue
        problems: list[str] = []
        for key in ("type", "frame_start", "frame_end"):
            if expected.get(key) and match.get(key) != expected.get(key):
                problems.append(f"{key}: expected={expected.get(key)} actual={match.get(key)}")
        event_checks.append(
            {
                "case_id": case_id,
                "event_id": expected.get("id"),
                "status": "PASS" if not problems else "FAIL",
                "reason": "; ".join(problems),
                "expected": expected,
                "actual": {
                    "event_id": match.get("event_id"),
                    "type": match.get("type"),
                    "frame_start": match.get("frame_start"),
                    "frame_end": match.get("frame_end"),
                    "best_frame": match.get("best_frame"),
                    "lines": match.get("lines"),
                },
            }
        )
    event_stage_ok = all(row["status"] == "PASS" for row in event_checks)

    gate_checks: list[dict[str, Any]] = []
    pools = case.get("gate_pools") or {}
    for role in ("yonetmen", "yapimci", "senaryo_yazar", "oyuncular"):
        pool = pools.get(role_key(role), [])
        for name in roles.get(role) or []:
            gate = strict_pool_gate(cc, name, pool)
            gate_checks.append({"case_id": case_id, "role": role, **gate})
    gate_stage_ok = all(row["action"] != "DUSTU" for row in gate_checks)

    return {
        "case_id": case_id,
        "title_tr": case.get("title_tr"),
        "ok": bool(frame_rows) and event_stage_ok and role_stage_ok and gate_stage_ok,
        "frames_ocrd": len(frame_rows),
        "events_n": len(events),
        "roles": roles,
        "role_checks": role_checks,
        "forbidden_hits": forbidden_hits,
        "event_checks": event_checks,
        "gate_checks": gate_checks,
        "stage_ok": {
            "frame_ocr": bool(frame_rows) and any(row.get("lines") for row in frame_rows),
            "segmentation": event_stage_ok,
            "role_parse": role_stage_ok,
            "strict_person_gate": gate_stage_ok,
            "pdf_contract": role_stage_ok and gate_stage_ok,
        },
        "temporal_report": str(temporal_out / "temporal_credit_structure_probe.md"),
    }


def run_fuzzy_tests(cc: Any | None, tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for test in tests:
        gate = strict_pool_gate(cc, test.get("input", ""), test.get("pool") or [])
        ok = gate.get("action") == test.get("expected_action") and gate.get("output") == test.get("expected_output")
        rows.append(
            {
                "id": test.get("id"),
                "role": test.get("role"),
                "input": test.get("input"),
                "expected_action": test.get("expected_action"),
                "expected_output": test.get("expected_output"),
                "actual_action": gate.get("action"),
                "actual_output": gate.get("output"),
                "distance": gate.get("distance"),
                "reason": gate.get("reason"),
                "status": "PASS" if ok else "FAIL",
            }
        )
    return rows


def run_global_db_checks(cc: Any | None, tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if cc is None:
        return [{"status": "SKIP", "reason": "credit_crosscheck_unavailable"}]
    try:
        kb = cc.CreditKB()
    except Exception as exc:  # noqa: BLE001
        return [{"status": "SKIP", "reason": f"CreditKB init failed: {exc}"}]
    available = bool(getattr(kb, "imdb", None) or getattr(kb, "wd", None))
    rows: list[dict[str, Any]] = []
    if not available:
        rows.append({"status": "SKIP", "reason": "IMDb/Wikidata local DB unavailable"})
    else:
        for test in tests:
            try:
                hit = kb.global_person_match(test.get("input", ""), role=test.get("role"), max_edits=1)
            except Exception as exc:  # noqa: BLE001
                hit = {"error": str(exc)}
            rows.append(
                {
                    "id": test.get("id"),
                    "role": test.get("role"),
                    "input": test.get("input"),
                    "expected_output": test.get("expected_output"),
                    "hit": hit,
                    "status": "INFO",
                }
            )
    try:
        kb.close()
    except Exception:
        pass
    return rows


def write_markdown(out_dir: Path, payload: dict[str, Any]) -> Path:
    path = out_dir / "credit_structure_regression_report.md"
    lines: list[str] = ["# Credit Structure Regression Report", ""]
    summary = payload["summary"]
    lines.append(f"- Cases: {summary['cases_passed']}/{summary['cases_total']} passed")
    lines.append(f"- Fuzzy tests: {summary['fuzzy_passed']}/{summary['fuzzy_total']} passed")
    lines.append(f"- Output JSON: `{out_dir / 'credit_structure_regression_report.json'}`")
    lines.append(f"- Output XLSX: `{out_dir / 'credit_structure_regression_report.xlsx'}`")
    lines.append("")
    lines.append("## Case Results")
    for case in payload["cases"]:
        lines.append(f"### {case['case_id']} - {'PASS' if case['ok'] else 'FAIL'}")
        lines.append(f"- Frames OCR'd: {case.get('frames_ocrd')}")
        lines.append(f"- Events: {case.get('events_n')}")
        lines.append(f"- Temporal report: `{case.get('temporal_report')}`")
        lines.append("- Stage status:")
        for stage, ok in (case.get("stage_ok") or {}).items():
            lines.append(f"  - {stage}: {'PASS' if ok else 'FAIL'}")
        lines.append("- Roles:")
        for role, values in (case.get("roles") or {}).items():
            lines.append(f"  - {role}: {', '.join(values) if values else '-'}")
        if case.get("forbidden_hits"):
            lines.append(f"- Forbidden hits: {', '.join(case['forbidden_hits'])}")
        failed_events = [x for x in case.get("event_checks", []) if x.get("status") != "PASS"]
        if failed_events:
            lines.append("- Failed events:")
            for row in failed_events:
                lines.append(f"  - {row.get('event_id')}: {row.get('reason')}")
        failed_roles = [x for x in case.get("role_checks", []) if x.get("status") != "PASS"]
        if failed_roles:
            lines.append("- Failed roles:")
            for row in failed_roles:
                lines.append(f"  - {row.get('role')}: missing={row.get('missing')} extra={row.get('extra')}")
        failed_gate = [x for x in case.get("gate_checks", []) if x.get("action") == "DUSTU"]
        if failed_gate:
            lines.append("- Gate drops:")
            for row in failed_gate:
                lines.append(f"  - {row.get('role')}: {row.get('input')} ({row.get('reason')})")
        lines.append("")
    lines.append("## Fuzzy Gate Tests")
    for row in payload["fuzzy_tests"]:
        lines.append(
            f"- {row['id']}: {row['status']} | {row['input']} -> {row.get('actual_output')} "
            f"({row.get('actual_action')}, distance={row.get('distance')})"
        )
    lines.append("")
    lines.append("## Global DB Checks")
    for row in payload["global_db_checks"]:
        lines.append(f"- {row.get('id', 'db')}: {row.get('status')} | {row.get('input', '')} -> {row.get('hit', row.get('reason'))}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_xlsx(out_dir: Path, payload: dict[str, Any]) -> Path | None:
    try:
        from openpyxl import Workbook
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] openpyxl unavailable: {exc}", flush=True)
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["metric", "value"])
    for key, value in payload["summary"].items():
        ws.append([key, value])

    def add_sheet(name: str, headers: list[str], rows: list[dict[str, Any]]) -> None:
        sheet = wb.create_sheet(name)
        sheet.append(headers)
        for row in rows:
            sheet.append([json.dumps(row.get(h), ensure_ascii=False) if isinstance(row.get(h), (list, dict)) else row.get(h) for h in headers])

    role_rows = [row for case in payload["cases"] for row in case.get("role_checks", [])]
    event_rows = [row for case in payload["cases"] for row in case.get("event_checks", [])]
    gate_rows = [row for case in payload["cases"] for row in case.get("gate_checks", [])]
    raw_roles = []
    for case in payload["cases"]:
        for role, values in (case.get("roles") or {}).items():
            raw_roles.append({"case_id": case["case_id"], "role": role, "values": values})

    add_sheet("RoleChecks", ["case_id", "role", "status", "expected", "actual", "missing", "extra"], role_rows)
    add_sheet("EventChecks", ["case_id", "event_id", "status", "reason", "expected", "actual"], event_rows)
    add_sheet("GateChecks", ["case_id", "role", "input", "output", "action", "distance", "reason"], gate_rows)
    add_sheet("FuzzyTests", ["id", "role", "input", "expected_action", "expected_output", "actual_action", "actual_output", "distance", "reason", "status"], payload["fuzzy_tests"])
    add_sheet("GlobalDbChecks", ["id", "role", "input", "expected_output", "hit", "status", "reason"], payload["global_db_checks"])
    add_sheet("RawRoles", ["case_id", "role", "values"], raw_roles)

    path = out_dir / "credit_structure_regression_report.xlsx"
    wb.save(path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.cases.read_text(encoding="utf-8"))
    tp = load_module("temporal_probe_regression", TEMPORAL_PROBE)
    cc = import_credit_crosscheck()
    pl = tp._load_pipeline100()

    case_results = [run_case(tp, cc, pl, case, args.out_dir) for case in data.get("cases") or []]
    fuzzy_tests = run_fuzzy_tests(cc, data.get("fuzzy_gate_tests") or [])
    global_db_checks = run_global_db_checks(cc, data.get("fuzzy_gate_tests") or [])

    summary = {
        "cases_total": len(case_results),
        "cases_passed": sum(1 for case in case_results if case.get("ok")),
        "fuzzy_total": len(fuzzy_tests),
        "fuzzy_passed": sum(1 for row in fuzzy_tests if row.get("status") == "PASS"),
        "global_db_checks": len(global_db_checks),
    }
    payload = {
        "summary": summary,
        "cases": case_results,
        "fuzzy_tests": fuzzy_tests,
        "global_db_checks": global_db_checks,
    }
    json_path = args.out_dir / "credit_structure_regression_report.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = write_markdown(args.out_dir, payload)
    xlsx_path = write_xlsx(args.out_dir, payload)
    print(json_path)
    print(md_path)
    if xlsx_path:
        print(xlsx_path)
    return 0 if summary["cases_passed"] == summary["cases_total"] and summary["fuzzy_passed"] == summary["fuzzy_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
