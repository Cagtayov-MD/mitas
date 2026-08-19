"""Secretary — tüm ajan raporlarını birleştir, tek özet çıkar.

Hiçbir teknik karar vermez. Sadece raporları okuyup:
  - TOPLAM Bug / TODO / Risk / Karar / Sonraki adım
"""
from __future__ import annotations

from datetime import date

from genel_sekreter.config import load_gs_config
from genel_sekreter.ajan_kontrol import analiz_kontrol
from genel_sekreter.ajan_performans import olcum_performans
from genel_sekreter.ajan_qc_dogrulama import spot_check
from genel_sekreter.rapor import emit_rapor, gunluk_append
from genel_sekreter.model_router import call_model


_MIN_FILM_API = 5


def gunluk_rapor() -> str:
    """Birleşik günlük rapor (Markdown)."""
    bugun = date.today().isoformat()
    kontrol = analiz_kontrol()
    onayli = spot_check()
    performans = olcum_performans()

    toplam = kontrol.get("toplam_film", 0)
    n_kontrol = kontrol.get("toplam_kontrol", 0)
    n_onayli = toplam - n_kontrol

    satirlar = [
        f"# MITAS System Review — {bugun}",
        "",
        "## Özet",
        "",
        f"**{toplam} film** işlendi: "
        f"**{n_onayli} ONAYLI**, **{n_kontrol} KONTROL**.",
        "",
    ]

    # KONTROL durumu
    satirlar.append("## KONTROL Durumu")
    satirlar.append("")
    ns = kontrol.get("neden_siniflar", [])
    if ns:
        for i, n in enumerate(ns[:5]):
            satirlar.append(
                f"{i+1}. **{n['sinif']}** → {n['sayi']} film (%{n['yuzde']}) "
                f"— {n['modul']}"
            )
    else:
        satirlar.append("KONTROL film yok.")
    satirlar.append("")

    # Sistemik bulgular
    bulgular = kontrol.get("sistemik_bulgular", [])
    if bulgular:
        satirlar.append("### Sistemik Bulgular")
        satirlar.append("")
        for b in bulgular:
            satirlar.append(f"- {b}")
        satirlar.append("")

    # ONAYLI QC
    satirlar.append("## ONAYLI QC")
    satirlar.append("")
    satirlar.append(
        f"Spot-check: {onayli.get('incelenen', 0)} film incelendi, "
        f"**{onayli.get('sorunlu', 0)} şüpheli** (false-positive)."
    )
    if onayli.get("bulgular"):
        for b in onayli["bulgular"][:3]:
            satirlar.append(f"- ⚠ {b.get('title', b['film'])}: {', '.join(b['sorunlar'][:2])}")
    satirlar.append("")

    # Performans
    satirlar.append("## Performans")
    satirlar.append("")
    t = performans.get("timing_ozet", {})
    if t.get("film_sayisi", 0) > 0:
        satirlar.append(
            f"- **Film:** {t['film_sayisi']} | "
            f"**Ort:** {t.get('toplam_ort_dk', '?')} dk | "
            f"**Medyan:** {t.get('toplam_medyan_dk', '?')} dk | "
            f"**Toplam:** {t.get('toplam_saat', '?')} saat"
        )
    if performans.get("gpu"):
        g = performans["gpu"]
        satirlar.append(f"- **GPU:** %{g['vram_pct']} VRAM, %{g['gpu_util_pct']} util")
    satirlar.append(f"- **Disk:** {performans.get('disk_bos_gb', '?')} GB boş")

    kosucu = performans.get("kosucu")
    if kosucu:
        satirlar.append(
            f"- **Koşu:** [{kosucu.get('son_n', '?')}/{kosucu.get('son_toplam', '?')}] "
            f"{kosucu.get('son_film', '?')[:50]}"
        )

    if performans.get("uyarilar"):
        for u in performans["uyarilar"]:
            satirlar.append(f"- {u}")
    satirlar.append("")

    # AI Sentez (yeterli veri varsa)
    if toplam >= _MIN_FILM_API:
        sentez = _api_sentez(kontrol, onayli, performans)
        if sentez and not sentez.startswith("["):
            satirlar.append("## AI Sentez")
            satirlar.append("")
            satirlar.append(sentez)
            satirlar.append("")

    # Sonraki adımlar
    satirlar.append("## Sonraki Adımlar")
    satirlar.append("")
    if bulgular:
        satirlar.append(f"1. **En kritik:** {bulgular[0][:100]}")
    if onayli.get("sorunlu", 0) > 0:
        satirlar.append(f"2. **ONAYLI QC:** {onayli['sorunlu']} şüpheli film incelenmeli")
    satirlar.append("")

    return "\n".join(satirlar)


def _api_sentez(kontrol: dict, onayli: dict, performans: dict) -> str:
    """API model ile kısa yönetici özeti."""
    prompt = (
        "MITAS pipeline günlük özeti yaz. Türkçe. 3-4 cümle. "
        "Odak: en kritik sorun, performans trendi, önerilen aksiyon.\n\n"
        f"KONTROL: {kontrol.get('toplam_kontrol', 0)} film, "
        f"nedenler: {kontrol.get('neden_siniflar', [])[:3]}\n"
        f"ONAYLI: {onayli.get('temiz', 0)} temiz / {onayli.get('sorunlu', 0)} şüpheli\n"
        f"Disk: {performans.get('disk_bos_gb', '?')} GB\n"
        f"Timing: ort {performans.get('timing_ozet', {}).get('toplam_ort_dk', '?')} dk/film"
    )
    return call_model("gunluk_sentez", prompt)


def yaz_ve_ekle() -> str:
    """Günlük raporu dosyaya yaz ve GUNLUK.md'ye ekle."""
    rapor_md = gunluk_rapor()
    dosya = emit_rapor("gunluk_rapor", rapor_md)

    cfg = load_gs_config()
    if cfg.get("rapor", {}).get("gunluk_append", True):
        bugun = date.today().isoformat()
        # Kısa versiyon
        ozet = rapor_md.split("## AI Sentez")[0] if "## AI Sentez" in rapor_md else rapor_md[:2000]
        gunluk_append(f"{bugun} — Genel Sekreter Raporu", ozet)

    return str(dosya)
