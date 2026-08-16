"""F3b — "mod hatası" kök-sebep fix'i için testler (MITAS_Master_Dup_Kok_Sebep_Plani_v1.md
kök-sebep turu). Bağımsız denetim: harness/master_dup/mod_denetim.py, taban koşusunda
427 filmde 137 "mod hatası" (kayan jenerik statik-sayfa olarak derlendi -- görsel kanıt:
acemiler-cetesi, benimle-dans-et; bkz. data/master_ex/<slug>/reading_master.png).

Kök sebep: split_runs_reading()'in birincil sinyali (split_runs ile aynı desen) TÜM-KARE
cv2.phaseCorrelate'tir. Kredi koyu/düz zemin üstünde kayarken bu sinyal ARKA PLAN
tarafından domine edilir (gerçek footage'da film greni; sürdürülen büyük kayma bazen
p.cut eşiğini de aşıp "kesim" olarak da yorumlanabilir) -- iki yoldan da run "S" (statik/
sayfa) kalır, gerçekte sürekli kayan içerik tekrarlı statik-sayfalar olarak derlenir.

Fix (db_compose_master.py, MITAS_MASTER_V2 flag-gated):
  - `_text_masked_dy_series()`: estimate_offsets() ile AYNI maskeleme deseniyle
    (text_mask + 11x11 dilate + maske-dışını sıfırla) per-frame metin-maskeli dy/response.
  - `_f3b_text_masked_rescue()`: mod_denetim.py'nin TAM AYNI imzası (kayan_oran>=0.35,
    monoton>=0.75, medyan|dy|>=F3_RUN_DY_FLOOR_PX, response>0.10 geçerlilik kapısı) bir
    run-yerel dy/response dilimine uygulanır.
  - `_resolve_reading_runs()`: nihai (birleşmiş) her "S" koşusu bu imzayla yeniden sınanır;
    tutarsa "R"ye (slit) çevrilir.

Test stratejisi (iki katman):
  1. `_f3b_text_masked_rescue` SAF fonksiyon testleri -- elle kurulmuş numpy dizileriyle,
     görüntü sentezi GEREKMEZ. Eşik sınırlarının (taban, örnek-sayısı, monotonluk, response
     kapısı) her biri ayrı ayrı kanıtlanır. "near-miss" testi mod_denetim.json'daki GERÇEK
     ölçümden alınır (kan-kirmizi: kayan_oran=1.0, monoton=0.625, dy_medyan=206.6 -- YÜKSEK
     kayma ama YETERSİZ monotonluk -- 427-film taban koşusunda mod_hatasi=False kalan,
     gerçek bir "yakın-ıskala" örneği; regresyon riskinin somut kanıtı).
  2. Uçtan-uca sentetik-görüntü testleri (split_runs_reading çağrılır, gerçek text_mask/
     phaseCorrelate kod yolundan geçer): sürekli-kayan-künye (bayrak kapalıyken "S" --
     kusur üretilir; bayrak açıkken "R" -- düzeltilir) + gerçek-statik (bayrak ne olursa
     olsun "S" kalır -- regresyon YOK). NOT (dürüst sınır): sentetik sahne burada "tam-kare
     sinyalin arka-plan tarafından domine edilmesi"ni DEĞİL, sürdürülen büyük kaymanın
     p.cut eşiğini aşıp kesim-benzeri yorumlanmasını kullanır -- ikisi de aynı GÖZLEMLENEN
     sonucu (gerçek sürekli kayma yanlışlıkla "S" kalır) üretir ve aynı fix dalıyla
     (F3b, nihai "S" koşusu üzerinde çalışır) düzeltilir; ama gerçek film-greni mekanizması
     BAŞKA bir testtir -- o kanıt gerçek Ex_Frame pilotlarından (acemiler-cetesi,
     benimle-dans-et, solaris) gelir, bkz. GUNLUK.md / plan dokümanı.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MONITOR_PY = PROJECT_ROOT / "OCR-worktree" / "master_png_monitor.py"


def _import_monitor():
    os.environ.setdefault("MITAS_PROJECT_ROOT", str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location("master_png_monitor_f3b", str(MONITOR_PY))
    mon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mon
    spec.loader.exec_module(mon)
    return mon


@pytest.fixture(scope="module")
def dc():
    return _import_monitor().dc


@pytest.fixture(autouse=True)
def _v2_flag_cleanup():
    """Her testten sonra bayrağı temizle -- testler arası sızıntı olmasın."""
    yield
    os.environ.pop("MITAS_MASTER_V2", None)


# --------------------------------------------------------------------------- #
# 1) _f3b_text_masked_rescue -- SAF fonksiyon testleri (görüntü sentezi YOK)
# --------------------------------------------------------------------------- #

def _dizi(*degerler: float) -> np.ndarray:
    return np.asarray(degerler, dtype=np.float64)


def test_guclu_monoton_kayma_kurtarilir(dc):
    """20 örnek, tamamı aynı yönde ~120px, response yüksek -> mod_denetim imzası net
    tutuyor (kayan_oran=1.0, monoton=1.0, medyan=120>=30) -- rescue TETIKLENMELI."""
    dy = _dizi(*([120.0] * 20))
    resp = _dizi(*([0.6] * 20))
    meas = np.ones(20, dtype=bool)
    assert dc._f3b_text_masked_rescue(dy, resp, meas) is True


def test_gercek_statik_titreme_kurtarilmaz(dc):
    """dy hep ~0 (gerçek statik kart + ölçüm gürültüsü) -> kayan_oran çok düşük ->
    rescue ATEŞLENMEMELİ (solaris pilotu tipi: 249 sağlıklı filmin çekirdek deseni)."""
    rng = np.random.default_rng(0)
    dy = rng.normal(0, 0.5, size=20)
    resp = _dizi(*([0.5] * 20))
    meas = np.ones(20, dtype=bool)
    assert dc._f3b_text_masked_rescue(dy, resp, meas) is False


def test_osilasyon_yuksek_kayan_ama_dusuk_monoton_kurtarilmaz(dc):
    """GERÇEK VERİ (mod_denetim.json, taban koşusu, 2026-07-26): 'kan-kirmizi' filmi
    kayan_oran=1.0 (TÜM örnekler >2px hareket ediyor) VE dy_medyan=206.6 (çok büyük) AMA
    monoton=0.625 (<0.75 imza eşiği) -- taban koşusunda mod_hatasi=False kalan 427 filmin
    427-137=290'ından biri (gerçek "yakın-ıskala" örneği, bkz. mod_denetim.json).
    Yön dizisi burada +/- dönüşümlü kurulur ki max(pos_oran,neg_oran)~0.625 çıksın --
    rescue KESİNLİKLE ATEŞLENMEMELİ (aksi halde 168 filmlik 'yüksek-kayan-ama-salınımlı'
    popülasyonu regrese eder -- bkz. görev brifingi 'near-miss' bulgusu)."""
    n = 40
    isaretler = np.array([1 if (i % 8) < 5 else -1 for i in range(n)])  # 5/8 pozitif ~0.625
    dy = isaretler * 200.0
    resp = _dizi(*([0.5] * n))
    meas = np.ones(n, dtype=bool)
    kayan_oran = float((np.abs(dy) > 2.0).mean())
    assert kayan_oran == 1.0  # önkoşul: gerçek 'kan-kirmizi' ölçümüyle aynı rejim
    assert dc._f3b_text_masked_rescue(dy, resp, meas) is False


def test_taban_altindaki_yavas_kayma_kurtarilmaz(dc):
    """M10 'yavaş-kayan-liste' popülasyonuyla karışmasın diye taban (F3_RUN_DY_FLOOR_PX,
    30px) şartı: monoton VE kayan_oran mükemmel ama medyan|dy|=15 (<30) -> rescue YOK.
    Bu, F3b'nin F4 (Şerit-Atlası) popülasyonunu 'çalmadığının' kanıtı."""
    dy = _dizi(*([15.0] * 20))
    resp = _dizi(*([0.6] * 20))
    meas = np.ones(20, dtype=bool)
    assert dc._f3b_text_masked_rescue(dy, resp, meas) is False


