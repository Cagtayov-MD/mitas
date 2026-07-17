#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
native_video_test_v2.py -- Qwen2.5-VL native-video vs image-list TEMIZ kosu.
Bir film, bir model, tek mod. CUDA hatasi riskini minimuma indirir.
"""

import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os, time, json, re, glob, argparse
import unicodedata

os.environ["HF_HOME"] = "E:\\hf_cache_vl"
os.environ["HUGGINGFACE_HUB_CACHE"] = "E:\\hf_cache_vl\\hub"

import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

DEVICE = "cuda"
DTYPE = torch.float16
ATTN = "sdpa"

PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştirerek sunlari bul. SADECE karelerde ACIKCA YAZAN isimleri kullan, uydurma; yoksa 'yok'. "
    "Ciktiyi tam olarak su formatta ver:\n"
    "YONETMEN: <Director/Yöneten/Rejisor yanindaki isim | yok>\n"
    "YAPIMCI: <Producer/Yapimci/Executive Producer yanindaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen basrol oyuncu adlari, en fazla 8, virgülle | yok>"
)

FILMS = {
    "fargo": {
        "isim": "FARGO (1996)",
        "giris": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_1996-1042-1-0000-50-0-FARGO\frames\giris",
        "cikis": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_1996-1042-1-0000-50-0-FARGO\frames\cikis",
        "gercek_yonetmen": ["Joel Coen", "Ethan Coen", "Coen Brothers"],
        "gercek_cast": ["Frances McDormand", "William H. Macy", "Steve Buscemi"],
    },
    "moneyball": {
        "isim": "KAZANMA SANATI / Moneyball (2011)",
        "giris": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_2011-1010-1-0000-50-0-KAZANMA_SANATI\frames\giris",
        "cikis": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_2011-1010-1-0000-50-0-KAZANMA_SANATI\frames\cikis",
        "gercek_yonetmen": ["Bennett Miller"],
        "gercek_cast": ["Brad Pitt", "Jonah Hill", "Philip Seymour Hoffman"],
    },
}

MODELS = {
    "qwen25vl": "Qwen/Qwen2.5-VL-7B-Instruct",
    "qwen3vl":  "Qwen/Qwen3-VL-8B-Instruct",
}

def list_frames(d):
    return (
        sorted(glob.glob(os.path.join(d, "g_*.png")))
        + sorted(glob.glob(os.path.join(d, "c_*.png")))
        + sorted(glob.glob(os.path.join(d, "*.jpg")))
    )

def even_sample(pool, k):
    if not pool: return []
    if len(pool) <= k: return pool
    return [pool[round(i * (len(pool) - 1) / (k - 1))] for i in range(k)]

def get_frames(film_key, n=16):
    """Her segmentten n//2 kare ornekle (toplam ~n)."""
    film = FILMS[film_key]
    frames = []
    for d in [film["giris"], film["cikis"]]:
        if os.path.isdir(d):
            pool = list_frames(d)
            frames += even_sample(pool, n // 2)
    return frames

def load_qwen25vl(hf_name):
    print(f"[YUKLEME] {hf_name}", flush=True)
    t0 = time.time()
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        hf_name, torch_dtype=DTYPE, attn_implementation=ATTN, device_map="auto"
    )
    processor = AutoProcessor.from_pretrained(hf_name)
    print(f"  yuklu {time.time()-t0:.1f}s, VRAM: {torch.cuda.memory_allocated()/1e9:.1f}GB", flush=True)
    return model, processor

def load_qwen3vl(hf_name):
    from transformers import AutoModelForImageTextToText
    print(f"[YUKLEME] {hf_name}", flush=True)
    t0 = time.time()
    model = AutoModelForImageTextToText.from_pretrained(
        hf_name, torch_dtype=DTYPE, attn_implementation=ATTN, device_map="auto"
    )
    processor = AutoProcessor.from_pretrained(hf_name)
    print(f"  yuklu {time.time()-t0:.1f}s, VRAM: {torch.cuda.memory_allocated()/1e9:.1f}GB", flush=True)
    return model, processor

