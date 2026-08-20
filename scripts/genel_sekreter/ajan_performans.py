"""Performans Ajanı — sürekli ölçüm, darboğaz tespiti.

Her film: kaç dk sürüyor, hangi aşamada kaç dk harcıyor.
Ortalamalar, medyan, min/max, std sapma.
GPU/CPU/RAM/disk durumu.

Temel prensip: min sürede max çıktı.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev

from genel_sekreter.config import (
    DB, EVENTS_PATH, QUEUE_PATH, KOSUCU_LOG, PROJE_KOKU, load_gs_config,
)


def _disk_bilgisi() -> dict:
    try:
        usage = shutil.disk_usage(str(PROJE_KOKU))
        return {
            "toplam_gb": round(usage.total / 1e9, 1),
            "kullanilan_gb": round(usage.used / 1e9, 1),
            "bos_gb": round(usage.free / 1e9, 1),
            "kullanim_pct": round(usage.used / usage.total * 100, 1),
        }
    except OSError:
        return {"toplam_gb": 0, "kullanilan_gb": 0, "bos_gb": 0, "kullanim_pct": 0}


def _gpu_bilgisi() -> dict | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        parts = result.stdout.strip().split(",")
        if len(parts) >= 3:
            used, total, util = int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
            return {
                "vram_used_mb": used, "vram_total_mb": total,
                "vram_pct": round(used / total * 100, 1) if total else 0,
                "gpu_util_pct": util,
            }
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return None


def _timing_istatistikleri() -> dict:
    """_DURUM.json dosyalarından per-film ve per-aşama timing."""
    if not DB.is_dir():
        return {"film_sayisi": 0}

    toplamlar = []
    asamalar: dict[str, list[float]] = {}
    film_detay: list[dict] = []

    ASAMA_ADLARI = ("coz", "ocr", "asr", "video_kunye", "vl_fallback",
                    "pdf", "v4_final", "qwen_qc", "track_kunye")

    for d in DB.iterdir():
        durum_path = d / "_DURUM.json"
        if not d.is_dir() or not durum_path.is_file():
            continue
        try:
            j = json.loads(durum_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        t = j.get("timings_sec") or {}
        toplam = t.get("toplam")
        if toplam and toplam > 0:
            toplamlar.append(toplam)
            detay = {"film": j.get("title", d.name)[:40], "toplam_sn": toplam}
            for asama in ASAMA_ADLARI:
                val = t.get(asama)
                if val is not None:
                    asamalar.setdefault(asama, []).append(val)
                    detay[asama] = val
            film_detay.append(detay)

    if not toplamlar:
        return {"film_sayisi": 0}

    sonuc = {
        "film_sayisi": len(toplamlar),
        "toplam_ort_dk": round(mean(toplamlar) / 60, 1),
        "toplam_medyan_dk": round(median(toplamlar) / 60, 1),
        "toplam_min_dk": round(min(toplamlar) / 60, 1),
        "toplam_max_dk": round(max(toplamlar) / 60, 1),
        "toplam_stddev_dk": round(stdev(toplamlar) / 60, 1) if len(toplamlar) > 1 else 0,
        "toplam_saat": round(sum(toplamlar) / 3600, 1),
    }

    # Aşama kırılımı
    asama_ozet = {}
    for ad, degerler in asamalar.items():
        if degerler:
            asama_ozet[ad] = {
                "ort_sn": round(mean(degerler), 1),
                "medyan_sn": round(median(degerler), 1),
                "min_sn": round(min(degerler), 1),
                "max_sn": round(max(degerler), 1),
                "n": len(degerler),
            }
    sonuc["asamalar"] = asama_ozet

    # En yavaş 10 film
    film_detay.sort(key=lambda x: -x["toplam_sn"])
    sonuc["en_yavas_10"] = film_detay[:10]

    # Darboğaz adayları
    sonuc["darbogaz_adaylari"] = _darbogaz_bul(asama_ozet, sonuc)

    return sonuc


def _darbogaz_bul(asama_ozet: dict, toplam: dict) -> list[str]:
    """En çok zaman harcayan aşamaları tespit et."""
    adaylar = []
    ort_toplam = toplam.get("toplam_ort_dk", 0) * 60  # sn'ye çevir

    for ad, bilgi in sorted(asama_ozet.items(), key=lambda x: -x[1]["ort_sn"]):
        oran = round(bilgi["ort_sn"] / ort_toplam * 100, 1) if ort_toplam else 0
        if oran > 25:
            adaylar.append(
                f"**{ad}**: ort {bilgi['ort_sn']}sn (%{oran} toplam süre) "
                f"— en büyük darboğaz adayı"
            )
        if bilgi["max_sn"] > bilgi["medyan_sn"] * 5:
            adaylar.append(
                f"**{ad}**: max {bilgi['max_sn']}sn vs medyan {bilgi['medyan_sn']}sn "
                f"— aşırı sapma, bazı filmler çok yavaş"
            )
    return adaylar


def _event_istatistikleri() -> dict:
    if not EVENTS_PATH.is_file():
        return {"event_toplam": 0}
    try:
        lines = EVENTS_PATH.read_text(encoding="utf-8").strip().split("\n")
    except OSError:
        return {"event_toplam": 0}

    toplam = len(lines)
    en_son_ts = None
    for line in lines[-50:]:  # son 50 event
        try:
            evt = json.loads(line)
            ts = evt.get("ts", "")
            if ts > (en_son_ts or ""):
                en_son_ts = ts
        except json.JSONDecodeError:
            continue

    return {"event_toplam": toplam, "en_son_event_ts": en_son_ts}


def _queue_durumu() -> dict | None:
    if not QUEUE_PATH.is_file():
        return None
    try:
        q = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        items = q.get("items", [])
        from collections import Counter
        statuses = Counter(i.get("status") for i in items)
        return {
            "toplam": len(items), "durumlar": dict(statuses),
            "aktif": statuses.get("running", 0) > 0,
        }
    except (json.JSONDecodeError, OSError):
        return None


def _kosucu_ilerleme() -> dict | None:
    """kosucu.log'dan son ilerleme bilgisini çıkar."""
    if not KOSUCU_LOG.is_file():
        return None
    try:
        lines = KOSUCU_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    son_satir = ""
    islenen = 0
    atlanan = 0
    for line in lines:
        if line.startswith("--- ["):
            son_satir = line
            islenen += 1
        if line.startswith("ATLA"):
            atlanan += 1

    # "=== [N/TOPLAM]" pattern'inden son ilerlemeyi çıkar
    import re
    son_n = 0
    son_toplam = 0
    for line in reversed(lines):
        m = re.search(r'\[(\d+)/(\d+)\]', line)
        if m:
            son_n, son_toplam = int(m.group(1)), int(m.group(2))
            break

    return {
        "islenen": islenen,
        "atlanan": atlanan,
        "son_n": son_n,
        "son_toplam": son_toplam,
        "son_film": son_satir[:100] if son_satir else "?",
    }


