#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
credit_export.py — TESLİM AKIŞI: Database deliverable -> teslimat/export -> (qwen QC) -> hazir/kontrol.

"Önce export, sonra qwen onayı ile hazır ya da kontrole düşer." MÜDAHALE ETMEZ (kopyalar, sınıflar).

AŞAMA 1 (export): pdf/kunye_teslim.md olan her clip'in {_DURUM.json, pdf/} -> teslimat/export/<clip>/ (resumable).
AŞAMA 2 (qwen QC): credit_qc.process her export clip'inde -> teslimat/hazir/ veya teslimat/kontrol/ (+ _kontrol_kayit.xlsx, PDF damga).

Kullanım:
  python scripts/credit_export.py                       # tüm Database -> export -> QC
  python scripts/credit_export.py --crosscheck          # + Wikidata/IMDb çapraz-kontrol (Idea 2)
  python scripts/credit_export.py --visual              # + qwen-VL görsel QC
  python scripts/credit_export.py --limit 10 --force
"""
import argparse
import glob
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit_qc

# Linux geçişi 2026-07-16: kök env'den (yoksa eski Windows davranışı birebir).
_ROOT = os.environ.get("MITAS_PROJECT_ROOT") or r"E:\MITAS"
SRC = os.path.join(_ROOT, "Database")
TESLIMAT = os.path.join(_ROOT, "teslimat")

def _safe(name):
    return re.sub(r"[^0-9A-Za-zĞÜŞİÖÇğüşıöç._-]", "_", str(name)) or "clip"

def export_clip(clipdir, export_root, force=False):
    """Database/<clip> deliverable'ını teslimat/export/<clip>/ altına kopyala (mirror: _DURUM.json + pdf/)."""
    md = os.path.join(clipdir, "pdf", "kunye_teslim.md")
    if not os.path.exists(md):
        return None
    dest = os.path.join(export_root, _safe(os.path.basename(clipdir)))
    if os.path.exists(dest) and not force:
        return dest
    os.makedirs(os.path.join(dest, "pdf"), exist_ok=True)
    durum = os.path.join(clipdir, "_DURUM.json")
    if os.path.exists(durum):
        try: shutil.copy2(durum, dest)
        except Exception: pass
    for f in glob.glob(os.path.join(clipdir, "pdf", "*")):
        try: shutil.copy2(f, os.path.join(dest, "pdf"))
        except Exception: pass
    return dest

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Teslim akışı: export -> qwen QC -> hazır/kontrol")
    ap.add_argument("--source", default=SRC)
    ap.add_argument("--teslimat", default=TESLIMAT)
    ap.add_argument("--crosscheck", action="store_true")
    ap.add_argument("--visual", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    export_root = os.path.join(args.teslimat, "export")
    os.makedirs(export_root, exist_ok=True)

    # AŞAMA 1: EXPORT
    clips = [d for d in sorted(glob.glob(os.path.join(args.source, "*")))
             if os.path.isdir(d) and os.path.exists(os.path.join(d, "pdf", "kunye_teslim.md"))]
    if args.limit:
        clips = clips[:args.limit]
    exported = []
    for c in clips:
        d = export_clip(c, export_root, args.force)
        if d:
            exported.append(d)
    print(f"[export] {len(exported)} clip -> {export_root}", flush=True)

    # AŞAMA 2: QWEN QC (export -> hazır/kontrol)
    use_cc = args.crosscheck or os.environ.get("MITAS_USE_CROSSCHECK", "").strip().lower() in ("1", "true", "yes", "on")
    kb = None
    if use_cc:
        try:
            import credit_crosscheck as _ccm
            kb = _ccm.CreditKB()
        except Exception as e:
            sys.stderr.write(f"[uyari] crosscheck kb acilamadi: {e}\n")
    haz = kon = 0
    cats = {}
    for exp in exported:
        r = credit_qc.process(exp, args.teslimat, args.visual, kb)
        if not r:
            continue
        _clip, karar, flags = r
        if karar == "hazir":
            haz += 1
        else:
            kon += 1
            for cat, _ in flags:
                cats[cat] = cats.get(cat, 0) + 1
        print(f"[{karar.upper():7}] {os.path.basename(exp)[:44]:44} {'· '+', '.join(c for c,_ in flags) if flags else ''}", flush=True)
    if kb:
        kb.close()
    print(f"\n=== AKIŞ BİTTİ: export {len(exported)} | hazır {haz} | kontrol {kon} -> {args.teslimat} ===")
    if cats:
        print("kontrol sebep dağılımı:")
        for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"   {n:3}  {cat}")

if __name__ == "__main__":
    main()
