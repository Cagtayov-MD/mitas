"""Qwen3-ASR vs MITAS pipeline karşılaştırma.

Her WAV dosyasını iki modelle transkribe eder, Markdown rapor üretir.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


CLIPS = [
    {"name": "azeri_spiker",        "wav": "outputs/azeri_comparison/azeri_spiker.wav",        "label": "Azeri Spikerin Duygusal Anları (36sn tam)"},
    {"name": "komedixana_5dk",      "wav": "outputs/azeri_comparison/komedixana_5dk.wav",      "label": "Komedixana bölüm (ilk 5 dk)"},
    {"name": "turkce_azeri_5dk",    "wav": "outputs/azeri_comparison/turkce_azeri_ders_5dk.wav","label": "Türkçe-Azerice Ders (ilk 5 dk)"},
]


def run_qwen(model, wav_path: str, language=None) -> dict:
    t0 = time.perf_counter()
    out = model.transcribe(audio=wav_path, language=language)
    elapsed = round(time.perf_counter() - t0, 2)
    text = out[0].text.strip() if out else ""
    lang = out[0].language if out else "?"
    return {"text": text, "detected_language": lang, "decode_seconds": elapsed}


def run_mitas(wav_path: str, profile: str = "fast_with_fallback") -> dict:
    from core.pipelines.asr.transcribe import transcribe
    t0 = time.perf_counter()
    result = transcribe(Path(wav_path), profile=profile)
    elapsed = round(time.perf_counter() - t0, 2)
    return {
        "text": result.clean_transcript,
        "model_used": result.model_name,
        "profile_used": result.profile_used,
        "fallback_triggered": result.fallback_triggered,
        "decode_seconds": result.timing.decode_seconds,
        "wall_seconds": elapsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "azeri_comparison")
    parser.add_argument("--qwen-language", default="auto",
                        help="'auto' veya 'Azerbaijani' / 'Turkish' gibi zorla")
    parser.add_argument("--mitas-profile", default="fast_with_fallback")
    parser.add_argument("--skip-mitas", action="store_true")
    parser.add_argument("--skip-qwen", action="store_true")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    forced_lang = None if args.qwen_language.lower() == "auto" else args.qwen_language

    # ── Qwen model yükle ────────────────────────────────────────────────────
    qwen_model = None
    if not args.skip_qwen:
        import torch
        from qwen_asr import Qwen3ASRModel
        print("Qwen3-ASR yükleniyor…")
        t0 = time.perf_counter()
        qwen_model = Qwen3ASRModel.from_pretrained(
            "Qwen/Qwen3-ASR-1.7B",
            dtype=torch.bfloat16,
            device_map="cuda:0",
            max_inference_batch_size=8,
            max_new_tokens=2048,
        )
        print(f"Qwen yüklendi ({time.perf_counter()-t0:.1f}s)\n")

    # ── Her klip için iki model ─────────────────────────────────────────────
    all_results = []

    for clip in CLIPS:
        wav = str(ROOT / clip["wav"])
        if not Path(wav).exists():
            print(f"ATLA (dosya yok): {wav}")
            continue

        print(f"\n{'='*60}")
        print(f"Klip : {clip['label']}")

        row: dict = {"name": clip["name"], "label": clip["label"], "wav": wav}

        if qwen_model:
            print("  → Qwen3-ASR…")
            row["qwen"] = run_qwen(qwen_model, wav, forced_lang)
            print(f"     Dil: {row['qwen']['detected_language']}  {row['qwen']['decode_seconds']}s")
            print(f"     {row['qwen']['text'][:300]}{'…' if len(row['qwen']['text'])>300 else ''}")

        if not args.skip_mitas:
            print(f"  → MITAS ({args.mitas_profile})…")
            try:
                row["mitas"] = run_mitas(wav, args.mitas_profile)
                print(f"     Model: {row['mitas']['model_used']}  fallback={row['mitas']['fallback_triggered']}  {row['mitas']['decode_seconds']}s")
                print(f"     {row['mitas']['text'][:300]}{'…' if len(row['mitas']['text'])>300 else ''}")
            except Exception as e:
                row["mitas"] = {"error": str(e)}
                print(f"     HATA: {e}")

        all_results.append(row)

    # ── JSON ────────────────────────────────────────────────────────────────
    json_path = args.output_dir / "comparison_results.json"
    json_path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Markdown ────────────────────────────────────────────────────────────
    md_lines = [
        "# Qwen3-ASR vs MITAS Pipeline — Azeri/Türkçe Karşılaştırma",
        "",
        f"Qwen language: `{forced_lang or 'auto-detect'}`  |  MITAS profile: `{args.mitas_profile}`",
        "",
    ]

    for row in all_results:
        md_lines += [f"## {row['label']}", ""]

        qwen = row.get("qwen", {})
        mitas = row.get("mitas", {})

        md_lines += [
            "### Qwen3-ASR-1.7B",
            f"**Tespit edilen dil:** `{qwen.get('detected_language','—')}`  |  **Süre:** `{qwen.get('decode_seconds','—')}s`",
            "",
            f"```\n{qwen.get('text','(boş)')}\n```",
            "",
            "### MITAS (fast_with_fallback)",
            f"**Model:** `{mitas.get('model_used','—')}`  |  "
            f"**Fallback:** `{mitas.get('fallback_triggered','—')}`  |  "
            f"**Süre:** `{mitas.get('decode_seconds','—')}s`",
            "",
            f"```\n{mitas.get('text', mitas.get('error','(boş)'))}\n```",
            "",
            "---",
            "",
        ]

    md_path = args.output_dir / "comparison_results.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"JSON : {json_path}")
    print(f"MD   : {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
