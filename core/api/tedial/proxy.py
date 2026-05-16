"""Pure helpers for the future Tedial BFF proxy.

This file intentionally avoids importing FastAPI/httpx. The Phase 1 POC can
wire these helpers into any API server while keeping URL validation testable and
dependency-light.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlencode, urlsplit

from core.api.tedial.config import TedialConfig
from core.api.tedial.session import TedialSessionBroker, TedialSessionSnapshot


class TedialProxyError(ValueError):
    """Raised when a Tedial proxy request is unsafe or malformed."""


@dataclass(frozen=True)
class TedialProxyPlan:
    """Resolved upstream target plus headers for an API layer to execute."""

    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None = None


class TedialProxyService:
    """Small service facade shared by future FastAPI/UI adapters."""

    def __init__(self, broker: TedialSessionBroker | None = None, config: TedialConfig | None = None) -> None:
        self.broker = broker or TedialSessionBroker()
        self.config = config or TedialConfig.from_env()

    def session_status(self, user_id: str) -> TedialSessionSnapshot:
        return self.broker.get(user_id)

    def start_session(self, user_id: str, remember: bool = False) -> TedialSessionSnapshot:
        return self.broker.start(user_id, remember=remember)

    def forget_session(self, user_id: str) -> TedialSessionSnapshot:
        return self.broker.forget(user_id)

    def plan_search(self, user_id: str, search_field: str, *, trt_id_lookup: bool = False) -> TedialProxyPlan:
        cookie_header = self.broker.cookie_header_for(user_id)
        url = self.config.build_base_url(self.config.search_path)
        payload = self.config.trt_id_search_payload(search_field) if trt_id_lookup else self.config.default_search_payload(search_field)
        return TedialProxyPlan(
            method="POST",
            url=url,
            headers={
                "Cookie": cookie_header,
                "Content-Type": "application/json",
                "Accept": "text/html, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            },
            body=_json_bytes(payload),
        )

    def plan_playback_token_refresh(self, user_id: str, token: str) -> TedialProxyPlan:
        cookie_header = self.broker.cookie_header_for(user_id)
        url = self.config.build_base_url(self.config.playback_token_path)
        return TedialProxyPlan(
            method="POST",
            url=url,
            headers={
                "Cookie": cookie_header,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            },
            body=f"token={quote(token, safe='')}".encode("ascii"),
        )

    def plan_manifest(self, user_id: str, repository_id: str, asset_id: str) -> TedialProxyPlan:
        cookie_header = self.broker.cookie_header_for(user_id)
        return TedialProxyPlan(
            method="GET",
            url=self.config.build_manifest_url(repository_id=repository_id, asset_id=asset_id),
            headers={"Cookie": cookie_header, "Accept": "application/dash+xml, */*"},
        )

    def plan_media(self, media_url: str, range_header: str | None = None, cookie_header: str | None = None) -> TedialProxyPlan:
        if not self.config.is_allowed_media_url(media_url):
            raise TedialProxyError("Media URL is not an allowed Tedial cache_lowres URL")
        headers = {}
        if range_header:
            headers["Range"] = range_header
        if cookie_header:
            headers["Cookie"] = cookie_header
        return TedialProxyPlan(method="GET", url=media_url, headers=headers)

    def plan_keyframe(self, user_id: str, keyframe_url: str) -> TedialProxyPlan:
        if not self.config.is_allowed_keyframe_url(keyframe_url):
            raise TedialProxyError("Keyframe URL is not an allowed Tedial URL")
        cookie_header = self.broker.cookie_header_for(user_id)
        return TedialProxyPlan(
            method="GET",
            url=keyframe_url,
            headers={"Cookie": cookie_header, "Accept": "image/*,*/*;q=0.8"},
        )

    def build_import_plan(
        self,
        user_id: str,
        *,
        repository_id: str,
        asset_id: str,
        sequence_id: str | None = None,
        title: str | None = None,
        asset_type: str | None = None,
    ) -> dict[str, object]:
        self.broker.cookie_header_for(user_id)
        return build_tedial_import_plan(
            repository_id=repository_id,
            asset_id=asset_id,
            sequence_id=sequence_id,
            title=title,
            asset_type=asset_type,
        )


def rewrite_mpd_base_urls(mpd_xml: str, config: TedialConfig | None = None, media_route_prefix: str = "/api/tedial/media?url=") -> str:
    """Rewrite cache_lowres BaseURLs to a MITAS media proxy URL.

    The DASH player may request byte ranges from the rewritten URL. The upstream
    URL is kept as a URL-encoded query value so the media route can validate it
    before fetching.
    """
    cfg = config or TedialConfig.from_env()
    origin = cfg.media_url + cfg.media_path_prefix
    output = mpd_xml
    start = 0
    while True:
        open_tag = output.find("<BaseURL>", start)
        if open_tag < 0:
            break
        value_start = open_tag + len("<BaseURL>")
        close_tag = output.find("</BaseURL>", value_start)
        if close_tag < 0:
            break
        value = output[value_start:close_tag]
        if value.startswith(origin) and cfg.is_allowed_media_url(value):
            replacement = media_route_prefix + quote(value, safe="")
            output = output[:value_start] + replacement + output[close_tag:]
            start = value_start + len(replacement)
        else:
            start = close_tag + len("</BaseURL>")
    return output


def build_tedial_import_plan(
    *,
    repository_id: str,
    asset_id: str,
    sequence_id: str | None = None,
    title: str | None = None,
    asset_type: str | None = None,
) -> dict[str, object]:
    manifest_url = "/api/tedial/assets/" + quote(asset_id, safe="") + "/manifest?" + urlencode({"repository_id": repository_id})
    media_id = "tedial_" + asset_id
    return {
        "source": "tedial",
        "title": title,
        "repository_id": repository_id,
        "asset_id": asset_id,
        "sequence_id": sequence_id,
        "asset_type": asset_type,
        "manifest_url": manifest_url,
        "mitas_job_draft": {
            "media_id": media_id,
            "pipeline_name": "asr",
            "step_name": "tedial_lowres_import",
            "status": "pending",
            "input_artifacts": [manifest_url],
            "output_artifacts": [],
        },
    }


def _json_bytes(payload: dict[str, object]) -> bytes:
    import json

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
