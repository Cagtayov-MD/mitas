# -*- coding: utf-8 -*-
"""Kapanış geri-uzatma tarayıcısı (footage-GÜVENLİ).

Probe kareleri (kapanış-başının GERİSİ, zaman sırasıyla erken→geç) üzerinde db_compose
has_text (tophat metin-maskesi) ile SONDAN (kapanış-başı tarafı) geriye yürür: kredi
(metin) oldukça uzatır, ardışık `gap` kadar METİN-YOK kare (=footage) gelince DURUR.

Çıktı (tek satır JSON): {"earliest_credit_idx": i, "n_frames": M, "credit_count": K}
  earliest_credit_idx = probe sırasında (0=en erken) kesintisiz-kredi başının indeksi.
  i == M-1  → uzatma yok (kapanış-başının hemen gerisi footage).
  i == 0    → krediler probe'un en başına kadar sürüyor (tamamını uzat).
Hata/boş → earliest_credit_idx=None (orchestrator uzatmaz, fail-safe).
"""
import sys
import os
import re
import json
import types
import argparse
import importlib.util
from pathlib import Path

import cv2  # noqa: E402

DCM_PATH = r"E:\MITAS\OCR-worktree\db_compose_master.py"


def _loadf(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _nat(p):
    nums = re.findall(r"\d+", p.name)
    return (int(nums[-1]) if nums else -1, p.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True, help="probe kare klasörü (kapanış-başının gerisi)")
    ap.add_argument("--gap", type=int, default=3, help="ardışık metin-yok kare → footage = dur")
    a = ap.parse_args()

    out = {"earliest_credit_idx": None, "n_frames": 0, "credit_count": 0}
    try:
        dcm = _loadf("dcm_close_back", DCM_PATH)
        frames = sorted(Path(a.frames).glob("*.png"), key=_nat)
        out["n_frames"] = len(frames)
        if not frames:
            print(json.dumps(out, ensure_ascii=False))
            return

        args_ns = types.SimpleNamespace(tht=22, min_hold=5, polarity="auto")
        p = None
        for f in frames:
            img = dcm.rd_cached(str(f))
            if img is not None:
                p = dcm.derive_params(img.shape[0], img.shape[1], args_ns)
                break
        if p is None:
            print(json.dumps(out, ensure_ascii=False))
            return

        def _has(f):
            img = dcm.rd_cached(str(f))
            if img is None:
                return False
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            try:
                return bool(dcm.has_text(dcm.text_mask(g, p, "auto"), p))
            except Exception:  # noqa: BLE001
                return False

        flags = [_has(f) for f in frames]
        out["credit_count"] = sum(1 for x in flags if x)

        n = len(flags)
        earliest = n - 1          # default: uzatma yok
        miss = 0
        i = n - 1                 # SONDAN (kapanış-başı tarafı) geriye
        while i >= 0:
            if flags[i]:
                earliest = i
                miss = 0
            else:
                miss += 1
                if miss > a.gap:  # ardışık footage → dur
                    break
            i -= 1
        out["earliest_credit_idx"] = earliest
    except Exception as e:  # noqa: BLE001 — fail-safe
        out["error"] = f"{type(e).__name__}: {e}"[:200]

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
