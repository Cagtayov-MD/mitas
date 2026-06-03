"""
LLaVA-NeXT-Video-7B probe script for film end-credit transcription.
Reads frame folders, runs model ONCE per video, writes raw output to _vlm_probe/.
"""
import os
import sys
import time
import glob
import numpy as np
from pathlib import Path

# Must set BEFORE any HF import
os.environ["HF_HOME"] = r"E:\MITAS\hf-cache"
os.environ["HF_HUB_OFFLINE"] = "1"

import torch
from PIL import Image
from transformers import LlavaNextVideoProcessor, LlavaNextVideoForConditionalGeneration

MODEL_ID = "llava-hf/LLaVA-NeXT-Video-7B-hf"
OUT_DIR = Path(r"E:\MITAS\_vlm_probe")

PROMPT = (
    "bunlar cikis jenerigidir. Ekranda YAZAN her seyi AYNEN, oldugu gibi, satir satir yaz. "
    "Bicim degistirme, yorum katma, uzun uzun dusunme. "
    "Hicbir yazi yoksa veya okuyamiyorsan [okunamadi] yaz. /no_think"
)

VIDEOS = [
    {
        "folder": r"E:\MITAS\_vlm_probe\pages2_ahlat",
        "out": OUT_DIR / "out_llava_ahlat.txt",
    },
    {
        "folder": r"E:\MITAS\_vlm_probe\pages2_anjelik",
        "out": OUT_DIR / "out_llava_anjelik.txt",
    },
]


def load_frames(folder: str) -> np.ndarray:
    """Load sorted *.jpg frames from folder, return (N, H, W, 3) uint8 array."""
    paths = sorted(glob.glob(os.path.join(folder, "*.jpg")))
    if not paths:
        raise FileNotFoundError(f"No .jpg files in {folder}")
    frames = []
    for p in paths:
        img = Image.open(p).convert("RGB")
        frames.append(np.array(img, dtype=np.uint8))
    return np.stack(frames, axis=0)  # (N, H, W, 3)


def vram_used_mb() -> float:
    try:
        return torch.cuda.memory_allocated() / 1024**2
    except Exception:
        return -1.0


def peak_vram_mb() -> float:
    try:
        return torch.cuda.max_memory_allocated() / 1024**2
    except Exception:
        return -1.0


def main():
    print(f"[llava_probe] Python {sys.version}", flush=True)
    print(f"[llava_probe] torch {torch.__version__}, CUDA available: {torch.cuda.is_available()}", flush=True)
    if torch.cuda.is_available():
        print(f"[llava_probe] GPU: {torch.cuda.get_device_name(0)}", flush=True)
        print(f"[llava_probe] Free VRAM before load: "
              f"{(torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated()) / 1024**2:.0f} MB",
              flush=True)

    # --- Load model + processor ---
    print(f"[llava_probe] Loading processor from {MODEL_ID} ...", flush=True)
    t0 = time.time()
    processor = LlavaNextVideoProcessor.from_pretrained(MODEL_ID)
    print(f"[llava_probe] Loading model ...", flush=True)
    model = LlavaNextVideoForConditionalGeneration.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )
    model.to("cuda")
    model.eval()
    load_time = time.time() - t0
    print(f"[llava_probe] Model loaded in {load_time:.1f}s. Peak VRAM: {peak_vram_mb():.0f} MB", flush=True)

    # --- Run inference per video ---
    for vid in VIDEOS:
        folder = vid["folder"]
        out_path = vid["out"]

        print(f"\n[llava_probe] === Video: {folder} ===", flush=True)
        frames = load_frames(folder)
        num_frames = frames.shape[0]
        print(f"[llava_probe] Loaded {num_frames} frames, shape {frames.shape}", flush=True)

        # Build conversation with video placeholder + prompt text
        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "video"},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ]

        # apply_chat_template → formatted text string (not tokenized)
        text = processor.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            tokenize=False,
        )
        print(f"[llava_probe] Prompt text (first 200 chars): {text[:200]!r}", flush=True)

        # Process: pass text + videos
        # videos expects list of (N,H,W,3) uint8 arrays
        t1 = time.time()
        inputs = processor(
            text=[text],
            videos=[frames],
            return_tensors="pt",
        )
        inputs = {k: v.to("cuda") if hasattr(v, "to") else v for k, v in inputs.items()}

        print(f"[llava_probe] Processor done. Running generate ...", flush=True)
        torch.cuda.reset_peak_memory_stats()
        with torch.inference_mode():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=1024,
                do_sample=False,
            )
        infer_time = time.time() - t1
        peak = peak_vram_mb()
        print(f"[llava_probe] Generate done in {infer_time:.1f}s. Peak VRAM: {peak:.0f} MB", flush=True)

        # Decode only newly generated tokens
        input_len = inputs["input_ids"].shape[1]
        new_tokens = output_ids[0][input_len:]
        answer = processor.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        # Write output file (UTF-8)
        header = (
            f"model: {MODEL_ID}\n"
            f"folder: {folder}\n"
            f"frame_count: {num_frames}\n"
            f"prompt: {PROMPT}\n"
            f"load_time_s: {load_time:.1f}\n"
            f"infer_time_s: {infer_time:.1f}\n"
            f"peak_vram_mb: {peak:.0f}\n"
            f"{'='*60}\n"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(header + answer, encoding="utf-8")
        print(f"[llava_probe] Written: {out_path}", flush=True)
        print(f"[llava_probe] Answer preview: {answer[:300]!r}", flush=True)

    # Free GPU
    del model
    torch.cuda.empty_cache()
    print("\n[llava_probe] GPU freed. Done.", flush=True)


if __name__ == "__main__":
    main()
