# MITAS Faster-Whisper Import Smoke v1

## Amaç

Sprint 4.11 kapsamında ASR venv içinde `faster-whisper` ve bağımlılığı CTranslate2 kurulmuş, yalnız import/version smoke alınmıştır.

Bu görev benchmark değildir. Model seçimi değildir. Transcription değildir.

## Hedef Venv

- `E:\MITAS\venvs\asr`

## Kurulum

```powershell
E:\MITAS\venvs\asr\Scripts\python.exe -m pip install faster-whisper
```

Pip cache, geçici dizinler ve Hugging Face cache env değerleri `E:\MITAS` altına yönlendirilir. Kalıcı sistem environment değişikliği yapılmaz.

## Smoke Test

Yalnız şu kontroller yapılır:

- `import faster_whisper`
- `import ctranslate2`
- `faster-whisper` version
- `ctranslate2.__version__`
- `ctranslate2.get_cuda_device_count()`
- `ctranslate2.get_supported_compute_types("cuda")`
- `ctranslate2.get_supported_compute_types("cpu")`
- `pip check`
- `pip freeze`
- `pip inspect`

## Bilerek Yapılmayanlar

- `WhisperModel("large-v3")` veya başka model instantiate edilmedi.
- Hugging Face Hub'dan model indirilmedi.
- Ses/video dosyası işlenmedi.
- Benchmark çalıştırılmadı.
- WhisperX kurulmadı.
- pyannote kurulmadı.
- Pipeline yazılmadı.
- UI yazılmadı.
- `selected_as_engine` değiştirilmedi.

## Raporlar

- `outputs/faster_whisper_smoke_report.json`
- `outputs/model_env_inventory_report.json`
- `locks/asr.faster_whisper.freeze.txt`
- `locks/asr.faster_whisper.inspect.json`

## Son Karar

Bu sprint yalnız import/version smoke seviyesindedir.

ASR production motor seçimi yapılmaz ve model performansı ölçülmez.
