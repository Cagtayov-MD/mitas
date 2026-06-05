#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""music_gate_test.py — Çağatay'ın MÜZİK-GATE fikrinin PROTOTİP testi (production'a dokunmadan).

Her dil-tespit örneğini önce 'bu müzik mi?' diye AST (AudioSet) ile sınıflandır; MÜZİK ise
LID oyuna KATMA, sadece KONUŞMA örneklerinden dil tespit et. Arabesk/müzik-ağır filmde
(DERT BENDE turbo->AR/full->ru, DİRİLİŞ->ar) dil YANLIŞ çıkıyordu; müzik atlanınca DİYALOGDAN
doğru TR çıkmalı. Türkçe filmde (YALAZA) regresyon OLMAMALI.
Koş: venvs/asr/Scripts/python.exe scripts/music_gate_test.py"""
import sys, os
os.environ["USE_TF"] = "0"; os.environ["USE_FLAX"] = "0"   # transformers TF'yi import etmesin (numpy2 çakışması)
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
sys.stdout.reconfigure(encoding="utf-8")
import librosa, soundfile as sf
from faster_whisper import WhisperModel
from transformers import pipeline

ROOT = r"E:\MITAS"
DB = os.path.join(ROOT, "Database")
MODEL = os.path.join(ROOT, "models", "asr", "faster-whisper", "large-v3-turbo")
TMP = os.path.join(ROOT, "outputs", "model_test", "_mgate"); os.makedirs(TMP, exist_ok=True)

FILMS = {
    "DERT BENDE (arabesk, beklenen=tr)": "evoArcadmin_S_NEMA_F_LM4_1973-0174-1-0000-85-1-DERT_BENDE",
    "DİRİLİŞ (beklenen=tr)":             "web_client_dizi_2014-0053-0-0010-90-1-D_R_L__ERTU_RUL",
    "YALAZA (Türkçe, regresyon=tr)":     "web_client_dad_2017-0019-0-0001-90-1-YALAZA",
}
TIMES = [60, 130, 200, 300, 400, 480, 600, 720, 900, 1100]
SDUR, SR = 30, 16000


def is_music(ast_top):
    """AST top-k -> bu örnek MÜZİK mi? (top-1 müzik-tipi VE top-3'te konuşma YOK = müzik)."""
    labels = [d["label"].lower() for d in ast_top]
    speech_top3 = any(("speech" in l or "conversation" in l or "narration" in l) for l in labels[:3])
    top1 = labels[0]
    music_top1 = ("music" in top1) or ("singing" in top1)
    return music_top1 and not speech_top3


print("[yükleniyor] whisper-turbo + AST (ilk sefer AST ~350MB iner)...", flush=True)
wm = WhisperModel(MODEL, device="cuda", compute_type="float16", local_files_only=True)
ast = pipeline("audio-classification", model="MIT/ast-finetuned-audioset-10-10-0.4593", device=0, top_k=6)
print("    yüklendi", flush=True)

for title, clip in FILMS.items():
    wav = os.path.join(DB, clip, "audio", "audio16k.wav")
    if not os.path.exists(wav):
        print(f"\n##### {title}: SES YOK ({wav})", flush=True); continue
    y, _ = librosa.load(wav, sr=SR, mono=True, duration=1240)
    print(f"\n##### {title}  (yüklenen {len(y)/SR/60:.0f}dk) #####", flush=True)
    print(f"  {'t':>5}  {'karar':8} {'AST top1':24} {'AST top2':20} {'LID':4} prob", flush=True)
    ungated, gated, nsp = {}, {}, 0
    for t in TIMES:
        if (t + SDUR) * SR > len(y):
            continue
        seg = y[t * SR:(t + SDUR) * SR]
        tmp = os.path.join(TMP, "s.wav"); sf.write(tmp, seg, SR)
        atop = ast(tmp)
        mus = is_music(atop)
        _s, info = wm.transcribe(seg, language=None, beam_size=1, vad_filter=True)
        lang, prob = info.language, float(info.language_probability or 0)
        ungated[lang] = ungated.get(lang, 0) + prob
        if not mus:
            gated[lang] = gated.get(lang, 0) + prob; nsp += 1
        print(f"  {t:>5}  {'MÜZİK' if mus else 'konuşma':8} {atop[0]['label'][:24]:24} "
              f"{atop[1]['label'][:20]:20} {lang:4} {prob:.2f}", flush=True)
    ug = max(ungated, key=ungated.get) if ungated else None
    g = max(gated, key=gated.get) if gated else None
    flag = "OK" if g == "tr" else "!!"
    print(f"  --> GATE'SİZ: {ug}   |   GATE'Lİ: {g}  ({nsp} konuşma örneği)  [beklenen tr] {flag}", flush=True)
print("\nMGATE_DONE", flush=True)
