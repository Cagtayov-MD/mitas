"""MITAS pipeline transkripsiyon — karşılaştırma için."""

from __future__ import annotations

import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.pipelines.asr.transcribe import transcribe  # noqa: E402

CLIPS = [
    {"name": "azeri_spiker",     "wav": "outputs/azeri_comparison/azeri_spiker.wav",         "label": "Azeri Spikerin Duygusal Anları (36sn)"},
    {"name": "komedixana_5dk",   "wav": "outputs/azeri_comparison/komedixana_5dk.wav",       "label": "Komedixana bölüm (ilk 5 dk)"},
    {"name": "turkce_azeri_5dk", "wav": "outputs/azeri_comparison/turkce_azeri_ders_5dk.wav","label": "Türkçe-Azerice Ders (ilk 5 dk)"},
]

OUTPUT = ROOT / "outputs" / "azeri_comparison" / "mitas_results.json"


def main() -> int:
    results = []
    for clip in CLIPS:
        wav = ROOT / clip["wav"]
        if not wav.exists():
            print(f"ATLA: {wav}")
            continue
        print(f"\n{clip['label']}")
        t0 = time.perf_counter()
        try:
            r = transcribe(wav, profile="fast_with_fallback")
            wall = round(time.perf_counter() - t0, 2)
            row = {
                "name": clip["name"],
                "label": clip["label"],
                "model_used": r.model_name,
                "profile_used": r.profile_used,
                "fallback_triggered": r.fallback_triggered,
                "decode_seconds": r.timing.decode_seconds,
                "wall_seconds": wall,
                "text": r.clean_transcript,
            }
        except Exception as e:
            row = {"name": clip["name"], "label": clip["label"], "error": str(e)}
        results.append(row)
        try:
            txt = row.get("text", row.get("error", ""))
            safe = txt[:300].encode("utf-8", errors="replace").decode("ascii", errors="replace")
            print(f"  model={row.get('model_used','ERR')}  fallback={row.get('fallback_triggered','?')}  {row.get('decode_seconds','?')}s")
            print(f"  {safe}")
        except Exception:
            pass

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSonuç: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
