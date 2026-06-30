# -*- coding: utf-8 -*-
"""credit_qc_otorite_audit_test.py — OCR-OTORİTE DENETİM sinyallerinin (SIFIR-ROUTE) regresyon testleri.

Mühürlenen vakalar:
  - KEDİ GÖZÜ substitüsyon imzası: okunan ELEANOR PARKER düştüyse audit bunu görür.
  - KB sıfırdan kişi eklemez; kb_floor_added geriye dönük şema alanı olarak boş kalır.
  - HAZELTON/HAZLETON yakın-yazım çifti yakalanır.
  - BİTİŞİKLİK FP'si: 'ANN LEE' ham'da 'MARY ANN'+'BRUCE LEE' varken (bitişik değil) yakalanmaz.

ÇALIŞTIR (duckdb GEREKMEZ — saf-fonksiyon testi):
  E:/MITAS/venvs/ocr/Scripts/python.exe scripts/credit_qc_otorite_audit_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit_qc_block as q

_FAILED = []


def _chk(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    if not cond:
        _FAILED.append(name)


def test_kedi_gozu_substitution():
    """KEDİ GÖZÜ: Parker düştü (ocr_dropped); KB sıfırdan kişi ekleme sinyali artık yok."""
    # Ham-OCR star-kart yapısı (ELEANOR\nPARKER ardışık satır) — gerçek dosyanın iskeleti.
    raw = (["GAYLE", "HUNNICUTT"] * 3 + ["ELEANOR", "PARKER"] * 6
           + ["CO-STARRING", "TIM HENRY", "LAURENCE NAISMITH", "JENNIFER LEAK",
              "LINDEN CHILES", "MARK HERRON", "ANNABELLE GARTH"])
    final_cast = ["TIM HENRY", "LAURENCE NAISMITH", "JENNIFER LEAK", "LINDEN CHILES",
                  "MARK HERRON", "ANNABELLE GARTH", "MICHAEL SARRAZIN", "GAYLE HUNNICUTT"]
    final_yap = ["BERNARD SCHWARTZ", "PHILLIP HAZELTON", "PHILLIP HAZLETON"]
    otoriter = ["Michael Sarrazin", "Gayle Hunnicutt", "Eleanor Parker", "Tim Henry",
                "Laurence Naismith", "Jennifer Leak", "Linden Chiles", "Mark Herron"]
    iz = []
    r = q._compute_otorite_audit(raw, final_cast, final_yap, otoriter, iz)
    print("KEDİ GÖZÜ:", r)
    _chk("ocr_dropped = [Eleanor Parker]", [x.lower() for x in r["ocr_dropped"]] == ["eleanor parker"])
    _chk("kb_floor_added boş (KB sıfırdan ekleme yok)", r["kb_floor_added"] == [])
    _chk("fuzzy_dups HAZELTON/HAZLETON",
         any({a.lower(), b.lower()} == {"phillip hazelton", "phillip hazleton"} for a, b in r["fuzzy_dups"]))
    _chk("ocr_authority_violation = False", r["ocr_authority_violation"] is False)
    _chk("raw_groundtruth_used = True", r["raw_groundtruth_used"] is True)


def test_adjacency_fp():
    """BİTİŞİKLİK FP: 'ANN LEE' iki AYRI isimden (MARY ANN + BRUCE LEE) toplanmasın → eşleşme YOK."""
    raw = ["MARY ANN", "BRUCE LEE", "JANE DOE"]
    seq = q._audit_raw_token_seq(raw)
    _chk("'ANN LEE' bitişik DEĞİL → in_raw False (FP engellendi)",
         q._audit_name_in_raw("Ann Lee", seq) is False)
    _chk("'MARY ANN' bitişik → in_raw True", q._audit_name_in_raw("Mary Ann", seq) is True)
    _chk("'BRUCE LEE' bitişik → in_raw True", q._audit_name_in_raw("Bruce Lee", seq) is True)


def test_no_groundtruth_safe():
    """Groundtruth yokken: ocr_dropped/kb_floor_added boş, violation False (fail-safe)."""
    r = q._compute_otorite_audit(None, ["A B", "C D"], ["E F"],
                                 ["X Y", "A B"], [])
    _chk("groundtruth yok → raw_groundtruth_used False", r["raw_groundtruth_used"] is False)
    _chk("groundtruth yok → ocr_dropped boş", r["ocr_dropped"] == [])
    _chk("groundtruth yok → kb_floor_added boş", r["kb_floor_added"] == [])
    _chk("groundtruth yok → violation False", r["ocr_authority_violation"] is False)


def test_real_file_if_present():
    """Gerçek KEDİ GÖZÜ dosyası varsa onunla da doğrula (iskelet ≡ gerçek)."""
    import glob
    clip = "E:/MITAS/Database/KEDİ GÖZÜ 1969-0057-1-0000-00-1"
    rawf = sorted(glob.glob(clip + "/ocr/*/ocr_raw_all.txt"))
    if not rawf:
        print("  SKIP gerçek-dosya (yok)")
        return
    with open(rawf[-1], encoding="utf-8", errors="ignore") as f:
        raw = [ln.strip() for ln in f if ln.strip()]
    seq = q._audit_raw_token_seq(raw)
    _chk("gerçek ham: ELEANOR PARKER bitişik bulunur", q._audit_name_in_raw("Eleanor Parker", seq) is True)
    _chk("gerçek ham: GAYLE HUNNICUTT bitişik bulunur", q._audit_name_in_raw("Gayle Hunnicutt", seq) is True)
    _chk("gerçek ham: MICHAEL SARRAZIN YOK", q._audit_name_in_raw("Michael Sarrazin", seq) is False)


def test_floorfill_partition():
    """② Audit çekirdeği hâlâ ham-OCR'da okunan/okunmayan ayrımını yapar; ekleme için kullanılmaz."""
    raw = (["GAYLE", "HUNNICUTT"] * 3 + ["ELEANOR", "PARKER"] * 6
           + ["TIM HENRY", "LAURENCE NAISMITH"])
    seq = q._audit_raw_token_seq(raw)
    otoriter = ["Michael Sarrazin", "Gayle Hunnicutt", "Eleanor Parker", "Tim Henry"]
    read = [a for a in otoriter if q._audit_name_in_raw(a, seq)]
    unread = [a for a in otoriter if not q._audit_name_in_raw(a, seq)]
    _chk("② okunan = Hunnicutt+Parker+Tim Henry (Sarrazin değil)",
         [x.lower() for x in read] == ["gayle hunnicutt", "eleanor parker", "tim henry"])
    _chk("② okunmayan = [Michael Sarrazin]", [x.lower() for x in unread] == ["michael sarrazin"])


