# -*- coding: utf-8 -*-
"""test_credit_qc_block.py — credit_qc_block birleşik QC bloğu testleri.

İki katman:
  • HERMETİK (DB'siz, FakeKB): mantık + OCR-otorite invariant'i — her ortamda hızlı/deterministik.
  • ENTEGRASYON (gerçek duckdb): DB varsa AHLAT AĞACI uçtan-uca (casing + kimlik). Yoksa atlanır.

Çalıştır:  python -m pytest tests/test_credit_qc_block.py -v
       ya:  python tests/test_credit_qc_block.py   (kendi koşucusu — pytest gerekmez)
"""
import os
import sys
import tempfile

# Birim testleri AĞDAN BAĞIMSIZ olmalı: web_identity ÇAPA-2 (TMDB) ağa gitmesin.
os.environ.pop("MITAS_TMDB", None)
os.environ.pop("TMDB_API_KEY", None)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import credit_qc_block as q
import credit_crosscheck as cc

# ── Hermetik testlerde casing'i hızlandır (DB'ye gitme): mantık fold-bazlı doğrulanır, kasa önemsiz.
_REAL_UPPER = q._upper_names
_REAL_PROSE = q._tr_upper_prose
q._upper_names = lambda names: [str(n).upper() for n in (names or [])]
q._tr_upper_prose = lambda text, names: (text or "").upper()


class FakeKB:
    """CreditKB.crosscheck arayüzünü taklit eder (kontrollü kimlik kilidi)."""

    def __init__(self, *, verdict="TEYİT", oyon=None, ocast=None, cast_ov=0,
                 imdb_id="tt0000001", tmdb_id=None):
        self._d = dict(verdict=verdict, otoriter_yonetmen=list(oyon or []),
                       otoriter_cast=list(ocast or []), cast_ortusme=cast_ov,
                       matched_imdb_id=imdb_id, wikidata_imdb_id=imdb_id, wikidata_tmdb_id=tmdb_id)
        self.imdb = None  # _kb_producers atlanır

    def crosscheck(self, rd, rc, *, title_tr=None, original=None, year=None):
        return dict(self._d)

    def close(self):
        pass


def _ozet():  # gate'i geçen ≥20 kelime gerçek özet
    return ("Genc adam memleketine doner ve hayallerinin pesinden kosarken ailesiyle yasadigi "
            "catismalar arasinda kendi yolunu bulmaya calisir ve sonunda zor bir karar verir.")


# ─────────────────────────── SAF (DB'siz) BİRİM TESTLERİ ───────────────────────────
def test_detect_script():
    assert q.detect_script("Ivan Petrov") == "latin"
    assert q.detect_script("Иван Петров") == "cyrillic"
    assert q.detect_script("Γιώργος") == "greek"
    assert q.detect_script("张艺谋") == "han"
    assert q.detect_script("محمد") == "arabic"
    assert q.detect_script("") == "latin"


def test_transliterate_tablo():
    assert q.transliterate("Андрей Тарковский")[0] == "Andrey Tarkovskiy"
    assert q.transliterate("Иван Петров") == ("Ivan Petrov", "tablo")
    assert q.transliterate("Γιώργος Λάνθιμος")[0] == "Giorgos Lanthimos"


def test_transliterate_failed_without_lib():
    # Çince + lib yok → FAILED (sessiz silme YOK)
    latin, yontem = q.transliterate("张艺谋")
    assert yontem in ("FAILED", "pypinyin", "unidecode")
    if yontem == "FAILED":
        assert latin == "张艺谋"


def test_split_names_dedup():
    out = q._split_names(["Ali Veli & Ayşe Fatma", "Ali Veli", "Mehmet, Hasan"])
    folds = [cc.fold(x) for x in out]
    assert len(folds) == len(set(folds))           # tekrar yok
    assert any(cc.fold("Ali Veli") == f for f in folds)


def test_ozet_gate_placeholder_and_short():
    assert q._ozet_gate("HAM TRANSCRİPT buraya geldi", [])[1] == 0
    assert q._ozet_gate("KALIP ÖZET", [])[1] == 0
    assert q._ozet_gate("Kısa bir özet.", [])[1] == 3
    assert q._ozet_gate(_ozet(), [])[1] >= 20


