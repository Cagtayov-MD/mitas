# -*- coding: utf-8 -*-
"""GARBLE-TETİK ÖLÇÜM (ADIM-0, konsey ÇİFT-TANIK şartnamesi 2026-07-06). SALT-OKUR — üretim
koduna/Database'e SIFIR dokunuş. İki kanal-oranını geriye-dönük ölçer:
  KANAL-A: OneOCR yönetmen-kartını kareler-arası TUTARSIZ okudu (2+ benzersiz-fold varyant).
  KANAL-B: 'DIRECTED BY' etiketi kunye'de VAR ama yönetmen alanı BOŞ/garble ('kart-var-kör').
KARAR: KANAL-B oranı >%40 ise tetik 'her filme GLM'e yozlaşır → eşik yeniden-ayar. <%40 → ADIM-1.
"""
from __future__ import annotations
import glob
import json
import os
import re
import sys
from pathlib import Path
import unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# Linux gecisi (2026-08-01): sabit E:\MITAS yolu bu araci Linux'ta KOR ediyordu —
# 0 film gorup "%0 -> GEC" basiyordu, yani karar-kapisi SAHTE YESIL veriyordu.
_KOK = os.environ.get("MITAS_PROJECT_ROOT") or str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, os.path.join(_KOK, "scripts"))
try:
    from credit_text_read import _looks_garble
except Exception:  # noqa: BLE001
    def _looks_garble(_n):
        return None

DB = os.path.join(_KOK, "Database")
DIR_ET = re.compile(r"DIRECTED BY|MISE EN SCENE|REALISATION|A FILM BY|UN FILM DE|\bREGIA\b|\bREGIE\b"
                    r"|YÖNETMEN|YÖNETEN|REJISÖR", re.I)


def _fold(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def _case_garble(nm):
    for t in str(nm).split():
        if len(t) >= 3 and not t.isupper() and not t.istitle() and any(c.isupper() for c in t[1:]):
            return True
    return False


def _pdf_yonetmen(hub):
    md = os.path.join(hub, "pdf", "kunye_teslim.md")
    try:
        t = open(md, encoding="utf-8", errors="ignore").read()
        m = re.search(r"Yönetmen: ([^\n]+)", t)
        v = (m.group(1).strip() if m else "")
        return "" if v in ("—", "-", "") else v
    except Exception:  # noqa: BLE001
        return None  # md yok


def olc(limit=None):
    hubs = [d for d in glob.glob(os.path.join(DB, "*")) if os.path.isdir(d)]
    if limit:
        hubs = hubs[:limit]
    kart_var = 0          # jenerik-OCR'da yönetmen-etiketi geçen film sayısı
    kanal_b = []          # kart-var ama yönetmen boş/garble
    kanal_a = []          # kareler-arası tutarsız yönetmen okuması
    incel = 0
    for hub in hubs:
        # "-fb" SUFFIX kontrolü (2026-07-07 fix): substring→basename-suffix (bkz tek_film_kunye.py aynı fix).
        ks = sorted([q for q in glob.glob(os.path.join(hub, "ocr", "ocr-*", "kunye.txt"))
                     if not os.path.basename(os.path.dirname(q)).endswith("-fb")],
                    key=os.path.getmtime)
        if not ks:
            continue
        incel += 1
        kunye = open(ks[-1], encoding="utf-8", errors="ignore").read()
        # ham + dilim de etiket-taramasına dahil
        blob = kunye
        for extra in (glob.glob(os.path.join(hub, "ocr", "ocr-*", "ocr_ham", "*.txt")) +
                      glob.glob(os.path.join(hub, "ocr", "ocr-*", "*raw*.txt")) +
                      [os.path.join(hub, "master_dilim", "dilim_oneocr.txt")]):
            if os.path.exists(extra):
                try:
                    blob += "\n" + open(extra, encoding="utf-8", errors="ignore").read()
                except Exception:  # noqa: BLE001
                    pass
        etiket_var = bool(DIR_ET.search(blob))
        if not etiket_var:
            continue
        kart_var += 1
        # KANAL-B: etiket var ama PDF-yönetmen boş VEYA garble
        pdf_yon = _pdf_yonetmen(hub)
        bos = (pdf_yon == "" or pdf_yon is None)
        garble = bool(pdf_yon) and (_case_garble(pdf_yon) or (_looks_garble(pdf_yon) is not None))
        if bos or garble:
            kanal_b.append((os.path.basename(hub)[:44], "boş" if bos else f"garble:{pdf_yon[:24]}"))
        # KANAL-A: reads.jsonl'da etiket-komşusu isimlerin kareler-arası varyansı
        rr = glob.glob(os.path.join(hub, "ocr", "ocr-*", "ocr_raw_reads.jsonl"))
        if rr:
            try:
                recs = [json.loads(l) for l in open(rr[0], encoding="utf-8", errors="ignore") if l.strip()]
            except Exception:  # noqa: BLE001
                recs = []
            # etiket satırından hemen SONRAKİ line_index'teki okumaları topla (yön-adı adayları)
            by_frame = {}
            for r in recs:
                by_frame.setdefault(r.get("frame_path"), []).append(r)
            aday_okumalar = set()
            for fp, rs in by_frame.items():
                rs = sorted(rs, key=lambda x: x.get("line_index", 0))
                for i, r in enumerate(rs):
                    if DIR_ET.search(r.get("text", "")) and i + 1 < len(rs):
                        nb = rs[i + 1].get("text", "").strip().strip(",.")
                        if nb and 2 <= len(nb.split()) <= 4:
                            aday_okumalar.add(_fold(nb))
            if len(aday_okumalar) >= 2:
                kanal_a.append((os.path.basename(hub)[:44], len(aday_okumalar)))
    print(f"İncelenen film (kunye'li): {incel}")
    print(f"Yönetmen-etiketi olan film (kart_var): {kart_var}")
    print(f"\nKANAL-B (kart-var-ama-kör): {len(kanal_b)}  → oran %{100*len(kanal_b)/max(1,kart_var):.0f}")
    for f, n in kanal_b[:20]:
        print(f"   {f:46s} {n}")
    print(f"\nKANAL-A (kareler-arası tutarsız yön): {len(kanal_a)}  → oran %{100*len(kanal_a)/max(1,kart_var):.0f}")
    for f, n in kanal_a[:20]:
        print(f"   {f:46s} {n} varyant")
    orn_b = 100 * len(kanal_b) / max(1, kart_var)
    print(f"\n=== KARAR-KAPISI: KANAL-B oranı %{orn_b:.0f} → "
          f"{'ADIM-1e GEÇ (<%40)' if orn_b < 40 else 'EŞİK YENİDEN-AYAR (>=%40, her-filme-GLMe yozlaşır)'}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    olc(a.limit)
