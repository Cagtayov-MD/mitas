"""Shaq'ın saf karar motoru. Dosya, Pillow ve CLI bilmez."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .hizalama import Eslesme, hizala
from .kimlik import BosKimlikSaglayici, KimlikSaglayici, strong_canonical
from .kontrol import exact_answer, request_for
from .normalizasyon import normalize
from .roller import person_name, siniflandir


@dataclass
class Karar:
    durum: str
    records: list[dict[str, Any]] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)
    ariza: dict[str, str] | None = None


def _candidate_texts(pair: Eslesme, canonical: str | None, role: str) -> list[str]:
    values = [x["text"] for x in (pair.a, pair.b) if x]
    values.extend(name for name in (person_name(pair.a, role), person_name(pair.b, role)) if name)
    if canonical:
        values.append(canonical)
    return list(dict.fromkeys(values))


def _record(pair: Eslesme, role: str, status: str, accepted: str | None = None,
            canonical: str | None = None, request_ids: list[str] | None = None) -> dict[str, Any]:
    evidence = []
    readings = []
    for side, line in (("a", pair.a), ("b", pair.b)):
        if line:
            readings.append({"channel": side, "line_id": line["line_id"], "text": line["text"], "order": line["order"]})
            evidence.extend({"channel": side, "line_id": line["line_id"],
                             **{k: v for k, v in ev.items() if k != "_source_path"}}
                            for ev in line["evidence"])
    return {"record_id": f"{readings[0]['channel'] if readings else 'x'}-{readings[0]['line_id'] if readings else 'none'}",
            "role": role, "hizalama": pair.sinif, "decision": status,
            "ekranda_okunan": readings, "accepted_text": accepted,
            "canonical_name": canonical, "evidence": evidence,
            "kontrol_adaylari": _candidate_texts(pair, canonical, role),
            "control_request_ids": request_ids or [], "control_answers": {}}


def _visual_for_name(pair: Eslesme, role: str, name: str) -> str:
    """Kanonik isim ayrı tutulur; kabul edilen OCR satırı tam görsel satırdır."""
    for line in (pair.a, pair.b):
        if line and normalize(person_name(line, role) or "") == normalize(name):
            return line["text"]
    return next(line["text"] for line in (pair.a, pair.b) if line)


def _needs_control(pair: Eslesme) -> bool:
    return pair.sinif in ("YAKIN", "UZAK_ANCHOR", "A_ONLY", "B_ONLY")


def reconcile(a: dict[str, Any], b: dict[str, Any], *, provider: KimlikSaglayici | None = None,
              answers: dict[str, dict[str, Any]] | None = None, max_edits: int = 3) -> Karar:
    """İki geçerli paketi uzlaştırır. Kontrol yokken riskli her top bloklanır."""
    provider = provider or BosKimlikSaglayici()
    answers = answers or {}
    if a["durum"] == b["durum"] == "METIN_YOK" and not a.get("unread_regions") and not b.get("unread_regions"):
        return Karar("METIN_YOK")
    if a["durum"] == "ARIZA" and b["durum"] == "ARIZA":
        return Karar("ARIZA", ariza={"sinif": "IKI_KANAL_ARIZASI", "mesaj": "iki okuma kanali da ARIZA"})
    def all_lines(packet: dict[str, Any], channel: str) -> list[dict[str, Any]]:
        rows = list(packet.get("lines", []))
        rows.extend({"line_id": f"__unread_{channel}_{n}", "text": "", "order": 10_000 + n,
                     "evidence": [ev], "role_hint": ""}
                    for n, ev in enumerate(packet.get("unread_regions", [])))
        return rows
    pairs = hizala(all_lines(a, "a"), all_lines(b, "b"), max_edits=max_edits)
    records: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    external_ids = a["film"].get("external_ids", {})
    for pair in pairs:
        role = siniflandir(pair.a, pair.b)
        texts = _candidate_texts(pair, None, role)
        canonical = strong_canonical(provider, external_ids, role, texts)
        # Eş okuma, dış veri yokluğu dahil, doğrudan geçer.
        if pair.sinif == "ES":
            accepted = pair.a["text"]
            records.append(_record(pair, role, "IKI_KANAL_TEYITLI", accepted, canonical))
            continue
        # Güçlü film kapsamlı KB yalnız exact OCR adayını kanonikleştirir.
        if pair.sinif == "YAKIN" and canonical:
            records.append(_record(pair, role, "KB_KANONIK_TEYITLI", _visual_for_name(pair, role, canonical), canonical))
            continue
        evidence_lines = [line for line in (pair.a, pair.b) if line]
        request_ids: list[str] = []
        for line in evidence_lines:
            req = request_for(a["film"]["id"], a["bolum"], line["evidence"][0], role)
            request_ids.append(req["request_id"])
            requests.append(req)
        # ``tamamla`` çağrısı istek kimliklerini records'tan bulup yanıtlar.
        rec = _record(pair, role, "KONTROL_GEREKLI", None, canonical, request_ids)
        supplied = [answers[rid] for rid in request_ids if rid in answers]
        if supplied:
            if any(value.get("durum") == "ARIZA" for value in supplied):
                rec["decision"] = "KONTROL_ARIZASI"
            elif len(supplied) == len(request_ids):
                accepted = exact_answer(supplied, _candidate_texts(pair, canonical, role))
                if accepted:
                    rec["decision"], rec["accepted_text"] = "KONTROL_TEYITLI", accepted
                else:
                    rec["decision"] = "COZUMSUZ"
        records.append(rec)
    if any(r["decision"] == "KONTROL_ARIZASI" for r in records):
        return Karar("ARIZA", records, requests, {"sinif": "KONTROL_MOTORU", "mesaj": "kontrol cevabi ARIZA"})
    if any(r["decision"] == "KONTROL_GEREKLI" for r in records):
        return Karar("KONTROL_BEKLIYOR", records, requests)
    if any(r["decision"] == "COZUMSUZ" for r in records):
        return Karar("COZUMSUZ", records, requests)
    return Karar("GECTI", records, requests)
