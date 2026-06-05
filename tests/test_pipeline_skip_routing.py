"""
MİTAS pipeline Hazır/Kontrol yönlendirme kural testleri
========================================================
Karar mantığı kaynağı: scripts/mitas_pipeline.py  satır 767–827

NOT: mitas_pipeline.py doğrudan import edilMİYOR — pipeline argparse/model
yükleme/uvicorn/subprocess gibi ağır yan etkiler barındırıyor; import denenmesi
CI'da crash'e veya çok uzun başlangıç süresine yol açar.

Bunun yerine karar kuralı bu dosyada saf Python olarak yeniden ifade edilmiştir.
Her testin üstündeki `# kaynak:` yorumu kaynaktaki ilgili satırı gösterir.

Kural özeti (satır 767–827):
  reasons = []
  if ocr_bucket not in ("GUVENILIR",):          → reasons ← OCR bucket hatası
  if asr_status not in ("done","ATLANDI","skipped_unsupported_lang"):
                                                  → reasons ← ASR hatası
  if not pdf_path:                               → reasons ← PDF yok
  [+ qwen/cast kapıları — ayrı testlerle]
  karar = "Hazır" if not reasons else "Kontrol"
"""

import pytest


# ---------------------------------------------------------------------------
# Karar mantığını izole eden yardımcı fonksiyon
# (kaynak: scripts/mitas_pipeline.py, satır 767–827)
# ---------------------------------------------------------------------------

# kaynak: satır 771 — ASR whitelist
ASR_OK_SET = frozenset({"done", "ATLANDI", "skipped_unsupported_lang"})

# kaynak: satır 769 — OCR whitelist (tek eleman)
OCR_OK_SET = frozenset({"GUVENILIR"})


def _karar(
    ocr_bucket: str,
    asr_status: str,
    pdf_path: str | None,
    *,
    qwen_qc: dict | None = None,
    xml_pdf_cast_overlap_zero: bool = False,
    kimlik_celiskisi: bool = False,
) -> tuple[str, list[str]]:
    """
    scripts/mitas_pipeline.py satır 767–827'nin saf Python yansıması.

    Karar kapılarını sırasıyla uygular; reasons listesi boşsa "Hazır", dolu ise "Kontrol".
    qwen_qc None veya {"error":...} ise qwen kapısı atlanır (pipeline davranışıyla özdeş).
    xml_pdf_cast_overlap_zero True ise B-4 "cast kesişimi 0" uyarısı eklenir.
    kimlik_celiskisi True ise KB cross-check çelişkisi eklenir.
    """
    reasons: list[str] = []

    # ── Kural 1: OCR bucket ─────────────────────────────────────────────────
    # kaynak: satır 769–770
    if ocr_bucket not in OCR_OK_SET:
        reasons.append(f"OCR bucket={ocr_bucket}")

    # ── Kural 2: ASR durumu ─────────────────────────────────────────────────
    # kaynak: satır 771–772
    # "Kürtçe-atla = kasıtlı, Kontrol DEĞİL"
    if asr_status not in ASR_OK_SET:
        reasons.append(f"ASR={asr_status}")

    # ── Kural 3: PDF varlığı ────────────────────────────────────────────────
    # kaynak: satır 773–774
    if not pdf_path:
        reasons.append("PDF render yok (md teslim)")

    # ── Kural B-4: XML↔PDF cast kesişimi ───────────────────────────────────
    # kaynak: satır 775–788
    if xml_pdf_cast_overlap_zero:
        reasons.append("XML-PDF cast kesişimi 0 (yanlış-film şüphesi)")

    # ── Kural B-4 bonus: KB cross-check ────────────────────────────────────
    # kaynak: satır 789–806
    if kimlik_celiskisi:
        reasons.append("kimlik çelişkisi (KB cross-check)")

    # ── qwen final-QC kapısı ────────────────────────────────────────────────
    # kaynak: satır 811–821
    # qwen_qc None veya {"error":...} → ATLA (pipeline: "ollama yok/hata → atla, kapıyı BOZMA")
    if qwen_qc and not qwen_qc.get("error"):
        if not qwen_qc.get("ozet_var"):
            reasons.append("qwen: özet yok/placeholder")
        if (qwen_qc.get("oyuncu_sayisi") or 0) < 1:
            reasons.append("qwen: oyuncu yok")
        if not qwen_qc.get("yonetmen_var") and not qwen_qc.get("yapimci_var"):
            reasons.append("qwen: yön+yapımcı yok")
        if not qwen_qc.get("ses_dil_var"):
            reasons.append("qwen: ses/dil yok")
        if qwen_qc.get("turkce_karakter_bozuk_var"):
            reasons.append("qwen: Türkçe karakter bozuk")
        # NOT: afis_var + hepsi_buyuk_harf → SADECE uyarı, reasons'a EKLENMIYOR
        # kaynak: satır 822–826

    # ── Final karar ─────────────────────────────────────────────────────────
    # kaynak: satır 827
    karar = "Hazır" if not reasons else "Kontrol"
    return karar, reasons


