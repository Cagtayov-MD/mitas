"""MAGIC token-kimlik + uçtan-uca sentetik film (GPU'suz).

Kimlik hükmü: iki kare de yeterli token veriyorsa kapsama-oranı karar verir
(jetgiller/totoro sınıfı: NCC/IoU statik zemine domine oluyordu); token
kanıtı yetersizse geometrik fark (lebron'un yolu) devreye girer.

Sentetik film üç sahnelidir: kart A (duraksama) → kart B (AYNI konum/parlaklık,
FARKLI metin — yalnız token ayırt eder) → yukarı kayan bant (scroll).
Sahte el-feneri ve token sağlayıcı enjekte edilir; Paddle'a hiç dokunulmaz.
"""
import sys
from pathlib import Path

import numpy as np

KULE = Path(__file__).resolve().parents[1]
for p in (KULE / "aday", KULE / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from magic import derle, token_ayni, fark_tabani, TOKEN_KAPSAMA

H, W = 480, 640


# --------------------------------------------------------------------------- #
# token_ayni — saf hüküm
# --------------------------------------------------------------------------- #
def test_token_ayni_ayni_kart():
    a = {"DIRECTOR", "PRODUCER", "CAST", "MUSIC"}
    assert token_ayni(a, set(a)) is True


def test_token_ayni_farkli_kart():
    a = {"DIRECTOR", "PRODUCER", "CAST"}
    b = {"MUSIC", "EDITOR", "SOUND"}
    assert token_ayni(a, b) is False


def test_token_ayni_kapsama_oranı_dayanıklı():
    """Fade'de OCR bazı tokenları düşürse de ORAN dayanıklı (4 ortak / 4+5)."""
    a = {"AAA", "BBB", "CCC", "DDD"}
    b = {"AAA", "BBB", "CCC", "DDD", "EEE"}
    assert token_ayni(a, b) is True


def test_token_ayni_yetersiz_kanit_none():
    """<TOKEN_MIN_GUVEN token → hüküm YOK; çağıran geometrik fallback'e düşer.
    'Yazı yok' ile 'okuyamadık' karışmasın."""
    assert token_ayni({"AAA", "BBB"}, {"AAA", "BBB", "CCC"}) is None
    assert token_ayni(set(), set()) is None


# --------------------------------------------------------------------------- #
# sentetik film + sahte sağlayıcılar
# --------------------------------------------------------------------------- #
def _film():
    """14 kare: [0..3] kart A · [4..7] kart B (AYNI yerleşim, FARKLI içerik —
    kucuk-dev sınıfı: eşik düzeni aynı, yazı başka; piksel-farkı VE token
    birlikte 'farklı' der) · [8..9] boş geçiş · [10..13] yukarı kayan bant.
    Gren TÜM karelerde ortak (statik kartlar piksel-birebir eş olur; son çift
    lebron'un bitis=len-1 varsayımıyla her zaman düşer)."""
    rng = np.random.default_rng(42)
    gren = 20 + rng.integers(-4, 5, (H, W)).astype(np.uint8)
    ims = []
    for i in range(14):
        gri = gren.copy()
        if i <= 7:
            gri[100:107, 60:580] = 230
            if i >= 4:  # kart B: aynı bant yerleşimi, farklı 'yazı' dokusu
                gri[100:107, 60:300] = 170
        elif i >= 10:
            y0 = 300 - 20 * (i - 10)
            gri[y0:y0 + 7, 60:580] = 230
        ims.append(cv2_bgr(gri))
    return ims


def cv2_bgr(gri):
    import cv2
    return cv2.cvtColor(gri, cv2.COLOR_GRAY2BGR)


TOKEN_A = {"DIRECTOR", "PRODUCER", "CASTING"}
TOKEN_B = {"MUSIC", "EDITOR", "SOUND"}


def _sahte_el_fenerisi(img, _idx):
    import cv2
    gri = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return np.where(gri > 110, gri, 0).astype(np.uint8)


def _sahte_tokenler(img, idx):
    """Kare indeksine göre kart tokenı; scroll kareleri tokensız (gerçekte
    hareketli bant det+rec'te çözülür — kimlik fallback'i sınavdan geçer)."""
    if idx <= 3:
        return set(TOKEN_A)
    if idx <= 7:
        return set(TOKEN_B)
    return set()


def test_sentetik_film_uçtan_uca():
    ims = _film()
    master, man = derle("sentetik", ims=ims, flashlight=_sahte_el_fenerisi,
                        token_saglayici=_sahte_tokenler)
    assert master is not None, man
    # üç sayfa: kart A · kart B (yerleşim aynı, içerik farklı — fark+token
    # birlikte açar) · scroll bandı
    assert man["segment"] == 3, man["segment_kareler"]
    assert man["durum"] == "OK"
    assert man["mode"] == "magic"
    assert man["olcum_yolu"] == "ai_flashlight"
    assert man["dissolve_kesme"] == 2
    assert man["scroll_dy_medyan"] == 20.0
    # boy: kartA(480) + kartB(480) + scroll(480 + 2×20 — son çift düşer)
    assert master.shape[0] == 480 + 480 + 520, master.shape


def test_fade_kartini_token_dedup_etmez():
    """JETGİLLER dersi (ölçüldü: recall 0.52→0.82): aynı kartın piksel-farkına
    'farklı' düşen bir hali (bant başka konumda/çevrimde — fark 7280 px)
    token kapalıyken İKİ kez sayfalanır; token açıkken 'aynı' hükmü sayfayı
    engeller. Gren ortak: film-tabanı sıfır, fark kararı saf içerikten gelir
    (ızgara adayı 4. kareyi garantiler)."""
    rng = np.random.default_rng(3)
    gren = 20 + rng.integers(-4, 5, (H, W)).astype(np.uint8)
    ims = []
    for i in range(8):
        gri = gren.copy()
        if i < 4:
            gri[100:107, 60:580] = 230          # dolu bant
        else:
            gri[100:107, 60:580] = 20           # kesikli bant: konum aynı,
            gri[100:107, 60:580:2] = 230        # doku farklı → dy≈0, fark büyük
        ims.append(cv2_bgr(gri))
    tok = {"AAA", "BBB", "CCC"}
    _, man_acik = derle("fade", ims=ims, flashlight=_sahte_el_fenerisi,
                        token_saglayici=lambda img, idx: set(tok))
    _, man_kapali = derle("fade", ims=ims, flashlight=_sahte_el_fenerisi,
                          token_saglayici=lambda img, idx: set(tok),
                          ozellikler={"token_kimlik": False})
    assert man_kapali["segment"] > man_acik["segment"], (
        man_kapali["segment_kareler"], man_acik["segment_kareler"])
    assert man_acik["segment"] == 1, man_acik["segment_kareler"]


def test_halusinasyon_token_sayfa_acmaz():
    """HAYAT-AGACI dersi (2026-08-17, dup 0.81): okunmaz karelerde OCR her
    karede BAŞKA halüsinasyon token'ı üretir. Token 'farklı' hükmü tek
    başına sayfa açamaz — piksel-farkı da 'farklı' demeli. Pikseller özdeş
    olduğundan hiç yeni sayfa açılmaz (veto semantiği)."""
    ims = _film()[:4]  # 4 özdeş kart A karesi
    HALUSINASYON = [{"X1", "X2", "X3"}, {"Y1", "Y2", "Y3"},
                    {"Z1", "Z2", "Z3"}, {"W1", "W2", "W3"}]
    _, man = derle("halusinasyon", ims=ims, flashlight=_sahte_el_fenerisi,
                   token_saglayici=lambda img, idx: set(HALUSINASYON[idx]))
    assert man["segment"] == 1, man["segment_kareler"]


def test_fark_tabani_duraksama_yoksa_kesmeden_alinir():
    """HAYAT-AGACI dersi: hiç duraksama çifti yokken taban 500'e düşerse
    kar/gren filminde her kesme 'farklı' sanılır → sayfa fırtınası.
    Taban kesme çiftlerinden gelir; duraksama varsa yalnız oradan."""
    rng = np.random.default_rng(5)
    griler = [rng.integers(0, 255, (60, 80)).astype(np.uint8) for _ in range(6)]
    hep_kesme = [{"sinif": "kesme"} for _ in range(5)]
    t = fark_tabani(hep_kesme, griler)
    assert t > 1000, t  # gren-farklarından beslendi, 500 varsayılanı değil
    karisik = [{"sinif": "kesme"}, {"sinif": "duraksama"}, {"sinif": "scroll"},
               {"sinif": "duraksama"}]
    t2 = fark_tabani(karisik, griler)
    assert t2 > 0  # duraksama çiftleri varken onlardan (kesme hariç)


def test_kisaltma_yalniz_son_cifti_dusurur():
    """Lebron'un bitis=len-1 varsayımı: durma koşusu bulunamayan kısa filmde
    yalnız son çift kesilir — 13 çiftten 12'si kalır, 13 kare işlenir."""
    ims = _film()
    _, man = derle("sentetik", ims=ims, flashlight=_sahte_el_fenerisi,
                   token_saglayici=_sahte_tokenler)
    assert len(man["ciftler"]) == 12
    assert man["kare"] == 13
