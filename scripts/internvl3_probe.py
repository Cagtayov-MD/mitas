"""
InternVL3-8B credit-page OCR probe.
Processes each *.jpg in two folders one at a time.
Writes verbatim model answers to UTF-8 text files.
"""
import os
import sys
import time
import math
import glob
import torch
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from PIL import Image
from transformers import AutoModel, AutoTokenizer

# ----- environment -----
os.environ["HF_HOME"] = r"E:\MITAS\hf-cache"
os.environ["HF_HUB_OFFLINE"] = "1"

SNAP = r"E:\MITAS\hf-cache\hub\models--OpenGVLab--InternVL3-8B\snapshots\853e3a797a661694b1b8ece0cb72dc2b23e3dac9"

PROMPT = (
    "bunlar cikis jenerigidir. Ekranda YAZAN her seyi AYNEN, oldugu gibi, satir satir yaz. "
    "Bicim degistirme, yorum katma, uzun uzun dusunme. "
    "Hicbir yazi yoksa veya okuyamiyorsan [okunamadi] yaz. /no_think"
)

FOLDERS = [
    (r"E:\MITAS\_vlm_probe\pages2_ahlat",   r"E:\MITAS\_vlm_probe\out_internvl3_ahlat.txt"),
    (r"E:\MITAS\_vlm_probe\pages2_anjelik", r"E:\MITAS\_vlm_probe\out_internvl3_anjelik.txt"),
]

# ----- InternVL3 canonical tiling helpers (from official model card) -----

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD  = (0.229, 0.224, 0.225)


def build_transform(input_size):
    return T.Compose([
        T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def find_closest_aspect_ratio(aspect_ratio, target_ratios, width, height, image_size):
    best_ratio_diff = float("inf")
    best_ratio = (1, 1)
    area = width * height
    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)
        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff:
            if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                best_ratio = ratio
    return best_ratio


def dynamic_preprocess(image, min_num=1, max_num=12, image_size=448, use_thumbnail=True):
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    # build candidate tile grids
    target_ratios = set(
        (i, j)
        for n in range(min_num, max_num + 1)
        for i in range(1, n + 1)
        for j in range(1, n + 1)
        if i * j <= max_num and i * j >= min_num
    )
    target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

    best_ratio = find_closest_aspect_ratio(aspect_ratio, target_ratios, orig_width, orig_height, image_size)

    target_width  = image_size * best_ratio[0]
    target_height = image_size * best_ratio[1]
    blocks = best_ratio[0] * best_ratio[1]

    resized = image.resize((target_width, target_height))
    processed = []
    for i in range(blocks):
        row = i // best_ratio[0]
        col = i  % best_ratio[0]
        box = (
            col * image_size,
            row * image_size,
            (col + 1) * image_size,
            (row + 1) * image_size,
        )
        processed.append(resized.crop(box))

    if use_thumbnail and len(processed) != 1:
        processed.append(image.resize((image_size, image_size)))

    return processed


def load_image(image_file, input_size=448, max_num=12):
    image = Image.open(image_file).convert("RGB")
    transform = build_transform(input_size=input_size)
    images = dynamic_preprocess(image, image_size=input_size, use_thumbnail=True, max_num=max_num)
    pixel_values = torch.stack([transform(img) for img in images])
    return pixel_values


# ----- model load -----
print("Loading model...", flush=True)
t0 = time.time()
model = AutoModel.from_pretrained(
    SNAP,
    torch_dtype=torch.bfloat16,
    trust_remote_code=True,
    use_flash_attn=False,
    low_cpu_mem_usage=True,
).eval().cuda()
tokenizer = AutoTokenizer.from_pretrained(SNAP, trust_remote_code=True, use_fast=False)
load_time = time.time() - t0
print(f"Model loaded in {load_time:.1f}s", flush=True)

# ----- VRAM after load -----
torch.cuda.synchronize()
vram_after_load = torch.cuda.memory_allocated() / 1024**3

generation_config = dict(max_new_tokens=512, do_sample=False)

total_infer_start = time.time()
peak_vram = 0.0

for folder, out_path in FOLDERS:
    pages = sorted(glob.glob(os.path.join(folder, "*.jpg")))
    folder_name = os.path.basename(folder)
    print(f"\n=== {folder_name}: {len(pages)} pages ===", flush=True)

    folder_start = time.time()
    lines = []
    lines.append(f"model: OpenGVLab/InternVL3-8B  snap: {SNAP}")
    lines.append(f"folder: {folder}")
    lines.append(f"pages: {len(pages)}")
    lines.append(f"prompt: {PROMPT}")
    lines.append("")

    for pg_path in pages:
        pg_name = os.path.basename(pg_path)
        pg_num  = pg_name.replace("page_", "").replace(".jpg", "")
        print(f"  page {pg_num}...", end=" ", flush=True)
        t_pg = time.time()
        try:
            pixel_values = load_image(pg_path, input_size=448, max_num=12).to(torch.bfloat16).cuda()
            question = "<image>\n" + PROMPT
            response = model.chat(tokenizer, pixel_values, question, generation_config)
        except Exception as exc:
            response = f"[HATA: {exc}]"
        elapsed = time.time() - t_pg
        print(f"{elapsed:.1f}s", flush=True)

        # track peak VRAM
        vram_now = torch.cuda.max_memory_allocated() / 1024**3
        if vram_now > peak_vram:
            peak_vram = vram_now

        lines.append(f"--- sayfa {pg_num} ({pg_name}) ---")
        lines.append(response)
        lines.append("")

    folder_elapsed = time.time() - folder_start
    lines.insert(4, f"total_seconds: {folder_elapsed:.1f}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"  Written: {out_path}", flush=True)

total_infer = time.time() - total_infer_start

print(f"\n--- DONE ---")
print(f"Model load : {load_time:.1f}s")
print(f"Total infer: {total_infer:.1f}s")
print(f"Peak VRAM  : {peak_vram:.2f} GB")

# free GPU
del model
torch.cuda.empty_cache()
print("GPU freed.")