def test_fix_e2e_duckdb():
    """②+③ uçtan uca (duckdb varsa): KB sıfırdan cast eklemez; Hazleton-çift temizlenir."""
    import glob
    clip = "E:/MITAS/Database/KEDİ GÖZÜ 1969-0057-1-0000-00-1"
    rawf = sorted(glob.glob(clip + "/ocr/*/ocr_raw_all.txt"))
    if not rawf:
        print("  SKIP e2e (ham dosya yok)"); return
    try:
        kb = q.cc.CreditKB()
    except Exception:
        print("  SKIP e2e (duckdb yok)"); return
    raw = [ln.strip() for ln in open(rawf[-1], encoding="utf-8", errors="ignore") if ln.strip()]
    for k, v in {"MITAS_QC_FLOORFILL_OCRGUARD": "1", "MITAS_QC_FUZZY_DEDUP": "1"}.items():
        os.environ[k] = v
    try:
        r = q.qc_credit_block(
            ["David Lowell Rich"],
            ["TIM HENRY", "LAURENCE NAISMITH", "JENNIFER LEAK", "LINDEN CHILES", "MARK HERRON", "ANNABELLE GARTH"],
            ["Bernard Schwartz", "Phillip Hazelton"],
            title="KEDİ GÖZÜ", original="Eye of the Cat", year=1969, kb=kb, raw_names_groundtruth=raw)
    finally:
        for k in ("MITAS_QC_FLOORFILL_OCRGUARD", "MITAS_QC_FUZZY_DEDUP"):
            os.environ.pop(k, None)
        try:
            kb.close()
        except Exception:
            pass
    cu = [str(x).upper() for x in r["temiz_cast"]]
    yu = [str(x).upper() for x in r["temiz_yap"]]
    _chk("e2e: ELEANOR PARKER cast'e KB'den eklenmez", not any("PARKER" in x for x in cu))
    _chk("e2e: MICHAEL SARRAZIN cast'te DEĞİL", not any("SARRAZIN" in x for x in cu))
    _chk("e2e: HAZLETON çifti yok (tek HAZ-yapımcı)", sum(1 for x in yu if "HAZ" in x) == 1)


if __name__ == "__main__":
    test_kedi_gozu_substitution()
    test_adjacency_fp()
    test_no_groundtruth_safe()
    test_real_file_if_present()
    test_floorfill_partition()
    test_fix_e2e_duckdb()
    print("\nSONUC:", "TUMU PASS" if not _FAILED else f"{len(_FAILED)} FAIL: {_FAILED}")
    sys.exit(0 if not _FAILED else 1)
