"""Tedial endpoint configuration and SSRF guards.

The Phase 1 design is user-session based: MITAS must not collect or store a
Tedial password. This module only describes allowed Tedial origins and confirmed
paths from Phase 0, plus helpers for constructing safe upstream URLs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from posixpath import normpath
from urllib.parse import quote, urlsplit, urlunsplit


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: str = "0") -> bool:
    return _env(name, default).lower() in {"1", "true", "yes", "on"}


def _clean_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"Tedial origin must be an https URL: {value!r}")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


@dataclass(frozen=True)
class TedialConfig:
    """Resolved Tedial origins and confirmed AJAX paths."""

    base_url: str = field(default_factory=lambda: _clean_origin(_env("TEDIAL_BASE_URL", "https://evo.int.trt.net.tr:8885")))
    mam_url: str = field(default_factory=lambda: _clean_origin(_env("TEDIAL_MAM_URL", "https://evo.int.trt.net.tr:8181")))
    media_url: str = field(default_factory=lambda: _clean_origin(_env("TEDIAL_MEDIA_URL", "https://evo.int.trt.net.tr")))
    verify_tls: bool = field(default_factory=lambda: _env_bool("TEDIAL_VERIFY_TLS", "0"))

    default_repository: str = field(default_factory=lambda: _env("TEDIAL_DEFAULT_REPOSITORY", "TRT1"))
    default_search_type: str = "TARSYS_SEQUENCES"
    default_presentation_template: str = "BS_CAN"
    default_search_scope: str = "DEFAULT"
    default_items_per_page: str = "100"

    load_default_search_path: str = "/iTClient/tarsys/search/loadDefaultSearch.html"
    search_path: str = "/iTClient/tarsys/search/ajax/doNewSearch.html"
    playback_token_path: str = "/iTClient/player/ajax/refreshPlaybackToken.html"
    manifest_path_template: str = "/MamService/PlaylistService/mpd/{repository_id}/{asset_id}/file.mpd"
    keyframe_path_prefix: str = "/MamService/KeyframeService/"
    media_path_prefix: str = "/cache_lowres/"

    @classmethod
    def from_env(cls) -> "TedialConfig":
        return cls()

    @property
    def allowed_netlocs(self) -> set[str]:
        return {urlsplit(self.base_url).netloc, urlsplit(self.mam_url).netloc, urlsplit(self.media_url).netloc}

    @property
    def media_netloc(self) -> str:
        return urlsplit(self.media_url).netloc

    def build_base_url(self, path: str) -> str:
        return _join_origin_path(self.base_url, path)

    def build_mam_url(self, path: str) -> str:
        return _join_origin_path(self.mam_url, path)

    def build_media_url(self, path: str) -> str:
        return _join_origin_path(self.media_url, path)

    def build_manifest_url(self, repository_id: str, asset_id: str) -> str:
        path = self.manifest_path_template.format(
            repository_id=quote(repository_id, safe=""),
            asset_id=quote(asset_id, safe=""),
        )
        return self.build_mam_url(path)

    def default_search_payload(self, search_field: str) -> dict[str, object]:
        return {
            "searchType": self.default_search_type,
            "selectedRepositories": [self.default_repository],
            "multiRepository": False,
            "searchField": search_field,
            "placeHolder": "Search...",
            "selectedPresentationTemplate": self.default_presentation_template,
            "tqlExpression": "",
            "selectedOrderField": None,
            "ascendingSort": False,
            "searchFilterLineList": [],
            "selectedItemsPerPage": self.default_items_per_page,
            "searchScope": self.default_search_scope,
        }

    def trt_id_search_payload(self, trt_id: str) -> dict[str, object]:
        payload = self.default_search_payload("")
        payload["selectedPresentationTemplate"] = "GENEL_GORUNUM"
        payload["searchFilterLineList"] = [
            {
                "filterType": "FIELD",
                "tqlName": "JT_ID_SECTION_TRT_ID",
                "filterValue": trt_id,
                "fromDateFilter": None,
                "toDateFilter": None,
                "filterValueRange": [],
                "repositoryOfCategory": None,
                "deepSearch": False,
                "thesauroLevel": None,
                "thesauroOperator": None,
                "thesauroName": None,
                "complexFilters": [],
                "literalSearch": False,
                "collection": {"key": None, "value": None},
                "extraInfo": None,
            }
        ]
        return payload

    def is_allowed_upstream_url(self, url: str) -> bool:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            return False
        if parsed.netloc not in self.allowed_netlocs:
            return False
        return _path_is_normal(parsed.path)

    def is_allowed_media_url(self, url: str) -> bool:
        parsed = urlsplit(url)
        if not self.is_allowed_upstream_url(url):
            return False
        if parsed.netloc != self.media_netloc:
            return False
        return parsed.path.startswith(self.media_path_prefix)

    def is_allowed_keyframe_url(self, url: str) -> bool:
        parsed = urlsplit(url)
        if not self.is_allowed_upstream_url(url):
            return False
        return parsed.path.startswith(self.keyframe_path_prefix)


def _join_origin_path(origin: str, path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if not _path_is_normal(path):
        raise ValueError(f"Unsafe Tedial path: {path!r}")
    parsed = urlsplit(origin)
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _path_is_normal(path: str) -> bool:
    if "\\" in path or "\x00" in path:
        return False
    normalized = normpath(path)
    return normalized == path and not normalized.startswith("../") and "/../" not in path
