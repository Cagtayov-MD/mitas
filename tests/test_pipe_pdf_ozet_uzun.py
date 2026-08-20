"""_pipe_pdf --ozet uzun-metin koruması — 2026-07-30 gece regresyonu.

Linux'ta Path(uzun_metin).exists() OSError(ENAMETOOLONG) fırlatır (Windows
sessizce False dönerdi); 393 karakterlik gerçek özetler 14 filmin PDF'ini
düşürdü. Bu test korumanın kaynakta durduğunu ve mantığın uzun metinde
dosya-yolu denemesi YAPMADIĞINI doğrular (asr-venv bağımlılıkları import
edilmeden, kaynak + saf mantık düzeyinde).
"""
from pathlib import Path

KAYNAK = Path("/opt/mitas/scripts/_pipe_pdf.py").read_text(encoding="utf-8")


def test_ozet_yol_denemesi_uzunluk_kapili():
    assert "ENAMETOOLONG" in KAYNAK or "except OSError" in KAYNAK
    assert '< 250' in KAYNAK and "_ozet_dosya" in KAYNAK


def test_uzun_ozet_dosya_sanilmaz():
    # kaynaktaki mantığın birebir kopyası uzun metinde False üretmeli
    ozet_metin = "Will Kane, emekli olup yeni evlendiği Amy ile kaçmayı reddeder " * 8
    try:
        dosya_mi = bool(ozet_metin) and len(ozet_metin.encode("utf-8", "ignore")) < 250 \
            and Path(ozet_metin).exists()
    except OSError:
        dosya_mi = False
    assert dosya_mi is False
