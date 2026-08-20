#!/usr/bin/env python3
"""Adaptif Slit İyileştirme Benchmark'ı — Eski vs Yeni karşılaştırma.

4 iyileştirmeyi (Otsu, dy Smoothing, Fuzzy Token, Sub-Pixel) ölçer:
  1. TABAN: tüm bayraklar KAPALI (eski davranış, bit-birebir)
  2. HEPSI: tüm bayraklar AÇIK
  3. Her bayrak TEK TEK açık (hangisi ne kadar katkı sağlıyor?)

Her koşu için ölçülen:
  - Master PNG yüksekliği (boy)
  - Segment sayısı
  - Scroll/duraksama/kesme dağılımı
  - Üretim süresi
  - dup_metrik skoru (varsa)
  - Eski vs yeni piksel farkı (SSIM)

Kullanım:
  venv=/opt/mitas/venvs/ocr/bin/python
  $venv benchmark_iyilestirmeler.py --cikti-kok /tmp/benchmark_out
  $venv benchmark_iyilestirmeler.py --sluglar slug1,slug2,slug3 --cikti-kok ...
  $venv benchmark_iyilestirmeler.py --rapor /tmp/benchmark_out  # sadece rapor

Çıktı: <cikti-kok>/BENCHMARK_RAPORU.md + film başına karşılaştırma PNG'leri.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# dup_metrik ve adaptif_slit aynı dizinde
sys.path.insert(0, str(Path(__file__).parent))

EX_KARE_ROOT = Path("/home/cagatay/Ex_Frame")
EX_SUFFIX = "-exit_frames"

# Benchmark'ta kullanılacak varsayılan test filmleri — günlükte kanıtlanmış
# farklı sınıfları temsil ediyorlar:
#   footage-üstü kayan, değişken hız, dikiş tekrarı, soluk kart,
#   dissolve zinciri, parlak zemin, THE END tekrarı
VARSAYILAN_SLUGLAR = [
    "benimle-dans-et",      # footage-üstü kayan
    "gercek-yalanlar",      # değişken hız, duraksama
    "acemiler-cetesi",      # dikiş tekrarı
    "karadeniz",            # soluk kartlar, grenli
    "kucuk-dev-adam",       # dissolve zinciri
    "parti",                # parlak zemin
    "affedilmeyenler",      # THE END tekrarı
    "jetgiller",            # statik zemin, farklı yazı
    "hayat-agaci",          # kar yağışı, Farsça
    "totoro",               # çizgi-film çerçevesi
    "aydaki-adam",          # dikiş kayması
    "son-konser",           # uzun kayan liste
    "havaci",               # loş metin, soluk
    "komiser-cordier-yuksek-guvenlik",  # sabit fotoğraf üstünde kayan
]

# Bayrak kombinasyonları
KOSU_PLANI = {
    "TABAN":       {"OTSU": "0", "DY_SMOOTH": "0", "FUZZY": "0", "SUBPX": "0"},
    "OTSU":        {"OTSU": "1", "DY_SMOOTH": "0", "FUZZY": "0", "SUBPX": "0"},
    "DY_SMOOTH":   {"OTSU": "0", "DY_SMOOTH": "1", "FUZZY": "0", "SUBPX": "0"},
    "FUZZY":       {"OTSU": "0", "DY_SMOOTH": "0", "FUZZY": "1", "SUBPX": "0"},
    "SUBPX":       {"OTSU": "0", "DY_SMOOTH": "0", "FUZZY": "0", "SUBPX": "1"},
    "HEPSI":       {"OTSU": "1", "DY_SMOOTH": "1", "FUZZY": "1", "SUBPX": "1"},
}


def _bayrak_ayarla(plan: dict[str, str]) -> None:
    """Adaptif_slit modül-düzeyindeki bayrakları ayarla."""
    os.environ["MITAS_IYIL_OTSU"] = plan["OTSU"]
    os.environ["MITAS_IYIL_DY_SMOOTH"] = plan["DY_SMOOTH"]
    os.environ["MITAS_IYIL_FUZZY"] = plan["FUZZY"]
    os.environ["MITAS_IYIL_SUBPX"] = plan["SUBPX"]
    # modül-düzeyi değişkenlerini güncelle (import zamanında okunmuştu)
    import ibrahimovic as adaptif_slit as _m
    _m.IYIL_OTSU = plan["OTSU"] == "1"
    _m.IYIL_DY_SMOOTH = plan["DY_SMOOTH"] == "1"
    _m.IYIL_FUZZY = plan["FUZZY"] == "1"
    _m.IYIL_SUBPX = plan["SUBPX"] == "1"


def _mevcut_sluglar(slug_listesi: list[str]) -> list[str]:
    """Ex_Frame'de karesi bulunan slug'ları filtrele."""
    mevcut = []
    for s in slug_listesi:
        d = EX_KARE_ROOT / f"{s}{EX_SUFFIX}"
        if d.is_dir() and any(d.glob("exit_*.png")):
            mevcut.append(s)
    return mevcut


def _ssim_basit(a: np.ndarray, b: np.ndarray) -> float:
    """Basitleştirilmiş SSIM (yapısal benzerlik): 0-1 arası.
    İki farklı boyuttaki master'ı ortak yüksekliğe kırpar."""
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    if h < 10 or w < 10:
        return 0.0
    a_k, b_k = a[:h, :w], b[:h, :w]
    ga = cv2.cvtColor(a_k, cv2.COLOR_BGR2GRAY).astype(np.float64)
    gb = cv2.cvtColor(b_k, cv2.COLOR_BGR2GRAY).astype(np.float64)
    c1, c2 = 6.5025, 58.5225  # (0.01*255)^2, (0.03*255)^2
    mu_a, mu_b = ga.mean(), gb.mean()
    sig_a, sig_b = ga.std(), gb.std()
    sig_ab = ((ga - mu_a) * (gb - mu_b)).mean()
    ssim = ((2*mu_a*mu_b + c1) * (2*sig_ab + c2)) / \
           ((mu_a**2 + mu_b**2 + c1) * (sig_a**2 + sig_b**2 + c2))
    return float(ssim)


