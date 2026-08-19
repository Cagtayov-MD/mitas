"""Iverson kulesinin sözleşmesi — Girdi / Cikti / ariza.

Kulenin DIŞ yüzü burada tanımlıdır (kobe sozlesme kalıbı). Motor (src/motor.py)
bu dosyayı bilmez; çeviri main.py'de yapılır.

Girdi: ffmpeg çıktısı SES DOSYASI (16k mono wav önerilir — sheriff media_prep
kalıbı; diğer ses taşıyan formatlar da kabul edilir, kule kendi 16k mono'ya
indirir) + film_id.

Çıktı: out/<film_id>/iverson.json + _TAMAM (+ transcript.txt, transcript_plain.txt,
chlang.json). _TAMAM yazım bariyeridir, başarı hükmü değildir — tüketici JSON'a bakar.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DURUMLAR = ("TRANSKRIPT", "METIN_YOK", "DIL_DESTEKSIZ", "ARIZA")
SCHEMA = "iverson.girdi/v1"
SES_UZANTILARI = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".mp4", ".mkv", ".avi", ".mov", ".ts")


class GirdiHatasi(ValueError):
    """Girdi sözleşmesi ihlali — çağıranın hatası, kulenin değil."""


def paket_oku(yol: str | Path) -> dict:
    """Opsiyonel JSON girdi paketini (iverson.girdi/v1) doğrula → sözlük.
    {schema_version, film_id, ses, dil_hint?, tr_mensei?, max_saniye?}"""
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
    for k in ("film_id", "ses"):
        v = raw.get(k)
        if not isinstance(v, str) or not v.strip():
            raise GirdiHatasi(k + " zorunlu metindir")
    return raw


@dataclass(frozen=True)
class Girdi:
    """film_id + ses dosyası yolu. Standart yol: doğrudan ses (sheriff kalıbı)."""
    film_id: str
    ses: str

    def __post_init__(self) -> None:
        if not self.film_id:
            raise GirdiHatasi("film_id bos olamaz")
        if not self.ses:
            raise GirdiHatasi("ses yolu bos olamaz")


@dataclass
class Cikti:
    """out/<film_id>/iverson.json'un birebir karşılığı."""
    film_id: str
    durum: str                 # TRANSKRIPT | METIN_YOK | DIL_DESTEKSIZ | ARIZA
    dil: str | None = None     # tespit/kullanılan whisper dil kodu (ku dahil)
    model: str = ""            # large-v3-turbo | large-v3 | none
    kanal: str = ""            # "a:0/c1" ya da "downmix"
    segment_sayisi: int = 0
    ses_sure_sn: float = 0.0
    transkript: dict | None = None   # {yol, plain_yol, karakter_sayisi, ilk_280}
    chlang: dict | None = None       # kanal-dil tespiti (MMS-LID) — varsa
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
        #   1. ARIZA sınıf/mesajsız olamaz; arıza asla içerik gerçeğine dönüşmez.
        #   2. ARIZA dışı sinif/mesaj taşıyamaz.
        #   3. TRANSKRIPT transkriptsiz/segmentsiz olamaz.
        #   4. METIN_YOK segment taşımaz; DIL_DESTEKSIZ dil taşımak zorunda, transkript taşımaz.
        if self.durum == "ARIZA" and not (self.sinif and self.mesaj):
            raise ValueError("ARIZA icin sinif ve mesaj zorunlu")
        if self.durum != "ARIZA" and (self.sinif or self.mesaj):
            raise ValueError(self.durum + " sinif/mesaj tasiyamaz")
        if self.durum == "TRANSKRIPT" and not (self.transkript and self.segment_sayisi > 0):
            raise ValueError("TRANSKRIPT transkript ve segment>0 tasimak zorunda")
        if self.durum == "METIN_YOK" and (self.segment_sayisi > 0 or self.transkript):
            raise ValueError("METIN_YOK segment/transkript tasiyamaz")
        if self.durum == "DIL_DESTEKSIZ" and (not self.dil or self.transkript):
            raise ValueError("DIL_DESTEKSIZ dil tasimak zorunda, transkript tasiyamaz")
        if not self.uretim_zamani:
            self.uretim_zamani = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds")

    def sozluk(self) -> dict:
        d = {"film_id": self.film_id, "durum": self.durum}
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
            d |= {"dil": self.dil, "model": self.model, "kanal": self.kanal,
                  "segment_sayisi": self.segment_sayisi, "ses_sure_sn": self.ses_sure_sn,
                  "transkript": self.transkript, "chlang": self.chlang}
        if self.durum == "ARIZA":
            d |= {"sinif": self.sinif, "mesaj": self.mesaj}
        d |= {"kanit": self.kanit, "motor_surumu": self.motor_surumu,
              "uretim_zamani": self.uretim_zamani, "sure_sn": self.sure_sn}
        return d

    def yaz(self, kok: str | Path) -> Path:
        """out/<film_id>/iverson.json — atomik yaz, sonra _TAMAM.

        transcript.txt/transcript_plain.txt/chlang.json motor tarafından BU
        dizine öNCEDEN yazılmış olmalı; _TAMAM hepsinin bittiğini işaretler.
        """
        d = Path(kok) / self.film_id
        d.mkdir(parents=True, exist_ok=True)
        hedef, gecici = d / "iverson.json", d / "iverson.json.tmp"
        gecici.write_text(json.dumps(self.sozluk(), ensure_ascii=False, indent=1),
                          encoding="utf-8")
        os.replace(gecici, hedef)
        (d / "_TAMAM").write_text("", encoding="utf-8")
        return hedef


def ariza(film_id: str, sinif: str, mesaj: str, kanit: dict | None = None) -> Cikti:
    """Tek arıza üretim noktası — sinif/mesaj atlanamasın diye."""
    return Cikti(film_id=film_id, durum="ARIZA", sinif=sinif, mesaj=mesaj,
                 kanit=kanit or {})
