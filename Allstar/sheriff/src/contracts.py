from __future__ import annotations

import json
import mimetypes
import os
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from .util import atomic_write_json, now_iso, safe_component, sha256_file

SCHEMA_VERSION = "mitas.okuma/v2"
EXECUTION = {"SUCCEEDED", "FAILED", "NO_CONTENT"}
CONTENT = {"READ", "NO_TEXT", "PARTIAL", "UNKNOWN"}
PROOF = {"COMPLETE", "PARTIAL", "NONE"}
SECTIONS = {"giris", "cikis"}


class ContractError(ValueError):
    pass


def fold_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").casefold()
    return " ".join(value.split())


def asset_record(path: Path, *, asset_id: str | None = None,
                 origin_path: str | None = None, width: int | None = None,
                 height: int | None = None, frame_sequence: int | None = None,
                 source_time_s: float | None = None,
                 relative_to: Path | None = None) -> dict[str, Any]:
    path = path.resolve()
    display = str(path.relative_to(relative_to.resolve())) if relative_to else str(path)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {
        "asset_id": asset_id or f"asset-{uuid.uuid4().hex[:16]}",
        "path": display,
        "origin_path": origin_path or str(path),
        "sha256": sha256_file(path),
        "mime_type": mime,
        "bytes": path.stat().st_size,
        "width": width,
        "height": height,
        "frame_sequence": frame_sequence,
        "source_time_s": source_time_s,
    }


def line_record(raw_text: str, order: int, evidence: list[dict[str, Any]] | None = None,
                *, source_label: str | None = None) -> dict[str, Any]:
    return {
        "line_id": f"line-{order:06d}",
        "order": order,
        "raw_text": raw_text,
        "normalized_text": fold_text(raw_text),
        "source_label": source_label,
        "evidence": evidence or [],
    }


def packet(*, film_id: str, section: str, run_id: str, task_id: str,
           attempt_id: str, producer: dict[str, Any], inputs: list[dict[str, Any]],
           execution_status: str, content_status: str, proof_status: str,
           assets: list[dict[str, Any]] | None = None,
           lines: list[dict[str, Any]] | None = None,
           rejected_lines: list[dict[str, Any]] | None = None,
           unread_regions: list[dict[str, Any]] | None = None,
           diagnostics: dict[str, Any] | None = None,
           resource_usage: dict[str, Any] | None = None,
           parent_tasks: list[str] | None = None) -> dict[str, Any]:
    result = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": f"pkt-{uuid.uuid4().hex}",
        "created_at": now_iso(),
        "film": {"film_id": film_id},
        "section": section,
        "identity": {"run_id": run_id, "task_id": task_id,
                     "attempt_id": attempt_id},
        "producer": producer,
        "lineage": {"parent_tasks": parent_tasks or [], "inputs": inputs},
        "status": {"execution": execution_status, "content": content_status,
                   "proof": proof_status},
        "assets": assets or [],
        "lines": lines or [],
        "rejected_lines": rejected_lines or [],
        "unread_regions": unread_regions or [],
        "diagnostics": diagnostics or {},
        "resource_usage": resource_usage or {},
    }
    validate_packet(result)
    return result


