# MITAS Kurulu Paket Envanteri v1

## Kapsam

Bu doküman, `E:\MITAS` altındaki mevcut venv ve sistem araçları için “ne kurulu / ne eksik” özetidir.

Bu doküman sadece envanterdir. Kurulum, model indirme, benchmark veya pipeline çalıştırma yapılmamıştır.

## Sistem Araçları

| Araç | Durum | Not |
|---|---|---|
| `ffmpeg` | Kurulu | PATH içinde görünüyor |
| `ffprobe` | Kurulu | PATH içinde görünüyor |
| `nvidia-smi` | Kurulu | NVIDIA GPU/driver görünür |
| `fpcalc` | Kurulu | PATH içinde görünüyor |
| `tesseract` | Yok | `pytesseract` Python paketi olsa da sistem binary yok |
| `chromaprint` | Yok | `fpcalc` mevcut |

## core venv

Yol:

`E:\MITAS\venvs\core`

### Kurulu

- `pydantic 2.13.4`
- `pytest 9.0.3`
- `PyYAML 6.0.3`

### Yok

- `fastapi`
- `uvicorn`
- AI/model paketleri

## stt venv (legacy)

Yol:

`E:\MITAS\venvs\stt`

### Kurulu

- `fastapi 0.136.1`
- `uvicorn 0.46.0`
- `websockets 16.0`
- `faster-whisper 1.2.1`
- `ctranslate2 4.7.1`
- `torch 2.11.0+cu126`
- `torchaudio 2.11.0+cu126`
- `onnxruntime 1.23.2`
- `soundfile 0.13.1`
- `numpy 2.2.6`

### Durum

- `legacy_stt_venv`
- `deprecated_as_primary_runtime`
- `do_not_delete_yet`
- Canlı transkript artık `ASR > streaming_transcription` altında çalışır.

### Yok

- `whisperx`
- `pyannote-audio`
- `onnxruntime-gpu`

## asr venv

Yol:

`E:\MITAS\venvs\asr`

### Kurulu

- `torch 2.11.0+cu126`
- `torchaudio 2.11.0+cu126`
- `faster-whisper 1.2.1`
- `ctranslate2 4.7.1`
- `silero-vad 6.2.1`
- `pyannote-audio 4.0.4`
- `DeepFilterNet 0.5.6`
- `DeepFilterLib 0.5.6`
- `onnxruntime 1.23.2`
- `fastapi 0.136.1`
- `uvicorn 0.46.0`
- `websockets 16.0`
- `librosa 0.11.0`
- `soundfile 0.13.1`
- `numpy 2.2.6`
- `pillow 12.2.0`

### Yok

- `whisperx`
- `onnxruntime-gpu`
- `transformers`

## ocr venv

Yol:

`E:\MITAS\venvs\ocr`

### Kurulu

- `oneocr 1.0.12`
- `paddleocr 3.5.0`
- `paddlepaddle 3.3.1`
- `easyocr 1.7.2`
- `pytesseract 0.3.13`
- `torch 2.11.0+cu126`
- `torchvision 0.26.0`
- `opencv-python 4.13.0.92`
- `opencv-python-headless 4.13.0.92`
- `opencv-contrib-python 4.10.0.84`
- `pillow 12.2.0`
- `numpy 2.2.6`

### Eksik / Not

- Sistem `tesseract.exe` yok.
- `pytesseract` Python paketi var ama Tesseract binary olmadan OCR backend olarak kullanılamaz.

## face venv

Yol:

`E:\MITAS\venvs\face`

### Kurulu

- `insightface 0.7.3`
- `onnxruntime-gpu 1.23.2`
- `supervision 0.28.0`
- `torch 2.11.0+cu126`
- `opencv-python 4.13.0.92`
- `opencv-python-headless 4.13.0.92`
- `pillow 12.2.0`
- `numpy 2.2.6`
- `pgvector 0.4.2`
- `hdbscan 0.8.42`

## visual venv

Yol:

`E:\MITAS\venvs\visual`

### Kurulu

- `ultralytics 8.4.48`
- `transformers 5.8.0`
- `scenedetect 0.7`
- `torch 2.11.0+cu126`
- `torchaudio 2.11.0+cu126`
- `torchvision 0.26.0`
- `opencv-python 4.13.0.92`
- `pillow 12.2.0`
- `numpy 2.2.6`

### Yok / Ayrı Görünmüyor

- `GroundingDINO`
- `RAM` ayrı paket adıyla görünmüyor
- `SigLIP 2` model olarak kurulu değil; sadece `transformers` var

## audio venv

Yol:

`E:\MITAS\venvs\audio`

### Kurulu

- `tensorflow 2.21.0`
- `tensorflow-hub 0.16.1`
- `librosa 0.11.0`
- `soundfile 0.13.1`
- `pydub 0.25.1`
- `numpy 2.2.6`

### Yok / Not

- `torch`
- `torchaudio`
- `fpcalc` pip paketi yok; sistem binary olarak var

## tag venv

Yol:

`E:\MITAS\venvs\tag`

### Kurulu

- `zeyrek 0.1.3`
- `nltk 3.9.4`
- `rapidfuzz 3.14.5`
- `regex 2026.4.4`
- `pydantic 2.13.4`
- `PyYAML 6.0.3`

## Genel Kısa Sonuç

- FastAPI / uvicorn / websockets: birleşik ASR runtime içinde kurulu.
- ASR tarafı birleşik ASR/STT ortamıdır: `torch CUDA`, `faster-whisper`, `silero-vad`, `pyannote`, `DeepFilterNet`, `fastapi`, `uvicorn`, `websockets` var.
- ASR tarafında `whisperx` yok.
- OCR tarafı dolu: `OneOCR`, `PaddleOCR`, `EasyOCR`, `pytesseract` var.
- OCR için sistem `tesseract` binary eksik.
- Face tarafı hazır görünüyor: `insightface`, `onnxruntime-gpu`, `supervision` var.
- Visual tarafında `ultralytics`, `transformers`, `PySceneDetect` var.
- Audio tarafında `tensorflow`, `tensorflow-hub`, `librosa`, `pydub` var.
- Sistem araçlarında `ffmpeg`, `ffprobe`, `fpcalc`, `nvidia-smi` var.
- Sistem araçlarında `tesseract` ve `chromaprint` yok.
