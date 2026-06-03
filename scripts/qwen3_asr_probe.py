"""Qwen3-ASR ile F:/ root WAV dosyalarını transkribe et — dil auto-detect.

Uzun dosyalar için ilk SEGMENT_SEC saniyelik dilimi alır,
ardından tam dosyayı çalıştırır.
"""

from __future__ import annotations

import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import argparse
import json
import sys
import time
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FILES = [
    "F:/01_01.wav",
    "F:/01_02.wav",
    "F:/01_03.wav",
    "F:/01_04.wav",
]


def load_segment(path: str, start_sec: float = 0.0, duration_sec: float | None = None) -> tuple[np.ndarray, int]:
    info = sf.info(path)
    sr = info.samplerate
    start_frame = int(start_sec * sr)
    frames = int(duration_sec * sr) if duration_sec else -1

    data, _ = sf.read(path, start=start_frame, frames=frames, dtype="float32", always_2d=True)
    # stereo → mono
    if data.shape[1] > 1:
        data = data.mean(axis=1)
    else:
        data = data[:, 0]
    return data, sr


def save_tmp_wav(data: np.ndarray, sr: int) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, data, sr, subtype="PCM_16")
    return tmp.name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", default=DEFAULT_FILES)
    parser.add_argument("--segment", type=float, default=60.0,
                        help="Her dosyadan kaç saniye işlenecek (0 = tam dosya)")
    parser.add_argument("--language", default="auto",
                        help="'auto' = otomatik tespit, ya da 'Turkish', 'Arabic' vb.")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs" / "qwen3_asr_probe")
    args = parser.parse_args()

    import torch
    from qwen_asr import Qwen3ASRModel

    forced_lang = None if args.language.lower() == "auto" else args.language

    print(f"Model yükleniyor…")
    t0 = time.perf_counter()
    model = Qwen3ASRModel.from_pretrained(
        "Qwen/Qwen3-ASR-1.7B",
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=8,
        max_new_tokens=1024,
    )
    print(f"Yüklendi ({time.perf_counter()-t0:.1f}s)\n")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for fpath in args.files:
        p = Path(fpath)
        if not p.exists():
            print(f"ATLA: {fpath} bulunamadı")
            continue

        info = sf.info(str(p))
        total_dur = info.duration
        seg_dur = args.segment if args.segment > 0 else total_dur
        seg_dur = min(seg_dur, total_dur)

        print(f"{'='*55}")
        print(f"Dosya  : {p.name}  ({total_dur:.1f}s toplam, {seg_dur:.1f}s işlenecek)")

        data, sr = load_segment(str(p), 0.0, seg_dur)
        tmp = save_tmp_wav(data, sr)

        t1 = time.perf_counter()
        out = model.transcribe(audio=tmp, language=forced_lang)
        elapsed = round(time.perf_counter() - t1, 2)

        Path(tmp).unlink(missing_ok=True)

        text = out[0].text.strip() if out else ""
        lang = out[0].language if out else "?"
        rtf = round(elapsed / seg_dur, 3)

        safe_text = text.encode("utf-8", errors="replace").decode("ascii", errors="replace")
        print(f"Dil    : {lang}")
        print(f"RTF    : {rtf}  ({elapsed}s decode / {seg_dur}s ses)")
        print(f"Metin  :\n{safe_text}\n")

        results.append({
            "file": p.name,
            "total_duration": round(total_dur, 1),
            "segment_duration": round(seg_dur, 1),
            "detected_language": lang,
            "rtf": rtf,
            "decode_seconds": elapsed,
            "text": text,
        })

    out_path = args.output_dir / "probe_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSonuçlar: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
