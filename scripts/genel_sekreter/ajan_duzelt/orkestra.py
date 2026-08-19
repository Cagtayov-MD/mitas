"""Orkestra — mevcut QC altyapısını kullanarak ONAYLI filmleri düzelt.

Sıfırdan ekip yazmaz. Mevcut araçları tetikler:
  - credit_kb_lookup.py → yönetmen/yapımcı/tür/afiş lookup
  - credit_validate.py → çapraz doğrulama
  - translit_util.py → Latin transliterasyon
  - apply_qc_fixes.py → düzeltme uygula + PDF re-render
  - _ozet_kalite.py → özet kalite kontrolü

Akış:
  1. ONAYLI QC sonuçlarını al (ajan_qc_dogrulama)
  2. Her şüpheli film için correction data üret
  3. apply_qc_fixes.py'ye ver → o uygular + PDF re-render eder

Prensip: %100 güvenli olmayan düzeltme YAPILMAZ.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from genel_sekreter.config import DB, PROJE_KOKU
from genel_sekreter.ajan_qc_dogrulama import spot_check

_SCRIPTS = PROJE_KOKU / "scripts"


def _film_dir_bul(trt_id: str, film_ad: str) -> Path | None:
    """TRT ID veya film adıyla Database dizinini bul."""
    if not DB.is_dir():
        return None
    for d in DB.iterdir():
        if not d.is_dir():
            continue
        if trt_id and trt_id in d.name:
            return d
        if film_ad and film_ad.upper() in d.name.upper():
            return d
    return None


def _kb_lookup_calistir(film_dir: Path, title: str, trt_id: str, yonetmen: str = "") -> dict | None:
    """credit_kb_lookup.py'yi çağır → {yonetmen, yapimci, tur, afis, imdb_id}."""
    try:
        sys.path.insert(0, str(_SCRIPTS))
        from credit_kb_lookup import lookup_single

        yil = trt_id[:4] if trt_id and len(trt_id) >= 4 else ""
        sonuc = lookup_single(
            title=title,
            year=yil,
            yonetmen=yonetmen,
        )
        return sonuc
    except Exception as e:
        return {"hata": str(e)}
    finally:
        if str(_SCRIPTS) in sys.path:
            sys.path.remove(str(_SCRIPTS))


def _translit_duzelt(film_dir: Path) -> dict:
    """translit_util.py ile Latin-dışı karakter düzeltmesi."""
    try:
        sys.path.insert(0, str(_SCRIPTS))
        from translit_util import transliterate_mixed, detect_script

        # Künye dosyalarını tara
        for pattern in ("*kunye*.txt",):
            for kf in film_dir.glob(pattern):
                text = kf.read_text(encoding="utf-8", errors="replace")
                bulgular = []
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    script = detect_script(line)
                    if script != "latin":
                        latin, method = transliterate_mixed(line)
                        if method and "FAILED" not in str(method):
                            bulgular.append({"orijinal": line, "latin": latin, "method": str(method)})
                if bulgular:
                    return {"bulgular": bulgular, "dosya": str(kf.name)}
        return {"bulgular": []}
    except ImportError:
        return {"hata": "translit_util yüklenemedi"}
    finally:
        if str(_SCRIPTS) in sys.path:
            sys.path.remove(str(_SCRIPTS))


