# -*- coding: utf-8 -*-
"""TEZ KANITI — aynı 35B, map-reduce YOK, tüm transkript TEK pencerede.
Matt/Palmer doğru birleşirse → hata model değil, parçalanma (cloud'un full-context avantajı)."""
import os, sys, io, glob, json, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
sys.path.insert(0, r"E:\MITAS\scripts")
from _ollama import ollama_chat

MODEL = "qwen3.6:atlas1"
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

print(f"FİLM: {title} | {len(trans)} karakter (~{wc(trans)} kelime) | TEK-GEÇİŞ full-context\n", flush=True)
t0 = time.perf_counter()
r = ollama_chat(model=MODEL,
                prompt=f"{V5}\n\n--- TRANSCRIPT (TAMAMI) ---\n{trans}\n\n--- ÖZET ---",
                think=False, timeout=600,
                options={"temperature": 0.2, "num_ctx": 16384}, keep_alive="5m")
out = (r or {}).get("response", "").strip()
dt = time.perf_counter() - t0
print("="*70, flush=True)
print(f"TEK-GEÇİŞ FİNAL ÖZET — {wc(out)} kelime | {dt:.0f}s", flush=True)
print("="*70, flush=True)
print(out if out else "(BOŞ — muhtemelen num_ctx VRAM'e sığmadı / OOM)", flush=True)
