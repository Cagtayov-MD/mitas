"""Standalone Qwen3-ASR benchmark against MediaSpeech Turkish (smoke-20).

Karşılaştırma: turbo WER=0.185 | large-v3 WER=0.178 (mevcut baseline)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOKEN_RE = re.compile(r"[0-9a-zA-ZçğıöşüÇĞİÖŞÜ]+")

BASELINE = {
    "turbo":    {"avg_wer": 0.185},
    "large-v3": {"avg_wer": 0.178},
}


# ── text utils ───────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    return " ".join(TOKEN_RE.findall(text.casefold()))


def tokenize(text: str) -> list[str]:
    n = normalize(text)
    return n.split() if n else []


def edit_distance(a: list, b: list) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ai in enumerate(a, 1):
        curr = [i]
        for j, bj in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (0 if ai == bj else 1)))
        prev = curr
    return prev[-1]


def wer(ref: list[str], hyp: list[str]) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


def cer(ref_text: str, hyp_text: str) -> float:
    rc = list(normalize(ref_text).replace(" ", ""))
    hc = list(normalize(hyp_text).replace(" ", ""))
    if not rc:
        return 0.0 if not hc else 1.0
    return edit_distance(rc, hc) / len(rc)


# ── candidate selection (same logic as asr_mediaspeech_benchmark.py) ─────────

def read_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def collect_candidates(dataset_dir: Path, limit: int, seed: int) -> list[dict]:
    rows: list[dict] = []
    for txt in sorted(dataset_dir.glob("*.txt")):
        wav = txt.with_suffix(".wav")
        if not wav.exists():
            continue
        ref = txt.read_text(encoding="utf-8").strip()
        words = tokenize(ref)
        if not (12 <= len(words) <= 45):
            continue
        dur = read_duration(wav)
        if not (8.0 <= dur <= 15.5):
            continue
        rows.append({"id": txt.stem, "wav": str(wav), "duration": round(dur, 3),
                     "word_count": len(words), "reference": ref})
    if len(rows) <= limit:
        return rows
    rng = random.Random(seed)
    return sorted(rng.sample(rows, limit), key=lambda x: x["id"])


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen3-ASR smoke-20 benchmark")
    parser.add_argument("--dataset-dir", type=Path,
                        default=ROOT / "cache" / "external_datasets" / "mediaspeech_tr" / "TR")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "outputs" / "qwen3_asr_benchmark")
    parser.add_argument("--model", default="Qwen/Qwen3-ASR-1.7B")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260514)
    parser.add_argument("--language", default="Turkish",
                        help="Force language (e.g. 'Turkish') or 'auto' for detection")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    import torch
    from qwen_asr import Qwen3ASRModel

    forced_lang = None if args.language.lower() == "auto" else args.language

    print(f"Model       : {args.model}")
    print(f"Language    : {forced_lang or 'auto-detect'}")
    print(f"Dataset     : {args.dataset_dir}")
    print()

    print("Model yükleniyor (ilk çalıştırmada indirilir ~3.4 GB)…")
    load_start = time.perf_counter()
    model = Qwen3ASRModel.from_pretrained(
        args.model,
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=args.batch_size,
        max_new_tokens=512,
    )
    print(f"Model yüklendi ({time.perf_counter() - load_start:.1f}s)\n")

    candidates = collect_candidates(args.dataset_dir, args.limit, args.seed)
    if not candidates:
        print("HATA: Aday ses dosyası bulunamadı.", file=sys.stderr)
        return 1
    print(f"{len(candidates)} aday yüklendi.\n")

    results: list[dict] = []
    total_start = time.perf_counter()

    for i, cand in enumerate(candidates, 1):
        t0 = time.perf_counter()
        out = model.transcribe(audio=cand["wav"], language=forced_lang)
        elapsed = round(time.perf_counter() - t0, 3)

        hyp_text = out[0].text.strip() if out else ""
        detected = out[0].language if out else "?"

        w = round(wer(tokenize(cand["reference"]), tokenize(hyp_text)), 4)
        c = round(cer(cand["reference"], hyp_text), 4)

        results.append({
            "id": cand["id"],
            "duration": cand["duration"],
            "wall_seconds": elapsed,
            "detected_language": detected,
            "wer": w,
            "cer": c,
            "reference": cand["reference"],
            "hypothesis": hyp_text,
        })
        rtf = round(elapsed / cand["duration"], 3) if cand["duration"] else 0
        print(f"[{i:02d}/{len(candidates)}] {cand['id']}  WER={w:.4f}  CER={c:.4f}  lang={detected}  RTF={rtf}")

    total_wall = round(time.perf_counter() - total_start, 3)
    avg_wer = round(sum(r["wer"] for r in results) / len(results), 4)
    avg_cer = round(sum(r["cer"] for r in results) / len(results), 4)

    summary = {
        "model": args.model,
        "language_forced": forced_lang,
        "count": len(results),
        "avg_wer": avg_wer,
        "avg_cer": avg_cer,
        "total_wall_seconds": total_wall,
        "baseline_turbo_wer": BASELINE["turbo"]["avg_wer"],
        "baseline_large_v3_wer": BASELINE["large-v3"]["avg_wer"],
        "delta_vs_turbo": round(avg_wer - BASELINE["turbo"]["avg_wer"], 4),
        "delta_vs_large_v3": round(avg_wer - BASELINE["large-v3"]["avg_wer"], 4),
    }

    md = f"""# Qwen3-ASR Benchmark — MediaSpeech TR smoke-20

Model: `{args.model}`
Language forced: `{forced_lang or 'auto-detect'}`
Candidates: `{len(results)}` | seed=`{args.seed}`

## Summary

| | WER | CER |
|---|---:|---:|
| **Qwen3-ASR** | **`{avg_wer}`** | **`{avg_cer}`** |
| Baseline turbo | `{BASELINE["turbo"]["avg_wer"]}` | — |
| Baseline large-v3 | `{BASELINE["large-v3"]["avg_wer"]}` | — |

Δ vs turbo: `{summary["delta_vs_turbo"]:+.4f}` &nbsp; Δ vs large-v3: `{summary["delta_vs_large_v3"]:+.4f}`
_(negatif = Qwen3-ASR daha iyi)_

Total wall: `{total_wall}s`

## Per-Sample

| ID | WER | CER | Lang | Wall s | RTF |
|---|---:|---:|:---:|---:|---:|
"""
    for r in results:
        rtf = round(r["wall_seconds"] / r["duration"], 3) if r["duration"] else 0
        md += (f"| `{r['id']}` | `{r['wer']}` | `{r['cer']}` | "
               f"`{r['detected_language']}` | `{r['wall_seconds']}` | `{rtf}` |\n")

    md += "\n## Notes\n\n- Baseline WER değerleri `asr_mediaspeech_benchmark.py` smoke-20 sonuçlarından.\n"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "benchmark_results.json"
    md_path   = args.output_dir / "benchmark_results.md"
    json_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")

    print(f"\n{'='*55}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nRapor: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
