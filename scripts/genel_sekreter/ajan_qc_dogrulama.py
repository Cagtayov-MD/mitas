"""QC Doğrulama Ajanı — ONAYLI false-positive avı.

KONTROL'e düşenler sistem tarafından net hatası bulunanlardır.
Ama sistem bir şey bulamayıp hatalı şekilde ONAYLI'ya düşenler olabilir.

Bu ajan:
  1. ONAYLI filmlerden rastgele örnekle
  2. İnternet kaynaklarıyla teyit et (TMDB, IMDb, Wikipedia)
  3. Sistem "temiz" dedi ama gerçekte hata var mı?

Salt-okur: dosyalara DOKUNMAZ.
"""
from __future__ import annotations

import json
import random
import urllib.request
from pathlib import Path

from genel_sekreter.config import DB, ONAYLI_DIR, load_gs_config


def _durum_oku(film_dir: Path) -> dict | None:
    durum_path = film_dir / "_DURUM.json"
    if not durum_path.is_file():
        return None
    try:
        return json.loads(durum_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _deterministik_kontrol(durum: dict) -> list[str]:
    """Model gerektirmeyen kalite kontrolleri."""
    sorunlar = []
    qc = durum.get("qwen_qc") or {}

    if not qc.get("yonetmen_var"):
        sorunlar.append("yönetmen YOK (qwen_qc)")
    if not qc.get("yapimci_var"):
        sorunlar.append("yapımcı YOK (qwen_qc)")
    if qc.get("oyuncu_sayisi", 0) < 2:
        sorunlar.append(f"cast çok az ({qc.get('oyuncu_sayisi', 0)} oyuncu)")
    if not qc.get("afis_var"):
        sorunlar.append("afiş YOK")
    if not qc.get("ozet_var"):
        sorunlar.append("özet YOK")
    if qc.get("turkce_karakter_bozuk_var"):
        sorunlar.append("Türkçe karakter bozuk")
    if qc.get("latin_disi_alfabe_var"):
        sorunlar.append("Latin-dışı alfabe sızıntısı")

    bucket = durum.get("ocr_bucket", "")
    if bucket == "HATA":
        sorunlar.append("OCR bucket=HATA")

    timings = durum.get("timings_sec") or {}
    toplam = timings.get("toplam", 0)
    if toplam > 1800:
        sorunlar.append(f"işlem süresi şüpheli uzun ({toplam/60:.0f} dk)")

    return sorunlar


def _tmdb_sorgula(title: str, yil: str = "") -> dict | None:
    """TMDB API ile film bilgisi sorgula (API key varsa)."""
    import os
    api_key = os.environ.get("TMDB_API_KEY", "")
    if not api_key:
        return None
    try:
        query = urllib.parse.quote(title)
        url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}"
        if yil:
            url += f"&year={yil}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results", [])
        if results:
            r = results[0]
            return {
                "title": r.get("title"),
                "original_title": r.get("original_title"),
                "release_date": r.get("release_date"),
                "overview": r.get("overview", "")[:200],
                "vote_average": r.get("vote_average"),
            }
    except Exception:
        pass
    return None


def _export_trt_ids(export_dir):
    """Export klasöründen TRT ID'lerini çıkar."""
    import re
    from pathlib import Path
    ids = set()
    if not export_dir.is_dir():
        return ids
    for f in export_dir.iterdir():
        m = re.search(r'(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)', f.name)
        if m:
            ids.add(m.group(1))
    return ids


def spot_check(orneklem_pct: int | None = None) -> dict:
    """ONAYLI filmlerden rastgele örnekle, denetle.

    Kaynak: Mitas Output/export/ONAYLI (gerçek teslim).
    """
    if not DB.is_dir():
        return {"toplam_onayli": 0, "incelenen": 0, "temiz": 0,
                "sorunlu": 0, "bulgular": []}

    onayli_ids = _export_trt_ids(ONAYLI_DIR)

    if orneklem_pct is None:
        cfg = load_gs_config()
        orneklem_pct = cfg.get("thresholds", {}).get("onayli_sample_pct", 10)

    onayli_filmler: list[tuple[str, dict]] = []
    for d in sorted(DB.iterdir()):
        if not d.is_dir():
            continue
        durum = _durum_oku(d)
        if durum is None:
            continue
        # Export ONAYLI klasöründeki filmleri al
        trt_id = durum.get("trt_id", "")
        if not trt_id or trt_id not in onayli_ids:
            continue
        onayli_filmler.append((d.name, durum))

    toplam = len(onayli_filmler)
    if toplam == 0:
        return {"toplam_onayli": 0, "incelenen": 0, "temiz": 0,
                "sorunlu": 0, "bulgular": []}

    n_ornek = max(1, int(toplam * orneklem_pct / 100))
    ornekler = random.sample(onayli_filmler, min(n_ornek, toplam))

    temiz = 0
    sorunlu = 0
    bulgular = []

    for film_ad, durum in ornekler:
        sorunlar = _deterministik_kontrol(durum)

        # TMDB teyit (opsiyonel)
        title = durum.get("title", "")
        tmdb = _tmdb_sorgula(title) if title else None
        if tmdb:
            # TMDB'de var ama bizim verilerde eksik mi?
            if not durum.get("qwen_qc", {}).get("yonetmen_var"):
                sorunlar.append(f"TMDB'de mevcut ama bizde yönetmen YOK")

        if sorunlar:
            sorunlu += 1
            bulgular.append({
                "film": film_ad,
                "title": title,
                "trt_id": durum.get("trt_id", "?"),
                "sorunlar": sorunlar,
                "tmdb": tmdb,
            })
        else:
            temiz += 1

    return {
        "toplam_onayli": toplam,
        "incelenen": len(ornekler),
        "temiz": temiz,
        "sorunlu": sorunlu,
        "orneklem_pct": orneklem_pct,
        "bulgular": bulgular,
    }


def rapor_onayli() -> str:
    """ONAYLI QC raporu üret (Markdown)."""
    sonuc = spot_check()
    satirlar = [
        "# ONAYLI QC Doğrulama Raporu",
        "",
        "## Özet",
        "",
        f"- **Toplam ONAYLI:** {sonuc['toplam_onayli']}",
        f"- **İncelenen (spot-check):** {sonuc['incelenen']} (%{sonuc.get('orneklem_pct', '?')})",
        f"- **Temiz:** {sonuc['temiz']}",
        f"- **Sorunlu (false-positive şüphesi):** {sonuc['sorunlu']}",
        "",
    ]

    if sonuc["bulgular"]:
        satirlar.append("## Şüpheli Filmler")
        satirlar.append("")
        for b in sonuc["bulgular"]:
            satirlar.append(f"### {b['title']} ({b['trt_id']})")
            for s in b["sorunlar"]:
                satirlar.append(f"- ⚠ {s}")
            if b.get("tmdb"):
                t = b["tmdb"]
                satirlar.append(f"- ℹ TMDB: {t.get('title', '?')} ({t.get('release_date', '?')})")
            satirlar.append("")
    else:
        satirlar.append("## Sonuç\n\n✅ İncelenen tüm filmler temiz.")

    return "\n".join(satirlar)
