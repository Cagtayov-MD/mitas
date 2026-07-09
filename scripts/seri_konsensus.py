#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""seri_konsensus.py — dizi modu: ilk-N bölüm okumasından seri-master gövdesi (SAF motor).

Sözleşme: scripts/dizi_SISTEM.md → "Konsensüs kuralları" + "seri_master.json şeması"
+ "TEKİL alanlar". Bu modül IO YAPMAZ (dosya/duckdb/ağ yok); tek dış bağımlılık iki
saf kardeş modüldür: credit_crosscheck (fold/name_match/name_close) ve
credit_text_read (_looks_garble). Depo yazımı seri_kayit'in, kilit basmak çağıranın işidir.

KB ARAYÜZÜ (duck-typing — kb None-safe, None = KB'siz):
    kb.kanonik_yazim(adaylar: list[str]) -> str | None
      adaylar içinden KB'nin tanıdığı/tercih ettiği yazımı döndürür; hiçbirini
      tanımıyorsa None. Dönen değer fold-eşitliğiyle adaylardan birine eşlenir;
      eşlenemezse yok sayılır (KB asla listede olmayan bir yazım DAYATAMAZ).

İnce kararlar (sözleşmede açık olmayan, muhafazakâr yorum — raporlandı):
  • kb_teyit: KB verildiyse ve SEÇİLEN kanonik yazımı KB tanıyorsa True — yalnız
    beraberlik-çözümünde değil; kur_master'ın "tek tanık KB-teyitli → ZAYIF" kuralı
    tek-adaylı teyide muhtaçtır.
  • TEKİL alanda birden çok KB-teyitli tek-tanık küme = ÇELİŞKİ → alan yazılMAZ
    ("okunamadı > yanlış oku").
  • Eşiği aşamayan HER küme (TEKİL/CAST/teknik) alan bilgisiyle aday_havuzu'na düşer;
    anahtar çakışmasında İLK yazan kalır (işleme sırası: TEKİL → CAST → teknik_ekip).
  • CAST N≥3'te yalnız N/N=AKTIF ve N-1/N=ZAYIF_UYE girer; aradaki sayımlar
    (ör. 3/5) sözleşmede tanımsız → muhafazakâr: aday_havuzu.
  • Tanık sayımı bölüm-bazlıdır: bir bölüm aynı yazıma en çok 1 tanık verir
    (OCR çift-satır tekrarı oy şişirmesin).
  • Madde 8 (eş-görünüm vetosu): tanık kaydı kenar-testinin ÖNÜNE alındı ki yeni
    düğümün bölümü vetoya görünsün; reddedilen kenar sessizce atlanır ve kenarlar
    yalnız düğüm-doğumunda test edildiğinden sonradan yeniden denenMEZ.
  • Madde 9 (unvan-strip) YALNIZ isim_kumele kenar-testinde uygulanır — kur_master
    konuk-savunması (name_match) ve kanonik_sec KB fold-eşlemesi ORİJİNAL yazımla
    çalışmaya devam eder (sözleşme "kümeleme kenar-testi" der; muhafazakâr yorum).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import credit_crosscheck as cc     # fold / name_match / name_close — saf
import credit_text_read as ctr     # _looks_garble — saf (import-time yan etki yok)

# dizi_SISTEM.md "TEKİL alanlar" — kalanı teknik_ekip'e, CAST oyunculara gider
TEKIL_ALANLAR = ("Yönetmen", "Yapımcı", "Senaryo", "Müzik", "Görüntü Yönetmeni", "Kurgu")


# ---------------------------------------------------------------- union-find

def _kok(ebeveyn: list[int], i: int) -> int:
    while ebeveyn[i] != i:
        ebeveyn[i] = ebeveyn[ebeveyn[i]]   # yol-sıkıştırma
        i = ebeveyn[i]
    return i


def _birlestir(ebeveyn: list[int], i: int, j: int, kok_bolumler: list[set]) -> None:
    ri, rj = _kok(ebeveyn, i), _kok(ebeveyn, j)
    if ri == rj:
        return
    # Madde 8 — eş-görünüm vetosu: iki kümenin bölüm kümeleri KESİŞİYORSA birleştirme
    # yapılmaz (aynı bölümde birlikte tanıklanan iki farklı yazım = iki kişi kanıtı).
    # Reddedilen kenar sessizce atlanır — hata üretilmez.
    if kok_bolumler[ri] & kok_bolumler[rj]:
        return
    # KISIT: küçük indeks kök kalır → küme sırası ilk-görülmeye sabitlenir (determinizm)
    if ri > rj:
        ri, rj = rj, ri
    ebeveyn[rj] = ri
    kok_bolumler[ri] |= kok_bolumler[rj]


# ------------------------------------------- Madde 9 — unvan-strip (yalnız karşılaştırma)

# Akademik unvan token'ları (fold sonrası karşılaştırılır; DOÇ→"doc" fold'la birleşir).
# BEY/HANIM/PAŞA bilinçli LİSTE-DIŞI (soyadı riski — dizi_SISTEM.md Madde 9).
_UNVAN_FOLD = frozenset(("dr", "prof", "doc", "yrd", "op", "av", "dt"))


def _unvan_soy(yazim: str) -> str:
    """Baştaki akademik unvan token'larını soy — YALNIZ eşleşme kararı için (Madde 9).

    Nokta/birleşik varyantlar tanınır ("DR.", "PROF DR", "YRD DOÇ DR", "OP.DR." …):
    bir boşluk-token'ının nokta-parçalarının TÜMÜ fold sonrası unvansa o token soyulur;
    ard arda birden çok unvan token'ı soyulur, ilk unvan-olmayan token'da durulur.
    Soyma SONUCU boş/tek-token kalırsa ORİJİNAL döner (aşırı-soyma freni).
    Kaydedilen/basılan yazımlara ASLA uygulanmaz (OCR-otorite) — çağıran yalnız
    kenar-testinde kullanır; düğüm/yazimlar/kanonik hep orijinal yazımda kalır.
    """
    parcalar = yazim.split()
    i = 0
    while i < len(parcalar):
        alt = [p for p in parcalar[i].split(".") if p]      # "OP.DR." → ["OP", "DR"]
        if alt and all(cc.fold(p) in _UNVAN_FOLD for p in alt):
            i += 1
        else:
            break
    if i == 0 or len(parcalar) - i < 2:
        return yazim
    return " ".join(parcalar[i:])


def isim_kumele(tanikliklar: list[tuple[int, str]]) -> list[dict]:
    """[(bolum_no, yazim)] → union-find kümeleri.

    Kenar yüklemi SÖZLEŞMEDEKİ gibi name_match(a, b) or name_close(a, b) + iki yama:
      • Madde 9 (unvan-strip): kenar-testine giren yazımların BAŞINDAKİ akademik unvan
        token'ları soyulur (_unvan_soy) — YALNIZ eşleşme kararında; düğümler, yazimlar
        anahtarları ve kanonik seçim hep ORİJİNAL yazımla kalır.
      • Madde 8 (eş-görünüm vetosu): iki kümenin bölüm kümeleri KESİŞİYORSA kenar
        ATLANIR (aynı bölümde birlikte tanıklanan iki farklı yazım = iki kişi kanıtı).
        Bu yüzden tanık kaydı kenar-testinden ÖNCE işlenir (yeni düğümün bölümü vetoya
        görünür); kenarlar yalnız düğüm ilk görüldüğünde test edilir — sonradan gelen
        tanıklar reddedilmiş kenarı yeniden AÇMAZ.

    Birebir aynı yazım tek düğümdür; boş/boşluk yazım atlanır; aynı (bölüm, yazım)
    çifti ikinci kez tanık SAYILMAZ.

    Dönüş: [{"yazimlar": {yazim: tanik_sayisi}, "bolumler": artan-sıralı liste}]
    — küme sırası ve küme-içi yazım sırası deterministik: ilk görülme.
    """
    dugumler: list[str] = []
    kiyaslar: list[str] = []          # Madde 9: unvan-soyulmuş karşılaştırma yazımları
    dugum_ix: dict[str, int] = {}
    sayac: list[int] = []
    bolum_kume: list[set] = []
    ebeveyn: list[int] = []
    kok_bolumler: list[set] = []      # Madde 8: kök (küme) başına bölüm-kümesi bakımı
    gorulen: set = set()

    for bolum, yazim in tanikliklar:
        yz = (yazim or "").strip()
        if not yz:
            continue
        ix = dugum_ix.get(yz)
        yeni_dugum = ix is None
        if yeni_dugum:
            ix = len(dugumler)
            dugum_ix[yz] = ix
            dugumler.append(yz)
            kiyaslar.append(_unvan_soy(yz))
            sayac.append(0)
            bolum_kume.append(set())
            ebeveyn.append(ix)
            kok_bolumler.append(set())
        if (bolum, yz) not in gorulen:
            gorulen.add((bolum, yz))
            sayac[ix] += 1
            bolum_kume[ix].add(bolum)
            kok_bolumler[_kok(ebeveyn, ix)].add(bolum)   # veto küme-bölümlerini güncel görsün
        if yeni_dugum:
            for i in range(ix):
                if cc.name_match(kiyaslar[i], kiyaslar[ix]) or cc.name_close(kiyaslar[i], kiyaslar[ix]):
                    _birlestir(ebeveyn, i, ix, kok_bolumler)

    kumeler: dict[int, dict] = {}
    sira: list[int] = []
    for ix, yz in enumerate(dugumler):
        r = _kok(ebeveyn, ix)
        if r not in kumeler:
            kumeler[r] = {"yazimlar": {}, "bolumler": set()}
            sira.append(r)
        kumeler[r]["yazimlar"][yz] = sayac[ix]
        kumeler[r]["bolumler"].update(bolum_kume[ix])
    return [{"yazimlar": kumeler[r]["yazimlar"], "bolumler": sorted(kumeler[r]["bolumler"])}
            for r in sira]


# ---------------------------------------------------------------- kanonik seçim

def kanonik_sec(kume: dict, kb=None) -> tuple[str, bool]:
    """Küme içinden kanonik yazımı seç → (kanonik_yazim, kb_teyit).

    Sıra dizi_SISTEM.md'deki gibi:
      (1) rakam içeren yazım rakamsıza HER ZAMAN kaybeder (hepsi rakamlıysa eleme yok),
      (2) çoğunluk (toplam tanık sayısı),
      (3) beraberlikte KB yazımı → kb_teyit=True,
      (4) garble-siz olan (_looks_garble is None),
      (5) ilk bölümdeki (küme yazımları ilk-görülme sıralı geldiğinden ilk anahtar).

    kb_teyit: KB verildiyse ve seçilen yazımı KB tanıyorsa True — beraberlik olmasa da
    (kur_master'ın "tek tanık KB-teyitli → ZAYIF" kuralı bu teyide dayanır). KB arayüzü
    modül docstring'inde; kb=None güvenlidir (hiç çağrılmaz, kb_teyit=False).
    """
    yazimlar: dict = kume.get("yazimlar") or {}
    adaylar = list(yazimlar.keys())
    if not adaylar:
        raise ValueError("kanonik_sec: bos kume (yazimlar yok)")

    # (1) rakam cezası — çoğunluktan ÖNCE: rakamlı yazım oy sayısıyla kazanamaz
    rakamsiz = [a for a in adaylar if not any(ch.isdigit() for ch in a)]
    if rakamsiz:
        adaylar = rakamsiz

    # (2) çoğunluk
    if len(adaylar) > 1:
        tepe = max(yazimlar[a] for a in adaylar)
        adaylar = [a for a in adaylar if yazimlar[a] == tepe]

    # (3) beraberlikte KB — dönen yazım fold-eşitliğiyle adaylardan birine eşlenmeli
    if len(adaylar) > 1 and kb is not None:
        secim = kb.kanonik_yazim(list(adaylar))
        if secim:
            eslesen = [a for a in adaylar if cc.fold(a) == cc.fold(secim)]
            if eslesen:
                return eslesen[0], True

    # (4) garble-siz — hepsi garble ise eleme yapılmaz (bir aday kalmalı)
    if len(adaylar) > 1:
        temiz = [a for a in adaylar if ctr._looks_garble(a) is None]
        if temiz:
            adaylar = temiz

    # (5) ilk görülme
    kanonik = adaylar[0]
    kb_teyit = False
    if kb is not None:
        secim = kb.kanonik_yazim([kanonik])
        kb_teyit = bool(secim) and cc.fold(secim) == cc.fold(kanonik)
    return kanonik, kb_teyit


# ---------------------------------------------------------------- master kurulumu

def kur_master(okumalar: list[dict], *, seri_adi: str, seri_anahtar: str,
               kaynak_klasor: str = "", kb=None, simdi: str = "") -> dict:
    """Tohum BolumOkuma listesinden seri_master gövdesi kur (durum=BUILDING bırakılır;
    kilit olayını ve depo yazımını ÇAĞIRAN basar — bu motor saf kalır).

    Eşikler (N = tohum sayısı):
      TEKİL alan  : ≥2 bölüm-tanıklı küme(ler) kanonik (1 küme=KESIN, çok=COKLU);
                    hiç yoksa TEK KB-teyitli tek-tanık → ZAYIF, değilse alan yazılMAZ.
      CAST        : N/N → AKTIF; N-1/N → ZAYIF_UYE (yalnız N≥3); kalanı → aday_havuzu.
      teknik_ekip : ≥2 bölüm-tanık → girer; tek-tanık → aday_havuzu.
      N=2         : eşikler 2/2, ZAYIF_UYE yok. N=1: her şey girer, alan guven=TEK_TANIK.
    Tohumdaki konuk_acik isimleri konsensüse GİRMEZ → konuk_gecmisi'ne yazılır
    (cast listesine sızmışsa name_match ile savunmalı düşülür).
    tanik_kayitlari/surum_gecmisi BOŞ bırakılır: content_hash ve kilit IO'su çağıranın işi.
    """
    okumalar = sorted(list(okumalar or []), key=lambda o: o.get("bolum_no") or 0)
    n = len(okumalar)
    alt_esik = 2 if n >= 2 else 1     # TEKİL + teknik_ekip "≥2 tanık" eşiği (N=1'de hepsi girer)

    aday_havuzu: dict = {}

    def _aday_ekle(alan: str, kume: dict) -> None:
        # eşiği aşamayan küme kaybedilmez; anahtar çakışmasında ilk yazan kalır
        kanonik, _ = kanonik_sec(kume, kb)
        if kanonik not in aday_havuzu:
            aday_havuzu[kanonik] = {"alan": alan,
                                    "bolumler": kume["bolumler"],
                                    "yazimlar": kume["yazimlar"]}

    # ---- konuk_acik → konuk_gecmisi (konsensüs havuzuna GİRMEZ)
    konuk_tanik: list[tuple[int, str]] = []
    for o in okumalar:
        for isim in o.get("konuk_acik") or []:
            konuk_tanik.append((o.get("bolum_no"), isim))
    konuk_gecmisi: dict = {}
    for kume in isim_kumele(konuk_tanik):
        kanonik, _ = kanonik_sec(kume, kb)
        konuk_gecmisi[kanonik] = {"bolumler": kume["bolumler"], "yazimlar": kume["yazimlar"]}

    # ---- TEKİL alanlar
    alanlar: dict = {}
    for alan in TEKIL_ALANLAR:
        tanik = [(o.get("bolum_no"), isim)
                 for o in okumalar
                 for isim in (o.get("crew") or {}).get(alan) or []]
        if not tanik:
            continue
        kumeler = isim_kumele(tanik)
        kazanan = [k for k in kumeler if len(k["bolumler"]) >= alt_esik]
        kaybeden = [k for k in kumeler if len(k["bolumler"]) < alt_esik]
        if kazanan:
            # N=1'de sözleşme gereği güven her koşulda TEK_TANIK (COKLU'yu bile ezer)
            guven = "TEK_TANIK" if n == 1 else ("KESIN" if len(kazanan) == 1 else "COKLU")
            kanonikler, teyitler, tanik_map = [], [], {}
            for k in kazanan:
                kanonik, teyit = kanonik_sec(k, kb)
                kanonikler.append(kanonik)
                teyitler.append(teyit)
                tanik_map[kanonik] = {"bolumler": k["bolumler"], "yazimlar": k["yazimlar"]}
            alanlar[alan] = {"kanonik": kanonikler, "guven": guven,
                             "kb_teyit": bool(teyitler) and all(teyitler),
                             "tanik": tanik_map}
            for k in kaybeden:
                _aday_ekle(alan, k)
        else:
            # hepsi tek-tanık: YALNIZ tek bir KB-teyitli küme ZAYIF girer;
            # 0 teyit veya >1 teyit (çelişki) → alan yazılMAZ ("okunamadı > yanlış oku")
            teyitli = []
            for k in kumeler:
                kanonik, teyit = kanonik_sec(k, kb)
                if teyit:
                    teyitli.append((k, kanonik))
            if len(teyitli) == 1:
                k, kanonik = teyitli[0]
                alanlar[alan] = {"kanonik": [kanonik], "guven": "ZAYIF", "kb_teyit": True,
                                 "tanik": {kanonik: {"bolumler": k["bolumler"],
                                                     "yazimlar": k["yazimlar"]}}}
                for x in kumeler:
                    if x is not k:
                        _aday_ekle(alan, x)
            else:
                for x in kumeler:
                    _aday_ekle(alan, x)

    # ---- CAST (oyuncular) — konuk savunması + ilk-görünme konumu (sira için)
    cast_tanik: list[tuple[int, str]] = []
    ilk_konum: dict[str, tuple[int, int]] = {}   # yazım → (bölüm-sırası, bölüm-içi konum)
    for b_ix, o in enumerate(okumalar):
        konuklar = o.get("konuk_acik") or []
        konum = 0
        for isim in o.get("cast") or []:
            # BolumOkuma cast'i konuk-düşülmüş gelir; sızıntıya karşı ikinci kapı (name_match)
            if any(cc.name_match(isim, kx) for kx in konuklar):
                continue
            cast_tanik.append((o.get("bolum_no"), isim))
            yz = (isim or "").strip()
            if yz and yz not in ilk_konum:
                ilk_konum[yz] = (b_ix, konum)
            konum += 1

    girenler: list[tuple[tuple[int, int], dict, str]] = []
    for kume in isim_kumele(cast_tanik):
        bolum_sayisi = len(kume["bolumler"])
        if n >= 1 and bolum_sayisi >= n:
            durum = "AKTIF"                      # N/N (N=1'de "hepsi girer" buna düşer)
        elif n >= 3 and bolum_sayisi == n - 1:
            durum = "ZAYIF_UYE"                  # N-1/N — N=2'de ZAYIF_UYE YOK
        else:
            _aday_ekle("oyuncular", kume)
            continue
        anahtar = min(ilk_konum.get(yz, (n, 10 ** 9)) for yz in kume["yazimlar"])
        girenler.append((anahtar, kume, durum))
    girenler.sort(key=lambda uc: uc[0])

    oyuncular: dict = {}
    for sira_ix, (_, kume, durum) in enumerate(girenler):
        kanonik, teyit = kanonik_sec(kume, kb)
        oyuncular[kanonik] = {
            "yazimlar": kume["yazimlar"],
            "bolumler": kume["bolumler"],
            "sira": sira_ix,
            "kb_teyit": teyit,
            "durum": durum,
            "son_gorulme": max(kume["bolumler"]),
            "ardisik_yok": 0,
            "ayrilma_bolumu": None,
        }

    # ---- teknik_ekip (TEKİL-dışı crew rolleri; rol sırası ilk görülme)
    teknik_ekip: dict = {}
    roller: list[str] = []
    for o in okumalar:
        for rol in (o.get("crew") or {}):
            if rol not in TEKIL_ALANLAR and rol not in roller:
                roller.append(rol)
    for rol in roller:
        tanik = [(o.get("bolum_no"), isim)
                 for o in okumalar
                 for isim in (o.get("crew") or {}).get(rol) or []]
        for kume in isim_kumele(tanik):
            if len(kume["bolumler"]) >= alt_esik:
                kanonik, _ = kanonik_sec(kume, kb)
                teknik_ekip.setdefault(rol, {})[kanonik] = {
                    "yazimlar": kume["yazimlar"], "bolumler": kume["bolumler"]}
            else:
                _aday_ekle(rol, kume)

    # ---- gövde (seri_master.json şeması; IO alanları çağırana bırakılır)
    on_ekler: list[str] = []
    for o in okumalar:
        parcalar = (o.get("trt_id") or "").strip().split("-")
        if len(parcalar) >= 3:
            on_ek = "-".join(parcalar[:3])       # bölüm parseli maskelenir (ilk 3 parsel)
            if on_ek not in on_ekler:
                on_ekler.append(on_ek)
    kilit_bolumler = [o.get("bolum_no") for o in okumalar]

    return {
        "surum_sema": 1,
        "seri_anahtar": seri_anahtar,
        "seri_adi": seri_adi,
        "kaynak_klasor": kaynak_klasor,
        "trt_on_ekler": on_ekler,
        "durum": "BUILDING",                     # kilidi çağıran basar
        "master_surum": 1,
        "kilit_bolumler": kilit_bolumler,
        "surum_gecmisi": [],                     # "kilit" olayını çağıran ekler
        "alanlar": alanlar,
        "oyuncular": oyuncular,
        "teknik_ekip": teknik_ekip,
        "aday_havuzu": aday_havuzu,
        "konuk_gecmisi": konuk_gecmisi,
        "bekleyen_degisimler": [],
        "format_kopusu": {"ardisik": 0, "ilk_bolum": None},
        "tanik_kayitlari": {},                   # content_hash IO'su çağıranın işi
        "guncelleme": {"ts": simdi, "modul": "seri_konsensus",
                       "bolum": kilit_bolumler[-1] if kilit_bolumler else None},
    }
