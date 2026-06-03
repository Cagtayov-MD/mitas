# -*- coding: utf-8 -*-
"""Paddle ile ALTYAZI tespiti: film gövdesini tara, ALT BANT'ta (subtitle bölgesi)
persistan yazı var mı → "film altyazılı mı?".

Altyazı KONUŞMADA olur (jenerik/sessizlik değil) → gövdeden örnek (intro/outro jenerik hariç).
Kaliteli/stabil ise PDF ses-bloğuna "altyazılıdır" eklenir.

ocr venv:
  venvs/ocr/Scripts/python.exe scripts/_subtitle_detect.py "<video>"
"""
import sys, json, subprocess, tempfile
from pathlib import Path
sys.path.insert(0, r"E:\MITAS")
sys.stdout.reconfigure(encoding="utf-8")
from core.pipelines.ocr.credit_experiment import PaddleOcrEngine

ROOT = Path(r"E:\MITAS")
FF = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"
FP = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffprobe.exe"

N = 60                # film gövdesinden örnek kare
SUB_THRESH = 0.20     # alt-bant yazı oranı bu üstündeyse → altyazılı


def duration(v: str) -> float:
    try:
        o = subprocess.run([str(FP), "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", v], capture_output=True, text=True).stdout.strip()
        return float(o)
    except Exception:
        return 0.0


def main():
    v = sys.argv[1]
    d = duration(v)
    a, b = 130.0, max(200.0, d - 240.0)          # gövde (açılış/kapanış jenerik hariç)
    times = [a + (b - a) * i / (N - 1) for i in range(N)] if b > a else [max(1.0, d * 0.5)]
    eng = PaddleOcrEngine()
    hits, total, samples = 0, 0, []
    with tempfile.TemporaryDirectory() as td:
        band = Path(td) / "band.png"
        for t in times:
            subprocess.run([str(FF), "-ss", f"{t:.1f}", "-i", v,
                            "-vf", "crop=iw:ih*0.20:0:ih*0.80",   # alt %20 bant
                            "-frames:v", "1", "-q:v", "3", "-y", str(band)], capture_output=True)
            if not band.exists():
                continue
            total += 1
            try:
                recs = eng.recognize(band, strategy="scan")
            except Exception:
                continue
            txt = [str(r.get("text", "")).strip() for r in recs if str(r.get("text", "")).strip()]
            chars = sum(len(x) for x in txt)
            # altyazı imzası: anlamlı uzunlukta (>=8 karakter), 1-4 satır (diyalog)
            if txt and chars >= 8 and len(txt) <= 4:
                hits += 1
                if len(samples) < 8:
                    samples.append(" ".join(txt)[:80])
    ratio = hits / max(1, total)
    altyazili = ratio >= SUB_THRESH
    if ratio >= 0.40 or ratio <= 0.05:
        guven = "yüksek"
    elif ratio >= 0.30 or ratio <= 0.12:
        guven = "orta"
    else:
        guven = "düşük"
    print(json.dumps({"altyazili": altyazili, "oran": round(ratio, 3), "hits": hits, "total": total,
                      "guven": guven, "ornekler": samples}, ensure_ascii=False))


if __name__ == "__main__":
    main()
