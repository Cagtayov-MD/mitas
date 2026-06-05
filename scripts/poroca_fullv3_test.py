#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""poroca_fullv3_test.py — MADDE 3(c) ÖLÇÜM: yabancı-ses filminde FULL large-v3 vs mevcut turbo.
POROROCA (Romence) sesinin ilk 5 dk'sını full large-v3 (beam=5, auto-detect) ile yeniden-ASR et,
mevcut turbo transkriptiyle YAN YANA bas. Amaç: full large-v3 yabancı transkripti TEMİZ üretiyor mu
(→ özet düzelir mi) yoksa ses zaten çok mu bozuk (→ web-köprüsü şart). venvs/asr python ile koş."""
import sys, os, glob, time, subprocess
sys.stdout.reconfigure(encoding="utf-8")
from faster_whisper import WhisperModel

CLIP = r"E:\MITAS\Database\L_MC_L_JENERK_S_NEMA_F_LM4_2017-2124-1-0000-67-1-POROROCA"
FF = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
OUT = r"E:\MITAS\outputs\model_test\poroca_fullv3.txt"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

wav = os.path.join(CLIP, "audio", "audio16k.wav")
if not os.path.exists(wav):
    src = next(iter(glob.glob(os.path.join(CLIP, "source", "*.*"))), None)
    if not src:
        print("[HATA] ne audio16k ne source var"); sys.exit(1)
    wav = os.path.join(os.path.dirname(OUT), "poroca_16k.wav")
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
                    "-vn", "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", wav], check=True)

print("[full large-v3] yükleniyor (ilk sefer ~3GB iner)...", flush=True)
t0 = time.time()
m = WhisperModel("large-v3", device="cuda", compute_type="float16")  # turbo DEĞİL — FULL
print(f"    yüklendi {time.time()-t0:.0f}s", flush=True)

t1 = time.time()
segs, info = m.transcribe(wav, language=None, beam_size=5, vad_filter=True,
                          vad_parameters=dict(min_silence_duration_ms=500),
                          condition_on_previous_text=False, word_timestamps=False)
print(f"    tespit dil: {info.language} ({info.language_probability:.2f})", flush=True)
lines = []
for s in segs:
    lines.append(s.text.strip())
    if s.end > 300:   # ilk 5 dk yeterli (kalite örneği)
        break
full_text = " ".join(lines)
dt = time.time() - t1
open(OUT, "w", encoding="utf-8").write(full_text)

print(f"\n========== FULL large-v3 (ilk 5dk · dil={info.language} · {dt:.0f}s · beam=5) ==========")
print(full_text[:1600])
turbo = next(iter(glob.glob(os.path.join(CLIP, "asr", "*", "run", "transcript_plain.txt")) +
                  glob.glob(os.path.join(CLIP, "asr", "*", "run", "transcript.txt")) +
                  glob.glob(os.path.join(CLIP, "asr", "*", "transcript*.txt"))), None)
print(f"\n========== MEVCUT TURBO (overnight, ilk kısım) ==========")
print(open(turbo, encoding="utf-8").read()[:1600] if turbo else "(turbo transkripti yok)")
print("\n→ KIYAS: full large-v3 daha TEMİZ/anlamlı Romence mi üretti? (özet bundan yazılabilir mi?)")
print("POROCA_DONE")
