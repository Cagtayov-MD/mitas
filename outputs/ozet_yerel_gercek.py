# -*- coding: utf-8 -*-
"""YEREL MODELİN GERÇEK ÇIKTISI — qwen3:8b map-reduce, ÖLÜM BÖLGESİ.
Batch'i bozmamak için GPU'da yer açılmasını BEKLER, sonra koşar. Ham çıktıyı yazar."""
import os, sys, io, glob, json, time, re, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
sys.path.insert(0, r"E:\MITAS\scripts")
from _ollama import ollama_chat

MODEL = "qwen3:8b"
TRT = "1999-0473-1-0000-00-1"
V5 = open(r"E:\MITAS\core\api\prompts\ozet_film.txt", encoding="utf-8").read()
DB = r"E:\MITAS\Database"
def wc(s): return len(re.findall(r"\w+", s or ""))

def gpu_free_mb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            timeout=10).decode().strip().splitlines()[0]
        return int(out)
    except Exception:
        return 0

# transkript bul
trans, title = None, "?"
for d in glob.glob(os.path.join(DB, "*", "_DURUM.json")):
    j = json.load(open(d, encoding="utf-8"))
    if j.get("trt_id") == TRT:
        title = j.get("title", "?"); hub = os.path.dirname(d)
        for c in ("transcript_plain.txt", "transcript.txt"):
            g = glob.glob(os.path.join(hub, "asr", "*", "run", c))
            if g: trans = open(g[0], encoding="utf-8").read(); break
        break
print(f"FİLM: {title} | {len(trans)} karakter (~{wc(trans)} kelime)\n", flush=True)

# GPU'da yer açılmasını bekle (qwen3:8b ~6GB ister)
print("GPU'da yer bekleniyor (>=7000 MB boş)...", flush=True)
for i in range(150):                       # ~30 dk üst sınır
    free = gpu_free_mb()
    if free >= 7000:
        print(f"  ✓ yer açıldı: {free} MB boş — başlıyorum\n", flush=True); break
    if i % 5 == 0:
        print(f"  ... {free} MB boş, bekliyorum ({i*12}s)", flush=True)
    time.sleep(12)
else:
    print("30 dk içinde yeterli yer açılmadı; batch çok yoğun. Çıkıyorum.", flush=True)
    sys.exit(0)

def ask(prompt, timeout=300):
    r = ollama_chat(model=MODEL, prompt=prompt, think=False, timeout=timeout,
                    options={"temperature": 0.2}, keep_alive="2m")
    return (r or {}).get("response", "").strip()

# MAP: 4 parça → olay notu
N = 4
step = len(trans) // N
beats = []
for i in range(N):
    ch = trans[i*step:(i+1)*step]
    b = ask("Aşağıdaki metin bir Türkçe filmin transkriptinin bir bölümü (ASR, gürültülü). "
            "SADECE bu bölümde GERÇEKTEN geçen somut olayları, karakter adlarını ve dönüm "
            "noktalarını kısa madde madde yaz. Tahmin/yorum YOK; olmayan olayı UYDURMA.\n\n"
            f"--- BÖLÜM {i+1}/{N} ---\n{ch}\n\n--- OLAYLAR ---")
    beats.append(f"[Bölüm {i+1}]\n{b}")
    print(f"=== BÖLÜM {i+1}/{N} OLAY NOTU ({wc(b)} kelime) ===\n{b}\n", flush=True)

# REDUCE: v5 sentez
final = ask(f"{V5}\n\nFilm adı: {title}. Aşağıda filmin bölüm bölüm olay notları var (sıralı). "
            f"Bunlardaki olayları birleştirip yukarıdaki v5 kurallarına göre TEK özet yaz. "
            f"Notlarda olmayan hiçbir şey ekleme.\n\n--- OLAY NOTLARI ---\n"
            + "\n\n".join(beats) + "\n\n--- ÖZET ---")
print("="*70, flush=True)
print(f"YEREL MODEL ({MODEL}) FİNAL ÖZET — {wc(final)} kelime", flush=True)
print("="*70, flush=True)
print(final, flush=True)
