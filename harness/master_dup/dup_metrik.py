#!/usr/bin/env python
"""Şerit-tabanlı master-PNG duplikasyon metriği (M1).

Amaç: `reading_master_runaware` master-PNG'lerindeki (dikey uzun künye
görüntüleri) tekrar bloklarını OBJEKTİF ölçen bağımsız araç. Bu modül
db_compose_master.py / master_png_monitor.py üretim koduna DOKUNMAZ — salt
ölçüm katmanıdır.

Algoritma (bkz. docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md, Görev M1):
  1. Gri + genişlik 400px'e normalize. Şerit yüksekliği = metin-satır
     yüksekliği tahmini x2 (satır yüksekliği: yatay kenar-yoğunluğu profilinin
     otokorelasyon tepesi; bulunamazsa 48px varsayılan). Şeritler %50
     örtüşmeli kaydırılır (arama/eşleştirme penceresi olarak).
  2. Doku kapısı: kenar-yoğunluğu tabanın altındaki şeritler (boş/karanlık
     ara bantlar) metrik DIŞI bırakılır — yanlış-pozitifin ana kaynağı budur
     (iki boş bant birbirine "mükemmel" benzer görünür, ama içerik taşımaz).
  3. Her dokulu şerit çifti (bitişik + UZAK, tüm çiftler — n şerit yüksekse
     şerit dHash'iyle ön-eleme yapılır, yalnız yakın hash'li çiftlere NCC
     çalıştırılır): normalize çapraz-korelasyon, dikey ±şerit/2 hizalama
     aramalı (cv2.matchTemplate ile). Benzerlik >= eşik (varsayılan 0.92) ise
     eş sayılır. NOT: şeritler %50 örtüşmeli olduğundan, hizalama araması
     kendi çakışan komşusuyla (delta=1,2) sahte "mükemmel eşleşme" bulabilir
     (kaynağın kendi pikselini yeniden keşfeder) — bu yüzden yalnızca hizalı
     arama penceresinin kaynakla ASLA geometrik olarak çakışamayacağı minimum
     bir delta'dan (>= ceil((serit_h+max_off)/adim)) itibaren çiftler
     değerlendirilir; bu, gerçek "bitişik" (dokunan ama örtüşmeyen) ve "uzak"
     çiftlerin hepsini kapsar, yalnız geometrik-artefaktı eler.
  4. Blok şartı: tek şerit eşleşmesi SAYILMAZ (meşru tekrar: aynı rol
     başlığı, logo tekrarı gibi). Şerit-indeksinde >= 2 ARDIŞIK şerit AYNI
     ofsetle (şerit-indeks farkı sabit) eşleşirse duplikasyon bloğu sayılır.
     dup_oran = duplike (yalnız SONRAKİ/eşleşen taraf) alan / dokulu toplam
     alan — yani bir çift eşleştiğinde yalnız "kopya" (daha geç konumdaki)
     taraf sayılır, kaynak taraf sayılmaz (aksi halde tam-ikiz bir görüntüde
     dup_oran ~1.0 çıkar; istenen ~0.5 "yedek/gereksiz içerik oranı").
  5. Alan muhasebesi: eşleştirme penceresi (şerit) %50 örtüşmeli olsa da,
     her şeridin kendi ADIM kadar (örtüşmesiz) "hücre"si vardır — hücreler
     görüntü boyunu TAM ve ÇAKIŞMASIZ döşer. doku_kapsami / dup_oran bu
     hücreler üzerinden piksel-ağırlıklı hesaplanır (çifte sayım yok).

CLI: `dup_metrik.py <png|klasör> [--esik 0.92] [--json cikti.json]`
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import cv2

    _CV2 = True
except ImportError:  # pragma: no cover - venv/ocr'de cv2 mevcut, yine de güvenli düş
    _CV2 = False


# --------------------------------------------------------------------------- #
# sabitler
# --------------------------------------------------------------------------- #

NORM_GENISLIK = 400
VARSAYILAN_SATIR_YUKSEKLIGI = 48
VARSAYILAN_ESIK = 0.92

# doku kapısı: bir şeridin kenar-yoğunluğu, görüntüdeki en yoğun şeridin
# şu oranından azsa "boş/dokusuz" sayılır ve metrik dışı bırakılır.
DOKU_ORAN = 0.12
DOKU_MIN_ABS = 1.5

# şerit dHash ön-eleme: n şerit bu eşiği aşarsa tüm-çift NCC yerine önce
# hash-yakınlığıyla aday daraltması yapılır (performans - madde 3/4).
ON_ELEME_ESIK_SERIT_SAYISI = 200
HASH_BOYUT = 8  # 8x8 -> 64 bit dHash
HASH_HAMMING_ESIK = 10  # 64 bitten en çok bu kadar farklıysa "yakın" say

_POPCOUNT_TABLO = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint16)


# --------------------------------------------------------------------------- #
# görüntü yükleme / normalize
# --------------------------------------------------------------------------- #


def _yukle_gri(kaynak) -> np.ndarray:
    """PNG yolundan (str/Path) ya da doğrudan bir ndarray'den gri-tonlama al."""
    if isinstance(kaynak, np.ndarray):
        arr = kaynak
        if arr.ndim == 3:
            im = Image.fromarray(arr).convert("L")
            return np.array(im, dtype=np.uint8)
        return arr.astype(np.uint8)
    im = Image.open(kaynak).convert("L")
    return np.array(im, dtype=np.uint8)


