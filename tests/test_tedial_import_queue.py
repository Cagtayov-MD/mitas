from __future__ import annotations

from core.api.tedial.import_queue import TedialImportQueue
from core.api.tedial.proxy import build_tedial_import_plan
from core.jobs import JobRepository


def test_tedial_import_queue_creates_persistent_pending_job(tmp_path) -> None:
    store = tmp_path / "tedial_jobs.json"
    queue = TedialImportQueue(storage_path=store)
    plan = build_tedial_import_plan(repository_id="repo-1", asset_id="asset-1", title="Sample")

    result = queue.enqueue(plan)

    assert result.created is True
    assert result.job.status == "pending"
    assert result.job.pipeline_name == "asr"
    assert result.job.step_name == "tedial_lowres_import"
    assert result.job.input_artifacts == [
        "/api/tedial/assets/asset-1/manifest?repository_id=repo-1",
        "tedial://repo-1/asset-1",
    ]

    reloaded = JobRepository(store)
    assert reloaded.get(result.job.job_id).media_id == "tedial_asset-1"


def test_tedial_import_queue_is_idempotent_per_repository_asset(tmp_path) -> None:
    queue = TedialImportQueue(storage_path=tmp_path / "tedial_jobs.json")
    plan = build_tedial_import_plan(repository_id="repo-1", asset_id="asset-1", title="Sample")

    first = queue.enqueue(plan)
    second = queue.enqueue(plan)

    assert first.created is True
    assert second.created is False
    assert first.job.job_id == second.job.job_id
    assert len(queue.list_jobs()) == 1


def test_tedial_import_queue_can_use_existing_repository() -> None:
    repository = JobRepository()
    queue = TedialImportQueue(repository=repository)
    plan = build_tedial_import_plan(repository_id="repo-2", asset_id="asset-2")

    result = queue.enqueue(plan)

    assert repository.get(result.job.job_id) == result.job