def test_poster_ok(tmp_path=None):
    d = tempfile.mkdtemp()
    big_landscape = os.path.join(d, "land.bin")
    with open(big_landscape, "wb") as f:
        f.write(b"x" * 6000)
    # PIL yoksa boyut-fallback True; PIL varsa içerik resim değil → except → boyut-fallback True.
    assert q.poster_ok(big_landscape) in (True, False)
    assert q.poster_ok(os.path.join(d, "yok.jpg")) is False
    small = os.path.join(d, "small.jpg")
    with open(small, "wb") as f:
        f.write(b"x" * 100)
    assert q.poster_ok(small) is False


# ─────────────────────── KİMLİK / DOLDURMA / KARAR (FakeKB) ───────────────────────
def test_locked_floor_fill_invariant():
    """Güncel film: 4 OCR cast → KB'den 8'e doldur. INVARIANT: ilk 4 = OCR (aynı kişi), eklemeler sonra."""
    ocr = ["Dogu Demirkol", "Murat Cemcir", "Bennu Yildirimlar", "Hazar Erguclu"]
    kb = FakeKB(verdict="TEYİT", oyon=["Nuri Bilge Ceylan"],
                ocast=ocr + ["Serkan Keskin", "Tamer Levent", "Oner Erkan", "Ahmet Rifat Sungar"],
                cast_ov=4)
    r = q.qc_credit_block(["Nuri Bilge Ceylan"], ocr, [], title="AHLAT", year=2018,
                          ozet=_ozet(), kb=kb)
    assert r["kimlik"]["locked"] is True
    assert r["floor"]["ulasilan"] == 8 and r["floor"]["hedef"] == 8
    # INVARIANT: ilk 4 çıktı, 4 OCR ismiyle aynı kişi (sıra korunur)
    for i in range(4):
        assert cc.name_match(r["temiz_cast"][i], ocr[i]), (i, r["temiz_cast"][i])
    assert len(r["temiz_cast"]) == 8
    assert not r["gerekceler"]                       # tüm sert sinyaller temiz


def test_director_canonical_spelling():
    """OCR yönetmen yazımı KB-kanonik'e düzelir (aynı kişi, tek-token misread), ezme değil."""
    kb = FakeKB(oyon=["Nuri Bilge Ceylan"], ocast=["Ali Veli", "Ayse Can"], cast_ov=2)
    r = q.qc_credit_block(["Nuri Bilge Ceylon"], ["Ali Veli", "Ayse Can"], [], title="X", year=2018,
                          ozet=_ozet(), kb=kb)
    assert cc.name_match(r["temiz_yon"][0], "Nuri Bilge Ceylan")


def test_director_empty_kb_fill():
    """Deferans-ON (default): OCR yönetmen boş → KB-fill ATLANIR → temiz_yon=[].
    Deferans-OFF: OCR yönetmen boş + kimlik kilitli → KB'den doldurur (eski davranış)."""
    kb = FakeKB(oyon=["Akira Kurosawa"], ocast=["Ali Veli", "Ayse Can"], cast_ov=2)

    # --- Senaryo A: deferans-ON (default) ---
    old_val = os.environ.pop("MITAS_CREDIT_DEFERENCE", None)
    try:
        # MITAS_CREDIT_DEFERENCE set edilmemiş → default "1" → KB-fill ATLANIR
        r = q.qc_credit_block([], ["Ali Veli", "Ayse Can"], [], title="X", year=1985,
                              ozet=_ozet(), kb=kb)
        assert r["temiz_yon"] == [], f"deferans-ON: KB-fill atlanmalı, bulundu: {r['temiz_yon']}"
    finally:
        if old_val is not None:
            os.environ["MITAS_CREDIT_DEFERENCE"] = old_val

    # --- Senaryo B: deferans-OFF → eski davranış: OCR boş + kilitli → KB-fill ---
    old_val = os.environ.get("MITAS_CREDIT_DEFERENCE")
    os.environ["MITAS_CREDIT_DEFERENCE"] = "0"
    try:
        r2 = q.qc_credit_block([], ["Ali Veli", "Ayse Can"], [], title="X", year=1985,
                               ozet=_ozet(), kb=kb)
        assert r2["temiz_yon"], "deferans-OFF: KB-fill bekleniyor (OCR boş + kilitli)"
        assert cc.name_match(r2["temiz_yon"][0], "Akira Kurosawa"), \
            f"deferans-OFF: KB-fill 'Akira Kurosawa' bekleniyor, bulundu: {r2['temiz_yon']}"
    finally:
        if old_val is None:
            os.environ.pop("MITAS_CREDIT_DEFERENCE", None)
        else:
            os.environ["MITAS_CREDIT_DEFERENCE"] = old_val