def _dup_skoru(png_yolu: Path) -> float | None:
    """dup_metrik.py ile duplikasyon skoru ölç."""
    try:
        from dup_metrik import olc
        sonuc = olc(str(png_yolu))
        return sonuc.get("dup_oran", None)
    except Exception:
        return None


def _kiyas_png(taban_png: np.ndarray, yeni_png: np.ndarray,
               slug: str, kosu: str, kok: Path) -> None:
    """Taban ve yeni master'ı yan yana (veya üst üste) kaydet."""
    h = min(taban_png.shape[0], yeni_png.shape[0], 3000)  # ilk 3000px
    w_t, w_y = taban_png.shape[1], yeni_png.shape[1]
    w = max(w_t, w_y)
    # etiket bandı
    etiket_h = 30
    t_kismi = taban_png[:h, :min(w_t, w)]
    y_kismi = yeni_png[:h, :min(w_y, w)]
    # genişliği eşitle
    if t_kismi.shape[1] < w:
        t_kismi = cv2.copyMakeBorder(t_kismi, 0, 0, 0, w - t_kismi.shape[1],
                                     cv2.BORDER_CONSTANT, value=(0, 0, 0))
    if y_kismi.shape[1] < w:
        y_kismi = cv2.copyMakeBorder(y_kismi, 0, 0, 0, w - y_kismi.shape[1],
                                     cv2.BORDER_CONSTANT, value=(0, 0, 0))
    # etiket yaz
    bant_t = np.zeros((etiket_h, w, 3), dtype=np.uint8)
    bant_y = np.zeros((etiket_h, w, 3), dtype=np.uint8)
    cv2.putText(bant_t, f"TABAN ({slug})", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(bant_y, f"{kosu} ({slug})", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    ayirici = np.full((4, w, 3), 128, dtype=np.uint8)
    birlesik = np.vstack([bant_t, t_kismi, ayirici, bant_y, y_kismi])
    dosya = kok / f"kiyas_{slug}_{kosu}.png"
    cv2.imwrite(str(dosya), birlesik)


def tek_kosu(slug: str, kosu_adi: str, bayraklar: dict[str, str],
             kok: Path) -> dict:
    """Bir slug'ı verilen bayraklarla koştur, sonuçları döndür."""
    _bayrak_ayarla(bayraklar)
    import ibrahimovic as adaptif_slit
    # modül cache'lerini temizle (token önbelleği vb.)
    adaptif_slit.token_onbellek = {}  # compose_adaptif içinde tanımlı ama...

    t0 = time.time()
    kanvas, manifest = adaptif_slit.compose_adaptif(slug)
    sure = round(time.time() - t0, 2)

    sonuc = {
        "slug": slug, "kosu": kosu_adi, "sure_s": sure,
        "durum": manifest.get("durum", "?"),
    }
    if kanvas is not None:
        dosya = kok / kosu_adi / slug / "reading_master.png"
        dosya.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(dosya), kanvas)
        sonuc["boy"] = int(kanvas.shape[0])
        sonuc["genislik"] = int(kanvas.shape[1])
        sonuc["segment"] = manifest.get("segment", 0)
        sonuc["sinif_sayimi"] = manifest.get("sinif_sayimi", {})
        sonuc["olcum_yolu"] = manifest.get("olcum_yolu", "?")
        sonuc["dup_oran"] = _dup_skoru(dosya)
        sonuc["png_yolu"] = str(dosya)
    else:
        sonuc["boy"] = 0
        sonuc["segment"] = 0
    return sonuc


def karsilastirma_tablosu(sonuclar: dict[str, dict[str, dict]]) -> str:
    """Tüm sonuçları karşılaştırma tablosu olarak markdown formatla."""
    satirlar = []
    satirlar.append("| Film | Koşu | Boy | Segment | Süre(s) | Dup Oranı | Ölçüm Yolu | Boy Farkı |")
    satirlar.append("|---|---|---:|---:|---:|---:|---|---:|")

    for slug in sorted(sonuclar.keys()):
        kosular = sonuclar[slug]
        taban = kosular.get("TABAN", {})
        taban_boy = taban.get("boy", 0)
        for kosu_adi in ["TABAN", "OTSU", "DY_SMOOTH", "FUZZY", "SUBPX", "HEPSI"]:
            s = kosular.get(kosu_adi)
            if s is None:
                continue
            boy = s.get("boy", 0)
            fark = boy - taban_boy if kosu_adi != "TABAN" else 0
            fark_str = f"{fark:+d}" if fark != 0 else "—"
            dup = s.get("dup_oran")
            dup_str = f"{dup:.4f}" if dup is not None else "—"
            satirlar.append(
                f"| {slug} | **{kosu_adi}** | {boy} | {s.get('segment', '—')} | "
                f"{s.get('sure_s', '—')} | {dup_str} | {s.get('olcum_yolu', '—')} | {fark_str} |"
            )
    return "\n".join(satirlar)


def ssim_tablosu(sonuclar: dict[str, dict[str, dict]]) -> str:
    """TABAN vs HEPSI yapısal benzerlik tablosu."""
    satirlar = []
    satirlar.append("| Film | SSIM (Taban↔Hepsi) | Boy Taban | Boy Hepsi | Dup Taban | Dup Hepsi |")
    satirlar.append("|---|---:|---:|---:|---:|---:|")
    for slug in sorted(sonuclar.keys()):
        t = sonuclar[slug].get("TABAN", {})
        h = sonuclar[slug].get("HEPSI", {})
        t_png = t.get("png_yolu")
        h_png = h.get("png_yolu")
        ssim = "—"
        if t_png and h_png:
            ta = cv2.imread(t_png)
            ha = cv2.imread(h_png)
            if ta is not None and ha is not None:
                ssim = f"{_ssim_basit(ta, ha):.4f}"
        t_dup = f"{t.get('dup_oran', 0):.4f}" if t.get("dup_oran") is not None else "—"
        h_dup = f"{h.get('dup_oran', 0):.4f}" if h.get("dup_oran") is not None else "—"
        satirlar.append(
            f"| {slug} | {ssim} | {t.get('boy', '—')} | {h.get('boy', '—')} | {t_dup} | {h_dup} |"
        )
    return "\n".join(satirlar)


def rapor_yaz(sonuclar: dict, kok: Path) -> None:
    """Kapsamlı benchmark raporunu markdown olarak yaz."""
    rapor = [
        "# Adaptif Slit İyileştirme Benchmark Raporu",
        f"> Tarih: {time.strftime('%Y-%m-%d %H:%M')}",
        f"> Film sayısı: {len(sonuclar)}",
        "",
        "## Bayraklar",
        "| Bayrak | Açıklama |",
        "|---|---|",
        "| `MITAS_IYIL_OTSU` | Otsu adaptif eşikleme (sabit 110 yerine) |",
        "| `MITAS_IYIL_DY_SMOOTH` | Scroll dy'ye median filtre (titreme düzeltme) |",
        "| `MITAS_IYIL_FUZZY` | Levenshtein ≤ 1 toleranslı token eşleştirme |",
        "| `MITAS_IYIL_SUBPX` | Sub-pixel bilinear interpolasyon |",
        "",
        "## Detaylı Karşılaştırma",
        karsilastirma_tablosu(sonuclar),
        "",
        "## TABAN vs HEPSİ — Yapısal Benzerlik (SSIM)",
        ssim_tablosu(sonuclar),
        "",
        "## Yorumlama Rehberi",
        "- **Boy farkı**: Pozitif = daha fazla içerik yakalandı (genellikle iyi); "
        "negatif = daha iyi dedup veya daha az tekrar",
        "- **SSIM ≈ 1.0**: İki çıktı neredeyse aynı (iyileştirme etki etmemiş)",
        "- **SSIM < 0.95**: Görünür fark var — `kiyas_*.png` dosyalarını incele",
        "- **Dup oranı**: Düşük = iyi (tekrar az). 0.10 üstü sağlıksız",
        "",
        f"> Karşılaştırma görselleri: `{kok}/kiyas_*.png`",
    ]
    dosya = kok / "BENCHMARK_RAPORU.md"
    dosya.write_text("\n".join(rapor), encoding="utf-8")
    print(f"\n📊 Rapor yazıldı: {dosya}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sluglar", help="virgülle ayrılmış slug listesi")
    ap.add_argument("--cikti-kok", required=True, help="çıktı dizini")
    ap.add_argument("--sadece", help="sadece belirli koşuları çalıştır (virgülle)")
    ap.add_argument("--kiyas-png", action="store_true", default=True,
                    help="taban vs yeni karşılaştırma PNG'leri üret")
    args = ap.parse_args(argv)

    kok = Path(args.cikti_kok)
    kok.mkdir(parents=True, exist_ok=True)

    # slug listesi
    if args.sluglar:
        slug_listesi = [s.strip() for s in args.sluglar.split(",")]
    else:
        slug_listesi = VARSAYILAN_SLUGLAR

    mevcut = _mevcut_sluglar(slug_listesi)
    if not mevcut:
        print(f"❌ Hiçbir slug bulunamadı: {slug_listesi}")
        print(f"   Aranan dizin: {EX_KARE_ROOT}")
        return 1

    print(f"🎬 {len(mevcut)} film bulundu: {', '.join(mevcut)}")

    # hangi koşuları çalıştır?
    if args.sadece:
        kosu_isimleri = [k.strip().upper() for k in args.sadece.split(",")]
        # TABAN her zaman lazım
        if "TABAN" not in kosu_isimleri:
            kosu_isimleri.insert(0, "TABAN")
    else:
        kosu_isimleri = list(KOSU_PLANI.keys())

    sonuclar: dict[str, dict[str, dict]] = {}

    for slug in mevcut:
        print(f"\n{'='*60}")
        print(f"  📽  {slug}")
        print(f"{'='*60}")
        sonuclar[slug] = {}

        for kosu_adi in kosu_isimleri:
            if kosu_adi not in KOSU_PLANI:
                print(f"  ⚠️  Bilinmeyen koşu: {kosu_adi}, atlanıyor")
                continue
            bayraklar = KOSU_PLANI[kosu_adi]
            acik = [k for k, v in bayraklar.items() if v == "1"]
            etiket = ", ".join(acik) if acik else "—"
            print(f"  🏃 {kosu_adi:12s} [{etiket:30s}] ... ", end="", flush=True)

            s = tek_kosu(slug, kosu_adi, bayraklar, kok)
            sonuclar[slug][kosu_adi] = s

            boy = s.get("boy", 0)
            dup = s.get("dup_oran")
            dup_str = f"dup={dup:.4f}" if dup is not None else "dup=—"
            print(f"boy={boy:6d}  seg={s.get('segment', '—'):3}  "
                  f"{dup_str}  {s.get('sure_s', '?')}s")

        # karşılaştırma PNG'leri
        if args.kiyas_png and "TABAN" in sonuclar[slug]:
            taban_yol = sonuclar[slug]["TABAN"].get("png_yolu")
            if taban_yol:
                taban_png = cv2.imread(taban_yol)
                if taban_png is not None:
                    for kosu_adi in kosu_isimleri:
                        if kosu_adi == "TABAN":
                            continue
                        yeni_yol = sonuclar[slug].get(kosu_adi, {}).get("png_yolu")
                        if yeni_yol:
                            yeni_png = cv2.imread(yeni_yol)
                            if yeni_png is not None:
                                _kiyas_png(taban_png, yeni_png, slug, kosu_adi, kok)

    # JSON kaydet
    json_dosya = kok / "benchmark_sonuclar.json"
    json_dosya.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print(f"\n📁 JSON: {json_dosya}")

    # rapor yaz
    rapor_yaz(sonuclar, kok)

    # özet
    print(f"\n{'='*60}")
    print("ÖZET")
    print(f"{'='*60}")
    for slug in sorted(sonuclar.keys()):
        t = sonuclar[slug].get("TABAN", {})
        h = sonuclar[slug].get("HEPSI", {})
        boy_fark = h.get("boy", 0) - t.get("boy", 0)
        t_dup = t.get("dup_oran")
        h_dup = h.get("dup_oran")
        dup_degisim = ""
        if t_dup is not None and h_dup is not None:
            fark = h_dup - t_dup
            dup_degisim = f"dup: {fark:+.4f}"
        print(f"  {slug:40s}  boy: {boy_fark:+6d}  {dup_degisim}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
