"""HAKEEM saf karar motoru: gozlem -> conflict group -> kanitli karar."""
from __future__ import annotations

from typing import Any

from src.hakeem.hizalama import hizala
from src.hakeem.kontrol import request_for, stable_id
from src.hakeem.roller import annotate, entity_text, group_role
from src.kimlik import BosKimlikSaglayici, KimlikSaglayici
from src.normalizasyon import normalize


def _observations(raw: dict[str, Any], channel: str) -> list[dict[str, Any]]:
    asset_map = {asset["asset_id"]: asset for asset in raw.get("assets", [])}
    lines: list[dict[str, Any]] = []
    for source in raw.get("lines", []):
        line = dict(source)
        enriched = []
        for evidence in source["evidence"]:
            asset = asset_map[evidence["asset_id"]]
            enriched.append({**evidence, "_source_path": asset["path"],
                             "_asset_sha256": asset["sha256"],
                             "_asset_width": asset["width"],
                             "_asset_height": asset["height"]})
        line["evidence"] = enriched
        line["producer_id"] = raw["producer"]["id"]
        lines.append(line)
    annotated = annotate(lines, channel)
    last_order = max((line["order"] for line in annotated), default=0)
    for index, evidence in enumerate(raw.get("unread_regions", []), 1):
        asset = asset_map[evidence["asset_id"]]
        annotated.append({
            "line_id": f"__unread_{channel}_{index}", "order": last_order + index,
            "text": "", "normalized": "", "role_hint": "", "resolved_role": "ROL_BELIRSIZ",
            "is_role_heading": False, "channel": channel,
            "producer_id": raw["producer"]["id"],
            "evidence": [{**evidence, "_source_path": asset["path"],
                          "_asset_sha256": asset["sha256"],
                          "_asset_width": asset["width"],
                          "_asset_height": asset["height"]}],
        })
    return annotated


def _public_observation(line: dict[str, Any]) -> dict[str, Any]:
    evidence = [{k: value for k, value in item.items() if not k.startswith("_")}
                for item in line.get("evidence", [])]
    result = {"channel": line["channel"], "producer_id": line["producer_id"],
              "line_id": line["line_id"], "order": line["order"], "text": line["text"],
              "normalized": line["normalized"], "role": line.get("resolved_role", "ROL_BELIRSIZ"),
              "evidence": evidence}
    for optional in ("block_id", "page_id"):
        if optional in line:
            result[optional] = line[optional]
    return result


def _hypothesis(channel: str, lines: list[dict[str, Any]], role: str, group_id: str) -> dict[str, Any] | None:
    content = [line for line in lines if line.get("normalized")]
    if not content:
        return None
    serialized = []
    for line in content:
        variants = {line["normalized"]}
        entity = entity_text(line, role)
        if entity:
            variants.add(normalize(entity))
        serialized.append({"line_id": line["line_id"], "text": line["text"],
                           "normalized": line["normalized"],
                           "normalized_variants": sorted(variants)})
    signature = [line["normalized"] for line in serialized]
    return {"hypothesis_id": stable_id("hk-hyp", {"group": group_id, "signature": signature}),
            "source_channel": channel, "lines": serialized}


