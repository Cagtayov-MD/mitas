# -*- coding: utf-8 -*-
"""_jenerik_dense.py — AŞAMA-2v2 KÖK-FİX (üretim): master için ADAPTİF YOĞUN-KARE (çıkış).

SORUN (WSL 2026-07-14 kök-neden): compositor'ün scroll-tespiti kare-arası dikey kayma (dy) ile
çalışır: dy < static_dy(~1.9px) → STATİK ; dy > cut(~50px) → SAHNE-KESİĞİ (statiğe düşer) →
kart-yığma → SMEAR/COLLAPSE. 1.5fps'te kayan kredi dy≈75px → 'cut' sanılır (HALLERİ smear,
MAVZER collapse, ZENGİN tekrar). Sabit 25fps de yanlış: yavaş scroll'da dy<1.9 → yine statik.

ÇÖZÜM (POC: harness/adaptive_dense.py + harness/asama2_v2.py; HALLERİ scroll_frac 0→0.755):
havuzdaki gerçek dy'yi ÖLÇ → dy'yi hedef banda (~8px) oturtacak fps'i HESAPLA → kredi
zaman-aralığını o fps ile videodan YENİDEN çıkar. Statik film (dy<4px) seyrek kalır.

ÜRETİM TASARIMI (POC'tan fark): havuz ASLA değiştirilmez/silinmez. Yoğun kareler KARDEŞ dizine
yazılır: frames/cikis_jenerik_dense (+ cikis_jenerik_dense_manifest.json). Tercihi
master_png_monitor._seg_source yapar (dense doluysa onu okur). Kill-switch: MITAS_MASTER_DENSE=0
(hem üretim hem tercih kapanır). FAIL-SAFE: her hata → kısmi çıktı temizlenir, manifest'e hata
yazılır, exit 0 → mevcut davranış birebir sürer. Yalnız --seg cikis desteklenir (giriş havuzu
içerik-süzmeli/bitişik-değil; zaman-aralığı semantiği farklı — ayrı iş).

Env eşikleri: MITAS_DENSE_TARGET_DY=8  MITAS_DENSE_STATIC_DY=4  MITAS_DENSE_MAX_FPS=25
              MITAS_DENSE_MAX_FRAMES=3000  (kap: fps gerekirse düşürülür)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FFMPEG = os.environ.get("MITAS_FFMPEG", "ffmpeg")


def _env_f(ad: str, vars_: float) -> float:
    try:
        return float(os.environ.get(ad, "") or vars_)
    except ValueError:
        return vars_


def _acik() -> bool:
    return os.environ.get("MITAS_MASTER_DENSE", "1").strip().lower() not in ("0", "false", "off", "no")


def _frame_idx(p: Path) -> int | None:
    m = re.search(r"(\d+)$", p.stem)
    return int(m.group(1)) if m else None


def _measure_dy(frames: list[Path]) -> float:
    """Havuzda medyan |dy| (phaseCorrelate) — compositor'ün gördüğü sinyalin aynısı (POC birebir)."""
    import cv2
    import numpy as np
    if len(frames) < 3:
        return 0.0
    im0 = cv2.imread(str(frames[0]))
    if im0 is None:
        return 0.0
    h, w = im0.shape[:2]
    hann = cv2.createHanningWindow((w, h), cv2.CV_32F)
    prev = None
    dys: list[float] = []
    for f in frames[:60]:
        im = cv2.imread(str(f))
        if im is None or im.shape[:2] != (h, w):
            continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype("float32")
        if prev is not None:
            (_, dy), _ = cv2.phaseCorrelate(prev * hann, g * hann)
            dys.append(abs(float(dy)))
        prev = g
    import statistics
    return float(statistics.median(dys)) if dys else 0.0


