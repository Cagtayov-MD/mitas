"""McGrady kulesinin sözleşmesi — paket okuma / Cikti / ariza.

Kulenin DIŞ yüzü burada tanımlıdır (kobe sozlesme kalıbı). Motor (src/motor.py)
bu dosyayı bilmez; çeviri main.py'de yapılır.

Girdi paketi (mcgrady.girdi/v1, JSON):
    {"schema_version": "mcgrady.girdi/v1", "film_id": "...",
     "profile": "film"|"dizi",
     "baslik": {"tr": "...", "orijinal": "...", "yil": 2018},
     "yonetmen": ["..."], "cast": ["..."], "yapimci": ["..."] (ops),
     "script": "en" (ops)}

Çıktı: out/<film_id>/mcgrady.json + _TAMAM (atomik yazım; _TAMAM yazım
bariyeridir, başarı hükmü değildir — tüketici JSON içeriğine bakar).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DURUMLAR = ("DOGRULANDI", "KILITLENEMEDI", "ARIZA")
PROFILLER = ("film", "dizi")
SCHEMA = "mcgrady.girdi/v1"


class GirdiHatasi(ValueError):
    """Girdi sözleşmesi ihlali — çağıranın hatası, kulenin değil."""


def paket_oku(yol: str | Path) -> dict:
    """Girdi paketini doğrula ve sözlük olarak döndür. Uygunsuzsa GirdiHatasi."""
    p = Path(yol)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        raise GirdiHatasi("paket okunamadi: " + str(yol) + ": " + str(e)) from e
    except json.JSONDecodeError as e:
        raise GirdiHatasi("paket JSON degil: " + str(yol) + ": " + str(e)) from e
    if not isinstance(raw, dict):
        raise GirdiHatasi("paket nesne olmali")
    if raw.get("schema_version") != SCHEMA:
        raise GirdiHatasi("schema_version '" + SCHEMA + "' olmali")
    for k in ("film_id", "profile"):
        v = raw.get(k)
        if not isinstance(v, str) or not v.strip():
            raise GirdiHatasi(k + " zorunlu metindir")
    if raw["profile"] not in PROFILLER:
        raise GirdiHatasi("profile " + str(PROFILLER) + " olmali: " + str(raw["profile"]))
    baslik = raw.get("baslik")
    if not isinstance(baslik, dict):
        raise GirdiHatasi("baslik nesne olmali")
    for k in ("tr", "orijinal"):
        v = baslik.get(k)
        if v is not None and not isinstance(v, str):
            raise GirdiHatasi("baslik." + k + " metin olmali")
    if not (baslik.get("tr") or baslik.get("orijinal")):
        raise GirdiHatasi("baslik.tr ya da baslik.orijinal en az biri dolu olmali")
    yil = baslik.get("yil")
    if yil is not None and not isinstance(yil, int):
        raise GirdiHatasi("baslik.yil tamsayi olmali")
    for k in ("yonetmen", "cast", "yapimci"):
        v = raw.get(k, [])
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            raise GirdiHatasi(k + " metin listesi olmali")
    return raw


@dataclass
class Cikti:
    """out/<film_id>/mcgrady.json'un birebir karşılığı."""
    film_id: str
    durum: str                       # DOGRULANDI | KILITLENEMEDI | ARIZA
    profile: str = "film"
    kimlik: dict | None = None       # {method, imdb_id, tmdb_id, kaynak_izi, cast_ortusme, versiyon_teyitli}
    oneriler: list[dict] = field(default_factory=list)   # {alan, ocr, kanonik, kaynak} — EZME YOK
    yonetmen: dict = field(default_factory=dict)         # {ocr, karar, kaynak, kontrol_onerisi}
    web_oneri: dict | None = None    # qc2_web bloğu (method None dahil)
    garble: list[dict] = field(default_factory=list)     # imza-yokluğu satırları — SİLME YOK
    afis: dict | None = None         # {yol, gecerli, neden}
    karar_onerileri: list[str] = field(default_factory=list)  # KONTROL sebepleri (tüketici uygular)
    kanit: dict = field(default_factory=dict)
    motor_surumu: str = ""
    uretim_zamani: str = ""
    sure_sn: float = 0.0
    # yalnız ARIZA
    sinif: str | None = None
    mesaj: str | None = None

    def __post_init__(self) -> None:
        if self.durum not in DURUMLAR:
            raise ValueError("durum " + repr(self.durum) + " gecersiz — " + str(DURUMLAR))
        # DEĞİŞMEZLER (kobe kalıbı):
        #   1. ARIZA sınıf/mesajsız olamaz; arıza asla sessizce KILITLENEMEDI'ye dönüşmez.
        #   2. ARIZA dışı sinif/mesaj taşıyamaz.
        #   3. DOGRULANDI kimliksiz olamaz; KILITLENEMEDI kimlik taşıyamaz.
        if self.durum == "ARIZA" and not (self.sinif and self.mesaj):
            raise ValueError("ARIZA icin sinif ve mesaj zorunlu")
        if self.durum != "ARIZA" and (self.sinif or self.mesaj):
            raise ValueError(self.durum + " sinif/mesaj tasiyamaz")
        if self.durum == "DOGRULANDI" and not self.kimlik:
            raise ValueError("DOGRULANDI kimlik tasimak zorunda")
        if self.durum == "KILITLENEMEDI" and self.kimlik:
            raise ValueError("KILITLENEMEDI kimlik tasiyamaz")
        if not self.uretim_zamani:
            self.uretim_zamani = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds")

    def sozluk(self) -> dict:
        d = {"film_id": self.film_id, "profile": self.profile, "durum": self.durum}
        sheriff_keys = ("MITAS_SHERIFF_RUN_ID", "MITAS_SHERIFF_TASK_ID",
                        "MITAS_SHERIFF_ATTEMPT_ID")
        if all(os.environ.get(key) for key in sheriff_keys):
            d["schema_version"] = "mitas.boundary/v1"
            d["identity"] = {
                "run_id": os.environ[sheriff_keys[0]],
                "task_id": os.environ[sheriff_keys[1]],
                "attempt_id": os.environ[sheriff_keys[2]],
            }
        if self.durum != "ARIZA":
            d |= {"kimlik": self.kimlik, "oneriler": self.oneriler,
                  "yonetmen": self.yonetmen, "web_oneri": self.web_oneri,
                  "garble": self.garble, "afis": self.afis,
                  "karar_onerileri": self.karar_onerileri}
        if self.durum == "ARIZA":
            d |= {"sinif": self.sinif, "mesaj": self.mesaj}
        d |= {"kanit": self.kanit, "motor_surumu": self.motor_surumu,
              "uretim_zamani": self.uretim_zamani, "sure_sn": self.sure_sn}
        return d

    def yaz(self, kok: str | Path) -> Path:
        """out/<film_id>/mcgrady.json — atomik yaz, sonra _TAMAM.

        Kuyruk klasörün kendisi olduğu için tüketici biz yazarken okuyabilir;
        os.replace yarım dosya okunmasını, _TAMAM 'yazılıyor mu bitti mi'
        belirsizliğini kapatır. Tüketici kuralı: _TAMAM yoksa dosya yok sayılır.
        """
        d = Path(kok) / self.film_id
        d.mkdir(parents=True, exist_ok=True)
        hedef, gecici = d / "mcgrady.json", d / "mcgrady.json.tmp"
        gecici.write_text(json.dumps(self.sozluk(), ensure_ascii=False, indent=1),
                          encoding="utf-8")
        os.replace(gecici, hedef)
        (d / "_TAMAM").write_text("", encoding="utf-8")
        return hedef


def ariza(film_id: str, sinif: str, mesaj: str, kanit: dict | None = None,
          profile: str = "film") -> Cikti:
    """Tek arıza üretim noktası — sinif/mesaj atlanamasın diye."""
    return Cikti(film_id=film_id, profile=profile, durum="ARIZA", sinif=sinif,
                 mesaj=mesaj, kanit=kanit or {})
