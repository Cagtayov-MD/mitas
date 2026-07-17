#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ab_vl_test.py - qwen2.5vl:7b vs qwen3-vl:30b A/B karsilastirmasi

DEBUG BULGULARI:
- qwen2.5vl:7b: stream=False + num_ctx=24576 + budget=16 CALISIR.
- qwen3-vl:30b: think=False + stream=True + num_ctx=32768 + num_predict=4000 gerekli.
  Thinking tokenlar cevap tokenlarindan once geliyor; yüksek budget -> thinking çok büyüyor
  ve her seferinde farklı davranıyor (budget=8 iyi, budget=12 iyi, budget=16 vary).
  think=False olmadan model sadece thinking yapar, content bos kalir.
"""
import sys
import json
import time
import os
import base64
import io
import urllib.request
import urllib.error

sys.path.insert(0, r"E:\MITAS\scripts")
sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image
from credit_video_read import sample_basson, list_frames, parse_field, split_names, PROMPT, OLLAMA_HOST

# Her iki modele ayri ayari
CONFIG = {
    "qwen2.5vl:7b": {
        "budget": 16,
        "stream": False,
        "think": False,
        "num_ctx": 24576,
        "num_predict": 600,
        "repeat_penalty": 1.3,
    },
    "qwen3-vl:30b": {
        "budget": 8,       # 16 kare = thinking ~20K token -> tutarsiz; 8 kare daha güvenli
        "stream": True,
        "think": False,    # KRITIK: False olmadan model sadece thinking yapar
        "num_ctx": 32768,
        "num_predict": 4000,
        "repeat_penalty": 1.0,
    },
}

FRAME_W = 640

MODELS = ["qwen2.5vl:7b", "qwen3-vl:30b"]

FILMS = [
    {
        "ad": "FARGO (1996)",
        "giris": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_1996-1042-1-0000-50-0-FARGO\frames\giris",
        "cikis": r"E:\MITAS\Database\evoArcadmin__Z_MLEME10_1996-1042-1-0000-50-0-FARGO\frames\cikis",
        "gercek_yon": "ETHAN COEN / JOEL COEN",
        "gercek_yapimci": "TİM BEVAN, ERİC FELLNER, JOHN CAMERON",
        "gercek_cast": "WILLIAM H. MACY, STEVE BUSCEMI, FRANCES McDORMAND",
    },
    {
        "ad": "DRAKULA'NIN GELİNLERİ (1960)",
        "giris": r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S17_1960-0046-1-0000-00-1-DRAKULA_NIN_GEL_NLER\frames\giris",
        "cikis": r"E:\MITAS\Database\evoArcadmin_COZUMLEMEV2S17_1960-0046-1-0000-00-1-DRAKULA_NIN_GEL_NLER\frames\cikis",
        "gercek_yon": "TERENCE FISHER",
        "gercek_yapimci": "MICHAEL CARRERAS, ANTHONY HİNDS",
        "gercek_cast": "PETER CUSHING, MARTITA HUNT, DAVID PEEL",
    },
]


def _encode(path):
    im = Image.open(path).convert("RGB")
    if im.width > FRAME_W:
        im = im.resize((FRAME_W, round(im.height * FRAME_W / im.width)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def _call_model(model, imgs, cfg):
    """Model konfigürasyonuna göre dogru API modunu sec."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT, "images": imgs}],
        "stream": cfg["stream"],
        "keep_alive": "10m",
        "think": cfg["think"],
        "options": {
            "temperature": 0,
            "top_p": 1,
            "num_ctx": cfg["num_ctx"],
            "num_predict": cfg["num_predict"],
            "repeat_penalty": cfg["repeat_penalty"],
        },
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_HOST.rstrip("/") + "/api/chat",
        data=body_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        if cfg["stream"]:
            content = ""
            thinking_len = 0
            done_reason = ""
            with urllib.request.urlopen(req, timeout=900) as r:
                for line in r:
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    content += chunk.get("message", {}).get("content", "")
                    thinking_len += len(chunk.get("message", {}).get("thinking", ""))
                    if chunk.get("done"):
                        done_reason = chunk.get("done_reason", "")
                        break
            print(f"       [stream] thinking_chars={thinking_len}, done={done_reason}", flush=True)
            return content.strip()
        else:
            with urllib.request.urlopen(req, timeout=900) as r:
                resp = json.loads(r.read())
                return (resp.get("message", {}).get("content") or "").strip()
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  [HATA] HTTP {e.code}: {err[:200]}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"  [HATA] {type(e).__name__}: {e}", file=sys.stderr)
        return ""


