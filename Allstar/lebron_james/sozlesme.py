"""Lebron kulesinin sözleşmesi — Girdi / Cikti / ariza.

Kulenin DIŞ yüzü burada tanımlıdır. Derleyici (src/derleyici.py) bu dosyayı
bilmez; çeviri main.py'de yapılır. Böylece motorun iç tipleri dışarı sızmaz.

Spec: docs/superpowers/specs/2026-08-15-allstar-lebron-kulesi-design.md
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DURUMLAR = ("OKUNDU", "METIN_YOK", "ARIZA")
BOLUMLER = ("cikis", "giris")   # raf etiketi — karar DEGIL (bkz. spec 3.1)


class GirdiHatasi(ValueError):
    """Girdi sözleşmesi ihlali — çağıranın hatası, kulenin değil."""


@dataclass(frozen=True)
class Girdi:
    """film_id + kareler dizini. Faz 1'de tek girdi tipi kare klasörüdür."""
    film_id: str
    kareler: str
    bolum: str = "cikis"
    config: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.film_id:
            raise GirdiHatasi("film_id bos olamaz")
        if self.bolum not in BOLUMLER:
            raise GirdiHatasi(f"bolum {self.bolum!r} gecersiz — {BOLUMLER}")
        if not self.kareler:
            raise GirdiHatasi("kareler dizini zorunlu")


@dataclass
class Cikti:
    """out/<film_id>/<bolum>/lebron.json'un birebir karsiligi."""
    film_id: str
    durum: str
    bolum: str = "cikis"
    satirlar: list[str] = field(default_factory=list)
    # Uretilen artefakt(lar)in kunyesi. HER ZAMAN liste. Kompozisyon
    # basariliysa OKUMA SONUCUNDAN BAGIMSIZ dolar — okuyucu coksede master
    # diskte durur (spec 3.2). Bu Kobe'den bilincli ayrisma: orada artefakt
    # yalniz BULUNDU'da uretilirdi, burada ARIZA'da da paylasilir.
    uretilen: list[dict] = field(default_factory=list)
    kanit: dict = field(default_factory=dict)
    motor_surumu: str = ""
    uretim_zamani: str = ""
    sure_sn: float = 0.0
    # yalniz ARIZA
    sinif: str | None = None
    mesaj: str | None = None

    def __post_init__(self) -> None:
        if self.bolum not in BOLUMLER:
            raise ValueError(f"bolum {self.bolum!r} gecersiz — {BOLUMLER}")
        if self.durum not in DURUMLAR:
            raise ValueError(f"durum {self.durum!r} gecersiz — {DURUMLAR}")
        # DEGISMEZ: ARIZA kanitsiz olamaz, METIN_YOK ariza alani tasiyamaz.
        # Bu ikisi birlikte "ariza sessizce icerik gercegine donusmesin"
        # kapisidir (spec 3.3).
        if self.durum == "ARIZA" and not (self.sinif and self.mesaj):
            raise ValueError("ARIZA icin sinif ve mesaj zorunlu")
        if self.durum != "ARIZA" and (self.sinif or self.mesaj):
            raise ValueError(f"{self.durum} sinif/mesaj tasiyamaz")
        # Satir YALNIZ okundugunda olur: METIN_YOK'ta okunacak sey, ARIZA'da
        # guvenilecek cikti yoktur.
        if self.durum != "OKUNDU" and self.satirlar:
            raise ValueError(f"{self.durum} satir tasiyamaz")
        if self.durum == "OKUNDU" and not self.satirlar:
            raise ValueError("OKUNDU satirsiz olamaz — bos ise METIN_YOK")
        if not self.uretim_zamani:
            self.uretim_zamani = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds")

    def sozluk(self) -> dict:
        d = {"film_id": self.film_id, "bolum": self.bolum, "durum": self.durum}
        if self.durum == "OKUNDU":
            d["satirlar"] = self.satirlar
        if self.durum == "ARIZA":
            d |= {"sinif": self.sinif, "mesaj": self.mesaj}
        d |= {"uretilen": self.uretilen, "kanit": self.kanit,
              "motor_surumu": self.motor_surumu,
              "uretim_zamani": self.uretim_zamani, "sure_sn": self.sure_sn}
        return d

    def yaz(self, kok: str | Path, ek_dosyalar: dict[str, dict] | None = None) -> Path:
        """out/<film_id>/<bolum>/lebron.json — atomik yaz, sonra _TAMAM.

        Kuyruk klasorun kendisi oldugu icin tuketici biz yazarken okuyabilir.
        os.replace yarim dosya okunmasini, _TAMAM "yaziliyor mu bitti mi"
        belirsizligini kapatir. Tuketici kurali: _TAMAM yoksa dosya yok sayilir.

        lebron.txt YALNIZ OKUNDU'da yazilir: bos bir txt, yalniz metni okuyan
        bir tuketiciye "yazi bulunamadi" gibi gorunur ve METIN_YOK / ARIZA
        ayrimini yutar (spec 3.2).
        """
        d = Path(kok) / self.film_id / self.bolum
        d.mkdir(parents=True, exist_ok=True)
        (d / "_TAMAM").unlink(missing_ok=True)
        hedef, gecici = d / "lebron.json", d / "lebron.json.tmp"
        gecici.write_text(json.dumps(self.sozluk(), ensure_ascii=False, indent=1),
                          encoding="utf-8")
        os.replace(gecici, hedef)
        txt = d / "lebron.txt"
        if self.durum == "OKUNDU":
            txt.write_text("\n".join(self.satirlar) + "\n", encoding="utf-8")
        else:
            txt.unlink(missing_ok=True)
        ek_dosyalar = ek_dosyalar or {}
        if "lebron.okuma.json" not in ek_dosyalar:
            (d / "lebron.okuma.json").unlink(missing_ok=True)
        for ad, belge in ek_dosyalar.items():
            gecici = d / f"{ad}.tmp"
            gecici.write_text(json.dumps(belge, ensure_ascii=False, indent=1),
                               encoding="utf-8")
            os.replace(gecici, d / ad)
        (d / "_TAMAM").write_text("", encoding="utf-8")
        return hedef


def ariza(film_id: str, sinif: str, mesaj: str, kanit: dict | None = None,
          bolum: str = "cikis", uretilen: list[dict] | None = None) -> Cikti:
    """Tek ariza uretim noktasi — sinif/mesaj atlanamasin diye."""
    return Cikti(film_id=film_id, bolum=bolum, durum="ARIZA", sinif=sinif,
                 mesaj=mesaj, kanit=kanit or {}, uretilen=uretilen or [])
