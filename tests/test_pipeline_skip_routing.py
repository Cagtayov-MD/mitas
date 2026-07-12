# -*- coding: utf-8 -*-
"""MİTAS Hazır/Kontrol yönlendirme testleri — GERÇEK production import (İP-4 yeniden-yazımı).

TARİHÇE (2026-07-11): Bu dosyanın eski sürümü karar mantığını KOPYALIYORDU ("mitas_pipeline
doğrudan import edilmiyor" notuyla) — GPT tur-3 kör-nokta tespiti üzerine denetlendi ve kopya
yalnız kör değil BAYAT-YANLIŞTI: ASR-kapısı bugün MITAS_SES_DIL_KONTROL (default KAPALI),
özet-kapısı MITAS_OZET_KONTROL (default KAPALI) arkasında — kopya bunları koşulsuz sanıyordu.
Yeni sürüm, pipeline'ın GERÇEKTEN çağırdığı katmanı import eder:
    credit_severity_router.classify + from_signals/from_durum  (mitas_pipeline §karar bölgesi
    reasons→_sig→classify→folder zinciriyle bunu çağırır; İP-4 tek-sınıflandırıcı sözleşmesi).
NOT (İP-9'a): reasons-MONTAJI (OCR-bucket/ASR/PDF/xml-cast kapılarının inline zinciri,
mitas_pipeline ~2947-3130) hâlâ pipeline-içi; saf-fonksiyona çıkarma strangler fazında.
Buradaki testler o zincirin ÜRETTİĞİ reason-metinlerinin routing'ini production-kodla doğrular."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import credit_severity_router as router  # noqa: E402


def _route(reasons=None, qwen_qc=None, uyari=None, **ek):
    sig = router.from_signals(qwen_qc=qwen_qc or {}, reasons=reasons or [],
                              qwen_uyari=uyari or [], **ek)
    return router.classify(sig)


# ── INVARIANT: kusursuz film ONAYLI'ya ───────────────────────────────────────
def test_temiz_film_onayli():
    r = _route(qwen_qc={"ozet_var": True, "oyuncu_sayisi": 8, "yapimci_var": True,
                        "yonetmen_var": True, "afis_var": True, "hepsi_buyuk_harf": True})
    assert r["tier"] == "TEMIZ" and r["folder"] == "ONAYLI"


# ── INVARIANT: pipeline reason-metinleri KONTROL'e yönlendirir ───────────────
def test_yonetmen_okunamadi_reason_yonetmen_kontrol():
    # kaynak reason-metni: mitas_pipeline karar bölgesi / from_durum substring köprüsü
    r = _route(reasons=["yönetmen okunamadı"],
               qwen_qc={"ozet_var": True, "oyuncu_sayisi": 8, "yonetmen_var": False,
                        "yapimci_var": True, "afis_var": True, "hepsi_buyuk_harf": True})
    assert r["tier"] == "KONTROL"
    assert "YONETMEN" in r["kontrol_tip"]


def test_kimlik_celiskisi_kontrol():
    r = _route(reasons=["kimlik çelişki (KB cross-check)"],
               qwen_qc={"ozet_var": True, "oyuncu_sayisi": 8, "yonetmen_var": True,
                        "yapimci_var": True, "afis_var": True, "hepsi_buyuk_harf": True})
    assert r["tier"] == "KONTROL" and "KIMLIK" in r["kontrol_tip"]


def test_xml_pdf_cast_kesisimi_sifir_wrongfilm():
    r = _route(reasons=["cast kesişimi 0"],
               qwen_qc={"ozet_var": True, "oyuncu_sayisi": 8, "yonetmen_var": True,
                        "yapimci_var": True, "afis_var": True, "hepsi_buyuk_harf": True})
    assert r["tier"] == "KONTROL" and "KIMLIK" in r["kontrol_tip"]


def test_ozet_yok_kontrol():
    r = _route(qwen_qc={"ozet_var": False, "oyuncu_sayisi": 8, "yonetmen_var": True,
                        "yapimci_var": True, "afis_var": True, "hepsi_buyuk_harf": True})
    assert r["tier"] == "KONTROL" and "OZET" in r["kontrol_tip"]


def test_oyuncu_yok_kontrol():
    r = _route(qwen_qc={"ozet_var": True, "oyuncu_sayisi": 0, "yonetmen_var": True,
                        "yapimci_var": True, "afis_var": True, "hepsi_buyuk_harf": True})
    assert r["tier"] == "KONTROL" and "CAST" in r["kontrol_tip"]


# ── INVARIANT: AFIS tek başına warning; görünür ama teslimi engellemez ─────────
def test_afis_yok_warning_ile_onayliya_gider():
    r = _route(qwen_qc={"ozet_var": True, "oyuncu_sayisi": 8, "yonetmen_var": True,
                        "yapimci_var": True, "afis_var": False, "hepsi_buyuk_harf": True})
    assert r["tier"] == "TEMIZ"
    assert r["folder"] == "ONAYLI"
    assert r["kontrol_tip"] is None
    assert r["hafif"] == ["AFIS"]


# ── INVARIANT: AĞIR, hafifi gölgede bırakır (kontrol şart kalır) ─────────────
def test_agir_ve_hafif_birlikte_agir_kazanir():
    r = _route(reasons=["yönetmen okunamadı"],
               qwen_qc={"ozet_var": True, "oyuncu_sayisi": 8, "yonetmen_var": False,
                        "yapimci_var": True, "afis_var": False, "hepsi_buyuk_harf": True})
    assert r["tier"] == "KONTROL"
    assert "AFIS" in r["hafif"], "ağır filmin hafif kusuru da kayıtlı kalır"


# ── INVARIANT (eski dosyadan korunan niyet): ana_dil kapısı ──────────────────
def test_ana_dil_tr_ses_kontrol_tetiklemez():
    r = _route(qwen_qc={"ozet_var": True, "oyuncu_sayisi": 8, "yonetmen_var": True,
                        "yapimci_var": True, "afis_var": True, "hepsi_buyuk_harf": True},
               ana_dil="TR")
    assert r["tier"] == "TEMIZ"


def test_ana_dil_yabanci_ses_kontrol():
    r = _route(qwen_qc={"ozet_var": True, "oyuncu_sayisi": 8, "yonetmen_var": True,
                        "yapimci_var": True, "afis_var": True, "hepsi_buyuk_harf": True},
               ana_dil="EN")
    assert r["tier"] == "KONTROL" and r["kontrol_tip"] == "SES"
