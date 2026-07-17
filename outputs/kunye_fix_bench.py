#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""kunye_fix_bench.py — F1/F2/F3 düzeltmelerinin 43-film ölçümü.

Strateji:
  - ESKİ davranış: kunye_audit_tier1.json'daki mevcut pipeline çıktısını kullanır
    (gerçekten pipeline'ın ürettiği cast/yön — LLM yeniden koşulmaz).
  - YENİ davranış: aynı cast/yön listelerine F2 KB filtresi + F3 garble kapısını uygular.
  - F1 ensemble etkisi: Ollama canlı gerektirdiğinden bench'te ölçülmez; sadece F2+F3 ölçülür.
    (Canlı Ollama varsa --live flag ile F1 de koşulabilir.)
  - Ground-truth: DENETIM_43_KUNYE_2026-06-08.md'den parse edilen "Doğru yönetmen" + garble notları.

Çıktı:
  - Yönetmen DOLU sayısı (eski vs yeni) + GT eşleşme
  - Cast garble token sayısı (eski vs yeni)
  - Cast KB crew-sızıntı sayısı (eski vs yeni)
  - Regresyon: yeni fix bir doğru yönetmeni veya temiz oyuncuyu düşürdü mü?
"""
from __future__ import annotations
import json, re, sys, os, unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ─── yollar ──────────────────────────────────────────────────────────────────
MITAS = Path(r"E:\MITAS")
TIER1_JSON = MITAS / "outputs" / "kunye_audit_tier1.json"
GT_MD = MITAS / "outputs" / "DENETIM_43_KUNYE_2026-06-08.md"
SCRIPTS = MITAS / "scripts"

# credit_text_read'e erişim için scripts ekle
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# ─── filtre fonksiyonlarını import et ────────────────────────────────────────
try:
    from credit_text_read import (
        _apply_garble_gate,
        _apply_garble_gate_yapimci,
        _apply_kb_cast_filter,
        _apply_kb_yapimci_filter,
        _looks_garble,
        _get_kb,
        _fold,
    )
    FILTERS_OK = True
except Exception as e:
    print(f"[HATA] credit_text_read import başarısız: {e}")
    FILTERS_OK = False
    sys.exit(1)

kb = _get_kb()
KB_AVAILABLE = getattr(kb, "con", None) is not None
print(f"KB bağlantısı: {'VAR' if KB_AVAILABLE else 'YOK (F2 filtresi devre dışı)'}")

# ─── ground-truth parse ───────────────────────────────────────────────────────
def _fold_gt(s: str) -> str:
    s = (s or "").upper()
    for a, b in [("İ","I"),("Ş","S"),("Ğ","G"),("Ü","U"),("Ö","O"),("Ç","C"),("ı","I")]:
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()

gt_text = GT_MD.read_text(encoding="utf-8", errors="ignore")

# TRT-ID → {yonetmen: [..], garble_cast_notes: str, crew_cast_notes: str}
gt_map: dict[str, dict] = {}

for block in re.split(r"(?=^##\s)", gt_text, flags=re.M):
    # TRT-ID
    m_id = re.search(r"TRT:\s*([\d\-]+)", block)
    if not m_id:
        continue
    trt_id = m_id.group(1).strip()
    # Doğru yönetmen
    m_yon = re.search(r"\*\*Doğru yönetmen:\*\*\s*(.+)", block)
    yon_gt = []
    if m_yon:
        raw_yon = m_yon.group(1).strip()
        # virgül veya virgül-benzeri ile ayır
        for nm in re.split(r"[,/]", raw_yon):
            nm = nm.strip()
            if nm and nm != "—":
                yon_gt.append(nm)
    # Cast notu (garble ve crew sızıntısı ipuçları için)
    m_cast = re.search(r"\*\*Cast notu:\*\*\s*(.+)", block)
    cast_note = m_cast.group(1).strip() if m_cast else ""
    gt_map[trt_id] = {"yonetmen": yon_gt, "cast_note": cast_note}

print(f"Ground-truth yüklendi: {len(gt_map)} film\n")

# ─── tier1 verisi yükle ───────────────────────────────────────────────────────
tier1 = json.loads(TIER1_JSON.read_text(encoding="utf-8"))

# ─── KBVerify tablosu (bilinen crew üyeleri, GT notlarından) ─────────────────
# Garble audit.py'nin yakaladığı listeden + GT'den: bunlar kesin crew
_KNOWN_CREW = {
    "BEN BURTT",          # Star Wars — ses tasarımcısı
    "RICHARD PORTMAN",    # Semi-Tough — ses karma
    "STAN BROSSETTE",     # Semi-Tough — tanıtım
    "CHRISTOPHER GODSICK",# Broken Arrow
    "SANDI RENFROE",      # Broken Arrow
    "DWIGHT LITTLE",      # Broken Arrow (yönetmen, cast'e girmemeli)
    "MERYL O'LOUGHLÎN",   # Önce Ağlarsin — casting
    "CAROLE SKLAN",       # Asi — ekip
    "BELINDA WEST",       # Asi — ekip
    "IRENA PAVLASKOVA",   # Usaklarin Zamani — yönetmen (cast'te de görünüyor)
    "VACLAV VONDRACEK",   # Usaklarin Zamani — ses ekibi
    "PETER SUSSMAN",      # Sözün Değeri — producer
    "JACK MCQUEEN",       # Sözün Değeri — ekip
    "JULIE ASHTON-BARSON", # Cinayet Savunması — casting
    "SID KOZAK",          # Cinayet Savunması — casting
    "KRISTINE BAMATTRE",  # Cinayet Savunması — assoc. producer
    "ROMMEL JANAPIN",     # Düşman Hattında — set dekor
    "BABY C. MAITIM",     # Düşman Hattında — senaryo sup.
    "CALOY MEDINA",       # Düşman Hattında — yönetmen yrd.
    "MARCUS BARONE",      # Düşman Hattında — müzik sup.
    "KRISTIN PICKETT",    # Düşman Hattında — şarkı perf.
    "IAN BOYD",           # Şeytanin Atlisi — ses teknikeri
}

def _fold_up(s: str) -> str:
    return _fold_gt(s)

def _is_known_crew(name: str) -> bool:
    fn = _fold_up(name)
    for c in _KNOWN_CREW:
        if _fold_up(c) == fn or fn in _fold_up(c) or _fold_up(c) in fn:
            return True
    return False

# ─── ölçüm döngüsü ───────────────────────────────────────────────────────────
rows = []

STAT_OLD = {"yon_dolu": 0, "yon_gt_match": 0, "cast_garble": 0, "cast_crew": 0, "total": 0}
STAT_NEW = {"yon_dolu": 0, "yon_gt_match": 0, "cast_garble": 0, "cast_crew": 0, "total": 0}
REGRESYON = []

for entry in tier1:
    trt_id = entry.get("trt_id", "")
    title = entry.get("title", "")
    cast_old = entry.get("cast", [])
    yon_old = entry.get("yonetmen", [])
    yap_old = entry.get("yapimci", [])
    gt = gt_map.get(trt_id, {})
    gt_yon = gt.get("yonetmen", [])

    STAT_OLD["total"] += 1
    STAT_NEW["total"] += 1

    # ── ESKİ ölçüm ──────────────────────────────────────────────────────────
    old_yon_dolu = 1 if yon_old else 0
    old_yon_gt = 0
    for gy in gt_yon:
        for oy in yon_old:
            if _fold_up(gy) == _fold_up(oy) or _fold_up(gy) in _fold_up(oy) or _fold_up(oy) in _fold_up(gy):
                old_yon_gt = 1
                break

    old_garble_count = sum(1 for nm in cast_old if _looks_garble(nm) is not None)
    old_crew_count = sum(1 for nm in cast_old if _is_known_crew(nm))

    STAT_OLD["yon_dolu"] += old_yon_dolu
    STAT_OLD["yon_gt_match"] += old_yon_gt
    STAT_OLD["cast_garble"] += old_garble_count
    STAT_OLD["cast_crew"] += old_crew_count

    # ── YENİ: F2+F3 filtrelerini uygula ────────────────────────────────────
    cast_new = _apply_garble_gate(cast_old)
    cast_new = _apply_kb_cast_filter(cast_new, kb)
    yon_new = yon_old  # F1 canlı Ollama gerektiriyor; burada değişmez
    yap_new = _apply_garble_gate_yapimci(yap_old)
    yap_new = _apply_kb_yapimci_filter(yap_new, kb)

    new_yon_dolu = 1 if yon_new else 0
    new_yon_gt = 0
    for gy in gt_yon:
        for ny in yon_new:
            if _fold_up(gy) == _fold_up(ny) or _fold_up(gy) in _fold_up(ny) or _fold_up(ny) in _fold_up(gy):
                new_yon_gt = 1
                break

    new_garble_count = sum(1 for nm in cast_new if _looks_garble(nm) is not None)
    new_crew_count = sum(1 for nm in cast_new if _is_known_crew(nm))

    STAT_NEW["yon_dolu"] += new_yon_dolu
    STAT_NEW["yon_gt_match"] += new_yon_gt
    STAT_NEW["cast_garble"] += new_garble_count
    STAT_NEW["cast_crew"] += new_crew_count

    # ── Regresyon tespiti ──────────────────────────────────────────────────
    removed_cast = [nm for nm in cast_old if nm not in cast_new]
    lost_clean = [nm for nm in removed_cast if _looks_garble(nm) is None and not _is_known_crew(nm)]
    if lost_clean:
        REGRESYON.append((trt_id, title, "cast-temiz-kaldırıldı", lost_clean))

    removed_yap = [nm for nm in yap_old if nm not in yap_new]
    if removed_yap:
        # Yapımcıda yanlış kaldırmayı da izle
        REGRESYON.append((trt_id, title, "yapımcı-kaldırıldı", removed_yap))

    # Yön değişimi (F1 şimdilik yok — F1 canlı testle ölçülmeli)

    # ── Satır ──────────────────────────────────────────────────────────────
    cast_removed_garble = [nm for nm in cast_old if nm not in cast_new and _looks_garble(nm)]
    cast_removed_crew   = [nm for nm in cast_old if nm not in cast_new and _is_known_crew(nm) and not _looks_garble(nm)]
    rows.append({
        "trt_id": trt_id,
        "title": title,
        "gt_yon": gt_yon,
        "yon_old": yon_old,
        "yon_new": yon_new,
        "cast_old_n": len(cast_old),
        "cast_new_n": len(cast_new),
        "garble_old": old_garble_count,
        "garble_new": new_garble_count,
        "crew_old": old_crew_count,
        "crew_new": new_crew_count,
        "removed_garble": cast_removed_garble,
        "removed_crew": cast_removed_crew,
        "lost_clean": lost_clean,
    })

# ─── tablo çıkışı ────────────────────────────────────────────────────────────
print("=" * 110)
print(f"{'TRT-ID':<30} {'Başlık':<28} {'Yön-GT':>7} {'GG-old':>7} {'GG-new':>7} {'Crew-old':>9} {'Crew-new':>9} {'Kaldır-G':>9} {'Kaldır-C':>9}")
print("-" * 110)
for r in rows:
    gt_m = "✓" if any(
        _fold_up(gy) in _fold_up(ny) or _fold_up(ny) in _fold_up(gy)
        for gy in r["gt_yon"] for ny in r["yon_new"]
    ) else ("—" if not r["gt_yon"] else "✗")
    print(
        f"{r['trt_id']:<30} {r['title'][:27]:<28} {gt_m:>7} "
        f"{r['garble_old']:>7} {r['garble_new']:>7} "
        f"{r['crew_old']:>9} {r['crew_new']:>9} "
        f"{len(r['removed_garble']):>9} {len(r['removed_crew']):>9}"
    )
    if r["removed_garble"]:
        print(f"    garble kaldırıldı: {r['removed_garble']}")
    if r["removed_crew"]:
        print(f"    crew kaldırıldı  : {r['removed_crew']}")
    if r["lost_clean"]:
        print(f"    [!] temiz isim KAYBOLDU: {r['lost_clean']}")

print("=" * 110)
print(f"\n{'METRİK':<35} {'ESKİ':>10} {'YENİ':>10}  {'FARK':>10}")
print("-" * 70)
n = STAT_OLD["total"]
metrics = [
    ("Film sayısı", n, n),
    ("Yönetmen DOLU film", STAT_OLD["yon_dolu"], STAT_NEW["yon_dolu"]),
    ("Yönetmen GT eşleşmesi", STAT_OLD["yon_gt_match"], STAT_NEW["yon_gt_match"]),
    ("Toplam cast garble token", STAT_OLD["cast_garble"], STAT_NEW["cast_garble"]),
    ("Toplam cast crew-sızıntı (bilinen)", STAT_OLD["cast_crew"], STAT_NEW["cast_crew"]),
]
for lbl, old, new in metrics:
    diff = new - old
    sign = "+" if diff > 0 else ""
    print(f"{lbl:<35} {old:>10} {new:>10}  {sign}{diff:>9}")

print(f"\nNOT: F1 (ensemble yönetmen) canlı Ollama gerektiriyor → bu bench'te ölçülmedi.")
print(f"     Yönetmen DOLU sayısı F2+F3 sonrası değişmez (filtreler sadece cast/yapımcıya etki etti).")
print(f"     KB bağlantısı: {'VAR' if KB_AVAILABLE else 'YOK'} → F2 filtresi {'aktif' if KB_AVAILABLE else 'devre dışı'}.\n")

print("=" * 70)
print("REGRESYON RAPORU")
print("-" * 70)
reg_real = [(t, ti, ty, lst) for t, ti, ty, lst in REGRESYON if ty == "cast-temiz-kaldırıldı"]
reg_yap  = [(t, ti, ty, lst) for t, ti, ty, lst in REGRESYON if ty == "yapımcı-kaldırıldı"]
if not reg_real:
    print("Cast regresyon: YOK ✓ (hiçbir temiz/doğru isim F2+F3 tarafından kaldırılmadı)")
else:
    print(f"Cast regresyon: {len(reg_real)} UYARI")
    for trt, ti, ty, lst in reg_real:
        print(f"  [{trt}] {ti}: {lst}")
if reg_yap:
    print(f"\nYapımcı kaldırma: {len(reg_yap)} (incelenmeli)")
    for trt, ti, ty, lst in reg_yap:
        print(f"  [{trt}] {ti}: {lst}")
else:
    print("Yapımcı kaldırma: YOK ✓")

print("=" * 70)
print("\nÖZET:")
garble_azaldi = STAT_OLD["cast_garble"] - STAT_NEW["cast_garble"]
crew_azaldi   = STAT_OLD["cast_crew"] - STAT_NEW["cast_crew"]
print(f"  F3 garble kapısı: {garble_azaldi:+d} token kaldırıldı "
      f"({STAT_OLD['cast_garble']} → {STAT_NEW['cast_garble']})")
print(f"  F2 KB crew filtresi: {crew_azaldi:+d} crew kaldırıldı "
      f"({STAT_OLD['cast_crew']} → {STAT_NEW['cast_crew']})")
print(f"  F1 ensemble: canlı Ollama gerekiyor — ayrı test edilmeli")
print(f"  Regresyon: {len(reg_real)} temiz isim kayıp" if reg_real else "  Regresyon: YOK ✓")