def validate_packet(value: dict[str, Any], *, base_dir: Path | None = None,
                    verify_assets: bool = False) -> None:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"schema_version {SCHEMA_VERSION!r} olmali")
    if not isinstance(value.get("film"), dict):
        raise ContractError("film nesne olmali")
    if not str(value["film"].get("film_id") or "").strip():
        raise ContractError("film.film_id zorunlu")
    if not str(value.get("packet_id") or "").strip():
        raise ContractError("packet_id zorunlu")
    if not isinstance(value.get("producer"), dict):
        raise ContractError("producer nesne olmali")
    producer_id = value["producer"].get("id")
    if not producer_id:
        raise ContractError("producer.id zorunlu")
    try:
        safe_component(str(producer_id), "producer.id")
    except ValueError as exc:
        raise ContractError(str(exc)) from exc
    section = value.get("section")
    if section not in SECTIONS:
        raise ContractError(f"gecersiz section: {section!r}")
    identity = value.get("identity")
    if not isinstance(identity, dict):
        raise ContractError("identity nesne olmali")
    for key in ("run_id", "task_id", "attempt_id"):
        if not identity.get(key):
            raise ContractError(f"identity.{key} zorunlu")
    status = value.get("status")
    if not isinstance(status, dict):
        raise ContractError("status nesne olmali")
    if status.get("execution") not in EXECUTION:
        raise ContractError("status.execution gecersiz")
    if status.get("content") not in CONTENT:
        raise ContractError("status.content gecersiz")
    if status.get("proof") not in PROOF:
        raise ContractError("status.proof gecersiz")
    lines_value = value.get("lines")
    if not isinstance(lines_value, list):
        raise ContractError("lines liste olmali")
    lineage = value.get("lineage")
    if (not isinstance(lineage, dict)
            or not isinstance(lineage.get("parent_tasks"), list)
            or not isinstance(lineage.get("inputs"), list)):
        raise ContractError("lineage parent_tasks/inputs listeleri zorunlu")
    for field in ("rejected_lines", "unread_regions"):
        if not isinstance(value.get(field), list):
            raise ContractError(f"{field} liste olmali")
    for field in ("diagnostics", "resource_usage"):
        if not isinstance(value.get(field), dict):
            raise ContractError(f"{field} nesne olmali")
    if status.get("content") == "READ" and not lines_value:
        raise ContractError("READ icerik en az bir satir ister")
    if status.get("content") == "NO_TEXT" and lines_value:
        raise ContractError("NO_TEXT icerik satir tasiyamaz")
    if status.get("execution") == "NO_CONTENT" and (
            status.get("content") != "NO_TEXT" or status.get("proof") != "NONE"):
        raise ContractError("NO_CONTENT yalniz NO_TEXT/NONE ile kullanilir")
    if status.get("proof") == "COMPLETE" and (
            status.get("execution") != "SUCCEEDED"
            or status.get("content") != "READ" or not lines_value):
        raise ContractError("COMPLETE proof SUCCEEDED/READ ve satir ister")
    assets = value.get("assets")
    if not isinstance(assets, list):
        raise ContractError("assets liste olmali")
    ids: set[str] = set()
    assets_by_id: dict[str, dict[str, Any]] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            raise ContractError("asset kaydi nesne olmali")
        aid = asset.get("asset_id")
        if not aid or aid in ids:
            raise ContractError(f"asset_id eksik/tekrarli: {aid!r}")
        try:
            safe_component(str(aid), "asset_id")
        except ValueError as exc:
            raise ContractError(str(exc)) from exc
        ids.add(aid)
        assets_by_id[aid] = asset
        if not str(asset.get("path") or "").strip():
            raise ContractError(f"asset path eksik: {aid}")
        if not str(asset.get("mime_type") or "").strip():
            raise ContractError(f"asset mime_type eksik: {aid}")
        digest = asset.get("sha256")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise ContractError(f"asset sha256 gecersiz: {aid}")
        for dimension in ("width", "height"):
            number = asset.get(dimension)
            if number is not None and (not isinstance(number, int)
                                       or isinstance(number, bool) or number <= 0):
                raise ContractError(f"asset {dimension} pozitif tam sayi olmali: {aid}")
        sequence = asset.get("frame_sequence")
        if sequence is not None and (not isinstance(sequence, int)
                                     or isinstance(sequence, bool) or sequence < 1):
            raise ContractError(f"asset frame_sequence gecersiz: {aid}")
        source_time = asset.get("source_time_s")
        if source_time is not None and (not isinstance(source_time, (int, float))
                                        or isinstance(source_time, bool)
                                        or float(source_time) < 0):
            raise ContractError(f"asset source_time_s gecersiz: {aid}")
        if verify_assets:
            path = Path(asset.get("path", ""))
            path = path if path.is_absolute() else (base_dir or Path.cwd()) / path
            if not path.is_file() or sha256_file(path) != digest:
                raise ContractError(f"asset yok veya hash uyusmuyor: {path}")
            if asset.get("bytes") is not None and asset.get("bytes") != path.stat().st_size:
                raise ContractError(f"asset byte sayisi uyusmuyor: {path}")
    line_ids: set[str] = set()
    for line in lines_value:
        if not isinstance(line, dict):
            raise ContractError("line kaydi nesne olmali")
        line_id = line.get("line_id")
        if not line_id or line_id in line_ids:
            raise ContractError(f"line_id eksik/tekrarli: {line_id!r}")
        line_ids.add(line_id)
        if not isinstance(line.get("raw_text"), str) or not line["raw_text"].strip():
            raise ContractError("bos ham satir")
        if line.get("normalized_text") != fold_text(line["raw_text"]):
            raise ContractError(f"normalized_text ham satirla uyusmuyor: {line_id}")
        order = line.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 0:
            raise ContractError(f"line order gecersiz: {line_id}")
        evidence_values = line.get("evidence")
        if not isinstance(evidence_values, list):
            raise ContractError(f"line evidence liste olmali: {line_id}")
        for evidence in evidence_values:
            if not isinstance(evidence, dict):
                raise ContractError("evidence kaydi nesne olmali")
            if evidence.get("asset_id") not in ids:
                raise ContractError("evidence bilinmeyen asset kullaniyor")
            bbox = evidence.get("bbox")
            space = evidence.get("coordinate_space")
            if bbox is None:
                raise ContractError("evidence bbox olmadan tasinamaz")
            if space != "pixel_xyxy" or not _valid_bbox(bbox):
                raise ContractError(f"bbox pixel xyxy olmali: {bbox!r}")
            asset = assets_by_id[evidence["asset_id"]]
            if not str(asset.get("mime_type") or "").startswith("image/"):
                raise ContractError("bbox yalniz image asset uzerinde olabilir")
            width, height = asset.get("width"), asset.get("height")
            if not (isinstance(width, int) and width > 0
                    and isinstance(height, int) and height > 0):
                raise ContractError("bbox asset'i pozitif width/height tasimali")
            if bbox[2] > width or bbox[3] > height:
                raise ContractError(f"bbox asset sinirini asiyor: {bbox!r} > {width}x{height}")
    if status.get("proof") == "COMPLETE":
        for line in lines_value:
            localized = False
            for evidence in line.get("evidence") or []:
                if evidence.get("bbox") is None:
                    continue
                asset = assets_by_id[evidence["asset_id"]]
                if (asset.get("frame_sequence") is not None
                        and asset.get("source_time_s") is not None):
                    localized = True
                    break
            if not localized:
                raise ContractError(
                    "COMPLETE proof her satir icin bbox+frame_sequence+source_time_s ister")


