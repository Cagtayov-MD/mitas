"""
locateanything_probe.py
=======================
LocateAnything-3B (NVIDIA) text-detection PoC on Windows.
Stage A: detect text boxes on anjelik page_010, draw visualization.
Stage B: detect + crop + OCR (via glm-ocr Ollama) on ahlat page_010.

Usage:
    $env:PYTHONIOENCODING="utf-8"
    & E:\MITAS\venvs\locateanything\Scripts\python.exe E:\MITAS\scripts\locateanything_probe.py
"""

import os, sys, re, time, base64, json, io, requests
import numpy as np
import cv2
from PIL import Image
import torch

# ── env ────────────────────────────────────────────────────────────────
os.environ["HF_HOME"] = r"E:\MITAS\hf-cache"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

SNAPSHOT = r"E:\MITAS\hf-cache\hub\models--nvidia--LocateAnything-3B\snapshots\7a81d810571dc5f244b2f0b6868128f24b1cbd85"

IMG_ANJELIK = r"E:\MITAS\_vlm_probe\pages2_anjelik\page_010.jpg"
IMG_AHLAT   = r"E:\MITAS\_vlm_probe\pages2_ahlat\page_010.jpg"

OUT_ANJELIK_VIZ = r"E:\MITAS\_vlm_probe\locate_anjelik_p010.png"
OUT_AHLAT_VIZ   = r"E:\MITAS\_vlm_probe\locate_ahlat_p010.png"
CROPS_DIR       = r"E:\MITAS\_vlm_probe\locate_crops"
OUT_TXT_AHLAT   = r"E:\MITAS\_vlm_probe\out_locate_ocr_ahlat_p010.txt"

os.makedirs(CROPS_DIR, exist_ok=True)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
GLM_MODEL  = "glm-ocr:latest"
OCR_PROMPT = "Bu gorseldeki yaziyi AYNEN oku, sadece metni yaz."

BOX_RE = re.compile(r"<box><(\d+)><(\d+)><(\d+)><(\d+)></box>")

DETECT_PROMPT = "Detect all the text in box format."


# ── helpers ─────────────────────────────────────────────────────────────

def parse_boxes(raw: str, img_w: int, img_h: int):
    """Parse <box><x1><y1><x2><y2></box> normalized [0,1000] -> pixels."""
    matches = BOX_RE.findall(raw)
    boxes = []
    for m in matches:
        x1, y1, x2, y2 = [int(v) for v in m]
        px1 = int(x1 * img_w / 1000)
        py1 = int(y1 * img_h / 1000)
        px2 = int(x2 * img_w / 1000)
        py2 = int(y2 * img_h / 1000)
        boxes.append((px1, py1, px2, py2))
    return boxes


def draw_boxes(img_path: str, boxes, out_path: str):
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    for i, (x1, y1, x2, y2) in enumerate(boxes):
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, str(i), (x1, max(y1-4, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,255), 1)
    cv2.imencode(".png", img)[1].tofile(out_path)
    print(f"[viz] saved: {out_path}", flush=True)


def img_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def crop_and_save(img_path: str, box, pad: int, scale: int, out_path: str):
    """Crop with padding, upscale 3x, save."""
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w, x2 + pad)
    y2 = min(h, y2 + pad)
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return False
    nh, nw = crop.shape[:2]
    crop_up = cv2.resize(crop, (nw * scale, nh * scale), interpolation=cv2.INTER_CUBIC)
    cv2.imencode(".png", crop_up)[1].tofile(out_path)
    return True


def glm_ocr(crop_path: str) -> str:
    b64 = img_to_b64(crop_path)
    payload = {
        "model": GLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": OCR_PROMPT,
                "images": [b64],
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "repeat_penalty": 1.15,
            "num_predict": 256,
        }
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data.get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"[OCR_ERROR: {e}]"


# ── model load ──────────────────────────────────────────────────────────

def load_model():
    print("[load] importing AutoModel/AutoProcessor ...", flush=True)
    t0 = time.time()
    from transformers import AutoProcessor, AutoModel, AutoTokenizer

    print("[load] loading processor ...", flush=True)
    processor = AutoProcessor.from_pretrained(
        SNAPSHOT,
        trust_remote_code=True,
    )

    print("[load] loading model ...", flush=True)
    model = AutoModel.from_pretrained(
        SNAPSHOT,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        device_map="cuda",
        # force sdpa so magi/flash paths are skipped on Windows
        attn_implementation="sdpa",
    )
    model.eval()
    elapsed = time.time() - t0
    print(f"[load] done in {elapsed:.1f}s", flush=True)

    # tokenizer for generate()
    tokenizer = AutoTokenizer.from_pretrained(SNAPSHOT, trust_remote_code=True)

    return model, processor, tokenizer, elapsed


# ── detect ──────────────────────────────────────────────────────────────

