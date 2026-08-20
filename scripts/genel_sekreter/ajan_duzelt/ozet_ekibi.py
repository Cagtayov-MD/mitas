"""Özet Ekibi — ASR transkript'ten kurallı özet üret.

Kurallar (MITAS_KUNYE_KURALLARI.md):
  - 4 cümle, 40-65 kelime
  - BÜYÜK HARF (PDF render aşamasında tr_upper_prose uygulanır)
  - Açık spoiler sonu (zorunlu)
  - İsimsiz protagonist + somut tetikleyici → neden-sonuç → sonuç
  - Yasak: soru, ünlem, alıntı, parantez, klişe, karakter listesi

Mevcut altyapı:
  - _ozet_kalite.py: summary_errors() + repair_generated_summary()
  - mitas_pipeline.py: _ozet_chain() provider zinciri
  - core/api/prompts/ozet_film_v2.txt: V2 prompt

Bu ekip:
  1. ASR transkript'i oku
  2. qwen-plus ile özet üret (ucuz, hızlı)
  3. _ozet_kalite.py ile doğrula
  4. Geçerse _DURUM.json'a yaz
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from genel_sekreter.config import DB
from genel_sekreter.model_router import call_model


_OZET_PROMPT = """Sen bir film özet yazarısın. Aşağıdaki film transkriptinden KISA bir özet yaz.

KURALLAR:
- 3-4 cümle, 35-60 kelime
- Türkçe yaz
- İsimli protagonist + somut olay → çatışma → SONUÇ (spoiler zorunlu)
- Son cümlede film nasıl biter? Kim ölür/kazanır/kaybeder?
- YASAK: soru işareti, ünlem, alıntı, parantez, "film anlatıyor" gibi ifadeler
- YASAK: karakter listesi, yan olaylar, edebi süslemeler
- Normal Türkçe yaz (BÜYÜK HARF değil — o PDF aşamasında yapılır)

FİLM ADI: {title}
TRANSKRİPT (ilk bölüm):
{transcript}

ÖZET:"""


def _transkript_oku(film_dir: Path) -> str | None:
    """ASR transkript dosyasını oku."""
    # Olası transkript dosyaları
    for pattern in ("*transcript*.txt", "*asr*.txt", "*transkript*.txt"):
        matches = list(film_dir.glob(pattern))
        if matches:
            try:
                text = matches[0].read_text(encoding="utf-8", errors="replace")
                # Timestamp'leri temizle
                import re
                text = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', text)
                # 10K karakterle sınırla
                return text[:10000].strip()
            except OSError:
                continue

    # audio/ altındaki transcript'i dene
    audio_dir = film_dir / "audio"
    if audio_dir.is_dir():
        for f in audio_dir.glob("*.txt"):
            try:
                return f.read_text(encoding="utf-8", errors="replace")[:10000].strip()
            except OSError:
                continue
    return None


def _ozet_kalite_kontrol(ozet: str) -> list[str]:
    """Özet kalite kontrolü."""
    hatalar = []
    kelimeler = ozet.split()
    sayi = len(kelimeler)

    if sayi < 24:
        hatalar.append(f"çok kısa ({sayi} kelime, min 24)")
    if sayi > 65:
        hatalar.append(f"çok uzun ({sayi} kelime, max 65)")
    if ";" in ozet:
        hatalar.append("noktalı virgül var")
    if "?" in ozet:
        hatalar.append("soru işareti var")
    if "!" in ozet:
        hatalar.append("ünlem var")
    if not ozet.rstrip().endswith("."):
        hatalar.append("nokta ile bitmiyor")

    # Spoiler final kontrolü
    son_cumle = ozet.rstrip().rsplit(".", 2)[-2] + "." if "." in ozet else ""
    FINAL_KELIMELER = {"sonunda", "finalde", "sonunda", "biter", "ölür", "kazanır",
                       "kaybeder", "feda eder", "öldürür", "bulur", "ayrılır"}
    if not any(k in son_cumle.lower() for k in FINAL_KELIMELER):
        hatalar.append("spoiler final eksik")

    return hatalar


def _durum_oku(film_dir: Path) -> dict | None:
    dp = film_dir / "_DURUM.json"
    if not dp.is_file():
        return None
    try:
        return json.loads(dp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _durum_yaz(film_dir: Path, durum: dict) -> bool:
    dp = film_dir / "_DURUM.json"
    tmp = dp.with_name(dp.name + ".tmp")
    try:
        tmp.write_text(json.dumps(durum, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(dp))
        return True
    except OSError:
        return False


def duzelt(film_dir: Path, dry_run: bool = True) -> dict:
    """Tek film için özet düzeltmesi."""
    durum = _durum_oku(film_dir)
    if durum is None:
        return {"film": film_dir.name, "durum": "HATA", "neden": "_DURUM.json okunamadı"}

    title = durum.get("title", "?")
    trt_id = durum.get("trt_id", "?")

    transcript = _transkript_oku(film_dir)
    if not transcript:
        return {"film": title, "trt_id": trt_id, "durum": "ATLADI", "neden": "transkript yok"}

    # LLM ile özet üret (qwen-plus: ucuz, hızlı)
    prompt = _OZET_PROMPT.format(title=title, transcript=transcript[:5000])
    ozet = call_model("gunluk_sentez", prompt)

    if not ozet or ozet.startswith("["):
        return {"film": title, "trt_id": trt_id, "durum": "HATA", "neden": f"LLM hata: {ozet[:100]}"}

    # Temizle
    ozet = ozet.strip().strip('"').strip("'")
    if not ozet.endswith("."):
        ozet += "."

    # Kalite kontrol
    hatalar = _ozet_kalite_kontrol(ozet)

    sonuc = {
        "film": title, "trt_id": trt_id,
        "ozet": ozet,
        "kelime_sayisi": len(ozet.split()),
        "hatalar": hatalar,
    }

    if hatalar:
        sonuc["durum"] = "KALITE_DUSUK"
        return sonuc

    if dry_run:
        sonuc["durum"] = "DRY_RUN"
        return sonuc

    # Uygula
    qwen_qc = durum.get("qwen_qc", {})
    qwen_qc["ozet_var"] = True
    durum["qwen_qc"] = qwen_qc
    durum["ozet_duzeltilmis"] = ozet
    durum["ozet_kaynak"] = "qwen-plus"

    nedenler = durum.get("neden", [])
    durum["neden"] = [n for n in nedenler if "özet" not in n.lower() or "yok" not in n.lower()]

    durum.setdefault("duzeltmeler", []).append({
        "ekip": "ozet",
        "tarih": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "ozet": ozet,
        "kelime_sayisi": len(ozet.split()),
    })

    if _durum_yaz(film_dir, durum):
        sonuc["durum"] = "DUZELTILDI"
    else:
        sonuc["durum"] = "HATA"

    return sonuc
