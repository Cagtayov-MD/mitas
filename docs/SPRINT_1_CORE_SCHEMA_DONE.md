# Sprint 1 — Core Schema

## Oluşturulan Ana Dosyalar

- `core/schemas/common.py`
- `core/schemas/media.py`
- `core/schemas/timeline.py`
- `core/schemas/evidence.py`
- `core/schemas/candidate_relation.py`
- `core/schemas/job_run.py`
- `core/schemas/module_run.py`
- `scripts/export_json_schema.py`
- `schemas/media_item.schema.json`
- `schemas/timeline_event.schema.json`
- `schemas/evidence.schema.json`
- `schemas/candidate_relation.schema.json`
- `schemas/job_run.schema.json`
- `schemas/module_run.schema.json`
- `tests/test_schema_media.py`
- `tests/test_schema_timeline.py`
- `tests/test_schema_evidence.py`
- `tests/test_schema_candidate_relation.py`
- `tests/test_schema_job_run.py`
- `tests/test_schema_module_run.py`
- `outputs/core_schema_report.json`

## Test

- Test komutu: `E:\MITAS\venvs\core\Scripts\python.exe -m pytest E:\MITAS\tests -v`
- Test sonucu: `22 passed`

## JSON Schema Export

- JSON Schema export sonucu: `passed`

## Ortam

- Kullanılan Python ortamı: `E:\MITAS\venvs\core`
- pydantic version: `2.13.4`
- pytest version: `9.0.3`

## Son Karar

- Sprint 1 DONE

## Sonraki Sprint

- Sprint 2 — Job / Background Worker
