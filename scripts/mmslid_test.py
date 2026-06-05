#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mmslid_test.py — Meta MMS-LID (facebook/mms-lid-1024) dil-tespiti testi.
1024 dil (Kürtçe kmr/ckb, Azerice azj, Arapça arb dahil) — transkripsiyon YOK, sadece "hangi dil".
4 filmde c0 diyalog kanalını 6 noktadan ölç. Beklenen: ALTIN YUMRUK→kmr, DERT BENDE→arb, ESKİ ŞEHİR→azj, YALAZA→tur.
venvs/asr python ile koş."""
import sys, os
os.environ["USE_TF"] = "0"; os.environ["USE_FLAX"] = "0"
import glob, subprocess
sys.stdout.reconfigure(encoding="utf-8")
import torch, librosa
from transformers import Wav2Vec2ForSequenceClassification, AutoFeatureExtractor

DB = r"E:\MITAS\Database"
MODEL_ID = "facebook/mms-lid-1024"
FF = r"E:\MITAS\tools\ffmpeg-shared\ffmpeg-8.1.1-full_build-shared\bin\ffmpeg.exe"
TMP = r"E:\MITAS\outputs\model_test\_mmslid.wav"
os.makedirs(os.path.dirname(TMP), exist_ok=True)
SR = 16000

def src(pat):
    g = glob.glob(os.path.join(DB, pat, "source", "*.*"))
    return g[0] if g else None

FILMS = [
    ("ALTIN YUMRUK (Kürtçe bekle → kmr/ckb)", "*ALTIN_YUMRUK*"),
    ("DERT BENDE   (Arapça bekle → arb)",      "*1973-0174*DERT*"),
    ("ESKİ ŞEHİR   (Azeri bekle → azj)",       "*2024-1032*ESK*"),
    ("YALAZA       (Türkçe bekle → tur)",      "*YALAZA*"),
]

print("[MMS-LID] indiriliyor/yükleniyor (~1GB ilk sefer)...", flush=True)
fe = AutoFeatureExtractor.from_pretrained(MODEL_ID)
model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_ID).to("cuda").eval()
print("    yüklendi\n", flush=True)

for name, pat in FILMS:
    s = src(pat)
    if not s:
        print(f"{name}: KAYNAK YOK\n", flush=True); continue
    votes = {}
    print(name, flush=True)
    for t in [300, 600, 900, 1200, 1500, 1800]:
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-ss", str(t), "-t", "20", "-i", s,
                        "-map", "0:a:0", "-af", "pan=mono|c0=c0", "-ar", "16000",
                        "-acodec", "pcm_s16le", TMP], capture_output=True)
        if not os.path.exists(TMP):
            continue
        y, _ = librosa.load(TMP, sr=SR, mono=True)
        inputs = fe(y, sampling_rate=SR, return_tensors="pt")
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
        with torch.no_grad():
            logits = model(**inputs).logits[0]
        probs = torch.softmax(logits, dim=-1)
        top = torch.topk(probs, 3)
        labs = [(model.config.id2label[i.item()], round(p.item(), 2)) for p, i in zip(top.values, top.indices)]
        votes[labs[0][0]] = votes.get(labs[0][0], 0) + labs[0][1]
        print(f"  t={t:>4}s  top3={labs}", flush=True)
    print(f"  ==> OYLAR: {sorted(votes.items(), key=lambda x: -x[1])}\n", flush=True)
print("MMSLID_DONE")
