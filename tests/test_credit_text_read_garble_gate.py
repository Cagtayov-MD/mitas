# -*- coding: utf-8 -*-
"""test_credit_text_read_garble_gate.py -- _apply_garble_gate / _garble_reason_kb_gated testleri.

KOK (2026-07-10, spawn_task task_73abb131 -- AŞK EVLİLİĞİ/Mathilde Seigner kanıtı): _looks_garble'in
fuzzy Levenshtein dalı ("garbled rol-etiketi") 6+ harfli bir token'i _GA_ROLE_REF'teki 9 referans
kelimeden (DESIGNER/DIRECTOR/PRODUCER/EDITOR/OPERATOR/CAMERAMAN/SUPERVISOR/ASSISTANT/COMPOSER)
distance<=2 ise "garble" sayıyordu. "SEIGNER" (Mathilde Seigner, gerçek/ünlü Fransız oyuncu) "DESIGNER"e
Levenshtein-mesafe TAM 2 -- OCR'da 2 ayrı karede AYNI/tutarlı okunmuş halde sessizce cast'ten düşüyordu.

ÖLÇÜM (canlı, 2026-07-10): 296-film arşiv taramasında (gerçek LLM-girdi OCR metni) bu fuzzy dal
311 farklı (token, referans, mesafe) örüntüsü buluyor -- 310/311'i gerçek rol-kelimesi yazım-hatası/
çok-dilli varyant (DIRECTEUR/DIRETTORE/PRODUCAO/ASSISTENZ/GIREGTOR/PRODUCIEUR gibi), YALNIZ 1/311
(SEIGNER) gerçek bir kişi adı. KB-çapında (15M satır, 5.5M oyuncu/oyuncu) census: 976 gerçek
oyuncu/oyuncu tam-adı bu 9 referans kelimeyle distance<=2 çakışıyor -- yapısal risk, tek-örnek değil.
Eşik-sıkılaştırma (distance<=1) REDDEDİLDİ: DESIGN~DESIGNER(x80 film)/DIRECTED~DIRECTOR(x74)/
DIRECTION~DIRECTOR(x68)/DIRECTEUR~DIRECTOR(x32) gibi YÜKSEK-hacimli gerçek yakalamalar distance=2'de
oturuyor -- global sıkılaştırma bunların hepsini açardı.

FIX (dar, additive): SADECE fuzzy dal + KB'de TAM AYNI ad gerçek oyuncu/oyuncu profiliyle kayıtlıysa
muaf (_garble_reason_kb_gated). near-dup KB-güvenlik-valfi (satır ~853, önceden var) deseniyle simetrik.
Diğer iki _looks_garble sinyali (tam-token blocklist, TR fiil-eki) KB-muafiyetine TABİ DEĞİL --
çok daha yüksek-isabetli, dokunulmadı (bkz test_exact_blocklist_hit_not_kb_exempted).

Çalıştır:  python -m pytest tests/test_credit_text_read_garble_gate.py -v
       ya:  python tests/test_credit_text_read_garble_gate.py   (kendi koşucusu -- pytest gerekmez)
"""
import os
import sys

# Birim testleri AĞDAN BAĞIMSIZ olmalı.
os.environ.pop("MITAS_TMDB", None)
os.environ.pop("TMDB_API_KEY", None)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import credit_text_read as ctr


class _FakeCon:
    """_kb_has_actor_prof icin minimal .con stub -- gercek duckdb calistirmaz, isim->profession
    sozlugunden UPPER-eslesmeli dogrudan cevap dondurur (kb.con.execute(sql, [name]).fetchall())."""

    def __init__(self, prof_by_name):
        self._prof = {k.upper(): v for k, v in (prof_by_name or {}).items()}
        self._rows = []

    def execute(self, _sql, params):
        prof = self._prof.get(str(params[0]).upper())
        self._rows = [(prof,)] if prof is not None else []
        return self

    def fetchall(self):
        return self._rows


class FakeKB:
    """_kb_has_actor_prof'un beklediği .con arayüzünü taklit eder (KB-onaylı oyuncu/oyuncu seti)."""

    def __init__(self, prof_by_name=None):
        self.con = _FakeCon(prof_by_name or {})


# ─────────────────────────── KB-muafiyeti (asil fix) ───────────────────────────

def test_kb_confirmed_real_actor_survives_fuzzy_gate():
    """Mathilde Seigner deseni: SEIGNER~DESIGNER distance=2 fuzzy-yakalanir ama KB'de TAM AYNI ad
    actress profiliyle kayitli -- gate'i hayatta gecmeli."""
    kb = FakeKB({"Mathilde Seigner": "actress,soundtrack,archive_footage"})
    result = ctr._apply_garble_gate(["Mathilde Seigner", "Jean Pierre"], kb)
    assert "Mathilde Seigner" in result
    assert "Jean Pierre" in result


def test_fuzzy_hit_without_kb_confirmation_still_dropped():
    """Ayni fuzzy-desen ama KB'de KAYIT YOK (0-satir) -- mevcut davranis (dus) korunmali.
    Bu, 296-film arsiv taramasindaki 310/311 gercek-garble orneginin genel temsilcisi."""
    kb = FakeKB({})  # bos KB: hicbir isim onayli degil
    result = ctr._apply_garble_gate(["Georges Directeur", "Paul Designeur"], kb)
    assert result == []


