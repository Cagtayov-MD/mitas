"""Dizin → seçilmiş kareler. Havuz çekirdeğinin (havuz.py) üretim yüzeyi.

Bu modül SÖZLEŞMEYİ BİLMEZ — `hata` alanına etiket koyar, onu duruma/arızaya
main.py çevirir. Böylece Cikti tipleri src/'ye sızmaz.

Kaynak: harness/track_kunye/pilot_hat.havuz_derle_dizin + üretimdeki iki ayrı
örnekleme/sigorta katmanı (_pipe_track_kunye.ornekle, _pipe_hibrit_okuma.kol_frame).
Üçü burada tek yerde toplandı; davranış korundu.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2

import havuz as havuz_mod


@dataclass
class SecimSonucu:
    """`hata` None ise seçim başarılı. Etiketler main.py'de çevrilir:
    dizin_bos → ARIZA(GIRDI_HATASI) · kare_okunamadi → ARIZA(KARE_OKUNAMADI)
    havuz_bos → METIN_YOK (içerik gerçeği, arıza DEĞİL)."""
    yollar: list[Path] = field(default_factory=list)
    kanit: dict = field(default_factory=dict)
    hata: str | None = None
    analizler: dict = field(default_factory=dict, repr=False)


def _griler(yollar: list[Path]) -> tuple[list, list[Path]]:
    """Okunabilen kareleri griye çevir. Açılamayan kare SESSİZCE atlanır ama
    sayılır — 'kaç kare açılamadı' kanıta yazılır."""
    griler, gecerli = [], []
    for p in yollar:
        im = cv2.imread(str(p))
        if im is None:
            continue
        griler.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
        gecerli.append(p)
    return griler, gecerli


def ornekle(yollar: list[Path], tavan: int,
            son_kare_zorla: bool) -> tuple[list[Path], int]:
    """Kronolojik düzgün-adımlı örnekleme; düşürülen raporlanır.

    Sessiz kırpma YASAK — kaç sayfanın düştüğü kanıta yazılır. Üretimdeki
    referans (olcum_yatagi_faz2.py:147) bu sayıyı yanlış hesaplıyordu
    (atamadan SONRA çıkarma → daima 0); burada doğru hesaplanır.
    """
    if tavan <= 0 or len(yollar) <= tavan:
        return list(yollar), 0
    adim = len(yollar) / tavan
    indeksler = {min(len(yollar) - 1, int(i * adim)) for i in range(tavan)}
    if son_kare_zorla:
        indeksler.add(len(yollar) - 1)
    secim = [yollar[i] for i in sorted(indeksler)]
    return secim, len(yollar) - len(secim)


def ham_kuyruk_ekle(secim: list[Path], tum: list[Path],
                    n: int) -> tuple[list[Path], int]:
    """Ham dizinin SON n karesi her zaman seçime girer (giriş sigortası).

    Havuzdan değil HAM listeden alınır: havuz o kareleri hiç seçmemiş olabilir.
    Üretimdeki gibi seçimin SONUNA eklenir (kronolojik olarak zaten oradalar) —
    okuma sırası korunur, sayfalar arası dedup zinciri bozulmaz.
    """
    if n <= 0 or not tum:
        return secim, 0
    mevcut = {p.name for p in secim}
    ek = [p for p in tum[-n:] if p.name not in mevcut]
    return secim + ek, len(ek)


def havuz_derle_dizin(kare_dizin: Path,
                      desen: str = "*.png") -> tuple[list[Path], dict]:
    """Dizin → (seçilen yollar, istatistik). ÜRETİM YÜZEYİ — imza sabittir.

    `harness/track_kunye/pilot_hat.havuz_derle_dizin`'in birebir karşılığıdır
    ve onun yerini alır (Faz 3 sökümü). Üretim betikleri bunu çağırır; böylece
    havuz algoritmasının TEK kopyası kulenin içinde kalır.

    Örnekleme/sigorta UYGULANMAZ — üretimin kendi tavanları var ve bu yüzey
    onlardan önce gelir. Kule kendi akışında `sec()` kullanır.

    Boş dönüş de üretimdeki gibi ayrım YAPMAZ (`([], {"kare":0,"sayfa":0})`):
    `dizin_bos` / `kare_okunamadi` / `havuz_bos` ayrımı kulenin sözleşmesine
    özgüdür; üretime sızdırmak onun davranışını değiştirirdi.
    """
    yollar = sorted(Path(kare_dizin).glob(desen))
    griler, gecerli = _griler(yollar)
    if not griler:
        return [], {"kare": 0, "sayfa": 0}
    sonuc = havuz_mod.havuz_derle(griler)
    ekler = havuz_mod.ikinci_gecis(griler, sonuc)
    ist = {"kare": len(griler), "esik": sonuc.istatistik.esik,
           "grup": sonuc.istatistik.grup_sayisi, "alarm": sonuc.istatistik.alarm,
           "sayfa": len(sonuc.sayfalar), "ikinci_gecis_ek": len(ekler)}
    return [gecerli[i] for i in sorted(set(sonuc.sayfalar) | set(ekler))], ist


def sec(kare_dizin: Path, ayar: dict, desen: str = "*.png",
        detector: Callable | None = None) -> SecimSonucu:
    """Ham kare dizini → okunacak kareler + kanıt.

    `ayar`: {"tavan": int, "son_kare_zorla": bool, "ham_kuyruk": int}
    """
    kare_dizin = Path(kare_dizin)
    if not kare_dizin.is_dir():
        return SecimSonucu(hata="dizin_bos")
    tum = sorted(kare_dizin.glob(desen))
    if not tum:
        return SecimSonucu(hata="dizin_bos")

    if str(ayar.get("strateji", "legacy")).lower() == "text_run":
        import metin_secici
        try:
            if detector is None:
                analizler, detector_kanit = metin_secici.tara(
                    tum, ayar.get("detector") or {})
            else:
                detector_sonucu = detector(tum, ayar.get("detector") or {})
                if (isinstance(detector_sonucu, tuple)
                        and len(detector_sonucu) == 2):
                    analizler, detector_kanit = detector_sonucu
                else:
                    analizler, detector_kanit = detector_sonucu, {}
            if not isinstance(analizler, dict):
                raise metin_secici.DetectorArizasi(
                    "detector sonucu kare sozlugu degil")
            if not isinstance(detector_kanit, dict):
                detector_kanit = {}

            # Decode arizasi ile model/predict arizasini ayir. Worker'in dHash
            # verdigi normal yolda ana surec kareleri bir daha acmaz. Eski test
            # detectorleri/harici callback'ler dHash vermiyorsa uyumluluk icin
            # yalniz o yolda gri kareler uretilir.
            for p in tum:
                if p.name not in analizler:
                    analizler[p.name] = {
                        "boxes": [], "error_stage": "predict",
                        "error": "detector sonucu yok",
                    }
            okunabilir = [
                p for p in tum
                if (analizler.get(p.name) or {}).get("error_stage") != "decode"
            ]
            if not okunabilir:
                return SecimSonucu(
                    kanit={"kare": 0, "acilamayan": len(tum),
                           "strateji": "text_run", **detector_kanit},
                    hata="kare_okunamadi")
            gri_gerekli = any(
                not isinstance((analizler.get(p.name) or {}).get("dhash"), int)
                for p in okunabilir
                if not (analizler.get(p.name) or {}).get("error")
            )
            griler = None
            if gri_gerekli:
                griler, gercek_okunabilir = _griler(okunabilir)
                if len(gercek_okunabilir) != len(okunabilir):
                    okunabilir = gercek_okunabilir
            secim, text_kanit = metin_secici.sec(
                yollar=okunabilir, griler=griler, analizler=analizler,
                ayar=ayar)
        except metin_secici.DetectorArizasi as exc:
            return SecimSonucu(
                kanit={"kare": len(locals().get("okunabilir", [])),
                       "acilamayan": len(tum) - len(locals().get("okunabilir", [])),
                       "strateji": "text_run", "detector_hata": str(exc)[:500]},
                hata="detector_ariza")
        kanit = {"havuz": {"kare": len(okunabilir), "sayfa": len(secim),
                            "strateji": "text_run"},
                 "acilamayan": len(tum) - len(okunabilir),
                 **detector_kanit, **text_kanit}
        if not secim:
            if int(text_kanit.get("detector_hata_n", 0)):
                return SecimSonucu(kanit=kanit, hata="detector_ariza")
            return SecimSonucu(kanit=kanit, hata="havuz_bos")
        return SecimSonucu(yollar=secim, kanit=kanit, analizler=analizler)

    griler, gecerli = _griler(tum)
    if not griler:
        # Dosyalar VAR ama hicbiri acilamadi — bu bir ARIZA'dir, icerik gercegi
        # DEGIL. Bugun uretimde bu durum 'havuz_bos' ile ayni kutuda (spec 3.1).
        return SecimSonucu(kanit={"kare": 0, "acilamayan": len(tum)},
                           hata="kare_okunamadi")

    sonuc = havuz_mod.havuz_derle(griler)
    ekler = havuz_mod.ikinci_gecis(griler, sonuc)
    ist = {"kare": len(griler), "esik": sonuc.istatistik.esik,
           "grup": sonuc.istatistik.grup_sayisi, "alarm": sonuc.istatistik.alarm,
           "sayfa": len(sonuc.sayfalar), "ikinci_gecis_ek": len(ekler)}
    kanit: dict = {"havuz": ist, "acilamayan": len(tum) - len(gecerli)}

    havuzdan = [gecerli[i] for i in sorted(set(sonuc.sayfalar) | set(ekler))]
    if not havuzdan:
        # Kareler okundu ama temsilci cikmadi: hepsi iceriksiz (std < 3.0).
        # Bu ICERIK GERCEGI — METIN_YOK. Ariza degil.
        return SecimSonucu(kanit=kanit, hata="havuz_bos")

    secim, dusen = ornekle(havuzdan, int(ayar.get("tavan", 100)),
                           bool(ayar.get("son_kare_zorla", False)))
    secim, kuyruk_ek = ham_kuyruk_ekle(secim, tum, int(ayar.get("ham_kuyruk", 0)))
    kanit |= {"secilen_kare": len(secim), "dusurulen_n": dusen,
              "kuyruk_ek": kuyruk_ek}
    return SecimSonucu(yollar=secim, kanit=kanit)
