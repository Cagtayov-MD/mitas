"""Afiş Ekibi — TMDB'den poster bul ve künyeye ekle.

Mevcut altyapı:
  - credit_kb_lookup.py: TMDB API ile poster fetch
  - MITAS_TMDB env var: API key
  - Poster gate: identity verified olmalı (cast_overlap ≥ 3)

Bu ekip:
  1. Film adını TMDB'de arar
  2. Doğru eşleşmeyi bulur (yıl + başlık match)
  3. Poster URL'sini alır
  4. _DURUM.json'a afis_url ekler
  5. qwen_qc.afis_var = True yapar
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path

from genel_sekreter.config import PROJE_KOKU


def _tmdb_search(title: str, year: str = "") -> dict | None:
    """TMDB'de film ara."""
    api_key = os.environ.get("MITAS_TMDB", os.environ.get("TMDB_API_KEY", ""))
    if not api_key:
        return None
    try:
        query = urllib.parse.quote(title)
        url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}"
        if year:
            url += f"&year={year}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results", [])
        return results[0] if results else None
    except Exception:
        return None


def _tmdb_poster_url(tmdb_result: dict) -> str | None:
    """TMDB sonucundan poster URL'si çıkar."""
    poster_path = tmdb_result.get("poster_path")
    if poster_path:
        return f"https://image.tmdb.org/t/p/original{poster_path}"
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
    dp = film_dir / "_DURUM.json"
    tmp = dp.with_name(dp.name + ".tmp")
    try:
        tmp.write_text(json.dumps(durum, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(str(tmp), str(dp))
        return True
    except OSError:
        return False


def duzelt(film_dir: Path, dry_run: bool = True) -> dict:
    """Tek film için afiş düzeltmesi.

    Returns:
        {
            "film": str, "trt_id": str,
            "tmdb_match": {...} | None,
            "poster_url": str | None,
            "guven": float,  # 0.0 - 1.0
            "durum": "DUZELTILDI" | "BULUNAMADI" | "DRY_RUN" | "HATA",
        }
    """
    durum = _durum_oku(film_dir)
    if durum is None:
        return {"film": film_dir.name, "durum": "HATA", "neden": "_DURUM.json okunamadı"}

    title = durum.get("title", "?")
    trt_id = durum.get("trt_id", "?")
    yil = ""
    # TRT ID'den yıl çıkar (ilk 4 hane)
    if trt_id and len(trt_id) >= 4:
        yil = trt_id[:4]

    # TMDB ara
    tmdb = _tmdb_search(title, yil)
    if tmdb is None:
        # Yıl olmadan tekrar dene
        tmdb = _tmdb_search(title)

    if tmdb is None:
        return {
            "film": title, "trt_id": trt_id,
            "durum": "BULUNAMADI",
            "tmdb_match": None, "poster_url": None, "guven": 0.0,
        }

    poster_url = _tmdb_poster_url(tmdb)
    if not poster_url:
        return {
            "film": title, "trt_id": trt_id,
            "durum": "BULUNAMADI",
            "tmdb_match": tmdb, "poster_url": None, "guven": 0.0,
            "neden": "TMDB'de poster yok",
        }

    # Güven skoru: başlık eşleşmesi + yıl eşleşmesi
    tmdb_title = tmdb.get("title", "").upper()
    tmdb_yil = (tmdb.get("release_date") or "")[:4]
    guven = 0.5  # base
    if title.upper() in tmdb_title or tmdb_title in title.upper():
        guven += 0.3
    if yil and tmdb_yil == yil:
        guven += 0.2
    guven = min(guven, 1.0)

    sonuc = {
        "film": title,
        "trt_id": trt_id,
        "tmdb_match": {
            "title": tmdb.get("title"),
            "year": tmdb_yil,
            "overview": (tmdb.get("overview") or "")[:150],
            "vote_average": tmdb.get("vote_average"),
        },
        "poster_url": poster_url,
        "guven": round(guven, 2),
    }

    # %80 altı güven = atlama
    if guven < 0.80:
        sonuc["durum"] = "GUVEN_DUSUK"
        return sonuc

    if dry_run:
        sonuc["durum"] = "DRY_RUN"
        return sonuc

    # Uygula
    qwen_qc = durum.get("qwen_qc", {})
    qwen_qc["afis_var"] = True
    durum["qwen_qc"] = qwen_qc
    durum["afis_url"] = poster_url
    durum["afis_kaynak"] = "TMDB"
    durum["afis_guven"] = guven

    # Neden listesinden afiş nedenini kaldır
    nedenler = durum.get("neden", [])
    durum["neden"] = [n for n in nedenler if "afiş" not in n.lower() and "afis" not in n.lower()]

    durum.setdefault("duzeltmeler", []).append({
        "ekip": "afis",
        "tarih": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "tmdb": sonuc["tmdb_match"],
        "poster_url": poster_url,
        "guven": guven,
    })

    if _durum_yaz(film_dir, durum):
        sonuc["durum"] = "DUZELTILDI"
    else:
        sonuc["durum"] = "HATA"

    return sonuc
