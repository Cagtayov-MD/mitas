# -*- coding: utf-8 -*-
"""YEREL ÖZET KANITI — map-reduce vs tek-atış, gerçek transkriptte.
Batch'i bozmamak için YALNIZ yüklü qwen3:8b kullanır (büyük model yüklemez)."""
import os, sys, io, glob, json, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"E:\MITAS\scripts")
from _ollama import ollama_chat

MODEL = "qwen3:8b"          # ZATEN yüklü → eviction yok → batch bozulmaz
TRT = "1999-0473-1-0000-00-1"   # ÖLÜM BÖLGESİ (transkript tam, dil TR, özet boştu)
DB = r"E:\MITAS\Database"
V5 = open(r"E:\MITAS\core\api\prompts\ozet_film.txt", encoding="utf-8").read()

def wc(s): return len(re.findall(r"\w+", s or ""))

# --- transkripti bul ---
trans = None
title = "?"
for d in glob.glob(os.path.join(DB, "*", "_DURUM.json")):
    j = json.load(open(d, encoding="utf-8"))
    if j.get("trt_id") == TRT:
        title = j.get("title", "?")
        hub = os.path.dirname(d)
        for cand in ("transcript_plain.txt", "transcript.txt"):
            g = glob.glob(os.path.join(hub, "asr", "*", "run", cand))
            if g:
                trans = open(g[0], encoding="utf-8").read(); break
        break
if not trans:
    print("Transkript bulunamadı"); sys.exit(1)
print(f"FİLM: {title}  | transkript: {len(trans)} karakter (~{wc(trans)} kelime)\n")

def ask(prompt, timeout=180):
    r = ollama_chat(model=MODEL, prompt=prompt, think=False, timeout=timeout,
                    options={"temperature": 0.2})
    return (r or {}).get("response", "").strip()

# ============ YAKLAŞIM A: TEK-ATIŞ (mevcut mantık, yerelde) ============
t0 = time.perf_counter()
# 8192 bağlama sığması için head+tail ~20K karakter
oneshot_src = trans[:14000] + "\n...\n" + trans[-6000:]
a = ask(f"{V5}\n\n--- TRANSCRIPT ---\n{oneshot_src}\n\n--- ÖZET ---")
ta = time.perf_counter() - t0

# ============ YAKLAŞIM B: MAP-REDUCE ============
t0 = time.perf_counter()
N = 6
step = len(trans) // N
chunks = [trans[i*step:(i+1)*step] for i in range(N)]
beats = []
for i, ch in enumerate(chunks):
    b = ask(
        "Aşağıdaki metin bir Türkçe filmin transkriptinin bir bölümü (ASR çıktısı, gürültülü). "
        "SADECE bu bölümde GERÇEKTEN geçen somut olayları, karakter adlarını ve dönüm noktalarını "
        "kısa madde madde yaz. Tahmin/yorum/tema YOK; olmayan olayı UYDURMA. Türkçe.\n\n"
        f"--- BÖLÜM {i+1}/{N} ---\n{ch}\n\n--- BU BÖLÜMÜN OLAYLARI ---", timeout=120)
    beats.append(f"[Bölüm {i+1}]\n{b}")
    print(f"  ...böl {i+1}/{N} olay-notu çıkarıldı ({wc(b)} kelime)")
beats_txt = "\n\n".join(beats)
b_final = ask(
    f"{V5}\n\n"
    f"Film adı: {title}. Aşağıda filmin BÖLÜM BÖLÜM olay notları var (baştan sona sıralı). "
    f"Bu notlardaki olayları birleştirip yukarıdaki v5 kurallarına göre TEK özet yaz. "
    f"Notlarda olmayan hiçbir şeyi ekleme.\n\n--- OLAY NOTLARI ---\n{beats_txt}\n\n--- ÖZET ---",
    timeout=180)
tb = time.perf_counter() - t0

print("\n" + "="*70)
print(f"YAKLAŞIM A — TEK-ATIŞ  ({ta:.0f}s, {wc(a)} kelime)")
print("="*70)
print(a)
print("\n" + "="*70)
print(f"YAKLAŞIM B — MAP-REDUCE  ({tb:.0f}s, {wc(b_final)} kelime)")
print("="*70)
print(b_final)