def read_segment_ab(model, frames, cfg):
    imgs = [_encode(f) for f in frames]
    return _call_model(model, imgs, cfg)


def run_film_model(film, model):
    cfg = CONFIG[model]
    seg_frames = {}
    for seg, d in [("giris", film["giris"]), ("cikis", film["cikis"])]:
        if os.path.isdir(d):
            fr = sample_basson(list_frames(d), budget=cfg["budget"])
            if fr:
                seg_frames[seg] = fr
                print(f"  [{seg}] {len(fr)} kare", flush=True)

    results = {}
    for seg, fr in seg_frames.items():
        print(f"  -> {model} / {seg} ({len(fr)} kare)...", flush=True)
        t0 = time.time()
        ham = read_segment_ab(model, fr, cfg)
        elapsed = time.time() - t0
        yonetmen_raw = parse_field(ham, "YÖNETMEN")
        yapimci_raw = parse_field(ham, "YAPIMCI")
        oyuncular_raw = parse_field(ham, "OYUNCULAR")
        results[seg] = {
            "ham": ham,
            "yonetmen_raw": yonetmen_raw,
            "yapimci_raw": yapimci_raw,
            "oyuncular_raw": oyuncular_raw,
            "yonetmen": split_names(yonetmen_raw),
            "cast": split_names(oyuncular_raw),
            "sure_s": round(elapsed, 1),
        }
        print(f"     sure: {elapsed:.1f}s", flush=True)
        print(f"     yon : {yonetmen_raw!r}", flush=True)
        print(f"     cast: {oyuncular_raw!r}", flush=True)
    return results


print("=" * 70)
print("A/B VL Testi: qwen2.5vl:7b vs qwen3-vl:30b")
print("qwen2.5vl: budget=16, stream=False, num_ctx=24576")
print("qwen3-vl : budget=8,  stream=True,  think=False, num_ctx=32768, num_predict=4000")
print("=" * 70)

all_results = {}

for model in MODELS:
    print(f"\n{'#'*50}")
    print(f"### MODEL: {model} ###")
    print(f"{'#'*50}")
    all_results[model] = {}
    for film in FILMS:
        print(f"\n  Film: {film['ad']}")
        all_results[model][film["ad"]] = run_film_model(film, model)

print("\n")
print("=" * 70)
print("SONUC TABLOSU")
print("=" * 70)

for film in FILMS:
    fname = film["ad"]
    print(f"\n{'─'*65}")
    print(f"FİLM: {fname}")
    print(f"  Gerçek yönetmen: {film['gercek_yon']}")
    print(f"  Gerçek yapımcı : {film['gercek_yapimci']}")
    print(f"  Gerçek cast    : {film['gercek_cast']}")
    print(f"{'─'*65}")
    for model in MODELS:
        r = all_results.get(model, {}).get(fname, {})
        print(f"\n  [{model}]")
        for seg in ["giris", "cikis"]:
            sr = r.get(seg)
            if sr:
                print(f"    [{seg}] {sr['sure_s']}s")
                print(f"      YÖN : {sr['yonetmen_raw']!r}")
                print(f"      YAP : {sr['yapimci_raw']!r}")
                print(f"      CAST: {sr['oyuncular_raw']!r}")
            else:
                print(f"    [{seg}] HATA/YOK")

out_path = r"E:\MITAS\outputs\ab_vl_sonuc.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)
print(f"\nHam JSON: {out_path}")
print("\nTEST TAMAMLANDI.")
