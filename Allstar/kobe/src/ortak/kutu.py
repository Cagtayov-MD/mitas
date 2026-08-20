"""PaddleOCR detection-only kutu sinyali — jenerik/sahne ayırıcı.

Konsey (GLM+Kimi, 2026-07-21) + ölçüm: kenar-yoğunluğu sahne kenarlarına doyuyor;
PaddleOCR GERÇEK metni bulur. Sahne=0-1 kutu, jenerik=sürdürülen ≥2 kutu.
Geçiş (0→≥2) onset'i işaretliyor. Hızlı: ~0.02 sn/kare (det-only, rec kapalı).

Yapı filtresi (GLM): tek geniş kutu = başlık (elenir); yalnız alt %20 = altyazı/
haber-bandı (elenir); jenerik kutuları ekrana yayılır + düzenli.
"""
from __future__ import annotations

import json
import os

import numpy as np

_DET = None

# ── det-önbelleği ────────────────────────────────────────────────────────
# Kare→kutu sonucu deterministik; film klasörü başına _det_cache.json tutulur.
# Davranışı DEĞİŞTİRMEZ, sadece tekrar hesabı keser. MITAS_DET_CACHE=0 kapatır.
_CACHE: dict[str, dict] = {}      # dizin → {basename: analiz_dict}
_KIRLI: dict[str, int] = {}       # dizin → kaydedilmemiş güncelleme sayısı


def _cache_acik() -> bool:
    return os.environ.get("MITAS_DET_CACHE", "1") != "0"


def _cache_yolu(dizin: str) -> str:
    return os.path.join(dizin, "_det_cache.json")


def _cache_al(dizin: str) -> dict:
    if dizin not in _CACHE:
        try:
            _CACHE[dizin] = json.load(open(_cache_yolu(dizin), encoding="utf-8"))
        except Exception:
            _CACHE[dizin] = {}
        _KIRLI[dizin] = 0
    return _CACHE[dizin]


def _cache_kaydet(dizin: str) -> None:
    if _KIRLI.get(dizin, 0) == 0:
        return
    tmp = _cache_yolu(dizin) + f".tmp{os.getpid()}"
    try:
        json.dump(_CACHE[dizin], open(tmp, "w", encoding="utf-8"))
        os.replace(tmp, _cache_yolu(dizin))
        _KIRLI[dizin] = 0
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass


def _det():
    global _DET
    if _DET is None:
        from paddleocr import TextDetection
        _DET = TextDetection()
    return _DET


def _polys(path: str):
    try:
        r = _det().predict(path)
        p = r[0].get("dt_polys") if r else None
        return p if p is not None else []
    except Exception:
        return []


def kutu_analiz(path: str, H: int = 480, W: int = 600) -> dict:
    """Bir karenin kutu yapısı → jenerik-benzeri mi. (det-önbellekli)"""
    if _cache_acik():
        dizin, ad = os.path.split(path)
        c = _cache_al(dizin)
        if ad in c:
            return c[ad]
        sonuc = _kutu_analiz_hesapla(path, H, W)
        c[ad] = sonuc
        _KIRLI[dizin] = _KIRLI.get(dizin, 0) + 1
        if _KIRLI[dizin] >= 200:
            _cache_kaydet(dizin)
        return sonuc
    return _kutu_analiz_hesapla(path, H, W)


def _kutu_analiz_hesapla(path: str, H: int = 480, W: int = 600) -> dict:
    polys = _polys(path)
    n = len(polys)
    if n == 0:
        return {"n": 0, "jenerik_benzeri": False, "yayilim": 0.0}

    ymerk, xgen, xkonum = [], [], []
    for p in polys:
        xs = [pt[0] for pt in p]
        ys = [pt[1] for pt in p]
        xgen.append(max(xs) - min(xs))
        ymerk.append((min(ys) + max(ys)) / 2)
        xkonum.append((min(xs) + max(xs)) / 2)
    ymerk = np.array(ymerk)
    xgen = np.array(xgen)

    # gerçek görsel boyutunu al (varsayılan 600x480, ama değişebilir)
    try:
        from PIL import Image
        W, H = Image.open(path).size
    except Exception:
        pass

    tek_genis = bool(n == 1 and xgen[0] > W * 0.6)          # başlık kartı
    alt_only = bool((ymerk > H * 0.8).all())                 # altyazı/haber bandı
    yayilim = float((ymerk.max() - ymerk.min()) / H) if n > 1 else 0.0

    # jenerik: ≥2 kutu, tek-geniş-başlık değil, yalnız-alt değil
    jenerik = (n >= 2) and (not tek_genis) and (not alt_only)
    return {"n": n, "jenerik_benzeri": jenerik, "yayilim": yayilim,
            "tek_genis": tek_genis, "alt_only": alt_only}


def kutu_serisi(frame_yollari: list[str], stride: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Kare listesinde jenerik-benzeri kutu bayrağı + kutu sayısı serisi.
    stride>1 ise atlanan kareler komşudan doldurulur."""
    m = len(frame_yollari)
    jbayrak = np.zeros(m, bool)
    say = np.zeros(m, np.int16)
    idx = list(range(0, m, stride))
    for i in idx:
        a = kutu_analiz(frame_yollari[i])
        jbayrak[i] = a["jenerik_benzeri"]
        say[i] = a["n"]
    if stride > 1:
        for k in range(len(idx) - 1):
            i0, i1 = idx[k], idx[k + 1]
            jbayrak[i0:i1] = jbayrak[i0]
            say[i0:i1] = say[i0]
        jbayrak[idx[-1]:] = jbayrak[idx[-1]]
        say[idx[-1]:] = say[idx[-1]]
    if _cache_acik() and frame_yollari:
        _cache_kaydet(os.path.dirname(frame_yollari[0]))
    return jbayrak, say
