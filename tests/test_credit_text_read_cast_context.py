# -*- coding: utf-8 -*-
"""test_credit_text_read_cast_context.py -- filter_cast_by_raw_context (crew/cast ham-baglam suzgeci) testleri.

KOK (2026-07-10, SANTRAL/"The Operator" kaniti, task_ebc9425c): jenerik tek-kelime crew-anahtari
("operator") bir karakterin EKRAN-ADIYLA cakisinca VE/VEYA yogun "in order of appearance"
listelerinde komsu satirlar farkli cast-adaylarina ait olunca, gercek oyuncu yanlislikla crew
sayilip dusuyordu. Canli SANTRAL verisiyle IKI AYRI sizinti mekanizmasi bulundu:
  (A) KENDI-SATIR CAKISMASI: adayin KENDI ham-satiri jenerik crew-kelimesini iceriyor ("Operator
      JACQUELINE KIM" -- karakter adi = "Operator").
  (B) KOMSU-KIRLENMESI: adayin satiri crew-kelimesi ICERMIYOR ama hemen-onceki satir BASKA BIR
      cast-adayinin KENDI satiri olup crew-kelimesi iceriyor ("...Operator JACQUELINE KIM" satiri,
      hemen ardindan gelen BRION JAMES adayinin geriye-bakan penceresine sizip onu da crew sayiyor).

SADECE (B) FIXLENDI (komsu-disla: pencere, cast listesindeki HERHANGI bir adayin kendi satirini
"rol-etiketi" saymaz). 268-film canli-taramasinda SIFIR regresyon, 2 dogru-kurtarma (BRION JAMES,
MAZHAR ALANSON).

(A) BILINCLI KAPSAM-DISI birakildi: icerik-bazli dedup (ayni fiziksel kartin tekrarlanan
okumalarini TEK oya indirmek) SANTRAL'i duzeltiyordu AMA ayni 268-film taramasinda GERCEK
oyunculari (BILL MURRAY, MARTIN SHORT, ...) yanlis-crew sayip dusurdu -- bu kisilerin filmde
AYRICA bagimsiz/mesru crew-gorunumlu ek-satirlari da var (bkz test_dedup_would_regress_real_actor_
bill_murray, yasayan/donmus kanit -- dedup YENIDEN denenirse bu test kirilip fark ettirir).

Calistir:  python -m pytest tests/test_credit_text_read_cast_context.py -v
       ya:  python tests/test_credit_text_read_cast_context.py   (kendi kosucusu -- pytest gerekmez)
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import credit_text_read as ctr

SANTRAL_DIR = r"E:\MITAS\Database\SANTRAL 2000-0395-1-0000-00-1"
BIR_KONUSABILSE_DIR = r"E:\MITAS\Database\BİR KONUŞABİLSE 2003-9192-1-0000-00-1"


def _ocr_kunye(film_dir):
    hits = glob.glob(os.path.join(film_dir, "ocr", "ocr-*", "kunye.txt"))
    return hits[0] if hits else None


# ─────────────────────────── (B) KOMSU-KIRLENMESI -- FIXLENDI ───────────────────────────

def test_neighbor_contamination_rescued_by_exclusion():
    """Brion James deseni: TARGET'in KENDI satirinda crew-kelimesi YOK, ama TARGET'ten hemen once
    gelen satir BASKA bir cast-adayinin ('OTHER PERSON') kendi crew-carpisan satiri -- geriye-bakan
    pencere (i-2..i) bunu 'komsu rol-etiketi' sanip TARGET'i de crew sayardi. Komsu-disla, TARGET'in
    penceresinden OTHER PERSON'in kendi satirini cikarir, TARGET'i kurtarir. OTHER PERSON'in
    KENDISI hala dusmeli (kendi satiri gercekten crew-kelimesi tasiyor, sulandirici varyanti yok)."""
    cast = ["OTHER PERSON", "TARGET PERSON"]
    raw = (["Operator OTHER PERSON", "TARGET PERSON"] * 8)
    result = ctr.filter_cast_by_raw_context(cast, raw)
    assert "TARGET PERSON" in result
    assert "OTHER PERSON" not in result


def test_genuine_distinct_crew_mentions_stay_dropped():
    """Gercek crew: AYNI kelime-kalibi tekrarlanmiyor, ama BAGIMSIZ/farkli 3 crew-baglaminda
    geciyor, baska hicbir cast-adayina komsu degil -- komsu-disla hicbirini etkilemez, oran 1.0
    kalir, DUSER."""
    cast = ["JOHN CREW"]
    raw = [
        "Sound Mixer JOHN CREW",
        "unrelated filler line one",
        "Boom Operator JOHN CREW",
        "unrelated filler line two",
        "Dialogue Editor JOHN CREW",
    ]
    result = ctr.filter_cast_by_raw_context(cast, raw)
    assert "JOHN CREW" not in result


def test_cast_context_still_overrides_high_crew_ratio():
    """cast_seen (STARRING/CAST baglamdan gorulme) mantigina dokunulmadi: oran tek basina
    dusurecek kadar yuksek olsa bile (0.75), bir kez 'Starring' baglaminda gorulmus olmak
    yeterli -- KORUNMALI."""
    cast = ["REAL ACTOR"]
    raw = [
        "Starring", "REAL ACTOR",
        "Camera Operator REAL ACTOR",
        "filler",
        "Sound Mixer REAL ACTOR",
        "filler2",
        "Boom Operator REAL ACTOR",
    ]
    result = ctr.filter_cast_by_raw_context(cast, raw)
    assert "REAL ACTOR" in result


def test_empty_and_none_inputs_unaffected():
    """Bos/None girdi mevcut fail-safe davranisi korunmali."""
    assert ctr.filter_cast_by_raw_context([], ["a", "b"]) == []
    assert ctr.filter_cast_by_raw_context(["X"], None) == ["X"]
    assert ctr.filter_cast_by_raw_context(["X"], []) == ["X"]


def test_santral_real_data_brion_james_rescued():
    """Gercek SANTRAL ham-OCR verisiyle: BRION JAMES (komsu-kirlenme deseni) fix-sonrasi hayatta
    kalmali; kontrol isimleri (zaten hayatta kalan) yeni-DUSMEMELI. Database/ repo-disi/gitignored
    oldugundan bu klasor yoksa atlanir."""
    ocr = _ocr_kunye(SANTRAL_DIR)
    if not ocr:
        print("  SKIP  test_santral_real_data_brion_james_rescued (Database/SANTRAL bulunamadi)")
        return
    candidates = [
        "JACQUELINE KIM", "BRION JAMES", "STEPHEN TOBOLOWSKY",
        "MICHAEL LAURENCE", "CHRISTA MILLER",
    ]
    raw = ctr.load_raw_context_for_ocr(ocr)
    result = ctr.filter_cast_by_raw_context(candidates, raw)
    assert "BRION JAMES" in result, "SANTRAL: BRION JAMES (komsu-kirlenme) fix-sonrasi hayatta kalmali"
    for control in ("STEPHEN TOBOLOWSKY", "MICHAEL LAURENCE", "CHRISTA MILLER"):
        assert control in result, f"SANTRAL: kontrol ismi {control} yeni-DUSMEMELI"


# ─────────────────────────── (A) KENDI-SATIR CAKISMASI -- BILINCLI KAPSAM-DISI ───────────────────────────

def test_santral_jacqueline_kim_self_collision_remains_open():
    """BELGE (fix DEGIL): JACQUELINE KIM'in kendi-satir cakismasi (karakter adi 'Operator') bu
    fix'in kapsami DISINDA -- komsu-disla onu KURTARMAZ (kendi satiri her zaman j==i olarak
    penceresinde kalir). Bu, BILINCLI bir kapsam-siniri (bkz modul docstring'i /
    test_dedup_would_regress_real_actor_bill_murray) -- bu test gelecekte biri yanlislikla
    bu ismi "fixlendi" sanip regresyon eklerse fark ettirsin."""
    ocr = _ocr_kunye(SANTRAL_DIR)
    if not ocr:
        print("  SKIP  test_santral_jacqueline_kim_self_collision_remains_open (Database/SANTRAL bulunamadi)")
        return
    raw = ctr.load_raw_context_for_ocr(ocr)
    result = ctr.filter_cast_by_raw_context(["JACQUELINE KIM"], raw)
    assert "JACQUELINE KIM" not in result


def test_dedup_would_regress_real_actor_bill_murray():
    """DONMUS KANIT (2026-07-10 fix-degerlendirmesi, 268-film taramasindan): icerik-bazli dedup
    (denenip REDDEDILEN alternatif) SANTRAL'i duzeltirdi ama bu GERCEK filmde (Lost in
    Translation TR-kunyesi) BILL MURRAY'i (Scarlett Johansson'un ES-basrol oyuncusu) yanlislikla
    crew sayip dusururdu -- cunku ham OCR'da onun 3 BAGIMSIZ/gercek fiziksel satiri var: kendi
    oyuncu-satiri (8x tekrar, cogunlukla crew=False), 'ASSISTANTS TO BILL MURRAY' (11x tekrar,
    crew=True), 'Performed by Bill Murray' (9x tekrar, crew=True -- muzik katkisi). Ham-tekrar
    sayisi ORANI guvenle esigin (0.60) altinda tutuyordu (21/39=0.538); dedup bu payi yok edip
    2/3=0.667 veya 3/3=1.0'e cikarip onu dusururdu. Bu YUZDEN dedup fix'e DAHIL EDILMEDI -- bu
    test mevcut (dedup'suz) kodun onu DOGRU sekilde hayatta biraktigini kilitler."""
    ocr = _ocr_kunye(BIR_KONUSABILSE_DIR)
    if not ocr:
        print("  SKIP  test_dedup_would_regress_real_actor_bill_murray (Database/BIR KONUSABILSE bulunamadi)")
        return
    raw = ctr.load_raw_context_for_ocr(ocr)
    result = ctr.filter_cast_by_raw_context(["BILL MURRAY"], raw)
    assert "BILL MURRAY" in result


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
