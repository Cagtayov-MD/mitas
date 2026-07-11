# MITAS Dosya Envanteri

Olusturulma: 2026-05-10 21:54:48
Kok klasor: `E:\MITAS`

## Ozet

| Klasor | Icerik sayisi | Not |
|---|---:|---|
| `.claude` | 1 |  |
| `.pytest_cache` | 7 |  |
| `benchmark_templates` | 5 |  |
| `cache` | 1302 | Buyuk klasor, ayrintili agaca dahil edilmedi |
| `core` | 33 |  |
| `docs` | 22 |  |
| `locks` | 20 |  |
| `models` | 2 |  |
| `outputs` | 34 |  |
| `requirements` | 7 |  |
| `schemas` | 6 |  |
| `scripts` | 21 |  |
| `tests` | 47 |  |
| `tmp` | 7 |  |
| `venvs` | 258114 | Buyuk klasor, ayrintili agaca dahil edilmedi |

## Kok Dizindeki Dosyalar

- `benchmark_registry.yaml`
- `MITAS_Master_Plan_Denetimli_v5.md`
- `MITAS_Uygulama_Plani_v1.md`
- `model_manifest.yaml`

## Klasor Agaci

```text
MITAS/
+-- .claude/
    +-- settings.local.json
+-- .pytest_cache/
    +-- v/
        +-- cache/
            +-- lastfailed
            +-- nodeids
    +-- .gitignore
    +-- CACHEDIR.TAG
    +-- README.md
+-- benchmark_templates/
    +-- asr_benchmark.yaml
    +-- audio_activity_benchmark.yaml
    +-- face_benchmark.yaml
    +-- ocr_kj_benchmark.yaml
    +-- visual_tag_benchmark.yaml
+-- cache/ (1302 oge; ozetlendi)
+-- core/
    +-- __pycache__/
        +-- __init__.cpython-310.pyc
    +-- jobs/
        +-- __pycache__/
            +-- __init__.cpython-310.pyc
            +-- errors.cpython-310.pyc
            +-- repository.cpython-310.pyc
            +-- step_runner.cpython-310.pyc
            +-- worker.cpython-310.pyc
        +-- __init__.py
        +-- errors.py
        +-- repository.py
        +-- step_runner.py
        +-- worker.py
    +-- schemas/
        +-- __pycache__/
            +-- __init__.cpython-310.pyc
            +-- candidate_relation.cpython-310.pyc
            +-- common.cpython-310.pyc
            +-- evidence.cpython-310.pyc
            +-- job_run.cpython-310.pyc
            +-- media.cpython-310.pyc
            +-- module_run.cpython-310.pyc
            +-- timeline.cpython-310.pyc
        +-- __init__.py
        +-- candidate_relation.py
        +-- common.py
        +-- evidence.py
        +-- job_run.py
        +-- media.py
        +-- module_run.py
        +-- timeline.py
    +-- __init__.py
+-- docs/
    +-- MITAS_3_5_Karar_Dokumanlari_Denetim_Raporu.md
    +-- MITAS_ASR_Model_Cache_NoInternet_Strategy_v1.md
    +-- MITAS_ASR_Torch_Env_Lock_v1.md
    +-- MITAS_Benchmark_Plani_v1.md
    +-- MITAS_Environment_Lock_Health_Check_v1.md
    +-- MITAS_Faster_Whisper_Env_Lock_NoDownload_Guard_v1.md
    +-- MITAS_Faster_Whisper_Import_Smoke_v1.md
    +-- MITAS_GPU_CUDA_Driver_Kesfi_v1.md
    +-- MITAS_Karar_Denetim_Checklist_v1.md
    +-- MITAS_Lightweight_Paket_Kurulum_Raporu_v1.md
    +-- MITAS_Model_Env_Inventory_v1.md
    +-- MITAS_Model_Manifest_ve_Smoke_Test_Plani_v1.md
    +-- MITAS_Model_Smoke_Test_Raporlama_v1.md
    +-- MITAS_P1_Blocker_ve_Mimari_Duzeltmeler_v1.md
    +-- MITAS_Pip_Dryrun_Raporlama_v1.md
    +-- MITAS_Profile_Routing_Kaba_Kararlar_v1.md
    +-- MITAS_Requirements_Denetim_ve_Kurulum_Sirasi_v1.md
    +-- MITAS_Requirements_Taslaklari_v1.md
    +-- MITAS_Torch_CUDA_ASR_Smoke_v1.md
    +-- SPRINT_1_CORE_SCHEMA_DONE.md
    +-- SPRINT_2_JOB_WORKER_DONE.md
    +-- SPRINT_3_BENCHMARK_PLAN_DONE.md
+-- locks/
    +-- asr.faster_whisper.freeze.txt
    +-- asr.faster_whisper.inspect.json
    +-- asr.freeze.txt
    +-- asr.inspect.json
    +-- asr.torch.freeze.txt
    +-- asr.torch.inspect.json
    +-- audio.freeze.txt
    +-- audio.inspect.json
    +-- core.freeze.txt
    +-- core.inspect.json
    +-- face.freeze.txt
    +-- face.inspect.json
    +-- ocr.freeze.txt
    +-- ocr.inspect.json
    +-- stt.freeze.txt
    +-- stt.inspect.json
    +-- tag.freeze.txt
    +-- tag.inspect.json
    +-- visual.freeze.txt
    +-- visual.inspect.json
+-- models/
    +-- asr/
        +-- faster-whisper/
+-- outputs/
    +-- asr_emergency_report.json
    +-- asr_emergency_transcript.json
    +-- asr_emergency_transcript.txt
    +-- asr_model_cache_strategy_report.json
    +-- asr_torch_env_lock_report.json
    +-- benchmark_plan_report.json
    +-- core_schema_report.json
    +-- env_lock_health_report.json
    +-- faster_whisper_env_lock_report.json
    +-- faster_whisper_smoke_report.json
    +-- gpu_cuda_inventory_report.json
    +-- job_worker_report.json
    +-- lightweight_install_report.json
    +-- master_file_discovery_report.json
    +-- master_v5_origin_note_report.json
    +-- master_v5_sprint_3_5_update_report.json
    +-- model_env_inventory_report.json
    +-- model_manifest_report.json
    +-- model_smoke_report.json
    +-- pip_dryrun_asr.json
    +-- pip_dryrun_audio.json
    +-- pip_dryrun_face.json
    +-- pip_dryrun_ocr.json
    +-- pip_dryrun_stt.json
    +-- pip_dryrun_summary_report.json
    +-- pip_dryrun_tag.json
    +-- pip_dryrun_visual.json
    +-- pyannote_smoke_report.json
    +-- pyannote_smoke.json
    +-- pyannote_smoke.rttm
    +-- requirements_draft_report.json
    +-- requirements_review_report.json
    +-- torch_cuda_asr_smoke_report.json
    +-- venv_skeleton_report.json
+-- requirements/
    +-- asr.txt
    +-- audio.txt
    +-- face.txt
    +-- ocr.txt
    +-- stt.txt
    +-- tag.txt
    +-- visual.txt
+-- schemas/
    +-- candidate_relation.schema.json
    +-- evidence.schema.json
    +-- job_run.schema.json
    +-- media_item.schema.json
    +-- module_run.schema.json
    +-- timeline_event.schema.json
+-- scripts/
    +-- __pycache__/
        +-- inspect_model_envs.cpython-310.pyc
        +-- run_model_smoke_tests.cpython-310.pyc
        +-- run_pip_dryrun_reports.cpython-310.pyc
        +-- validate_benchmark_yaml.cpython-310.pyc
        +-- validate_model_manifest.cpython-310.pyc
    +-- asr_emergency_transcribe.py
    +-- asr_pyannote_pipeline.py
    +-- export_json_schema.py
    +-- inspect_gpu_cuda.py
    +-- inspect_model_envs.py
    +-- install_faster_whisper_smoke.py
    +-- install_lightweight_packages.py
    +-- install_torch_cuda_asr.py
    +-- lock_and_check_envs.py
    +-- lock_asr_torch_env.py
    +-- lock_faster_whisper_env.py
    +-- run_model_smoke_tests.py
    +-- run_pip_dryrun_reports.py
    +-- validate_benchmark_yaml.py
    +-- validate_model_manifest.py
+-- tests/
    +-- __pycache__/
        +-- test_asr_model_cache_strategy_report.cpython-310-pytest-9.0.3.pyc
        +-- test_asr_torch_env_lock_report.cpython-310-pytest-9.0.3.pyc
        +-- test_benchmark_yaml_parse.cpython-310-pytest-9.0.3.pyc
        +-- test_dummy_worker.cpython-310-pytest-9.0.3.pyc
        +-- test_env_lock_health_report.cpython-310-pytest-9.0.3.pyc
        +-- test_faster_whisper_env_lock_report.cpython-310-pytest-9.0.3.pyc
        +-- test_faster_whisper_smoke_report.cpython-310-pytest-9.0.3.pyc
        +-- test_gpu_cuda_inventory_report.cpython-310-pytest-9.0.3.pyc
        +-- test_job_partial.cpython-310-pytest-9.0.3.pyc
        +-- test_job_repository.cpython-310-pytest-9.0.3.pyc
        +-- test_job_retry.cpython-310-pytest-9.0.3.pyc
        +-- test_lightweight_install_report.cpython-310-pytest-9.0.3.pyc
        +-- test_model_env_inventory_dry.cpython-310-pytest-9.0.3.pyc
        +-- test_model_manifest_parse.cpython-310-pytest-9.0.3.pyc
        +-- test_model_smoke_runner_dry.cpython-310-pytest-9.0.3.pyc
        +-- test_pip_dryrun_runner_dry.cpython-310-pytest-9.0.3.pyc
        +-- test_schema_candidate_relation.cpython-310-pytest-9.0.3.pyc
        +-- test_schema_evidence.cpython-310-pytest-9.0.3.pyc
        +-- test_schema_job_run.cpython-310-pytest-9.0.3.pyc
        +-- test_schema_media.cpython-310-pytest-9.0.3.pyc
        +-- test_schema_module_run.cpython-310-pytest-9.0.3.pyc
        +-- test_schema_timeline.cpython-310-pytest-9.0.3.pyc
        +-- test_torch_cuda_asr_smoke_report.cpython-310-pytest-9.0.3.pyc
    +-- test_asr_model_cache_strategy_report.py
    +-- test_asr_torch_env_lock_report.py
    +-- test_benchmark_yaml_parse.py
    +-- test_dummy_worker.py
    +-- test_env_lock_health_report.py
    +-- test_faster_whisper_env_lock_report.py
    +-- test_faster_whisper_smoke_report.py
    +-- test_gpu_cuda_inventory_report.py
    +-- test_job_partial.py
    +-- test_job_repository.py
    +-- test_job_retry.py
    +-- test_lightweight_install_report.py
    +-- test_model_env_inventory_dry.py
    +-- test_model_manifest_parse.py
    +-- test_model_smoke_runner_dry.py
    +-- test_pip_dryrun_runner_dry.py
    +-- test_schema_candidate_relation.py
    +-- test_schema_evidence.py
    +-- test_schema_job_run.py
    +-- test_schema_media.py
    +-- test_schema_module_run.py
    +-- test_schema_timeline.py
    +-- test_torch_cuda_asr_smoke_report.py
+-- tmp/
    +-- asr_torch_lock/
    +-- env_lock_health/
    +-- faster_whisper_install/
    +-- faster_whisper_lock/
    +-- pip_dryrun/
    +-- pip_install_lightweight/
    +-- torch_cuda_asr/
+-- venvs/ (258114 oge; ozetlendi)
+-- benchmark_registry.yaml
+-- MITAS_Master_Plan_Denetimli_v5.md
+-- MITAS_Uygulama_Plani_v1.md
+-- model_manifest.yaml
```

## Buyuk Klasor Notlari

- `venvs`: toplam 258114 oge; ilk seviyede 8 klasor, 0 dosya.
- `cache`: toplam 1302 oge; ilk seviyede 3 klasor, 0 dosya.
