# -*- coding: utf-8 -*-
"""YEREL 35B GERÇEK ÇIKTI — qwen3.6:atlas1 (zaten yüklü) map-reduce, ÖLÜM BÖLGESİ."""
import os, sys, io, glob, json, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
sys.path.insert(0, r"E:\MITAS\scripts")
from _ollama import ollama_chat

MODEL = "qwen3.6:atlas1"          # ZATEN yüklü (23GB) → yükleme yok
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
print(f"FİLM: {title} | {len(trans)} karakter (~{wc(trans)} kelime) | MODEL: {MODEL}\n", flush=True)

def ask(prompt, timeout=300):
    r = ollama_chat(model=MODEL, prompt=prompt, think=False, timeout=timeout,
                    options={"temperature": 0.2, "num_ctx": 8192}, keep_alive="5m")
    return (r or {}).get("response", "").strip()

# MAP: 6 parça (4096 bağlama sığsın) → olay notu
N = 6
step = len(trans) // N
beats = []
t0 = time.perf_counter()
for i in range(N):
    ch = trans[i*step:(i+1)*step]
    b = ask("Aşağıdaki metin bir Türkçe filmin transkriptinin bir bölümü (ASR, gürültülü). "
            "SADECE bu bölümde GERÇEKTEN geçen somut olayları, karakter adlarını ve dönüm "
            "noktalarını kısa madde madde yaz. Tahmin/yorum YOK; olmayan olayı UYDURMA.\n\n"
            f"--- BÖLÜM {i+1}/{N} ---\n{ch}\n\n--- OLAYLAR ---")
    beats.append(f"[Bölüm {i+1}]\n{b}")
    print(f"=== BÖLÜM {i+1}/{N} ({wc(b)} kelime, {time.perf_counter()-t0:.0f}s) ===\n{b}\n", flush=True)

# REDUCE: v5 sentez
final = ask(f"{V5}\n\nFilm adı: {title}. Aşağıda filmin bölüm bölüm olay notları var (sıralı). "
            f"Bunlardaki olayları birleştirip yukarıdaki v5 kurallarına göre TEK özet yaz. "
            f"Notlarda olmayan hiçbir şey ekleme.\n\n--- OLAY NOTLARI ---\n"
            + "\n\n".join(beats) + "\n\n--- ÖZET ---")
toplam = time.perf_counter() - t0
print("="*70, flush=True)
print(f"YEREL 35B FİNAL ÖZET — {wc(final)} kelime | TOPLAM SÜRE {toplam:.0f}s ({N} parça + sentez)", flush=True)
print("="*70, flush=True)
print(final, flush=True)