# ===========================================================================
# INVARIANT (a): "ATLANDI" veya "skipped_unsupported_lang" → Kontrol'e DÜŞMEZ
# kaynak: satır 771 — "Kürtçe-atla = kasıtlı, Kontrol DEĞİL"
# ===========================================================================

class TestASRAtlanaWhitelist:
    """asr_status whitelist'inin Kontrol tetiklememesi."""

    def test_atlandi_tek_basina_kontrol_degil(self):
        """--no-asr veya Türkçe olmayan dil atlandığında ATLANDI durumu Hazır'ı bozmamalı."""
        karar, reasons = _karar("GUVENILIR", "ATLANDI", "/tmp/k.pdf")
        assert karar == "Hazır", f"ATLANDI Kontrol'e düşürdü — reasons: {reasons}"
        assert not any("ASR" in r for r in reasons)

    def test_skipped_unsupported_lang_kontrol_degil(self):
        """Kürtçe (ku) veya desteklenmeyen dil → skipped_unsupported_lang Hazır'ı bozmamalı."""
        karar, reasons = _karar("GUVENILIR", "skipped_unsupported_lang", "/tmp/k.pdf")
        assert karar == "Hazır", f"skipped_unsupported_lang Kontrol'e düşürdü — reasons: {reasons}"
        assert not any("ASR" in r for r in reasons)

    def test_done_hazir(self):
        """Normal başarılı ASR 'done' → Hazır."""
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf")
        assert karar == "Hazır"

    def test_atlandi_diger_sorunla_kontrol(self):
        """ATLANDI ama başka sorun varsa (PDF yok) → Kontrol, reason'da ASR yok."""
        karar, reasons = _karar("GUVENILIR", "ATLANDI", None)
        assert karar == "Kontrol"
        assert not any("ASR" in r for r in reasons), "ATLANDI kendi başına neden olmamalı"
        assert any("PDF" in r for r in reasons)


# ===========================================================================
# INVARIANT (b): ocr_bucket "GUVENILIR" değilse → Kontrol
# kaynak: satır 769–770
# ===========================================================================

class TestOCRBucketKontrol:
    """OCR bucket 'GUVENILIR' dışı → Kontrol."""

    @pytest.mark.parametrize("bucket", [
        "ZAYIF", "HATA", "ATLANDI", "BELIRSIZ", "DUSUK", "", "unknown",
    ])
    def test_guvenilir_olmayan_bucket_kontrol(self, bucket):
        karar, reasons = _karar(bucket, "done", "/tmp/k.pdf")
        assert karar == "Kontrol", f"bucket={bucket!r} Hazır döndürdü"
        assert any("OCR bucket" in r for r in reasons)

    def test_guvenilir_bucket_hazir(self):
        karar, _ = _karar("GUVENILIR", "done", "/tmp/k.pdf")
        assert karar == "Hazır"

    def test_ocr_atlandi_default_kontrol(self):
        """--no-ocr → ocr_bucket='ATLANDI' (satır 474) → Kontrol."""
        # kaynak: satır 474 (varsayılan değer) + satır 769
        karar, reasons = _karar("ATLANDI", "done", "/tmp/k.pdf")
        assert karar == "Kontrol"
        assert any("OCR bucket=ATLANDI" in r for r in reasons)


