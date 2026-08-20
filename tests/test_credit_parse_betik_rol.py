"""OCR-worktree/pdf-mitas/credit_parse.py — betik-farkında rol_tablosu delegasyonu
+ Yönetmen/Kameraman sıra hatası düzeltmesi (adım 5/5, spec §2.4/§4.5/§7.E).

Kök sebep: _ROLE_MATCH listesinde 'Kameraman' girdisi 'Yönetmen'den ÖNCE geliyordu.
role_of() ilk-eşleşen-etiketi döndürdüğü için 'Director-Cameraman' (SENİ SEVİYORUM
FRANK 1988-0480 gerçek OCR satırı) 'Kameraman' sayılıyordu — yanlış, 'Yönetmen'
olmalıydı ('director' kelimesi 'cameraman' kelimesinden ÖNCE bir role işaret eder).

Düzeltilmiş öncelik sırası (spec §4.5):
  Yönetmen Yardımcısı > Görüntü Yönetmeni > Sanat Yönetmeni > Yönetmen >
  Kameraman Yardımcısı > Kameraman

Bu dosya OCR-worktree/pdf-mitas/ ağacında, importlib+path ile yüklenir (mevcut
test_credit_crew_leak_gate.py'deki load_module deseniyle AYNI).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cp = _load_module(
    "credit_parse_betik_test", ROOT / "OCR-worktree" / "pdf-mitas" / "credit_parse.py"
)


# ── §7.E — asıl sıra-hatası düzeltmesi ────────────────────────────────────
def test_director_cameraman_artik_yonetmen():
    assert cp.role_of("Director-Cameraman") == "Yönetmen"


def test_seni_seviyorum_frank_gercek_satir():
    """SENİ SEVİYORUM FRANK 1988-0480 gerçek ocr_ham.txt satırı."""
    assert cp.role_of("Director-Cameraman, Ron Sandilands") == "Yönetmen"


# ── Öncelik sırası korunuyor (nitelikli roller Yönetmen'den ÖNCE hâlâ kazanır) ──
@pytest.mark.parametrize("satir,beklenen", [
    ("Yönetmen Yardımcısı", "Yönetmen Yardımcısı"),
    ("Assistant Director", "Yönetmen Yardımcısı"),
    ("Görüntü Yönetmeni", "Görüntü Yönetmeni"),
    ("Director of Photography", "Görüntü Yönetmeni"),
    ("Sanat Yönetmeni", "Sanat Yönetmeni"),
    ("Art Director", "Sanat Yönetmeni"),
    ("Kameraman Yardımcısı", "Kameraman Yardımcısı"),
    ("Kameraman", "Kameraman"),
    ("Cameraman", "Kameraman"),
])
def test_nitelikli_roller_yonetmene_dusmuyor(satir, beklenen):
    assert cp.role_of(satir) == beklenen, satir


# ── Düz Yönetmen davranışı bozulmadı ──────────────────────────────────────
@pytest.mark.parametrize("satir", [
    "Yönetmen", "Directed by", "Director", "Yoneten", "Regie", "Regia",
])
def test_duz_yonetmen_bozulmadi(satir):
    assert cp.role_of(satir) == "Yönetmen", satir


# ── rol_tablosu'na delegasyon — kapsam genişlemesi ────────────────────────
def test_diretto_da_artik_taniniyor():
    """'diretto da' eski hardcoded listede YOKTU (yalnız 'regia' vardı) —
    LATIN.YONETMEN'de VAR, delegasyon sonrası tanınmalı."""
    assert cp.role_of("Diretto da") == "Yönetmen"


def test_role_match_yonetmen_tablodan_geliyor():
    sys.path.insert(0, str(ROOT))
    from core.lexicon.rol_tablosu import TABLO
    yonetmen_entry = next(label_kws for label_kws in cp._ROLE_MATCH if label_kws[0] == "Yönetmen")
    beklenen = tuple(k.lower() for k in TABLO["LATIN"]["YONETMEN"])
    assert yonetmen_entry[1] == beklenen


