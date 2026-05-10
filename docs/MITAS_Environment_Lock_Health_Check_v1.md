# MITAS Environment Lock + Health Check v1

## Amaç

Sprint 4.8 kapsamında Sprint 4.7 sonrasında oluşan hafif paket ortamları kilitlenmiş ve sağlık kontrolünden geçirilmiştir.

Bu görev benchmark değildir. Model seçimi değildir. Ağır model kurulumu değildir.

## Kontrol Edilen Venv'ler

- `venvs/ocr`
- `venvs/asr`
- `venvs/face`
- `venvs/visual`
- `venvs/audio`
- `venvs/tag`
- `venvs/core`

Legacy olarak izlenen ama primary runtime olmayan ortam:

- `venvs/stt` (`legacy_stt_venv`, `deprecated_as_primary_runtime`, `do_not_delete_yet`)

## Üretilen Lock Dosyaları

Her venv için `pip freeze` çıktısı alınmıştır:

- `locks/ocr.freeze.txt`
- `locks/asr.freeze.txt`
- `locks/face.freeze.txt`
- `locks/visual.freeze.txt`
- `locks/audio.freeze.txt`
- `locks/tag.freeze.txt`
- `locks/core.freeze.txt`
- `locks/stt.freeze.txt` (legacy)

Her venv için `pip inspect` JSON çıktısı alınmıştır:

- `locks/ocr.inspect.json`
- `locks/asr.inspect.json`
- `locks/face.inspect.json`
- `locks/visual.inspect.json`
- `locks/audio.inspect.json`
- `locks/tag.inspect.json`
- `locks/core.inspect.json`
- `locks/stt.inspect.json` (legacy)

## Sağlık Kontrolleri

Her venv için:

- `pip check` çalıştırılmıştır.
- Hafif paket import smoke testleri tekrar çalıştırılmıştır.
- Ağır paket import smoke testi yapılmamıştır.
- Ağır paketlerin kurulu olup olmadığı metadata üzerinden kontrol edilmiştir.

## Bilerek Yapılmayanlar

- `torch` kurulmadı.
- `torchaudio` kurulmadı.
- `tensorflow` kurulmadı.
- `onnxruntime-gpu` kurulmadı.
- `whisperx` kurulmadı.
- `faster-whisper` kurulmadı.
- `paddleocr` kurulmadı.
- `easyocr` kurulmadı.
- `insightface` kurulmadı.
- `ultralytics` kurulmadı.
- `transformers` kurulmadı.
- Model indirilmedi.
- Benchmark çalıştırılmadı.
- Video/ses/görüntü analizi yapılmadı.
- UI yazılmadı.
- `selected_as_engine` değiştirilmedi.

## Raporlar

- `outputs/env_lock_health_report.json`
- `outputs/model_env_inventory_report.json`

## Son Karar

Sprint 4.8 ortam lock ve health check çıktıları başarılıdır.

Beklenen durum:

- `broken_dependency_count`: 0
- `heavy_packages_installed`: false
- `model_download_executed`: false
- `benchmark_executed`: false
- `selected_as_engine_count`: 0
- `status`: passed
