"""Vince Carter kulesinin sözleşmesi — Girdi / Cikti / ariza.

Kulenin DIŞ yüzü burada tanımlıdır. Motor (src/) bu dosyayı bilmez; çeviri
main.py'de yapılır. Böylece motorun iç tipleri dışarı sızmaz (Kobe/Jordan
deseni — bkz. Allstar/kobe/sozlesme.py, Allstar/jordan/sozlesme.py).

Vince Carter ya jenerik videosunu ya da hazırlanmış kare dizinini alır.
İki girdi aynı anda verilmez. Çıktı satırları KESİN/ZAYIF/ÇATIŞMA/SÜPHELİ
sınıflarından biriyle etiketlenir (docs/PLAN.md §3 — kanıt tartısı); yalnız
SÜPHELİ ana metinden (vince.txt) dışlanır, vince_supheli.txt'e gider.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DURUMLAR = ("OKUNDU", "METIN_YOK", "ARIZA")
BOLUMLER = ("cikis", "giris")   # kapanis jenerigi (STANDART) / giris jenerigi

# docs/PLAN.md §3 — kanıt tartısının ürettiği dört sınıf. KESİN/ZAYIF/ÇATIŞMA
# vince.txt'e yazılır (görünür); SÜPHELİ yalnız vince_supheli.txt'e (gizli).
SATIR_SINIFLARI = ("KESIN", "ZAYIF", "CATISMA", "SUPHELI")
GORUNUR_SINIFLAR = ("KESIN", "ZAYIF", "CATISMA")
GIZLI_SINIF = "SUPHELI"

# İş tanımının sabitlediği arıza sınıfları — kapalı küme değil (Kobe/Jordan da
# yeni sinif değerini serbestçe üretebiliyor, örn. Jordan'ın
# KARE_HAVUZU_OKUNAMADI'sı), ama bunlar dokümante edilen çekirdek beşli.
ARIZA_SINIFLARI = ("GIRDI_HATASI", "VIDEO_HATASI", "MODEL_HATASI",
                    "BELLEK_HATASI", "CIKTI_BOZUK")

# durum/sinif/mesaj/satirlar/film_id birbirine bağlı ya da güvenlik-kritik
# alanlar — ARIZA'nın METIN_YOK'a dönüşmemesi VE film_id'nin yol kaçışına
# izin vermemesi için her mutasyonda yeniden doğrulanır.
_KORUNAN_ALANLAR = ("durum", "sinif", "mesaj", "satirlar", "film_id")
_EKSIK = object()  # "alan hic yoktu" isaretcisi — None'dan ayirt etmek icin


def _film_id_gecerli_mi(film_id: str) -> bool:
    """film_id TEK yol bileşeni olmalı — `Path(kok) / film_id / bolum` kule
    dışına ya da başka bir filmin klasörüne taşamaz (Nash dersi: "film
    kimliği tek yol bileşeni olarak zorlanır"). "/", "\\", "." , ".." hiçbiri
    geçerli değil — boş string de değil.
    """
    if not film_id or film_id in (".", ".."):
        return False
    if "/" in film_id or "\\" in film_id:
        return False
    return len(Path(film_id).parts) == 1


class GirdiHatasi(ValueError):
    """Girdi sözleşmesi ihlali — çağıranın hatası, kulenin değil."""


@dataclass(frozen=True)
class Girdi:
    """film_id + (video XOR kareler). Standart yol: video."""
    film_id: str
    video: str | None = None
    kareler: str | None = None
    bolum: str = "cikis"          # "cikis" = kapanis jenerigi (STANDART)
    config: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.film_id:
            raise GirdiHatasi("film_id bos olamaz")
        if not _film_id_gecerli_mi(self.film_id):
            raise GirdiHatasi(
                f"film_id {self.film_id!r} tek yol bileseni olmali — "
                "'/', '\\\\', '.', '..' icermez (film kimligi kule disina "
                "tasan bir yol olamaz)")
        if self.bolum not in BOLUMLER:
            raise GirdiHatasi(f"bolum {self.bolum!r} gecersiz — {BOLUMLER}")
        if bool(self.video) == bool(self.kareler):
            raise GirdiHatasi(
                "video ve kareler'den TAM OLARAK biri verilmeli — "
                f"video={self.video!r} kareler={self.kareler!r}. "
                "Kule sessizce bir tarafi secmez.")


@dataclass
class Cikti:
    """out/<film_id>/<bolum>/vince.json'un birebir karsiligi.

    `durum`/`sinif`/`mesaj`/`satirlar` kurulduktan sonra da korunur: bu dört
    alandan biri değiştirilmeye çalışılırsa sözleşme yeniden doğrulanır.
    ARIZA'nın kod yoluyla (yapım anında veya sonradan mutasyonla) METIN_YOK'a
    kayması bu yüzden mümkün değildir — bkz. `_dogrula`.
    """
    film_id: str
    durum: str
    bolum: str = "cikis"
    # yalniz OKUNDU: ekran sirasiyla siniflandirilmis satirlar. Her oge en az
    # {"metin": str, "sinif": SATIR_SINIFLARI'ndan biri} tasir; geri kalani
    # (ocr_skor, faz_tutar, catisma, kare_araligi, y_bandi...) kanit soy agaci.
    satirlar: list = field(default_factory=list)
    kanit: dict = field(default_factory=dict)
    motor_surumu: str = ""
    uretim_zamani: str = ""
    sure_sn: float = 0.0
    # yalniz ARIZA
    sinif: str | None = None
    mesaj: str | None = None

    def __post_init__(self) -> None:
        if not self.uretim_zamani:
            # dogrudan __dict__ uzerinden: __setattr__'daki koruma dongusune
            # girmeden tek seferlik varsayilani doldurur.
            self.__dict__["uretim_zamani"] = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds")
        self._dogrula()
        self.__dict__["_kuruldu"] = True

    def __setattr__(self, ad, deger) -> None:
        """Korunan alan sonradan degistirilirse yeniden dogrula; gecersizse
        ESKI DEGERE GERI AL (yalniz ValueError firlatip degeri degismis
        birakmak "ARIZA sessizce METIN_YOK oldu" ile ayni sonucu dogurur)."""
        korumali = ad in _KORUNAN_ALANLAR and self.__dict__.get("_kuruldu", False)
        eski = self.__dict__.get(ad, _EKSIK) if korumali else None
        object.__setattr__(self, ad, deger)
        if not korumali:
            return
        try:
            self._dogrula()
        except ValueError:
            if eski is _EKSIK:
                object.__delattr__(self, ad)
            else:
                object.__setattr__(self, ad, eski)
            raise

    def _dogrula(self) -> None:
        if not _film_id_gecerli_mi(self.film_id):
            raise ValueError(
                f"film_id {self.film_id!r} tek yol bileseni olmali — "
                "'/', '\\\\', '.', '..' icermez")
        if self.bolum not in BOLUMLER:
            raise ValueError(f"bolum {self.bolum!r} gecersiz — {BOLUMLER}")
        if self.durum not in DURUMLAR:
            raise ValueError(f"durum {self.durum!r} gecersiz — {DURUMLAR}")
        # DEGISMEZ: ARIZA kanitsiz olamaz, digerleri ariza alani tasiyamaz.
        # Bu iki kural birlikte "ariza sessizce icerik gercegine donusmesin"
        # kapisidir (Kobe/Jordan'dan devralinan en onemli ders).
        if self.durum == "ARIZA" and not (self.sinif and self.mesaj):
            raise ValueError("ARIZA icin sinif ve mesaj zorunlu")
        if self.durum != "ARIZA" and (self.sinif or self.mesaj):
            raise ValueError(f"{self.durum} sinif/mesaj tasiyamaz")
        # Satirlar YALNIZ okunmussa tasinir: "metin yok" derken satir tasimak,
        # ya da ariza aninda yarim okumayi cikti saymak celiskidir.
        if self.durum != "OKUNDU" and self.satirlar:
            raise ValueError(f"{self.durum} satir tasiyamaz")
        if self.durum == "OKUNDU" and not self.satirlar:
            raise ValueError("OKUNDU en az bir satir ister; boşsa METIN_YOK'tur")
        for s in self.satirlar:
            if not isinstance(s, dict) or not str(s.get("metin", "")).strip():
                raise ValueError(f"satir gecersiz (metin zorunlu): {s!r}")
            if s.get("sinif") not in SATIR_SINIFLARI:
                raise ValueError(
                    f"satir sinifi gecersiz: {s.get('sinif')!r} — {SATIR_SINIFLARI}")

    def gorunur_satirlar(self) -> list[str]:
        """vince.txt'e giren satirlar (KESIN+ZAYIF+CATISMA), ekran sirasiyla."""
        return [s["metin"] for s in self.satirlar if s.get("sinif") in GORUNUR_SINIFLAR]

    def supheli_satirlar(self) -> list[str]:
        """vince_supheli.txt'e giren satirlar (yalniz SUPHELI)."""
        return [s["metin"] for s in self.satirlar if s.get("sinif") == GIZLI_SINIF]

    def sozluk(self) -> dict:
        d = {"film_id": self.film_id, "bolum": self.bolum, "durum": self.durum}
        if self.durum == "OKUNDU":
            d["satirlar"] = self.satirlar
        if self.durum == "ARIZA":
            d |= {"sinif": self.sinif, "mesaj": self.mesaj}
        d |= {"kanit": self.kanit, "motor_surumu": self.motor_surumu,
              "uretim_zamani": self.uretim_zamani, "sure_sn": self.sure_sn}
        return d

    def yaz(self, kok: str | Path) -> Path:
        """out/<film_id>/<bolum>/ — ONCE eskiyi temizle, SONRA atomik yaz,
        _TAMAM EN SON.

        Kuyruk klasorun kendisi oldugu icin tuketici biz yazarken okuyabilir.
        os.replace yarim dosya okunmasini, _TAMAM ise "yaziliyor mu bitti mi"
        belirsizligini kapatir. Tuketici kurali: _TAMAM yoksa dosya yok sayilir.

        BAYAT DOSYA KORUMASI: bu film/bolum daha once OKUNDU ile yazilmis
        (vince.txt var) ama bu kosu ARIZA/METIN_YOK donuyorsa, ESKI vince.txt
        silinmeden sadece vince.json + _TAMAM tazelenirse tuketici bayat
        satirlari GECERLI okuma sanir — ARIZA'nin icerik gercegine
        donusmesiyle AYNI sonuc, dolambacli yoldan (koordinator bulgusu,
        bkz. Allstar/nash/DURUM.md: "eski _TAMAM isareti kosu basinda
        kaldirilir"). Bu yuzden ONCE _TAMAM (ilk is — yazim yarida kesilirse
        dizin "yarim" gorunsun, "gecerli" degil), SONRA vince.txt/
        vince_supheli.txt/vince.json/*.tmp silinir; ancak ONDAN SONRA yeni
        icerik yazilir.

        vince.txt YALNIZ OKUNDU'da ve YALNIZ doluysa yazilir (Nash dersi:
        _TAMAM + bos dosya = sessiz yalan). vince_supheli.txt yalniz supheli
        satir varsa yazilir.
        """
        d = Path(kok) / self.film_id / self.bolum
        d.mkdir(parents=True, exist_ok=True)
        self._temizle(d)
        if self.durum == "OKUNDU":
            gorunur = self.gorunur_satirlar()
            if gorunur:
                self._atomik(d / "vince.txt", "\n".join(gorunur))
            supheli = self.supheli_satirlar()
            if supheli:
                self._atomik(d / "vince_supheli.txt", "\n".join(supheli))
        self._atomik(d / "vince.json",
                     json.dumps(self.sozluk(), ensure_ascii=False, indent=1))
        (d / "_TAMAM").write_text("", encoding="utf-8")
        return d / "vince.json"

    @staticmethod
    def _temizle(d: Path) -> None:
        """Onceki kosudan kalan TUM cikti dosyalarini sil — _TAMAM ILK once."""
        (d / "_TAMAM").unlink(missing_ok=True)
        for ad in ("vince.txt", "vince_supheli.txt", "vince.json",
                   "vince.txt.tmp", "vince_supheli.txt.tmp", "vince.json.tmp"):
            (d / ad).unlink(missing_ok=True)

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
