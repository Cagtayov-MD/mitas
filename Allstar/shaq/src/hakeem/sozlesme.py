"""HAKEEM'in Shaq'tan daha kati girdi ve bagimsizlik kapisi.

Ayni ``mitas.okuma/v1`` zarfi kullanilir. Boylece iki motor birebir ayni
paketlerle olculebilir; HAKEEM yalnız semantik degismezleri daha kati uygular.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sozlesme import OkumaPaketi, SozlesmeHatasi, oku
from src.normalizasyon import normalize


HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class Kanal:
    ad: str
    paket: OkumaPaketi
    packet_sha256: str
    independence_key: str


@dataclass(frozen=True)
class GirdiCifti:
    film_id: str
    bolum: str
    kanallar: tuple[Kanal, Kanal]

    @property
    def packet_hashes(self) -> list[str]:
        return [kanal.packet_sha256 for kanal in self.kanallar]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strict_packet(packet: OkumaPaketi) -> None:
    raw = packet.raw
    if raw["durum"] == "OKUNDU" and not raw.get("lines"):
        raise SozlesmeHatasi("HAKEEM: OKUNDU en az bir satir ister; bossa METIN_YOK olmali")
    orders: set[int] = set()
    for line in raw.get("lines", []):
        if not normalize(line["text"]):
            raise SozlesmeHatasi("HAKEEM: yalniz noktalama/bosluk olan satir okunmus sayilamaz")
        if line["order"] in orders:
            raise SozlesmeHatasi("HAKEEM: line.order kanal icinde benzersiz olmali")
        orders.add(line["order"])
        for optional in ("block_id", "page_id"):
            if optional in line and not isinstance(line[optional], (str, int)):
                raise SozlesmeHatasi(f"HAKEEM: line.{optional} metin veya tamsayi olmali")
        if "role_hint" in line and not isinstance(line["role_hint"], str):
            raise SozlesmeHatasi("HAKEEM: line.role_hint metin olmali")
    external_ids = raw["film"].get("external_ids", {})
    for namespace, value in external_ids.items():
        if not isinstance(namespace, str) or not namespace.strip():
            raise SozlesmeHatasi("HAKEEM: external_ids anahtari bos olmayan metin olmali")
        if not isinstance(value, str) or not value.strip():
            raise SozlesmeHatasi("HAKEEM: external_ids degeri bos olmayan metin olmali")
    for asset in raw["assets"]:
        if not HEX64.fullmatch(asset["sha256"]):
            raise SozlesmeHatasi("HAKEEM: asset.sha256 hexadecimal olmali")


def _independence_key(raw: dict[str, Any]) -> str:
    producer = raw["producer"]
    explicit = producer.get("independence_group")
    if explicit is not None:
        if not isinstance(explicit, str) or not explicit.strip():
            raise SozlesmeHatasi("HAKEEM: producer.independence_group bos olmayan metin olmali")
        return explicit.strip()
    return f"{producer['engine_family'].strip()}::{producer['model_digest'].strip()}"


def paket_dosyalari(film_dir: str | Path, bolum: str) -> list[Path]:
    folder = Path(film_dir) / bolum
    paths = sorted(folder.glob("*.okuma.json"))
    if len(paths) != 2:
        raise SozlesmeHatasi(f"{folder}: HAKEEM bolum basina tam iki *.okuma.json ister (bulunan={len(paths)})")
    return paths


def cift_oku(film_dir: str | Path, film_id: str, bolum: str) -> GirdiCifti:
    paths = paket_dosyalari(film_dir, bolum)
    entries = sorted(((oku(path), path) for path in paths), key=lambda item: item[0].producer_id)
    packets = [entry[0] for entry in entries]
    paths = [entry[1] for entry in entries]
    for packet in packets:
        _strict_packet(packet)
        if packet.film_id != film_id or packet.bolum != bolum:
            raise SozlesmeHatasi("HAKEEM: CLI film_id/bolum paketle uyusmuyor")
    if packets[0].raw.get("film") != packets[1].raw.get("film"):
        raise SozlesmeHatasi("HAKEEM: iki kanal film metadata/external_ids olarak uyusmuyor")
    if packets[0].producer_id == packets[1].producer_id:
        raise SozlesmeHatasi("HAKEEM: iki kanal ayni producer.id olamaz")
    keys = [_independence_key(packet.raw) for packet in packets]
    digests = [packet.raw["producer"]["model_digest"].strip() for packet in packets]
    if keys[0] == keys[1] or digests[0] == digests[1]:
        raise SozlesmeHatasi(
            "HAKEEM: iki kanal bagimsiz degil; independence_group ve model_digest farkli olmali")
    channels = tuple(
        Kanal(ad=ad, paket=packet, packet_sha256=_file_sha256(path), independence_key=key)
        for ad, packet, path, key in zip(("a", "b"), packets, paths, keys, strict=True)
    )
    return GirdiCifti(film_id=film_id, bolum=bolum, kanallar=channels)  # type: ignore[arg-type]


def run_id(cift: GirdiCifti, config_digest: str, engine_version: str,
           provider_version: str, code_digest: str, runtime_digest: str) -> str:
    value = {
        "film_id": cift.film_id,
        "bolum": cift.bolum,
        "packets": sorted((channel.paket.producer_id, channel.packet_sha256)
                          for channel in cift.kanallar),
        "config_digest": config_digest,
        "engine_version": engine_version,
        "provider_version": provider_version,
        "code_digest": code_digest,
        "runtime_digest": runtime_digest,
    }
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return "hk-run-" + hashlib.sha256(encoded).hexdigest()[:24]
