# MITAS Requirements Taslakları v1

## Amaç

Sprint 4.4 kapsamında her MITAS venv’i için requirements taslak dosyaları oluşturulmuştur.

Bu çalışma kurulum değildir.
Model indirme değildir.
Benchmark değildir.
Pipeline değildir.
Ana motor seçimi değildir.

## Oluşturulan Dosyalar

- `requirements/ocr.txt`
- `requirements/asr.txt`
- `requirements/face.txt`
- `requirements/visual.txt`
- `requirements/audio.txt`
- `requirements/tag.txt`

`requirements/stt.txt` legacy referans olarak kalır; ayrı ana runtime taslağı değildir.

## Ortak Kural

Her requirements dosyası taslaktır.
Bu sprintte `pip install` çalıştırılmayacaktır.
Benchmark ve smoke test sonuçlarından sonra paketler sadeleştirilecek, sürüm pinleri ve CUDA/CPU kararları netleştirilecektir.

## Paket Grupları

### OCR

- OneOCR placeholder
- PaddleOCR placeholder
- pytesseract placeholder
- opencv-python
- pillow
- numpy

### ASR

- faster-whisper
- WhisperX placeholder
- silero-vad
- torch placeholder
- torchaudio placeholder
- soundfile
- librosa
- numpy
- fastapi 0.136.1
- uvicorn 0.46.0
- websockets 16.0
- onnxruntime 1.23.2

### Face

- insightface
- onnxruntime-gpu placeholder
- opencv-python
- numpy
- pillow
- bytetrack placeholder

### Visual

- ultralytics / YOLO-World placeholder
- transformers
- torch placeholder
- opencv-python
- pillow
- numpy

### Audio

- librosa
- soundfile
- pydub
- numpy
- YAMNet placeholder
- tensorflow placeholder
- chromaprint/fpcalc external binary note

### Tag

- pydantic
- rapidfuzz
- regex
- zeyrek / Turkish morphology placeholder
- pyyaml

### Legacy STT

- `legacy_stt_venv`
- `deprecated_as_primary_runtime`
- `do_not_delete_yet`
- Canlı transkript artık `ASR > streaming_transcription` alt modudur.

## Son Karar

Requirements dosyaları model seçimi değildir.
Production ana motor belirlemez.
Kurulum yapılmadan, sonraki smoke/benchmark adımlarına hazırlık için taslak olarak tutulur.