def detect_text(model, processor, tokenizer, img_path: str, label: str):
    """Run text detection, return (raw_output, boxes, detect_time_sec)."""
    print(f"\n[detect:{label}] reading {img_path}", flush=True)
    image = Image.open(img_path).convert("RGB")
    img_w, img_h = image.size
    print(f"[detect:{label}] image size: {img_w}x{img_h}", flush=True)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": img_path},
                {"type": "text",  "text": DETECT_PROMPT},
            ]
        }
    ]

    # Build text from chat template
    text = processor.py_apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    # Process vision info
    image_inputs, video_inputs = processor.process_vision_info(messages)

    # Build model inputs
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to("cuda")

    vram_before = torch.cuda.memory_allocated() / 1e9
    t0 = time.time()

    with torch.no_grad():
        # Try hybrid first, fall back to slow on error
        # The custom model.generate() returns a STRING directly (not token ids).
        for mode in ("hybrid", "slow"):
            try:
                raw_text = model.generate(
                    **inputs,
                    tokenizer=tokenizer,
                    max_new_tokens=2048,
                    use_cache=True,
                    generation_mode=mode,
                    do_sample=False,
                    temperature=1.0,
                )
                used_mode = mode
                break
            except Exception as e:
                print(f"[detect:{label}] generation_mode={mode} failed: {e}", flush=True)
                if mode == "slow":
                    raise
                continue

    detect_time = time.time() - t0
    vram_peak = torch.cuda.max_memory_allocated() / 1e9

    # raw_text is already a decoded string from the custom generate()
    if not isinstance(raw_text, str):
        # Shouldn't happen, but handle list return
        raw_text = raw_text[0] if isinstance(raw_text, list) else str(raw_text)

    print(f"[detect:{label}] raw decoded ({used_mode}, {detect_time:.1f}s):", flush=True)
    print(raw_text[:2000], flush=True)

    boxes = parse_boxes(raw_text, img_w, img_h)
    print(f"[detect:{label}] boxes parsed: {len(boxes)}, peak VRAM: {vram_peak:.2f}GB", flush=True)

    return raw_text, boxes, detect_time, vram_peak


# ── main ────────────────────────────────────────────────────────────────

def main():
    print("=" * 60, flush=True)
    print("LocateAnything-3B probe", flush=True)
    print("=" * 60, flush=True)

    # GPU status before load
    import subprocess
    smi = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.used,memory.free,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True
    )
    print(f"[gpu pre-load] {smi.stdout.strip()}", flush=True)

    # ── Load ──
    model, processor, tokenizer, load_time = load_model()

    smi2 = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.used,memory.free,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True
    )
    print(f"[gpu post-load] {smi2.stdout.strip()}", flush=True)

    # ── STAGE A ──
    print("\n" + "="*40, flush=True)
    print("STAGE A — anjelik page_010", flush=True)
    print("="*40, flush=True)
    raw_a, boxes_a, dt_a, vram_a = detect_text(model, processor, tokenizer, IMG_ANJELIK, "anjelik")
    draw_boxes(IMG_ANJELIK, boxes_a, OUT_ANJELIK_VIZ)

    print(f"\n[STAGE A SUMMARY]", flush=True)
    print(f"  Raw output length: {len(raw_a)} chars", flush=True)
    print(f"  Boxes detected: {len(boxes_a)}", flush=True)
    print(f"  Detection time: {dt_a:.1f}s", flush=True)
    print(f"  Peak VRAM: {vram_a:.2f} GB", flush=True)
    print(f"  Viz saved: {OUT_ANJELIK_VIZ}", flush=True)

    # ── STAGE B ──
    print("\n" + "="*40, flush=True)
    print("STAGE B — ahlat page_010", flush=True)
    print("="*40, flush=True)

    torch.cuda.reset_peak_memory_stats()
    raw_b, boxes_b, dt_b, vram_b = detect_text(model, processor, tokenizer, IMG_AHLAT, "ahlat")
    draw_boxes(IMG_AHLAT, boxes_b, OUT_AHLAT_VIZ)

    print(f"\n[Stage B] {len(boxes_b)} boxes detected, now OCR-ing each ...", flush=True)

    results = []
    for i, box in enumerate(boxes_b):
        crop_path = os.path.join(CROPS_DIR, f"ahlat_p010_box{i:03d}.png")
        ok = crop_and_save(IMG_AHLAT, box, pad=6, scale=3, out_path=crop_path)
        if not ok:
            ocr_text = "[EMPTY_CROP]"
        else:
            ocr_text = glm_ocr(crop_path)
            print(f"  box {i:03d} {box} -> {repr(ocr_text[:80])}", flush=True)
        results.append((i, box, ocr_text))

    # Write results UTF-8
    with open(OUT_TXT_AHLAT, "w", encoding="utf-8") as f:
        for i, box, txt in results:
            f.write(f"BOX {i:03d} | coords={box}\n")
            f.write(f"{txt}\n")
            f.write("-" * 60 + "\n")

    print(f"\n[Stage B] results written to {OUT_TXT_AHLAT}", flush=True)

    # ── Free GPU ──
    del model
    torch.cuda.empty_cache()
    print("\n[gpu freed]", flush=True)

    smi3 = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.used,memory.free,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True
    )
    print(f"[gpu post-free] {smi3.stdout.strip()}", flush=True)

    # ── Final summary ──
    print("\n" + "=" * 60, flush=True)
    print("FINAL SUMMARY", flush=True)
    print("=" * 60, flush=True)
    print(f"Load time: {load_time:.1f}s", flush=True)
    print(f"Stage A — anjelik: {len(boxes_a)} boxes, detect={dt_a:.1f}s, VRAM={vram_a:.2f}GB", flush=True)
    print(f"Stage B — ahlat  : {len(boxes_b)} boxes, detect={dt_b:.1f}s, VRAM={vram_b:.2f}GB", flush=True)
    print(f"\nStage A viz: {OUT_ANJELIK_VIZ}", flush=True)
    print(f"Stage B viz: {OUT_AHLAT_VIZ}", flush=True)
    print(f"Stage B crops: {CROPS_DIR}", flush=True)
    print(f"Stage B OCR txt: {OUT_TXT_AHLAT}", flush=True)
    print("\n--- RAW OUTPUT STAGE A (first 3000 chars) ---", flush=True)
    print(raw_a[:3000], flush=True)
    print("\n--- STAGE B OCR TXT CONTENT ---", flush=True)
    try:
        with open(OUT_TXT_AHLAT, "r", encoding="utf-8") as f:
            print(f.read(), flush=True)
    except Exception as e:
        print(f"[read error: {e}]", flush=True)


if __name__ == "__main__":
    main()
