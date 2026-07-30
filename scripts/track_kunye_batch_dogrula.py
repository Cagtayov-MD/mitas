#!/usr/bin/env python3
"""15-film (ve sonrası) batch doğrulayıcı — "istisnasız bağlı çalışıyor" kanıtı.

Spec: docs/superpowers/specs/2026-07-30-track-kunye-uretim-entegrasyon-design.md
Kullanım:
  /opt/mitas/venvs/ocr/bin/python scripts/track_kunye_batch_dogrula.py \
      --liste kliplerim.txt [--events /opt/mitas/outputs/system_events.jsonl]
kliplerim.txt: satır başına bir clip_dir mutlak yolu.
Çıktı: film×kontrol tablosu + "N/M PASSED"; eksik varsa exit 1.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MID_DESEN = re.compile(r"(\d{4}-\d{4}-\d-\d{4}-\d{2}-\d)")
VARSAYILAN_EVENTS = "/opt/mitas/outputs/system_events.jsonl"


def olaylari_yukle(yol: Path) -> list[dict]:
    olaylar = []
    p = Path(yol)
    if not p.is_file():
        return olaylar
    for satir in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            olaylar.append(json.loads(satir))
        except Exception:
            continue
    return olaylar


def _pdf_saglam(pdf: Path) -> bool:
    """fitz ocr-venv'de yok — magic-byte + boyut + EOF kontrolü yeterli."""
    if not pdf.is_file() or pdf.stat().st_size <= 10240:
        return False
    veri = pdf.read_bytes()
    return veri.startswith(b"%PDF") and b"%%EOF" in veri[-2048:]


def klip_dogrula(clip_dir: Path, olaylar: list[dict]) -> dict:
    eksikler: list[str] = []
    uyarilar: list[str] = []
    mid_m = MID_DESEN.search(clip_dir.name)
    mid = mid_m.group(1) if mid_m else ""
    # Üretimde event media_id'si dosya-adı türevi ("evoArcadmin_..._<mid>-...") —
    # çıplak TRT no ile TAM eşleşmez; alt-dizgi araması şart (2026-07-30 smoke bulgusu).
    film_olaylari = [e for e in olaylar
                     if mid and (mid in str(e.get("media_id") or "")
                                 or mid in str(e.get("filename") or ""))]
    kinds = {str(e.get("kind") or "") for e in film_olaylari}

    # K1 — PDF
    if not _pdf_saglam(clip_dir / "pdf" / "kunye.pdf"):
        eksikler.append("pdf/kunye.pdf yok/bozuk/kucuk")

    # K2 — QC olay zinciri. credit_qc1_* YALNIZ RED tetiklenince yazılır
    # (mitas_pipeline.py:2874,2945,2957); temiz geçişin kanıtı karar.pipeline.json.
    if not any(k.startswith("credit_qc1") for k in kinds):
        if (clip_dir / "karar.pipeline.json").is_file():
            uyarilar.append("qc1_temiz_yol")
        else:
            eksikler.append("QC1 kanıtı yok (credit_qc1_* eventi de karar.pipeline.json da yok)")
    if not any(("validate" in k) or ("qc2" in k.lower()) for k in kinds):
        eksikler.append("QC2/validate olayı yok")
    if not any(k.startswith("track_kunye") for k in kinds):
        eksikler.append("track_kunye olayı yok")

    # K3 — track_kunye çıktıları + manifest tutarlılığı
    tk = clip_dir / "track_kunye"
    man_p = tk / "manifest.json"
    man: dict = {}
    if man_p.is_file():
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
        except Exception:
            eksikler.append("manifest.json bozuk")
    else:
        eksikler.append("track_kunye/manifest.json yok")
    durum = man.get("status")
    if durum == "done":
        for ad in ("frame_dokum.txt", "master_dokum.txt", "ronaldo_kunye.txt",
                   "ronaldo_fark.json"):
            p = tk / ad
            if ad == "ronaldo_kunye.txt":
                if not p.is_file() or p.stat().st_size == 0:
                    eksikler.append(f"{ad} yok/0-bayt")
            elif not p.is_file():
                eksikler.append(f"{ad} yok")
        if man.get("band") is None and not man.get("ibra_atlandi_sebep") \
                and not man.get("common_blind"):
            eksikler.append("band null ama sebep yok (ibra_atlandi/common_blind boş)")
        if not list(clip_dir.glob("* kunye3.txt")):
            eksikler.append("kök kunye3.txt yok")
    elif durum == "skipped":
        if man.get("reason"):
            uyarilar.append(f"skipped:{man['reason']}")
        else:
            eksikler.append("skipped ama reason yok")
    elif durum is not None:
        eksikler.append(f"track_kunye status={durum}")

    return {"film": clip_dir.name, "gecti": not eksikler,
            "eksikler": eksikler, "uyari": ",".join(uyarilar)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liste", required=True)
    ap.add_argument("--events", default=VARSAYILAN_EVENTS)
    a = ap.parse_args()
    klipler = [Path(s.strip()) for s in Path(a.liste).read_text(encoding="utf-8").splitlines()
               if s.strip()]
    olaylar = olaylari_yukle(Path(a.events))
    gecen = 0
    for clip in klipler:
        s = klip_dogrula(clip, olaylar)
        durum = "PASS" if s["gecti"] else "FAIL"
        if s["uyari"]:
            durum += f" ({s['uyari']})"
        print(f"{durum:28s} {s['film']}")
        for e in s["eksikler"]:
            print(f"    - {e}")
        gecen += 1 if s["gecti"] else 0
    print(f"\n{gecen}/{len(klipler)} PASSED")
    return 0 if gecen == len(klipler) else 1


if __name__ == "__main__":
    raise SystemExit(main())
