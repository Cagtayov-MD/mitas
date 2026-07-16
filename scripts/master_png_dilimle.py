# -*- coding: utf-8 -*-
"""master_png_dilimle.py — reading-master PNG'leri VL-okunur parçalara AKILLI dilimleme.

AMAÇ (Çağatay 2026-07-03): reading_master_runaware.png + giris_reading_master_runaware.png
şu anda sadece üretiliyor, sisteme katkı vermiyor. VL modeli (qwen-sınıfı) makul yükseklikte
(~3000px) master'ları çok verimli okuyor; uzun master'lar (max ~36k px ölçüldü) DÜZGÜN YERDEN
kesilip 2-12 parçaya bölünmeli ki hiçbir isim satırı ortadan biçilmesin.

KURALLAR:
  * ANA DOSYALARA DOKUNULMAZ (salt-okunur girdi). Çıktı film içinde YENİ klasöre yazılır:
      <film>/master_dilim/<kaynak-stem>_pNN.png  +  <kaynak-stem>_dilim_manifest.json
  * Kesim yeri = BOŞ YATAY BANT (satır arası): satır-mürekkep profili çıkarılır, hedef
    yüksekliğe (default 3000px) en yakın boş banttan kesilir.
  * Pencerede hiç boş bant yoksa: en az mürekkepli satırdan MECBUREN kesilir ve bir sonraki
    parça OVERLAP kadar geriden başlar (kesilen satır iki parçada da TAM görünür — isim kaybolmaz).
  * Zaten kısa (<= max) dosya tek parça kopyalanır (tüketici tek örüntü görsün diye).

Kullanım:
  python scripts/master_png_dilimle.py --clip "E:\\MITAS\\Database\\<film>"
  python scripts/master_png_dilimle.py --all                      (tüm Database)
  python scripts/master_png_dilimle.py --png <dosya> --out <klasör>
  Ayar (env): MITAS_DILIM_TARGET=3000  MITAS_DILIM_MAX=3600  MITAS_DILIM_MIN=600
              MITAS_DILIM_OVERLAP=48   MITAS_DILIM_FG_DELTA=48  MITAS_DILIM_BLANK_FRAC=0.002

FAIL-SAFE: dosya-başına try/except — bir master bozuksa diğerleri işlenmeye devam eder;
manifest'e hata kaydı düşülür. Kesinlikle hiçbir kaynak dosya silinmez/değiştirilmez.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None          # 36k+ px yükseklik meşru (decompression-bomb korumasını aş)

DB_ROOT = Path(r"E:\MITAS\Database")
DILIM_DIRNAME = "master_dilim"
# Varsayılan kaynak seti: SADECE okuma-master'ları (kanonik '<TRT> giris/cikis.png' teslim
# yüzeyidir, dilimlemeye şimdilik dahil değil — istenirse --include-kanonik ile açılır).
DEFAULT_SOURCES = ("giris_reading_master_runaware.png", "reading_master_runaware.png")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def params_from_env() -> dict:
    p = {
        "target": _env_int("MITAS_DILIM_TARGET", 3000),   # hedef parça yüksekliği
        "hard_max": _env_int("MITAS_DILIM_MAX", 3600),    # sert üst sınır (VL bağlam güvenliği)
        "min_part": _env_int("MITAS_DILIM_MIN", 600),     # cüce-parça önleme
        "overlap": _env_int("MITAS_DILIM_OVERLAP", 120),  # mecburi-kesimde geri-bindirme (~2-3 kredi satırı;
                                                          # biçilen satır SONRAKİ parçada tam görünür — kayıp yok)
        "fg_delta": _env_int("MITAS_DILIM_FG_DELTA", 48), # önplan eşiği: |px - zemin| > delta
        "blank_frac": _env_float("MITAS_DILIM_BLANK_FRAC", 0.002),  # boş-satır önplan oranı tavanı
    }
    # tutarlılık: min < target <= hard_max
    p["hard_max"] = max(p["hard_max"], p["target"])
    p["min_part"] = min(p["min_part"], p["target"] // 2)
    return p


def row_ink_profile(img: Image.Image, fg_delta: int) -> "np.ndarray":
    """Satır-başına önplan-piksel oranı. Zemin = global mod (siyah-zemin çıkış slit'i de,
    açık-zemin crop-stack de doğru çalışır — zemine UZAK piksel önplandır)."""
    g = np.asarray(img.convert("L"), dtype=np.int16)
    # global mod (256-kutu histogram; en kalabalık gri ton = zemin)
    hist = np.bincount(g.reshape(-1).clip(0, 255).astype(np.uint8), minlength=256)
    bg = int(hist.argmax())
    fg = (np.abs(g - bg) > fg_delta)
    return fg.mean(axis=1)


def blank_runs(ink: "np.ndarray", blank_frac: float) -> list[tuple[int, int]]:
    """[y0, y1) yarı-açık boş-bant aralıkları (önplan oranı eşik altı ardışık satırlar)."""
    blank = ink <= blank_frac
    runs, start = [], None
    for y, b in enumerate(blank):
        if b and start is None:
            start = y
        elif not b and start is not None:
            runs.append((start, y))
            start = None
    if start is not None:
        runs.append((start, len(blank)))
    return runs


def choose_cuts(height: int, ink: "np.ndarray", p: dict) -> list[dict]:
    """Kesim noktaları: her biri {'row': y, 'type': 'blank'|'forced'}. Son parça sınırı (height) hariç."""
    runs = blank_runs(ink, p["blank_frac"])
    cuts: list[dict] = []
    cursor = 0
    while height - cursor > p["hard_max"]:
        ideal = cursor + p["target"]
        lo, hi = cursor + p["min_part"], cursor + p["hard_max"]
        # pencere içinde MERKEZİ kalan boş bantlar aday; ideale yakınlık + bant genişliği ödülü
        best, best_score = None, None
        for (r0, r1) in runs:
            c = (r0 + r1) // 2
            if c < lo or c > hi:
                continue
            width_bonus = min(r1 - r0, 80)           # geniş bant daha güvenli kesim yeri
            score = abs(c - ideal) - 2 * width_bonus
            if best_score is None or score < best_score:
                best, best_score = c, score
        if best is not None:
            cuts.append({"row": int(best), "type": "blank"})
            cursor = int(best)
            continue
        # boş bant yok → YUMUŞATILMIŞ profilde yerel-minimum satırdan MECBUREN kes: yoğun-metinli
        # master'da (GÜLE GÜLE JÜPİTER Japonca-jenerik vakası) ham argmin gürültüyle satır ORTASINA
        # düşebiliyordu; 15px hareketli-ortalama satır-arası boşluğu yakalar. Overlap telafisi yazımda.
        seg = ink[lo:hi].astype(float)
        k = 15
        kern = np.ones(k) / k
        smooth = np.convolve(seg, kern, mode="same")
        y = int(lo + int(smooth.argmin()))
        cuts.append({"row": y, "type": "forced"})
        cursor = y
    return cuts


def slice_master(png: Path, out_dir: Path, p: dict) -> dict:
    """Tek master'ı dilimle → out_dir'e parçalar + manifest kaydı döndür."""
    t0 = time.perf_counter()
    with Image.open(png) as im:
        im.load()
        w, h = im.size
        stem = png.stem
        rec = {"source": str(png), "width": w, "height": h, "parts": [], "cuts": [],
               "params": dict(p), "ts": datetime.now(timezone.utc).isoformat()}
        out_dir.mkdir(parents=True, exist_ok=True)
        # kendi eski parçalarını temizle (yalnız BU stem'e ait, BU klasörde — güvenli dar kapsam)
        if out_dir.name != DILIM_DIRNAME:
            raise ValueError(f"guvenlik: dilim klasoru '{DILIM_DIRNAME}' olmali: {out_dir}")
        for old in out_dir.glob(f"{stem}_p*.png"):
            old.unlink()
        if h <= p["hard_max"]:
            dst = out_dir / f"{stem}_p01.png"
            im.save(dst, "PNG")
            rec["parts"].append({"file": dst.name, "y0": 0, "y1": h})
            rec["secs"] = round(time.perf_counter() - t0, 2)
            return rec
        ink = row_ink_profile(im, p["fg_delta"])
        cuts = choose_cuts(h, ink, p)
        rec["cuts"] = cuts
        bounds = [0] + [c["row"] for c in cuts] + [h]
        for i in range(len(bounds) - 1):
            y0, y1 = bounds[i], bounds[i + 1]
            # mecburi kesimden sonraki parça overlap kadar geriden başlar (kesilen satır tam görünsün)
            if i > 0 and cuts[i - 1]["type"] == "forced":
                y0 = max(0, y0 - p["overlap"])
            part = im.crop((0, y0, w, y1))
            dst = out_dir / f"{stem}_p{i + 1:02d}.png"
            part.save(dst, "PNG")
            rec["parts"].append({"file": dst.name, "y0": int(y0), "y1": int(y1)})
        rec["secs"] = round(time.perf_counter() - t0, 2)
        return rec


def process_clip(clip_dir: Path, sources: tuple[str, ...], p: dict) -> dict:
    """Bir film klasöründeki mevcut kaynak master'ları dilimle; manifest yaz."""
    out_dir = clip_dir / DILIM_DIRNAME
    results, found = [], 0
    for name in sources:
        png = clip_dir / name
        if not png.exists():
            continue
        found += 1
        try:
            results.append(slice_master(png, out_dir, p))
        except Exception as exc:  # noqa: BLE001 — bir master bozuksa diğeri işlenmeye devam etsin
            results.append({"source": str(png), "error": f"{type(exc).__name__}: {exc}"})
    summary = {"film": clip_dir.name, "found": found, "results": results,
               "ts": datetime.now(timezone.utc).isoformat()}
    if found:
        try:
            (out_dir / "dilim_manifest.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 — manifest yazılamasa da parçalar geçerli
            summary["manifest_error"] = str(exc)
    return summary


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", help="tek film klasörü")
    ap.add_argument("--all", action="store_true", help="tüm Database")
    ap.add_argument("--png", help="tek PNG dosyası (test)")
    ap.add_argument("--out", help="--png için çıktı klasörü (default: yanına master_dilim/)")
    ap.add_argument("--include-kanonik", action="store_true",
                    help="'<ad> giris.png/cikis.png' kanonik master'ları da dilimle")
    ap.add_argument("--source", default="reading", choices=["canonical", "reading", "both"],
                    help="VARSAYILAN reading: reading_master_runaware (TAM künye — oyuncu+ekip+sponsor). "
                         "canonical: '<ad> giris/cikis.png' — DEDUP uzun kaydırmalı künyeyi KESER (eksik). "
                         "Not: footage-şişkinlik reading'de değil AŞAMA-1 erken-tespit havuzundan gelir.")
    a = ap.parse_args()
    p = params_from_env()
    if a.png:
        png = Path(a.png)
        out = Path(a.out) if a.out else (png.parent / DILIM_DIRNAME)
        rec = slice_master(png, out, p)
        print(json.dumps(rec, ensure_ascii=False))
        return 0
    clips: list[Path] = []
    if a.clip:
        clips = [Path(a.clip)]
    elif a.all:
        clips = sorted(d for d in DB_ROOT.iterdir() if d.is_dir())
    else:
        ap.error("--clip, --all veya --png verin")
    total = {"clips": 0, "masters": 0, "parts": 0, "errors": 0}
    for clip in clips:
        canon = [q.name for q in sorted(clip.glob("* giris.png"))] + [q.name for q in sorted(clip.glob("* cikis.png"))]
        if a.source == "reading":
            sources = list(DEFAULT_SOURCES)
        elif a.source == "both":
            sources = canon + list(DEFAULT_SOURCES)
        else:  # canonical (VARSAYILAN): kanonik master; yoksa reading'e düş
            sources = canon if canon else list(DEFAULT_SOURCES)
        if a.include_kanonik and a.source == "reading":
            sources += canon
        s = process_clip(clip, tuple(sources), p)
        if s["found"]:
            total["clips"] += 1
            for r in s["results"]:
                if r.get("error"):
                    total["errors"] += 1
                    print(f"[HATA] {r['source']}: {r['error']}", file=sys.stderr)
                else:
                    total["masters"] += 1
                    total["parts"] += len(r["parts"])
    print(json.dumps(total, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
