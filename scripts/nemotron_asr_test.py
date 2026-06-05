#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""nemotron_asr_test.py — nvidia/nemotron-3.5-asr-streaming-0.6b'yi MEVCUT large-v3-turbo'ya karşı
TÜRKÇE bir filmde yan-yana karşılaştır (transkript kalitesi gözle + hız).

KURULUM (bir kez, izole venv):
  python -m venv E:\\MITAS\\venvs\\nemo
  E:\\MITAS\\venvs\\nemo\\Scripts\\python.exe -m pip install -U pip
  E:\\MITAS\\venvs\\nemo\\Scripts\\python.exe -m pip install "nemo_toolkit[asr]" torch --index-url https://download.pytorch.org/whl/cu121
  (model from_pretrained ilk çağrıda hf-cache'e iner ~1.5GB)

ÇALIŞTIR:
  E:\\MITAS\\venvs\\nemo\\Scripts\\python.exe scripts/nemotron_asr_test.py [klip_dizini]
  (varsayılan: YALAZA — Türkçe dizi; istersen başka klip ver)

NE YAPAR: klibin audio16k.wav'ından İLK 120 sn'yi alır → nemotron ile transcribe →
mevcut turbo transkriptinin (Database'de hazır) ilk kısmıyla YAN YANA basar + hız. Türkçe
kalitesini (isimler/kelimeler/İ-Ş-Ğ/noktalama) GÖZLE kıyasla. WER referansımız olmadığı için
nicel değil, niteliksel + hız ölçümü."""
import sys, os, glob, time, subprocess
sys.stdout.reconfigure(encoding="utf-8")

CLIP = sys.argv[1] if len(sys.argv) > 1 else r"E:\MITAS\Database\web_client_dad_2017-0019-0-0001-90-1-YALAZA"
FF = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
SECONDS = 120

wav = os.path.join(CLIP, "audio", "audio16k.wav")
if not os.path.exists(wav):
    print(f"[HATA] audio16k yok: {wav}"); sys.exit(1)

# mevcut turbo transkripti (Database'de hazır)
turbo_txt = next(iter(
    glob.glob(os.path.join(CLIP, "asr", "*", "run", "transcript_plain.txt")) +
    glob.glob(os.path.join(CLIP, "asr", "*", "run", "transcript.txt")) +
    glob.glob(os.path.join(CLIP, "asr", "*", "transcript*.txt"))), None)

# 120 sn dilim
slice_wav = os.path.join(os.path.dirname(wav), "_nemotest_120.wav")
subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", wav,
                "-t", str(SECONDS), "-ar", "16000", "-ac", "1", slice_wav], check=True)

print(f"=== Klip: {os.path.basename(CLIP)} | {SECONDS}s dilim ===", flush=True)
print("[nemotron] yükleniyor (ilk sefer model iner)...", flush=True)
import nemo.collections.asr as nemo_asr
t0 = time.time()
m = nemo_asr.models.ASRModel.from_pretrained("nvidia/nemotron-3.5-asr-streaming-0.6b")
load = time.time() - t0
t1 = time.time()
out = m.transcribe([slice_wav])
dt = time.time() - t1
o = out[0]
nemo_text = getattr(o, "text", None) or (o[0] if isinstance(o, (list, tuple)) else str(o))

print(f"\n========== NEMOTRON-3.5-ASR (yükleme {load:.0f}s · transcribe {dt:.0f}s · ~{SECONDS/max(1,dt):.0f}x realtime) ==========")
print((nemo_text or "")[:1800])
print(f"\n========== MEVCUT large-v3-turbo (Database'deki hazır transkript, ilk kısım) ==========")
print(open(turbo_txt, encoding="utf-8").read()[:1800] if turbo_txt else "(turbo transkripti bulunamadı)")
print("\n→ GÖZLE KIYASLA: Türkçe kelime/isim doğruluğu, İ-Ş-Ğ-ç, noktalama, anlam bütünlüğü. + hız.")
print("NEMOTEST_DONE")