def _yaz_manifest(frames_dir: Path, seg: str, veri: dict) -> None:
    veri["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (frames_dir / f"{seg}_jenerik_dense_manifest.json").write_text(
        json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")


def _temizle(d: Path) -> None:
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True, help="Database/<film> hub dizini")
    ap.add_argument("--video", required=True, help="kaynak video dosyası")
    ap.add_argument("--seg", default="cikis", choices=["cikis"])
    ap.add_argument("--win-start", type=float, required=True,
                    help="frames/<seg> penceresinin video-zamanı başlangıcı (sn)")
    ap.add_argument("--src-fps", type=float, default=1.5, help="seyrek çıkarım fps'i")
    a = ap.parse_args()

    clip = Path(a.clip)
    frames_dir = clip / "frames"
    pool = frames_dir / f"{a.seg}_jenerik"
    dense = frames_dir / f"{a.seg}_jenerik_dense"
    tmp = frames_dir / f".{a.seg}_jenerik_dense.tmp"

    TARGET_DY = _env_f("MITAS_DENSE_TARGET_DY", 8.0)
    STATIC_DY = _env_f("MITAS_DENSE_STATIC_DY", 4.0)
    MAX_FPS = _env_f("MITAS_DENSE_MAX_FPS", 25.0)
    MAX_FRAMES = int(_env_f("MITAS_DENSE_MAX_FRAMES", 3000))

    def biter(veri: dict, kod: int = 0) -> int:
        # SCROLL dışında bayat dense kalmasın: eski dense/tmp silinir → monitor havuza döner.
        if veri.get("mode") != "SCROLL":
            _temizle(dense)
        _temizle(tmp)
        try:
            _yaz_manifest(frames_dir, a.seg, veri)
        except OSError:
            pass
        print(json.dumps(veri, ensure_ascii=False))
        return kod

    try:
        if not _acik():
            return biter({"mode": "kapali"})
        video = Path(a.video)
        if not video.exists():
            return biter({"mode": "skip", "neden": "video-yok"})
        havuz = sorted(p for p in pool.glob("*.png")) if pool.is_dir() else []
        if len(havuz) < 5:
            return biter({"mode": "skip", "neden": "havuz-kucuk", "frames": len(havuz)})

        dy = _measure_dy(havuz)
        if dy < STATIC_DY:
            return biter({"mode": "STATIK", "dy": round(dy, 2), "frames": len(havuz)})

        idx = [i for i in (_frame_idx(p) for p in havuz) if i is not None]
        if not idx:
            return biter({"mode": "skip", "neden": "indeks-okunamadi"})
        i0, i1 = min(idx) - 1, max(idx) - 1                       # 1-tabanlı ad → 0-tabanlı
        t0 = a.win_start + i0 / a.src_fps
        t1 = a.win_start + (i1 + 1) / a.src_fps
        span = max(0.5, t1 - t0)

        dense_fps = min(MAX_FPS, max(a.src_fps, a.src_fps * dy / TARGET_DY))
        if span * dense_fps > MAX_FRAMES:                          # disk/süre kapı: fps'i düşür
            dense_fps = MAX_FRAMES / span
        if dense_fps < a.src_fps * 1.34:                           # kayda değer yoğunlaşma yoksa dokunma
            return biter({"mode": "skip", "neden": "yogunlasma-marjinal",
                          "dy": round(dy, 2), "fps": round(dense_fps, 2)})

        _temizle(tmp)
        tmp.mkdir(parents=True)
        r = subprocess.run(
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-ss", f"{t0:.3f}", "-i", str(video), "-t", f"{span:.3f}",
             "-vf", f"fps={dense_fps:.4f}", "-start_number", "1",
             str(tmp / "c_%05d.png")],
            capture_output=True, text=True, timeout=int(_env_f("MITAS_DENSE_FFMPEG_TIMEOUT", 480)))
        n = len(list(tmp.glob("*.png")))
        if r.returncode != 0 or n < max(5, len(havuz)):            # dense, seyrekten AZ olamaz
            return biter({"mode": "hata", "neden": "ffmpeg", "rc": r.returncode, "dense": n,
                          "err": (r.stderr or "")[-200:]})
        _temizle(dense)
        os.replace(tmp, dense)
        return biter({"mode": "SCROLL", "dy": round(dy, 2), "fps": round(dense_fps, 2),
                      "sparse": len(havuz), "dense": n, "t0": round(t0, 2), "t1": round(t1, 2),
                      "beklenen_dy": round(dy / (dense_fps / a.src_fps), 2)})
    except Exception as e:  # noqa: BLE001 — dense ASLA üst akışı bozmaz
        return biter({"mode": "hata", "neden": type(e).__name__, "err": str(e)[:200]})


if __name__ == "__main__":
    sys.exit(main())
