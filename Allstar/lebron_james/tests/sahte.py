"""Test iskeleleri — derleyici ve okuyucu yerine geçen sahteler.

Amaç: akış ve sözleşme testleri PaddleOCR/GPU olmadan koşsun. main.py'de
derleyiciye ve okuyucuya dokunan TEK yer `_derle` / `_oku` olduğu için
sahtelemek tek satırdır — bu ayrım kasıtlıdır.
"""
from types import SimpleNamespace

import yukleyici


class SahteKanvas:
    """cv2 dizisi yerine geçer — main.py kanvasın içine bakmaz, yalnız yazar."""

    def __init__(self, en=1920, boy=8000):
        self.shape = (boy, en, 3)


def sahte_derleyici(yazilan=None, cokmus_mu=False):
    """Gerçek yükleyiciyi kullanan, motoru sahte olan bir derleyici modülü."""
    def _yaz(yol, goruntu):
        # gerçek dosya üret ki main.py stat() alabilsin
        with open(yol, "wb") as h:
            h.write(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
        if yazilan is not None:
            yazilan.append(yol)

    return SimpleNamespace(
        H_MAKS=45000,
        COKME_MIN_KARE=20,
        kareler=yukleyici.kareler,
        kare_oku=lambda p: SahteKanvas(boy=1080),
        kareleri_yukle=lambda d: ([SahteKanvas() for _ in yukleyici.kareler(d)],
                                  len(yukleyici.kareler(d))),
        cokmus=lambda m, k, h: cokmus_mu,
        yaz=_yaz,
    )


def kare_dizini_kur(tmp_path, n=30, ad="c_{:05d}.png"):
    d = tmp_path / "kareler"
    d.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        (d / ad.format(i)).write_bytes(b"\x89PNG\r\n\x1a\n")
    return d


def manifest_ok(kare=30, en=1920, boy=8000, segment=5):
    return {"slug": "T", "durum": "OK", "mode": "lebron_james", "kare": kare,
            "size": [en, boy], "segment": segment, "sinif_sayimi": {"scroll": 10},
            "scroll_dy_medyan": 12.0, "olcum_yolu": "ai_flashlight"}