def test_yetersiz_ornek_sayisi_kurtarilmaz(dc):
    """SLIT_HY_MIN_MEAS (8) altında istatistik güvenilmez -- kısa run'da rescue YOK,
    şartlar (dy/monoton) mükemmel olsa bile."""
    dy = _dizi(*([150.0] * 5))
    resp = _dizi(*([0.6] * 5))
    meas = np.ones(5, dtype=bool)
    assert dc._f3b_text_masked_rescue(dy, resp, meas) is False


def test_dusuk_response_olcumleri_elenir(dc):
    """mod_denetim.py ile AYNI: response<=0.10 olan ölçümler güvenilmez sayılır. Tüm
    ölçümler bu kapıyı geçemezse (measured=True ama response düşük) geçerli örnek
    sayısı MIN_MEAS altına düşer -> rescue YOK (response filtresi gerçekten uygulanıyor)."""
    dy = _dizi(*([150.0] * 20))
    resp = _dizi(*([0.05] * 20))  # F3B_RESP_FLOOR (0.10) altı
    meas = np.ones(20, dtype=bool)
    assert dc._f3b_text_masked_rescue(dy, resp, meas) is False


def test_olculmemis_kareler_sayilmaz(dc):
    """measured=False (metin yok / okunamayan kare) örnekler valid kümesine girmez."""
    dy = _dizi(*([150.0] * 20))
    resp = _dizi(*([0.6] * 20))
    meas = np.zeros(20, dtype=bool)
    assert dc._f3b_text_masked_rescue(dy, resp, meas) is False


# --------------------------------------------------------------------------- #
# 2) Uçtan-uca sentetik-görüntü testleri (split_runs_reading, gerçek kod yolu)
# --------------------------------------------------------------------------- #

H, W = 240, 300


def _sabit_zemin_gurultusu() -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.normal(0, 5, size=(H, W)).astype(np.float32)