def test_director_conflict_goes_kontrol():
    """OCR yönetmen KB ile çelişiyor → KB ile EZME YOK → yön boş → KONTROL/YONETMEN."""
    kb = FakeKB(oyon=["Akira Kurosawa"], ocast=["Ali Veli", "Ayse Can"], cast_ov=2)
    r = q.qc_credit_block(["Zhang Yimou"], ["Ali Veli", "Ayse Can"], [], title="X", year=1985,
                          ozet=_ozet(), kb=kb)
    assert r["temiz_yon"] == []
    assert r["karar"] == "KONTROL" and r["kontrol_tip"] == "YONETMEN"


def test_old_film_floor_lenient():
    """Eski film (<2000) az oyuncu → floor ESNEK → CAST sinyali YOK (KABUL)."""
    kb = FakeKB(oyon=["Dir"], ocast=["Ali Veli", "Ayse Can", "Mehmet Han"], cast_ov=3)
    r = q.qc_credit_block(["Dir"], ["Ali Veli", "Ayse Can", "Mehmet Han"], ["Yapimci Bir"],
                          title="ESKI", year=1965, ozet=_ozet(), kb=kb)
    assert r["floor"]["hedef"] == 6 and r["floor"]["kabul"] is True
    assert not any("oyuncu yetersiz" in g for g in r["gerekceler"])


def test_new_film_floor_strict_kontrol():
    """Güncel film, KB de az → 8'e ulaşılamaz → KONTROL/CAST."""
    kb = FakeKB(oyon=["Dir"], ocast=["Ali Veli", "Ayse Can", "Mehmet Han"], cast_ov=3)
    r = q.qc_credit_block(["Dir"], ["Ali Veli", "Ayse Can", "Mehmet Han"], ["Yapimci Bir"],
                          title="YENI", year=2018, ozet=_ozet(), kb=kb)
    assert r["floor"]["ulasilan"] < 8
    assert any("oyuncu yetersiz" in g for g in r["gerekceler"])
    assert r["kontrol_tip"] in ("CAST", "KIMLIK", "YONETMEN")


def test_garbage_dropped_real_preserved():
    """İsim-DIŞI çöp (kurum/tek-token) düşer, gerçek OCR ismi korunur (çöp sızdırma yok).
    NOT: 'valid görünen' OCR-bozulması (GEORCE STOAD ALRRDED) OCR-otorite gereği DÜŞÜRÜLMEZ
    (gerçek alt-oyuncu olabilir) — bu kapı yalnız leksikal-garble + kurum/tek-token eler."""
    ocr = ["Yul Brynner", "Paramount", "George Segal"]   # 'Paramount' tek-token kurum → düşer
    kb = FakeKB(oyon=["Richard Wilson"], ocast=["Yul Brynner", "George Segal"], cast_ov=2)
    r = q.qc_credit_block(["Richard Wilson"], ocr, [], title="SILAHSORE DAVET", year=1964,
                          ozet=_ozet(), kb=kb)
    folds = [cc.fold(x) for x in r["temiz_cast"]]
    assert any("yul brynner" == f for f in folds)        # gerçek korunur
    assert all(f != "paramount" for f in folds)          # çöp sızmaz


