"""Yapımcı Ekibi — IMDb/Wikidata'dan yapımcı bul.

Yönetmen ekibi ile aynı altyapıyı kullanır.
IMDb principals: category='producer'
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[3]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from genel_sekreter.ajan_duzelt.yonetmen_ekibi import (
    _duckdb_baglan, _durum_oku, _durum_yaz, _name_fold,
)


def _imdb_yapimci_ara(conn, title: str, year: str = "") -> list[dict]:
    """IMDb principals tablosundan yapımcı ara."""
    try:
        q = """
            SELECT t.tconst, t.primaryTitle, t.startYear
            FROM imdb_titles t
            WHERE LOWER(t.primaryTitle) LIKE ?
        """
        params = [f"%{title.lower()}%"]
        if year:
            q += " AND CAST(t.startYear AS VARCHAR) = ?"
            params.append(year)
        q += " LIMIT 5"

        results = conn.execute(q, params).fetchall()
        if not results:
            return []

        yapimcilar = []
        for tconst, ptitle, syear in results:
            prods = conn.execute("""
                SELECT n.primaryName
                FROM imdb_principals p
                JOIN imdb_names n ON p.nconst = n.nconst
                WHERE p.tconst = ? AND p.category = 'producer'
                ORDER BY p.ordering
                LIMIT 3
            """, [tconst]).fetchall()

            for (pname,) in prods:
                yapimcilar.append({
                    "yapimci": pname,
                    "imdb_title": ptitle,
                    "imdb_year": str(syear) if syear else "",
                    "kaynak": "IMDb",
                })
        return yapimcilar
    except Exception:
        return []


def duzelt(film_dir: Path, dry_run: bool = True) -> dict:
    """Tek film için yapımcı düzeltmesi."""
    durum = _durum_oku(film_dir)
    if durum is None:
        return {"film": film_dir.name, "durum": "HATA", "neden": "_DURUM.json okunamadı"}

    title = durum.get("title", "?")
    trt_id = durum.get("trt_id", "?")
    yil = trt_id[:4] if trt_id and len(trt_id) >= 4 else ""

    conn = _duckdb_baglan()
    if conn is None:
        return {"film": title, "trt_id": trt_id, "durum": "HATA", "neden": "DuckDB bağlantısı yok"}

    adaylar = _imdb_yapimci_ara(conn, title, yil)
    conn.close()

    if not adaylar:
        return {"film": title, "trt_id": trt_id, "durum": "BULUNAMADI", "adaylar": []}

    # İlk yapımcı = en güvenilir (ordering=1)
    en_iyi = adaylar[0]
    guven = 0.85  # IMDb producer ordering güvenilir
    if yil and en_iyi.get("imdb_year") == yil:
        guven = min(guven + 0.10, 1.0)

    sonuc = {
        "film": title, "trt_id": trt_id,
        "adaylar": adaylar[:5],
        "en_iyi": en_iyi,
        "guven": round(guven, 2),
    }

    if guven < 0.90:
        sonuc["durum"] = "GUVEN_DUSUK"
        return sonuc

    if dry_run:
        sonuc["durum"] = "DRY_RUN"
        return sonuc

    # Uygula
    qwen_qc = durum.get("qwen_qc", {})
    qwen_qc["yapimci_var"] = True
    durum["qwen_qc"] = qwen_qc
    durum["yapimci_duzeltilmis"] = en_iyi["yapimci"]
    durum["yapimci_kaynak"] = "IMDb"
    durum["yapimci_guven"] = guven

    nedenler = durum.get("neden", [])
    durum["neden"] = [n for n in nedenler if "yapımcı" not in n.lower() or "yok" not in n.lower()]

    durum.setdefault("duzeltmeler", []).append({
        "ekip": "yapimci",
        "tarih": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "yapimci": en_iyi["yapimci"],
        "kaynak": "IMDb",
        "guven": guven,
    })

    if _durum_yaz(film_dir, durum):
        sonuc["durum"] = "DUZELTILDI"
    else:
        sonuc["durum"] = "HATA"

    return sonuc