def _metin_satiri(rng: np.random.Generator, w: int, cell: int = 6) -> np.ndarray:
    n = max(4, w // cell)
    pat = (rng.random(n) > 0.45).astype(np.float32) * 220.0
    row = np.repeat(pat, cell)
    if row.shape[0] < w:
        row = np.pad(row, (0, w - row.shape[0]))
    return row[:w]


def _kredi_tuvali(yukseklik: int, seed: int = 7) -> np.ndarray:
    """Yüksek bir 'sanal kayan-künye' tuvali -- pencereleme ile 'offset' ilerletilerek
    ardışık karelerde ÖRTÜŞEN (dolayısıyla faz-korelasyonla izlenebilir) içerik üretir."""
    rng = np.random.default_rng(seed)
    canvas = np.zeros((yukseklik, W), dtype=np.float32)
    y = 0
    while y < yukseklik:
        row_h = 14
        if rng.random() < 0.7:
            canvas[y:y + row_h, :] = np.tile(_metin_satiri(rng, W), (row_h, 1))
        y += 22
    return canvas


def _kare_yaz(tmp_path: Path, tag: str, i: int, gray: np.ndarray) -> str:
    p = tmp_path / f"{tag}_{i:03d}.png"
    bgr = cv2.cvtColor(np.clip(gray, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    ok = cv2.imwrite(str(p), bgr)
    assert ok
    return str(p)


def test_surekli_kayan_kunye_bayrak_kapaliyken_hatali_acikken_duzelir(dc, tmp_path):
    """Kök-senaryo (acemiler-cetesi/benimle-dans-et'in sentetik minyatürü): metin
    bandı (görsel alanın çoğunluğu -- gerçek footage'da bu oran ve zeminin greni
    tam-kare sinyali domine ediyor; burada sürdürülen büyük kayma p.cut eşiğini de
    aşıyor -- İKİ mekanizma da aynı gözlemlenen sonucu üretir: split_runs_reading
    raw etiketi hiç "R" olmuyor, tüm koşu "S" kalıyor) 40px/kare monoton kayıyor.
    Bayrak KAPALI: kusur üretilir (tüm koşu "S" -- kayan içerik tekrarlı statik-sayfa
    olarak derlenecek). Bayrak AÇIK: F3b bunu yakalar, "R"ye çevirir (slit'e gider)."""
    zemin = _sabit_zemin_gurultusu()
    tuval = _kredi_tuvali(2000)
    band_y0, band_h, hiz, n = 20, 200, 40, 20

    frames = []
    for i in range(n):
        gray = np.clip(25.0 + zemin, 0, 255)
        band = tuval[i * hiz: i * hiz + band_h, :]
        gray[band_y0:band_y0 + band_h, :] = np.maximum(gray[band_y0:band_y0 + band_h, :] * 0.15, band)
        frames.append(_kare_yaz(tmp_path, "scroll", i, gray))

    mon = _import_monitor()
    args = mon.make_args()
    p = dc.derive_params(H, W, args)

    os.environ["MITAS_MASTER_V2"] = "0"
    runs_off = dc.split_runs_reading(frames, p, args)
    assert all(label == "S" for _, _, label in runs_off), (
        f"beklenmedik: bayrak kapalıyken zaten 'R' -- sentetik kusur senaryosu kurulamadı: {runs_off}"
    )

    os.environ["MITAS_MASTER_V2"] = "1"
    runs_on = dc.split_runs_reading(frames, p, args)
    assert any(label == "R" for _, _, label in runs_on), (
        f"F3b beklenen kurtarmayı yapmadı -- runs_on={runs_on}"
    )


def test_gercek_statik_kart_regrese_etmez(dc, tmp_path):
    """Hareket YOK (aynı kare tekrarı -- solaris pilotunun sentetik minyatürü): bayrak
    ne olursa olsun 'S' kalmalı. 249 sağlıklı filmin çekirdek deseni -- F3b'nin yanlış-
    pozitif ÜRETMEDİĞİNin en temel kanıtı."""
    zemin = _sabit_zemin_gurultusu()
    tuval = _kredi_tuvali(500)
    band_y0, band_h, n = 20, 200, 20

    frames = []
    for i in range(n):
        gray = np.clip(25.0 + zemin, 0, 255)
        band = tuval[0:band_h, :]  # HEP aynı pencere -- hareket yok
        gray[band_y0:band_y0 + band_h, :] = np.maximum(gray[band_y0:band_y0 + band_h, :] * 0.15, band)
        frames.append(_kare_yaz(tmp_path, "static", i, gray))

    mon = _import_monitor()
    args = mon.make_args()
    p = dc.derive_params(H, W, args)

    os.environ["MITAS_MASTER_V2"] = "0"
    runs_off = dc.split_runs_reading(frames, p, args)
    os.environ["MITAS_MASTER_V2"] = "1"
    runs_on = dc.split_runs_reading(frames, p, args)

    assert all(label == "S" for _, _, label in runs_off)
    assert all(label == "S" for _, _, label in runs_on), (
        f"REGRESYON: gerçek-statik sahne bayrak açıkken 'R'ye çevrildi -- runs_on={runs_on}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-s"]))
