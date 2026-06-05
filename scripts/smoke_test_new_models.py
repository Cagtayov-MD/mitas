#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
smoke_test_new_models.py
3 YENİ MODEL icin KUNYE-OKUMA SMOKE TEST
- gemma3:12b (ollama) — multimodal, vision var
- InternVL3-8B (transformers, hf-cache) — zaten indirilmis
- gemma4:12b / PaddleOCR-VL — durum notu

Test filmleri:
  1. DRAKULA'NIN GELİNLERİ (giris+cikis frames)
  2. ATTİLA MARCEL (giris+cikis)
  3. YALAZA (giris)

Cikti: E:\MITAS\outputs\model_test\smoke_results.json + smoke_results.txt
"""
import base64
import glob
import io
import json
import os
import re
import sys
import time
import urllib.request
import unicodedata
from pathlib import Path
from PIL import Image

# ───────────────────────────────────────────────
OUTPUT_DIR = r"E:\MITAS\outputs\model_test"
OLLAMA_BASE = "http://127.0.0.1:11434"
FRAME_W = 640  # genislik (VRAM/token tasarrufu)
BUDGET = 10    # smoke test: 10 kare / segment (az ama temsili)

PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştirerek şunları bul. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, uydurma; yoksa 'yok'. "
    "Çıktıyı tam olarak şu formatta ver:\n"
    "YÖNETMEN: <Director/Yöneten/Rejisör yanındaki isim | yok>\n"
    "YAPIMCI: <Producer/Yapımcı/Executive Producer yanındaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen başrol oyuncu adları, en fazla 8, virgülle | yok>"
)

# Beklenen cast
GOLD = {
    "DRAKULA": {
        "yonetmen": ["Terence Fisher"],
        "oyuncular": ["Peter Cushing", "Martita Hunt", "Yvonne Monlaur", "David Peel"]
    },
    "ATTILA": {
        "yonetmen": ["Sylvain Chomet"],
        "oyuncular": ["Guillaume Gouix", "Anne Le Ny", "Bernadette Lafont"]
    },
    "YALAZA": {
        "yonetmen": [],
        "oyuncular": []  # Türkçe isim testi — manual review gerekir
    }
}

TEST_FILMS = [
    {
        "id": "DRAKULA",
        "label": "DRAKULA'NIN GELINLERİ (1960)",
        "folders": [
            r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S17_1960-0046-1-0000-00-1-DRAKULA_NIN_GEL_NLER\frames\giris",
            r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S17_1960-0046-1-0000-00-1-DRAKULA_NIN_GEL_NLER\frames\cikis",
        ]
    },
    {
        "id": "ATTILA",
        "label": "ATTİLA MARCEL (2013)",
        "folders": [
            r"E:\MITAS\Database\evoArcadmin_S_NEMA_F_LM4_2013-1015-1-0000-70-1-ATT_LA_MARCEL\frames\giris",
            r"E:\MITAS\Database\evoArcadmin_S_NEMA_F_LM4_2013-1015-1-0000-70-1-ATT_LA_MARCEL\frames\cikis",
        ]
    },
    {
        "id": "YALAZA",
        "label": "YALAZA (Türkçe-isim testi)",
        "folders": [
            r"E:\MITAS\Database\web_client_dad_2017-0019-0-0001-90-1-YALAZA\frames\giris",
        ]
    },
]

def fold(s):
    s = s or ""
    for a, b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),
                 ("Ğ","g"),("ğ","g"),("Ü","u"),("ü","u"),
                 ("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()

def score_names(found_text, expected_names):
    """Bulunan isimlerden kaç tanesi expected_names içinde var (fold ile)."""
    found_fold = fold(found_text)
    hits = sum(1 for n in expected_names if fold(n) in found_fold)
    return hits, len(expected_names)

def sample_frames(folders, budget):
    """Birden fazla klasörden eşit dağılımla BUDGET kare seç."""
    all_frames = []
    for folder in folders:
        if os.path.exists(folder):
            pngs = sorted(glob.glob(os.path.join(folder, "*.png")))
            jpgs = sorted(glob.glob(os.path.join(folder, "*.jpg")))
            frames = pngs if pngs else jpgs
            all_frames.extend(frames)
    if not all_frames:
        return []
    step = max(1, len(all_frames) // budget)
    return all_frames[::step][:budget]

def resize_to_b64(path, width=FRAME_W):
    """Kareyi yeniden boyutlandır ve base64 döndür."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    if w > width:
        img = img.resize((width, int(h * width / w)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()

# ───────────────────────── MODEL 1: gemma3:12b (ollama) ─────────────────────────

def run_ollama_model(model_tag, frames, prompt, timeout=120):
    """ollama /api/chat images[] ile çalıştır, metin döndür."""
    images_b64 = []
    for f in frames:
        try:
            images_b64.append(resize_to_b64(f))
        except Exception as e:
            print(f"  [UYARI] Kare yüklenemedi {f}: {e}")

    if not images_b64:
        return "[kare yok]", 0.0

    payload = {
        "model": model_tag,
        "messages": [{"role": "user", "content": prompt, "images": images_b64}],
        "stream": False,
        "options": {
            "num_ctx": 8192,
            "num_predict": 600,
            "temperature": 0,
            "think": False
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_BASE + "/api/chat",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read())
        elapsed = time.time() - t0
        text = raw.get("message", {}).get("content", "") or raw.get("response", "")
        return text.strip(), elapsed
    except Exception as e:
        return f"[HATA: {e}]", time.time() - t0


def smoke_ollama(model_tag, model_label):
    """Ollama modeliyle tüm test filmlerini çalıştır."""
    print(f"\n{'='*60}")
    print(f"MODEL: {model_label} ({model_tag})")
    print(f"{'='*60}")

    # Bağlantı testi
    try:
        req = urllib.request.Request(OLLAMA_BASE + "/api/tags")
        with urllib.request.urlopen(req, timeout=10) as r:
            pass
        print("  Ollama: BAĞLANTILI")
    except Exception as e:
        print(f"  Ollama: BAĞLANTI HATASI — {e}")
        return {"model": model_tag, "label": model_label, "durum": f"BAĞLANTI HATASI: {e}", "filmler": []}

    results = {"model": model_tag, "label": model_label, "durum": "OK", "filmler": []}

    for film in TEST_FILMS:
        frames = sample_frames(film["folders"], BUDGET)
        if not frames:
            print(f"  {film['id']}: KARE YOK — atlanıyor")
            results["filmler"].append({"id": film["id"], "durum": "KARE_YOK"})
            continue

        print(f"\n  [{film['id']}] {len(frames)} kare...", flush=True)
        text, elapsed = run_ollama_model(model_tag, frames, PROMPT)
        print(f"  Süre: {elapsed:.1f}s")
        print(f"  Çıktı:\n{text}")

        gold = GOLD.get(film["id"], {})
        hit_y, tot_y = score_names(text, gold.get("yonetmen", []))
        hit_o, tot_o = score_names(text, gold.get("oyuncular", []))

        # Türkçe karakter kontrolü
        has_tr_chars = any(c in text for c in "İıŞşĞğÜüÖöÇç")

        print(f"  Yönetmen: {hit_y}/{tot_y}, Oyuncu: {hit_o}/{tot_o}, Türkçe-karakter: {has_tr_chars}")

        results["filmler"].append({
            "id": film["id"],
            "label": film["label"],
            "kare_sayisi": len(frames),
            "sure_sn": round(elapsed, 1),
            "cikti": text,
            "hit_yonetmen": f"{hit_y}/{tot_y}",
            "hit_oyuncu": f"{hit_o}/{tot_o}",
            "turkce_karakter": has_tr_chars,
        })

    return results


# ───────────────────────── MODEL 2: InternVL3-8B (transformers) ─────────────────────────

def smoke_internvl3():
    """InternVL3-8B transformers ile test — minicpmv venv'de çalıştırılmalı."""
    print(f"\n{'='*60}")
    print("MODEL: InternVL3-8B (transformers/hf-cache)")
    print(f"{'='*60}")

    SNAP = r"E:\MITAS\hf-cache\hub\models--OpenGVLab--InternVL3-8B\snapshots\853e3a797a661694b1b8ece0cb72dc2b23e3dac9"

    try:
        import torch
        import torchvision.transforms as T
        from torchvision.transforms.functional import InterpolationMode
        from transformers import AutoModel, AutoTokenizer
    except ImportError as e:
        msg = f"[IMPORT HATASI: {e}] — minicpmv venvde çalıştırın"
        print(f"  {msg}")
        return {"model": "InternVL3-8B", "label": "InternVL3-8B (transformers)", "durum": msg, "filmler": []}

    IMAGENET_MEAN = (0.485, 0.456, 0.406)
    IMAGENET_STD  = (0.229, 0.224, 0.225)

    def build_transform(size):
        return T.Compose([
            T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
            T.Resize((size, size), interpolation=InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ])

    def find_closest_ratio(ar, ratios, w, h, sz):
        best_diff = float("inf")
        best = (1,1)
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
        best = find_closest_ratio(ar, ratios, w, h, sz)
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

    print("  Model yükleniyor...", flush=True)
    t0 = time.time()
    try:
        os.environ["HF_HOME"] = r"E:\MITAS\hf-cache"
        os.environ["HF_HUB_OFFLINE"] = "1"
        model = AutoModel.from_pretrained(
            SNAP, torch_dtype=torch.bfloat16, trust_remote_code=True,
            use_flash_attn=False, low_cpu_mem_usage=True
        ).eval().cuda()
        tokenizer = AutoTokenizer.from_pretrained(SNAP, trust_remote_code=True, use_fast=False)
        load_time = time.time() - t0
        vram_gb = torch.cuda.memory_allocated() / 1024**3
        print(f"  Yüklendi: {load_time:.1f}s, VRAM: {vram_gb:.2f}GB")
    except Exception as e:
        return {"model": "InternVL3-8B", "label": "InternVL3-8B (transformers)",
                "durum": f"MODEL YÜKLEME HATASI: {e}", "filmler": []}

    gen_cfg = dict(max_new_tokens=512, do_sample=False)
    results = {"model": "InternVL3-8B", "label": "InternVL3-8B (transformers)",
               "durum": "OK", "load_time_s": round(load_time, 1),
               "vram_load_gb": round(vram_gb, 2), "filmler": []}

    INTERNVL_PROMPT = (
        "Bunlar bir film jeneriginin ardisik kareleri. Gorundugu gibi yaz, uydurma; yoksa 'yok'.\n"
        "YONETMEN: <isim|yok>\nYAPIMCI: <isim|yok>\nOYUNCULAR: <virgullu liste|yok>"
    )

    for film in TEST_FILMS:
        frames = sample_frames(film["folders"], BUDGET)
        if not frames:
            results["filmler"].append({"id": film["id"], "durum": "KARE_YOK"})
            continue

        print(f"\n  [{film['id']}] {len(frames)} kare...", flush=True)
        t_film = time.time()

        # Her kare ayrı mesaj olarak (context'te biriktirelim)
        combined_text = []
        try:
            for i, fp in enumerate(frames[:6]):  # max 6 kare (VRAM)
                pv = load_frame(fp).to(torch.bfloat16).cuda()
                question = "<image>\n" + INTERNVL_PROMPT
                resp = model.chat(tokenizer, pv, question, gen_cfg)
                combined_text.append(f"[Kare {i+1}] {resp}")
                vram_now = torch.cuda.max_memory_allocated() / 1024**3
            full_text = "\n".join(combined_text)
        except Exception as e:
            full_text = f"[HATA: {e}]"

        elapsed = time.time() - t_film
        print(f"  Süre: {elapsed:.1f}s")
        print(f"  Çıktı:\n{full_text[:600]}")

        gold = GOLD.get(film["id"], {})
        hit_y, tot_y = score_names(full_text, gold.get("yonetmen", []))
        hit_o, tot_o = score_names(full_text, gold.get("oyuncular", []))
        has_tr = any(c in full_text for c in "İıŞşĞğÜüÖöÇç")

        print(f"  Yönetmen: {hit_y}/{tot_y}, Oyuncu: {hit_o}/{tot_o}, Türkçe-karakter: {has_tr}")
        peak_vram = torch.cuda.max_memory_allocated() / 1024**3

        results["filmler"].append({
            "id": film["id"], "label": film["label"],
            "kare_sayisi": len(frames), "sure_sn": round(elapsed, 1),
            "cikti": full_text[:1500], "hit_yonetmen": f"{hit_y}/{tot_y}",
            "hit_oyuncu": f"{hit_o}/{tot_o}", "turkce_karakter": has_tr,
            "peak_vram_gb": round(peak_vram, 2)
        })

    del model
    torch.cuda.empty_cache()
    print("  GPU serbest bırakıldı.")
    return results


# ───────────────────────── ANA AKIŞ ─────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_results = []

    # ── 1. gemma3:12b (ollama, multimodal) ──
    r1 = smoke_ollama("gemma3:12b", "gemma3:12b (ollama, vision)")
    all_results.append(r1)

    # ── 2. InternVL3-8B (transformers) — sadece bu scriptin venv'i destekliyorsa ──
    r2 = smoke_internvl3()
    all_results.append(r2)

    # ── 3. PaddleOCR-VL: durum notu ──
    paddle_note = {
        "model": "PaddleOCR-VL-1.6",
        "label": "PaddleOCR-VL 1.6",
        "durum": (
            "ZATEN GÜNCEL DEĞİL UYARISI: venvs/ocr'da paddleocr 3.5.0 + paddlepaddle-gpu 3.3.1 MEVCUT. "
            "PaddleOCR-VL 1.6 PaddleX 3.x tabanlıdır (paddleocr>=3.0 = VL desteği var). "
            "Mevcut kurulum zaten PaddleOCR-VL API'sine sahip olabilir — "
            "paddleocr 3.5.0 == VL 1.6'nın üstünde bir sürüm. "
            "Ayrı kurulum gerekmeyebilir; test: from paddleocr import PaddleOCR (VL modları için)."
        ),
        "filmler": []
    }
    all_results.append(paddle_note)

    # ── Kaydet ──
    out_json = os.path.join(OUTPUT_DIR, "smoke_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nJSON kaydedildi: {out_json}")

    # ── Özet rapor ──
    out_txt = os.path.join(OUTPUT_DIR, "smoke_results.txt")
    lines = ["MITAS YENİ MODEL SMOKE TEST RAPORU", "="*60, ""]
    for r in all_results:
        lines.append(f"MODEL: {r['label']}")
        lines.append(f"  Durum: {r['durum']}")
        for film in r.get("filmler", []):
            if "hit_oyuncu" in film:
                lines.append(
                    f"  [{film['id']}] Yönetmen:{film['hit_yonetmen']} "
                    f"Oyuncu:{film['hit_oyuncu']} "
                    f"Türkçe:{film['turkce_karakter']} "
                    f"Süre:{film['sure_sn']}s"
                )
        lines.append("")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"TXT kaydedildi: {out_txt}")


if __name__ == "__main__":
    main()