def test_no_kb_object_falls_back_to_pre_fix_behavior():
    """kb=None (KB hic yuklenemediyse) -- guvenli varsayilan: eski davranis (dus), crash yok."""
    result = ctr._apply_garble_gate(["Mathilde Seigner"], None)
    assert result == []


def test_exact_blocklist_hit_not_kb_exempted():
    """KB-muafiyeti SADECE fuzzy dal icin -- tam-token blocklist (_GA_ROLE_INST) cok daha
    yuksek-isabetli oldugundan KB onayli olsa BILE muaf DEGIL (kasitli dar kapsam)."""
    kb = FakeKB({"John Director": "actor"})
    assert ctr._looks_garble("John Director") == "rol/kurum/çöp token (DIRECTOR)"
    result = ctr._apply_garble_gate(["John Director"], kb)
    assert result == []


def test_verb_suffix_hit_not_kb_exempted():
    """TR fiil-eki sinyali de KB-muafiyetine tabi degil (ayni dar-kapsam karari)."""
    kb = FakeKB({"Ahmet Ceviren Yapildigi": "actor"})
    g = ctr._looks_garble("Ahmet Ceviren Yapildigi")
    assert g is not None and g.startswith("cümle/fiil-eki")
    result = ctr._apply_garble_gate(["Ahmet Ceviren Yapildigi"], kb)
    assert result == []


def test_near_dup_kb_exempted_name_survives_tie_break():
    """_garble_reason_kb_gated near-dup asamasinda da kullanilmali: KB-onayli isim + gercek
    OCR-cift-okuma near-dup ikizi ayni gate'ten GECMELI (once tekil tarama, sonra near-dup
    tie-break ham _looks_garble'a bakip geri dusurmemeli)."""
    kb = FakeKB({"Mathilde Seigner": "actress"})
    result = ctr._apply_garble_gate(["Mathilde Seigner", "Mathilde Seignez"], kb)
    assert "Mathilde Seigner" in result


def test_kb_exemption_does_not_add_names_only_prevents_drop():
    """Guvenlik: KB-muafiyeti asla YENI isim EKLEMEZ, sadece zaten LLM/OCR'in cikardigi bir
    ismi yanlislikla silmekten korur (OCR-otorite kanunuyla tutarlilik)."""
    kb = FakeKB({"Mathilde Seigner": "actress", "Someone Else": "actor"})
    result = ctr._apply_garble_gate(["Jean Pierre"], kb)
    assert result == ["Jean Pierre"]
    assert "Mathilde Seigner" not in result  # girdide yoktu, KB'de olsa da eklenmez


# ─────────────────────────── regresyon-kilidi: gercek arsivden true-positive orneklem ───────────────────────────

def test_archive_true_positive_sample_still_dropped():
    """296-film arsiv taramasindan (2026-07-10) secilmis, gercekten karsilasilan role-word
    OCR-garble ornekleri -- KB'de kayitli olmadiklarindan (gercek kisi degiller) fix-sonrasi da
    DUSMELI. Bu liste kucculurse/degisirse regresyonu hemen yakalar."""
    kb = FakeKB({})  # arsivdeki hicbiri KB-onayli gercek oyuncu degil
    true_garbles = [
        "GIREGTOR",       # DIRECTOR, HAROLD VE MAUDE
        "PRODUCIEUR",     # PRODUCER, YARGIÇ VE POLİS
        "DIRECTEUR",      # DIRECTOR, x32 film
        "SUPERVISORE",    # SUPERVISOR, TAŞ DEVRİ SEVİMLİ ANNE
        "ASSISTENZ",      # ASSISTANT, YEDİ CÜCELER 1
        "KAMERAMAN",      # CAMERAMAN (TR yazim), ADI YUNUS
        "OMPOSEO",        # COMPOSER, MUTLU GÜNLER
    ]
    for tok in true_garbles:
        name = f"Test {tok}"
        assert ctr._looks_garble(name) is not None, f"{tok}: fuzzy sinyal beklenirdi"
        result = ctr._apply_garble_gate([name], kb)
        assert result == [], f"{tok}: KB-onaysiz gercek-garble yanlislikla hayatta kaldi"


# ─────────────────────────── AŞK EVLİLİĞİ uctan-uca (gercek KB, opsiyonel) ───────────────────────────

def test_ask_evlilik_real_kb_end_to_end():
    """Gercek KB'ye (mitas.duckdb) karsi uctan-uca: rapor edilen orijinal vaka. DB yoksa/erisilemezse
    atlanir (CI/farkli ortamda kirilgan olmasin)."""
    kb = ctr._get_kb()
    if not getattr(kb, "con", None):
        print("  SKIP  test_ask_evlilik_real_kb_end_to_end (gerçek KB erişilemedi)")
        return
    result = ctr._apply_garble_gate(["Mathilde Seigner", "Antoine Koutsonias"], kb)
    assert "Mathilde Seigner" in result, "AŞK EVLİLİĞİ: Mathilde Seigner fix-sonrası hayatta kalmalı"
    assert "Antoine Koutsonias" in result


# ─────────────────────────── kendi kosucusu (pytest'siz) ───────────────────────────

def _run_all():
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = fail = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            ok += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {fn.__name__}: {e}")
            traceback.print_exc()
            fail += 1
    print(f"\n{ok} gecti, {fail} basarisiz ({len(fns)} test)")
    return fail


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(1 if _run_all() else 0)
