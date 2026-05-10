# MITAS ASR/STT Venv Paket Listesi v2

## Kapsam

Bu dokuman ASR/STT birlestirmesinden sonraki kritik Python paket durumunu listeler.

Birlesik primary runtime:

```text
E:\MITAS\venvs\asr
```

Legacy runtime:

```text
E:\MITAS\venvs\stt
```

## Kisa Ozet

| Venv | Durum | Not |
|---|---|---|
| `asr` | primary | Birlesik ASR/STT runtime |
| `stt` | legacy | `legacy_stt_venv`, `deprecated_as_primary_runtime`, `do_not_delete_yet` |

## ASR Kritik Paketler

| Paket | Versiyon |
|---|---:|
| torch | 2.11.0+cu126 |
| torchaudio | 2.11.0+cu126 |
| faster-whisper | 1.2.1 |
| ctranslate2 | 4.7.1 |
| silero-vad | 6.2.1 |
| pyannote-audio | 4.0.4 |
| librosa | 0.11.0 |
| soundfile | 0.13.1 |
| fastapi | 0.136.1 |
| uvicorn | 0.46.0 |
| websockets | 16.0 |
| onnxruntime | 1.23.2 |
| numpy | 2.2.6 |

## ASR Alt Modlari

- `file_transcription`
- `streaming_transcription`
- `vad`
- `diarization`
- `alignment`

## Legacy STT Venv

`E:\MITAS\venvs\stt` silinmez ve primary runtime sayilmaz.

Durum notlari:

- `legacy_stt_venv`
- `deprecated_as_primary_runtime`
- `do_not_delete_yet`

## Dikkat Notlari

- Bu liste model dosyalarinin indirildigi veya benchmark yapildigi anlamina gelmez.
- WhisperX bu birlestirme isinde kurulmaz.
- Production ana motor secimi yapilmaz.