def test_cyrillic_cast_kb_latin():
    """Kiril OCR yönetmen+cast → S2 translit → KB-Latin kanonik eşleşme.

    Kök-neden (düzeltildi, 2026-06-28): _split_names içinde _fold Kiril için '' döndürdüğünden
    isimler S0'da siliniyordu → S2 translit hiç çalışmıyordu → yon=[] → KB-fill "OCR boş" dalına
    giriyordu. Fix: fold boşsa part.lower() ile tekilleştir, isim korunur, S2 devreye girer.
    """
    kb = FakeKB(oyon=["Andrey Tarkovskiy"],
                ocast=["Anatoliy Solonitsyn", "Ivan Lapikov"], cast_ov=2)
    r = q.qc_credit_block(["Андрей Тарковский"],
                          ["Анатолий Солоницын", "Иван Лапиков"], [],
                          title="ANDREY RUBLEV", year=1966, ozet=_ozet(), kb=kb)
    # S2 translit → 'Andrey Tarkovskiy'; S4 ilk dal: yon=[translit] + locked + otoriter_yon → KB-kanonik
    assert r["temiz_yon"], f"Kiril yönetmen translit edilip KB eşleşmeli, temiz_yon={r['temiz_yon']}"
    assert cc.name_match(r["temiz_yon"][0], "Andrey Tarkovskiy"), \
        f"Kiril→translit→KB-kanonik bekleniyor, bulundu: {r['temiz_yon'][0]}"
    # cast de translit edilmeli; Latin-dışı sızmadı
    assert q.detect_script(" ".join(r["temiz_cast"])) == "latin", \
        f"Kiril cast Latin'e dönmeli, temiz_cast={r['temiz_cast']}"


def test_placeholder_ozet_kontrol():
    kb = FakeKB(oyon=["Dir"], ocast=["Ali Veli", "Ayse Can"], cast_ov=2)
    r = q.qc_credit_block(["Dir"], ["Ali Veli", "Ayse Can", "Mehmet Han", "Veli Han"],
                          [], title="X", year=1980, ozet="HAM TRANSCRİPT", kb=kb)
    assert any("özet" in g.lower() for g in r["gerekceler"])
    assert r["kontrol_tip"] == "OZET" or "OZET" in [g["tip"] for g in r["gerekce_tipleri"]]


def test_not_locked_goes_kontrol_kimlik():
    """Kimlik kurulamaz (KAYNAK_YOK) → doldurma YOK, OCR korunur, KONTROL/KIMLIK."""
    kb = FakeKB(verdict="KAYNAK_YOK", oyon=[], ocast=[], cast_ov=0, imdb_id=None)
    r = q.qc_credit_block(["Bir Yon"], ["Ali Veli", "Ayse Can"], [], title="BILINMEYEN",
                          year=2019, ozet=_ozet(), kb=kb)
    assert r["kimlik"]["locked"] is False
    assert r["karar"] == "KONTROL" and r["kontrol_tip"] == "KIMLIK"
    # OCR cast EZİLMEDİ (korunur)
    folds = [cc.fold(x) for x in r["temiz_cast"]]
    assert any("ali veli" == f for f in folds)


def test_invariant_no_ocr_added_when_unlocked():
    """Kilit yokken HİÇ doldurma olmaz (eklemeler yalnız kilitliyken)."""
    kb = FakeKB(verdict="KAYNAK_YOK", oyon=[], ocast=[], cast_ov=0, imdb_id=None)
    r = q.qc_credit_block([], ["Ali Veli", "Ayse Can"], [], title="X", year=2019,
                          ozet=_ozet(), kb=kb)
    assert len(r["temiz_cast"]) == 2                  # KB-fill yok
    assert r["floor"]["ulasilan"] == 2