def infer(model, processor, frames, mode):
    """mode: 'image_list' veya 'native_video'"""
    if mode == "image_list":
        content = [{"type": "image", "image": f} for f in frames]
        content.append({"type": "text", "text": PROMPT})
    else:
        content = [
            {"type": "video", "video": frames, "fps": 2.0},
            {"type": "text", "text": PROMPT},
        ]

    messages = [{"role": "user", "content": content}]
    text_in = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    img_in, vid_in = process_vision_info(messages)
    inputs = processor(text=[text_in], images=img_in, videos=vid_in,
                       padding=True, return_tensors="pt").to(DEVICE)

    print(f"    input_ids shape: {inputs.input_ids.shape}, VRAM: {torch.cuda.memory_allocated()/1e9:.1f}GB", flush=True)

    t0 = time.time()
    with torch.no_grad():
        gen = model.generate(**inputs, max_new_tokens=400, do_sample=False,
                             temperature=None, top_p=None)
    sn = time.time() - t0

    gen_trimmed = [o[len(i):] for i, o in zip(inputs.input_ids, gen)]
    txt = processor.batch_decode(gen_trimmed, skip_special_tokens=True,
                                 clean_up_tokenization_spaces=False)[0].strip()
    return txt, sn

def fold(s):
    s = s or ""
    for a, b in [("I","i"),("s","s"),("g","g"),("u","u"),("o","o"),("c","c")]:
        pass  # ASCII fold gereksiz burada
    return s.lower().strip()

def match(okunan, gercek_liste):
    okunan_l = (okunan or "").lower()
    for g in gercek_liste:
        words = [w for w in g.lower().split() if len(w) > 2]
        if all(w in okunan_l for w in words):
            return True
        if g.lower() in okunan_l:
            return True
    return False

def parse_field(text, key):
    for line in (text or "").splitlines():
        kl = line.lower().strip()
        kk = key.lower()
        if kl.startswith(kk):
            return line.split(":",1)[1].strip() if ":" in line else ""
    return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen25vl", choices=list(MODELS.keys()))
    ap.add_argument("--film", default="fargo", choices=list(FILMS.keys()))
    ap.add_argument("--mode", default="both", choices=["image_list","native_video","both"])
    ap.add_argument("--frames", type=int, default=16)
    args = ap.parse_args()

    print(f"[BASLANGIC] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"model={args.model}, film={args.film}, mode={args.mode}, frames={args.frames}", flush=True)

    import transformers
    print(f"torch:{torch.__version__} tf:{transformers.__version__} CUDA:{torch.cuda.is_available()}", flush=True)

    hf_name = MODELS[args.model]
    film = FILMS[args.film]
    frames = get_frames(args.film, n=args.frames)
    print(f"Kareler: {len(frames)} / {frames[:2]}", flush=True)

    # Model yükle
    try:
        if args.model == "qwen25vl":
            model, processor = load_qwen25vl(hf_name)
        else:
            model, processor = load_qwen3vl(hf_name)
    except Exception as e:
        print(f"[YUKLEME HATASI] {e}", flush=True)
        sys.exit(1)

    results = {}
    modes = ["image_list","native_video"] if args.mode == "both" else [args.mode]

    for mode in modes:
        print(f"\n--- MOD: {mode} ---", flush=True)
        try:
            txt, sn = infer(model, processor, frames, mode)
            yon = parse_field(txt, "YONETMEN")
            cast = parse_field(txt, "OYUNCULAR")
            yon_ok = match(yon, film["gercek_yonetmen"])
            cast_ok = match(cast, film["gercek_cast"])
            print(f"  YONETMEN: {yon!r}  {'OK' if yon_ok else 'YANLIS'} (gercek: {film['gercek_yonetmen']})", flush=True)
            print(f"  OYUNCULAR: {cast!r}  {'OK' if cast_ok else 'YANLIS'}", flush=True)
            print(f"  Sure: {sn:.1f}s", flush=True)
            results[mode] = {"yon": yon, "cast": cast, "yon_ok": yon_ok, "cast_ok": cast_ok, "sure": sn, "ham": txt}
        except Exception as e:
            import traceback
            print(f"  [HATA] {e}", flush=True)
            traceback.print_exc()
            results[mode] = {"hata": str(e)}

    # Kaydet
    out = {
        "model": args.model, "film": args.film, "n_frames": len(frames),
        "gercek_yonetmen": film["gercek_yonetmen"],
        "results": results
    }
    outf = f"E:\\MITAS\\outputs\\nvtest_{args.model}_{args.film}.json"
    with open(outf, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[KAYDEDILDI] {outf}", flush=True)
    print(f"[BITIS] {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

if __name__ == "__main__":
    main()
