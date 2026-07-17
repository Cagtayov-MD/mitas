# -*- coding: utf-8 -*-
"""bayrak_envanteri.py — MITAS_* env-bayrak envanterini koddan üretir (docs/BAYRAK_ENVANTERI.md).

AMAÇ (Çağatay 2026-07-17, "bayrak enflasyonu" düzeltmesi): 280+ bayrağın kanonik listesi elle
tutulamaz; bu betik kodu tarar, her bayrağın görüldüğü varsayılan(lar)ı ve dosyaları çıkarır.
Bayrak ekleyen/söken her işten sonra yeniden koş: python scripts/bayrak_envanteri.py

Salt-okunur; yalnız docs/BAYRAK_ENVANTERI.md yazar.
"""
from __future__ import annotations
import os, re, sys
from collections import defaultdict
from pathlib import Path

PROJE = Path(os.environ.get("MITAS_PROJECT_ROOT") or Path(__file__).resolve().parents[1])
TARANAN = ["scripts", "core", "OCR-worktree", "harness"]
FLAG_RE = re.compile(r"MITAS_[A-Z0-9_]+")
# os.environ.get("MITAS_X", "def") / env.get("MITAS_X") or "def" kalıplarından varsayılan yakala
DEF_RE = re.compile(r"""(?:environ|env)\.get\(\s*["'](MITAS_[A-Z0-9_]+)["']\s*(?:,\s*(["'][^"']*["']|[\w.]+))?\s*\)""")


def tara() -> tuple[dict, dict]:
    dosyalar: dict[str, set] = defaultdict(set)
    varsayilan: dict[str, set] = defaultdict(set)
    for kok in TARANAN:
        for p in sorted((PROJE / kok).rglob("*.py")):
            if ".git" in p.parts:
                continue
            try:
                metin = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(p.relative_to(PROJE))
            for m in FLAG_RE.finditer(metin):
                dosyalar[m.group(0)].add(rel)
            for m in DEF_RE.finditer(metin):
                if m.group(2):
                    varsayilan[m.group(1)].add(m.group(2).strip("\"'"))
    return dosyalar, varsayilan


def main() -> int:
    dosyalar, varsayilan = tara()
    cikti = PROJE / "docs" / "BAYRAK_ENVANTERI.md"
    satirlar = [
        "# MITAS env-bayrak envanteri (ÜRETİLMİŞ DOSYA — elle düzenleme!)",
        "",
        "Üretici: `python scripts/bayrak_envanteri.py` — bayrak ekleyen/söken işten sonra yeniden koş.",
        f"Toplam bayrak: **{len(dosyalar)}**",
        "",
        "| Bayrak | Varsayılan(lar) | Dosya sayısı | Dosyalar |",
        "|---|---|---|---|",
    ]
    for ad in sorted(dosyalar):
        defs = " / ".join(sorted(varsayilan.get(ad, {"—"}))) or "—"
        fl = sorted(dosyalar[ad])
        gosterim = ", ".join(f"`{f}`" for f in fl[:4]) + (f" +{len(fl)-4}" if len(fl) > 4 else "")
        satirlar.append(f"| `{ad}` | {defs} | {len(fl)} | {gosterim} |")
    cikti.parent.mkdir(exist_ok=True)
    cikti.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    print(f"YAZILDI: {cikti}  ({len(dosyalar)} bayrak)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