def olcum_performans() -> dict:
    """Tüm performans metriklerini topla."""
    cfg = load_gs_config()
    disk = _disk_bilgisi()
    gpu = _gpu_bilgisi()
    timing = _timing_istatistikleri()
    events = _event_istatistikleri()
    queue = _queue_durumu()
    kosucu = _kosucu_ilerleme()

    sonuc = {
        "olcum_zamani": datetime.now(timezone.utc).isoformat(),
        "disk_bos_gb": disk["bos_gb"],
        "disk": disk,
        "gpu": gpu,
        "timing_ozet": timing,
        "event_toplam": events["event_toplam"],
        "events": events,
        "queue": queue,
        "kosucu": kosucu,
    }

    # Uyarılar
    uyari = []
    esik_disk = cfg.get("thresholds", {}).get("disk_warn_gb", 100)
    if disk["bos_gb"] < esik_disk:
        uyari.append(f"⚠ Disk düşük: {disk['bos_gb']} GB boş (eşik: {esik_disk} GB)")
    if gpu and gpu.get("vram_pct", 0) > cfg.get("thresholds", {}).get("gpu_vram_warn_pct", 85):
        uyari.append(f"⚠ GPU VRAM yüksek: %{gpu['vram_pct']}")
    sonuc["uyarilar"] = uyari

    return sonuc


def rapor_performans() -> str:
    """Performans raporu üret (Markdown)."""
    p = olcum_performans()
    satirlar = [
        "# Performans Denetimi",
        f"*Ölçüm: {p['olcum_zamani']}*",
        "",
        "## Disk",
        f"- **Boş:** {p['disk']['bos_gb']} GB (%{p['disk']['kullanim_pct']} dolu)",
        "",
    ]

    if p["gpu"]:
        g = p["gpu"]
        satirlar.extend([
            "## GPU",
            f"- **VRAM:** {g['vram_used_mb']} / {g['vram_total_mb']} MB (%{g['vram_pct']})",
            f"- **Utilization:** %{g['gpu_util_pct']}",
            "",
        ])

    t = p["timing_ozet"]
    if t.get("film_sayisi", 0) > 0:
        satirlar.extend([
            "## Timing (Sürekli Ölçüm)",
            "",
            f"- **Film sayısı:** {t['film_sayisi']}",
            f"- **Ortalama:** {t['toplam_ort_dk']} dk/film",
            f"- **Medyan:** {t['toplam_medyan_dk']} dk",
            f"- **Min / Max:** {t['toplam_min_dk']} / {t['toplam_max_dk']} dk",
            f"- **Std Sapma:** {t['toplam_stddev_dk']} dk",
            f"- **Toplam iş yükü:** {t['toplam_saat']} saat",
            "",
        ])

        if "asamalar" in t:
            satirlar.extend([
                "### Aşama Kırılımı",
                "",
                "| Aşama | Ort (sn) | Medyan | Min | Max | N |",
                "|-------|----------|--------|-----|-----|---|",
            ])
            for asama, b in sorted(t["asamalar"].items(), key=lambda x: -x[1]["ort_sn"]):
                satirlar.append(
                    f"| {asama} | {b['ort_sn']} | {b['medyan_sn']} | {b['min_sn']} | {b['max_sn']} | {b['n']} |"
                )
            satirlar.append("")

        if t.get("darbogaz_adaylari"):
            satirlar.append("### Darboğaz Adayları")
            satirlar.append("")
            for d in t["darbogaz_adaylari"]:
                satirlar.append(f"- {d}")
            satirlar.append("")

        if t.get("en_yavas_10"):
            satirlar.append("### En Yavaş 10 Film")
            satirlar.append("")
            for f in t["en_yavas_10"]:
                satirlar.append(f"- {f['film']}: {f['toplam_sn']:.0f}sn ({f['toplam_sn']/60:.1f} dk)")
            satirlar.append("")

    if p.get("kosucu"):
        k = p["kosucu"]
        satirlar.extend([
            "## Toplu Koşu İlerlemesi",
            f"- **İşlenen:** {k['islenen']} film",
            f"- **Atlanan:** {k['atlanan']}",
            f"- **Son:** [{k['son_n']}/{k['son_toplam']}] {k['son_film'][:60]}",
            "",
        ])

    if p.get("uyarilar"):
        satirlar.extend(["## Uyarılar", ""])
        for u in p["uyarilar"]:
            satirlar.append(f"- {u}")

    return "\n".join(satirlar)
