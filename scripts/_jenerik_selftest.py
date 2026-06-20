# -*- coding: utf-8 -*-
"""Sentetik birim testi — jenerik_detector 4-tip + kritik fix doğrulaması (CLIP'siz, sezgisel).

Senaryolar:
  1 static_dark    : siyah zemin + beyaz statik yazı           → present, bg_static_text_static
  2 static_bright  : PARLAK zemin + beyaz statik yazı           → present (ESKİ DEDEKTÖRÜN KAÇIRDIĞI)
  3 scroll_dark    : siyah zemin + yukarı kayan yazı            → present, bg_static_text_scroll
  4 bgpan_static   : panlayan parlak zemin + sabit yazı         → present, bg_moving_text_static
  5 footage        : dokulu rastgele (yazı yok)                 → KOŞU YOK
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import cv2
from core.pipelines.ocr import jenerik_detector as jd

H, W, N = 480, 640, 24
rng = np.random.default_rng(7)
LINES = ["AHMET YILMAZ", "YONETMEN MEHMET", "GORUNTU ALI VELI",
         "KURGU AYSE FATMA", "MUZIK CAN DENIZ", "YAPIM ARSIV FILM"]


def _noise(c):
    return np.clip(c.astype(np.int16) + rng.integers(-4, 5, c.shape, dtype=np.int16), 0, 255).astype(np.uint8)


def draw_text(canvas, yshift=0, color=(255, 255, 255)):
    for k, t in enumerate(LINES):
        y = 90 + k * 58 + yshift
        if 20 < y < H - 8:
            cv2.putText(canvas, t, (70, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
    return canvas


def s_static(bg_val):
    out = []
    for _ in range(N):
        c = np.full((H, W, 3), bg_val, np.uint8)
        draw_text(c)
        out.append(_noise(c))
    return out


def s_scroll():
    out = []
    for i in range(N):
        c = np.zeros((H, W, 3), np.uint8)
        draw_text(c, yshift=-7 * i % 350)
        out.append(_noise(c))
    return out


def s_bgpan():
    # Gerçek footage gibi GÜÇLÜ-ÖZELLİKLİ panlayan zemin (izlenebilir köşeler → LK kilitlenir).
    base = np.full((H, 2 * W), 30, np.uint8)
    r2 = np.random.default_rng(3)
    for _ in range(180):
        x = int(r2.integers(0, 2 * W - 50)); y = int(r2.integers(0, H - 50))
        w = int(r2.integers(18, 50)); h = int(r2.integers(18, 50))
        cv2.rectangle(base, (x, y), (x + w, y + h), int(r2.integers(70, 255)), -1)
    out = []
    for i in range(N):
        sh = (6 * i) % W
        bg = base[:, sh:sh + W]
        c = cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR)
        draw_text(c)  # yazı SABİT
        out.append(_noise(c))
    return out


def s_footage():
    out = []
    for _ in range(N):
        c = rng.integers(0, 255, (H, W, 3), dtype=np.uint8)
        c = cv2.GaussianBlur(c, (0, 0), 6)  # dokulu ama yapısal-yazı yok
        out.append(c)
    return out


SCEN = {
    "static_dark": (s_static(0), True, "bg_static_text_static"),
    "static_bright": (s_static(195), True, "bg_static_text_static"),
    "scroll_dark": (s_scroll(), True, "bg_static_text_scroll"),
    "bgpan_static": (s_bgpan(), True, "bg_moving_text_static"),
    "footage": (s_footage(), False, None),
}

print("=== JENERİK detektör sentetik test (CLIP yok) ===\n")
ok_all = True
for name, (frames, want_present, want_quad) in SCEN.items():
    sigs, runs = jd.analyze(frames, clip_ctx=None)
    valid = [r for r in runs if r["valid"]]
    chosen = jd._pick_run(runs, len(frames), "first")
    got_present = chosen is not None
    got_quad = chosen["quad_type"] if chosen else None
    present_ok = got_present == want_present
    quad_ok = (want_quad is None) or (got_quad == want_quad)
    line = (f"[{name:14s}] present={got_present}(iste={want_present}) "
            f"quad={got_quad}(iste={want_quad}) "
            f"| koşu={len(runs)} geçerli={len(valid)}")
    if chosen:
        line += (f" cs={chosen['confidence']:.2f} dy={chosen['scroll_dy_px']:.1f} "
                 f"bg={chosen['bg_motion']} txt={chosen['text_motion']}")
    status = "OK " if (present_ok and quad_ok) else "FAIL"
    ok_all = ok_all and present_ok and quad_ok
    print(f"  {status} {line}")
    # ek teşhis: kare-medyan sinyalleri
    md_cs = float(np.median([s.credit_score for s in sigs]))
    md_heur = float(np.median([s.heur for s in sigs]))
    md_dark = float(np.median([s.dark_ratio for s in sigs]))
    print(f"        med credit={md_cs:.2f} heur={md_heur:.2f} dark={md_dark:.2f}")

print("\n" + ("TÜMÜ GEÇTİ ✓" if ok_all else "BAZILARI BAŞARISIZ ✗"))
raise SystemExit(0 if ok_all else 1)