def correction_uret(film_bulgu: dict) -> dict | None:
    """Tek film için correction data üret (apply_qc_fixes.py formatı).

    Returns:
        {
            "trt_id": str,
            "db_folder": str,
            "corrections": {
                "yonetmen": str | None,
                "yapimci": str | None,
                "ozet": str | None,
                "tur": str | None,
            },
            "guven": float,
            "kaynaklar": [str],
        }
    """
    trt_id = film_bulgu.get("trt_id", "")
    film_ad = film_bulgu.get("title", film_bulgu.get("film", ""))
    sorunlar = film_bulgu.get("sorunlar", [])

    film_dir = _film_dir_bul(trt_id, film_ad)
    if film_dir is None:
        return None

    corrections = {}
    kaynaklar = []
    guven = 1.0

    # Mevcut _DURUM.json'u oku
    dp = film_dir / "_DURUM.json"
    durum = {}
    if dp.is_file():
        try:
            durum = json.loads(dp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    title = durum.get("title", film_ad)
    trt_id = durum.get("trt_id", trt_id)

    # Sorun türlerine göre düzeltme üret
    sorun_metin = " ".join(sorunlar).lower()

    # ── Yönetmen / Yapımcı / Tür / Afiş ──────────────────────────
    kb_ihtiyac = any(k in sorun_metin for k in ("yönetmen", "yapımcı", "afiş", "tür"))
    if kb_ihtiyac:
        mevcut_yon = ""
        # Mevcut yönetmen bilgisini bul
        for f in film_dir.glob("*kunye*.txt"):
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
                for line in txt.splitlines():
                    if "yönetmen" in line.lower() or "director" in line.lower():
                        mevcut_yon = line.split(":", 1)[-1].strip() if ":" in line else ""
                        break
            except OSError:
                pass

        kb = _kb_lookup_calistir(film_dir, title, trt_id, mevcut_yon)
        if kb and not kb.get("hata"):
            if "yönetmen" in sorun_metin and kb.get("otoriter_yonetmen"):
                yon_list = kb["otoriter_yonetmen"]
                if isinstance(yon_list, list) and yon_list:
                    corrections["yonetmen"] = yon_list[0]
                    kaynaklar.append(f"KB yonetmen: {yon_list[0]}")

            if "yapımcı" in sorun_metin and kb.get("yapimci"):
                yap_list = kb["yapimci"]
                if isinstance(yap_list, list) and yap_list:
                    corrections["yapimci"] = yap_list[0]
                    kaynaklar.append(f"KB yapimci: {yap_list[0]}")

            if "tür" in sorun_metin and kb.get("tur"):
                corrections["tur"] = kb["tur"]
                kaynaklar.append(f"KB tur: {kb['tur']}")

    # ── Latin transliterasyon ────────────────────────────────────
    if "latin" in sorun_metin:
        translit = _translit_duzelt(film_dir)
        if translit.get("bulgular"):
            kaynaklar.append(f"translit: {len(translit['bulgular'])} satır düzeltildi")
            # Latin düzeltmesi doğrudan uygulanır (correction değil, dosya düzeltmesi)

    if not corrections and not kaynaklar:
        return None

    return {
        "trt_id": trt_id,
        "title": title,
        "db_folder": str(film_dir),
        "corrections": corrections,
        "guven": guven,
        "kaynaklar": kaynaklar,
        "sorunlar": sorunlar,
    }


def calistir(dry_run: bool = True, orneklem_pct: int = 100) -> dict:
    """Tüm şüpheli ONAYLI filmler için correction üret.

    Args:
        dry_run: True = sadece rapor, apply_qc_fixes çağırmaz
        orneklem_pct: ONAYLI filmlerin yüzde kaçını kontrol et

    Returns:
        {
            "toplam_sorunlu": int,
            "correction_uretilen": int,
            "atlanamayan": int,
            "corrections": [...],
            "dry_run": bool,
        }
    """
    qc = spot_check(orneklem_pct=orneklem_pct)
    sorunlu_filmler = qc.get("bulgular", [])

    corrections = []
    atlanan = 0

    for film_bulgu in sorunlu_filmler:
        corr = correction_uret(film_bulgu)
        if corr:
            corrections.append(corr)
        else:
            atlanan += 1

    # YIL DOĞRULAMA KAPISI (hard-gate): IMDb yılı TRT yılıyla eşleşmeli.
    # Eşleşmezse → ATLA (yanlış film eşleşmesi riski).
    if yil and imdb_yil and str(imdb_yil) != yil:
        return {
            "film": title, "trt_id": trt_id,
            "durum": "YIL_UYUMSUZ",
            "neden": f"TRT yıl={yil}, IMDb yıl={imdb_yil} — farklı film",
            "guven": 0.0,
        }
        "toplam_sorunlu": len(sorunlu_filmler),
        "correction_uretilen": len(corrections),
        "atlanamayan": atlanan,
        "corrections": corrections,
        "dry_run": dry_run,
    }

    if not dry_run and corrections:
        # apply_qc_fixes.py'yi çağır
        sonuc["apply_sonuc"] = _apply_fixes(corrections)

    return sonuc


def _apply_fixes(corrections: list[dict]) -> dict:
    """apply_qc_fixes.py'yi correction data ile çağır."""
    import subprocess

    # Correction data'yı geçici JSON dosyasına yaz
    tmp_file = PROJE_KOKU / "outputs" / "gs_corrections.json"
    tmp_file.write_text(
        json.dumps(corrections, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        result = subprocess.run(
            [
                str(PROJE_KOKU / "venvs" / "asr" / "bin" / "python"),
                str(_SCRIPTS / "apply_qc_fixes.py"),
                "--corrections", str(tmp_file),
                "--apply",
            ],
            capture_output=True, text=True, timeout=600,
        )
        return {
            "rc": result.returncode,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:500],
        }
    except Exception as e:
        return {"hata": str(e)}


def rapor_duzelt(sonuc: dict | None = None) -> str:
    """Düzeltme raporu üret (Markdown)."""
    if sonuc is None:
        sonuc = calistir(dry_run=True)

    mod = "DRY RUN" if sonuc.get("dry_run", True) else "UYGULANDI"

    satirlar = [
        f"# Otomatik Düzeltme Raporu ({mod})",
        f"*{datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## Özet",
        "",
        f"- **Şüpheli film:** {sonuc['toplam_sorunlu']}",
        f"- **Correction üretilen:** {sonuc['correction_uretilen']}",
        f"- **Atlanan:** {sonuc['atlanamayan']}",
        "",
        "## Corrections",
        "",
    ]

    for c in sonuc.get("corrections", []):
        title = c.get("title", "?")
        trt_id = c.get("trt_id", "?")
        corr = c.get("corrections", {})
        kaynaklar = c.get("kaynaklar", [])

        satirlar.append(f"### {title} ({trt_id})")
        satirlar.append(f"**Sorunlar:** {', '.join(c.get('sorunlar', []))}")

        if corr:
            satirlar.append("**Düzeltmeler:**")
            for alan, deger in corr.items():
                satirlar.append(f"- `{alan}`: **{deger}**")

        if kaynaklar:
            satirlar.append("**Kaynaklar:**")
            for k in kaynaklar:
                satirlar.append(f"- {k}")
        satirlar.append("")

    return "\n".join(satirlar)
