"""
smoke_tier_sim.py
Tier-routing K1/K2/K3 kural simülasyonu — KOD DEĞİŞTİRMEZ, sadece ölçer.
En son 60 _DURUM.json hub'ı tarar, yeni kuralların etkisini raporlar.
"""

import sys
import io
import os
import json
import re
from pathlib import Path
from datetime import datetime

# UTF-8 çıktı zorla
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATABASE = Path(r"E:\MITAS\Database")
OUTPUT_MD = Path(r"E:\MITAS\outputs\SMOKE_TIER_20260613.md")

# Regresyon testi: bu filmler Hazır kalmalı (title içerme eşleştirmesi)
REGRESYON_FILMLER = {
    "HIRSIZ": "MICHAEL MANN",   # HIRSIZ (MICHAEL MANN)
    "SILVERADO": "SILVERADO",
    "TITUS_ANDRONICUS": "TITUS ANDRONICUS",
    "ZOR__L_M_2": "ZOR ÖLÜM 2",
}

# Beklenti: bu filmler Hazır ama bozuk yönetmenli — K1/K2 yakalamalı
BEKLENTI_FILMLER = {
    "FRANKIE_VE_JOHNNY": "FRANKIE VE JOHNNY",
    "SOKAK_MUHAB_R": "SOKAK MUHABİRİ",
    "_ILGIN_YA_AMIM": "ÇİLGİN YAŞAMIM",
    "VAH__AT": "VAHŞİ AT",
}

# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────

def load_md_lines(md_path: Path) -> list[str]:
    if not md_path.exists():
        return []
    try:
        return md_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

def find_section_value(lines: list[str], key: str) -> str | None:
    """'- Yönetmen: X' gibi satırı bulup değeri döndür."""
    pattern = re.compile(rf"^\s*-\s*{re.escape(key)}:\s*(.*)", re.IGNORECASE)
    for line in lines:
        m = pattern.match(line)
        if m:
            return m.group(1).strip()
    return None

def parse_yonetmen_list(raw: str) -> list[str]:
    """Virgülle ayır, boş/'—' elemanları at."""
    if not raw or raw.strip() == "—":
        return []
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p and p != "—"]

def apply_rules(yonetmen_list: list[str], ana_dil: str | None, altyazi: str | None) -> list[str]:
    """Tetiklenen kural adlarını döndür."""
    triggered = []

    # K1: yönetmen sayısı > 2
    if len(yonetmen_list) > 2:
        triggered.append(f"K1 (yönetmen sayısı={len(yonetmen_list)}>2)")

    # K2: herhangi bir eleman > 45 karakter
    for elem in yonetmen_list:
        if len(elem) > 45:
            triggered.append(f"K2 ('{elem[:50]}…' {len(elem)} kar)")
            break  # bir kere yeter

    # K3: ana_dil TR-dışı VE altyazı=HAYIR
    if ana_dil is not None:
        ana_dil_norm = ana_dil.strip().upper()
        altyazi_norm = (altyazi or "").strip().upper()
        if ana_dil_norm not in ("TR", "—", "") and altyazi_norm == "HAYIR":
            triggered.append(f"K3 (ana_dil={ana_dil_norm}, altyazı=HAYIR)")

    return triggered

# ── Ana tarama ─────────────────────────────────────────────────────────────