def _valid_bbox(bbox: Any) -> bool:
    return (isinstance(bbox, list) and len(bbox) == 4
            and all(isinstance(v, int) and not isinstance(v, bool) for v in bbox)
            and 0 <= bbox[0] < bbox[2] and 0 <= bbox[1] < bbox[3])


def read_packet(path: Path, *, expected: dict[str, str] | None = None,
                verify_assets: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"JSON okunamadi: {path}: {exc}") from exc
    validate_packet(value, base_dir=path.parent, verify_assets=verify_assets)
    for key, wanted in (expected or {}).items():
        if key == "film_id":
            actual = (value.get("film") or {}).get("film_id")
        elif key in {"run_id", "task_id", "attempt_id"}:
            actual = (value.get("identity") or {}).get(key)
        else:
            actual = value.get(key)
        if actual != wanted:
            raise ContractError(f"{key} uyusmuyor: {actual!r} != {wanted!r}")
    return value


def write_packet(path: Path, value: dict[str, Any]) -> None:
    validate_packet(value)
    atomic_write_json(path, value)


def sheriff_identity() -> dict[str, str]:
    return {
        "run_id": os.environ.get("MITAS_SHERIFF_RUN_ID", "standalone"),
        "task_id": os.environ.get("MITAS_SHERIFF_TASK_ID", "standalone"),
        "attempt_id": os.environ.get("MITAS_SHERIFF_ATTEMPT_ID", "standalone"),
    }
