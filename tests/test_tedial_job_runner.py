from __future__ import annotations

import asyncio
from pathlib import Path

from core.api.tedial import TedialConfig, TedialImportQueue, TedialProxyService, TedialSessionBroker
from core.api.tedial.job_runner import TedialJobRunner, TedialModuleResult
from core.api.tedial.media_resolver import TedialMediaDownload
from core.api.tedial.proxy import build_tedial_import_plan
from core.schemas.common import JobStatus


class FakeResponse:
    status_code = 200
    text = """
    <MPD xmlns="urn:mpeg:dash:schema:mpd:2011">
      <Period><BaseURL>https://evo.int.trt.net.tr/cache_lowres/repo-1/asset-1/file.mp4</BaseURL></Period>
    </MPD>
    """


def test_tedial_job_runner_resolves_media_and_updates_job(tmp_path, monkeypatch) -> None:
    broker = TedialSessionBroker()
    broker.attach_cookie_header("dev-local", "JSESSIONID=abc123")
    service = TedialProxyService(broker=broker, config=TedialConfig())
    queue = TedialImportQueue(storage_path=tmp_path / "jobs.json")
    enqueued = queue.enqueue(build_tedial_import_plan(repository_id="repo-1", asset_id="asset-1"))

    async def fake_send_plan(*args, **kwargs):
        return FakeResponse()

    async def fake_download_tedial_media(*, media_url, destination, config, httpx, cookie_header=None):
        media_path = Path(destination)
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"video")
        return TedialMediaDownload(media_url=media_url, path=media_path, content_type="video/mp4", bytes_written=5, cached=False)

    def fake_asr_runner(**kwargs):
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        transcript = output_dir / "transcript_review.md"
        transcript.write_text("hello", encoding="utf-8")
        return TedialModuleResult(status=JobStatus.done, output_artifacts=[str(transcript)], last_successful_step="asr")

    monkeypatch.setattr("core.api.tedial.job_runner._send_plan", fake_send_plan)
    monkeypatch.setattr("core.api.tedial.job_runner.download_tedial_media", fake_download_tedial_media)

    runner = TedialJobRunner(
        service=service,
        queue=queue,
        run_root=tmp_path / "runs",
        media_root=tmp_path / "media",
        asr_runner=fake_asr_runner,
        httpx_module=object(),
    )

    result = asyncio.run(runner.run_job(job_id=enqueued.job.job_id, user_id="dev-local", modules=["asr"]))

    assert result.job.status == "done"
    assert result.job.last_successful_step == "asr"
    assert any(path.endswith("manifest.raw.mpd") for path in result.job.output_artifacts)
    assert any(path.endswith("transcript_review.md") for path in result.job.output_artifacts)
    assert queue.get_job(enqueued.job.job_id).status == "done"
