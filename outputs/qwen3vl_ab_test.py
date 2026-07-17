#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qwen3vl_ab_test.py — qwen2.5vl:7b vs qwen3-vl:30b vs qwen3-vl:8b adil karsilastirma.

API DUZELTMESI:
  Onceki A/B'de qwen3-vl kaybetmisinin nedeni:
    - _ollama.py: stream=False hardcoded → think=False olsa bile
      qwen3-vl thinking tokenlarini tukettikten sonra content="" donuyor
      (thinking tokenlar num_predict limitini dolduruyor, content'e yer kalmıyor)
    - Duzeltme: stream=True ile chunk'lari topla → content ve thinking ayri gelir

  Bu script dogrudan urllib ile /api/chat cagirir, stream=True kullanir.

Test filmleri (frames/giris + frames/cikis):
  1. IVAN'IN COCUKLUGU (Rusça orijinal, garble riski)
  2. KADIN AFFETMEZ (Türkce)
  3. BABA (Türkce)

Kullanim:
  python outputs/qwen3vl_ab_test.py
"""
import base64
import glob
import io
import json
import os
import sys
import time
import urllib.request
import re
import unicodedata

# Pillow import (venvs\asr veya global)
try:
    from PIL import Image
except ImportError:
    sys.path.insert(0, r"E:\MITAS\venvs\asr\Lib\site-packages")
    from PIL import Image

OLLAMA_HOST = "http://127.0.0.1:11434"
FRAME_W = 640
BUDGET = 12          # her segment icin max kare; 12+12=24 kare ~ 25k token (32768 ctx icine sigdirir)
LONG_THR = 1500
END_WIN = 900
NUM_CTX = 32768      # 24 kare * ~1050 tok/kare = ~25k + prompt ~200 tok -> sigdirir
NUM_PREDICT = 4000   # qwen3-vl görsel+thinking için yeterli pay (8b ~6000c thinking ~ 1500tok görsel ile)

PROMPT = (
    "Bunlar bir film jeneriğinin ARDIŞIK kareleri (video). Kareler boyunca görünen yazıları "
    "birleştirerek şunları bul. SADECE karelerde AÇIKÇA YAZAN isimleri kullan, uydurma YOK; "
    "görmüyorsan 'yok' yaz. "
    "Çıktıyı TAM OLARAK şu formatta ver:\n"
    "YÖNETMEN: <isim | yok>\n"
    "YAPIMCI: <isim(ler) | yok>\n"
    "OYUNCULAR: <başrol oyuncu adları virgülle, en fazla 6 | yok>"
)

TEST_FILMS = [
    {
        "ad": "IVAN'IN COCUKLUGU (1962, Rusca)",
        "giris": r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S27_1962-1124-1-0000-72-1-IVAN_IN__OCUKLU_U\frames\giris",
        "cikis": r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S27_1962-1124-1-0000-72-1-IVAN_IN__OCUKLU_U\frames\cikis",
        "gercek": {
            "yonetmen": "Andrei Tarkovsky",
            "yapimci": "G. Kuznetsova",
            "cast": ["Nikolai Burlyaev", "Valentin Zubkov", "Yevgeni Zharikov"]
        }
    },
    {
        "ad": "KADIN AFFETMEZ (1971, Turkce)",
        "giris": r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S27_1971-0093-1-0000-00-1-KADIN_AFFETMEZ\frames\giris",
        "cikis": r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S27_1971-0093-1-0000-00-1-KADIN_AFFETMEZ\frames\cikis",
        "gercek": {
            "yonetmen": "Aram Gulyuz",
            "yapimci": None,
            "cast": None  # dogrulanacak
        }
    },
    {
        "ad": "BABA (1988, Turkce)",
        "giris": r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S28_1988-0342-1-0000-00-1-BABA\frames\giris",
        "cikis": r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S28_1988-0342-1-0000-00-1-BABA\frames\cikis",
        "gercek": {
            "yonetmen": "Halit Refig",
            "yapimci": None,
            "cast": None
        }
    },
]

MODELS = [
    ("qwen2.5vl:7b",  "stream=False (baseline, orijinal yontem)"),
    ("qwen3-vl:30b",  "stream=True think=False (API-duzeltilmis)"),
    ("qwen3-vl:8b",   "stream=True think=False (API-duzeltilmis)"),
]


# ─────────────────────── yardimcilar ───────────────────────

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

def sample_basson(frames, budget=BUDGET):
    n = len(frames)
    if n > LONG_THR:
        h = budget // 2
        return _even(frames[:END_WIN], h) + _even(frames[-END_WIN:], budget - h)
    return _even(frames, budget)

def encode_frame(path):
    im = Image.open(path).convert("RGB")
    if im.width > FRAME_W:
        im = im.resize((FRAME_W, round(im.height * FRAME_W / im.width)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


# ─────────────────────── VLM cagrisi: eski (stream=False) ───────────────────────

def call_stream_false(model, images_b64):
    """Orijinal yontem: stream=False. qwen3-vl icin bozuk."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT, "images": images_b64}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "repeat_penalty": 1.3,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_HOST + "/api/chat",
        data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            resp = json.loads(r.read())
            content = (resp.get("message", {}).get("content") or "").strip()
            thinking = (resp.get("message", {}).get("thinking") or "")
            return content, len(thinking)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:200]
        return f"HATA HTTP{e.code}: {err}", 0
    except Exception as e:
        return f"HATA: {e}", 0


# ─────────────────────── VLM cagrisi: yeni (stream=True) ───────────────────────

