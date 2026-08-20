#!/usr/bin/env python3
"""Curry — şelime (cascade) deney kolu: ucuz düzlem seçer, pahalı düzlem okur.

DENEY KOLU, KULE DEĞİL. Sözleşmesi, kuyruğu, _TAMAM protokolü yok; üretim
yoluna giren hiçbir şeyi değiştirmez. Tek sorusu var:

  **Ucuz sinyal düzlemi (hash + faz korelasyonu) Nash'in Otsu havuzundan
  daha AZ sayfada aynı kart kapsamını yakalıyor mu?**

  Kaba kuvvet reçetesinin (her kareyi oku, sonra dedup) pahalı düzlemi
  israf ettiği; çözmeye değer tek şeyin "hangi kare bilgi taşıyor" sorusu
  olduğu fikrinin ölçümlü sınanması. Hız Qwen'den, disiplin Nash'ten.

Düzlemler:
  UCUZ  (kare başına ~ms, saf numpy/cv2, belirlilik — rastgelelik yok):
    parlaklık · Laplacian varyansı (keskinlik) · aHash 8x8 (64 bit) ·
    önceki kareyle faz korelasyonu dikey ofisi (kaydırma hızı).
  PAHALI (sayfa başına ~2-4 sn): DeepSeek-OCR — yalnız `oku` komutunda.

Segmentasyon: kareler → [kart (durur) | kayan (scroll) | siyah (boş)].
Seçim: kart → en keskin 1 kare; kayan → ardışık sayfalar ~yarım ekran
kayacak biçimde (≥%30 ≤%70 örtüşme); sigortalar ve tavanlar Nash'inkiyle
aynı (kıyas adil olsun diye): cikis tavan 100 + son kare, giris tavan 40 +
son 12 ham kare.

Komutlar:
  curry.py kendilik                     sentetik yatakta öz-denetim (GPU yok)
  curry.py sec --kareler D [--bolum B]  segmentasyon + seçim raporu
  curry.py kiyas --kareler D [--bolum B] curry seçimi vs Nash havuz seçimi
  curry.py yatak [--bolum B]            15 filmlik ölçüm yatağında kıyas
  curry.py oku  --kareler D [--bolum B] seçili sayfaları DeepSeek-OCR ile oku

Koşum: Allstar/nash/venv/bin/python Allstar/curry.py ...
Çıktılar: Allstar/curry_out/ altına.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

ALLSTAR = Path(__file__).resolve().parent
NASH = ALLSTAR / "nash"
OUT = ALLSTAR / "curry_out"
YATAK = Path("/opt/mitas/outputs/olcum_yatagi/klipler")

# --- eşikler: tek yerde, ölçülebilir olsunlar -------------------------------
KUCUK_GENISLIK = 256   # sinyal düzlemi çözünürlüğü (piksel)
ICERIKSIZ_STD = 3.0    # bunun altı → boş kare (Nash havuzunun ölçütüyle aynı)
STATIK_HAMMING = 6     # ardışık kare hash farkı ≤ bu → aynı kart duruyor
KART_ADIM_MIN = 2      # kart saymak için en az bu kadar statik adım
KAYMA_HIZ_MIN = 4.0     # px/adım (TAM ölçek) — altında ölçülebilir kaydırma yok
YARIM_EKRAN = 0.5      # kayan segmentte sayfalar arası hedef kaydırma (ekran oranı)
DEGISIM_HAMMING = 8    # kaydırma ölçülemediğinde: son seçilenden bu kadar farklı kare
KART_ESIGI = 10        # iki kare 'farklı kart' sayılsın diye gereken hash uzaklığı
AYARLAR = {
    "cikis": {"tavan": 100, "son_kare_zorla": True, "ham_kuyruk": 0},
    "giris": {"tavan": 40, "son_kare_zorla": False, "ham_kuyruk": 12},
}
OKUMA = {"min_uzunluk": 200, "min_alnum_oran": 0.30, "dedup_esigi": 0.92}


# --- ucuz düzlem --------------------------------------------------------------
@dataclass
class Kare:
    yol: Path
    indeks: int
    parlaklik: float
    keskinlik: float
    hash_: np.ndarray          # 64 bit bool
    std: float = 0.0           # piksel std — içeriksizlik ölçütü (parlaklık DEĞİL)
    dy: float = 0.0            # önceki kareye göre dikey ofis (px, TAM ölçek, profil korelasyonu)
    adim: str = ""             # statik | degisim | siyah


def _ahash(kucuk: np.ndarray) -> np.ndarray:
    """pHash: 32x32 DCT'nin düşük frekans 8x8'i, medyan eşiğiyle 64 bit.

    aHash ile başlandı ama grain'e KIRILGAN çıktı (ölçüldü): düz zeminde σ=6
    gürültü, ortalama-eşiği civarındaki bitleri çevirip 15 karelik kartı
    kırptı. DCT düşük frekansı gürültüyü (yüksek frekans) doğal olarak atar.
    """
    otuziki = cv2.resize(kucuk, (32, 32)).astype(np.float32)
    d = cv2.dct(otuziki)[:8, :8]
    return d > np.median(d[1:, 1:])


def _hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def _satir_profili(im: np.ndarray) -> np.ndarray:
    """Kenar enerjisi satır imzası (tam çözünürlük, merkez %60 genişlik).

    Jenerik kaydırmasının dedektörü: satır imzalarının 1B korelasyonu dikey
    ofisi verir. Faz korelasyonu 2B'de iki kez yanılttı (ölçüldü): siyah
    bantlar/statik çerçeve ofisi sıfıra iğneliyor; düzenli satır aralığı
    periyot alyası üretiyor (sentetikte 8px yerine 71px). Profil yolu
    bantlara bağışık — bantlar her satır imzasına aynı katkıyı verir.
    """
    h, w = im.shape
    merkez = im[:, round(w * 0.2):round(w * 0.8)].astype(np.float32)
    gx = cv2.Sobel(merkez, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(merkez, cv2.CV_32F, 0, 1)
    return np.sqrt(gx * gx + gy * gy).sum(axis=1)


def _profil_ofisi(a: np.ndarray, b: np.ndarray) -> float:
    """b'nin a'ya göre dikey ofisi (px). Tepe ±%10 ekran dışında → 0 (güvensiz)."""
    a = a - a.mean()
    b = b - b.mean()
    kor = np.correlate(b, a, mode="full")
    tepe = int(np.argmax(kor)) - (len(a) - 1)
    if abs(tepe) > 0.1 * len(a):
        return 0.0
    return float(tepe)


def kareleri_oku(dizin: Path, desen: str = "*.png") -> tuple[list[Kare], int]:
    """Dizin → (sinyaller, tam ölçek yükseklik). Açılamayan kare hata verir."""
    yollar = sorted(Path(dizin).glob(desen))
    if not yollar:
        return [], 0
    kareler: list[Kare] = []
    onceki_hash: np.ndarray | None = None
    onceki_profil: np.ndarray | None = None
    h_tam = 0
    for i, yol in enumerate(yollar):
        im = cv2.imread(str(yol), cv2.IMREAD_GRAYSCALE)
        if im is None:
            raise RuntimeError(f"kare acilamadi: {yol}")
        h_tam = im.shape[0]
        kucuk = cv2.resize(im, (KUCUK_GENISLIK,
                                max(1, round(im.shape[0] * KUCUK_GENISLIK / im.shape[1]))))
        hu = kucuk.astype(np.float32)
        par, lap, std = (float(hu.mean()), float(cv2.Laplacian(hu, cv2.CV_32F).var()),
                         float(hu.std()))
        h = _ahash(kucuk)
        profil = _satir_profili(im)
        dy = _profil_ofisi(onceki_profil, profil) if onceki_profil is not None else 0.0
        # DİKKAT: konumsal kuruluşta dy/std yer değiştirdi (ölçüldü — std
        # sütununda -33'ler belirdi, tüm film 'siyah' sayıldı). Anahtar sözcüklü.
        kare = Kare(yol=yol, indeks=i, parlaklik=par, keskinlik=lap,
                    hash_=h, std=std, dy=dy)
        if onceki_hash is None:
            kare.adim = "statik" if std >= ICERIKSIZ_STD else "siyah"
        elif std < ICERIKSIZ_STD or kareler[-1].std < ICERIKSIZ_STD:
            # İçeriksizlik PARLAKLIK değil STD işidir: karanlık jenerikte beyaz
            # yazı parlar (std yüksek) — parlaklık eşiği 168 karelik bir jeneriği
            # topluca "siyah" saydı (ARJANTİN TANGOSU, ölçüldü). Nash havuzunun
            # kendi içeriksizlik ölçütüyle (std < 3.0) hizalandık.
            kare.adim = "siyah"
        else:
            # KART = hash yakınsa VE ölçülebilir kayma yoksa. Yavaş kayan yazıda
            # ardışık hash farkı KÜÇÜK kalır — kaydırmayı satır profili söyler.
            kare.adim = ("statik" if _hamming(h, onceki_hash) <= STATIK_HAMMING
                         and abs(dy) < KAYMA_HIZ_MIN else "degisim")
        onceki_hash, onceki_profil = h, profil
        kareler.append(kare)
    return kareler, h_tam


# --- segmentasyon -------------------------------------------------------------
@dataclass
class Segment:
    tur: str                    # kart | kayan | siyah
    kareler: list[Kare] = field(default_factory=list)

    @property
    def dy_medyan(self) -> float:
        return float(np.median([abs(k.dy) for k in self.kareler[1:]]) if len(self.kareler) > 1 else 0.0)


def segmentle(kareler: list[Kare]) -> list[Segment]:
    """Adım etiketleri → tür segmentleri (saf öbekler, birleştirme YOK).

    Kart = ardışık statik adım öbeği; kesme/crossfade adımı (degisim) kartı
    KAPATIR — ölçümde görüldü: tek karelik kayanı karta yapıştırmak, sert
    kesmeli kartları tek segmentte birleştirip temsilcileri yutuyor
    (MOBY DICK: 11 kart → 4 sayfa). Kısa kart (1-2 kare) gerçek olabilir,
    temsilcisi yine seçilir.
    """
    segmentler: list[Segment] = []
    tur = {"statik": "kart", "degisim": "kayan", "siyah": "siyah"}
    for k in kareler:
        if segmentler and segmentler[-1].tur == tur[k.adim]:
            segmentler[-1].kareler.append(k)
        else:
            segmentler.append(Segment(tur[k.adim], [k]))
    return segmentler


# --- seçim --------------------------------------------------------------------
def segmendan_sayfa(seg: Segment, h_tam: int) -> list[Kare]:
    if seg.tur == "kart":
        return [max(seg.kareler, key=lambda k: k.keskinlik)]
    if seg.tur == "siyah":
        return []
    # kayan: yarı ekran kaydırma politikası; hız ölçülemediyse hash farkı
    hiz = seg.dy_medyan
    secili = [seg.kareler[0]]
    if hiz >= KAYMA_HIZ_MIN:
        adim = max(1, round(YARIM_EKRAN * h_tam / hiz))
        secili = seg.kareler[::adim]
    else:
        son = seg.kareler[0]
        for k in seg.kareler[1:]:
            if _hamming(k.hash_, son.hash_) >= KART_ESIGI:
                secili.append(k)
                son = k
        # grain gürültüsü her kareyi "farklı" gösterebilir (SİHİRLİ FLÜT 88/88,
        # ölçüldü) — segmentin üçte birini aşan seçim üniform adıma iner
        if len(secili) > max(8, len(seg.kareler) // 3):
            adim = max(1, len(seg.kareler) // max(8, len(seg.kareler) // 3))
            secili = seg.kareler[::adim]
    if secili[-1] is not seg.kareler[-1]:
        secili.append(seg.kareler[-1])   # segment sonunu koru — uç satır kaymasın
    return secili


def sec(dizin: Path, bolum: str = "cikis") -> dict:
    """Dizin → seçim + kanıt. Belirlilik: aynı girdi = aynı çıktı."""
    t0 = time.time()
    kareler, h_tam = kareleri_oku(dizin)
    if not kareler:
        return {"hata": "dizin_bos"}
    segmentler = segmentle(kareler)
    ayar = AYARLAR[bolum]

    secili_tur: dict[int, str] = {}
    tum_secili: dict[int, Kare] = {}
    for seg in segmentler:
        for k in segmendan_sayfa(seg, h_tam):
            tum_secili[k.indeks] = k
            secili_tur[k.indeks] = seg.tur
    secili = sorted(tum_secili.values(), key=lambda k: k.indeks)

    dusurulen = 0
    if len(secili) > ayar["tavan"]:
        kartlar = [k for k in secili if secili_tur[k.indeks] == "kart"]
        kayanlar = [k for k in secili if secili_tur[k.indeks] != "kart"]
        # tavan aşılırsa kayandan düşür; kart TAMAMEN atlanamaz
        kalan = max(0, ayar["tavan"] - len(kartlar))
        if len(kartlar) > ayar["tavan"]:
            kartlar = kartlar[:ayar["tavan"]]
            kalan = 0
        dusurulen = len(kayanlar) - min(kalan, len(kayanlar))
        kayanlar = (kayanlar[::max(1, round(len(kayanlar) / kalan))]
                    if kalan and len(kayanlar) > kalan else kayanlar[:kalan])
        secili = sorted(kartlar + kayanlar, key=lambda k: k.indeks)

    tur_say = {}
    for s in segmentler:
        tur_say[s.tur] = tur_say.get(s.tur, 0) + 1
    sigorta = 0
    if not secili and not (ayar["son_kare_zorla"] or ayar["ham_kuyruk"]):
        return {"hata": "secim_bos", "dizin": str(dizin), "bolum": bolum,
                "kare": len(kareler), "segment": tur_say}
    if ayar["son_kare_zorla"] and (not secili or secili[-1] is not kareler[-1]):
        secili.append(kareler[-1])
        sigorta += 1
    if ayar["ham_kuyruk"]:
        mevcut = {k.indeks for k in secili}
        for k in kareler[-ayar["ham_kuyruk"]:]:
            if k.indeks not in mevcut:
                secili.append(k)
                sigorta += 1
        secili.sort(key=lambda k: k.indeks)

    kart_sayfa = sum(1 for k in secili if secili_tur.get(k.indeks) == "kart")
    return {
        "dizin": str(dizin), "bolum": bolum,
        "kare": len(kareler), "segment": tur_say,
        "sayfa_curry": len(secili),
        "kart_sayfa": kart_sayfa,
        "kayan_sayfa": len(secili) - kart_sayfa - sigorta,
        "sigorta_sayfa": sigorta,
        "tavan_asim_dusurulen": dusurulen,
        "secilenler": [k.yol.name for k in secili],
        "yollar": [k.yol for k in secili],
        "sure_sn": round(time.time() - t0, 2),
    }


# --- kıyas: curry vs nash havuzu ----------------------------------------------
def kart_kumeleri(kareler: list[Kare]) -> list[np.ndarray]:
    """İmza kümesi sayısı (bilgi amaçlı): birbirinden KART_ESIGI kadar uzak hashler."""
    temsilciler: list[np.ndarray] = []
    for k in kareler:
        if all(_hamming(k.hash_, t) >= KART_ESIGI for t in temsilciler):
            temsilciler.append(k.hash_)
    return temsilciler


def kart_obeleri(kareler: list[Kare]) -> list[list[Kare]]:
    """Durağan kart öbekleri: ardışık 'statik' adım öbeği (>= 2 kare).

    Kapsamın ASIL ölçütü budur: her kart en az bir sayfayla okunmalı.
    İmza-küme kapsamı kayan yazıda her hash alt-durumunu saydığından
    yanıltıcıdır — kayan yazının görevi örtüşme, kartların görevi tam kapsam.
    """
    obepler, mevcut = [], []
    for k in kareler:
        if k.adim == "statik":
            mevcut.append(k)
        else:
            if len(mevcut) >= 2:
                obepler.append(mevcut)
            mevcut = []
    if len(mevcut) >= 2:
        obepler.append(mevcut)
    return obepler


def obe_kapsam(obepler: list[list[Kare]], secilen: list[Kare]) -> float:
    """Kart öbeği, seçimde İÇERİKÇE yakın (hash ≤ STATIK_HAMMING) kare varsa kapsanmış.

    Kare-indeks eşitliği YANLIŞ ölçü çıktı (DONÖR'de ölçüldü): tartışmalı öbeğin
    temsilcisi 0715'ti, Nash'in 0713'ü AYNI içeriği taşıyordu (beyaz-oran ve
    kenar satırı birebir) — indeks farklı, içerik aynı. Kapsam içerikle ölçülür.
    """
    if not obepler:
        return 1.0
    tutan = 0
    for o in obepler:
        rep = max(o, key=lambda k: k.keskinlik)
        if any(_hamming(k.hash_, rep.hash_) <= STATIK_HAMMING for k in secilen):
            tutan += 1
    return tutan / len(obepler)


def kiyas(dizin: Path, bolum: str = "cikis") -> dict:
    sys.path.insert(0, str(NASH / "src"))
    import secim as nash_secim

    r = sec(dizin, bolum)
    if "hata" in r:
        return r
    n = nash_secim.sec(Path(dizin), AYARLAR[bolum])
    kareler, _ = kareleri_oku(dizin)
    obepler = kart_obeleri(kareler)
    curry_adlari = set(r["secilenler"])
    nash_adlari = {p.name for p in n.yollar}
    curry_kareler = [k for k in kareler if k.yol.name in curry_adlari]
    nash_kareler = [k for k in kareler if k.yol.name in nash_adlari]
    kesisim = len(curry_adlari & nash_adlari)
    return {
        "dizin": str(dizin), "bolum": bolum, "kare": len(kareler),
        "kart_obe": len(obepler),
        "imza_kumesi": len(kart_kumeleri(kareler)),
        "sayfa_nash": len(n.yollar), "sayfa_curry": r["sayfa_curry"],
        "jaccard": round(kesisim / len(curry_adlari | nash_adlari), 3) if kesisim else 0.0,
        "kart_kapsam_curry": round(obe_kapsam(obepler, curry_kareler), 3),
        "kart_kapsam_nash": round(obe_kapsam(obepler, nash_kareler), 3),
        "maliyet_sn_nash": round(len(n.yollar) * 2.5),
        "maliyet_sn_curry": round(r["sayfa_curry"] * 2.5),
        "segment": r["segment"],
        "nash_havuz": (n.kanit or {}).get("havuz"),
        "secilenler": r["secilenler"],
    }


def yatak(bolum: str = "cikis") -> int:
    """15 filmlik ölçüm yatağı: kıyas satırları + toplam."""
    satirlar, toplam = [], {"kare": 0, "sayfa_nash": 0, "sayfa_curry": 0,
                            "kap_n": 0.0, "kap_c": 0.0, "n": 0}
    for film in sorted(YATAK.iterdir()):
        if not film.is_dir():
            continue
        alt = "frames/cikis_jenerik" if bolum == "cikis" else "frames/giris"
        d = film / alt
        if not d.is_dir() or not list(d.glob("*.png")):
            continue
        r = kiyas(d, bolum)
        if "hata" in r:
            print(f"  [atla] {film.name[:40]} {r['hata']}")
            continue
        satirlar.append({"film": film.name, **{k: v for k, v in r.items()
                                               if k not in ("secilenler", "nash_havuz")}})
        toplam["n"] += 1
        toplam["kare"] += r["kare"]
        toplam["sayfa_nash"] += r["sayfa_nash"]
        toplam["sayfa_curry"] += r["sayfa_curry"]
        toplam["kap_n"] += r["kart_kapsam_nash"]
        toplam["kap_c"] += r["kart_kapsam_curry"]
        print(f"  {film.name[:38]:38s} kare={r['kare']:4d} öbe={r['kart_obe']:3d} "
              f"nash={r['sayfa_nash']:3d} curry={r['sayfa_curry']:3d} "
              f"kartKapN={r['kart_kapsam_nash']:.2f} kartKapC={r['kart_kapsam_curry']:.2f}")
    if toplam["n"]:
        print(f"\n  TOPLAM {toplam['n']} yüzey · kare {toplam['kare']} · "
              f"sayfa nash {toplam['sayfa_nash']} vs curry {toplam['sayfa_curry']} "
              f"({100 * (1 - toplam['sayfa_curry'] / max(1, toplam['sayfa_nash'])):.0f}% az) · "
              f"ortalama kapsam nash {toplam['kap_n'] / toplam['n']:.2f} "
              f"curry {toplam['kap_c'] / toplam['n']:.2f}")
    OUT.mkdir(exist_ok=True)
    (OUT / f"yatak_{bolum}.json").write_text(
        json.dumps({"toplam": toplam, "satirlar": satirlar}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"  rapor: {OUT / f'yatak_{bolum}.json'}")
    return 0


# --- pahalı düzlem: DeepSeek-OCR (yalnız seçili sayfalar) ----------------------
def oku(dizin: Path, bolum: str = "cikis") -> int:
    sys.path.insert(0, str(NASH / "src"))
    from model import yukle

    r = sec(dizin, bolum)
    if "hata" in r:
        print(f"HATA: {r['hata']}")
        return 2
    ayar = {"model_yol": str(NASH / "model" / "deepseek-ocr"),
            "istem": "Free OCR.", "max_new_tokens": 2048, "temperature": 0.0}
    OUT.mkdir(exist_ok=True)
    sor = yukle(ayar, OUT)   # scratch curry_out altına

    sayfalar, t0 = [], time.time()
    for yol in r["yollar"]:
        t1 = time.time()
        metin = sor(Path(yol))
        alnum = sum(c.isalnum() for c in metin)
        sayfalar.append({"kare": Path(yol).name, "sure_sn": round(time.time() - t1, 1),
                         "uzunluk": len(metin),
                         "alnum_oran": round(alnum / max(1, len(metin)), 3),
                         "metin": metin})
        print(f"  [{len(sayfalar):3d}/{r['sayfa_curry']}] {Path(yol).name} "
              f"{sayfalar[-1]['sure_sn']:4.1f}sn {len(metin):5d} krk")

    # satır birleştirme: 0.92 fold-dedup (deney düzeyi; vetolar nash'te)
    satirlar: list[str] = []
    for s in sayfalar:
        for satir in s["metin"].splitlines():
            satir = satir.strip()
            if len(satir) < 2:
                continue
            if not any(difflib.SequenceMatcher(None, satir, u).ratio()
                       >= OKUMA["dedup_esigi"] for u in satirlar):
                satirlar.append(satir)
    birlesik = "\n".join(s["metin"] for s in sayfalar)
    saglik = ("garble_yuksek" if (sum(c.isalnum() for c in birlesik)
             / max(1, len(birlesik)) < OKUMA["min_alnum_oran"]) else
             "cok_kisa" if len(birlesik) < OKUMA["min_uzunluk"] else "ok")

    hedef = OUT / Path(dizin).name / bolum
    hedef.mkdir(parents=True, exist_ok=True)
    (hedef / "curry.json").write_text(json.dumps({
        "dizin": str(dizin), "bolum": bolum, "kare": r["kare"],
        "sayfa": len(sayfalar), "saglik": saglik,
        "segment": r["segment"], "satirlar": satirlar, "sayfalar": sayfalar,
        "sure_sn": round(time.time() - t0, 1)}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n  sayfa {len(sayfalar)} · satır {len(satirlar)} · sağlık {saglik} · "
          f"{round(time.time() - t0, 1)} sn → {hedef / 'curry.json'}")
    return 0


# --- v2: ele → grupla → medyan-sentez (Çağatay tasarımı, 2026-08-18) -----------
def _hizali_medyan(yollar: list[Path], kaydirmalar: list[tuple[float, float]]) -> np.ndarray:
    """Kareleri (dy,dx) SUB-PIKSEL kaydırıp hizala → medyan sayfa.

    Ölçülen dersler: (1) hizasız medyan keskinliği düşürür — gate weave.
    (2) weave SUB-PIKSEL (+0.1..0.6px, BOZGUNCULAR'da ölçüldü) → tamsayı
    yuvarlama kaydı yutar; warpAffine float kaydırma şart.
    """
    yigin = []
    for yol, (dy, dx) in zip(yollar, kaydirmalar):
        im = cv2.imread(str(yol), cv2.IMREAD_GRAYSCALE)
        if im is None:
            continue
        if dy or dx:
            m = np.float32([[1, 0, dx], [0, 1, dy]])
            im = cv2.warpAffine(im, m, (im.shape[1], im.shape[0]),
                                flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REPLICATE)
        yigin.append(im)
    if not yigin:
        raise RuntimeError("medyan sentez: hiç kare açılamadı")
    return np.median(np.stack(yigin), axis=0).astype(np.uint8)


def _kayit_ofisi(im: np.ndarray, rep: np.ndarray) -> tuple[float, float]:
    """im'yi rep'e hizalayan (dy,dx) — merkez %70 dilimde faz korelasyonu.

    Kenarlar kırpılır (bantlar/logo korelasyonu iğnelemez — ölçülmüş ders).
    ±8px dışı güvensiz → (0,0). Dönüş SUB-PIKSEL float.
    """
    h, w = im.shape
    dil = (slice(round(h * 0.15), round(h * 0.85)),
           slice(round(w * 0.15), round(w * 0.85)))
    try:
        (dx, dy), _ = cv2.phaseCorrelate(
            im[dil].astype(np.float32), rep[dil].astype(np.float32))
    except cv2.error:
        return 0.0, 0.0
    if abs(dx) > 8 or abs(dy) > 8:
        return 0.0, 0.0
    return float(dy), float(dx)


def _arka_plan_gurultu(im: np.ndarray) -> float:
    """Zemin (parlaklık < 40) piksellerinin std'si — grain ölçüsü."""
    zemin = im[im < 40]
    return float(zemin.std()) if zemin.size > 100 else float("nan")


def sec_v2(dizin: Path, bolum: str = "cikis", yaz: bool = False,
           sentez: bool = False) -> dict:
    """v2 akışı: yazı-var eledi → statik gruplar + kayan zincir → sayfalar.

    Aşama 1 (ele): std < 3.0 kareler içeriksiz sayılır (Nash ölçütü) — ŞÜPHEDE
    TUT: yalnız bariz boş düşer. Aşama 2 (grupla): hash yakınlığı + dy≈0 → kart
    grubu; kalan → kayan zincir. Aşama 3: kart başına 1 temsilci (en keskin),
    kayan gövdede yarı-ekran aralıklı sayfa; sigortalar bölüm farkıyla.

    MEDYAN-SENTEZ DENENDİ, BU VERİDE REDDEDİLDİ (2026-08-18, BOZGUNCULAR
    1955): hizasız medyan grain'i düşürmedi (15.2→16.4) ve keskinlik
    götürdü; sub-piksel warpAffine kaydı (weave +0.1..0.6px ölçüldü) işaret
    ve interpolasyon ne olursa olsun keskinliği daha çok düşürdü (bilinear
    358→245, Lanczos 319). Sebep: piksel gürültüsü kareler arası İLİNTİLİ
    (sıkıştırma + tarama dokusu) — medyan ilintisiz gürültüyü siler, bunu
    silmez. Sentez `sentez=True` ile denenebilir; temsilci kare varsayılan.
    """
    t0 = time.time()
    kareler, h_tam = kareleri_oku(dizin)
    if not kareler:
        return {"hata": "dizin_bos"}
    ayar = AYARLAR[bolum]
    segmentler = segmentle(kareler)

    sayfalar, kalite = [], []
    for seg in segmentler:
        if seg.tur == "kart":
            rep_k = max(seg.kareler, key=lambda k: k.keskinlik)
            if sentez:
                uye = seg.kareler
                if len(uye) > 9:
                    uye = uye[::max(1, len(uye) // 9)][:9]
                rep_im = cv2.imread(str(rep_k.yol), cv2.IMREAD_GRAYSCALE)
                sayfalar.append({"ad": f"kart_{seg.kareler[0].indeks:05d}", "tur": "kart",
                                 "uyeler": [k.yol for k in uye],
                                 "kaydirma": [_kayit_ofisi(cv2.imread(
                                     str(k.yol), cv2.IMREAD_GRAYSCALE), rep_im)
                                     for k in uye],
                                 "rep": rep_k.yol})
            else:
                sayfalar.append({"ad": f"kart_{seg.kareler[0].indeks:05d}", "tur": "kart",
                                 "uyeler": [rep_k.yol],
                                 "kaydirma": [(0.0, 0.0)], "rep": rep_k.yol})
        elif seg.tur == "kayan":
            hiz = seg.dy_medyan
            yerel = {k.indeks: n for n, k in enumerate(seg.kareler)}
            for k in segmendan_sayfa(seg, h_tam):
                loc = yerel[k.indeks]
                if sentez:
                    komsu = seg.kareler[max(0, loc - 2):loc + 3]
                    sayfalar.append({"ad": f"kayan_{k.indeks:05d}", "tur": "kayan",
                                     "uyeler": [kk.yol for kk in komsu],
                                     "kaydirma": [(float((k.indeks - kk.indeks) * hiz), 0.0)
                                                  for kk in komsu],
                                     "rep": k.yol})
                else:
                    sayfalar.append({"ad": f"kayan_{k.indeks:05d}", "tur": "kayan",
                                     "uyeler": [k.yol],
                                     "kaydirma": [(0.0, 0.0)], "rep": k.yol})

    # sigortalar
    uye_adlari = {p.name for s in sayfalar for p in s["uyeler"]}
    sigorta = 0
    if bolum == "giris":
        for k in kareler[-ayar["ham_kuyruk"]:]:
            if k.yol.name not in uye_adlari:
                sayfalar.append({"ad": f"sigorta_{k.indeks:05d}", "tur": "sigorta",
                                 "uyeler": [k.yol], "kaydirma": [(0.0, 0.0)], "rep": k.yol})
                sigorta += 1
    else:
        son = kareler[-1]
        if son.yol.name not in uye_adlari:
            sayfalar.append({"ad": f"sigorta_{son.indeks:05d}", "tur": "sigorta",
                             "uyeler": [son.yol], "kaydirma": [(0.0, 0.0)], "rep": son.yol})
            sigorta += 1

    # tavan: kart sentezleri korunur, kayandan düşülür
    dusurulen = 0
    kartlar = [s for s in sayfalar if s["tur"] == "kart"]
    kayanlar = [s for s in sayfalar if s["tur"] == "kayan"]
    if len(sayfalar) > ayar["tavan"] and kayanlar:
        kalan = max(0, ayar["tavan"] - len(kartlar) - sigorta)
        dusurulen = len(kayanlar) - min(kalan, len(kayanlar))
        kayanlar = (kayanlar[::max(1, round(len(kayanlar) / kalan))]
                    if kalan and len(kayanlar) > kalan else kayanlar[:kalan])
        sayfalar = kartlar + kayanlar + [s for s in sayfalar if s["tur"] == "sigorta"]

    tur_say: dict[str, int] = {}
    for s in sayfalar:
        tur_say[s["tur"]] = tur_say.get(s["tur"], 0) + 1

    if yaz:
        hedef = OUT / "v2" / Path(dizin).name / bolum
        hedef.mkdir(parents=True, exist_ok=True)
        for s in sayfalar:
            sentez = _hizali_medyan(s["uyeler"], s["kaydirma"])
            cv2.imwrite(str(hedef / f"{s['ad']}.png"), sentez)
            tek = cv2.imread(str(s["rep"]), cv2.IMREAD_GRAYSCALE)
            kalite.append({"sayfa": s["ad"], "tur": s["tur"], "uye": len(s["uyeler"]),
                           "grain_tek": round(_arka_plan_gurultu(tek), 2),
                           "grain_sentez": round(_arka_plan_gurultu(sentez), 2),
                           "keskin_tek": round(float(cv2.Laplacian(
                               tek, cv2.CV_32F).var()), 1),
                           "keskin_sentez": round(float(cv2.Laplacian(
                               sentez.astype(np.float32), cv2.CV_32F).var()), 1)})

    return {"dizin": str(dizin), "bolum": bolum, "kare": len(kareler),
            "elenen_bos": sum(1 for k in kareler if k.adim == "siyah"),
            "sayfa_v2": len(sayfalar), "sayfa_tur": tur_say,
            "tavan_asim_dusurulen": dusurulen,
            "grain_azalma": (round(1 - sum(k["grain_sentez"] for k in kalite)
                                   / max(1e-6, sum(k["grain_tek"] for k in kalite)), 3)
                             if kalite else None),
            "kalite": kalite, "sure_sn": round(time.time() - t0, 1)}


def v2yatak(bolum: str = "cikis") -> int:
    sys.path.insert(0, str(NASH / "src"))
    import secim as nash_secim
    toplam = {"n": 0, "kare": 0, "elenen": 0, "sayfa_nash": 0, "sayfa_v2": 0}
    satirlar = []
    for film in sorted(YATAK.iterdir()):
        alt = "frames/cikis_jenerik" if bolum == "cikis" else "frames/giris"
        d = film / alt
        if not film.is_dir() or not d.is_dir() or not list(d.glob("*.png")):
            continue
        r = sec_v2(d, bolum)
        if "hata" in r:
            continue
        n = nash_secim.sec(d, AYARLAR[bolum])
        toplam["n"] += 1
        toplam["kare"] += r["kare"]
        toplam["elenen"] += r["elenen_bos"]
        toplam["sayfa_nash"] += len(n.yollar)
        toplam["sayfa_v2"] += r["sayfa_v2"]
        satirlar.append({"film": film.name, "kare": r["kare"],
                         "elenen": r["elenen_bos"], "sayfa_v2": r["sayfa_v2"],
                         "tur": r["sayfa_tur"], "sayfa_nash": len(n.yollar)})
        print(f"  {film.name[:38]:38s} kare={r['kare']:4d} elenen={r['elenen_bos']:3d} "
              f"v2={r['sayfa_v2']:3d} {r['sayfa_tur']} nash={len(n.yollar):3d}")
    print(f"\n  TOPLAM {toplam['n']} yüzey · kare {toplam['kare']} · "
          f"elenen boş {toplam['elenen']} · sayfa nash {toplam['sayfa_nash']} "
          f"vs v2 {toplam['sayfa_v2']} "
          f"({100 * (1 - toplam['sayfa_v2'] / max(1, toplam['sayfa_nash'])):.0f}% az)")
    OUT.mkdir(exist_ok=True)
    (OUT / f"v2yatak_{bolum}.json").write_text(
        json.dumps({"toplam": toplam, "satirlar": satirlar}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return 0


# --- sentetik öz-denetim --------------------------------------------------------
def kendilik() -> int:
    """Kart + kayan + siyah sentezi → beklenen seçim tutuyor mu? (GPU yok)"""
    kok = OUT / "sentetik"
    kok.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)          # belirlilik: tohumlu grain
    for i in range(60):
        if i < 15:                                   # kart: aynı yazı durur (+ grain)
            im = np.full((144, 256), 30, np.uint8)
            cv2.putText(im, "BOZGUNCULAR 1955", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, 255, 2)
            im = np.clip(im.astype(np.int16)
                         + rng.normal(0, 6, im.shape).astype(np.int16), 0, 255
                         ).astype(np.uint8)
        elif i < 20:                                 # siyah geçiş (grain YOK — boş kalsın)
            im = np.zeros((144, 256), np.uint8)
        else:                                        # kayan: yazı sararak akar (+ grain)
            im = np.full((144, 256), 30, np.uint8)
            for j, satir in enumerate(["AAAA BBBB", "CCCC DDDD", "EEEE FFFF",
                                       "GGGG HHHH", "IIII JJJJ", "KKKK LLLL"]):
                y = ((i - 20) * 8 + j * 22) % 176 - 16   # alttan gir, üstten çık, sar
                cv2.putText(im, satir, (40, y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 1)
            im = np.clip(im.astype(np.int16)
                         + rng.normal(0, 6, im.shape).astype(np.int16), 0, 255
                         ).astype(np.uint8)
        cv2.imwrite(str(kok / f"{i:04d}.png"), im)

    r = sec(kok, "cikis")
    beklenen_kart = 1
    kayan_sayfa = sum(1 for ad in r.get("secilenler", []) if int(ad[:-4]) >= 20)
    sorun = []
    if r.get("hata"):
        sorun.append(f"hata: {r['hata']}")
    if r["kart_sayfa"] != beklenen_kart:
        sorun.append(f"kart sayfa {r['kart_sayfa']} != {beklenen_kart}")
    kart_ici = [ad for ad in r.get("secilenler", [])
                if 1 <= int(ad[:-4]) <= 14]
    if len(kart_ici) > 1:                      # tek temsilci serbest, 2+ = kart kırıldı
        sorun.append(f"kart kırıldı (grain/dy zaafı): {kart_ici}")
    if kayan_sayfa < 3:
        sorun.append(f"kayan sayfa çok az: {kayan_sayfa}")
    if r["secilenler"][-1] != "0059.png":
        sorun.append("son kare sigortası çalışmadı")
    print(json.dumps({k: v for k, v in r.items() if k != "yollar"},
                     ensure_ascii=False, indent=1))
    if sorun:
        print("KENDİLİK: SORUN — " + "; ".join(sorun))
        return 1
    # v2 öz-denetimi: İLİNTİSİZ gürültüde medyan çalışır (sentetik grain σ=6,
    # 9 üye → ~2). Gerçek filmde ilintili gürültü yüzünden reddedildi — bkz. docstring.
    r2 = sec_v2(kok, "cikis", yaz=True, sentez=True)
    kart_k = [k for k in r2["kalite"] if k["tur"] == "kart"]
    if r2.get("hata"):
        sorun.append(f"v2 hata: {r2['hata']}")
    elif not kart_k:
        sorun.append("v2 kart sayfası yok")
    elif not kart_k[0]["grain_sentez"] < kart_k[0]["grain_tek"]:
        sorun.append(f"v2 medyan grain düşürmedi: {kart_k[0]}")
    if sorun:
        print("KENDİLİK: SORUN — " + "; ".join(sorun))
        return 1
    print(f"KENDİLİK: OK — kart 1, kayan çok-adımlı, son kare sigortalı; "
          f"v2 grain {kart_k[0]['grain_tek']} → {kart_k[0]['grain_sentez']}.")
    return 0


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    alt = a.add_subparsers(dest="komut", required=True)
    for ad in ("sec", "kiyas", "oku", "v2"):
        p = alt.add_parser(ad)
        p.add_argument("--kareler", required=True)
        p.add_argument("--bolum", choices=list(AYARLAR), default="cikis")
        if ad == "v2":
            p.add_argument("--yaz", action="store_true",
                           help="sayfaları PNG olarak yaz + grain ölç")
            p.add_argument("--sentez", action="store_true",
                           help="medyan-sentez dene (gerçek filmde reddedildi, bkz. docstring)")
    for ad in ("yatak", "v2yatak"):
        p = alt.add_parser(ad)
        p.add_argument("--bolum", choices=list(AYARLAR), default="cikis")
    alt.add_parser("kendilik")
    n = a.parse_args(argv)

    if n.komut == "kendilik":
        return kendilik()
    if n.komut == "yatak":
        return yatak(n.bolum)
    if n.komut == "v2yatak":
        return v2yatak(n.bolum)
    if n.komut == "oku":
        return oku(Path(n.kareler), n.bolum)
    if n.komut == "v2":
        r = sec_v2(Path(n.kareler), n.bolum, yaz=bool(n.yaz), sentez=bool(n.sentez))
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
        return 0

    r = (sec if n.komut == "sec" else kiyas)(Path(n.kareler), n.bolum)
    goster = {k: v for k, v in r.items() if k not in ("yollar",)}
    print(json.dumps(goster, ensure_ascii=False, indent=1))
    OUT.mkdir(exist_ok=True)
    (OUT / f"{n.komut}_{Path(n.kareler).name}_{n.bolum}.json").write_text(
        json.dumps({k: v for k, v in r.items() if k != "yollar"},
                   ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
