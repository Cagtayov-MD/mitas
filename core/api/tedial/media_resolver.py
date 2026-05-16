"""Resolve Tedial DASH manifests into local MITAS media artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
import xml.etree.ElementTree as ET

from core.api.tedial.config import TedialConfig


@dataclass(frozen=True)
class TedialMediaDownload:
    media_url: str
    path: Path
    content_type: str | None
    bytes_written: int
    cached: bool


@dataclass(frozen=True)
class TedialMpdRepresentation:
    representation_id: str | None
    mime_type: str | None
    media_url: str


class TedialMediaResolveError(RuntimeError):
    """Raised when a Tedial manifest cannot be converted to a playable asset."""


def extract_mpd_base_urls(mpd_xml: str) -> list[str]:
    """Return BaseURL values from an MPD document.

    Tedial manifests are XML, but this helper keeps a tiny regex fallback so
    tests and malformed fragments still exercise the same media-selection path.
    """
    values: list[str] = []
    try:
        root = ET.fromstring(mpd_xml)
    except ET.ParseError:
        root = None
    if root is not None:
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] == "BaseURL" and element.text:
                value = element.text.strip()
                if value:
                    values.append(value)

    for match in re.finditer(r"<BaseURL>\s*(.*?)\s*</BaseURL>", mpd_xml, flags=re.IGNORECASE | re.DOTALL):
        value = match.group(1).strip()
        if value and value not in values:
            values.append(value)
    return values


def extract_mpd_representations(mpd_xml: str) -> list[TedialMpdRepresentation]:
    values: list[TedialMpdRepresentation] = []
    try:
        root = ET.fromstring(mpd_xml)
    except ET.ParseError:
        root = None
    if root is None:
        return [
            TedialMpdRepresentation(representation_id=None, mime_type=None, media_url=value)
            for value in extract_mpd_base_urls(mpd_xml)
        ]
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "Representation":
            continue
        base_url = None
        for child in element:
            if child.tag.rsplit("}", 1)[-1] == "BaseURL" and child.text:
                base_url = child.text.strip()
                break
        if not base_url:
            continue
        values.append(
            TedialMpdRepresentation(
                representation_id=element.attrib.get("id"),
                mime_type=element.attrib.get("mimeType"),
                media_url=base_url,
            )
        )
    return values


def select_mpd_media_url(mpd_xml: str, config: TedialConfig | None = None) -> str:
    cfg = config or TedialConfig.from_env()
    for value in extract_mpd_base_urls(mpd_xml):
        candidate = unwrap_media_proxy_url(value)
        if cfg.is_allowed_media_url(candidate):
            return candidate
    raise TedialMediaResolveError("Tedial manifest does not contain an allowed cache_lowres BaseURL")


def select_mpd_audio_video_urls(
    mpd_xml: str,
    config: TedialConfig | None = None,
    *,
    audio_track_index: int = 0,
) -> tuple[str, str | None]:
    cfg = config or TedialConfig.from_env()
    video_url = None
    audio_urls: list[str] = []
    for representation in extract_mpd_representations(mpd_xml):
        candidate = unwrap_media_proxy_url(representation.media_url)
        if not cfg.is_allowed_media_url(candidate):
            continue
        mime_type = (representation.mime_type or "").lower()
        rep_id = (representation.representation_id or "").lower()
        if video_url is None and ("video" in mime_type or rep_id.startswith("video")):
            video_url = candidate
        if "audio" in mime_type or rep_id.startswith("audio"):
            audio_urls.append(candidate)
    if video_url is None:
        video_url = select_mpd_media_url(mpd_xml, cfg)
    audio_url = None
    if audio_urls:
        safe_index = max(0, audio_track_index)
        audio_url = audio_urls[safe_index] if safe_index < len(audio_urls) else audio_urls[0]
    return video_url, audio_url


def keep_mpd_audio_track(mpd_xml: str, audio_track_index: int = 0) -> str:
    """Return MPD XML with only one audio AdaptationSet left.

    Tedial can expose multiple audio tracks in a single manifest. Browser DASH
    players may pick a later low-bandwidth/silent track unless the manifest is
    narrowed to the operator's selected channel.
    """
    try:
        root = ET.fromstring(mpd_xml)
    except ET.ParseError:
        return mpd_xml

    audio_sets: list[tuple[Any, Any]] = []
    for parent in root.iter():
        children = list(parent)
        for child in children:
            if child.tag.rsplit("}", 1)[-1] != "AdaptationSet":
                continue
            if _adaptation_set_audio_bandwidth(child) is not None:
                audio_sets.append((parent, child))

    if len(audio_sets) <= 1:
        return mpd_xml

    safe_index = max(0, audio_track_index)
    keep_parent, keep_child = audio_sets[safe_index] if safe_index < len(audio_sets) else audio_sets[0]
    for parent, child in audio_sets:
        if parent is keep_parent and child is keep_child:
            continue
        parent.remove(child)
    return ET.tostring(root, encoding="unicode")


def keep_primary_mpd_audio(mpd_xml: str) -> str:
    try:
        root = ET.fromstring(mpd_xml)
    except ET.ParseError:
        return mpd_xml

    audio_sets: list[tuple[Any, Any, int]] = []
    for parent in root.iter():
        children = list(parent)
        for child in children:
            if child.tag.rsplit("}", 1)[-1] != "AdaptationSet":
                continue
            bandwidth = _adaptation_set_audio_bandwidth(child)
            if bandwidth is not None:
                audio_sets.append((parent, child, bandwidth))

    if len(audio_sets) <= 1:
        return mpd_xml

    keep_parent, keep_child, _ = max(audio_sets, key=lambda item: item[2])
    for parent, child, _ in audio_sets:
        if parent is keep_parent and child is keep_child:
            continue
        parent.remove(child)
    return ET.tostring(root, encoding="unicode")


def _adaptation_set_audio_bandwidth(adaptation_set: Any) -> int | None:
    bandwidths: list[int] = []
    for element in adaptation_set.iter():
        if element.tag.rsplit("}", 1)[-1] != "Representation":
            continue
        mime_type = (element.attrib.get("mimeType") or "").lower()
        rep_id = (element.attrib.get("id") or "").lower()
        if "audio" not in mime_type and not rep_id.startswith("audio"):
            continue
        try:
            bandwidths.append(int(element.attrib.get("bandwidth") or "0"))
        except ValueError:
            bandwidths.append(0)
    return max(bandwidths) if bandwidths else None


def unwrap_media_proxy_url(value: str) -> str:
    """Convert a local MITAS media proxy URL back to its upstream Tedial URL."""
    parsed = urlsplit(value)
    if parsed.path == "/api/tedial/media":
        url_values = parse_qs(parsed.query).get("url") or []
        if url_values:
            return unquote(url_values[0])
    if value.startswith("/api/tedial/media?"):
        url_values = parse_qs(urlsplit(value).query).get("url") or []
        if url_values:
            return unquote(url_values[0])
    return value


def tedial_media_cache_path(output_dir: str | Path, repository_id: str, asset_id: str, media_url: str) -> Path:
    suffix = Path(urlsplit(media_url).path).suffix or ".mp4"
    return Path(output_dir) / f"{safe_artifact_id(repository_id)}_{safe_artifact_id(asset_id)}{suffix}"


def tedial_materialized_media_path(output_dir: str | Path, repository_id: str, asset_id: str) -> Path:
    return Path(output_dir) / f"{safe_artifact_id(repository_id)}_{safe_artifact_id(asset_id)}_mitas.mp4"


async def download_tedial_media(
    *,
    media_url: str,
    destination: str | Path,
    config: TedialConfig,
    httpx: Any,
    cookie_header: str | None = None,
) -> TedialMediaDownload:
    path = Path(destination)
    if path.exists() and path.stat().st_size > 0:
        return TedialMediaDownload(
            media_url=media_url,
            path=path,
            content_type=None,
            bytes_written=path.stat().st_size,
            cached=True,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Accept": "video/*,application/octet-stream,*/*;q=0.8"}
    if cookie_header:
        headers["Cookie"] = cookie_header
    temp_path = path.with_suffix(path.suffix + ".part")
    bytes_written = 0
    content_type = None

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, read=1800.0),
        verify=config.verify_tls,
        trust_env=False,
        follow_redirects=True,
    ) as client:
        async with client.stream("GET", media_url, headers=headers) as response:
            if response.status_code not in (200, 206):
                raise TedialMediaResolveError(f"Tedial media download failed ({response.status_code})")
            content_type = response.headers.get("content-type")
            with temp_path.open("wb") as handle:
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    handle.write(chunk)
                    bytes_written += len(chunk)

    temp_path.replace(path)
    return TedialMediaDownload(
        media_url=media_url,
        path=path,
        content_type=content_type,
        bytes_written=bytes_written,
        cached=False,
    )


def mux_tedial_audio_video(
    *,
    video_path: str | Path,
    audio_path: str | Path | None,
    output_path: str | Path,
    ffmpeg_executable: str,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size > 0:
        return output
    if audio_path is None:
        shutil.copy2(video_path, output)
        return output
    temp_output = output.with_suffix(output.suffix + ".part.mp4")
    command = [
        ffmpeg_executable,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(temp_output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise TedialMediaResolveError((completed.stderr or completed.stdout or "Tedial media mux failed").strip())
    temp_output.replace(output)
    return output


def safe_artifact_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("._-") or "artifact"
