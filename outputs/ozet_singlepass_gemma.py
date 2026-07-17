# -*- coding: utf-8 -*-
"""TEZ KANITI (temiz) — KÜÇÜK model + BÜYÜK bağlam → tüm transkript gerçekten sığar.
gemma3:12b (8GB) → KV'ye yer var → num_ctx 24576. Matt/Palmer birleşirse: bağlam > model-boyutu."""
import os, sys, io, glob, json, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
sys.path.insert(0, r"E:\MITAS\scripts")
from _ollama import ollama_chat

MODEL = "gemma3:12b"
TRT = "1999-0473-1-0000-00-1"
V5 = open(r"E:\MITAS\core\api\prompts\ozet_film.txt", encoding="utf-8").read()
DB = r"E:\MITAS\Database"
def wc(s): return len(re.findall(r"\w+", s or ""))

trans, title = None, "?"
for d in glob.glob(os.path.join(DB, "*", "_DURUM.json")):
    j = json.load(open(d, encoding="utf-8"))
    if j.get("trt_id") == TRT:
        title = j.get("title", "?"); hub = os.path.dirname(d)
        for c in ("transcript_plain.txt", "transcript.txt"):
            g = glob.glob(os.path.join(hub, "asr", "*", "run", c))
            if g: trans = open(g[0], encoding="utf-8").read(); break
        break

print(f"FİLM: {title} | {len(trans)} karakter (~{wc(trans)} kelime) | gemma3:12b TEK-GEÇİŞ ctx=24576\n", flush=True)

# 1) Önce SADECE kimlik sorusu — full-context'te Matt=Palmer'ı çözüyor mu?
t0 = time.perf_counter()
kimlik = ollama_chat(model=MODEL,
    prompt=("Aşağıda bir filmin tam transkripti var (ASR, gürültülü). SADECE şunu cevapla: "
            "Bu filmin ANA karakteri kimdir ve hangi farklı adlarla/takma adlarla anılıyor? "
            "Özellikle 'Matt', 'Palmer', 'Matthew Pellman' AYNI kişi mi yoksa farklı kişiler mi? "
            "Kısa ve net.\n\n--- TRANSKRİPT ---\n" + trans),
    timeout=500, options={"temperature": 0.0, "num_ctx": 24576}, keep_alive="5m")
kimlik_txt = (kimlik or {}).get("response", "").strip()
print(f"=== KİMLİK ÇÖZÜMÜ ({time.perf_counter()-t0:.0f}s) ===\n{kimlik_txt or '(BOŞ)'}\n", flush=True)

# 2) Sonra full-context özet
t1 = time.perf_counter()
r = ollama_chat(model=MODEL,
    prompt=f"{V5}\n\n--- TRANSCRIPT (TAMAMI) ---\n{trans}\n\n--- ÖZET ---",
    timeout=500, options={"temperature": 0.2, "num_ctx": 24576}, keep_alive="5m")
out = (r or {}).get("response", "").strip()
print("="*70, flush=True)
print(f"gemma3:12b TEK-GEÇİŞ ÖZET — {wc(out)} kelime | {time.perf_counter()-t1:.0f}s", flush=True)
print("="*70, flush=True)
print(out if out else "(BOŞ)", flush=True)