# ===========================================================================
# INVARIANT (c): pdf_path yok → Kontrol
# kaynak: satır 773–774
# ===========================================================================

class TestPDFYokKontrol:
    """pdf_path falsy → Kontrol."""

    @pytest.mark.parametrize("pdf_path", [None, ""])
    def test_pdf_yok_kontrol(self, pdf_path):
        # pipeline: `not pdf_info.get("pdf_path")` → None ve "" falsy → Kontrol
        # "  " (boşluk) truthy olduğu için bu set'e dahil değil
        karar, reasons = _karar("GUVENILIR", "done", pdf_path or None)
        assert karar == "Kontrol"
        assert any("PDF render yok" in r for r in reasons)

    def test_pdf_var_hazir(self):
        karar, _ = _karar("GUVENILIR", "done", "/output/film/kunye.pdf")
        assert karar == "Hazır"


# ===========================================================================
# INVARIANT (d): Tüm bloklar temiz → Hazır
# kaynak: satır 827
# ===========================================================================

class TestHepsiTemizHazir:
    """ocr=GUVENILIR + asr=done + pdf var → Hazır."""

    def test_minimal_hazir(self):
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf")
        assert karar == "Hazır"
        assert reasons == []

    def test_minimal_hazir_atlandi_asr(self):
        """--no-asr → ATLANDI, OCR temiz, PDF var → Hazır."""
        karar, reasons = _karar("GUVENILIR", "ATLANDI", "/tmp/k.pdf")
        assert karar == "Hazır"
        assert reasons == []

    def test_minimal_hazir_kurtce_atlandi(self):
        """Kürtçe atla → skipped_unsupported_lang, OCR temiz, PDF var → Hazır."""
        karar, reasons = _karar("GUVENILIR", "skipped_unsupported_lang", "/tmp/k.pdf")
        assert karar == "Hazır"
        assert reasons == []

    def test_qwen_none_bozmuyor(self):
        """qwen_qc=None (ollama yok) → kapı atlanır, Hazır bozulmaz."""
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=None)
        assert karar == "Hazır"
        assert reasons == []

    def test_qwen_error_bozmuyor(self):
        """qwen_qc={"error": "..."} → kapı atlanır, Hazır bozulmaz."""
        karar, reasons = _karar(
            "GUVENILIR", "done", "/tmp/k.pdf",
            qwen_qc={"error": "ConnectionRefusedError: ollama"}
        )
        assert karar == "Hazır"
        assert reasons == []


# ===========================================================================
# Bonus: qwen kapısı (kaynak: satır 811–821)
# ===========================================================================

