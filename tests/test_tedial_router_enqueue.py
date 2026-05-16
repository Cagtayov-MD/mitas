from __future__ import annotations

import pytest

from core.api.tedial import TedialConfig, TedialImportQueue, TedialProxyService, TedialSessionBroker
from core.api.tedial.router import create_tedial_router


fastapi = pytest.importorskip("fastapi")
testclient = pytest.importorskip("fastapi.testclient")


def test_enqueue_endpoint_creates_job_from_connected_tedial_session(tmp_path) -> None:
    broker = TedialSessionBroker()
    broker.attach_cookie_header("dev-local", "JSESSIONID=abc123")
    service = TedialProxyService(broker=broker, config=TedialConfig())
    queue = TedialImportQueue(storage_path=tmp_path / "jobs.json")
    app = fastapi.FastAPI()
    app.include_router(create_tedial_router(service=service, import_queue=queue))
    client = testclient.TestClient(app)

    response = client.post(
        "/api/tedial/assets/asset-1/enqueue",
        json={
            "repository_id": "repo-1",
            "sequence_id": "seq-1",
            "title": "Sample",
            "asset_type": "VIDEO",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] is True
    assert payload["job"]["status"] == "pending"
    assert payload["job"]["pipeline_name"] == "asr"
    assert payload["job"]["input_artifacts"] == [
        "/api/tedial/assets/asset-1/manifest?repository_id=repo-1",
        "tedial://repo-1/asset-1",
    ]

    duplicate = client.post(
        "/api/tedial/assets/asset-1/enqueue",
        json={"repository_id": "repo-1"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["created"] is False