def main():
    # En son 60 _DURUM.json'u mtime'a göre al
    all_durum = sorted(
        DATABASE.rglob("*_DURUM.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:60]

    print(f"Taranan hub sayısı: {len(all_durum)}", flush=True)

    results = []
    for dpath in all_durum:
        hub_dir = dpath.parent
        try:
            data = json.loads(dpath.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  HATA {dpath}: {e}", flush=True)
            continue

        title = data.get("title", hub_dir.name)
        eski_karar = data.get("karar", "?")

        # MD yolunu belirle
        md_path_str = data.get("md", "")
        md_path = Path(md_path_str) if md_path_str else hub_dir / "pdf" / "kunye_teslim.md"

        lines = load_md_lines(md_path)

        yonetmen_raw = find_section_value(lines, "Yönetmen")
        ana_dil = find_section_value(lines, "Ana dil")
        altyazi = find_section_value(lines, "Altyazı")

        yonetmen_list = parse_yonetmen_list(yonetmen_raw or "")
        triggered = apply_rules(yonetmen_list, ana_dil, altyazi)

        yeni_karar = "Kontrol" if triggered else eski_karar

        # regresyon / beklenti etiket
        folder = hub_dir.name
        regresyon_label = None
        for key, label in REGRESYON_FILMLER.items():
            if key in folder:
                regresyon_label = label
                break
        beklenti_label = None
        for key, label in BEKLENTI_FILMLER.items():
            if key in folder:
                beklenti_label = label
                break

        results.append({
            "title": title,
            "folder": folder,
            "eski_karar": eski_karar,
            "yeni_karar": yeni_karar,
            "triggered": triggered,
            "yonetmen_raw": yonetmen_raw or "",
            "yonetmen_list": yonetmen_list,
            "ana_dil": ana_dil or "",
            "altyazi": altyazi or "",
            "md_path": str(md_path),
            "md_exists": md_path.exists(),
            "regresyon_label": regresyon_label,
            "beklenti_label": beklenti_label,
        })

    # ── Çıktı hesaplamaları ────────────────────────────────────────────────

    degisen = [r for r in results if r["eski_karar"] == "Hazır" and r["yeni_karar"] == "Kontrol"]
    zaten_kontrol_tetik = [r for r in results if r["eski_karar"] == "Kontrol" and r["triggered"]]
    etkilenmez = [r for r in results if not r["triggered"]]

    degisen_set = {r["title"] for r in degisen}
    tetik_set = {r["title"] for r in (degisen + zaten_kontrol_tetik)}

    regresyon_kontrol = [r for r in results if r["regresyon_label"]]
    beklenti_kontrol = [r for r in results if r["beklenti_label"]]

    k3_tetiklenenler = [r for r in results if any("K3" in t for t in r["triggered"])]

    # ── Rapor üret ────────────────────────────────────────────────────────

    lines_out = []
    a = lines_out.append

    a(f"# SMOKE TIER SİMÜLASYONU — {datetime.now():%Y-%m-%d %H:%M}")
    a(f"\nTaranan hub: **{len(results)}** · Tarih: 2026-06-13\n")
    a("---\n")

    # 1. Tablo: değişen veya kural-tetiklenen filmler
    a("## 1. Değişen / Kural Tetiklenen Filmler Tablosu\n")
    tablo_rows = [r for r in results if r["triggered"]]
    if tablo_rows:
        a("| Film | Eski Karar | Tetiklenen Kural(lar) | Yeni Karar |")
        a("|------|-----------|----------------------|-----------|")
        for r in tablo_rows:
            kurallar = "; ".join(r["triggered"])
            a(f"| {r['title']} | {r['eski_karar']} | {kurallar} | {r['yeni_karar']} |")
    else:
        a("*(Hiçbir film tetiklenmedi)*")
    a("")

    # 2. Karar değişen filmler (Hazır→Kontrol)
    a("## 2. Karar Değişen Filmler (Hazır → Kontrol)\n")
    a("Bu filmler yeni kuralların yakaladığı sızıntılardır.\n")
    if degisen:
        for r in degisen:
            a(f"- **{r['title']}** — {'; '.join(r['triggered'])}")
            a(f"  - Yönetmen satırı: `{r['yonetmen_raw']}`")
    else:
        a("*(Hiçbir Hazır film Kontrol'e düşmedi)*")
    a("")

    # 3. Regresyon kontrolü
    a("## 3. Regresyon Kontrolü\n")
    a("Aşağıdaki filmler **Hazır KALMALI** — eğer tetikleniyorsa false-positive demektir.\n")
    a("| Film | Yönetmen Satırı | Tetiklenen Kural | Yeni Karar | Sonuç |")
    a("|------|----------------|-----------------|-----------|-------|")
    for r in regresyon_kontrol:
        kural_str = "; ".join(r["triggered"]) if r["triggered"] else "—"
        sonuc = "⚠️ FALSE-POSITIVE" if r["triggered"] else "OK — Hazır"
        a(f"| {r['regresyon_label']} | `{r['yonetmen_raw']}` | {kural_str} | {r['yeni_karar']} | {sonuc} |")

    missing_reg = [label for label in REGRESYON_FILMLER.values() if not any(r["regresyon_label"] == label for r in regresyon_kontrol)]
    if missing_reg:
        a(f"\n> **DİKKAT:** Son 60 hub'da bulunamayan regresyon filmleri: {', '.join(missing_reg)}")
        a("> Bu filmler en son 60 hub içinde değil — mtime sırasına göre dışarıda kaldı.")
    a("")

    # 4. Beklenti doğrulaması
    a("## 4. Beklenti Doğrulaması\n")
    a("Bu filmler Hazır ve bozuk yönetmenli — K1/K2 yakalamalı.\n")
    a("| Film | Yönetmen Satırı | K1/K2 Tetiklendi? | Açıklama |")
    a("|------|----------------|------------------|---------|")
    for r in beklenti_kontrol:
        kural_str = "; ".join(r["triggered"]) if r["triggered"] else "—"
        tetik = "EVET" if r["triggered"] else "HAYIR — gözden geçir"
        a(f"| {r['beklenti_label']} | `{r['yonetmen_raw']}` | {tetik} | {kural_str} |")

    missing_bek = [label for label in BEKLENTI_FILMLER.values() if not any(r["beklenti_label"] == label for r in beklenti_kontrol)]
    if missing_bek:
        a(f"\n> **DİKKAT:** Son 60 hub'da bulunamayan beklenti filmleri: {', '.join(missing_bek)}")
        a("> Bu filmler mtime sırasına göre 60-dışında kaldı.")
    a("")

    # 5. Sayısal özet
    a("## 5. Sayısal Özet\n")
    a(f"- Taranan toplam film: **{len(results)}**")
    a(f"- Hazır → Kontrol (yeni kural yakaladı): **{len(degisen)}**")
    a(f"- Zaten Kontrol + yeni kural eklendi: **{len(zaten_kontrol_tetik)}**")
    a(f"- Hiç etkilenmeyen: **{len(etkilenmez)}**")
    a("")
    a("### K1 Tetikleyenler (yönetmen >2)")
    k1 = [r for r in results if any("K1" in t for t in r["triggered"])]
    if k1:
        for r in k1:
            a(f"- **{r['title']}**: `{r['yonetmen_raw'][:80]}` → {len(r['yonetmen_list'])} eleman")
    else:
        a("*(yok)*")
    a("")
    a("### K2 Tetikleyenler (yönetmen elemanı >45 kar)")
    k2 = [r for r in results if any("K2" in t for t in r["triggered"])]
    if k2:
        for r in k2:
            uzun = [e for e in r["yonetmen_list"] if len(e) > 45]
            a(f"- **{r['title']}**: `{uzun[0][:70]}` ({len(uzun[0])} kar)")
    else:
        a("*(yok)*")
    a("")
    a("### K3 Tetikleyenler (ana_dil≠TR + altyazı=HAYIR)")
    if k3_tetiklenenler:
        for r in k3_tetiklenenler:
            a(f"- **{r['title']}**: ana_dil=`{r['ana_dil']}`, altyazı=`{r['altyazi']}`")
    else:
        a("*(yok — tüm non-TR filmler ya altyazılı ya da listede değil)*")
    a("")

    # Yazılan MD
    report_text = "\n".join(lines_out)
    OUTPUT_MD.write_text(report_text, encoding="utf-8")
    print(f"\nRapor yazıldı: {OUTPUT_MD}", flush=True)
    print(report_text, flush=True)

if __name__ == "__main__":
    main()
