#!/usr/bin/env python3
"""Shaq CLI — iki kaynak-bağımsız okuma paketini uzlaştırır."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

KULE = Path(__file__).resolve().parent
sys.path.insert(0, str(KULE))

from sozlesme import DURUMLAR, SozlesmeHatasi, atomic_json, oku, utc_now  # noqa: E402
from src.karar import Karar, reconcile  # noqa: E402
from src.kimlik import BosKimlikSaglayici  # noqa: E402
from src.kontrol import read_answers  # noqa: E402
from src.normalizasyon import normalize  # noqa: E402
from src.roller import person_name  # noqa: E402

OUT = KULE / "out"


def _config() -> dict[str, Any]:
    try:
        import yaml
        return yaml.safe_load((KULE / "config.yaml").read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise RuntimeError(f"config okunamadi: {type(exc).__name__}: {exc}") from exc


class JsonKimlikSaglayici:
    """İsteğe bağlı, salt-okunur yerel film-ID → kredi listesi adaptörü.

    Ağ aramaz, başlıkla tahmin yapmaz. Biçim: {"tt123": {"CAST_KESIN": ["Ad"]}}.
    """
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.version = f"local-json:{self.path.name}"

    def candidates(self, external_ids: dict[str, str], role: str) -> list[str]:
        found: list[str] = []
        for external_id in external_ids.values():
            item = self.data.get(external_id, {})
            found.extend(item.get(role, []))
        return list(dict.fromkeys(x for x in found if isinstance(x, str)))


def _provider(path: str | None):
    return JsonKimlikSaglayici(path) if path else BosKimlikSaglayici()


def _output_dir(film_id: str, bolum: str) -> Path:
    return OUT / film_id / bolum


def _remove_marker(target: Path) -> None:
    (target / "_TAMAM").unlink(missing_ok=True)


def _packet_files(film_dir: Path, bolum: str) -> list[Path]:
    paths = sorted((film_dir / bolum).glob("*.okuma.json"))
    if len(paths) != 2:
        raise SozlesmeHatasi(f"{film_dir / bolum}: V1 tam iki *.okuma.json ister (bulunan={len(paths)})")
    return paths


def _same_film(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """İki kanal aynı filmin aynı metadata künyesini taşımalıdır."""
    return left.get("film") == right.get("film")


def _asset(packet: dict[str, Any], asset_id: str) -> dict[str, Any]:
    return next(asset for asset in packet["assets"] if asset["asset_id"] == asset_id)


def _crop_requests(decision: Karar, packet_a: dict[str, Any], packet_b: dict[str, Any], target: Path,
                   *, min_pad_px: int = 20) -> None:
    if not decision.requests:
        return
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - kurulum hatası
        raise RuntimeError("crop icin Pillow gerekli") from exc
    crops = target / "kontrol" / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    for request in decision.requests:
        bbox = request["bbox"]
        source = Path(request.pop("_source_path"))
        tight = crops / f"{request['request_id']}.png"
        context = crops / f"{request['request_id']}.context.png"
        # ``copy`` kendi out alanına yazar; kaynak asset değişmeden kalır.
        with Image.open(source) as image:
            pad_x = max(min_pad_px, (bbox["x1"] - bbox["x0"]) // 2)
            pad_y = max(min_pad_px, (bbox["y1"] - bbox["y0"]) * 2)
            cb = (max(0, bbox["x0"] - pad_x), max(0, bbox["y0"] - pad_y),
                  min(image.width, bbox["x1"] + pad_x), min(image.height, bbox["y1"] + pad_y))
            image.crop((bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"])).save(tight)
            image.crop(cb).save(context)
        request["crop"] = str(tight.relative_to(target))
        request["context_crop"] = str(context.relative_to(target))


def _serialize(film_id: str, bolum: str, packets: list[dict[str, Any]], decision: Karar,
               provider_version: str) -> dict[str, Any]:
    out: dict[str, Any] = {"schema_version": "mitas.shaq/v1", "film_id": film_id, "bolum": bolum,
                           "durum": decision.durum, "uretim_zamani": utc_now(),
                           "channels": [{"producer_id": p["producer"]["id"], "engine_family": p["producer"]["engine_family"],
                                         "model_digest": p["producer"]["model_digest"], "source": str(p.get("_source", ""))}
                                        for p in packets],
                           "kimlik_saglayici": provider_version, "records": decision.records}
    if decision.ariza:
        out["ariza"] = decision.ariza
    return out


def _write(target: Path, output: dict[str, Any], decision: Karar) -> Path:
    _remove_marker(target)
    # Önce karar ve kontrol istekleri yazılır, marker her zaman en son gelir.
    atomic_json(target / "shaq.json", output)
    request_path = target / "kontrol" / "istekler.jsonl"
    if decision.requests:
        request_path.parent.mkdir(parents=True, exist_ok=True)
        temp = request_path.with_suffix(".jsonl.tmp")
        temp.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in decision.requests), encoding="utf-8")
        os.replace(temp, request_path)
    else:
        request_path.unlink(missing_ok=True)
    text_path = target / "shaq.txt"
    if decision.durum == "GECTI":
        passed = [record["accepted_text"] for record in decision.records if record.get("accepted_text")]
        temp = text_path.with_suffix(".txt.tmp")
        temp.write_text("\n".join(passed) + ("\n" if passed else ""), encoding="utf-8")
        os.replace(temp, text_path)
    else:
        text_path.unlink(missing_ok=True)
    (target / "_TAMAM").write_text("", encoding="utf-8")
    return target / "shaq.json"


def tek(film_dir: str | Path, film_id: str, bolum: str, kimlik_json: str | None = None) -> Path:
    film_dir = Path(film_dir)
    target = _output_dir(film_id, bolum)
    _remove_marker(target)
    try:
        paths = _packet_files(film_dir, bolum)
        packets = [oku(path) for path in paths]
        if any(p.film_id != film_id or p.bolum != bolum for p in packets):
            raise SozlesmeHatasi("CLI film_id/bolum paketle uyusmuyor")
        if not _same_film(packets[0].raw, packets[1].raw):
            raise SozlesmeHatasi("iki kanal film metadata/external_ids olarak uyusmuyor")
        if packets[0].producer_id == packets[1].producer_id:
            raise SozlesmeHatasi("iki kanal ayni producer.id olamaz")
        raw = []
        for packet in packets:
            value = json.loads(json.dumps(packet.raw))
            value["_source"] = str(packet.path)
            for line in value.get("lines", []):
                for evidence in line.get("evidence", []):
                    evidence["_source_path"] = next(asset["path"] for asset in value["assets"]
                                                      if asset["asset_id"] == evidence["asset_id"])
            for evidence in value.get("unread_regions", []):
                evidence["_source_path"] = next(asset["path"] for asset in value["assets"]
                                                  if asset["asset_id"] == evidence["asset_id"])
            raw.append(value)
        config = _config()
        max_edits = int(config.get("hizalama", {}).get("max_edit", 3))
        min_pad_px = int(config.get("kontrol", {}).get("context_min_pad_px", 20))
        if max_edits < 0 or min_pad_px < 0:
            raise RuntimeError("config esikleri negatif olamaz")
        provider = _provider(kimlik_json)
        decision = reconcile(raw[0], raw[1], provider=provider, max_edits=max_edits)
        _crop_requests(decision, raw[0], raw[1], target, min_pad_px=min_pad_px)
        output = _serialize(film_id, bolum, raw, decision, provider.version)
    except Exception as exc:
        decision = Karar("ARIZA", ariza={"sinif": "GIRDI_VEYA_KULE", "mesaj": f"{type(exc).__name__}: {exc}"})
        output = _serialize(film_id, bolum, [], decision, "none")
    return _write(target, output, decision)


def tamamla(film_id: str, bolum: str, answers_path: str | Path) -> Path:
    """Bekleyen kör istekleri yanıtlarla kapatır; OCR adaylarına fuzzy uygulanmaz."""
    target = _output_dir(film_id, bolum)
    _remove_marker(target)
    existing = json.loads((target / "shaq.json").read_text(encoding="utf-8"))
    answers = read_answers(answers_path)
    records = existing.get("records", [])
    request_path = target / "kontrol" / "istekler.jsonl"
    queued: dict[str, dict[str, Any]] = {}
    if request_path.exists():
        for raw in request_path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                value = json.loads(raw)
                queued[value["request_id"]] = value
    failed = False
    for record in records:
        ids = record.get("control_request_ids", [])
        if not ids:
            continue
        saved = record.setdefault("control_answers", {})
        # Kısmi cevaplar karar dosyasında kalıcıdır; sonraki çağrı yalnız eksik
        # istekleri bekler. Aynı request_id için ilk kanıt sabittir.
        for request_id in ids:
            if request_id in answers and request_id not in saved:
                saved[request_id] = answers[request_id]
        supplied = [saved[x] for x in ids if x in saved]
        if any(value.get("durum") == "ARIZA" for value in supplied):
            record["decision"] = "KONTROL_ARIZASI"; failed = True; continue
        if len(supplied) < len(ids):
            record["decision"] = "KONTROL_GEREKLI"; continue
        candidates = record.get("kontrol_adaylari") or [r["text"] for r in record.get("ekranda_okunan", [])]
        if record.get("canonical_name") and record["canonical_name"] not in candidates:
            candidates.append(record["canonical_name"])
        normalized_texts = {normalize(value.get("text", "")) for value in supplied if value.get("durum") == "OKUNDU"}
        matching = [c for c in candidates if normalize(c) in normalized_texts]
        if len(set(normalize(x) for x in matching)) == 1 and len(normalized_texts) == 1:
            visual = next((r["text"] for r in record.get("ekranda_okunan", [])
                           if (normalize(r["text"]) == normalize(matching[0]) or
                               normalize(person_name({"text": r["text"]}, record.get("role", "")) or "")
                               == normalize(matching[0]))), None)
            record["decision"], record["accepted_text"] = "KONTROL_TEYITLI", (visual or record["ekranda_okunan"][0]["text"])
        else:
            record["decision"] = "COZUMSUZ"
    existing["uretim_zamani"] = utc_now()
    decisions = {record.get("decision") for record in records}
    if failed or "KONTROL_ARIZASI" in decisions:
        existing["durum"] = "ARIZA"
    elif "KONTROL_GEREKLI" in decisions:
        existing["durum"] = "KONTROL_BEKLIYOR"
    elif "COZUMSUZ" in decisions:
        existing["durum"] = "COZUMSUZ"
    else:
        existing["durum"] = "GECTI"
    pending_requests = [queued[x] for record in records if record.get("decision") == "KONTROL_GEREKLI"
                        for x in record.get("control_request_ids", []) if x not in record.get("control_answers", {}) and x in queued]
    decision = Karar(existing["durum"], records, pending_requests)
    if failed:
        existing["ariza"] = {"sinif": "KONTROL_MOTORU", "mesaj": "kontrol cevabi ARIZA"}
    return _write(target, existing, decision)


def start(input_root: str | Path, bolumler: str, kimlik_json: str | None = None) -> int:
    root = Path(input_root)
    count = 0
    for film_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        for bolum in [x.strip() for x in bolumler.split(",") if x.strip()]:
            if (film_dir / bolum).is_dir():
                tek(film_dir, film_dir.name, bolum, kimlik_json); count += 1
    return count


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest="command", required=True)
    one = subs.add_parser("tek"); one.add_argument("--film-dir", required=True); one.add_argument("--film-id", required=True)
    one.add_argument("--bolum", choices=("giris", "cikis"), default="cikis"); one.add_argument("--kimlik-json")
    many = subs.add_parser("start"); many.add_argument("--input", required=True); many.add_argument("--bolum", default="giris,cikis")
    many.add_argument("--kimlik-json")
    done = subs.add_parser("tamamla"); done.add_argument("--film-id", required=True); done.add_argument("--bolum", choices=("giris", "cikis"), default="cikis")
    done.add_argument("--cevaplar", required=True)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "tek":
        print(tek(args.film_dir, args.film_id, args.bolum, args.kimlik_json)); return 0
    if args.command == "start":
        print(start(args.input, args.bolum, args.kimlik_json)); return 0
    print(tamamla(args.film_id, args.bolum, args.cevaplar)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
