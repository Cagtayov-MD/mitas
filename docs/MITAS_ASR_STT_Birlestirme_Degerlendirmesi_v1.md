# MITAS ASR + STT Birlestirme Degerlendirmesi v1

## Kapsam

Bu dokuman `E:\MITAS\venvs\asr` ve `E:\MITAS\venvs\stt` icin ASR/STT birlestirme kararini kaydeder.

Kontrol tarihi: 2026-05-10

## Karar

`E:\MITAS\venvs\asr` birlesik ASR/STT calisma ortami kabul edilir.

STT artik ayri ana venv, profil veya modul degildir. Canli/anlik transcript akisi ASR modulunun su alt modudur:

```text
ASR > streaming_transcription
```

ASR alt modlari:

- `file_transcription`
- `streaming_transcription`
- `vad`
- `diarization`
- `alignment`

## ASR Venv Korunan Paketler

Asagidaki paketler ASR venv icinde korunur:

- `torch==2.11.0+cu126`
- `torchaudio==2.11.0+cu126`
- `faster-whisper==1.2.1`
- `ctranslate2==4.7.1`
- `silero-vad==6.2.1`
- `pyannote-audio==4.0.4`
- `librosa==0.11.0`
- `soundfile==0.13.1`

Servis/stream paketleri ASR venv icinde dogrulanmistir:

- `fastapi==0.136.1`
- `uvicorn==0.46.0`
- `websockets==16.0`
- `onnxruntime==1.23.2`

## Legacy STT Venv

`E:\MITAS\venvs\stt` silinmez. Durumu:

- `legacy_stt_venv`
- `deprecated_as_primary_runtime`
- `do_not_delete_yet`

Bu venv artik primary runtime degildir; yalnizca gecmis uyumluluk ve audit izi olarak korunur.

## Yapilmayanlar

- Torch downgrade yapilmadi.
- Torchaudio downgrade yapilmadi.
- CTranslate2 downgrade yapilmadi.
- faster-whisper degistirilmedi.
- pyannote-audio degistirilmedi.
- DeepFilterNet icin numpy/torch/torchaudio degistirilmedi.
- WhisperX kurulumu yapilmadi.
- large-v3 indirilmedi.
- Benchmark calistirilmadi.
- Production ana motor secimi yapilmadi.
- STT venv silinmedi.

## Sonuc

ASR ve STT paketleri ASR venv icinde birlestirildi. Bundan sonraki dokuman ve config dilinde STT ana profil yerine `ASR > streaming_transcription` kullanilir.
