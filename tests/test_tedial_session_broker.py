from __future__ import annotations

import pytest

from core.api.tedial import TedialConfig, TedialProxyService, TedialSessionBroker, TedialSessionStatus
from core.api.tedial.proxy import TedialProxyError, build_tedial_import_plan, rewrite_mpd_base_urls
from core.api.tedial.session import TedialCookieJar, TedialSessionNotConnected


def test_cookie_jar_masks_repr_and_builds_header() -> None:
    jar = TedialCookieJar()
    jar.update_from_set_cookie_headers(["JSESSIONID=abc123; Path=/; HttpOnly", "JREPLICA=node1; Path=/"])

    assert jar.names() == ["JREPLICA", "JSESSIONID"]
    assert "JSESSIONID=abc123" not in repr(jar)
    assert "JSESSIONID=abc123" in jar.as_header()


def test_session_broker_connect_forget_roundtrip() -> None:
    broker = TedialSessionBroker()

    started = broker.start("user-1", remember=True)
    assert started.status == TedialSessionStatus.connecting

    connected = broker.attach_cookie_header("user-1", "JSESSIONID=abc123; JREPLICA=node1")
    assert connected.status == TedialSessionStatus.connected
    assert broker.cookie_header_for("user-1") == "JREPLICA=node1; JSESSIONID=abc123"

    forgotten = broker.forget("user-1")
    assert forgotten.status == TedialSessionStatus.disconnected
    with pytest.raises(TedialSessionNotConnected):
        broker.cookie_header_for("user-1")


def test_cookie_header_if_any_is_available_during_connecting() -> None:
    broker = TedialSessionBroker()
    broker.start("user-1")
    broker.attach_set_cookie_headers("user-1", ["JSESSIONID=abc123; Path=/"])

    assert broker.cookie_header_if_any("user-1") == "JSESSIONID=abc123"


def test_session_broker_persists_remembered_cookie_jar(tmp_path) -> None:
    storage_dir = tmp_path / "sessions"
    broker = TedialSessionBroker(storage_dir=storage_dir)
    broker.start("user-1", remember=True)
    broker.attach_cookie_header("user-1", "JSESSIONID=abc123")

    reloaded = TedialSessionBroker(storage_dir=storage_dir)

    assert reloaded.get("user-1").status == TedialSessionStatus.connected
    assert reloaded.cookie_header_for("user-1") == "JSESSIONID=abc123"

    reloaded.mark_checked("user-1", connected=False, error="expired")
    assert not (storage_dir / "user-1.cookies").exists()


def test_config_allows_only_tedial_cache_lowres_media() -> None:
    cfg = TedialConfig()

    assert cfg.is_allowed_media_url("https://evo.int.trt.net.tr/cache_lowres/1/2/file.mp4")
    assert not cfg.is_allowed_media_url("https://evil.example/cache_lowres/1/2/file.mp4")
    assert not cfg.is_allowed_media_url("https://evo.int.trt.net.tr/not_cache/1.mp4")
    assert not cfg.is_allowed_media_url("http://evo.int.trt.net.tr/cache_lowres/1/2/file.mp4")


def test_config_allows_only_tedial_keyframes() -> None:
    cfg = TedialConfig()

    assert cfg.is_allowed_keyframe_url("https://evo.int.trt.net.tr:8181/MamService/KeyframeService/repo/asset/0")
    assert not cfg.is_allowed_keyframe_url("https://evil.example/MamService/KeyframeService/repo/asset/0")
    assert not cfg.is_allowed_keyframe_url("https://evo.int.trt.net.tr:8181/cache_lowres/repo/asset/0")


def test_proxy_service_plans_session_scoped_requests() -> None:
    broker = TedialSessionBroker()
    broker.attach_cookie_header("user-1", "JSESSIONID=abc123")
    service = TedialProxyService(broker=broker, config=TedialConfig())

    plan = service.plan_search("user-1", "tr-*")

    assert plan.method == "POST"
    assert plan.url.endswith("/iTClient/tarsys/search/ajax/doNewSearch.html")
    assert plan.headers["Cookie"] == "JSESSIONID=abc123"
    assert b'"searchField":"tr-*"' in plan.body


def test_proxy_service_rejects_unsafe_media_url() -> None:
    service = TedialProxyService()

    with pytest.raises(TedialProxyError):
        service.plan_media("https://evil.example/cache_lowres/1.mp4")


def test_proxy_service_plans_keyframe_with_session_cookie() -> None:
    broker = TedialSessionBroker()
    broker.attach_cookie_header("user-1", "JSESSIONID=abc123")
    service = TedialProxyService(broker=broker, config=TedialConfig())

    plan = service.plan_keyframe(
        "user-1",
        "https://evo.int.trt.net.tr:8181/MamService/KeyframeService/repo/asset/0",
    )

    assert plan.method == "GET"
    assert plan.headers["Cookie"] == "JSESSIONID=abc123"
    assert plan.headers["Accept"].startswith("image/")


def test_build_tedial_import_plan_maps_asset_to_mitas_job_draft() -> None:
    plan = build_tedial_import_plan(
        repository_id="repo-1",
        asset_id="asset-1",
        sequence_id="seq-1",
        title="Sample",
        asset_type="VIDEO",
    )

    assert plan["source"] == "tedial"
    assert plan["manifest_url"] == "/api/tedial/assets/asset-1/manifest?repository_id=repo-1"
    assert plan["mitas_job_draft"]["media_id"] == "tedial_asset-1"
    assert plan["mitas_job_draft"]["pipeline_name"] == "asr"
    assert plan["mitas_job_draft"]["input_artifacts"] == [plan["manifest_url"]]


def test_rewrite_mpd_base_urls_keeps_cache_behind_media_route() -> None:
    mpd = (
        "<MPD><BaseURL>"
        "https://evo.int.trt.net.tr/cache_lowres/445/925/video.mp4"
        "</BaseURL></MPD>"
    )

    rewritten = rewrite_mpd_base_urls(mpd, TedialConfig())

    assert "https://evo.int.trt.net.tr/cache_lowres" not in rewritten
    assert "/api/tedial/media?url=https%3A%2F%2Fevo.int.trt.net.tr%2Fcache_lowres" in rewritten
