"""Benchmark MITAS MT candidates on an EN->TR JSONL eval set."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import gc
import json
import os
from pathlib import Path
import re
import statistics
from time import perf_counter
from typing import Any

import ctranslate2
import sacrebleu
from transformers import AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TORCH_DLL_DIRS = (
    PROJECT_ROOT / "venvs" / "asr" / "Lib" / "site-packages" / "torch" / "lib",
    PROJECT_ROOT / "venvs" / "translate" / "Lib" / "site-packages" / "torch" / "lib",
)
_DLL_HANDLES = []
for _dll_dir in _TORCH_DLL_DIRS:
    if _dll_dir.exists():
        _DLL_HANDLES.append(os.add_dll_directory(str(_dll_dir)))
        os.environ["PATH"] = f"{_dll_dir}{os.pathsep}{os.environ.get('PATH', '')}"


MODELS_ROOT = PROJECT_ROOT / "models" / "translate"
SNAPSHOT_ROOT = MODELS_ROOT / "_hf_snapshots"
DEFAULT_EVAL = PROJECT_ROOT / "data" / "translate_eval" / "flores_en_tr_100.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "outputs" / "translate_eval"
DEFAULT_DOC = PROJECT_ROOT / "docs" / "MITAS_MT_Benchmark_v0_2_Rapor.md"


@dataclass(frozen=True)
class BenchModel:
    key: str
    display_name: str
    kind: str
    hf_snapshot_dir: str
    ct2_dir: str


MODELS: dict[str, BenchModel] = {
    "nllb_3b": BenchModel(
        key="nllb_3b",
        display_name="NLLB 3.3B CT2",
        kind="nllb",
        hf_snapshot_dir="nllb-200-3.3B-hf",
        ct2_dir="nllb-200-3.3B-ct2-int8",
    ),
    "nllb_1b": BenchModel(
        key="nllb_1b",
        display_name="NLLB 1.3B distilled CT2",
        kind="nllb",
        hf_snapshot_dir="nllb-200-distilled-1.3B-hf",
        ct2_dir="nllb-200-distilled-1.3B-ct2-int8",
    ),
    "opus": BenchModel(
        key="opus",
        display_name="OPUS-MT-TC-BIG EN-TR CT2",
        kind="opus",
        hf_snapshot_dir="opus-mt-tc-big-en-tr-hf",
        ct2_dir="opus-mt-tc-big-en-tr-ct2-int8",
    ),
}


def read_eval(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not row.get("src") or not row.get("ref"):
            raise ValueError(f"Empty src/ref at {path}:{line_number}")
        rows.append(row)
    return rows


def detect_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def translate_model(model: BenchModel, rows: list[dict[str, Any]], *, device: str, beam_size: int) -> tuple[list[str], list[float]]:
    snapshot_path = SNAPSHOT_ROOT / model.hf_snapshot_dir
    ct2_path = MODELS_ROOT / model.ct2_dir
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Missing HF snapshot: {snapshot_path}")
    if not (ct2_path / "model.bin").exists():
        raise FileNotFoundError(f"Missing CT2 model.bin: {ct2_path / 'model.bin'}")

    translator = ctranslate2.Translator(str(ct2_path), device=device)
    tokenizer = AutoTokenizer.from_pretrained(str(snapshot_path), src_lang="eng_Latn", local_files_only=True)
    hypotheses: list[str] = []
    latencies_ms: list[float] = []
    try:
        for index, row in enumerate(rows, 1):
            started = perf_counter()
            if model.kind == "nllb":
                text = translate_one_nllb(translator, tokenizer, row["src"], beam_size=beam_size)
            elif model.kind == "opus":
                text = translate_one_opus(translator, tokenizer, row["src"], beam_size=beam_size)
            else:
                raise ValueError(f"Unsupported model kind: {model.kind}")
            latencies_ms.append((perf_counter() - started) * 1000)
            hypotheses.append(text)
            if index % 10 == 0:
                print(f"[{model.key}] translated {index}/{len(rows)}", flush=True)
    finally:
        del translator
        del tokenizer
        gc.collect()
    return hypotheses, latencies_ms


def translate_one_nllb(translator: ctranslate2.Translator, tokenizer: Any, source: str, *, beam_size: int) -> str:
    source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(source))
    result = translator.translate_batch(
        [source_tokens],
        target_prefix=[["tur_Latn"]],
        beam_size=beam_size,
        max_batch_size=1,
    )[0]
    target_tokens = result.hypotheses[0][1:]
    target_ids = tokenizer.convert_tokens_to_ids(target_tokens)
    return clean_text(tokenizer.decode(target_ids, skip_special_tokens=True))


def translate_one_opus(translator: ctranslate2.Translator, tokenizer: Any, source: str, *, beam_size: int) -> str:
    source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(source))
    result = translator.translate_batch([source_tokens], beam_size=beam_size, max_batch_size=1)[0]
    target_ids = tokenizer.convert_tokens_to_ids(result.hypotheses[0])
    return clean_text(tokenizer.decode(target_ids, skip_special_tokens=True))


def clean_text(text: str) -> str:
    return re.sub(r"^>>\w+<<\s*", "", text).strip()


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def compute_comet_scores(srcs: list[str], refs: list[str], hypotheses_by_model: dict[str, list[str]]) -> dict[str, float]:
    from comet import download_model, load_from_checkpoint

    checkpoint = download_model("Unbabel/wmt22-comet-da")
    model = load_from_checkpoint(checkpoint)
    scores: dict[str, float] = {}
    for key, hypotheses in hypotheses_by_model.items():
        data = [
            {"src": src, "mt": hyp, "ref": ref}
            for src, hyp, ref in zip(srcs, hypotheses, refs)
        ]
        prediction = model.predict(data, batch_size=8, gpus=0)
        scores[key] = round(float(statistics.mean(prediction.scores)) * 100.0, 4)
    return scores


def compute_scores(
    srcs: list[str],
    refs: list[str],
    hypotheses_by_model: dict[str, list[str]],
    latencies_by_model: dict[str, list[float]],
) -> dict[str, Any]:
    comet_scores = compute_comet_scores(srcs, refs, hypotheses_by_model)
    scores: dict[str, Any] = {}
    for key, hypotheses in hypotheses_by_model.items():
        chrf = sacrebleu.corpus_chrf(hypotheses, [refs], word_order=2)
        latencies = latencies_by_model[key]
        scores[key] = {
            "display_name": MODELS[key].display_name,
            "comet_22": comet_scores[key],
            "chrf_pp": round(float(chrf.score), 4),
            "p50_ms": round(percentile(latencies, 0.50), 1),
            "p95_ms": round(percentile(latencies, 0.95), 1),
            "mean_ms": round(statistics.mean(latencies), 1),
        }
    return scores


def write_translations(
    path: Path,
    rows: list[dict[str, Any]],
    hypotheses_by_model: dict[str, list[str]],
    latencies_by_model: dict[str, list[float]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row_index, row in enumerate(rows):
            payload: dict[str, Any] = {
                "index": row["index"],
                "src": row["src"],
                "ref": row["ref"],
                "domain": row.get("domain"),
            }
            for key in MODELS:
                payload[f"{key}_hyp"] = hypotheses_by_model[key][row_index]
                payload[f"{key}_latency_ms"] = round(latencies_by_model[key][row_index], 1)
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_scores(path: Path, scores: dict[str, Any], *, eval_path: Path, row_count: int, device: str) -> None:
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "eval_path": str(eval_path),
        "row_count": row_count,
        "device": device,
        "models": scores,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(
    path: Path,
    rows: list[dict[str, Any]],
    scores: dict[str, Any],
    hypotheses_by_model: dict[str, list[str]],
) -> None:
    lines = [
        "# MITAS MT Benchmark v0.2",
        "",
        f"> Tarih: {datetime.now(timezone.utc).date().isoformat()}",
        f"> Eval: FLORES EN->TR devtest slice, {len(rows)} cumle",
        "",
        "## Skorlar",
        "",
        "| Model | COMET-22 | CHRF++ | P50 ms | P95 ms | Mean ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key in MODELS:
        item = scores[key]
        lines.append(
            f"| {item['display_name']} | {item['comet_22']:.4f} | {item['chrf_pp']:.4f} | "
            f"{item['p50_ms']:.1f} | {item['p95_ms']:.1f} | {item['mean_ms']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## Ornekler",
            "",
            "| # | Source | Reference | NLLB 3.3B | NLLB 1.3B | OPUS |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for sample_index, row in enumerate(rows[:10]):
        lines.append(
            "| "
            f"{row['index']} | {md_cell(row['src'])} | {md_cell(row['ref'])} | "
            f"{md_cell(hypotheses_by_model['nllb_3b'][sample_index])} | "
            f"{md_cell(hypotheses_by_model['nllb_1b'][sample_index])} | "
            f"{md_cell(hypotheses_by_model['opus'][sample_index])} |"
        )
    lines.extend(
        [
            "",
            "## Notlar",
            "",
            "- COMET-22 skoru `Unbabel/wmt22-comet-da` ile hesaplandi ve 0-100 olceginde raporlandi.",
            "- CHRF++ `sacrebleu.corpus_chrf(..., word_order=2)` ile hesaplandi.",
            "- Bu benchmark TRT-domain degildir; Faz A karar setidir.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--beam-size", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = read_eval(args.eval)
    srcs = [row["src"] for row in rows]
    refs = [row["ref"] for row in rows]
    device = detect_device(args.device)
    hypotheses_by_model: dict[str, list[str]] = {}
    latencies_by_model: dict[str, list[float]] = {}

    for key, model in MODELS.items():
        print(f"[benchmark] {key} on {device}", flush=True)
        hypotheses, latencies = translate_model(model, rows, device=device, beam_size=args.beam_size)
        hypotheses_by_model[key] = hypotheses
        latencies_by_model[key] = latencies

    translations_path = args.out / "translations.jsonl"
    scores_path = args.out / "scores.json"
    write_translations(translations_path, rows, hypotheses_by_model, latencies_by_model)
    print("[benchmark] computing COMET + CHRF", flush=True)
    scores = compute_scores(srcs, refs, hypotheses_by_model, latencies_by_model)
    write_scores(scores_path, scores, eval_path=args.eval, row_count=len(rows), device=device)
    write_markdown_report(args.doc, rows, scores, hypotheses_by_model)
    print(f"[ok] translations -> {translations_path}", flush=True)
    print(f"[ok] scores -> {scores_path}", flush=True)
    print(f"[ok] report -> {args.doc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
