#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
"""
native_video_test.py — Qwen2.5-VL ve Qwen3-VL için:
  1. GÖRÜNTÜ-LİSTESİ modu: her kare ayrı {"type":"image",...}
  2. NATIVE-VİDEO modu: {"type":"video","video":[...], "fps":2.0}
  Aynı kareler, aynı prompt, tek fark mod.

Kullanım:
  python outputs/native_video_test.py
"""

import os, sys, time, json, re, glob
import unicodedata

# HF cache konumunu E: diske yönlendir (C: dolup taşmasın)
os.environ["HF_HOME"] = "E:\\hf_cache_vl"
os.environ["HUGGINGFACE_HUB_CACHE"] = "E:\\hf_cache_vl\\hub"
os.environ.setdefault("TRANSFORMERS_CACHE", "E:\\hf_cache_vl\\hub")

import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoTokenizer, AutoProcessor
from qwen_vl_utils import process_vision_info

# ─────────────────────── yapılandırma ───────────────────────
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
ATTN = "sdpa"  # Windows'ta flash_attn yok → sdpa
DTYPE = torch.float16

# Filmler: (isim, giris_frames_dir, cikis_frames_dir, gercek_yonetmen, gercek_cast_en_az_1)
FILMS = [
    {
        "isim": "FARGO (1996)",
        "giris": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_1996-1042-1-0000-50-0-FARGO\frames\giris",
        "cikis": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_1996-1042-1-0000-50-0-FARGO\frames\cikis",
        "gercek_yonetmen": "Joel Coen",
        "gercek_cast": ["Frances McDormand", "William H. Macy", "Steve Buscemi"],
    },
    {
        "isim": "KAZANMA SANATI / Moneyball (2011)",
        "giris": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_2011-1010-1-0000-50-0-KAZANMA_SANATI\frames\giris",
        "cikis": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_2011-1010-1-0000-50-0-KAZANMA_SANATI\frames\cikis",
        "gercek_yonetmen": "Bennett Miller",
        "gercek_cast": ["Brad Pitt", "Jonah Hill", "Philip Seymour Hoffman"],
    },
]

PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştirerek şunları bul. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, uydurma; yoksa 'yok'. "
    "Çıktıyı tam olarak şu formatta ver:\n"
    "YÖNETMEN: <Director/Yöneten/Rejisör yanındaki isim | yok>\n"
    "YAPIMCI: <Producer/Yapımcı/Executive Producer yanındaki isim(ler) | yok>\n"
    "OYUNCULAR: <görünen başrol oyuncu adları, en fazla 8, virgülle | yok>"
)

# Qwen2.5-VL-7B önce, sonra Qwen3-VL-8B
MODELS_TO_TEST = [
    {
        "key": "qwen25vl",
        "hf_name": "Qwen/Qwen2.5-VL-7B-Instruct",
        "label": "Qwen2.5-VL-7B",
        "model_class": "Qwen2_5_VLForConditionalGeneration",
    },
    # Qwen3-VL-8B sonra (bağımsız yükleme)
    {
        "key": "qwen3vl",
        "hf_name": "Qwen/Qwen3-VL-8B-Instruct",
        "label": "Qwen3-VL-8B",
        "model_class": "AutoModelForImageTextToText",
    },
]

SAMPLE_N = 20  # her segment için kare sayısı (toplam 40 / 2 segment)

# ─────────────────────── kare örnekleme ───────────────────────
def list_frames(d):
    files = (
        sorted(glob.glob(os.path.join(d, "g_*.png")))
        + sorted(glob.glob(os.path.join(d, "c_*.png")))
        + sorted(glob.glob(os.path.join(d, "f_*.png")))
        + sorted(glob.glob(os.path.join(d, "*.jpg")))
    )
    return files

def even_sample(pool, k):
    if len(pool) <= k:
        return pool
    return [pool[round(i * (len(pool) - 1) / (k - 1))] for i in range(k)]

