"""Deterministik, kanita bagli ve tekrar oynatmaya dayanikli kontrol sozlesmesi."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.normalizasyon import normalize


REQUEST_SCHEMA = "mitas.kontrol/v2"
ANSWER_SCHEMA = "mitas.kontrol.cevap/v2"


class KontrolHatasi(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def stable_id(prefix: str, value: Any, length: int = 24) -> str:
    return f"{prefix}-" + hashlib.sha256(_canonical(value)).hexdigest()[:length]


def request_for(*, film_id: str, bolum: str, run_id: str, group_id: str,
                observation: dict[str, Any], evidence_index: int,
                evidence: dict[str, Any], role: str) -> dict[str, Any]:
    """Aday metni disari sizdirmadan goruntuyu ve kaynagini kriptografik baglar."""
    identity = {
        "film_id": film_id, "bolum": bolum, "run_id": run_id,
        "group_id": group_id, "channel": observation["channel"],
        "producer_id": observation["producer_id"], "line_id": observation["line_id"],
        "evidence_index": evidence_index, "asset_id": evidence["asset_id"],
        "asset_sha256": evidence["_asset_sha256"], "bbox": evidence["bbox"],
    }
    request_id = stable_id("hk-req", identity)
    request = {
        "schema_version": REQUEST_SCHEMA,
        "task": "TRANSCRIBE_VISIBLE_TEXT_EXACTLY",
        "instruction_version": "hakeem-blind-read/v1",
        "request_id": request_id,
        **identity,
        "view_id": stable_id("hk-view", identity),
        "role": role,
        "crop": None,
        "context_crop": None,
        "crop_sha256": None,
        "context_crop_sha256": None,
    }
    request["request_digest"] = stable_id("sha256", identity, 64)
    request["_source_path"] = evidence["_source_path"]
    return request


def finalize_request(request: dict[str, Any], *, crop: str, context_crop: str,
                     crop_sha256: str, context_crop_sha256: str) -> None:
    request["crop"] = crop
    request["context_crop"] = context_crop
    request["crop_sha256"] = crop_sha256
    request["context_crop_sha256"] = context_crop_sha256
    request.pop("_source_path", None)


def read_answers(path: str | Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_no, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            answer = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise KontrolHatasi(f"kontrol cevabi JSON degil, satir={line_no}: {exc}") from exc
        if not isinstance(answer, dict) or answer.get("schema_version") != ANSWER_SCHEMA:
            raise KontrolHatasi(f"kontrol cevabi schema_version {ANSWER_SCHEMA!r} olmali")
        for key in ("answer_id", "request_id", "request_digest", "crop_sha256", "uretim_zamani"):
            if not isinstance(answer.get(key), str) or not answer[key].strip():
                raise KontrolHatasi(f"kontrol cevabi {key} zorunlu metindir")
        if answer["answer_id"] in seen:
            raise KontrolHatasi(f"yinelenen answer_id: {answer['answer_id']}")
        seen.add(answer["answer_id"])
        if answer.get("durum") not in ("OKUNDU", "ARIZA"):
            raise KontrolHatasi("kontrol cevabi durum OKUNDU veya ARIZA olmali")
        producer = answer.get("producer")
        if not isinstance(producer, dict):
            raise KontrolHatasi("kontrol cevabi producer nesnesi zorunlu")
        for key in ("id", "engine_family", "model_digest", "prompt_digest", "independence_group"):
            if not isinstance(producer.get(key), str) or not producer[key].strip():
                raise KontrolHatasi(f"kontrol cevabi producer.{key} zorunlu metindir")
        if answer["durum"] == "OKUNDU":
            if not isinstance(answer.get("text"), str) or not normalize(answer["text"]):
                raise KontrolHatasi("OKUNDU kontrol cevabi bos olmayan text ister")
        elif answer.get("text") not in (None, ""):
            raise KontrolHatasi("ARIZA kontrol cevabi text tasiyamaz")
        result.append(answer)
    return result


def verify_answer(answer: dict[str, Any], request: dict[str, Any]) -> None:
    if answer["request_digest"] != request["request_digest"]:
        raise KontrolHatasi(f"request_digest uyusmuyor: {answer['request_id']}")
    if answer["crop_sha256"].lower() != str(request["crop_sha256"]).lower():
        raise KontrolHatasi(f"crop_sha256 uyusmuyor: {answer['request_id']}")


def merge_answers(group: dict[str, Any], answers: list[dict[str, Any]]) -> None:
    saved = group.setdefault("control_answers", {})
    for answer in answers:
        bucket = saved.setdefault(answer["request_id"], [])
        previous = next((old for old in bucket if old.get("answer_id") == answer["answer_id"]), None)
        if previous is not None and previous != answer:
            raise KontrolHatasi(f"answer_id farkli icerikle tekrar kullanildi: {answer['answer_id']}")
        if previous is None:
            bucket.append(answer)


def _hypothesis_matches(hypothesis: dict[str, Any], answer_texts: set[str]) -> bool:
    line_variants = [set(line["normalized_variants"]) for line in hypothesis.get("lines", [])]
    if not line_variants or not answer_texts:
        return False
    allowed = set().union(*line_variants)
    return answer_texts <= allowed and all(variants & answer_texts for variants in line_variants)


def resolve_group(group: dict[str, Any], *, min_novel_independent_answers: int = 2) -> None:
    ids = group.get("control_request_ids", [])
    saved = group.get("control_answers", {})
    if not ids:
        return
    if any(not saved.get(request_id) for request_id in ids):
        group["decision"] = "KONTROL_GEREKLI"
        return
    successful = [answer for request_id in ids for answer in saved[request_id]
                  if answer.get("durum") == "OKUNDU"]
    if any(not any(a.get("durum") == "OKUNDU" for a in saved[request_id]) for request_id in ids):
        group["decision"] = "KONTROL_ARIZASI"
        return
    answer_texts = {normalize(answer["text"]) for answer in successful}
    hypotheses = [hypothesis for hypothesis in group.get("hypotheses", []) if hypothesis.get("lines")]
    matching = [hypothesis for hypothesis in hypotheses if _hypothesis_matches(hypothesis, answer_texts)]
    signatures = {tuple(line["normalized"] for line in h["lines"]): h for h in matching}
    if len(signatures) == 1:
        selected = next(iter(signatures.values()))
        group["decision"] = "KONTROL_TEYITLI"
        group["accepted_lines"] = [line["text"] for line in selected["lines"]]
        group["selected_hypothesis_id"] = selected["hypothesis_id"]
        return
    if not hypotheses and len(answer_texts) == 1:
        groups = {answer["producer"]["independence_group"] for answer in successful}
        models = {answer["producer"]["model_digest"] for answer in successful}
        producers = {answer["producer"]["id"] for answer in successful}
        independent = min(len(groups), len(models), len(producers))
        if independent >= min_novel_independent_answers:
            group["decision"] = "KONTROL_YENI_IKI_KANAL_TEYITLI"
            group["accepted_lines"] = [successful[0]["text"].strip()]
            return
        group["decision"] = "KONTROL_GEREKLI"
        group["needed_independent_answers"] = min_novel_independent_answers - independent
        return
    group["decision"] = "COZUMSUZ"
