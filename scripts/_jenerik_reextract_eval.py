# -*- coding: utf-8 -*-
"""Etiketli set için frames/cikis YENİDEN ÇIKAR — SABİT 240s pencere (= etiket-koruyan).

Altın-set (jenerik_verify_full60.csv) etiketleri, ORİJİNAL frames/cikis'in SABİT-pencere
çıkarımına (son `--tail` sn @ fps2 = 480 kare, c_0001.png..) göre yapılmıştı. Aynı sabit
pencereyle yeniden çıkarınca kare-pozisyonları (dolayısıyla region=[a-b] etiketleri) KORUNUR.
Credit-detect KULLANILMAZ (o pencereyi kaydırır → etiket bozulur).

KULLANIM:
  # 1) DOĞRULA (kare'si OLAN bir filmi yeniden çıkar, mevcutla karşılaştır — reproduksiyon birebir mi?):
  python scripts\_jenerik_reextract_eval.py --validate-film "TAPU 2000-0563-1-0000-00-1" --validate-source "W:\...\...TAPU.mp4"
  # 2) worklist'i çıkar (W: indeksinden eşleşen eksik filmler):
  python scripts\_jenerik_reextract_eval.py            # outputs/.../_reextract_worklist.json okur
Çıktı: outputs/jenerik_start_eval/reframes/<safe>/cikis/c_%04d.png + _frames_map.json {film: cikis_dir}
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"E:\MITAS\outputs\jenerik_start_eval")
REFRAMES = OUT / "reframes"
DB = Path(r"E:\MITAS\Database")
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
TAIL = 240.0
FPS = 2.0


def safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)[:60]


def dur_sec(video: Path) -> float | None:
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1", str(video)],
            capture_output=True, text=True, timeout=120).stdout.strip()
        return float(out)
    except Exception:
        return None


def extract(video: Path, dst: Path, tail: float = TAIL, fps: float = FPS) -> tuple[int, float | None]:
    dst.mkdir(parents=True, exist_ok=True)
    for p in dst.glob("c_*.png"):
        p.unlink()
    d = dur_sec(video)
    if not d:
        return 0, None
    start = max(0.0, d - tail)
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-ss", str(start), "-i", str(video), "-t", str(tail),
           "-vf", f"fps={fps}", str(dst / "c_%04d.png")]
    try:
        subprocess.run(cmd, timeout=1800)
    except Exception as e:
        print(f"    ffmpeg hata: {e}")
    return len(list(dst.glob("c_*.png"))), d


def dhash8(path: Path):
    import cv2
    import numpy as np
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    s = cv2.resize(img, (9, 8), interpolation=cv2.INTER_AREA)
    return (s[:, 1:] > s[:, :-1]).tobytes()


def _ham(a: bytes, b: bytes) -> int:
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))


def validate(film: str, source: str) -> None:
    existing = sorted((DB / film / "frames" / "cikis").glob("c_*.png"))
    if not existing:
        print(f"DOĞRULAMA YAPILAMAZ: {film} mevcut kare yok.")
        return
    tmp = REFRAMES / ("_VALIDATE_" + safe(film)) / "cikis"
    n, d = extract(Path(source), tmp)
    re_ = sorted(tmp.glob("c_*.png"))
    print(f"DOĞRULAMA {film}: mevcut={len(existing)} yeni={len(re_)} dur={d}")
    common = min(len(existing), len(re_))
    ok = abs(len(existing) - len(re_)) <= 1 and common > 0
    checks = [0, common // 4, common // 2, 3 * common // 4, common - 1] if common else []
    for i in checks:
        he, hr = dhash8(existing[i]), dhash8(re_[i])
        ham = _ham(he, hr) if (he and hr) else -1
        print(f"  pos {i:4d}: {existing[i].name} vs {re_[i].name} -> {'AYNI' if ham == 0 else f'ham={ham}'}")
        if ham > 5:
            ok = False
    print("SONUÇ:", "PASS — reproduksiyon birebir/yakın, etiketler korunuyor" if ok
          else "FAIL — pencere uyuşmuyor, fixed-window varsayımı bu filmde GEÇERSİZ")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worklist", default=str(OUT / "_reextract_worklist.json"))
    ap.add_argument("--validate-film", default=None)
    ap.add_argument("--validate-source", default=None)
    ap.add_argument("--tail", type=float, default=TAIL)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    if args.validate_film and args.validate_source:
        validate(args.validate_film, args.validate_source)
        return 0

    wl = json.loads(Path(args.worklist).read_text(encoding="utf-8"))
    if args.limit:
        wl = wl[: args.limit]
    fmap: dict[str, str] = {}
    for i, w in enumerate(wl):
        film, src = w["film"], Path(w["source"])
        if not src.exists():
            print(f"  [{i+1}] KAYNAK YOK: {film}")
            continue
        dst = REFRAMES / safe(film) / "cikis"
        n, d = extract(src, dst, tail=args.tail)
        if n:
            fmap[film] = str(dst)
            print(f"  [{i+1}/{len(wl)}] {film[:40]:40s} {n} kare (dur={d:.0f}s)")
        else:
            print(f"  [{i+1}/{len(wl)}] {film[:40]:40s} ÇIKARILAMADI")
    (OUT / "_frames_map.json").write_text(json.dumps(fmap, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(fmap)} film yeniden çıkarıldı -> {REFRAMES}")
    print(f"frames-map -> {OUT / '_frames_map.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