def test_deference_director_producer_on_off():
    """Regresyon kalkanı: deferans-ON/OFF davranışını kilitler.

    Deferans-ON (default, MITAS_CREDIT_DEFERENCE=1):
      - Yönetmen OCR boşsa KB-fill YAPILMAZ (temiz_yon=[]).
      - Yapımcı OCR boşsa KB-fill YAPILMAZ (temiz_yap=[]).
    Deferans-OFF (MITAS_CREDIT_DEFERENCE=0):
      - Yönetmen OCR boşsa + kilitliyse KB'den doldurulur (temiz_yon dolu).
    """
    kb = FakeKB(oyon=["Akira Kurosawa"], ocast=["Ali Veli", "Ayse Can"], cast_ov=2,
                tmdb_id="123")

    # ── Deferans-ON ──
    saved = os.environ.pop("MITAS_CREDIT_DEFERENCE", None)
    try:
        r_on = q.qc_credit_block([], ["Ali Veli", "Ayse Can"], [],
                                 title="X", year=1990, ozet=_ozet(), kb=kb)
        assert r_on["temiz_yon"] == [], \
            f"deferans-ON: yönetmen KB-fill atlanmalı, bulundu: {r_on['temiz_yon']}"
        assert r_on["temiz_yap"] == [], \
            f"deferans-ON: yapımcı KB-fill atlanmalı, bulundu: {r_on['temiz_yap']}"
    finally:
        if saved is not None:
            os.environ["MITAS_CREDIT_DEFERENCE"] = saved

    # ── Deferans-OFF ──
    old = os.environ.get("MITAS_CREDIT_DEFERENCE")
    os.environ["MITAS_CREDIT_DEFERENCE"] = "0"
    try:
        r_off = q.qc_credit_block([], ["Ali Veli", "Ayse Can"], [],
                                  title="X", year=1990, ozet=_ozet(), kb=kb)
        assert r_off["temiz_yon"], \
            f"deferans-OFF: yönetmen KB-fill bekleniyor, temiz_yon={r_off['temiz_yon']}"
        assert cc.name_match(r_off["temiz_yon"][0], "Akira Kurosawa"), \
            f"deferans-OFF: 'Akira Kurosawa' bekleniyor, bulundu: {r_off['temiz_yon']}"
    finally:
        if old is None:
            os.environ.pop("MITAS_CREDIT_DEFERENCE", None)
        else:
            os.environ["MITAS_CREDIT_DEFERENCE"] = old


def test_dubbing_director_drop():
    """Türkçe-dublaj rol (SESLENDİRME/DUBLAJ YÖNETMENİ +yard.) yönetmen alanından düşer; gerçek kalır."""
    from credit_text_read import _drop_dubbing_directors
    raw = ["KURGU", "AHMET K", "SESLENDİRME YÖNETMEN YARDIMCISI", "ESRA TANAR",
           "SESLENDİRME YÖNETMENİ", "ENGİN AYBAKAN", "YÖNETMEN", "Sam Raimi"]
    kept, dropped = _drop_dubbing_directors(["ESRA TANAR", "ENGİN AYBAKAN", "Sam Raimi"], raw)
    assert "ESRA TANAR" in dropped and "ENGİN AYBAKAN" in dropped   # dublaj rolleri düşer
    assert "Sam Raimi" in kept                                       # gerçek yönetmen korunur
    assert _drop_dubbing_directors(["X"], None)[0] == ["X"]          # ham yoksa dokunma (fail-safe)


# ─────────────────────────── ENTEGRASYON (gerçek duckdb) ───────────────────────────
def _db_var():
    return os.path.exists(os.environ.get("MITAS_WIKIDATA_DUCKDB",
                                          r"X:\DIGER\Mitas_Files\MitaData\mitas.duckdb"))


def test_integration_ahlat_real_db():
    """Gerçek DB ile AHLAT AĞACI: kimlik TEYİT + Türkçe İ korunur + yabancı ASCII (casing)."""
    if not _db_var():
        print("  [atla] gerçek duckdb yok — entegrasyon testi atlandı")
        return
    up, pr = q._upper_names, q._tr_upper_prose
    q._upper_names, q._tr_upper_prose = _REAL_UPPER, _REAL_PROSE   # gerçek casing
    try:
        r = q.qc_credit_block(
            ["Nuri Bilge Ceylan"],
            ["Doğu Demirkol", "Murat Cemcir", "Bennu Yıldırımlar", "Hazar Ergüçlü"],
            [], title="AHLAT AĞACI", original="The Wild Pear Tree", year=2018, ozet=_ozet())
        assert r["kimlik"]["locked"] is True
        assert r["kimlik"]["verdict"] == "TEYİT"
        assert r["floor"]["ulasilan"] == 8
        assert "NURİ BİLGE CEYLAN" in r["temiz_yon"]            # Türkçe İ korundu
        for i, ocr in enumerate(["Doğu Demirkol", "Murat Cemcir", "Bennu Yıldırımlar", "Hazar Ergüçlü"]):
            assert cc.name_match(r["temiz_cast"][i], ocr)       # INVARIANT (gerçek DB)
    finally:
        q._upper_names, q._tr_upper_prose = up, pr


# ─────────────────────────── kendi koşucusu (pytest'siz) ───────────────────────────
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
    print(f"\n{ok} geçti, {fail} başarısız ({len(fns)} test)")
    return fail


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(1 if _run_all() else 0)
