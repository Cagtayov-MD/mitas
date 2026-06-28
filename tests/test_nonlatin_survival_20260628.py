# -*- coding: utf-8 -*-
"""test_nonlatin_survival_20260628.py — Latin-dışı alfabe SESSİZ-SİLME karşıtı koruma.

Denetim bulgusu (2026-06-28): sistemde birkaç yer Arap/Kiril/Yunan/CJK harfini sessizce
SİLİYORDU (otomatik rede düşürme) — özellikle:
  [A] OCR künye: baskın-script mantığı Latin-baskın satırdaki AZINLIK non-Latin ismi ham bırakıp
      _fold (re.sub r"[^a-z0-9 ]") ile siliyordu → 'DIRECTOR Иван' → 'DIRECTOR ' (Иван kayıp).
  [B] ASR özet _latin_only: Kiril/Arap harfini transliterE etmeden DÜŞÜRÜYORDU → 'Иван' → ''.

ÇÖZÜM: translit_util.transliterate_mixed() TOKEN-bazlı çevirir (azınlık non-Latin token de iner),
çevrilemezse HAM korur (sessiz silme YOK). _latin_only artık silmeden ÖNCE bunu çağırır → çıktı
yine Latin/ASCII (KANUN B3) ama isim KAYBOLMAZ.

İNVARYANT: saf-Latin/saf-Türkçe metin DEĞİŞMEZ (0 regresyon) — translit hiç tetiklenmez.

Çalıştır:  python -m pytest tests/test_nonlatin_survival_20260628.py -v
"""
import os
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from translit_util import transliterate_mixed  # noqa: E402


# ─────────────────────── transliterate_mixed: ÇEKİRDEK ───────────────────────
def test_saf_latin_degismez_0_regresyon():
    for s in ["JOHN DOE", "John Q. Public", "STANLEY KUBRICK"]:
        out, methods = transliterate_mixed(s)
        assert out == s, f"{s!r} → {out!r} (saf-Latin değişmemeli)"
        assert methods == set(), f"{s!r} translit tetiklememeli (methods={methods})"


def test_saf_turkce_korunur_0_regresyon():
    # Türkçe harfler (ç ğ ı İ ö ş ü) Latin'dir → asciify KORUR, translit tetiklenmez.
    for s in ["ŞERİF ŞAHİN", "ÇAĞATAY ÖZTÜRK", "ZEKİ MÜREN", "İBRAHİM TATLISES"]:
        out, methods = transliterate_mixed(s)
        assert out == s, f"{s!r} → {out!r} (Türkçe korunmalı)"
        assert methods == set()


def test_yabanci_aksan_asciiye_iner():
    # Latin-yabancı aksan ASCII'ye (José→Jose) — ama bu translit DEĞİL (methods boş kalır).
    out, methods = transliterate_mixed("José Peña")
    assert out == "Jose Pena"
    assert methods == set()


def test_saf_kiril_transliterE():
    out, methods = transliterate_mixed("Иван Петров")
    assert out == "Ivan Petrov"
    assert "tablo" in methods


def test_AZINLIK_kiril_token_hayatta_kalir():
    # [A] çekirdek bug: Latin-baskın satırdaki tek Kiril isim ESKİDEN ham kalıp _fold'da ölürdü.
    out, methods = transliterate_mixed("DIRECTOR Иван")
    assert out == "DIRECTOR Ivan", f"azınlık Kiril token inmedi: {out!r}"
    assert "tablo" in methods
    # Türkçe-baskın + Arap azınlık: Türkçe korunur, Arap romanize olur (boş kalmaz).
    out2, _ = transliterate_mixed("Yönetmen محمد")
    assert out2.startswith("Yönetmen ")
    assert out2 != "Yönetmen "  # Arap kısım SİLİNMEDİ (romanize edildi)


def test_yunan_ve_karma_script():
    out, _ = transliterate_mixed("Λάμπρος")
    assert out == "Lampros"
    # Tek string'de Kiril + Yunan bir arada
    out2, _ = transliterate_mixed("РЕЖИССЕР Λάμπρος")
    assert out2 == "Rezhisser Lampros"


def test_sessiz_silme_YOK_invaryant():
    # Non-boş, harf-içeren her girdi için çıktı ASLA boş olmamalı (sessiz silme yasak).
    for s in ["Иван", "محمد علي", "नमस्ते", "田中", "Зеки Алясья"]:
        out, _ = transliterate_mixed(s)
        assert out.strip(), f"{s!r} → {out!r} BOŞ (sessiz silme!)"


def test_bos_ve_noktalama():
    assert transliterate_mixed("") == ("", set())
    out, methods = transliterate_mixed("123 - / .")
    assert out == "123 - / ."
    assert methods == set()


# ─────────────────────── _latin_only (ASR özet kemeri) GERÇEK FONKSİYON ───────────────────────
def _is_latin_ascii_safe(s: str) -> bool:
    """KANUN B3: çıktıda Latin-DIŞI harf olmamalı (ASCII veya Latin-blok harf serbest)."""
    for ch in s:
        if ch.isascii():
            continue
        if unicodedata.category(ch)[0] != "L":
            continue
        if "LATIN" in unicodedata.name(ch, ""):
            continue
        return False
    return True


def test_latin_only_kiril_hayatta_kalir_ve_b3_korunur():
    import mitas_pipeline as mp
    # Kiril isim ESKİDEN silinirdi ('Иван'→''); ARTIK 'Ivan' (kaybolmaz).
    out = mp._latin_only("Иван ve José filmi")
    assert "Ivan" in out, f"Kiril isim kayboldu: {out!r}"
    assert "Jose" in out
    assert _is_latin_ascii_safe(out), f"B3 ihlali (Latin-dışı sızdı): {out!r}"


def test_latin_only_turkce_bozulmaz():
    import mitas_pipeline as mp
    out = mp._latin_only("Şükrü'nün öyküsü çok güzel")
    # Türkçe harfler korunur (B3 Türkçe'yi Latin sayar)
    assert "Şükrü" in out and "öyküsü" in out and "güzel" in out


def test_latin_only_arap_romanize_silinmez():
    import mitas_pipeline as mp
    out = mp._latin_only("محمد bir film yönetti")
    assert "bir film" in out
    assert _is_latin_ascii_safe(out)
    # Arap kısım romanize edildi (boş değil) — 'bir film' öncesi metin var
    assert out.strip() != "bir film yönetti" or "Mhmd" in out or out.strip().startswith("M")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
