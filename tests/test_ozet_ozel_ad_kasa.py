"""Özet prose'unda isim kasası — yabancı ad ASCII, Türkçe ad Türkçe kalır.

ÇAĞATAY KURALI (2026-08-01, sözlü talimat):
    "Hiçbir aksan geçmeyecek, hangi dil olduğu önemli değil.
     Türkçede Ü Ğ İ Ş Ç Ö büyüyebilir; Latin'de ne aksan var ne Ü Ğ İ Ş Ç Ö."

GERÇEK VAKA (ŞANSLI FİRAR 2001-9376 PDF'i, Çağatay bildirdi):
    "...banka soyan JİMMY HENS..."  →  JIMMY olmalı.

KÖK SEBEP: özeti üreten API kuralı ZATEN biliyor ve uyuyor
(core/api/prompts/ozet_film.txt:19-20 "Yabancı adda Türkçe karakter YOK") —
"Jimmy" diye normal kasada gönderiyor. Bozan PDF katmanı: tr_upper prose'u
Türkçe kurallarla büyütürken i→İ yapıyor. Eski onarım (_repair_foreign_prose_i)
yalnız BELİRTEÇ arıyordu (W/Q/X harfi, -IE/-IO/-IA sonu, sabit liste) ve
belirteçsizleri kaçırıyordu: EMİLY, DİANA, NİRO, HOPKİNS, JİMMY.

ÇÖZÜM: büyütme küçük/büyük bilgisini yok etmeden ÖNCE ham metne bak —
cümle ORTASINDA büyük harfle başlayan saf-ASCII sözcük = özel ad → ASCII büyüt.
Künye listesi/DB "bu isim Türkçe" derse sezgi İPTAL edilir (öncelik künyede).
"""
from __future__ import annotations

import importlib.util
import os

import pytest

_NN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "OCR-worktree", "pdf-mitas", "name_normalize.py")

if not os.path.isfile(_NN):
    pytest.skip("name_normalize.py yok (pdf-mitas eksik)", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("nn_test", _NN)
nn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nn)


# ───────── yabancı ad: ASCII olmalı (Türkçe harf YASAK) ─────────

def test_sansli_firar_gercek_vakasi():
    """Çağatay'ın PDF'te gördüğü satır. JİMMY → JIMMY."""
    c = "Çocukluk arkadaşı Rudy ile banka soyan Jimmy Hens yakalanır ve 12 yıl yatar."
    out = nn.tr_upper_prose(c, names=[])
    assert "JIMMY" in out
    assert "JİMMY" not in out


@pytest.mark.parametrize("ham,olmali,olmamali", [
    ("Filmde Emily Watson oynuyor.", "EMILY", "EMİLY"),
    ("Başrolde Diana Ross var.", "DIANA", "DİANA"),
    ("Oyuncu Anthony Hopkins sahnede.", "HOPKINS", "HOPKİNS"),
    ("Yönetmen Robert De Niro geldi.", "NIRO", "NİRO"),
    ("Karakter Massimo Rossi kaçar.", "MASSIMO", "MASSİMO"),
])
def test_belirtecsiz_yabanci_adlar(ham, olmali, olmamali):
    """Eski onarımın BELİRTEÇ bulamadığı için kaçırdığı sınıf."""
    out = nn.tr_upper_prose(ham, names=[])
    assert olmali in out
    assert olmamali not in out


# ───────── Türkçe: bozulmamalı ─────────

def test_turkce_prose_sozcukleri_korunur():
    """Küçük harfli Türkçe sözcükler özel ad değildir; İ'lerini korur."""
    out = nn.tr_upper_prose("Bu film ile ilgili bir iş için geçiyor.", names=[])
    for kelime in ("FİLM", "İLE", "İLGİLİ", "BİR", "İŞ", "İÇİN", "GEÇİYOR"):
        assert kelime in out, f"Türkçe sözcük bozuldu: {kelime} eksik → {out}"


def test_turkce_ozel_ad_turkce_harfliyse_korunur():
    out = nn.tr_upper_prose("Olay İstanbul da Şener Şen ile geçer.", names=[])
    assert "İSTANBUL" in out and "ŞENER" in out
    assert "ISTANBUL" not in out


def test_kunye_turkce_derse_sezgi_iptal():
    """ÖNCELİK: künye/DB bilgisi ham-metin sezgisini EZER.

    'Ali Kaya' saf-ASCII ve cümle ortasında büyük harfli → sezgi 'yabancı' der.
    Künye onu Türk olarak biliyorsa ALİ kalmalı, ALI olmamalı.
    (DB erişilemezse bu vaka atlanır — sezgi zaten muhafazakâr tarafta kalır.)
    """
    if not (nn._TR_GIVEN or nn._TR_SUR):
        pytest.skip("Türkçe isim DB'si bu ortamda yüklü değil")
    out = nn.tr_upper_prose("Bu filmde Ali Kaya bir iş kurar.", names=["Ali Kaya"])
    assert "ALİ KAYA" in out


# ───────── kill-switch ─────────

def test_kapatilabilir():
    """MITAS_PROSE_OZEL_AD=0 → eski davranış birebir (geri dönüş yolu)."""
    eski = os.environ.get("MITAS_PROSE_OZEL_AD")
    os.environ["MITAS_PROSE_OZEL_AD"] = "0"
    try:
        assert nn._ozel_ad_repl("Filmde Emily Watson oynuyor.") == {}
    finally:
        if eski is None:
            os.environ.pop("MITAS_PROSE_OZEL_AD", None)
        else:
            os.environ["MITAS_PROSE_OZEL_AD"] = eski


def test_cumle_basi_ozel_ad_kaniti_degil():
    """Cümle başındaki büyük harf özel ad kanıtı DEĞİL — 'Film' → FİLM kalmalı."""
    assert "FILM" not in nn._ozel_ad_repl("Film burada biter.")
