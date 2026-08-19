"""N-kanal uzlastirma (1..3) + guven etiketi.

NEDEN N: 'tam iki paket' sarti gercege uymuyor — 76 bolumde LeBron
49 SUCCEEDED / 21 NO_CONTENT / 6 FAILED, yani %36'sinda hic satir yok
(olculdu 2026-08-19). Sabit iki kanal Shaq'i o bolumlerde calisamaz kilardi.

DEGISMEZLER:
  * Satir SILINMEZ. Her kanaldaki her benzersiz metin ciktida kalir.
  * Muhalif okuma saklanir; cogunluk karari DOGRULUK IDDIASI DEGIL, yalnizca
    guven seviyesidir — uc okuyucu ayni pikselleri okudugu icin ortak hataya
    da dusebilir.
  * 'Ayni' = normalize sonrasi BIREBIR esitlik. Fuzzy yakinlik ayni degildir:
    'UMIT' ile 'UMIT'(noktali) yakin ama biri yanlistir; ayni saymak yanlis
    yazimi sessizce kabul etmek olur.
  * Nash zorunlu kanaldir: bbox yalniz onda var (%100; lebron %1, jordan %0),
    kontrol kuyrugu onun koordinatlarina bagli.
"""
from __future__ import annotations

from typing import Any

from normalizasyon import normalize

CAPA = "nash"


def uzlastir(paketler: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Kanal adi -> okuma paketi. Her benzersiz satir icin bir karar dondurur."""
    kanal_metin: dict[str, dict[str, str]] = {}
    for kanal, paket in paketler.items():
        esle: dict[str, str] = {}
        for satir in (paket or {}).get("lines") or []:
            ham = str(satir.get("raw_text") or "").strip()
            if not ham:
                continue
            esle.setdefault(normalize(ham), ham)
        kanal_metin[kanal] = esle

    capa_var = CAPA in paketler
    tum_anahtarlar: list[str] = []
    for esle in kanal_metin.values():
        for anahtar in esle:
            if anahtar not in tum_anahtarlar:
                tum_anahtarlar.append(anahtar)

    sonuc: list[dict[str, Any]] = []
    for anahtar in tum_anahtarlar:
        diyen = {k: v[anahtar] for k, v in kanal_metin.items() if anahtar in v}
        demeyen = {k: v for k, v in kanal_metin.items() if anahtar not in v}
        muhalif: dict[str, str] = {}
        for kanal, esle in demeyen.items():
            if esle:
                muhalif[kanal] = next(iter(esle.values()))

        metin = next(iter(diyen.values()))
        if not capa_var:
            durum, guven = "COZUMSUZ", "dusuk"
        elif len(diyen) >= 3:
            durum, guven = "GECTI", "yuksek"
        elif len(diyen) == 2:
            durum, guven = "GECTI", "orta"
        elif len(diyen) == 1 and len(paketler) == 1:
            durum, guven = "GECTI", "dusuk"
        else:
            durum, guven = "KONTROL_BEKLIYOR", "dusuk"

        sonuc.append({"metin": metin, "durum": durum, "guven": guven,
                      "kanallar": diyen,
                      "muhalif": muhalif if durum == "GECTI" else {}})
    return sonuc