def call_stream_true(model, images_b64):
    """Duzeltilmis yontem: stream=True, thinking ayri toplanir."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT, "images": images_b64}],
        "stream": True,
        "think": False,
        "options": {
            "temperature": 0,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "repeat_penalty": 1.3,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_HOST + "/api/chat",
        data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST"
    )
    content_parts = []
    thinking_chars = 0
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            for line in r:
                line = line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = chunk.get("message", {})
                if msg.get("content"):
                    content_parts.append(msg["content"])
                if msg.get("thinking"):
                    thinking_chars += len(msg["thinking"])
                if chunk.get("done"):
                    break
        return "".join(content_parts).strip(), thinking_chars
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:200]
        return f"HATA HTTP{e.code}: {err}", 0
    except Exception as e:
        return f"HATA: {e}", 0


# ─────────────────────── cagri yonlendirici ───────────────────────

def vlm_call(model, images_b64):
    """
    qwen2.5vl -> stream=False (orijinal, referans)
    qwen3-vl  -> stream=True + think=False (duzeltilmis)
    """
    if model.startswith("qwen3"):
        return call_stream_true(model, images_b64)
    else:
        return call_stream_false(model, images_b64)


# ─────────────────────── ana test dongusu ───────────────────────

def parse_field(text, key):
    for line in (text or "").splitlines():
        k_fold = key.lower().replace("ö","o").replace("ü","u").replace("ı","i").replace("ğ","g").replace("ş","s").replace("ç","c")
        l_fold = line.lower().replace("ö","o").replace("ü","u").replace("ı","i").replace("ğ","g").replace("ş","s").replace("ç","c")
        if l_fold.strip().startswith(k_fold.rstrip(":")):
            return line.split(":", 1)[1].strip() if ":" in line else ""
    return ""

def run_test():
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 70)
    print("qwen3-vl ADIL TEST -- API DUZELTILMIS (stream=True)")
    print("=" * 70)

    results = {}  # film -> model -> {"content", "thinking_chars", "sure"}

    for film in TEST_FILMS:
        print(f"\n{'-'*60}")
        print(f"FILM: {film['ad']}")
        print(f"{'-'*60}")

        # Kareleri bir kez yükle
        giris_frames = sample_basson(list_frames(film["giris"])) if os.path.isdir(film["giris"]) else []
        cikis_frames = sample_basson(list_frames(film["cikis"])) if os.path.isdir(film["cikis"]) else []
        all_frames = giris_frames + cikis_frames

        if not all_frames:
            print(f"  UYARI: Kare bulunamadi, atlanıyor.")
            continue

        # Kareleri encode et (bir kez, tüm modeller paylaşır)
        print(f"  {len(all_frames)} kare encode ediliyor ({len(giris_frames)} giris + {len(cikis_frames)} cikis)...")
        t0 = time.time()
        images_b64 = [encode_frame(f) for f in all_frames]
        print(f"  Encode: {time.time()-t0:.1f}s")

        results[film["ad"]] = {}

        for model, aciklama in MODELS:
            print(f"\n  MODEL: {model}  ({aciklama})")
            t0 = time.time()
            content, thinking_chars = vlm_call(model, images_b64)
            sure = time.time() - t0

            results[film["ad"]][model] = {
                "content": content,
                "thinking_chars": thinking_chars,
                "sure": sure,
            }

            # Parse
            yon = parse_field(content, "YÖNETMEN")
            yap = parse_field(content, "YAPIMCI")
            oyu = parse_field(content, "OYUNCULAR")

            print(f"    sure={sure:.1f}s  thinking={thinking_chars}c")
            print(f"    YONETMEN : {yon or '(bos)'}")
            print(f"    YAPIMCI  : {yap or '(bos)'}")
            print(f"    OYUNCULAR: {oyu or '(bos)'}")

            if not content or content.startswith("HATA"):
                print(f"    !!! BOSH/HATA yanit: {repr(content[:100])}")

            # Gerçek zemin karsilastirma
            gercek_yon = film["gercek"].get("yonetmen")
            if gercek_yon:
                yon_fold = yon.lower().replace(" ","")
                gercek_fold = gercek_yon.lower().replace(" ","")
                eslesme = gercek_fold in yon_fold or yon_fold in gercek_fold
                print(f"    GERCEK YON: {gercek_yon} -> {'DOGRU' if eslesme else 'YANLIS'}")

    # ─── OZET TABLOSU ───
    print("\n\n" + "=" * 70)
    print("OZET TABLOSU")
    print("=" * 70)
    print(f"{'Film':<35} {'Model':<20} {'Sur(s)':<8} {'Think(c)':<10} {'YON':<25} {'BOSH?'}")
    print("-" * 110)

    for film in TEST_FILMS:
        film_ad = film["ad"]
        if film_ad not in results:
            continue
        for model, _ in MODELS:
            if model not in results[film_ad]:
                continue
            r = results[film_ad][model]
            content = r["content"]
            yon = parse_field(content, "YÖNETMEN")
            bosh = "BOŞ!" if (not content or content.startswith("HATA") or not yon) else ""
            print(f"{film_ad[:34]:<35} {model:<20} {r['sure']:<8.1f} {r['thinking_chars']:<10} {yon[:24]:<25} {bosh}")

    print("\n" + "=" * 70)
    print("SONUC: API duzeltmesi (stream=True) qwen3-vl'i kurtardi mi?")
    print("  qwen3-vl:30b stream=False'de content='' (thinking token tukeniyor)")
    print("  qwen3-vl:30b stream=True'de content dolu gelmeli")
    print("=" * 70)

    # JSON kaydet
    out_path = r"E:\MITAS\outputs\qwen3vl_ab_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nHam sonuclar: {out_path}")


if __name__ == "__main__":
    run_test()