class TestQwenKapisi:
    """qwen-QC sinyalleri doğru tetiklemeli."""

    _base_ok = {"ozet_var": True, "oyuncu_sayisi": 3, "yonetmen_var": True,
                "yapimci_var": True, "ses_dil_var": True,
                "turkce_karakter_bozuk_var": False,
                "afis_var": True, "hepsi_buyuk_harf": True}

    def test_qwen_temiz_hazir(self):
        karar, _ = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=self._base_ok)
        assert karar == "Hazır"

    def test_qwen_ozet_yok_kontrol(self):
        qc = {**self._base_ok, "ozet_var": False}
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=qc)
        assert karar == "Kontrol"
        assert any("özet yok" in r for r in reasons)

    def test_qwen_oyuncu_yok_kontrol(self):
        qc = {**self._base_ok, "oyuncu_sayisi": 0}
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=qc)
        assert karar == "Kontrol"
        assert any("oyuncu yok" in r for r in reasons)

    def test_qwen_yon_yapimci_ikisi_de_yok_kontrol(self):
        qc = {**self._base_ok, "yonetmen_var": False, "yapimci_var": False}
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=qc)
        assert karar == "Kontrol"
        assert any("yön+yapımcı yok" in r for r in reasons)

    def test_qwen_yon_var_yapimci_yok_hazir(self):
        """Sadece biri (yönetmen) varsa → kural geçilir, Kontrol tetiklemez."""
        qc = {**self._base_ok, "yapimci_var": False, "yonetmen_var": True}
        karar, _ = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=qc)
        assert karar == "Hazır"

    def test_qwen_ses_dil_yok_kontrol(self):
        qc = {**self._base_ok, "ses_dil_var": False}
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=qc)
        assert karar == "Kontrol"
        assert any("ses/dil yok" in r for r in reasons)

    def test_qwen_turkce_karakter_bozuk_kontrol(self):
        qc = {**self._base_ok, "turkce_karakter_bozuk_var": True}
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=qc)
        assert karar == "Kontrol"
        assert any("Türkçe karakter bozuk" in r for r in reasons)

    def test_qwen_afis_yok_sadece_uyari_bozmuyor(self):
        """afiş yok → sadece uyarı (reasons'a EKLENMİYOR) — kaynak: satır 822–824."""
        qc = {**self._base_ok, "afis_var": False}
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=qc)
        assert karar == "Hazır", "afiş sinyali kırılgan → Kontrol tetiklememeli"
        assert not any("afiş" in r for r in reasons)

    def test_qwen_kucuk_harf_sadece_uyari_bozmuyor(self):
        """büyük-harf değil → sadece uyarı — kaynak: satır 825–826."""
        qc = {**self._base_ok, "hepsi_buyuk_harf": False}
        karar, reasons = _karar("GUVENILIR", "done", "/tmp/k.pdf", qwen_qc=qc)
        assert karar == "Hazır", "büyük-harf sinyali kırılgan → Kontrol tetiklememeli"
        assert not any("büyük-harf" in r.lower() for r in reasons)


# ===========================================================================
# Bonus: ASR başarısız durumlar → Kontrol
# ===========================================================================

class TestASRBasarisizKontrol:
    """Whitelist dışı ASR durumları Kontrol'e düşmeli."""

    @pytest.mark.parametrize("asr_status", [
        "failed", "partial", "timeout", "error", "", "unknown",
    ])
    def test_basarisiz_asr_kontrol(self, asr_status):
        karar, reasons = _karar("GUVENILIR", asr_status, "/tmp/k.pdf")
        assert karar == "Kontrol"
        assert any("ASR=" in r for r in reasons)


# ===========================================================================
# Bonus: Çoklu sorun → hepsi reasons'ta görünmeli
# ===========================================================================

class TestCokluSorun:
    """Birden fazla sorun varsa hepsi reasons'ta yer almalı."""

    def test_ocr_asr_pdf_uc_sorun(self):
        karar, reasons = _karar("ZAYIF", "failed", None)
        assert karar == "Kontrol"
        assert any("OCR bucket" in r for r in reasons)
        assert any("ASR=" in r for r in reasons)
        assert any("PDF render yok" in r for r in reasons)
        assert len(reasons) == 3

    def test_cast_kesisimi_sifir_kontrol(self):
        karar, reasons = _karar(
            "GUVENILIR", "done", "/tmp/k.pdf",
            xml_pdf_cast_overlap_zero=True
        )
        assert karar == "Kontrol"
        assert any("cast kesişimi 0" in r for r in reasons)

    def test_kimlik_celiskisi_kontrol(self):
        karar, reasons = _karar(
            "GUVENILIR", "done", "/tmp/k.pdf",
            kimlik_celiskisi=True
        )
        assert karar == "Kontrol"
        assert any("kimlik çelişkisi" in r for r in reasons)
