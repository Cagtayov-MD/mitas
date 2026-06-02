"""full_pipeline_test.py — 3 film için uçtan uca pipeline testi.

CreditDetector → ScrollReconstructor → OneOCR → rapor

Kullanım:
    venv\Scripts\python.exe tools/full_pipeline_test.py
"""

from __future__ import annotations
import sys
import io
import re
import time
import json
from pathlib import Path
from difflib import SequenceMatcher

# Windows konsolunda UTF-8 çıktı — cp1254 hatalarını önler
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.credit_detector import CreditDetector
from tools.scroll_reconstructor import ScrollReconstructor

# ── Film seçimi ────────────────────────────────────────────────────────────────
VDIR = Path(r"E:\filmtest")
OUTD = ROOT / "Project" / "test_outputs" / "pipeline_test"

# 3 scroll film: bilinen iyi (K-2), orta hız (FARELER), ters yön (CARIKLI)
FILMS = [
    "evoArcadmin_COZUMLEMEV2S17_1991-0339-1-0000-01-1-K-2.mp4",
    "evoArcadmin_ÇÖZÜMLEME5_1992-1150-1-0000-50-1-FARELER_VE_İNSANLAR.mp4",
    "evoArcadmin_ÇÖZÜMLEME5_1983-0176-1-0000-90-1-ÇARIKLI_MİLYONER.mp4",
]

# ── OneOCR setup ───────────────────────────────────────────────────────────────
try:
    import oneocr as _oneocr_mod
    import os as _os
    _cfg = _os.environ.get("ONEOCR_CONFIG_DIR") or r"F:\REPO_GitHub\oneocr"
    if _os.path.isdir(_cfg):
        _oneocr_mod.CONFIG_DIR = _cfg
    OCR_ENGINE = _oneocr_mod.OcrEngine()
    HAS_OCR = True
except Exception as e:
    HAS_OCR = False
    OCR_ENGINE = None
    print(f"[UYARI] oneocr yüklenemedi: {e}")

SLICE   = 480
OVERLAP = 80


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def polygon_to_rect(rect: dict) -> tuple[int, int, int, int]:
    xs = [rect.get(f"x{i}", 0) for i in range(1, 5)]
    ys = [rect.get(f"y{i}", 0) for i in range(1, 5)]
    if not any(xs):
        x, y = rect.get("x", 0), rect.get("y", 0)
        w, h = rect.get("width", 0), rect.get("height", 0)
        return int(x), int(y), int(x + w), int(y + h)
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def norm(t: str) -> str:
    return "".join(c.lower() for c in t if c.isalnum())


def is_upper_heavy(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) >= 0.65


def run_ocr_on_composite(comp: np.ndarray, split_x: int) -> list[str]:
    """Kompozite OCR uygula, ROL | İSİM satırlarını döndür."""
    if not HAS_OCR or comp is None:
        return []

    gray = cv2.cvtColor(comp, cv2.COLOR_BGR2GRAY) if comp.ndim == 3 else comp
    H = gray.shape[0]
    # OCR gri+kontrast artırılmış versiyon üzerinde daha iyi çalışır
    ocr_img = cv2.cvtColor(comp, cv2.COLOR_BGR2RGB) if comp.ndim == 3 else cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    items: list[dict] = []
    y = 0
    while y < H:
        y2 = min(H, y + SLICE)
        sl = ocr_img[y:y2]
        try:
            result = OCR_ENGINE.recognize_cv2(sl) or {}
        except Exception:
            result = {}
        for line in result.get("lines", []):
            text = (line.get("text") or "").strip()
            if len(text) < 2:
                continue
            x1, ly1, x2, ly2 = polygon_to_rect(line.get("bounding_rect", {}))
            items.append({"y": y + ly1, "x1": x1, "x2": x2, "text": text})
        y += SLICE - OVERLAP

    if not items:
        return []

    # Y'ye göre sırala, yakın y'leri aynı satır say (±14px)
    items.sort(key=lambda d: d["y"])
    rows: list[list[dict]] = []
    cur: list[dict] = []
    cur_y: float | None = None
    for it in items:
        if cur_y is None or abs(it["y"] - cur_y) <= 14:
            cur.append(it)
            cur_y = it["y"] if cur_y is None else cur_y
        else:
            rows.append(cur)
            cur, cur_y = [it], float(it["y"])
    if cur:
        rows.append(cur)

    out_lines: list[str] = []
    seen: set[str] = set()
    for row in rows:
        # overlap tekrarları temizle (fuzzy)
        uniq: list[dict] = []
        for it in sorted(row, key=lambda d: d["x1"]):
            k = norm(it["text"])
            if not k:
                continue
            if any(SequenceMatcher(None, k, norm(u["text"])).ratio() > 0.72
                   for u in uniq):
                continue
            uniq.append(it)

        role_parts = [it["text"] for it in uniq
                      if not is_upper_heavy(it["text"]) and it["x1"] < split_x]
        name_parts = [it["text"] for it in uniq
                      if is_upper_heavy(it["text"]) or it["x1"] >= split_x]
        role = " ".join(role_parts).strip()
        name = " ".join(name_parts).strip()
        line = f"{role:<28}  |  {name}"
        key = norm(line)
        if key and key not in seen:
            seen.add(key)
            out_lines.append(line)

    return out_lines


