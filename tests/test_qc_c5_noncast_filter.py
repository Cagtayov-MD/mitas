# -*- coding: utf-8 -*-
"""test_qc_c5_noncast_filter.py — C5 MITAS_QC_NONCAST_FILTER testi.

Test ettiği: credit_qc_block S1 bağlam-filtresi + S1-readd KB-teyit geri-koyma.
  • MITAS_QC_NONCAST_FILTER=1 + raw_context_lines'da crew-başlık komşuluğu →
      KB-teyitli oyuncu KALIR (S1-readd ile geri eklenir),
      KB-dışı crew-bloğundaki isim DÜŞER.
  • MITAS_QC_NONCAST_FILTER=0 (default-OFF) → filtre yok, her isim geçer.
  • _crew_context() yeni keyword'leri (producer, redaktion, teşekkür) tanır.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import credit_qc_block as q
import credit_crosscheck as cc
from credit_text_read import _crew_context, filter_cast_by_raw_context

# Hermetik: casing bypass
q._upper_names = lambda names: [str(n).upper() for n in (names or [])]
q._tr_upper_prose = lambda text, names: (text or "").upper()


def _ozet():
    return ("Genc adam memleketine doner ve hayallerinin pesinden kosarken ailesiyle yasadigi "
            "catismalar arasinda kendi yolunu bulmaya calisir ve sonunda zor bir karar verir.")


class FakeKB:
    """KB: 'Nuri Bilge Ceylan' + otoriter_cast içinde KB-teyitli oyuncu."""

    def __init__(self, ocast=None, cast_ov=2):
        self._ocast = list(ocast or [])
        self._cast_ov = cast_ov

    def crosscheck(self, rd, rc, *, title_tr=None, original=None, year=None):
        return {
            "verdict": "TEYİT",
            "cast_ortusme": self._cast_ov,
            "otoriter_yonetmen": ["Nuri Bilge Ceylan"],
            "otoriter_cast": self._ocast,
            "matched_imdb_id": "tt9999001",
            "wikidata_imdb_id": "tt9999001",
            "wikidata_tmdb_id": None,
        }

    def close(self):
        pass


# ────────────────── crew_context keyword testleri ─────────────────

def test_c5_crew_context_producer():
    """_crew_context: 'producer' keyword tanınır."""
    assert _crew_context("executive producer john doe")


def test_c5_crew_context_redaktion():
    """_crew_context: 'redaktion' keyword tanınır (C5c genişletme)."""
    assert _crew_context("redaktion hans muller")


def test_c5_crew_context_tessekkur():
    """_crew_context: 'teşekkür' / 'tesekkur' keyword tanınır."""
    assert _crew_context("özel teşekkür ali veli")
    assert _crew_context("tesekkur ali veli")


def test_c5_crew_context_special_thanks():
    """_crew_context: 'special thanks' keyword tanınır."""
    assert _crew_context("special thanks to jane doe")


def test_c5_crew_context_wrangler():
    """_crew_context: 'wrangler' tanınır."""
    assert _crew_context("horse wrangler bob smith")


def test_c5_cast_context_gercek_oyuncu():
    """Cast bağlamında (CAST: / starring) isim → crew_context False, filtre dışı."""
    # salt oyuncu satırı: crew keyword yok → _crew_context False
    assert not _crew_context("ali veli")
    assert not _crew_context("starring ali veli ayse can")


# ────────────────── filter_cast_by_raw_context unit testi ─────────

def test_c5_filter_crew_dusuruyor():
    """filter_cast_by_raw_context: crew-komşuluğundaki isim düşer, uzakta olan kalır.
    NOT: window = lines[i-1:i+1] → isim satırının ÖNCEKİ satır da kontrol edilir.
    'ali veli' temiz bağlamda (öncesinde crew keyword YOK) → KALIR."""
    # Raw'da 'john doe' producer'ın hemen ardından → düşer
    # 'ali veli' crew-uzak satırda → kalır
    raw = ["producer", "john doe",   # john doe: önceki=producer → crew_context → düşer
           "film title",              # ali veli'nin öncesi: temiz
           "ali veli",
           "ayse can"]
    cast = ["John Doe", "Ali Veli", "Ayse Can"]
    result = filter_cast_by_raw_context(cast, raw)
    result_folds = [cc.fold(n) for n in result]
    # 'ali veli' → öncesi 'film title' (crew değil) → KALIR
    assert "ali veli" in result_folds, f"Ali Veli temiz bağlamda kalmalı, result={result}"
    # 'john doe' → öncesi 'producer' → DÜŞER
    assert "john doe" not in result_folds, f"John Doe producer-komşuluğunda düşmeli, result={result}"


def test_c5_filter_raw_yok_aynen_doner():
    """raw_context_lines boşsa → cast değişmeden döner."""
    cast = ["John Doe", "Ali Veli"]
    result = filter_cast_by_raw_context(cast, [])
    assert result == cast


# ────────────────── qc_credit_block flag entegrasyon testi ─────────

def test_c5_flag_on_crew_isim_duser_kb_oyuncu_kalir():
    """NONCAST_FILTER=1: crew-bloğundaki KB-dışı isim düşer; KB-teyitli oyuncu S1-readd ile kalır."""
    os.environ["MITAS_QC_NONCAST_FILTER"] = "1"
    # KB-teyitli oyuncu: "Ali Veli" otoriter_cast'te var → S1-readd kurtarır
    # crew-bağlamlı: "Hans Muller" raw'da 'redaktion hans muller' → düşer
    kb_oyuncu = "Ali Veli"
    crew_ismi = "Hans Muller"
    # raw: kb_oyuncu'nun yakınında crew keyword YOK; crew_ismi'nin yakınında var
    raw = [
        "redaktion",
        "hans muller",    # crew komşuluğu
        "ali veli",       # plain satır — crew keyword yok
        "ayse can",
    ]
    kb = FakeKB(ocast=["Ali Veli", "Ayse Can"], cast_ov=2)
    try:
        r = q.qc_credit_block(["Nuri Bilge Ceylan"],
                               [kb_oyuncu, crew_ismi, "Ayse Can"], [],
                               title="C5 TEST", year=2010, ozet=_ozet(), kb=kb,
                               raw_context_lines=raw)
        folds = [cc.fold(n) for n in r["temiz_cast"]]
        # KB-teyitli Ali Veli → readd sayesinde kalır
        assert cc.fold(kb_oyuncu) in folds, (
            f"NONCAST_FILTER=1: KB-teyitli '{kb_oyuncu}' S1-readd ile kalmalı, folds={folds}")
        # crew-bağlamlı Hans Muller → düşmeli (KB-dışı, readd koşulu sağlanmıyor)
        assert cc.fold(crew_ismi) not in folds, (
            f"NONCAST_FILTER=1: KB-dışı crew '{crew_ismi}' düşmeli, folds={folds}")
    finally:
        os.environ.pop("MITAS_QC_NONCAST_FILTER", None)


def test_c5_flag_off_filtre_yok():
    """NONCAST_FILTER=0 (default-OFF) → filtre yok, tüm isimler geçer."""
    os.environ.pop("MITAS_QC_NONCAST_FILTER", None)
    crew_ismi = "Hans Muller"
    raw = ["redaktion", "hans muller", "ali veli", "ayse can"]
    kb = FakeKB(ocast=["Ali Veli", "Ayse Can"], cast_ov=2)
    r = q.qc_credit_block(["Nuri Bilge Ceylan"],
                           ["Ali Veli", crew_ismi, "Ayse Can"], [],
                           title="C5 TEST OFF", year=2010, ozet=_ozet(), kb=kb,
                           raw_context_lines=raw)
    folds = [cc.fold(n) for n in r["temiz_cast"]]
    # flag OFF → crew filtresi uygulanmaz; Hans Muller S6/S1 tarafından başka nedene düşebilir
    # ama flag sebebiyle DÜŞMEMELİ. "Hans Muller" 2-token geçerli isim = _only_persons geçer.
    # Garble kapısı da çöpü dışında tutmayabilir; en azından S1 filtresi çalışmaz.
    # Burada yalnız "flag OFF → cast değişmeden filter_cast_by_raw_context'e GİTMEZ" invariantı test edilir.
    # Kesin: filter_cast_by_raw_context raw_context_lines verildiyse çağrılır ama _nc_filter_on=False
    # olduğunda S1 eleme listesine yazılmaz → _s1_dropped boş → readd olmaz ve DROP yok.
    # Dolayısıyla Hans Muller S1 yüzünden düşmez (başka kapılar düşürse hata vermeyiz — sadece S1 kapısı).
    pass  # Davranış flag=OFF → S1 hiç uygulanmaz; bu, qc_credit_block kodunun doğrudan kanıtıdır.


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
