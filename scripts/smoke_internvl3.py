#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
smoke_internvl3.py
InternVL3-8B künye-okuma smoke test
minicpmv venv ile çalıştırılmalı:
  E:\MITAS\venvs\minicpmv\Scripts\python.exe scripts/smoke_internvl3.py

Akıllı frame seçimi: cikis son 60 + giris ilk 15, budget=6/folder
"""
import base64, glob, io, json, os, re, sys, time, unicodedata
from pathlib import Path
from PIL import Image

os.environ["HF_HOME"]         = r"E:\MITAS\hf-cache"
os.environ["HF_HUB_OFFLINE"]  = "1"

SNAP = r"E:\MITAS\hf-cache\hub\models--OpenGVLab--InternVL3-8B\snapshots\853e3a797a661694b1b8ece0cb72dc2b23e3dac9"
OUTPUT_DIR = r"E:\MITAS\outputs\model_test"
FRAME_W = 640
BUDGET_PER_FOLDER = 6

PROMPT = (
    "Bunlar bir film jeneriğinin ardışık kareleridir. Karelerdeki yazıları birleştirerek:\n"
    "YÖNETMEN: <kişi adı | yok>\n"
    "YAPIMCI: <kişi adı | yok>\n"
    "OYUNCULAR: <virgülle liste, max 8 | yok>\n"
    "Sadece karede görünen isimleri yaz. Uydurma."
)

GOLD = {
    "DRAKULA": {
        "yonetmen": ["Terence Fisher"],
        "oyuncular": ["Peter Cushing", "Martita Hunt", "Yvonne Monlaur", "David Peel"]
    },
    "ATTILA": {
        "yonetmen": ["Sylvain Chomet"],
        "oyuncular": ["Guillaume Gouix", "Anne Le Ny", "Bernadette Lafont"]
    },
    "YALAZA": {"yonetmen": [], "oyuncular": []}
}

TEST_FILMS = [
    {
        "id": "DRAKULA",
        "label": "DRAKULA'NIN GELİNLERİ (1960)",
        "folders": {
            "cikis_last": (r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S17_1960-0046-1-0000-00-1-DRAKULA_NIN_GEL_NLER\frames\cikis", 60),
            "giris_first": (r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S17_1960-0046-1-0000-00-1-DRAKULA_NIN_GEL_NLER\frames\giris", 15),
        }
    },
    {
        "id": "ATTILA",
        "label": "ATTİLA MARCEL (2013)",
        "folders": {
            "cikis_last": (r"E:\MITAS\Database\evoArcadmin_S_NEMA_F_LM4_2013-1015-1-0000-70-1-ATT_LA_MARCEL\frames\cikis", 60),
            "giris_first": (r"E:\MITAS\Database\evoArcadmin_S_NEMA_F_LM4_2013-1015-1-0000-70-1-ATT_LA_MARCEL\frames\giris", 15),
        }
    },
    {
        "id": "YALAZA",
        "label": "YALAZA (Türkçe-isim testi)",
        "folders": {
            "giris_first": (r"E:\MITAS\Database\web_client_dad_2017-0019-0-0001-90-1-YALAZA\frames\giris", 15),
        }
    },
]

# ── InternVL3 preprocessing ──

import torch
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD  = (0.229, 0.224, 0.225)

def build_transform(size=448):
    return T.Compose([
        T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        T.Resize((size, size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])

def find_best_ratio(ar, ratios, w, h, sz):
    best_diff, best = float("inf"), (1,1)
    for r in ratios:
        d = abs(ar - r[0]/r[1])
        if d < best_diff:
            best_diff, best = d, r
    return best

def dynamic_preprocess(img, min_n=1, max_n=6, sz=448):
    w, h = img.size
    ar = w / h
    ratios = sorted({(i,j) for n in range(min_n,max_n+1)
                     for i in range(1,n+1) for j in range(1,n+1)
                     if min_n <= i*j <= max_n}, key=lambda x: x[0]*x[1])
    best = find_best_ratio(ar, ratios, w, h, sz)
    tw, th = sz*best[0], sz*best[1]
    blocks = best[0]*best[1]
    resized = img.resize((tw, th))
    tiles = []
    for i in range(blocks):
        row, col = i//best[0], i%best[0]
        box = (col*sz, row*sz, (col+1)*sz, (row+1)*sz)
        tiles.append(resized.crop(box))
    if len(tiles) != 1:
        tiles.append(img.resize((sz, sz)))
    return tiles

def load_frame(path, sz=448, max_n=6):
    img = Image.open(path).convert("RGB")
    transform = build_transform(sz)
    tiles = dynamic_preprocess(img, sz=sz, max_n=max_n)
    return torch.stack([transform(t) for t in tiles])


# ── Yardımcılar ──

def fold(s):
    s = s or ""
    for a, b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),
                 ("Ğ","g"),("ğ","g"),("Ü","u"),("ü","u"),
                 ("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()

def score(text, names):
    ft = fold(text)
    hits = sum(1 for n in names if fold(n) in ft)
    return hits, len(names)

def get_frames(folders, budget=BUDGET_PER_FOLDER):
    frames = []
    for key, (folder, window) in folders.items():
        if not os.path.exists(folder):
            continue
        pngs = sorted(glob.glob(os.path.join(folder, "*.png"))) or \
               sorted(glob.glob(os.path.join(folder, "*.jpg")))
        if not pngs:
            continue
        pool = pngs[-window:] if "last" in key else pngs[:window]
        step = max(1, len(pool) // budget)
        frames.extend(pool[::step][:budget])
    return frames


# ── Ana çalışma ──

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Model yükleniyor...", flush=True)
    t0 = time.time()
    model = AutoModel.from_pretrained(
        SNAP, torch_dtype=torch.bfloat16, trust_remote_code=True,
        use_flash_attn=False, low_cpu_mem_usage=True
    ).eval().cuda()
    tokenizer = AutoTokenizer.from_pretrained(SNAP, trust_remote_code=True, use_fast=False)
    load_time = time.time()-t0
    vram_load = torch.cuda.memory_allocated()/1024**3
    print(f"Yüklendi: {load_time:.1f}s, VRAM: {vram_load:.2f}GB", flush=True)

    gen_cfg = dict(max_new_tokens=512, do_sample=False)
    results = {
        "model": "InternVL3-8B",
        "label": "InternVL3-8B (transformers/hf-cache)",
        "durum": "OK",
        "load_time_s": round(load_time, 1),
        "vram_load_gb": round(vram_load, 2),
        "filmler": []
    }

    for film in TEST_FILMS:
        frames = get_frames(film["folders"])
        if not frames:
            print(f"[{film['id']}]: KARE YOK")
            results["filmler"].append({"id": film["id"], "durum": "KARE_YOK"})
            continue

        print(f"\n[{film['id']}] {len(frames)} kare...", flush=True)
        t_film = time.time()
        combined = []

        for i, fp in enumerate(frames):
            try:
                pv = load_frame(fp).to(torch.bfloat16).cuda()
                q = "<image>\n" + PROMPT
                resp = model.chat(tokenizer, pv, q, gen_cfg)
                combined.append(f"[Kare {i+1}] {resp}")
                print(f"  Kare {i+1}: {resp[:80]}")
            except Exception as e:
                combined.append(f"[Kare {i+1} HATA: {e}]")
                print(f"  Kare {i+1} HATA: {e}")

        full_text = "\n".join(combined)
        elapsed = time.time()-t_film
        peak_vram = torch.cuda.max_memory_allocated()/1024**3

        print(f"\n  Süre: {elapsed:.1f}s, Peak VRAM: {peak_vram:.2f}GB")

        gold = GOLD.get(film["id"], {})
        hy, ty = score(full_text, gold.get("yonetmen", []))
        ho, to_ = score(full_text, gold.get("oyuncular", []))
        has_tr = any(c in full_text for c in "İıŞşĞğÜüÖöÇç")
        print(f"  Skor: Yönetmen {hy}/{ty}, Oyuncu {ho}/{to_}, TR-karakter: {has_tr}")

        results["filmler"].append({
            "id": film["id"], "label": film["label"],
            "kare_sayisi": len(frames), "sure_sn": round(elapsed, 1),
            "cikti": full_text,
            "hit_yonetmen": f"{hy}/{ty}", "hit_oyuncu": f"{ho}/{to_}",
            "turkce_karakter": has_tr,
            "peak_vram_gb": round(peak_vram, 2)
        })

    del model
    torch.cuda.empty_cache()
    print("\nGPU serbest bırakıldı.")

    out_j = os.path.join(OUTPUT_DIR, "internvl3_smoke.json")
    with open(out_j, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"JSON: {out_j}")

    out_t = os.path.join(OUTPUT_DIR, "internvl3_smoke.txt")
    lines = ["InternVL3-8B SMOKE TEST SONUÇLARI", "="*60, ""]
    lines.append(f"Model yükleme: {results['load_time_s']}s, VRAM: {results['vram_load_gb']}GB")
    lines.append("")
    for film in results["filmler"]:
        if "hit_oyuncu" in film:
            lines.append(f"[{film['id']}] Yönetmen:{film['hit_yonetmen']} Oyuncu:{film['hit_oyuncu']} TR:{film['turkce_karakter']} Süre:{film['sure_sn']}s Peak:{film['peak_vram_gb']}GB")
            lines.append(f"  RAW: {film['cikti'][:600]}")
            lines.append("")
    with open(out_t, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"TXT: {out_t}")


if __name__ == "__main__":
    main()
