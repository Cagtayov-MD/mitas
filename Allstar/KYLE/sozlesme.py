from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DURUMLAR = ("DEGISIKLIK_VAR", "DEGISIKLIK_YOK", "ARIZA")


class GirdiHatasi(ValueError):
    pass


@dataclass(frozen=True)
class Girdi:
    series_id: str
    episode_id: str
    sources: dict[str, str]
    profile: str

    def __post_init__(self) -> None:
        if not self.series_id or not self.episode_id:
            raise GirdiHatasi("series_id ve episode_id zorunlu")
        if len(self.sources) < 2:
            raise GirdiHatasi("en az iki bagimsiz kaynak zorunlu")
        if len(set(self.sources)) != len(self.sources):
            raise GirdiHatasi("kaynak adlari benzersiz olmali")


@dataclass
class Cikti:
    series_id: str
    episode_id: str
    durum: str
    changes: list[dict] = field(default_factory=list)
    review_candidates: list[dict] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    sinif: str | None = None
    mesaj: str | None = None
    uretim_zamani: str = ""
    motor_surumu: str = "kyle/1.0.0"

    def __post_init__(self) -> None:
        if self.durum not in DURUMLAR:
            raise ValueError(f"gecersiz durum: {self.durum}")
        if self.durum == "ARIZA" and not (self.sinif and self.mesaj):
            raise ValueError("ARIZA sinif + mesaj zorunlu")
        if self.durum != "ARIZA" and (self.sinif or self.mesaj):
            raise ValueError("yalniz ARIZA sinif/mesaj tasir")
        if self.durum == "DEGISIKLIK_YOK" and self.changes:
            raise ValueError("DEGISIKLIK_YOK changes tasiyamaz")
        if self.durum == "DEGISIKLIK_VAR" and not self.changes:
            raise ValueError("DEGISIKLIK_VAR changes bos olamaz")
        if not self.uretim_zamani:
            self.uretim_zamani = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def as_dict(self) -> dict:
        data = {
            "schema_version": "kyle.result/v1",
            "series_id": self.series_id,
            "episode_id": self.episode_id,
            "durum": self.durum,
            "changes": self.changes,
            "review_candidates": self.review_candidates,
            "evidence": self.evidence,
            "motor_surumu": self.motor_surumu,
            "uretim_zamani": self.uretim_zamani,
        }
        if self.durum == "ARIZA":
            data |= {"sinif": self.sinif, "mesaj": self.mesaj}
        return data

    def write(self, out_root: str | Path) -> Path:
        d = Path(out_root) / self.series_id / self.episode_id
        d.mkdir(parents=True, exist_ok=True)
        target = d / "kyle.json"
        tmp = d / "kyle.json.tmp"
        tmp.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, target)
        return target
