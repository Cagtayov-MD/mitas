"""Kobe kulesinin sözleşmesi — Girdi / Cikti / ariza.

Kulenin DIŞ yüzü burada tanımlıdır. Motor (src/motor.py) bu dosyayı bilmez;
çeviri main.py'de yapılır. Böylece motorun iç tipleri (Sonuc) dışarı sızmaz.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DURUMLAR = ("BULUNDU", "KREDI_YOK", "ARIZA")


class GirdiHatasi(ValueError):
    """Girdi sözleşmesi ihlali — çağıranın hatası, kulenin değil."""


@dataclass(frozen=True)
class Girdi:
    """film_id + (video XOR kareler). Standart yol: video."""
    film_id: str
    video: str | None = None
    kareler: str | None = None
    config: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.film_id:
            raise GirdiHatasi("film_id bos olamaz")
        if bool(self.video) == bool(self.kareler):
            raise GirdiHatasi(
                "video ve kareler'den TAM OLARAK biri verilmeli — "
                f"video={self.video!r} kareler={self.kareler!r}. "
                "Kule sessizce bir tarafi secmez.")


@dataclass
class Cikti:
    """out/<film_id>/kobe.json'un birebir karsiligi."""
    film_id: str
    durum: str
    baslangic_kare: int | None = None
    baslangic_sn: float | None = None
    guven: float | None = None
    script: str | None = None
    kanit: dict = field(default_factory=dict)
    motor_surumu: str = ""
    uretim_zamani: str = ""
    sure_sn: float = 0.0
    # yalniz ARIZA
    sinif: str | None = None
    mesaj: str | None = None

    def __post_init__(self) -> None:
        if self.durum not in DURUMLAR:
            raise ValueError(f"durum {self.durum!r} gecersiz — {DURUMLAR}")
        # DEGISMEZ: ARIZA kanitsiz olamaz, KREDI_YOK ariza alani tasiyamaz.
        # Bu iki kural birlikte "ariza sessizce icerik gercegine donusmesin"
        # kapisidir (spec 4.3).
        if self.durum == "ARIZA" and not (self.sinif and self.mesaj):
            raise ValueError("ARIZA icin sinif ve mesaj zorunlu")
        if self.durum != "ARIZA" and (self.sinif or self.mesaj):
            raise ValueError(f"{self.durum} sinif/mesaj tasiyamaz")
        if not self.uretim_zamani:
            self.uretim_zamani = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds")

    def sozluk(self) -> dict:
        d = {"film_id": self.film_id, "durum": self.durum}
        if self.durum == "BULUNDU":
            d |= {"baslangic_kare": self.baslangic_kare,
                  "baslangic_sn": self.baslangic_sn,
                  "guven": self.guven, "script": self.script}
        if self.durum == "ARIZA":
            d |= {"sinif": self.sinif, "mesaj": self.mesaj}
        d |= {"kanit": self.kanit, "motor_surumu": self.motor_surumu,
              "uretim_zamani": self.uretim_zamani, "sure_sn": self.sure_sn}
        return d

    def yaz(self, kok: str | Path) -> Path:
        """out/<film_id>/kobe.json — atomik yaz, sonra _TAMAM.

        Kuyruk klasorun kendisi oldugu icin tuketici biz yazarken okuyabilir.
        os.replace yarim dosya okunmasini, _TAMAM ise "yaziliyor mu bitti mi"
        belirsizligini kapatir. Tuketici kurali: _TAMAM yoksa dosya yok sayilir.
        """
        d = Path(kok) / self.film_id
        d.mkdir(parents=True, exist_ok=True)
        hedef, gecici = d / "kobe.json", d / "kobe.json.tmp"
        gecici.write_text(json.dumps(self.sozluk(), ensure_ascii=False, indent=1),
                          encoding="utf-8")
        os.replace(gecici, hedef)
        (d / "_TAMAM").write_text("", encoding="utf-8")
        return hedef


def ariza(film_id: str, sinif: str, mesaj: str, kanit: dict | None = None) -> Cikti:
    """Tek ariza uretim noktasi — sinif/mesaj atlanamasin diye."""
    return Cikti(film_id=film_id, durum="ARIZA", sinif=sinif, mesaj=mesaj,
                 kanit=kanit or {})
