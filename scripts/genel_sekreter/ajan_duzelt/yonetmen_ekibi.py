"""Yönetmen Ekibi — IMDb/Wikidata'dan yönetmen bul.

Mevcut altyapı:
  - credit_crosscheck.py: CreditKB sınıfı (Wikidata + IMDb DuckDB)
  - credit_kb_lookup.py: Tek film lookup
  - mitas.duckdb: imdb.principals (category='director'), works_master.director

Bu ekip:
  1. Film adını IMDb/Wikidata'da arar
  2. Yönetmen bilgisini bulur
  3. Çapraz doğrular (IMDb + Wikidata uyumlu mu?)
  4. Güven skoru hesaplar
  5. %95 üstü ise _DURUM.json'a yazar
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


def _duckdb_baglan():
    """mitas.duckdb'ye bağlan."""
    try:
        import duckdb
        db_path = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas")) / "Mitas_Files" / "MitaData" / "mitas.duckdb"
        if not db_path.is_file():
            # cache altındaki kopyayı dene
            db_path = Path(os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas")) / "cache" / "duckdb" / "mitas.duckdb"
        if not db_path.is_file():
            return None
        return duckdb.connect(str(db_path), read_only=True)
    except ImportError:
        return None


def _imdb_yonetmen_ara(conn, title: str, year: str = "") -> list[dict]:
    """IMDb principals tablosundan yönetmen ara."""
    try:
        # Önce tconst bul
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

        yonetmenler = []
        for tconst, ptitle, syear in results:
            # principals'dan director kategorisi
            dirs = conn.execute("""
                SELECT n.primaryName
                FROM imdb_principals p
                JOIN imdb_names n ON p.nconst = n.nconst
                WHERE p.tconst = ? AND p.category = 'director'
                ORDER BY p.ordering
                LIMIT 3
            """, [tconst]).fetchall()

            for (dname,) in dirs:
                yonetmenler.append({
                    "yonetmen": dname,
                    "imdb_title": ptitle,
                    "imdb_year": str(syear) if syear else "",
                    "tconst": tconst,
                    "kaynak": "IMDb",
                })
        return yonetmenler
    except Exception:
        return []


def _wikidata_yonetmen_ara(conn, title: str) -> list[dict]:
    """Wikidata works_master'dan yönetmen ara."""
    try:
        results = conn.execute("""
            SELECT label_tr, label_en, director, publication_year
            FROM works_master
            WHERE LOWER(label_tr) LIKE ? OR LOWER(label_en) LIKE ?
            LIMIT 5
        """, [f"%{title.lower()}%", f"%{title.lower()}%"]).fetchall()

        yonetmenler = []
        for label_tr, label_en, director, pub_year in results:
            if director:
                for d in director.split("|")[:3]:
                    yonetmenler.append({
                        "yonetmen": d.strip(),
                        "wd_title": label_tr or label_en,
                        "wd_year": str(pub_year) if pub_year else "",
                        "kaynak": "Wikidata",
                    })
        return yonetmenler
    except Exception:
        return []


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


def _name_fold(s: str) -> str:
    """Turkish-aware casefold for name matching."""
    import unicodedata
    s = s.replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ç", "c").replace("ö", "o").replace("ü", "u")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def duzelt(film_dir: Path, dry_run: bool = True) -> dict:
    """Tek film için yönetmen düzeltmesi."""
    durum = _durum_oku(film_dir)
    if durum is None:
        return {"film": film_dir.name, "durum": "HATA", "neden": "_DURUM.json okunamadı"}

    title = durum.get("title", "?")
    trt_id = durum.get("trt_id", "?")
    yil = trt_id[:4] if trt_id and len(trt_id) >= 4 else ""

    conn = _duckdb_baglan()
    if conn is None:
        return {"film": title, "trt_id": trt_id, "durum": "HATA", "neden": "DuckDB bağlantısı yok"}

    imdb_sonuc = _imdb_yonetmen_ara(conn, title, yil)
    wd_sonuc = _wikidata_yonetmen_ara(conn, title)
    conn.close()

    if not imdb_sonuc and not wd_sonuc:
        return {"film": title, "trt_id": trt_id, "durum": "BULUNAMADI", "adaylar": []}

    # Çapraz doğrulama: IMDb + Wikidata aynı ismi söylüyor mu?
    imdb_adlar = {_name_fold(d["yonetmen"]) for d in imdb_sonuc}
    wd_adlar = {_name_fold(d["yonetmen"]) for d in wd_sonuc}
    ortak = imdb_adlar & wd_adlar

    adaylar = imdb_sonuc + wd_sonuc
    guven = 0.0

    if ortak:
        # Her iki kaynak da anlaşıyor → yüksek güven
        en_iyi = [d for d in adaylar if _name_fold(d["yonetmen"]) in ortak][0]
        guven = 0.95
    elif imdb_sonuc:
        en_iyi = imdb_sonuc[0]
        guven = 0.75
    else:
        en_iyi = wd_sonuc[0]
        guven = 0.65

    # Yıl eşleşmesi bonusu
    if yil and en_iyi.get("imdb_year") == yil:
        guven = min(guven + 0.05, 1.0)
    if yil and en_iyi.get("wd_year") == yil:
        guven = min(guven + 0.05, 1.0)

    sonuc = {
        "film": title, "trt_id": trt_id,
        "adaylar": adaylar[:5],
        "en_iyi": en_iyi,
        "guven": round(guven, 2),
        "capraz_dogrulama": bool(ortak),
    }

    if guven < 0.90:
        sonuc["durum"] = "GUVEN_DUSUK"
        return sonuc

    if dry_run:
        sonuc["durum"] = "DRY_RUN"
        return sonuc

    # Uygula
    qwen_qc = durum.get("qwen_qc", {})
    qwen_qc["yonetmen_var"] = True
    durum["qwen_qc"] = qwen_qc
    durum["yonetmen_duzeltilmis"] = en_iyi["yonetmen"]
    durum["yonetmen_kaynak"] = en_iyi["kaynak"]
    durum["yonetmen_guven"] = guven

    nedenler = durum.get("neden", [])
    durum["neden"] = [n for n in nedenler if "yönetmen" not in n.lower() or "okunamadı" not in n.lower()]

    durum.setdefault("duzeltmeler", []).append({
        "ekip": "yonetmen",
        "tarih": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "yonetmen": en_iyi["yonetmen"],
        "kaynak": en_iyi["kaynak"],
        "guven": guven,
    })

    if _durum_yaz(film_dir, durum):
        sonuc["durum"] = "DUZELTILDI"
    else:
        sonuc["durum"] = "HATA"

    return sonuc
