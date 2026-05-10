# MITAS Model Environment Inventory v1

## Amaç

Sprint 4.2 kapsamında mevcut venv, paket, CUDA/Torch ve binary araç durumunu model indirmeden, model kurmadan ve benchmark yapmadan çıkarmak.

Bu çalışma model seçimi değildir.
Production ana motor seçimi değildir.
Video analizi veya pipeline çalıştırma değildir.

## Kapsam

Kontrol edilen venv adayları:

- `E:\MITAS\venvs\core`
- `E:\MITAS\venvs\ocr`
- `E:\MITAS\venvs\asr`
- `E:\MITAS\venvs\face`
- `E:\MITAS\venvs\visual`
- `E:\MITAS\venvs\audio`
- `E:\MITAS\venvs\tag`
- `E:\MITAS\venvs\stt` (legacy: `legacy_stt_venv`, `deprecated_as_primary_runtime`, `do_not_delete_yet`)

Birleşik ASR/STT primary runtime:

- `E:\MITAS\venvs\asr`
- ASR alt modları: `file_transcription`, `streaming_transcription`, `vad`, `diarization`, `alignment`

Kontrol edilen binary araçlar:

- `fpcalc`
- `chromaprint`
- `tesseract`

## Envanter Scripti

Script:

```text
E:\MITAS\scripts\inspect_model_envs.py
```

Script şunları yapar:

- venv klasörü var mı kontrol eder
- `python.exe` var mı kontrol eder
- `python --version` çıktısını alır
- `importlib.metadata` ile paket özetini çıkarır
- Torch kuruluysa Torch/CUDA özetini alır
- Torch kurulu değilse hata fırlatmadan `missing` yazar
- binary araçları PATH üzerinde arar
- `model_manifest.yaml` adaylarını okur
- `TBD` smoke komutlarını ve real smoke’a hazır görünen adayları ayırır
- hiçbir ağır model yüklemez
- hiçbir video, ses veya görüntü işlemez
- hata durumunu ilgili venv/adaya izole eder

## Rapor

Rapor dosyası:

```text
E:\MITAS\outputs\model_env_inventory_report.json
```

Rapor alanları:

- `checked_venvs`
- `active_venvs`
- `legacy_venvs`
- `venv_status`
- `asr_submodules`
- `existing_venvs`
- `missing_venvs`
- `python_versions`
- `package_presence`
- `torch_status`
- `cuda_status`
- `binary_tools`
- `manifest_candidates_seen`
- `manifest_candidates_with_tbd_smoke_command`
- `manifest_candidates_ready_for_real_smoke`
- `status`

## Manifest Güvenlik Kuralı

Bu sprintte manifest için yalnızca şu alanlar gerekirse güncellenebilir:

- `install_state`
- `smoke_test_command`
- `notes`

Şu alanlara dokunulmaz:

- `selected_as_engine`
- `benchmark_required`
- `priority`
- `candidate_name`
- `module_area`

`selected_as_engine` tüm adaylarda `false` kalmalıdır.

## Son Karar

Sprint 4.2 yalnızca ortam envanteri ve smoke komut hazırlığıdır.
Model kurulumuna, model indirmeye, benchmarka veya pipeline çalıştırmaya geçmez.
