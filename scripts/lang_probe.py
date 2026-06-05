#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lang_probe.py — bir videonun c0 (diyalog) kanalını FULL large-v3 ile birkaç noktadan dinle,
TESPİT EDİLEN dili + transkript örneğini bas. Amaç: turbo'nun 'tr' sandığı sesin gerçek dilini
(Azerice/Kürtçe/Arapça...) ÖLÇMEK (tahmin değil). Koş: venvs/asr python lang_probe.py "<mp4>" [stream] [channel]"""
import sys, os, subprocess
sys.stdout.reconfigure(encoding="utf-8")
from faster_whisper import WhisperModel

SRC = sys.argv[1]
ST = sys.argv[2] if len(sys.argv) > 2 else "0"
CH = sys.argv[3] if len(sys.argv) > 3 else "0"
FF = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
TMP = r"E:\MITAS\outputs\model_test\_langprobe.wav"
os.makedirs(os.path.dirname(TMP), exist_ok=True)

print(f"[full large-v3] yükleniyor... (kanal a:{ST}/c{CH})", flush=True)
m = WhisperModel(r"E:\MITAS\models\asr\faster-whisper\large-v3", device="cuda", compute_type="float16")
print("    yüklendi\n", flush=True)

votes = {}
for t in [300, 600, 900, 1200, 1500, 1800, 2100, 2400]:
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(t), "-t", "45", "-i", SRC,
                    "-map", f"0:a:{ST}", "-af", f"pan=mono|c0=c{CH}", "-ar", "16000",
                    "-acodec", "pcm_s16le", TMP], capture_output=True)
    if not os.path.exists(TMP):
        continue
    segs, info = m.transcribe(TMP, language=None, beam_size=5, vad_filter=True,
                              vad_parameters=dict(min_silence_duration_ms=500))
    txt = " ".join(s.text.strip() for s in segs)
    votes[info.language] = votes.get(info.language, 0) + float(info.language_probability or 0)
    print(f"t={t:>4}s  dil={info.language:4} ({info.language_probability:.2f})  »  {txt[:160]}", flush=True)

print(f"\n=== oy toplamı: {sorted(votes.items(), key=lambda x:-x[1])} ===")
print("LANGPROBE_DONE")