# ── Diğer roller (Yapımcı, Kurgu, vb.) bozulmadı ──────────────────────────
@pytest.mark.parametrize("satir,beklenen", [
    ("Yapımcı", "Yapımcı"),
    ("Produced by", "Yapımcı"),
    ("Senaryo", "Senaryo"),
    ("Kurgu", "Kurgu"),
    ("Müzik", "Müzik"),
    ("CAST", "CAST"),
])
def test_diger_roller_bozulmadi(satir, beklenen):
    assert cp.role_of(satir) == beklenen, satir


# ── HARIC koruması (haric_uygula=True) — §6.1 taban karşılaştırmasında
# BULUNAN gerçek düzeltmeler (öncesi: eski kelime-sınırsız/HARIC'siz kod bu
# satırları YANLIŞLIKLA 'Yönetmen' sayıyordu — gerçek OCR verisiyle ölçüldü,
# scripts/anlik_latin_taban.py 50.000 satırlık Latin taban karşılaştırması).
# Bunlar §6.1'in "sıfır regresyon" ölçütüyle GÖRÜNÜŞTE çelişir (role_of çıktısı
# değişti) ama spec §4.5'in "kayıp olmadığı test edilir" ölçütüne UYAR — kayıp
# yok, KAZANIM var: eski davranış zaten YANLIŞTI (dublaj/asistan/finans rolünü
# film-yönetmeni sayıyordu). Bu testler o düzeltmeyi kilitler.
@pytest.mark.parametrize("satir", [
    "dublaj yönetmeni",           # TR dublaj yönetmeni ≠ film yönetmeni
    "YARDIMCI YÖNETMEN",          # TR yardımcı yönetmen ≠ film yönetmeni
    "Animation Directors",        # çoğul — credit_role_lexicon ile TUTARLI (o da eşlemez)
    "Art-Director",               # LATIN.HARIC "ART DIRECTOR"
    "Director's Assistant",       # LATIN.HARIC bare "ASSISTANT"
    "2nd Assistants Director",    # LATIN.HARIC bare "ASSISTANT"
    "Auxiliaire de réalisation",  # FR yardımcı — credit_parse.py'ye özel _ROLE_DISQUALIFY
    "Exposure Sheet Direction & Storyboard Slugging",  # animasyon departman terimi, yönetmen değil
])
def test_haric_korumasi_gercek_olcum_kanitiyla(satir):
    assert cp.role_of(satir) != "Yönetmen", satir


@pytest.mark.parametrize("satir,beklenen", [
    ("Finance Director    REMI GEORGE", None),        # isim satırın SONUNDA — kelime-sınırı korur
    ("aiuto assistente alla regia  CAROLINA PAVONE", None),   # İtalyanca "yönetmen asistanının asistanı"
    ("stagiaire mise en scène Matilde BARBAGALLO", None),     # FR "yönetmenlik stajyeri"
    ("assistenti alla regia  NATALIA FAGO", None),            # İtalyanca "yönetmen asistanları"
])
def test_isimli_satirlarda_da_haric_korumasi(satir, beklenen):
    assert cp.role_of(satir) == beklenen, satir


# ── Meşru yeni kapsam (§6.1 taban karşılaştırmasında bulunan GERÇEK kazanımlar) ──
@pytest.mark.parametrize("satir", [
    "Rendező: ENYEDI ILDIKÓ",     # Macarca bare label + isim
    "Rejisser    JANNAT ALSHANOVA",  # RU/UA/BG translit + isim
    "Rendezte:",                  # Macarca bare label
    "FILM DIRECTION",             # bare label
])
def test_yeni_kapsam_gercek_kazanim(satir):
    assert cp.role_of(satir) == "Yönetmen", satir


# ── §5.4 kanonik sıra hâlâ değişmedi (bu adımın konusu DEĞİL) ────────────
def test_canon_out_degismedi():
    assert cp.CANON_OUT[:2] == ["Yapımcı", "Yönetmen"]
