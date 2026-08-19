"""Kör bbox kontrol kuyruğu; burada hiçbir model çağrılmaz."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .normalizasyon import normalize


def request_for(film_id: str, bolum: str, evidence: dict[str, Any], role: str) -> dict[str, Any]:
    """Aday OCR metni içermez: kontrol sağlayıcısı crop'u kör okur."""
    result = {"request_id": str(uuid.uuid4()), "film_id": film_id, "bolum": bolum,
            "asset_id": evidence["asset_id"], "bbox": evidence["bbox"], "role": role,
            "crop": None, "context_crop": None, "schema_version": "mitas.kontrol/v1"}
    # Sadece Shaq içindeki crop üretimi için; yazılmadan önce çıkarılır.
    if "_source_path" in evidence:
        result["_source_path"] = evidence["_source_path"]
    return result


def read_answers(path: str | Path) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        value = json.loads(raw)
        if value.get("durum") not in ("OKUNDU", "ARIZA") or not isinstance(value.get("request_id"), str):
            raise ValueError("gecersiz kontrol cevabi")
        answers[value["request_id"]] = value
    return answers


def exact_answer(answers: list[dict[str, Any]], candidates: list[str]) -> str | None:
    texts = {normalize(value["text"]) for value in answers if value.get("durum") == "OKUNDU" and isinstance(value.get("text"), str)}
    matches = [candidate for candidate in candidates if normalize(candidate) in texts]
    return matches[0] if len(matches) == 1 and len(texts) == 1 else None
