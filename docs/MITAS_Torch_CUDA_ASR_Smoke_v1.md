# MITAS Torch CUDA ASR Smoke v1

## Amaç

Sprint 4.10 kapsamında yalnızca ASR venv içinde PyTorch CUDA kurulumu yapılır ve CUDA görünürlüğü küçük smoke test ile doğrulanır.

Bu görev benchmark değildir. Model seçimi değildir. Whisper veya faster-whisper kurulumu değildir.

## Hedef Venv

- `E:\MITAS\venvs\asr`

## Kurulum Komutu

```powershell
E:\MITAS\venvs\asr\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126
```

Pip cache ve geçici dizinler `E:\MITAS` altında tutulur. Kalıcı sistem environment değişikliği yapılmaz.

## Smoke Test

Smoke test yalnızca şu kontrolleri yapar:

- `import torch`
- `import torchaudio`
- `torch.__version__`
- `torchaudio.__version__`
- `torch.version.cuda`
- `torch.cuda.is_available()`
- `torch.cuda.device_count()`
- `torch.cuda.get_device_name(0)`
- `torch.cuda.mem_get_info()`
- Küçük tensor CUDA'ya taşınabiliyor mu

## Bilerek Yapılmayanlar

- `faster-whisper` kurulmadı.
- `whisperx` kurulmadı.
- `paddleocr` kurulmadı.
- `easyocr` kurulmadı.
- `insightface` kurulmadı.
- `onnxruntime-gpu` kurulmadı.
- `tensorflow` kurulmadı.
- `ultralytics` kurulmadı.
- `transformers` kurulmadı.
- Model indirilmedi.
- Benchmark çalıştırılmadı.
- Video/ses/görüntü analizi yapılmadı.
- UI yazılmadı.
- `selected_as_engine` değiştirilmedi.

## Rapor

- `outputs/torch_cuda_asr_smoke_report.json`
- `outputs/model_env_inventory_report.json`

## Son Karar

Bu sprint yalnızca ASR venv içinde PyTorch CUDA görünürlüğünü smoke test seviyesinde doğrular.

Production ana motor seçimi yapılmaz.
