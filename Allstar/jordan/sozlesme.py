"""Jordan kulesinin sözleşmesi — Girdi / Cikti / ariza.

Kulenin DIŞ yüzü burada tanımlıdır. Motor (src/) bu dosyayı bilmez; çeviri
main.py'de yapılır. Böylece motorun iç tipleri dışarı sızmaz.

Jordan'ın tek girdisi VİDEO'dur (mp4). Kare dizini, PNG havuzu almaz —
"nereden okunacağı" sorusu Kobe'nin işidir, Jordan verilen klibi okur.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DURUMLAR = ("OKUNDU", "METIN_YOK", "ARIZA")
BOLUMLER = ("cikis", "giris")   # kapanis jenerigi / giris jenerigi


class GirdiHatasi(ValueError):
    """Girdi sözleşmesi ihlali — çağıranın hatası, kulenin değil."""


@dataclass(frozen=True)
class Girdi:
    """film_id + video. Video, jeneriğin KENDİSİ olan bir kliptir."""
    film_id: str
    video: str = ""
    bolum: str = "cikis"
    config: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.film_id:
            raise GirdiHatasi("film_id bos olamaz")
        if self.bolum not in BOLUMLER:
            raise GirdiHatasi(f"bolum {self.bolum!r} gecersiz — {BOLUMLER}")
        if not self.video:
            raise GirdiHatasi(
                "video zorunlu — Jordan'in girdisi mp4'tur. Kare dizini/PNG "
                "havuzu okumaz; jeneriğin nerede olduğu Kobe'nin isidir.")


@dataclass
class Cikti:
    """out/<film_id>/<bolum>/jordan.json'un birebir karsiligi."""
    film_id: str
    durum: str
    bolum: str = "cikis"
    # gecis 1 — videodan okunan ham metin, ekran bloklari korunarak
    bloklar: list = field(default_factory=list)
    # gecis 2 — bloklardan turetilen rol->isim ciftleri (GORUNTU GORMEDEN)
    ciftler: list = field(default_factory=list)
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
        # DEGISMEZ: ARIZA kanitsiz olamaz, digerleri ariza alani tasiyamaz.
        # Bu iki kural birlikte "ariza sessizce icerik gercegine donusmesin"
        # kapisidir — Kobe'den devralinan en onemli ders.
        if self.durum == "ARIZA" and not (self.sinif and self.mesaj):
            raise ValueError("ARIZA icin sinif ve mesaj zorunlu")
        if self.durum != "ARIZA" and (self.sinif or self.mesaj):
            raise ValueError(f"{self.durum} sinif/mesaj tasiyamaz")
        # Metin YALNIZ okunmussa tasinir: "metin yok" derken metin tasimak,
        # ya da ariza aninda yarim okumayi cikti saymak celiskidir.
        if self.durum != "OKUNDU" and (self.bloklar or self.ciftler):
            raise ValueError(f"{self.durum} blok/cift tasiyamaz")
        if self.durum == "OKUNDU" and not self.bloklar:
            raise ValueError("OKUNDU en az bir blok ister; boşsa METIN_YOK'tur")
        if not self.uretim_zamani:
            self.uretim_zamani = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds")

    def satirlar(self) -> list[str]:
        """Tum bloklarin satirlari, goruldugu sirayla — duz metin gorunumu."""
        return [s for b in self.bloklar for s in b.get("satirlar", [])]

    def sozluk(self) -> dict:
        d = {"film_id": self.film_id, "bolum": self.bolum, "durum": self.durum}
        sheriff_keys = ("MITAS_SHERIFF_RUN_ID", "MITAS_SHERIFF_TASK_ID",
                        "MITAS_SHERIFF_ATTEMPT_ID")
        if all(os.environ.get(key) for key in sheriff_keys):
            d["schema_version"] = "mitas.jordan/v1"
            d["identity"] = {
                "run_id": os.environ[sheriff_keys[0]],
                "task_id": os.environ[sheriff_keys[1]],
                "attempt_id": os.environ[sheriff_keys[2]],
            }
        if self.durum == "OKUNDU":
            d |= {"bloklar": self.bloklar, "ciftler": self.ciftler}
        if self.durum == "ARIZA":
            d |= {"sinif": self.sinif, "mesaj": self.mesaj}
        d |= {"kanit": self.kanit, "motor_surumu": self.motor_surumu,
              "uretim_zamani": self.uretim_zamani, "sure_sn": self.sure_sn}
        return d

    def yaz(self, kok: str | Path) -> Path:
        """out/<film_id>/<bolum>/ — atomik yaz, _TAMAM EN SON.

        Kuyruk klasorun kendisi oldugu icin tuketici biz yazarken okuyabilir.
        os.replace yarim dosya okunmasini, _TAMAM "yaziliyor mu bitti mi"
        belirsizligini kapatir. Tuketici kurali: _TAMAM yoksa dosya yok sayilir.
        """
        d = Path(kok) / self.film_id / self.bolum
        d.mkdir(parents=True, exist_ok=True)
        self._atomik(d / "jordan.txt", "\n".join(self.satirlar()))
        self._atomik(d / "jordan.json",
                     json.dumps(self.sozluk(), ensure_ascii=False, indent=1))
        (d / "_TAMAM").write_text("", encoding="utf-8")
        return d / "jordan.json"

    @staticmethod
    def _atomik(hedef: Path, icerik: str) -> None:
        gecici = hedef.with_suffix(hedef.suffix + ".tmp")
        gecici.write_text(icerik, encoding="utf-8")
        os.replace(gecici, hedef)


def ariza(film_id: str, sinif: str, mesaj: str, kanit: dict | None = None,
          bolum: str = "cikis") -> Cikti:
    """Tek ariza uretim noktasi — sinif/mesaj atlanamasin diye."""
    return Cikti(film_id=film_id, bolum=bolum, durum="ARIZA", sinif=sinif,
                 mesaj=mesaj, kanit=kanit or {})
