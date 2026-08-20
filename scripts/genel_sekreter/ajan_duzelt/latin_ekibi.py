"""Latin Ekibi — Non-Latin karakter transliterasyonu.

Mevcut altyapı: scripts/translit_util.py
  - detect_script(text) → latin|cyrillic|greek|arabic|han|hangul|other
  - transliterate(name, script) → (latin_text, method)
  - transliterate_mixed(s) → token-level transliteration
  - asciify_foreign(s) → foreign accented Latin → ASCII (Turkish chars preserved)

Bu ekip:
  1. Film künyesindeki non-Latin isimleri bulur
  2. translit_util ile Latin'e çevirir
  3. Sadece method != "FAILED" olanları uygular
  4. _DURUM.json'u günceller
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# MITAS scripts yolunu ekle
_SCRIPTS_DIR = Path(__file__).resolve().parents[3]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _translit_util_yukle():
    """translit_util modülünü güvenli yükle."""
    try:
        from translit_util import (
            detect_script, transliterate, transliterate_mixed,
            asciify_foreign, normalize_text,
        )
        return {
            "detect_script": detect_script,
            "transliterate": transliterate,
            "transliterate_mixed": transliterate_mixed,
            "asciify_foreign": asciify_foreign,
            "normalize_text": normalize_text,
        }
    except ImportError:
        return None


def _durum_oku(film_dir: Path) -> dict | None:
    dp = film_dir / "_DURUM.json"
    if not dp.is_file():
        return None
    try:
        return json.loads(dp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _durum_yaz(film_dir: Path, durum: dict) -> bool:
    """Atomic write: tmp + os.replace."""
    dp = film_dir / "_DURUM.json"
    tmp = dp.with_name(dp.name + ".tmp")
    try:
        tmp.write_text(json.dumps(durum, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(dp))
        return True
    except OSError:
        return False


def _nonlatin_isimler_bul(kunye_text: str, tu) -> list[dict]:
    """Künye metnindeki non-Latin isimleri bul."""
    bulgular = []
    for line in kunye_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        script = tu["detect_script"](line)
        if script != "latin":
            latin, method = tu["transliterate"](line, script)
            if method != "FAILED":
                bulgular.append({
                    "orijinal": line,
                    "latin": latin,
                    "method": method,
                    "script": script,
                })
    return bulgular


def duzelt(film_dir: Path, dry_run: bool = True) -> dict:
    """Tek film için Latin düzeltmesi.

    Returns:
        {
            "film": str,
            "trt_id": str,
            "bulgular": [...],
            "duzeltilen": int,
            "atlanamayan": int,
            "durum": "DUZELTILDI" | "ATLADI" | "HATA" | "KURU",
        }
    """
    durum = _durum_oku(film_dir)
    if durum is None:
        return {"film": film_dir.name, "durum": "HATA", "neden": "_DURUM.json okunamadı"}

    title = durum.get("title", "?")
    trt_id = durum.get("trt_id", "?")

    tu = _translit_util_yukle()
    if tu is None:
        return {"film": title, "trt_id": trt_id, "durum": "HATA", "neden": "translit_util yüklenemedi"}

    # Künye metnini oku
    kunye_dosyalari = list(film_dir.glob("*kunye*.txt"))
    if not kunye_dosyalari:
        return {"film": title, "trt_id": trt_id, "durum": "ATLADI", "neden": "künye dosyası yok"}

    kunye_text = kunye_dosyalari[0].read_text(encoding="utf-8", errors="replace")
    bulgular = _nonlatin_isimler_bul(kunye_text, tu)

    if not bulgular:
        return {"film": title, "trt_id": trt_id, "durum": "KURU", "bulgular": []}

    duzeltilen = sum(1 for b in bulgular if b["method"] != "FAILED")
    atlanan = len(bulgular) - duzeltilen

    sonuc = {
        "film": title,
        "trt_id": trt_id,
        "bulgular": bulgular,
        "duzeltilen": duzeltilen,
        "atlanamayan": atlanan,
    }

    if dry_run:
        sonuc["durum"] = "DRY_RUN"
        return sonuc

    # Uygula: qwen_qc'deki latin_disi_alfabe_var bayrağını temizle
    qwen_qc = durum.get("qwen_qc", {})
    if qwen_qc.get("latin_disi_alfabe_var"):
        qwen_qc["latin_disi_alfabe_var"] = False
        durum["qwen_qc"] = qwen_qc

    # Neden listesinden latin-dışı nedenini kaldır
    nedenler = durum.get("neden", [])
    durum["neden"] = [n for n in nedenler if "latin" not in n.lower() and "alfabe" not in n.lower()]

    # Düzeltme kaydı
    durum.setdefault("duzeltmeler", []).append({
        "ekip": "latin",
        "tarih": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "bulgular": bulgular,
    })

    if _durum_yaz(film_dir, durum):
        sonuc["durum"] = "DUZELTILDI"
    else:
        sonuc["durum"] = "HATA"
        sonuc["neden"] = "_DURUM.json yazılamadı"

    return sonuc
