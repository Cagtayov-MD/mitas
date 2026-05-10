# MITAS Lightweight Paket Kurulum Raporu v1

## Amaç

Sprint 4.7 kapsamında model venv'lerine yalnızca hafif altyapı paketleri kurulmuş ve ilgili import smoke testleri alınmıştır.

Bu görev benchmark değildir. Ana motor seçimi değildir. Ağır model kurulumu değildir.

## Kurulum Kapsamı

Kurulumlar yalnızca `E:\MITAS\venvs` altındaki model venv'lerine yapılmıştır.

- `ocr`: `numpy`, `pillow`, `opencv-python`
- `asr`: `numpy`, `soundfile`, `librosa`, `fastapi`, `uvicorn`, `websockets`, `onnxruntime`
- `audio`: `numpy`, `soundfile`, `librosa`, `pydub`
- `tag`: `pydantic`, `rapidfuzz`, `regex`, `pyyaml`
- `stt`: legacy, primary runtime değil
- `face`: `numpy`, `pillow`, `opencv-python`
- `visual`: `numpy`, `pillow`, `opencv-python`

## Bilerek Kurulmayan Ağır Paketler

- `torch`
- `torchaudio`
- `tensorflow`
- `onnxruntime-gpu`
- `whisperx`
- `faster-whisper`
- `paddleocr`
- `easyocr`
- `insightface`
- `ultralytics`
- `transformers`

## Smoke Test Sonucu

Beklenen import testleri ilgili venv'lerde başarılıdır:

- `ocr`: `numpy`, `PIL`, `cv2`
- `asr`: `numpy`, `soundfile`, `librosa`, `fastapi`, `uvicorn`, `websockets`, `onnxruntime`
- `audio`: `numpy`, `soundfile`, `librosa`, `pydub`
- `tag`: `pydantic`, `rapidfuzz`, `regex`, `yaml`
- `stt`: legacy, primary runtime değil
- `face`: `numpy`, `PIL`, `cv2`
- `visual`: `numpy`, `PIL`, `cv2`

## Rapor Dosyaları

- `outputs/lightweight_install_report.json`
- `outputs/model_env_inventory_report.json`

## Güvenlik Notları

- Pip cache `E:\MITAS\cache\pip` altında tutulmuştur.
- Geçici pip dosyaları `E:\MITAS\tmp\pip_install_lightweight` altında tutulmuştur.
- Kalıcı sistem environment değişikliği yapılmamıştır.
- Model indirilmemiştir.
- Benchmark çalıştırılmamıştır.
- `selected_as_engine` alanı değiştirilmemiştir.

## Sonuç

Sprint 4.7 lightweight paket kurulumu başarılıdır.

Durum:

- `install_executed`: true
- `heavy_packages_installed`: false
- `model_download_executed`: false
- `benchmark_executed`: false
- `selected_as_engine_count`: 0
- `status`: passed
