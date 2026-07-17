#!/usr/bin/env python3
"""Sürüm denetimi: her venv'deki anahtar paketler kurulu-vs-PyPI-son karşılaştırması."""
import json, subprocess, urllib.request, concurrent.futures, sys

VENVS_MITAS = ["core","tag","ocr","visual","stt","alignment","denoise","face","audio",
               "translate","tts","asr","ina","vlm","locateanything","nemo","internvl","minicpmv","vllm"]
ANAHTAR = {"torch","torchvision","torchaudio","transformers","tokenizers","paddleocr","paddlepaddle-gpu",
           "paddlex","faster-whisper","ctranslate2","whisperx","ultralytics","opencv-contrib-python",
           "insightface","onnxruntime","tensorflow","keras","librosa","nemo-toolkit","vllm","easyocr",
           "duckdb","fastapi","uvicorn","accelerate","timm","scenedetect","spacy","nltk","zeyrek",
           "DeepFilterNet","decord","inaSpeechSegmenter","speechbrain","numpy","pillow","av","gliner",
           "sentence-transformers","reportlab","pypdf"}
# Belgeli istisnalar: geride kalması BİLİNÇLİ (upstream kilidi)
ISTISNA = {
    ("denoise","torch"),("denoise","torchaudio"),          # DeepFilterNet 0.5.6 API
    ("ina","tensorflow"),("ina","keras"),("asr","tensorflow"),("asr","keras"),  # inaSpeechSegmenter
    ("vlm","decord"),("locateanything","decord"),          # decord terk edilmiş
    ("minicpmv","transformers"),("internvl","transformers"),("internvl","torch"),("internvl","torchvision"),  # model kilidi
    ("vllm","torch"),("vllm","torchvision"),("vllm","torchaudio"),  # vllm kendi pinler
    ("translate","transformers"),("translate","tokenizers"),  # ct2 çeviri hattı çifti
}

def kurulu(venv_yolu):
    try:
        out = subprocess.check_output([f"{venv_yolu}/bin/pip","list","--format","json"], text=True, timeout=60)
        return {p["name"]: p["version"] for p in json.loads(out)}
    except Exception:
        return {}

def pypi_son(pkg):
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=15) as r:
            return json.load(r)["info"]["version"]
    except Exception:
        return "?"

# 1) tüm venv'lerden kurulu sürümleri topla
tum = {}
for v in VENVS_MITAS:
    yol = f"/opt/mitas/venvs/{v}"
    tum[("M",v)] = kurulu(yol)
for v in ["core","ocr","asr","visual","face","nlp","audio"]:
    tum[("A",v)] = kurulu(f"/opt/atlas/venvs/{v}")

# 2) görülen anahtar paketlerin PyPI-son sürümlerini paralel çek
gorulen = set()
for paketler in tum.values():
    for ad in paketler:
        if ad in ANAHTAR or ad.lower() in {a.lower() for a in ANAHTAR}:
            gorulen.add(ad)
with concurrent.futures.ThreadPoolExecutor(16) as ex:
    son = dict(zip(gorulen, ex.map(pypi_son, gorulen)))

def norm(v): return v.split("+")[0]

# 3) rapor
geride, istisna_n, guncel_n = [], 0, 0
for (proje,venv), paketler in sorted(tum.items()):
    for ad, kv in sorted(paketler.items()):
        if ad not in gorulen: continue
        sv = son.get(ad,"?")
        if sv == "?" : continue
        if norm(kv) == sv:
            guncel_n += 1
        elif (venv,ad if ad!="tensorflow-cpu" else "tensorflow") in ISTISNA or (venv,ad.replace("-cpu","")) in ISTISNA:
            istisna_n += 1
        else:
            geride.append((proje,venv,ad,kv,sv))
print(f"GUNCEL={guncel_n}  BELGELI-ISTISNA={istisna_n}  GERIDE={len(geride)}")
print("--- GERİDE KALANLAR (istisna-dışı) ---")
for proje,venv,ad,kv,sv in geride:
    print(f"[{proje}] {venv:<15} {ad:<28} kurulu={kv:<18} pypi-son={sv}")
