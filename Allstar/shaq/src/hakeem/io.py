"""HAKEEM cikti islemleri: kilit, crop, atomik coklu dosya ve marker."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterator

from sozlesme import atomic_json
from src.hakeem.kontrol import finalize_request
from src.hakeem.motor import accepted_text


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@contextlib.contextmanager
def locked(target: Path) -> Iterator[None]:
    target.mkdir(parents=True, exist_ok=True)
    lock_path = target / ".lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def crop_requests(requests: list[dict[str, Any]], target: Path, run_id: str,
                  *, min_pad_px: int) -> None:
    if not requests:
        return
    from PIL import Image
    crop_dir = target / "kontrol" / "crops" / run_id
    crop_dir.mkdir(parents=True, exist_ok=True)
    for request in requests:
        bbox = request["bbox"]
        source = Path(request["_source_path"])
        tight = crop_dir / f"{request['request_id']}.png"
        context = crop_dir / f"{request['request_id']}.context.png"
        with Image.open(source) as image:
            pad_x = max(min_pad_px, (bbox["x1"] - bbox["x0"]) // 2)
            pad_y = max(min_pad_px, (bbox["y1"] - bbox["y0"]) * 2)
            context_bbox = (max(0, bbox["x0"] - pad_x), max(0, bbox["y0"] - pad_y),
                            min(image.width, bbox["x1"] + pad_x),
                            min(image.height, bbox["y1"] + pad_y))
            image.crop((bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"])).save(tight)
            image.crop(context_bbox).save(context)
        finalize_request(
            request,
            crop=str(tight.relative_to(target)),
            context_crop=str(context.relative_to(target)),
            crop_sha256=file_sha256(tight),
            context_crop_sha256=file_sha256(context),
        )


def validate_output(output: dict[str, Any]) -> None:
    statuses = {"GECTI", "METIN_YOK", "KONTROL_BEKLIYOR", "COZUMSUZ", "ARIZA"}
    if output.get("schema_version") != "mitas.hakeem/v1" or output.get("durum") not in statuses:
        raise ValueError("gecersiz HAKEEM cikti zarfi")
    groups = output.get("groups")
    if not isinstance(groups, list):
        raise ValueError("HAKEEM cikti groups liste olmali")
    decisions = {group.get("decision") for group in groups}
    group_ids = [group.get("group_id") for group in groups]
    if (any(not isinstance(group_id, str) or not group_id for group_id in group_ids) or
            len(group_ids) != len(set(group_ids))):
        raise ValueError("HAKEEM group_id degerleri benzersiz zorunlu metindir")
    request_ids = [request_id for group in groups for request_id in group.get("control_request_ids", [])]
    if len(request_ids) != len(set(request_ids)):
        raise ValueError("HAKEEM control_request_ids benzersiz olmali")
    if output["durum"] == "GECTI" and decisions & {"KONTROL_GEREKLI", "COZUMSUZ", "KONTROL_ARIZASI"}:
        raise ValueError("GECTI kapanmamis group tasiyamaz")
    if output["durum"] == "METIN_YOK" and groups:
        raise ValueError("METIN_YOK group tasiyamaz")
    if output["durum"] == "ARIZA" and not output.get("ariza"):
        raise ValueError("ARIZA kaniti zorunlu")
    if output["durum"] != "ARIZA" and output.get("ariza"):
        raise ValueError("ARIZA disi sonuc ariza alani tasiyamaz")


def write_result(target: Path, output: dict[str, Any], requests: list[dict[str, Any]]) -> Path:
    validate_output(output)
    marker = target / "_TAMAM"
    marker.unlink(missing_ok=True)
    atomic_json(target / "hakeem.json", output)
    request_path = target / "kontrol" / "istekler.jsonl"
    if requests:
        request_path.parent.mkdir(parents=True, exist_ok=True)
        temp = request_path.with_suffix(".jsonl.tmp")
        temp.write_text("".join(json.dumps(request, ensure_ascii=False) + "\n" for request in requests),
                        encoding="utf-8")
        os.replace(temp, request_path)
    else:
        request_path.unlink(missing_ok=True)
    text_path = target / "hakeem.txt"
    if output["durum"] == "GECTI":
        lines = accepted_text(output["groups"])
        temp = text_path.with_suffix(".txt.tmp")
        temp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        os.replace(temp, text_path)
    else:
        text_path.unlink(missing_ok=True)
    marker.write_text("", encoding="utf-8")
    return target / "hakeem.json"


def read_requests(target: Path) -> dict[str, dict[str, Any]]:
    path = target / "kontrol" / "istekler.jsonl"
    if not path.exists():
        return {}
    values: dict[str, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            value = json.loads(raw)
            values[value["request_id"]] = value
    return values