def _canonical(provider: KimlikSaglayici, external_ids: dict[str, str], role: str,
               raw_lines: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    if role not in ("CAST_KESIN", "YONETMEN_KESIN") or not external_ids:
        return None, None
    try:
        candidates = provider.candidates(external_ids, role)
    except Exception:
        return None, None
    observed = [(line, entity_text(line, role)) for line in raw_lines]
    hits: list[tuple[str, dict[str, Any]]] = []
    for candidate in candidates:
        for line, entity in observed:
            if entity and normalize(candidate) == normalize(entity):
                hits.append((candidate, line))
    unique = {(normalize(candidate), line["channel"], line["line_id"]): (candidate, line)
              for candidate, line in hits}
    names = {key[0] for key in unique}
    if len(names) != 1:
        return None, None
    candidate, line = next(iter(unique.values()))
    return candidate, line["channel"]


def decide(*, film_id: str, bolum: str, run_id: str, raw_a: dict[str, Any], raw_b: dict[str, Any],
           provider: KimlikSaglayici | None = None, max_edits: int = 3) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    provider = provider or BosKimlikSaglayici()
    if raw_a["durum"] == raw_b["durum"] == "METIN_YOK" and not raw_a.get("unread_regions") and not raw_b.get("unread_regions"):
        return "METIN_YOK", [], [], None
    lines_a, lines_b = _observations(raw_a, "a"), _observations(raw_b, "b")
    if not lines_a and not lines_b:
        statuses = {raw_a["durum"], raw_b["durum"]}
        reason = "en az bir kanal ARIZA ve karar verecek gozlem yok" if "ARIZA" in statuses else "karar verecek gozlem yok"
        return "ARIZA", [], [], {"sinif": "BOS_VEYA_ARIZALI_GIRDI", "mesaj": reason}
    proto_groups = hizala(lines_a, lines_b, max_edits=max_edits)
    groups: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    external_ids = raw_a["film"].get("external_ids", {})
    for index, proto in enumerate(proto_groups):
        raw_lines = proto["a"] + proto["b"]
        identity = {"run_id": run_id, "index": index, "kind": proto["kind"],
                    "observations": [(line["channel"], line["line_id"]) for line in raw_lines]}
        group_id = stable_id("hk-grp", identity)
        role = group_role(raw_lines)
        hypotheses = [value for value in (
            _hypothesis("a", proto["a"], role, group_id),
            _hypothesis("b", proto["b"], role, group_id)) if value]
        # Es hipotezleri tek secenege indir; kanal sayisi gozlemlerde zaten korunur.
        distinct: dict[tuple[str, ...], dict[str, Any]] = {}
        for hypothesis in hypotheses:
            signature = tuple(line["normalized"] for line in hypothesis["lines"])
            distinct.setdefault(signature, hypothesis)
        hypotheses = list(distinct.values())
        group: dict[str, Any] = {
            "group_id": group_id, "kind": proto["kind"], "role": role,
            "observations": [_public_observation(line) for line in raw_lines],
            "hypotheses": hypotheses, "decision": "KONTROL_GEREKLI",
            "accepted_lines": [], "canonical_entities": [],
            "control_request_ids": [], "control_answers": {},
        }
        if proto["kind"] == "CONSENSUS":
            group["decision"] = "IKI_BAGIMSIZ_KANAL_TEYITLI"
            group["accepted_lines"] = [proto["a"][0]["text"]]
            canonical, _ = _canonical(provider, external_ids, role, raw_lines)
            if canonical:
                group["canonical_entities"] = [{"role": role, "canonical_name": canonical,
                                                  "source": getattr(provider, "version", "unknown")}]
        elif proto["kind"] == "NEAR_CONFLICT":
            canonical, selected_channel = _canonical(provider, external_ids, role, raw_lines)
            if canonical and selected_channel:
                selected = next((hypothesis for hypothesis in hypotheses
                                 if hypothesis["source_channel"] == selected_channel), None)
                if selected:
                    group["decision"] = "FILM_KAPSAMLI_KIMLIK_TEYITLI"
                    group["accepted_lines"] = [line["text"] for line in selected["lines"]]
                    group["selected_hypothesis_id"] = selected["hypothesis_id"]
                    group["canonical_entities"] = [{"role": role, "canonical_name": canonical,
                                                      "source": getattr(provider, "version", "unknown")}]
        if group["decision"] == "KONTROL_GEREKLI":
            for line in raw_lines:
                for evidence_index, evidence in enumerate(line.get("evidence", [])):
                    request = request_for(film_id=film_id, bolum=bolum, run_id=run_id,
                                          group_id=group_id, observation=line,
                                          evidence_index=evidence_index, evidence=evidence, role=role)
                    group["control_request_ids"].append(request["request_id"])
                    requests.append(request)
        groups.append(group)
    decisions = {group["decision"] for group in groups}
    if "KONTROL_GEREKLI" in decisions:
        status = "KONTROL_BEKLIYOR"
    elif "COZUMSUZ" in decisions:
        status = "COZUMSUZ"
    elif "KONTROL_ARIZASI" in decisions:
        status = "ARIZA"
    else:
        status = "GECTI"
    return status, groups, requests, None


def accepted_text(groups: list[dict[str, Any]]) -> list[str]:
    return [text for group in groups for text in group.get("accepted_lines", []) if text]


def aggregate_status(groups: list[dict[str, Any]]) -> str:
    decisions = {group.get("decision") for group in groups}
    if "KONTROL_ARIZASI" in decisions:
        return "ARIZA"
    if "KONTROL_GEREKLI" in decisions:
        return "KONTROL_BEKLIYOR"
    if "COZUMSUZ" in decisions:
        return "COZUMSUZ"
    return "GECTI"
