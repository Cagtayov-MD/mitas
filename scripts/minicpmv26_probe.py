"""
MiniCPM-V 2.6 single-image OCR probe for Turkish film end-credits.
Processes each .jpg one at a time; writes verbatim model answers.
"""
import os
import sys
import time
import glob
import subprocess

# --- Env setup (must be first, before any HF import) ---
os.environ["HF_HOME"] = r"E:\MITAS\hf-cache"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# Force UTF-8 stdout/stderr on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import torch
from PIL import Image
from transformers import AutoModel, AutoTokenizer

# -------------------------------------------------------
MODEL_ID = "openbmb/MiniCPM-V-2_6"
MODEL_PATH = r"E:\MITAS\hf-cache\hub\models--openbmb--MiniCPM-V-2_6\snapshots\6c04d9e3022bcff6e6738dfb1fc19a5cfd2a855f"

PROMPT = (
    "bunlar cikis jenerigidir. Ekranda YAZAN her seyi AYNEN, oldugu gibi, satir satir yaz. "
    "Bicim degistirme, yorum katma, uzun uzun dusunme. "
    "Hicbir yazi yoksa veya okuyamiyorsan [okunamadi] yaz. /no_think"
)

FOLDERS = [
    (r"E:\MITAS\_vlm_probe\pages2_ahlat",   r"E:\MITAS\_vlm_probe\out_minicpmv_fp16_ahlat.txt"),
    (r"E:\MITAS\_vlm_probe\pages2_anjelik", r"E:\MITAS\_vlm_probe\out_minicpmv_fp16_anjelik.txt"),
]

# -------------------------------------------------------
def get_vram_mb():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        vals = [int(x.strip()) for x in result.stdout.strip().splitlines() if x.strip()]
        return vals[0] if vals else -1
    except Exception:
        return -1

# -------------------------------------------------------
print("[INFO] Loading model ...", flush=True)
t_load_start = time.time()

model = AutoModel.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
    attn_implementation="sdpa",
    torch_dtype=torch.bfloat16,
)
model = model.eval().cuda()

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)

t_load_end = time.time()
load_time = t_load_end - t_load_start
vram_after_load = get_vram_mb()
print(f"[INFO] Model loaded in {load_time:.1f}s  |  VRAM used after load: {vram_after_load} MiB", flush=True)

# -------------------------------------------------------
t_infer_start = time.time()
peak_vram = vram_after_load

for folder_path, out_path in FOLDERS:
    jpg_files = sorted(glob.glob(os.path.join(folder_path, "*.jpg")))
    n_pages = len(jpg_files)
    folder_name = os.path.basename(folder_path)
    print(f"[INFO] Processing folder: {folder_name}  ({n_pages} pages)", flush=True)

    lines = []
    lines.append(f"model: {MODEL_ID}")
    lines.append(f"folder: {folder_path}")
    lines.append(f"page_count: {n_pages}")
    lines.append(f"prompt: {PROMPT}")
    lines.append("")  # placeholder for total_seconds, filled after

    results = []
    folder_ok = True
    err_reason = ""

    for idx, jpg_path in enumerate(jpg_files, start=1):
        page_name = os.path.basename(jpg_path)
        print(f"  [{idx:02d}/{n_pages}] {page_name} ...", end=" ", flush=True)
        t0 = time.time()
        try:
            image = Image.open(jpg_path).convert("RGB")
            msgs = [{"role": "user", "content": [image, PROMPT]}]
            answer = model.chat(
                image=None,
                msgs=msgs,
                tokenizer=tokenizer,
                sampling=False,
                max_new_tokens=512,
            )
            elapsed = time.time() - t0
            cur_vram = get_vram_mb()
            if cur_vram > peak_vram:
                peak_vram = cur_vram
            print(f"done ({elapsed:.1f}s)  VRAM={cur_vram}MiB", flush=True)
            results.append((idx, page_name, answer))
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"ERROR ({elapsed:.1f}s): {exc}", flush=True)
            results.append((idx, page_name, f"[HATA: {exc}]"))
            folder_ok = False
            err_reason = str(exc)

    total_folder_secs = time.time() - t_infer_start

    # Build output
    header_block = [
        f"model: {MODEL_ID}",
        f"folder: {folder_path}",
        f"page_count: {n_pages}",
        f"prompt: {PROMPT}",
        f"total_seconds: {total_folder_secs:.1f}",
        "",
    ]

    page_blocks = []
    for idx, page_name, answer in results:
        page_blocks.append(f"--- sayfa {idx:02d} ({page_name}) ---")
        page_blocks.append(answer)
        page_blocks.append("")

    full_text = "\n".join(header_block) + "\n".join(page_blocks)

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(full_text)

    status = "SUCCESS" if folder_ok else f"PARTIAL FAILURE: {err_reason}"
    print(f"[INFO] {folder_name}: {status}  ->  {out_path}", flush=True)

t_infer_end = time.time()
total_infer = t_infer_end - t_infer_start
print(f"\n[INFO] All done.  Total inference time: {total_infer:.1f}s  |  Peak VRAM: {peak_vram} MiB", flush=True)

# --- Free GPU ---
del model
torch.cuda.empty_cache()
print("[INFO] GPU freed.", flush=True)
