"""Nash kulesinin sözleşmesi — Girdi / Cikti / ariza.

Kulenin DIŞ yüzü burada tanımlıdır. src/ bu dosyayı bilmez; çeviri main.py'de
yapılır. Böylece iç tipler (HavuzSonucu, Sayfa) dışarı sızmaz.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DURUMLAR = ("OKUNDU", "METIN_YOK", "ARIZA")
BOLUMLER = ("cikis", "giris")   # kapanis jenerigi / giris jenerigi

# ARIZA siniflari — tek liste, main.py disinda uretilmez.
SINIFLAR = (
    "GIRDI_HATASI",     # dizin yok/bos, sozlesme ihlali
    "KARE_OKUNAMADI",   # kareler var, cv2.imread HICBIRINI acamadi
    "BELLEK",           # CUDA OOM
    "CIKTI_BOZUK",      # model konustu, cikti garble
    "MODEL",            # model yuklenemedi / beklenmedik istisna
    "YAPILANDIRMA",     # eksik/bozuk/bilinmeyen config
)


class GirdiHatasi(ValueError):
    """Girdi sözleşmesi ihlali — çağıranın hatası, kulenin değil."""


@dataclass(frozen=True)
class Girdi:
    """film_id + kareler (HAM kare dizini). Nash'in tek girdisi budur."""
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
            raise GirdiHatasi(
                "kareler (ham kare dizini) zorunlu — Nash video almaz, "
                "kare havuzu okur")


@dataclass
class Cikti:
    """out/<film_id>/<bolum>/nash.json'un birebir karsiligi."""
    film_id: str
    durum: str
    bolum: str = "cikis"
    # satirlar: [{"kaynak": "cikis_0647.png", "sayfa_sira": 1,
    #             "satir_sira": 0, "text": "..."}]
    satirlar: list[dict] = field(default_factory=list)
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
        # DEGISMEZ 1: ARIZA kanitsiz olamaz.
        if self.durum == "ARIZA" and not (self.sinif and self.mesaj):
            raise ValueError("ARIZA icin sinif ve mesaj zorunlu")
        if self.durum == "ARIZA" and self.sinif not in SINIFLAR:
            raise ValueError(f"sinif {self.sinif!r} gecersiz — {SINIFLAR}")
        if self.durum != "ARIZA" and (self.sinif or self.mesaj):
            raise ValueError(f"{self.durum} sinif/mesaj tasiyamaz")
        # DEGISMEZ 2: ARIZA ve METIN_YOK satir TASIYAMAZ. Bu iki kural birlikte
        # "ariza sessizce icerik gercegine donusmesin" kapisidir — ve aynasi:
        # icerik gercegi de ariza diye etiketlenmesin (spec 3.1).
        if self.durum != "OKUNDU" and self.satirlar:
            raise ValueError(f"{self.durum} satir tasiyamaz")
        # DEGISMEZ 3: OKUNDU bos olamaz — okunduysa bir sey okunmustur.
        if self.durum == "OKUNDU" and not self.satirlar:
            raise ValueError("OKUNDU satirsiz olamaz — bos ise METIN_YOK")
        if not self.uretim_zamani:
            self.uretim_zamani = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds")

    def metin(self) -> str:
        """nash.txt — satirlar, gorundugu sirayla, duz metin."""
        return "\n".join(s.get("text", "") for s in self.satirlar)

    def sozluk(self) -> dict:
        d = {"film_id": self.film_id, "bolum": self.bolum, "durum": self.durum}
        if self.durum == "OKUNDU":
            d["satirlar"] = self.satirlar
        if self.durum == "ARIZA":
            d |= {"sinif": self.sinif, "mesaj": self.mesaj}
        d |= {"kanit": self.kanit, "motor_surumu": self.motor_surumu,
              "uretim_zamani": self.uretim_zamani, "sure_sn": self.sure_sn}
        return d

    def yaz(self, kok: str | Path, ek_dosyalar: dict[str, dict] | None = None) -> Path:
        """out/<film_id>/<bolum>/ — atomik yaz, _TAMAM EN SON.

        Kuyruk klasorun kendisi oldugu icin tuketici biz yazarken okuyabilir.
        os.replace yarim dosya okunmasini, _TAMAM ise "yaziliyor mu bitti mi"
        belirsizligini kapatir. Tuketici kurali: _TAMAM yoksa dosya yok sayilir.
        nash.txt de _TAMAM'dan ONCE yazilir — isaret varsa IKISI de hazirdir.

        nash.txt YALNIZ `OKUNDU`'da yazilir. Bos bir nash.txt, yalniz metni
        okuyan bir tuketiciye "yazi bulunamadi" gibi gorunur ve ARIZA ile
        METIN_YOK ayrimini yutar — kulenin kapatmak icin var oldugu korluk.
        Dosya YOKSA tuketici nash.json'a bakmak ZORUNDA kalir.
        """
        d = Path(kok) / self.film_id / self.bolum
        d.mkdir(parents=True, exist_ok=True)
        # Yeniden kosu basladi: eski tamam isareti ve bu kosuda uretilmeyecek
        # onceki urunler tuketiciye yeni sonucmus gibi gorunemez.
        (d / "_TAMAM").unlink(missing_ok=True)
        ek_dosyalar = ek_dosyalar or {}
        for ad in ek_dosyalar:
            if Path(ad).name != ad or ad in {"_TAMAM", "nash.json", "nash.txt"}:
                raise ValueError(f"gecersiz ek dosya adi: {ad!r}")
        istenen = {"nash.json", *( ["nash.txt"] if self.durum == "OKUNDU" else []),
                   *ek_dosyalar.keys()}
        for eski in ("nash.txt", "nash.okuma.json"):
            if eski not in istenen:
                (d / eski).unlink(missing_ok=True)
        yazilacak = [("nash.json", json.dumps(self.sozluk(), ensure_ascii=False,
                                              indent=1))]
        if self.durum == "OKUNDU":
            yazilacak.append(("nash.txt", self.metin() + "\n"))
        for ad, icerik in yazilacak:
            gecici = d / f"{ad}.tmp"
            gecici.write_text(icerik, encoding="utf-8")
            os.replace(gecici, d / ad)
        for ad, belge in ek_dosyalar.items():
            gecici = d / f"{ad}.tmp"
            gecici.write_text(json.dumps(belge, ensure_ascii=False, indent=1),
                               encoding="utf-8")
            os.replace(gecici, d / ad)
        tamam_gecici = d / "_TAMAM.tmp"
        tamam_gecici.write_text("", encoding="utf-8")
        os.replace(tamam_gecici, d / "_TAMAM")
        return d / "nash.json"


def ariza(film_id: str, sinif: str, mesaj: str, kanit: dict | None = None,
          bolum: str = "cikis") -> Cikti:
    """Tek ariza uretim noktasi — sinif/mesaj atlanamasin diye."""
    return Cikti(film_id=film_id, bolum=bolum, durum="ARIZA", sinif=sinif,
                 mesaj=mesaj, kanit=kanit or {})