# ── Ana döngü ─────────────────────────────────────────────────────────────────

def film_label(stem: str) -> str:
    """evoArcadmin_...-90-1-FILM_ADI -> FILM_ADI"""
    m = re.search(r"-\d{1,2}-[01]-(.+)$", stem)
    return m.group(1) if m else stem[-20:]


def run_film(video: Path, outd: Path) -> dict:
    outd.mkdir(parents=True, exist_ok=True)
    label = film_label(video.stem)
    print(f"\n{'='*70}")
    print(f"FİLM: {label}")
    print(f"{'='*70}")

    result: dict = {"film": label, "path": str(video)}
    t0 = time.time()

    # ── 1. Kredi tespiti ──────────────────────────────────────────────────────
    print("  [1/3] CreditDetector...")
    det = CreditDetector()
    dr = det.detect(str(video))
    result["detect"] = dr
    if not dr.get("found"):
        print(f"  !! Kredi bulunamadı (found=False)")
        result["ok"] = False
        return result
    print(f"  OK  tür={dr['type']}  "
          f"{dr['start_sec']:.0f}s-{dr['end_sec']:.0f}s  "
          f"hız={dr.get('scroll_speed', 0):+.2f}px/fr")

    if dr["type"] != "scroll":
        print(f"  -- Statik jenerik — ScrollReconstructor gerekmiyor, atlanıyor")
        result["ok"] = True
        result["note"] = "static — no composite"
        return result

    # ── 2. Composite oluştur ──────────────────────────────────────────────────
    print("  [2/3] ScrollReconstructor...")
    rec = ScrollReconstructor()
    comp, sharpened = rec.process_video(
        video,
        start_sec=dr["start_sec"],
        end_sec=dr["end_sec"],
        frame_step=2,
        output_dir=str(outd),
    )
    t_rec = time.time() - t0
    if comp is None:
        print("  !! Composite üretilemedi")
        result["ok"] = False
        return result

    q = rec.quality_score(comp)
    split_x = rec.find_column_split(comp)
    print(f"  OK  composite={comp.shape[1]}x{comp.shape[0]}px  "
          f"quality={q['score']:.2f}  split={split_x}px  "
          f"({t_rec:.0f}s)")
    result["composite_shape"] = [comp.shape[1], comp.shape[0]]
    result["quality"] = q
    result["split_x"] = split_x

    comp_path = outd / "composite.png"
    result["composite_path"] = str(comp_path)

    # ── 3. OCR ───────────────────────────────────────────────────────────────
    print("  [3/3] OneOCR...")
    if not HAS_OCR:
        print("  -- OCR motoru yok, atlanıyor")
        result["ok"] = True
        result["ocr_lines"] = []
        return result

    ocr_lines = run_ocr_on_composite(comp, split_x)
    txt_path = outd / "credits.txt"
    txt_path.write_text("\n".join(ocr_lines), encoding="utf-8")
    print(f"  OK  {len(ocr_lines)} satır  →  {txt_path.name}")
    result["ocr_lines"] = len(ocr_lines)
    result["ocr_sample"] = ocr_lines[:20]
    result["ocr_path"] = str(txt_path)
    result["ok"] = True
    result["elapsed"] = round(time.time() - t0, 1)

    # İlk 20 satırı ekrana bas
    print()
    for ln in ocr_lines[:20]:
        print(f"    {ln}")
    if len(ocr_lines) > 20:
        print(f"    ... ({len(ocr_lines)-20} satır daha)")

    return result


def main():
    OUTD.mkdir(parents=True, exist_ok=True)
    print(f"OneOCR: {'HAZIR' if HAS_OCR else 'YOK'}")
    print(f"Çıktı dizini: {OUTD}")

    all_results = []
    for fname in FILMS:
        video = VDIR / fname
        if not video.exists():
            print(f"\n!! Dosya bulunamadı: {video}")
            continue
        label = video.stem.split("-")[-1].replace("_", " ")
        subdir = OUTD / film_label(video.stem)
        r = run_film(video, subdir)
        all_results.append(r)

    # ── Özet rapor ────────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("ÖZET")
    print(f"{'='*70}")
    print(f"{'Film':<20} {'Tür':<8} {'Composite':<16} {'Kalite':<8} "
          f"{'OCR satır':<10} {'Süre'}")
    print("-" * 70)
    for r in all_results:
        film = r["film"][-18:]
        typ = r.get("detect", {}).get("type", "?")
        shape = "x".join(str(x) for x in r.get("composite_shape", [])) or "—"
        q = r.get("quality", {}).get("score", 0.0)
        q_str = f"{q:.2f}" if q else "—"
        ocr = str(r.get("ocr_lines", "—"))
        t = f"{r.get('elapsed', 0):.0f}s" if r.get("elapsed") else "—"
        print(f"{film:<20} {typ:<8} {shape:<16} {q_str:<8} {ocr:<10} {t}")

    json_path = OUTD / "report.json"
    json_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"\nJSON rapor: {json_path}")
    print(f"Composite PNG'ler: {OUTD}/**/composite.png")


if __name__ == "__main__":
    main()
