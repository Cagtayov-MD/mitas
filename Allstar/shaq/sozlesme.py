"""Shaq'ın kaynak-bağımsız dış sözleşmesi.

Bu modül başka kuleleri import etmez. ``mitas.okuma/v1`` paketlerini doğrular
ve Shaq sonucunu atomik olarak yazar.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "mitas.okuma/v1"
BOLUMLER = ("giris", "cikis")
PAKET_DURUMLARI = ("OKUNDU", "METIN_YOK", "ARIZA")
DURUMLAR = ("GECTI", "METIN_YOK", "KONTROL_BEKLIYOR", "COZUMSUZ", "ARIZA")


class SozlesmeHatasi(ValueError):
    """Çağıranın verdiği paket sözleşmeye uymuyor."""


def normalize_bbox(value: Any, asset: dict[str, Any]) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != {"x0", "y0", "x1", "y1"}:
        raise SozlesmeHatasi("bbox tam olarak x0,y0,x1,y1 tasimali")
    try:
        bbox = {k: int(value[k]) for k in ("x0", "y0", "x1", "y1")}
    except (TypeError, ValueError) as exc:
        raise SozlesmeHatasi("bbox tamsayi olmali") from exc
    if not (0 <= bbox["x0"] < bbox["x1"] <= asset["width"] and
            0 <= bbox["y0"] < bbox["y1"] <= asset["height"]):
        raise SozlesmeHatasi(f"bbox asset sinirlari disinda: {bbox}")
    return bbox


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class OkumaPaketi:
    raw: dict[str, Any]
    path: Path

    @property
    def film_id(self) -> str:
        return self.raw["film"]["id"]

    @property
    def bolum(self) -> str:
        return self.raw["bolum"]

    @property
    def producer_id(self) -> str:
        return self.raw["producer"]["id"]

    @property
    def durum(self) -> str:
        return self.raw["durum"]

    @property
    def lines(self) -> list[dict[str, Any]]:
        return self.raw.get("lines", [])


def _must_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SozlesmeHatasi(f"{name} nesne olmali")
    return value


def validate_packet(raw: Any, path: Path) -> OkumaPaketi:
    raw = _must_dict(raw, "paket")
    if raw.get("schema_version") != SCHEMA:
        raise SozlesmeHatasi(f"schema_version {SCHEMA!r} olmali")
    film = _must_dict(raw.get("film"), "film")
    if not isinstance(film.get("id"), str) or not film["id"].strip():
        raise SozlesmeHatasi("film.id bos olamaz")
    external_ids = film.get("external_ids", {})
    if not isinstance(external_ids, dict):
        raise SozlesmeHatasi("film.external_ids nesne olmali")
    if raw.get("bolum") not in BOLUMLER:
        raise SozlesmeHatasi(f"gecersiz bolum: {raw.get('bolum')!r}")
    producer = _must_dict(raw.get("producer"), "producer")
    for key in ("id", "engine_family", "model_digest"):
        if not isinstance(producer.get(key), str) or not producer[key].strip():
            raise SozlesmeHatasi(f"producer.{key} zorunlu metindir")
    if raw.get("durum") not in PAKET_DURUMLARI:
        raise SozlesmeHatasi("durum OKUNDU, METIN_YOK veya ARIZA olmali")
    assets = raw.get("assets")
    if not isinstance(assets, list):
        raise SozlesmeHatasi("assets liste olmali")
    asset_map: dict[str, dict[str, Any]] = {}
    for asset in assets:
        asset = _must_dict(asset, "asset")
        aid = asset.get("asset_id")
        if not isinstance(aid, str) or not aid or aid in asset_map:
            raise SozlesmeHatasi("asset_id benzersiz zorunlu metindir")
        if not isinstance(asset.get("path"), str) or not asset["path"]:
            raise SozlesmeHatasi("asset.path zorunlu")
        if not isinstance(asset.get("width"), int) or not isinstance(asset.get("height"), int):
            raise SozlesmeHatasi("asset width/height tamsayi olmali")
        if asset["width"] <= 0 or asset["height"] <= 0:
            raise SozlesmeHatasi("asset width/height pozitif olmali")
        checksum = asset.get("sha256")
        if not isinstance(checksum, str) or len(checksum) != 64:
            raise SozlesmeHatasi("asset.sha256 64 karakter zorunludur")
        asset_map[aid] = asset
    lines = raw.get("lines", [])
    if not isinstance(lines, list):
        raise SozlesmeHatasi("lines liste olmali")
    if raw["durum"] != "OKUNDU" and lines:
        raise SozlesmeHatasi("OKUNDU olmayan paket satir tasiyamaz")
    seen_ids: set[str] = set()
    for line in lines:
        line = _must_dict(line, "line")
        lid, text, order = line.get("line_id"), line.get("text"), line.get("order")
        if not isinstance(lid, str) or not lid or lid in seen_ids:
            raise SozlesmeHatasi("line_id benzersiz zorunlu metindir")
        seen_ids.add(lid)
        if not isinstance(text, str) or not text.strip():
            raise SozlesmeHatasi("OKUNDU line.text bos olamaz")
        if not isinstance(order, int):
            raise SozlesmeHatasi("line.order tamsayi olmali")
        evidence = line.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise SozlesmeHatasi("OKUNDU satiri en az bir bbox kaniti tasimali")
        for ev in evidence:
            ev = _must_dict(ev, "evidence")
            aid = ev.get("asset_id")
            if aid not in asset_map:
                raise SozlesmeHatasi("evidence bilinmeyen asset_id kullaniyor")
            normalize_bbox(ev.get("bbox"), asset_map[aid])
    # OCR'nin metin veremediği ama dedektörün gördüğü alanlar içerik boşluğu
    # değildir. Bunlar kör kontrol kuyruğuna taşınır; ``lines`` değillerdir.
    unread = raw.get("unread_regions", [])
    if not isinstance(unread, list):
        raise SozlesmeHatasi("unread_regions liste olmali")
    for ev in unread:
        ev = _must_dict(ev, "unread_region")
        aid = ev.get("asset_id")
        if aid not in asset_map:
            raise SozlesmeHatasi("unread_region bilinmeyen asset_id kullaniyor")
        normalize_bbox(ev.get("bbox"), asset_map[aid])
    return OkumaPaketi(raw=raw, path=path)


def oku(path: str | Path, *, verify_assets: bool = True) -> OkumaPaketi:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        # Paket taşınabilir olabilir; göreli asset yolu paketin bulunduğu dizine
        # göre çözülür. Sonraki crop adımları da bu mutlak, salt-okunur yolu görür.
        if isinstance(raw, dict) and isinstance(raw.get("assets"), list):
            for asset in raw["assets"]:
                if isinstance(asset, dict) and isinstance(asset.get("path"), str):
                    source = Path(asset["path"])
                    if not source.is_absolute():
                        asset["path"] = str((path.parent / source).resolve())
        packet = validate_packet(raw, path)
    except OSError as exc:
        raise SozlesmeHatasi(f"paket okunamadi: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SozlesmeHatasi(f"paket JSON degil: {path}: {exc}") from exc
    if verify_assets:
        for asset in packet.raw["assets"]:
            source = Path(asset["path"])
            if not source.is_file():
                raise SozlesmeHatasi(f"asset yok veya dosya degil: {source}")
            if sha256(source) != asset["sha256"].lower():
                raise SozlesmeHatasi(f"asset hash uyusmuyor: {source}")
            try:
                from PIL import Image
                with Image.open(source) as image:
                    actual = (image.width, image.height)
            except Exception as exc:
                raise SozlesmeHatasi(f"asset goruntu olarak acilamadi: {source}: {exc}") from exc
            if actual != (asset["width"], asset["height"]):
                raise SozlesmeHatasi(f"asset boyutu uyusmuyor: beklenen={(asset['width'], asset['height'])}, gercek={actual}")
    return packet


def utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)