def _normalize_genislik(gray: np.ndarray, hedef_w: int = NORM_GENISLIK) -> np.ndarray:
    h, w = gray.shape
    if w == hedef_w:
        return gray.astype(np.float32)
    olcek = hedef_w / w
    yeni_h = max(1, round(h * olcek))
    if _CV2:
        yeni = cv2.resize(gray, (hedef_w, yeni_h), interpolation=cv2.INTER_AREA)
    else:  # pragma: no cover - fallback yolu
        yeni = np.array(Image.fromarray(gray).resize((hedef_w, yeni_h), Image.BILINEAR))
    return yeni.astype(np.float32)


def _kenar_genlik(gray: np.ndarray) -> np.ndarray:
    """Piksel-başı kenar büyüklüğü (|Sobel_x| + |Sobel_y|)."""
    if _CV2:
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    else:  # pragma: no cover
        gy, gx = np.gradient(gray.astype(np.float32))
    return np.abs(gx) + np.abs(gy)


# --------------------------------------------------------------------------- #
# satır yüksekliği tahmini — yatay kenar-yoğunluğu profili otokorelasyonu
# --------------------------------------------------------------------------- #


def _satir_yuksekligi_tahmin(gray: np.ndarray, min_lag: int = 8, max_lag: int | None = None) -> int:
    """Metin-satır aralığını, dikey Sobel (yatay kenar) profilinin otokorelasyon
    tepesinden tahmin eder. Belirgin bir periyodik tepe bulunamazsa
    VARSAYILAN_SATIR_YUKSEKLIGI (48px) döner."""
    h, w = gray.shape
    if h < min_lag * 4:
        return VARSAYILAN_SATIR_YUKSEKLIGI
    if _CV2:
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    else:  # pragma: no cover
        gy, _ = np.gradient(gray.astype(np.float32))
    profil = np.abs(gy).mean(axis=1)
    profil = profil - profil.mean()
    varyans = float(np.dot(profil, profil))
    if varyans <= 1e-6:
        return VARSAYILAN_SATIR_YUKSEKLIGI
    if max_lag is None:
        max_lag = min(h // 3, 300)
    max_lag = max(max_lag, min_lag + 1)
    skorlar = np.array(
        [float(np.dot(profil[:-lag], profil[lag:])) / varyans for lag in range(min_lag, max_lag + 1)]
    )
    tepe_skor = float(skorlar.max())
    if tepe_skor < 0.15:
        return VARSAYILAN_SATIR_YUKSEKLIGI
    # OKTAV HATASI KORUMASI: global maksimumu değil, en KÜÇÜK lag'i tercih et
    # (periyodik bir satır-aralığı sinyalinin otokorelasyonu 2x, 3x... katlarında
    # da güçlü tepe verir; global argmax genelde bir harmonik'i, temel periyodu
    # değil, seçebilir — bu satır-yüksekliğini gereksiz büyütüp performansı
    # bozar). En küçük lag'den başlayıp tepe skorun makul bir oranına ilk
    # ulaşan lag = temel periyot.
    esik_skor = 0.6 * tepe_skor
    for offset, skor in enumerate(skorlar):
        if skor >= esik_skor:
            return int(min_lag + offset)
    return VARSAYILAN_SATIR_YUKSEKLIGI  # pragma: no cover - skorlar boşsa buraya düşülmez


# --------------------------------------------------------------------------- #
# şerit (pencere + hücre) sınırları
# --------------------------------------------------------------------------- #


def _serit_pencereleri(h: int, serit_h: int, adim: int) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Her şerit için (pencereler, hücreler) döner:
    - pencere: eşleştirme/doku ölçümü için kullanılan, serit_h yükseklikte,
      %50 örtüşmeli arama penceresi.
    - hücre: alan muhasebesi için kullanılan, adim yükseklikte, ÇAKIŞMASIZ
      ve görüntü boyunu TAM döşeyen muhasebe birimi (aynı üst-y'den başlar).
    """
    pencereler: list[tuple[int, int]] = []
    hucreler: list[tuple[int, int]] = []
    if h <= 0 or serit_h <= 0 or adim <= 0:
        return pencereler, hucreler
    y = 0
    while y < h:
        pencereler.append((y, min(y + serit_h, h)))
        hucreler.append((y, min(y + adim, h)))
        if y + serit_h >= h:
            break
        y += adim
    return pencereler, hucreler


# --------------------------------------------------------------------------- #
# şerit dHash (ön-eleme)
# --------------------------------------------------------------------------- #


def _serit_hash(serit: np.ndarray, boyut: int = HASH_BOYUT) -> int:
    if serit.size == 0:
        return 0
    kaynak_u8 = np.clip(serit, 0, 255).astype(np.uint8)
    if _CV2:
        kucuk = cv2.resize(kaynak_u8, (boyut + 1, boyut), interpolation=cv2.INTER_AREA)
    else:  # pragma: no cover
        kucuk = np.array(Image.fromarray(kaynak_u8).resize((boyut + 1, boyut)))
    fark = kucuk[:, 1:] > kucuk[:, :-1]
    bit = 0
    for v in fark.flatten():
        bit = (bit << 1) | int(v)
    return bit


def _hash_dizisine_cevir(hashler: list[int]) -> np.ndarray:
    """64-bit int hash listesini (N,8) uint8 byte dizisine çevirir (vektörel Hamming için)."""
    n = len(hashler)
    arr = np.zeros((n, 8), dtype=np.uint8)
    for i, hh in enumerate(hashler):
        for k in range(8):
            arr[i, k] = (hh >> (8 * k)) & 0xFF
    return arr


# --------------------------------------------------------------------------- #
# hizalı NCC (dikey ±şerit/2 arama)
# --------------------------------------------------------------------------- #


def _ncc_en_iyi(gray: np.ndarray, kaynak_sin: tuple[int, int], hedef_sin: tuple[int, int], max_off: int) -> float:
    """kaynak şeridini, hedef şeridi çevresinde ±max_off dikey kaydırarak
    en iyi normalize çapraz-korelasyonu (NCC) döner."""
    y1, y2 = kaynak_sin
    template = gray[y1:y2, :]
    th = y2 - y1
    if th <= 0 or template.size == 0:
        return 0.0
    hy1, hy2 = hedef_sin
    ay1 = max(0, hy1 - max_off)
    ay2 = min(gray.shape[0], hy2 + max_off)
    bolge = gray[ay1:ay2, :]
    if bolge.shape[0] < th:
        return 0.0
    if _CV2:
        sonuc = cv2.matchTemplate(bolge.astype(np.float32), template.astype(np.float32), cv2.TM_CCOEFF_NORMED)
        sonuc = np.nan_to_num(sonuc, nan=0.0, posinf=1.0, neginf=-1.0)
        return float(sonuc.max()) if sonuc.size else 0.0
    # numpy-only düşüş yolu (cv2 yoksa): kaba kaydırmalı Pearson korelasyonu
    en_iyi = -1.0  # pragma: no cover
    a = template.astype(np.float64)
    a = a - a.mean()
    a_norm = np.sqrt((a * a).sum())
    if a_norm == 0:
        return 0.0
    for off in range(0, bolge.shape[0] - th + 1):
        b = bolge[off : off + th, :].astype(np.float64)
        b = b - b.mean()
        b_norm = np.sqrt((b * b).sum())
        if b_norm == 0:
            continue
        korelasyon = float((a * b).sum() / (a_norm * b_norm))
        en_iyi = max(en_iyi, korelasyon)
    return max(en_iyi, 0.0)


# --------------------------------------------------------------------------- #
# ana ölçüm
# --------------------------------------------------------------------------- #


def olc(
    png_yolu, esik: float = VARSAYILAN_ESIK, satir_yuksekligi: int | None = None,
    *, korunan_araliklari: list[tuple[int, int]] | None = None,
) -> dict:
    """Master-PNG üzerinde şerit-tabanlı dup-metriğini hesaplar.

    Args:
        png_yolu: PNG dosya yolu (str/Path) — CLI/gerçek kullanım.
        esik: NCC benzerlik eşiği (varsayılan 0.92).
        satir_yuksekligi: testte determinizm için otokorelasyon tahminini
            atlayıp doğrudan satır yüksekliği vermek için opsiyonel eklenti
            (public arayüzü bozmaz — verilmezse otomatik tahmin edilir).
        korunan_araliklari: K3 (Görev M8, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md)
            -- composer'ın manifest'e kaydettiği `korunan_esleme` (protected)
            bloklarının ORİJİNAL-görüntü y-aralıkları [(y0,y1), ...]. Verilirse,
            "es" (tekrar/duplike) tarafı bu aralıklardan biriyle ÇOĞUNLUKLA
            (>=%50 piksel) örtüşen eşleşme blokları dup_oran hesabından
            (tekrar_mask) DIŞLANIR -- meşru-farklı-metin (Sınıf C) metrik
            yanlış-pozitifini düzeltir; composer'ın SKIP/KORU kararını
            ETKİLEMEZ (yalnız bu ÖLÇÜM katmanında). Verilmezse davranış eskisiyle
            BİREBİR aynı (varsayılan None -- geriye-dönük uyumlu).

    Returns:
        {"dup_oran": float, "blok_sayisi": int, "bloklar": [...],
         "boy": [W,H], "doku_kapsami": float}
    """
    gray0 = _yukle_gri(png_yolu)
    h0, w0 = gray0.shape
    gray = _normalize_genislik(gray0)
    olcek = gray.shape[1] / w0 if w0 else 1.0
    h = gray.shape[0]

    sy = satir_yuksekligi if satir_yuksekligi else _satir_yuksekligi_tahmin(gray)
    serit_h = max(8, int(sy) * 2)
    adim = max(4, serit_h // 2)

    pencereler, hucreler = _serit_pencereleri(h, serit_h, adim)
    n = len(pencereler)

    if n == 0:
        return {
            "dup_oran": 0.0,
            "blok_sayisi": 0,
            "bloklar": [],
            "boy": [int(w0), int(h0)],
            "doku_kapsami": 0.0,
        }

    kenar = _kenar_genlik(gray)
    yogunluklar = np.array(
        [float(kenar[y1:y2].mean()) if y2 > y1 else 0.0 for (y1, y2) in pencereler],
        dtype=np.float32,
    )
    en_yogun = float(yogunluklar.max()) if yogunluklar.size else 0.0
    taban = max(DOKU_MIN_ABS, DOKU_ORAN * en_yogun)
    doku_mask = yogunluklar >= taban
    textured_idx = np.nonzero(doku_mask)[0]

    # --- eşleşme adayları + NCC ---
    max_off = adim
    # ÖNEMLİ: şeritler %50 örtüşmeli olduğundan, ±max_off hizalama araması
    # yakın-delta çiftlerinde kaynağın KENDİ pikselini yeniden keşfedip
    # yapay (sahte) bir "eşleşme" üretebilir (i ve i+1 zaten yarı yarıya aynı
    # pikselleri paylaşıyor). Bunu önlemek için, hizalanmış arama penceresi
    # kaynağın gerçek aralığıyla ASLA çakışmayacak minimum delta zorunlu
    # kılınır: (delta*adim - max_off) >= serit_h  =>  delta >= ceil((serit_h+max_off)/adim).
    min_delta = -(-(serit_h + max_off) // adim)  # tavana yuvarlama
    eslesmeler_by_delta: dict[int, dict[int, float]] = {}

    use_prefilter = n > ON_ELEME_ESIK_SERIT_SAYISI
    if use_prefilter and textured_idx.size:
        hashler = [_serit_hash(gray[pencereler[i][0] : pencereler[i][1], :]) for i in textured_idx]
        hash_arr = _hash_dizisine_cevir(hashler)

    for a_pos in range(textured_idx.size):
        i = int(textured_idx[a_pos])
        if use_prefilter:
            xor = hash_arr[a_pos + 1 :] ^ hash_arr[a_pos]
            if xor.size:
                dist = _POPCOUNT_TABLO[xor].sum(axis=1)
                yakin_pos = np.nonzero(dist <= HASH_HAMMING_ESIK)[0] + (a_pos + 1)
                j_list = [int(j) for j in textured_idx[yakin_pos].tolist() if j - i >= min_delta]
            else:
                j_list = []
        else:
            j_list = [int(j) for j in textured_idx if j - i >= min_delta]

        for j in j_list:
            benzerlik = _ncc_en_iyi(gray, pencereler[i], pencereler[j], max_off)
            if benzerlik >= esik:
                delta = j - i
                mevcut = eslesmeler_by_delta.setdefault(delta, {})
                if i not in mevcut or benzerlik > mevcut[i]:
                    mevcut[i] = benzerlik

    # --- blok şartı: aynı delta'da >= 2 ardışık şerit-indeksi ---
    ham_bloklar: list[tuple[int, int, int, float]] = []  # (i0, i1, delta, ort_benzerlik)
    for delta, esleme in eslesmeler_by_delta.items():
        idxs = sorted(esleme.keys())
        run: list[int] = []
        for k in idxs:
            if run and k == run[-1] + 1:
                run.append(k)
            else:
                if len(run) >= 2:
                    benzs = [esleme[x] for x in run]
                    ham_bloklar.append((run[0], run[-1], delta, float(np.mean(benzs))))
                run = [k]
        if len(run) >= 2:
            benzs = [esleme[x] for x in run]
            ham_bloklar.append((run[0], run[-1], delta, float(np.mean(benzs))))

    # --- alan muhasebesi (yalnız "es" / sonraki-konum tarafı sayılır) ---
    hucre_piksel = np.array([c2 - c1 for (c1, c2) in hucreler], dtype=np.float64)
    tekrar_mask = np.zeros(n, dtype=bool)
    bloklar_out = []
    for i0, i1, delta, benzerlik in sorted(ham_bloklar, key=lambda b: b[0]):
        j0, j1 = i0 + delta, i1 + delta
        if j1 >= n:
            continue
        y1n, y2n = hucreler[i0][0], hucreler[i1][1]
        ey1n, ey2n = hucreler[j0][0], hucreler[j1][1]
        es_y1_orig = ey1n / olcek
        es_y2_orig = ey2n / olcek
        # K3: "es" (tekrar) tarafı bir korunan aralıkla ÇOĞUNLUKLA örtüşüyorsa
        # bu blok dup_oran'ın tekrar_mask'ına KATILMAZ (metrik-katmanı düzeltmesi,
        # composer kararını etkilemez).
        korunan_disi = False
        if korunan_araliklari:
            es_h = max(1.0, es_y2_orig - es_y1_orig)
            for ky0, ky1 in korunan_araliklari:
                kesisim = max(0.0, min(es_y2_orig, ky1) - max(es_y1_orig, ky0))
                if kesisim / es_h >= 0.5:
                    korunan_disi = True
                    break
        if not korunan_disi:
            tekrar_mask[j0 : j1 + 1] = True
        blok = {
            "y1": int(round(y1n / olcek)),
            "y2": int(round(y2n / olcek)),
            "es_y1": int(round(es_y1_orig)),
            "es_y2": int(round(es_y2_orig)),
            "benzerlik": round(float(benzerlik), 4),
        }
        if korunan_disi:
            blok["korunan_disi_birakildi"] = True
        bloklar_out.append(blok)

    doku_piksel_toplam = float(hucre_piksel[doku_mask].sum())
    tekrar_piksel_toplam = float(hucre_piksel[tekrar_mask & doku_mask].sum())
    toplam_piksel = float(hucre_piksel.sum())

    dup_oran = (tekrar_piksel_toplam / doku_piksel_toplam) if doku_piksel_toplam > 0 else 0.0
    doku_kapsami = (doku_piksel_toplam / toplam_piksel) if toplam_piksel > 0 else 0.0

    return {
        "dup_oran": round(float(dup_oran), 4),
        "blok_sayisi": len(bloklar_out),
        "bloklar": bloklar_out,
        "boy": [int(w0), int(h0)],
        "doku_kapsami": round(float(doku_kapsami), 4),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _cli(argv=None):
    ap = argparse.ArgumentParser(description="Şerit-tabanlı master-PNG dup-metriği (M1)")
    ap.add_argument("yol", help="PNG dosyası veya PNG'leri içeren klasör")
    ap.add_argument("--esik", type=float, default=VARSAYILAN_ESIK, help="NCC benzerlik eşiği (varsayılan 0.92)")
    ap.add_argument("--json", dest="json_cikti", default=None, help="Sonucu JSON olarak bu yola yaz")
    args = ap.parse_args(argv)

    yol = Path(args.yol)
    if yol.is_dir():
        sonuc = {}
        for png in sorted(yol.glob("*.png")):
            sonuc[png.name] = olc(str(png), esik=args.esik)
    elif yol.is_file():
        sonuc = olc(str(yol), esik=args.esik)
    else:
        print(f"Bulunamadı: {yol}", file=sys.stderr)
        return 1

    metin = json.dumps(sonuc, ensure_ascii=False, indent=2)
    if args.json_cikti:
        Path(args.json_cikti).write_text(metin, encoding="utf-8")
        print(f"Yazıldı: {args.json_cikti}")
    else:
        print(metin)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
