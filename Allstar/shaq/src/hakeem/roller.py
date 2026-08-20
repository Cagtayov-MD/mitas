"""Satir ve blok baglamindan muhafazakar rol/entity cikarma."""
from __future__ import annotations

import re
from typing import Any

from src.normalizasyon import normalize
from src.roller import person_name as shaq_person_name
from src.roller import siniflandir


_HEADINGS = {
    "CAST": "CAST_KESIN", "STARRING": "CAST_KESIN", "OYUNCULAR": "CAST_KESIN",
    "OYUNCU": "CAST_KESIN", "DIRECTOR": "YONETMEN_KESIN",
    "DIRECTED BY": "YONETMEN_KESIN", "YONETMEN": "YONETMEN_KESIN",
    "YÖNETMEN": "YONETMEN_KESIN",
}


def heading_role(text: str) -> str | None:
    value = normalize(text)
    value = re.sub(r"\s+", " ", value).strip()
    return _HEADINGS.get(value)


def annotate(lines: list[dict[str, Any]], channel: str) -> list[dict[str, Any]]:
    """Rol basligini ayni bloktaki/cok yakin izleyen ada kontrollu yayar."""
    ordered = sorted(lines, key=lambda line: (line["order"], line["line_id"]))
    block_roles: dict[str, set[str]] = {}
    for line in ordered:
        block = str(line.get("block_id", ""))
        role = heading_role(line.get("role_hint", "")) or heading_role(line["text"])
        if block and role:
            block_roles.setdefault(block, set()).add(role)
    result: list[dict[str, Any]] = []
    active_role: str | None = None
    active_order: int | None = None
    for line in ordered:
        value = dict(line)
        explicit = siniflandir(value)
        header = heading_role(value.get("role_hint", "")) or heading_role(value["text"])
        block = str(value.get("block_id", ""))
        block_values = block_roles.get(block, set()) if block else set()
        if header:
            role = header
            active_role, active_order = header, value["order"]
        elif len(block_values) == 1:
            role = next(iter(block_values))
        elif explicit != "ROL_BELIRSIZ":
            role = explicit
            if role in ("CAST_KESIN", "YONETMEN_KESIN"):
                active_role, active_order = role, value["order"]
        elif active_role and active_order is not None and value["order"] == active_order + 1:
            role = active_role
            # Blok kimligi yoksa basligi yalniz hemen sonraki tek satira yay.
            # Bir sonraki rol basligina kadar korlemesine CAST yaymak daha riskli.
            active_role = active_order = None
        else:
            role = "ROL_BELIRSIZ"
            active_role = active_order = None
        value.update({"channel": channel, "normalized": normalize(value["text"]),
                      "resolved_role": role, "is_role_heading": bool(header)})
        result.append(value)
    return result


def entity_text(line: dict[str, Any], role: str) -> str | None:
    if role not in ("CAST_KESIN", "YONETMEN_KESIN") or line.get("is_role_heading"):
        return None
    extracted = shaq_person_name(line, role)
    if extracted:
        return extracted
    # Rol bloktan/role_hint'ten geldiyse ekrandaki yalın satirin tamami isimdir.
    if line.get("resolved_role") == role:
        return str(line.get("text", "")).strip() or None
    return None


def group_role(lines: list[dict[str, Any]]) -> str:
    roles = {line.get("resolved_role", "ROL_BELIRSIZ") for line in lines}
    concrete = roles - {"ROL_BELIRSIZ"}
    return next(iter(concrete)) if len(concrete) == 1 else "ROL_BELIRSIZ"
