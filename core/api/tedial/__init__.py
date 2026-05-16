"""Tedial archive integration primitives.

This package intentionally exposes only the dependency-light Phase 1 building
blocks. FastAPI routing, standalone UI, job execution, and OCR wiring are kept
out of the default import surface until they are reviewed against the current
MITAS API server.
"""

from core.api.tedial.config import TedialConfig
from core.api.tedial.import_queue import TedialEnqueueResult, TedialImportQueue
from core.api.tedial.job_runner import TedialJobRunResult, TedialJobRunner, TedialModuleResult
from core.api.tedial.media_resolver import (
    TedialMediaDownload,
    TedialMediaResolveError,
    TedialMpdRepresentation,
    extract_mpd_base_urls,
    extract_mpd_representations,
    keep_mpd_audio_track,
    keep_primary_mpd_audio,
    safe_artifact_id,
    select_mpd_audio_video_urls,
    select_mpd_media_url,
    tedial_media_cache_path,
    tedial_materialized_media_path,
    unwrap_media_proxy_url,
)
from core.api.tedial.parser import TedialSearchResult, parse_search_results
from core.api.tedial.proxy import (
    TedialProxyError,
    TedialProxyPlan,
    TedialProxyService,
    build_tedial_import_plan,
    rewrite_mpd_base_urls,
)
from core.api.tedial.router import create_tedial_router
from core.api.tedial.session import (
    TedialCookieJar,
    TedialSessionBroker,
    TedialSessionError,
    TedialSessionNotConnected,
    TedialSessionSnapshot,
    TedialSessionStatus,
)

__all__ = [
    "TedialConfig",
    "TedialCookieJar",
    "TedialEnqueueResult",
    "TedialImportQueue",
    "TedialJobRunResult",
    "TedialJobRunner",
    "TedialMediaDownload",
    "TedialMediaResolveError",
    "TedialMpdRepresentation",
    "TedialModuleResult",
    "TedialProxyError",
    "TedialProxyPlan",
    "TedialProxyService",
    "TedialSearchResult",
    "TedialSessionBroker",
    "TedialSessionError",
    "TedialSessionNotConnected",
    "TedialSessionSnapshot",
    "TedialSessionStatus",
    "build_tedial_import_plan",
    "create_tedial_router",
    "extract_mpd_base_urls",
    "extract_mpd_representations",
    "keep_mpd_audio_track",
    "keep_primary_mpd_audio",
    "parse_search_results",
    "rewrite_mpd_base_urls",
    "safe_artifact_id",
    "select_mpd_audio_video_urls",
    "select_mpd_media_url",
    "tedial_media_cache_path",
    "tedial_materialized_media_path",
    "unwrap_media_proxy_url",
]
