#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
internvl3_bench.py — InternVL3-8B (transformers, sdpa) vs qwen2.5vl:7b (ollama)
Jenerik kare okuma benchmark. credit_video_read.py mantığını taklit eder.

Kullanim (internvl venv ile):
  E:\MITAS\venvs\internvl\Scripts\python.exe E:\MITAS\outputs\internvl3_bench.py
"""
import base64
import glob
import io
import json
import os
import sys
import time
import requests
from pathlib import Path
from PIL import Image

# ---- Konfigurasyon ----
SNAP = r"C:\Users\TRT03\.cache\huggingface\hub\models--OpenGVLab--InternVL3_5-8B\snapshots\9bb6a56ad9cc69db95e2d4eeb15a52bbcac4ef79"
OLLAMA_HOST = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434")
QWEN_MODEL = "qwen2.5vl:7b"
FRAME_W = 640
BUDGET = 12   # bench için düşük (hız ölçümü)
IMG_SIZE = 448

DB = r"E:\MITAS\Database"

TEST_FILMS = [
    (r"evoArcadmin__Z_MLEME10_1996-1042-1-0000-50-0-FARGO", "FARGO (yabancı)"),
    (r"evoArcadmin__Z_MLEME10_2013-1015-1-0000-70-0-ATT_LA_MARCEL", "ATTILA MARCEL (Fransız)"),
]

PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştirerek şunları bul. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, uydurma; yoksa 'yok'. "
    "Çıktıyı tam olarak şu formatta ver:\n"
    "YÖNETMEN: <Director/Yöneten/Rejisör yanındaki isim | yok>\n"
    "YAPIMCI: <Producer/Yapımcı/Executive Producer yanındaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen başrol oyuncu adları, en fazla 8, virgülle | yok>"
)


def _even(pool, k):
    if len(pool) <= k:
        return pool
    return [pool[round(i * (len(pool) - 1) / (k - 1))] for i in range(k)]


def list_frames(d):
    return sorted(
        glob.glob(os.path.join(d, "f_*.png")) +
        glob.glob(os.path.join(d, "g_*.png")) +
        glob.glob(os.path.join(d, "c_*.png")) +
        glob.glob(os.path.join(d, "*.jpg"))
    )


def sample_frames(giris_dir, cikis_dir, budget=BUDGET):
    g = list_frames(giris_dir) if os.path.isdir(giris_dir) else []
    c = list_frames(cikis_dir) if os.path.isdir(cikis_dir) else []
    all_frames = g + c
    return _even(all_frames, budget)


def encode_b64(path):
    im = Image.open(path).convert("RGB")
    if im.width > FRAME_W:
        im = im.resize((FRAME_W, round(im.height * FRAME_W / im.width)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


# ======== YÖNTEM 1: ollama qwen2.5vl ========
def read_qwen_ollama(frames):
    images = [encode_b64(f) for f in frames]
    payload = {
        "model": QWEN_MODEL,
        "messages": [{"role": "user", "content": PROMPT, "images": images}],
        "stream": False,
        "options": {"temperature": 0, "top_p": 1, "num_ctx": 20480, "num_predict": 600},
    }
    t0 = time.time()
    r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=300)
    elapsed = time.time() - t0
    if r.status_code != 200:
        return f"HATA {r.status_code}: {r.text[:200]}", elapsed
    return r.json()["message"]["content"], elapsed


# ======== YÖNTEM 2: InternVL3-8B transformers (sdpa) ========
_ivl_model = None
_ivl_tok = None
_ivl_load_time = 0


def _build_transform():
    from torchvision import transforms as T
    MEAN = (0.485, 0.456, 0.406)
    STD  = (0.229, 0.224, 0.225)
    return T.Compose([
        T.Resize((IMG_SIZE, IMG_SIZE), interpolation=T.InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=MEAN, std=STD),
    ])


def _load_internvl():
    global _ivl_model, _ivl_tok, _ivl_load_time
    if _ivl_model is not None:
        return
    import torch
    from transformers import AutoTokenizer, AutoModel
    print(f"  [InternVL3] Model yükleniyor: {SNAP}")
    t0 = time.time()
    _ivl_tok = AutoTokenizer.from_pretrained(SNAP, trust_remote_code=True)
    _ivl_model = AutoModel.from_pretrained(
        SNAP,
        torch_dtype=torch.bfloat16,
        attn_implementation="eager",   # sdpa InternVLChatModel'de desteklenmiyor
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    ).eval().cuda()
    _ivl_load_time = time.time() - t0
    print(f"  [InternVL3] Yükleme: {_ivl_load_time:.1f}s")
    import torch
    allocated = torch.cuda.memory_allocated() / 1e9
    print(f"  [InternVL3] GPU bellek: {allocated:.1f} GB")


def read_internvl3(frames):
    import torch
    _load_internvl()
    transform = _build_transform()

    # Her kare: tek patch (448x448) → num_patches_list her biri için 1
    pixel_values_list = []
    for f in frames:
        img = Image.open(f).convert("RGB")
        t = transform(img)  # (3, 448, 448)
        pixel_values_list.append(t)

    n = len(frames)
    # Stack: (N, 3, 448, 448)
    pixel_values = torch.stack(pixel_values_list).to(torch.bfloat16).cuda()
    num_patches_list = [1] * n  # her kare 1 patch

    # Prompt: N adet <image> etiketi
    img_tags = "".join([f"Kare {i+1}: <image>\n" for i in range(n)])
    full_prompt = img_tags + PROMPT

    gen_config = {
        "max_new_tokens": 600,
        "do_sample": False,
    }

    t0 = time.time()
    with torch.no_grad():
        response = _ivl_model.chat(
            _ivl_tok,
            pixel_values,
            full_prompt,
            gen_config,
            num_patches_list=num_patches_list,
        )
    elapsed = time.time() - t0
    return response, elapsed


# ======== MAIN ========
def run():
    print(f"\n{'='*60}")
    print("InternVL3-8B vs qwen2.5vl:7b — KÜNYİ KARE OKUMA BENCH")
    print(f"{'='*60}")

    results = []
    ivl_first_load = True

    for film_dir_name, film_label in TEST_FILMS:
        film_path = os.path.join(DB, film_dir_name)
        giris = os.path.join(film_path, "frames", "giris")
        cikis = os.path.join(film_path, "frames", "cikis")

        if not os.path.isdir(giris):
            print(f"\n[ATLANDI] {film_label}: giris klasörü yok ({giris})")
            continue

        frames = sample_frames(giris, cikis, BUDGET)
        if not frames:
            print(f"\n[ATLANDI] {film_label}: frame yok")
            continue

        print(f"\n{'='*60}")
        print(f"FİLM: {film_label}")
        print(f"Kare sayısı: {len(frames)}")
        print(f"İlk 3 kare: {[os.path.basename(f) for f in frames[:3]]}")
        print(f"{'='*60}")

        # -- qwen2.5vl ollama --
        print("\n[1] qwen2.5vl:7b (ollama) ...")
        try:
            qwen_resp, qwen_t = read_qwen_ollama(frames)
        except Exception as e:
            qwen_resp, qwen_t = f"HATA: {e}", 0
        print(f"  Süre: {qwen_t:.1f}s")
        print(f"  CEVAP:\n{qwen_resp}")

        # -- InternVL3-8B transformers --
        print("\n[2] InternVL3-8B (transformers/sdpa) ...")
        try:
            ivl_resp, ivl_t = read_internvl3(frames)
            load_note = f" (+ {_ivl_load_time:.0f}s yükleme)" if ivl_first_load else ""
            ivl_first_load = False
        except Exception as e:
            import traceback
            ivl_resp, ivl_t = f"HATA: {e}\n{traceback.format_exc()}", 0
            load_note = ""
        print(f"  Süre: {ivl_t:.1f}s{load_note}")
        print(f"  CEVAP:\n{ivl_resp}")

        results.append({
            "film": film_label,
            "n_frames": len(frames),
            "qwen_t": round(qwen_t, 1),
            "qwen_resp": qwen_resp,
            "ivl_t": round(ivl_t, 1),
            "ivl_load_t": round(_ivl_load_time, 1),
            "ivl_resp": ivl_resp,
        })

    # Özet
    print(f"\n{'='*60}")
    print("ÖZET")
    print(f"{'='*60}")
    print(f"InternVL3 yükleme: {_ivl_load_time:.0f}s (ilk kez, sonraki filmler sıfır)")
    print(f"{'Film':<30} {'qwen_t':>8} {'ivl_t':>8} (sadece inference)")
    for r in results:
        print(f"{r['film']:<30} {r['qwen_t']:>7.1f}s {r['ivl_t']:>7.1f}s")

    out = r"E:\MITAS\outputs\internvl3_bench_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSonuçlar: {out}")


if __name__ == "__main__":
    run()
