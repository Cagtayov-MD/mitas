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


def sec(kare_dizin: Path, ayar: dict, desen: str = "*.png") -> SecimSonucu:
    """Ham kare dizini → okunacak kareler + kanıt.

    `ayar`: {"tavan": int, "son_kare_zorla": bool, "ham_kuyruk": int}
    """
    kare_dizin = Path(kare_dizin)
    if not kare_dizin.is_dir():
        return SecimSonucu(hata="dizin_bos")
    tum = sorted(kare_dizin.glob(desen))
    if not tum:
        return SecimSonucu(hata="dizin_bos")

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