def sample_frames(giris_dir, cikis_dir, n=SAMPLE_N):
    """Giris baş+son n/2 + cikis baş+son n/2 → toplam ~2*n kare."""
    frames = []
    for d in [giris_dir, cikis_dir]:
        if d and os.path.isdir(d):
            pool = list_frames(d)
            if pool:
                half = n // 2
                # baş yarısı
                frames += even_sample(pool[:len(pool)//2], half)
                # son yarısı
                frames += even_sample(pool[len(pool)//2:], n - half)
    return frames

# ─────────────────────── model yükleme ───────────────────────
def load_model(hf_name, model_class_str):
    print(f"\n[YÜKLEME] {hf_name} ({model_class_str})", flush=True)
    t0 = time.time()
    if model_class_str == "Qwen2_5_VLForConditionalGeneration":
        from transformers import Qwen2_5_VLForConditionalGeneration
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            hf_name,
            torch_dtype=DTYPE,
            attn_implementation=ATTN,
            device_map="auto",
        )
    else:
        from transformers import AutoModelForImageTextToText
        model = AutoModelForImageTextToText.from_pretrained(
            hf_name,
            torch_dtype=DTYPE,
            attn_implementation=ATTN,
            device_map="auto",
        )
    processor = AutoProcessor.from_pretrained(hf_name)
    elapsed = time.time() - t0
    mem = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
    print(f"  → yüklendi {elapsed:.1f}s, VRAM kullanım: {mem:.1f} GB", flush=True)
    return model, processor

# ─────────────────────── çıkarım ───────────────────────
def run_inference(model, processor, frames, mode):
    """
    mode: "image_list" veya "native_video"
    Döndürür: (metin_cevap, sure_sn)
    """
    assert mode in ("image_list", "native_video")

    if mode == "image_list":
        content = []
        for f in frames:
            content.append({"type": "image", "image": f})
        content.append({"type": "text", "text": PROMPT})
    else:  # native_video
        content = [
            {"type": "video", "video": frames, "fps": 2.0},
            {"type": "text", "text": PROMPT},
        ]

    messages = [{"role": "user", "content": content}]

    text_input = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text_input],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(DEVICE)

    t0 = time.time()
    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=400,
            do_sample=False,
            temperature=None,
            top_p=None,
        )
    elapsed = time.time() - t0

    # trim prompt token'larını
    generated_ids_trimmed = [
        out_ids[len(in_ids):]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0]
    return output_text.strip(), elapsed

# ─────────────────────── sonuç değerlendirme ───────────────────────
def fold(s):
    s = s or ""
    for a, b in (("İ","i"),("I","i"),("ı","i"),("Ş","s"),("ş","s"),
                 ("Ğ","g"),("ğ","g"),("Ü","u"),("ü","u"),
                 ("Ö","o"),("ö","o"),("Ç","c"),("ç","c")):
        s = s.replace(a, b)
    return unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().lower().strip()

def parse_field(text, key):
    for line in (text or "").splitlines():
        if fold(line).startswith(fold(key)):
            return line.split(":",1)[1].strip() if ":" in line else ""
    return ""

def check_match(okunan, gercek_liste):
    """Okunan metinde gerçek isimlerden en az biri var mı?"""
    okunan_f = fold(okunan)
    for g in gercek_liste:
        if fold(g) in okunan_f or all(fold(w) in okunan_f for w in g.split() if len(w) > 2):
            return True
    return False

# ─────────────────────── ANA DÖNGÜ ───────────────────────
def main():
    results = []
    log_lines = []

    def log(s):
        print(s, flush=True)
        log_lines.append(s)

    log(f"[BAŞLANGIÇ] {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"DEVICE: {DEVICE}, DTYPE: {DTYPE}, ATTN: {ATTN}")
    log(f"torch: {torch.__version__}")

    import transformers
    log(f"transformers: {transformers.__version__}")

    # Filmlerin karelerini önceden örnekle
    film_frames = {}
    for film in FILMS:
        frames = sample_frames(film["giris"], film["cikis"], n=SAMPLE_N)
        film_frames[film["isim"]] = frames
        log(f"  Film: {film['isim']} -> {len(frames)} kare orneklendi")

    for minfo in MODELS_TO_TEST:
        log(f"\n{'='*60}")
        log(f"MODEL: {minfo['label']} ({minfo['hf_name']})")
        log(f"{'='*60}")

        try:
            t_load_start = time.time()
            model, processor = load_model(minfo["hf_name"], minfo["model_class"])
            t_load = time.time() - t_load_start
            log(f"  Yükleme süresi: {t_load:.1f}s")
        except Exception as e:
            log(f"  [HATA] Model yüklenemedi: {e}")
            for film in FILMS:
                for mode in ["image_list", "native_video"]:
                    results.append({
                        "film": film["isim"], "model": minfo["label"], "mod": mode,
                        "yonetmen_okunan": "YÜKLEME HATASI", "cast_okunan": "",
                        "sure_sn": 0, "yonetmen_dogru": False, "cast_dogru": False,
                        "ham": str(e),
                    })
            continue

        for film in FILMS:
            frames = film_frames[film["isim"]]
            log(f"\n  Film: {film['isim']} ({len(frames)} kare)")

            for mode in ["image_list", "native_video"]:
                log(f"    Mod: {mode} ...", )
                try:
                    cevap, sure = run_inference(model, processor, frames, mode)
                except Exception as e:
                    log(f"      [HATA] {e}")
                    results.append({
                        "film": film["isim"], "model": minfo["label"], "mod": mode,
                        "yonetmen_okunan": f"HATA: {e}", "cast_okunan": "",
                        "sure_sn": 0, "yonetmen_dogru": False, "cast_dogru": False,
                        "ham": str(e),
                    })
                    continue

                yon_okunan = parse_field(cevap, "YÖNETMEN")
                cast_okunan = parse_field(cevap, "OYUNCULAR")

                yon_dogru = check_match(yon_okunan, [film["gercek_yonetmen"]])
                cast_dogru = check_match(cast_okunan, film["gercek_cast"])

                log(f"      YÖNETMEN: {yon_okunan!r}  {'✓' if yon_dogru else '✗'} (gerçek: {film['gercek_yonetmen']})")
                log(f"      OYUNCULAR: {cast_okunan!r}  {'✓' if cast_dogru else '✗'}")
                log(f"      Süre: {sure:.1f}s")

                results.append({
                    "film": film["isim"],
                    "model": minfo["label"],
                    "mod": mode,
                    "yonetmen_okunan": yon_okunan,
                    "cast_okunan": cast_okunan,
                    "sure_sn": round(sure, 1),
                    "yonetmen_dogru": yon_dogru,
                    "cast_dogru": cast_dogru,
                    "ham": cevap,
                })

        # Modeli bellekten temizle
        log("\n  [TEMİZLEME] Model GPU'dan siliniyor...")
        del model
        torch.cuda.empty_cache()
        import gc; gc.collect()

    # ─── RAPOR ───
    log("\n\n" + "="*60)
    log("SONUÇ TABLOSU")
    log("="*60)
    header = f"{'Film':<35} {'Model':<18} {'Mod':<14} {'Yön?':<6} {'Cast?':<6} {'Süre':>6}"
    log(header)
    log("-"*90)
    for r in results:
        yn = "✓" if r["yonetmen_dogru"] else "✗"
        cn = "✓" if r["cast_dogru"] else "✗"
        row = f"{r['film'][:34]:<35} {r['model']:<18} {r['mod']:<14} {yn:<6} {cn:<6} {r['sure_sn']:>5.1f}s"
        log(row)

    # JSON kaydet
    out_json = "E:\\MITAS\\outputs\\native_video_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log(f"\n[JSON] {out_json}")

    # MD rapor
    md_lines = [
        "# Native Video Test — Sonuçlar",
        f"Tarih: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Kurulum",
        f"- Env: E:\\MITAS\\venvs\\vlm",
        f"- transformers: {transformers.__version__}",
        f"- torch: {torch.__version__}",
        f"- attn: {ATTN} (flash_attn kurulmadı — sdpa)",
        f"- DEVICE: {DEVICE}",
        "",
        "## Sonuç Tablosu",
        "",
        "| Film | Model | Mod | Yönetmen Okunan | Cast OK | Süre |",
        "|------|-------|-----|-----------------|---------|------|",
    ]
    for r in results:
        yn = "✓" if r["yonetmen_dogru"] else "✗"
        cn = "✓" if r["cast_dogru"] else "✗"
        md_lines.append(f"| {r['film']} | {r['model']} | {r['mod']} | {r['yonetmen_okunan']} {yn} | {cn} | {r['sure_sn']}s |")

    md_lines += ["", "## Ham Çıktılar", ""]
    for r in results:
        md_lines.append(f"### {r['film']} / {r['model']} / {r['mod']}")
        md_lines.append("```")
        md_lines.append(r["ham"][:1000])
        md_lines.append("```")
        md_lines.append("")

    # Analiz bölümü (ham sonuçlardan)
    qwen25_rows = [r for r in results if "2.5" in r["model"]]
    qwen3_rows = [r for r in results if "3-VL" in r["model"] or "Qwen3" in r["model"]]

    md_lines += ["## Analiz", ""]
    if qwen25_rows:
        img_rows = [r for r in qwen25_rows if r["mod"] == "image_list"]
        vid_rows = [r for r in qwen25_rows if r["mod"] == "native_video"]
        img_yon = sum(1 for r in img_rows if r["yonetmen_dogru"])
        vid_yon = sum(1 for r in vid_rows if r["yonetmen_dogru"])
        md_lines.append(f"**Qwen2.5-VL — image_list yönetmen doğru: {img_yon}/{len(img_rows)}**")
        md_lines.append(f"**Qwen2.5-VL — native_video yönetmen doğru: {vid_yon}/{len(vid_rows)}**")
        if vid_yon > img_yon:
            md_lines.append("→ Native video DAHA İYİ")
        elif vid_yon < img_yon:
            md_lines.append("→ Image list DAHA İYİ")
        else:
            md_lines.append("→ FARK YOK (aynı)")
        md_lines.append("")

    if qwen3_rows:
        vid_yon = sum(1 for r in qwen3_rows if r["yonetmen_dogru"] and r["mod"] == "native_video")
        q25_vid = sum(1 for r in qwen25_rows if r["yonetmen_dogru"] and r["mod"] == "native_video")
        md_lines.append(f"**Qwen3-VL-8B native_video yönetmen: {vid_yon}/{len([r for r in qwen3_rows if r['mod']=='native_video'])}**")
        md_lines.append(f"**Qwen2.5-VL-7B native_video yönetmen: {q25_vid}/{len([r for r in qwen25_rows if r['mod']=='native_video'])}**")
        md_lines.append("")

    out_md = "E:\\MITAS\\outputs\\NATIVE_VIDEO_TEST_20260613.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    log(f"[MD] {out_md}")

    log("\n[BİTİŞ] " + time.strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == "__main__":
    main()
