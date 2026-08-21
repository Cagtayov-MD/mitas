#!/usr/bin/env python3
"""puan.py — GT metni ile okuma çıktısını SATIR DÜZEYİNDE karşılaştırır.

Bu dosya Vince Carter'ın **ölçüm aletidir**; okuma motoru değildir. Motor
değişse de bu alet değişmez — "ölçüm yapılmadan hiçbir eşik/kanal iyileştirme
sayılmaz" kuralının (docs/PLAN.md §7.5) somut karşılığı.

TEMEL KURAL: normalizasyon YALNIZ karşılaştırma içindir. Çıktı metni asla
değiştirilmez — raporlarda her zaman HAM satır gösterilir.

Hizalama (docs/PLAN.md §4):
  1. difflib.SequenceMatcher ile sıra-korumalı hizalama → eşleşen bloklar
     = BİREBİR (normalize eşit).
  2. Hizalanmayan boşluklarda yerel bulanık tur: benzerlik ≥ eşik (varsayılan
     0.90). Diakritik-katlanmış ve boşluksuz varyantlar da denenir → YAKIN.
     Bir GT satırı yalnız bir kez eşleşir.
  3. Kalan GT satırı = KAYIP (en pahalı hata).
     Kalan çıktı satırı = FAZLA (uydurma adayı).

Kullanım:
    puan.py --gt <dosya> --cikti <dosya> [--fark-dokumu]
    puan.py --yatak [olcum/yatak.json] --cikti-kok out/
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent

VARSAYILAN_ESIK = 0.90          # YAKIN sayılma eşiği (docs/PLAN.md §4)
VARSAYILAN_ESIK_ALTI = 0.70     # KAYIP sebep ayrımı: "bozuk okundu" vs "hiç yok"

# --------------------------------------------------------------------------
# Normalizasyon — YALNIZ karşılaştırma için
# --------------------------------------------------------------------------

# Türkçe casefold: str.lower() YANLIŞ sonuç verir.
#   "İ".lower() -> "i̇"  (i + U+0307 birleşen nokta) — sahte karakter
#   "I".lower() -> "i"   — Türkçe'de "ı" olmalı
# Bu yüzden özel tablo ÖNCE uygulanır, kalanı .lower()'a bırakılır.
_CASEFOLD_TABLOSU = str.maketrans({"İ": "i", "I": "ı"})

# Diakritik katlama — YALNIZ eşleştirme katmanında (konsey kararı 6).
# Çıktı metnine dokunmaz; "MÜZEYYEN" ile "MUZEYVEN" bu tablo sayesinde
# birbirine yaklaşır ama rapor yine HAM hâlini gösterir.
_KATLAMA_TABLOSU = str.maketrans({
    "ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c",
    "â": "a", "î": "i", "û": "u", "ê": "e", "ô": "o",
})


def turkce_casefold(s: str) -> str:
    """Türkçe-doğru küçük harfe çevirme (İ→i, I→ı), sonra standart lower."""
    return s.translate(_CASEFOLD_TABLOSU).lower()


def diakritik_katla(s: str) -> str:
    """Eşleştirme için diakritik denklik: ı↔i, ş↔s, ğ↔g, ü↔u, ö↔o, ç↔c, â↔a…"""
    return s.translate(_KATLAMA_TABLOSU)


def normalize(s: str) -> str:
    """Baş/son boşluk kırp + iç boşlukları teke indir + Türkçe casefold."""
    return " ".join(turkce_casefold(s).split())


def bosluksuz(s: str) -> str:
    """Hata sınıfı ④ için: 'SEDA CANPOL A T' ↔ 'SEDA CANPOLAT'."""
    return "".join(s.split())


def anlamli_satir_mi(ham: str) -> bool:
    """'#' ile başlayan yorum satırları ve boş satırlar ölçüme girmez."""
    s = ham.strip()
    return bool(s) and not s.startswith("#")


@dataclass
class Satir:
    """Bir satırın ham hâli + karşılaştırma varyantları. `ham` ASLA değişmez.

    `sira` = SÜZÜLMÜŞ listedeki konum (hizalama indeksleriyle birebir aynı).
    `kaynak_satir` = dosyadaki gerçek satır numarası (1'den başlar) — yorum
    ve boş satırlar atıldığı için ikisi birbirinden farklıdır; raporda insana
    dosya satırını göstermek için ayrı tutulur.
    """
    ham: str
    sira: int
    sinif: str | None = None          # yalnız vince.json girdilerinde
    kaynak_satir: int | None = None
    norm: str = field(init=False)
    katlanmis: str = field(init=False)
    bosluksuz_norm: str = field(init=False)
    bosluksuz_katlanmis: str = field(init=False)

    def __post_init__(self) -> None:
        self.norm = normalize(self.ham)
        self.katlanmis = diakritik_katla(self.norm)
        self.bosluksuz_norm = bosluksuz(self.norm)
        self.bosluksuz_katlanmis = bosluksuz(self.katlanmis)


def _oran(a: str, b: str, kesme: float) -> float:
    """Ucuzdan pahalıya kaskad — büyük yataklarda O(n*m) taramayı taşınabilir
    kılar.

    real_quick_ratio/quick_ratio gerçek orana ÜST SINIRDIR: üst sınır `kesme`
    altındaysa gerçek oran da altındadır, pahalı ratio() hiç çağrılmaz. Bu
    yüzden ">= kesme mi?" sorusunun cevabı KESİNDİR; `kesme` altındaki değerler
    ise yalnızca üst-sınır tahminidir. Çağıran, kullanacağı TÜM eşiklerin en
    küçüğünü `kesme` olarak vermek zorundadır — yoksa eşiğin altındaki bir
    tahmin yanlışlıkla eşleşme sayılabilir.
    """
    if not a or not b:
        return 0.0
    sm = SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < kesme:
        return sm.real_quick_ratio()
    if sm.quick_ratio() < kesme:
        return sm.quick_ratio()
    return sm.ratio()


def benzerlik(a: Satir, b: Satir,
              kesme: float = VARSAYILAN_ESIK_ALTI) -> tuple[float, str]:
    """En iyi varyant skoru + hangi varyantın kazandığı.

    Dört varyant denenir; kazanan varyant YAKIN eşleşmelerin SEBEBİNİ verir:
      norm      → yazım/genel bulanıklık
      katlanmis → diakritik kusuru (③ İ→I çöküşü dâhil)
      bosluksuz → kelime ortası boşluk (④)
    """
    adaylar = (
        (_oran(a.norm, b.norm, kesme), "YAZIM"),
        (_oran(a.katlanmis, b.katlanmis, kesme), "DIAKRITIK"),
        (_oran(a.bosluksuz_norm, b.bosluksuz_norm, kesme), "BOSLUK"),
        (_oran(a.bosluksuz_katlanmis, b.bosluksuz_katlanmis, kesme),
         "DIAKRITIK_BOSLUK"),
    )
    return max(adaylar, key=lambda t: t[0])


# --------------------------------------------------------------------------
# Okuma — .txt veya vince.json
# --------------------------------------------------------------------------

def satirlari_oku(yol: str | Path) -> list[Satir]:
    """Düz metin ya da vince.json'dan Satir listesi üretir.

    vince.json ise `satirlar[].sinif` korunur (sınıf bazlı rapor için).
    ARIZA/METIN_YOK durumundaki bir vince.json boş liste verir — bu bir hata
    değil, ölçülebilir bir gerçektir (o koşu hiçbir satır üretmemiştir).
    """
    p = Path(yol)
    metin = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        veri = json.loads(metin)
        ham_satirlar = veri.get("satirlar") or []
        ciftler = []
        for i, s in enumerate(ham_satirlar, start=1):
            if isinstance(s, dict):
                m, sinif = str(s.get("metin", "")), s.get("sinif")
            else:
                m, sinif = str(s), None
            if anlamli_satir_mi(m):
                ciftler.append((m, sinif, i))
    else:
        ciftler = [(s, None, i)
                   for i, s in enumerate(metin.splitlines(), start=1)
                   if anlamli_satir_mi(s)]
    # `sira` SÜZME SONRASI verilir: hizalama indeksleriyle birebir örtüşmeli,
    # yoksa sinif_raporu yanlış satırı sorgular (atılan yorum satırları kadar
    # kayar).
    return [Satir(ham=m, sira=k, sinif=sinif, kaynak_satir=ks)
            for k, (m, sinif, ks) in enumerate(ciftler)]


# --------------------------------------------------------------------------
# Hizalama
# --------------------------------------------------------------------------

@dataclass
class Hizalama:
    birebir: list[tuple[int, int]] = field(default_factory=list)
    # (gt_indeks, cikti_indeks, skor, varyant)
    yakin: list[tuple[int, int, float, str]] = field(default_factory=list)
    kayip: list[int] = field(default_factory=list)
    fazla: list[int] = field(default_factory=list)


def hizala(gt: list[Satir], ck: list[Satir],
           esik: float = VARSAYILAN_ESIK) -> Hizalama:
    """Sıra-korumalı hizalama + boşluklarda yerel bulanık tur."""
    h = Hizalama()
    sm = SequenceMatcher(None, [s.norm for s in gt], [s.norm for s in ck],
                         autojunk=False)  # autojunk sık geçen rol adlarını
                                          # "çöp" sayıp hizalamayı bozardı
    bosluklar: list[tuple[range, range]] = []
    for etiket, i1, i2, j1, j2 in sm.get_opcodes():
        if etiket == "equal":
            h.birebir.extend((i1 + k, j1 + k) for k in range(i2 - i1))
        else:
            bosluklar.append((range(i1, i2), range(j1, j2)))

    for gt_araligi, ck_araligi in bosluklar:
        # Boşluk içinde tüm çiftleri puanla, en iyiden başlayarak açgözlü ata.
        # Yerel tutulur (global değil): jenerik ekran sırasıyla akar, uzak bir
        # eşleşme kanıt değil gürültüdür.
        adaylar = []
        for gi in gt_araligi:
            for ci in ck_araligi:
                skor, varyant = benzerlik(gt[gi], ck[ci], kesme=esik)
                if skor >= esik:
                    adaylar.append((skor, gi, ci, varyant))
        # Deterministik sıralama: yüksek skor, sonra sıra numarası.
        adaylar.sort(key=lambda t: (-t[0], t[1], t[2]))
        tutulan_gt, tutulan_ck = set(), set()
        for skor, gi, ci, varyant in adaylar:
            if gi in tutulan_gt or ci in tutulan_ck:
                continue          # bir GT satırı YALNIZ bir kez eşleşir
            tutulan_gt.add(gi)
            tutulan_ck.add(ci)
            h.yakin.append((gi, ci, round(skor, 4), varyant))
        h.kayip.extend(gi for gi in gt_araligi if gi not in tutulan_gt)
        h.fazla.extend(ci for ci in ck_araligi if ci not in tutulan_ck)

    h.yakin.sort(key=lambda t: t[0])
    h.kayip.sort()
    h.fazla.sort()
    return h


# --------------------------------------------------------------------------
# Metrikler
# --------------------------------------------------------------------------

def _bol(pay: float, payda: float) -> float | None:
    """Tanımsız oranı 0.0 diye raporlamak YALAN olur — None döner ('ölçülmedi')."""
    return None if payda == 0 else pay / payda


def metrikler(h: Hizalama, gt: list[Satir], ck: list[Satir]) -> dict:
    birebir, yakin = len(h.birebir), len(h.yakin)
    tutan = birebir + yakin
    kesinlik = _bol(tutan, len(ck))
    duyarlilik = _bol(tutan, len(gt))
    if kesinlik is None or duyarlilik is None or (kesinlik + duyarlilik) == 0:
        f1 = None if (kesinlik is None or duyarlilik is None) else 0.0
    else:
        f1 = 2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)
    return {
        "birebir": birebir, "yakin": yakin,
        "kayip": len(h.kayip), "fazla": len(h.fazla),
        "gt_toplam": len(gt), "cikti_toplam": len(ck),
        "kesinlik": None if kesinlik is None else round(kesinlik, 4),
        "duyarlilik": None if duyarlilik is None else round(duyarlilik, 4),
        "f1": None if f1 is None else round(f1, 4),
    }


def sinif_raporu(h: Hizalama, ck: list[Satir]) -> dict | None:
    """Konsey kararı 7 — SINIF BAZLI DOĞRULUK.

    "SÜPHELİ'ye attığım satırlar GERÇEKTE doğru muydu?" — mimarinin recall'ı
    sessizce kırıp kırmadığının tek dürüst ölçüsü. Her sınıf için: kaç satır
    üretildi, kaçının GT'de karşılığı var.

    Çıktıda hiç `sinif` alanı yoksa (düz .txt) None döner — uydurma sınıf
    üretmez.
    """
    if not any(s.sinif for s in ck):
        return None
    birebir_ck = {ci for _, ci in h.birebir}
    yakin_ck = {ci for _, ci, _, _ in h.yakin}
    rapor: dict[str, dict] = {}
    for s in ck:
        ad = s.sinif or "SINIFSIZ"
        d = rapor.setdefault(ad, {"toplam": 0, "birebir": 0, "yakin": 0,
                                  "gt_karsiligi_yok": 0})
        d["toplam"] += 1
        if s.sira in birebir_ck:
            d["birebir"] += 1
        elif s.sira in yakin_ck:
            d["yakin"] += 1
        else:
            d["gt_karsiligi_yok"] += 1
    for d in rapor.values():
        d["gt_karsiligi_var"] = d["birebir"] + d["yakin"]
        d["dogruluk"] = round(d["gt_karsiligi_var"] / d["toplam"], 4)
    return rapor


# --------------------------------------------------------------------------
# Fark dökümü — sebep sayaçları
# --------------------------------------------------------------------------

# Model meta-yorumu belirteçleri. Bunlar jenerik satırı DEĞİL, okuyucunun
# kendi cümlesidir (ör. gt_dizi/.../cikis_referans_8b.txt son satırı:
# "There is no visible credit text in the provided images...").
# YÜKSEK KESİNLİK tercih edildi: az yakalamak, yanlış yakalamaktan iyidir.
_MOTOR_NOTU_BELIRTECLERI = (
    "no credit text", "no visible credit", "not visible", "provided image",
    "the images are", "there is no", "i cannot", "i'm unable", "i am unable",
    "as an ai", "appears to be blank", "no discernible text",
)


def _motor_notu_mu(s: Satir) -> bool:
    d = s.norm
    return any(b in d for b in _MOTOR_NOTU_BELIRTECLERI)


def fark_dokumu(h: Hizalama, gt: list[Satir], ck: list[Satir],
                esik: float = VARSAYILAN_ESIK,
                esik_alti: float = VARSAYILAN_ESIK_ALTI) -> dict:
    """Her KAYIP/FAZLA/YAKIN satırı SEBEBİYLE sınıflandırır.

    Ham F1 "ne kadar kötü" der; bu döküm "NEDEN kötü" der — hangi hata sınıfına
    (docs/PLAN.md §0 tablosu) yatırım yapılacağını sayıyla söyler.

    FAZLA sebepleri:
      MOTOR_NOTU       modelin kendi cümlesi, jenerik satırı değil
      TEKRAR           aynı normalize metin çıktıda zaten var (⑤ kekeleme)
      GT_DISI_ESLESME  GT'de var ama BAŞKA yerde — hizalama kayması / rol
                       kayması (②) adayı, saf uydurma değil
      UYDURMA_ADAYI    GT'nin hiçbir yerinde karşılığı yok (① adayı)

    KAYIP sebepleri:
      ESIK_ALTI  çıktıda benzeri var ama eşiğin altında (bozuk okunmuş)
      HIC_YOK    çıktıda hiçbir benzeri yok (hiç okunmamış)
    """
    sayac: dict[str, int] = {}
    detay: dict[str, list] = {"yakin": [], "fazla": [], "kayip": []}

    def _say(anahtar: str) -> None:
        sayac[anahtar] = sayac.get(anahtar, 0) + 1

    # --- YAKIN: neden BİREBİR değildi? -------------------------------------
    for gi, ci, skor, varyant in h.yakin:
        _say(f"YAKIN_{varyant}")
        detay["yakin"].append({
            "gt": gt[gi].ham, "cikti": ck[ci].ham,
            "skor": skor, "sebep": varyant,
        })

    # --- FAZLA: neden çıktıda var ama GT'de yok? ---------------------------
    gorulen_norm: dict[str, int] = {}
    for s in ck:
        gorulen_norm[s.norm] = gorulen_norm.get(s.norm, 0) + 1
    eslesmis_ck = {ci for _, ci in h.birebir} | {ci for _, ci, _, _ in h.yakin}
    gt_norm_kumesi = {s.norm for s in gt}
    gt_katlanmis_kumesi = {s.katlanmis for s in gt}

    for ci in h.fazla:
        s = ck[ci]
        if _motor_notu_mu(s):
            sebep = "MOTOR_NOTU"
        elif gorulen_norm.get(s.norm, 0) > 1:
            sebep = "TEKRAR"
        elif s.norm in gt_norm_kumesi or s.katlanmis in gt_katlanmis_kumesi:
            sebep = "GT_DISI_ESLESME"
        else:
            en_iyi = max((benzerlik(g, s, kesme=esik)[0] for g in gt), default=0.0)
            sebep = "GT_DISI_ESLESME" if en_iyi >= esik else "UYDURMA_ADAYI"
        _say(f"FAZLA_{sebep}")
        detay["fazla"].append({"cikti": s.ham, "sebep": sebep})

    # --- KAYIP: neden GT'de var ama çıktıda yok? ---------------------------
    for gi in h.kayip:
        g = gt[gi]
        en_iyi, en_iyi_metin = 0.0, None
        for ci, s in enumerate(ck):
            if ci in eslesmis_ck:
                continue
            skor, _ = benzerlik(g, s, kesme=esik_alti)
            if skor > en_iyi:
                en_iyi, en_iyi_metin = skor, s.ham
        sebep = "ESIK_ALTI" if en_iyi >= esik_alti else "HIC_YOK"
        _say(f"KAYIP_{sebep}")
        detay["kayip"].append({
            "gt": g.ham, "sebep": sebep,
            "en_yakin_cikti": en_iyi_metin if en_iyi >= esik_alti else None,
            "en_iyi_skor": round(en_iyi, 4),
        })

    return {"sebep_sayaclari": dict(sorted(sayac.items())), "detay": detay}


# --------------------------------------------------------------------------
# Üst seviye API
# --------------------------------------------------------------------------

def puanla(gt_yolu: str | Path, cikti_yolu: str | Path,
           esik: float = VARSAYILAN_ESIK, dokum: bool = True) -> dict:
    gt = satirlari_oku(gt_yolu)
    ck = satirlari_oku(cikti_yolu)
    h = hizala(gt, ck, esik)
    sonuc = {
        "gt": str(gt_yolu), "cikti": str(cikti_yolu), "esik": esik,
        "metrikler": metrikler(h, gt, ck),
    }
    sr = sinif_raporu(h, ck)
    if sr is not None:
        sonuc["sinif_raporu"] = sr
        # Karantina gerçekten yardım mı ediyor? SÜPHELİ'ler atıldığında
        # metrikler ne oluyor — "vince.txt olarak teslim edilen" ölçüsü.
        # YENİ Satir nesneleri kurulur: mevcutların `sira` alanını ezmek
        # `ck`yi bozar ve ardından gelen fark_dokumu/sinif_raporu yanlış
        # satırı sorgular.
        gorunur = [Satir(ham=s.ham, sira=k, sinif=s.sinif,
                         kaynak_satir=s.kaynak_satir)
                   for k, s in enumerate(s for s in ck if s.sinif != "SUPHELI")]
        sonuc["metrikler_gorunur"] = metrikler(hizala(gt, gorunur, esik), gt, gorunur)
    if dokum:
        sonuc["fark_dokumu"] = fark_dokumu(h, gt, ck, esik)
    return sonuc


# --------------------------------------------------------------------------
# İnsan-okur çıktı
# --------------------------------------------------------------------------

def _y(deger, basamak: int = 3) -> str:
    return "—" if deger is None else f"{deger:.{basamak}f}"


def ozet_yaz(sonuc: dict, fark_detayi: bool = False) -> None:
    m = sonuc["metrikler"]
    print(f"GT    : {sonuc['gt']}")
    print(f"ÇIKTI : {sonuc['cikti']}   (eşik={sonuc['esik']})")
    print("-" * 68)
    print(f"  BİREBİR {m['birebir']:>5}   YAKIN {m['yakin']:>5}   "
          f"KAYIP {m['kayip']:>5}   FAZLA {m['fazla']:>5}")
    print(f"  GT satır {m['gt_toplam']:>4}   çıktı satır {m['cikti_toplam']:>4}")
    print(f"  kesinlik {_y(m['kesinlik'])}   duyarlılık {_y(m['duyarlilik'])}"
          f"   F1 {_y(m['f1'])}")
    if "metrikler_gorunur" in sonuc:
        g = sonuc["metrikler_gorunur"]
        print(f"  [SÜPHELİ hariç] kesinlik {_y(g['kesinlik'])}   "
              f"duyarlılık {_y(g['duyarlilik'])}   F1 {_y(g['f1'])}")
    if "sinif_raporu" in sonuc:
        print("-" * 68)
        print("  SINIF BAZLI DOĞRULUK (GT'de karşılığı var mı):")
        for ad, d in sorted(sonuc["sinif_raporu"].items()):
            print(f"    {ad:<10} {d['gt_karsiligi_var']:>4}/{d['toplam']:<4} "
                  f"= {d['dogruluk']:.3f}   "
                  f"(birebir {d['birebir']}, yakın {d['yakin']})")
    if "fark_dokumu" in sonuc:
        print("-" * 68)
        print("  FARK DÖKÜMÜ — sebep sayaçları:")
        sayaclar = sonuc["fark_dokumu"]["sebep_sayaclari"]
        if not sayaclar:
            print("    (fark yok)")
        for ad, n in sayaclar.items():
            print(f"    {ad:<28} {n:>5}")
        if fark_detayi:
            d = sonuc["fark_dokumu"]["detay"]
            for baslik, anahtar in (("KAYIP", "kayip"), ("FAZLA", "fazla"),
                                    ("YAKIN", "yakin")):
                if not d[anahtar]:
                    continue
                print(f"\n  --- {baslik} ({len(d[anahtar])}) ---")
                for oge in d[anahtar]:
                    if anahtar == "kayip":
                        ek = (f"  ~ '{oge['en_yakin_cikti']}' ({oge['en_iyi_skor']})"
                              if oge["en_yakin_cikti"] else "")
                        print(f"    [{oge['sebep']:<10}] {oge['gt']}{ek}")
                    elif anahtar == "fazla":
                        print(f"    [{oge['sebep']:<16}] {oge['cikti']}")
                    else:
                        print(f"    [{oge['sebep']:<16}] {oge['gt']}"
                              f"  ←→  {oge['cikti']}  ({oge['skor']})")


# --------------------------------------------------------------------------
# Yatak taraması
# --------------------------------------------------------------------------

def _mutlak(yol: str) -> Path:
    p = Path(yol)
    return p if p.is_absolute() else KULE / p


def yatak_tara(yatak_yolu: Path, cikti_kok: Path, esik: float = VARSAYILAN_ESIK,
               belirsiz_dahil: bool = False) -> dict:
    """Yataktaki her yüzey için <cikti_kok>/<film>/<bolum>/vince.json'ı puanlar."""
    yatak = json.loads(Path(yatak_yolu).read_text(encoding="utf-8"))
    satirlar, atlanan = [], []
    for y in yatak["yuzeyler"]:
        if not y.get("dogrulanmis", True) and not belirsiz_dahil:
            atlanan.append({"film": y["film"], "bolum": y["bolum"],
                            "sebep": "GT dogrulanmamis (--belirsiz-dahil ile katilir)"})
            continue
        cikti = Path(cikti_kok) / y["film"] / y["bolum"] / "vince.json"
        if not cikti.exists():
            atlanan.append({"film": y["film"], "bolum": y["bolum"],
                            "sebep": f"cikti yok: {cikti}"})
            continue
        s = puanla(_mutlak(y["gt"]), cikti, esik, dokum=True)
        satirlar.append({"film": y["film"], "bolum": y["bolum"], **s})
    return {"esik": esik, "cikti_kok": str(cikti_kok),
            "yuzeyler": satirlar, "atlanan": atlanan}


def yatak_tablosu_yaz(rapor: dict) -> None:
    print(f"{'film':<20} {'bölüm':<6} {'BİREBİR':>7} {'YAKIN':>6} "
          f"{'KAYIP':>6} {'FAZLA':>6} {'kesin':>6} {'duyar':>6} {'F1':>6}")
    print("-" * 82)
    for r in rapor["yuzeyler"]:
        m = r["metrikler"]
        print(f"{r['film']:<20} {r['bolum']:<6} {m['birebir']:>7} {m['yakin']:>6} "
              f"{m['kayip']:>6} {m['fazla']:>6} {_y(m['kesinlik'], 3):>6} "
              f"{_y(m['duyarlilik'], 3):>6} {_y(m['f1'], 3):>6}")
    for a in rapor["atlanan"]:
        print(f"{a['film']:<20} {a['bolum']:<6}  — atlandı: {a['sebep']}")


# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="puan.py", description="GT ile okuma ciktisini satir duzeyinde puanla")
    ap.add_argument("--gt", help="GT dosyasi (.txt)")
    ap.add_argument("--cikti", help="okuma ciktisi (.txt veya vince.json)")
    ap.add_argument("--yatak", nargs="?", const="olcum/yatak.json",
                    help="tum yatagi tara (varsayilan: olcum/yatak.json)")
    ap.add_argument("--cikti-kok", default="out",
                    help="--yatak icin cikti kok dizini (varsayilan: out/)")
    ap.add_argument("--esik", type=float, default=VARSAYILAN_ESIK,
                    help=f"YAKIN esigi (varsayilan {VARSAYILAN_ESIK})")
    ap.add_argument("--fark-dokumu", action="store_true",
                    help="sebep sayaclarina EK OLARAK satir satir farki yaz")
    ap.add_argument("--json", action="store_true", help="yalniz JSON yaz")
    n = ap.parse_args(argv)

    if n.yatak:
        rapor = yatak_tara(_mutlak(n.yatak), _mutlak(n.cikti_kok), n.esik)
        if n.json:
            print(json.dumps(rapor, ensure_ascii=False, indent=1))
        else:
            yatak_tablosu_yaz(rapor)
        return 0

    if not (n.gt and n.cikti):
        ap.error("--gt ve --cikti birlikte zorunlu (ya da --yatak kullan)")
    sonuc = puanla(n.gt, n.cikti, n.esik)
    if n.json:
        print(json.dumps(sonuc, ensure_ascii=False, indent=1))
    else:
        ozet_yaz(sonuc, fark_detayi=n.fark_dokumu)
    return 0


if __name__ == "__main__":
    sys.exit(main())
