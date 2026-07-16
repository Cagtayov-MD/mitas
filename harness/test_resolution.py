# -*- coding: utf-8 -*-
"""test_resolution.py — GPT fikri testi: yüksek-çözünürlük + crop, ATTİLA kırmızı-scroll körlüğünü çözer mi?
Aynı VLM (qwen3-vl:30b), aynı prompt; sadece downscale çözünürlüğü + crop değişkeni.
Ground-truth: ATTİLA #143/#332/#899=footage/beach, #560-830=KIRMIZI KREDİ(=CREDIT olmalı).
"""
import sys, os, io, json, base64, urllib.request, glob
sys.path.insert(0, "/opt/mitas/scripts")
from pathlib import Path
from PIL import Image, ImageOps
import credit_start_vlm as cvlm

RUN = "/opt/mitas/candidate_runs/kunye51_20260714"
cd = [d for d in glob.glob(f"{RUN}/Database/*") if "ATTİLA_MARCEL" in os.path.basename(d)][0]
full = sorted(Path(cd, "frames", "cikis").glob("*.png"))

def enc(path, long_edge, crop=False):
    im = Image.open(path).convert("RGB")
    if crop:  # merkez %70 crop (yazı bölgesine yakınlaş) sonra long_edge
        w, h = im.size
        im = im.crop((int(w*0.12), int(h*0.12), int(w*0.88), int(h*0.88)))
    w, h = im.size
    s = long_edge / max(w, h)
    if s < 1.0:
        im = im.resize((max(1,int(w*s)), max(1,int(h*s))), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()

def classify_res(path, long_edge, crop=False):
    b64 = enc(path, long_edge, crop)
    body = {"model": cvlm.MODEL, "messages": [{"role":"user","content":cvlm._PROMPT,"images":[b64]}],
            "stream": False, "options": {"temperature":0,"num_ctx":8192,"num_predict":64}}
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(
            cvlm.OLLAMA + "/api/chat", data=json.dumps(body).encode(),
            headers={"Content-Type":"application/json"}), timeout=120).read())
        msg = r.get("message", {}) or {}
        txt = (msg.get("content") or "") or (msg.get("thinking") or "")
        return cvlm._parse_label(txt)[0]
    except Exception as e:
        return f"ERR:{e}"

# test kareleri: index → beklenen
TESTS = [
    (143, "footage(otobüs)"), (332, "footage(tarla)"),
    (560, "KIRMIZI-KREDİ"), (650, "KIRMIZI-KREDİ"), (750, "KIRMIZI-KREDİ"), (830, "KIRMIZI-KREDİ"),
    (899, "footage(plaj)"),
]
CONFIGS = [("512", 512, False), ("640", 640, False), ("768", 768, False), ("640+crop", 640, True)]

print(f"{'kare':>18} | " + " | ".join(f"{c[0]:>10}" for c in CONFIGS))
print("-"*72)
for idx, exp in TESTS:
    labs = [classify_res(full[idx], le, cr) for _, le, cr in CONFIGS]
    print(f"#{idx} {exp:>13} | " + " | ".join(f"{l:>10}" for l in labs))
