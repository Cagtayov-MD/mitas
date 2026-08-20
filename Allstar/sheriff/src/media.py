from __future__ import annotations

import json
import os
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any, Callable

from .config import SheriffConfig
from .runner import run_capture
from .util import atomic_write_json, now_iso, sha256_file, sha256_json


class MediaError(RuntimeError):
    pass


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise MediaError(f"gecersiz PNG: {path}")
    return struct.unpack(">II", header[16:24])


def verify_frame_pool(directory: Path, *, expected_section: str | None = None,
                      require_contiguous_sequence: bool = True) -> str:
    """Validate a tower frame input and return its stable content hash."""
    manifest = directory / "frames.jsonl"
    try:
        rows = [json.loads(line) for line in manifest.read_text(
            encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise MediaError(f"frame manifest okunamadi: {manifest}: {exc}") from exc
    paths = sorted(directory.glob("frame_*.png"))
    all_png_names = sorted(path.name for path in directory.glob("*.png"))
    if not rows or len(rows) != len(paths):
        raise MediaError(f"frame manifest/dosya sayisi uyusmuyor: {directory}")
    names = [path.name for path in paths]
    if all_png_names != names:
        raise MediaError(f"frame havuzunda manifest disi PNG var: {directory}")
    if [row.get("filename") for row in rows if isinstance(row, dict)] != names:
        raise MediaError(f"frame manifest dosya sirasi uyusmuyor: {directory}")
    previous_source = -1.0
    previous_section = -1.0
    previous_sequence = 0
    for index, (row, path) in enumerate(zip(rows, paths), start=1):
        sequence = row.get("sequence") if isinstance(row, dict) else None
        if (not isinstance(sequence, int) or isinstance(sequence, bool)
                or sequence <= previous_sequence
                or (require_contiguous_sequence and sequence != index)
                or path.name != f"frame_{sequence:06d}.png"):
            raise MediaError(f"frame sequence gecersiz: {path}")
        if (row.get("schema_version") != "mitas.frame/v1"
                or (expected_section is not None
                    and row.get("section") != expected_section)):
            raise MediaError(f"frame schema/section gecersiz: {path}")
        source_time = row.get("source_time_s")
        section_time = row.get("section_time_s")
        if (not isinstance(source_time, (int, float)) or isinstance(source_time, bool)
                or not isinstance(section_time, (int, float))
                or isinstance(section_time, bool)
                or float(source_time) < 0
                or float(section_time) < 0
                or float(source_time) < previous_source
                or float(section_time) < previous_section):
            raise MediaError(f"frame timecode gecersiz/azalan: {path}")
        width, height = png_size(path)
        if row.get("width") != width or row.get("height") != height:
            raise MediaError(f"frame boyutu manifestle uyusmuyor: {path}")
        if sha256_file(path) != row.get("sha256"):
            raise MediaError(f"frame hash uyusmuyor: {path}")
        previous_source, previous_section = float(source_time), float(section_time)
        previous_sequence = sequence
    return sha256_json({"manifest_sha256": sha256_file(manifest),
                        "frames": [[row["filename"], row["sha256"]] for row in rows]})


class MediaPreparer:
    def __init__(self, config: SheriffConfig) -> None:
        self.config = config
        self.media = config.raw["media"]

    def probe(self, source: Path, *, heartbeat=None, should_cancel=None,
              on_process_start=None, metrics_sink=None) -> dict[str, Any]:
        cmd = [str(self.media["ffprobe"]), "-v", "error", "-show_streams",
               "-show_format", "-of", "json", str(source)]
        returncode, stdout, stderr = run_capture(
            cmd, timeout_s=120, heartbeat=heartbeat, should_cancel=should_cancel,
            on_start=on_process_start, metrics_sink=metrics_sink)
        if returncode:
            raise MediaError(f"ffprobe rc={returncode}: {stderr[-500:]}")
        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise MediaError(f"ffprobe bozuk JSON: {exc}") from exc
        streams = raw.get("streams") or []
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        if not video:
            raise MediaError("video stream bulunamadi")
        duration = _float((raw.get("format") or {}).get("duration"))
        if duration is None:
            duration = _float(video.get("duration"))
        if duration is None or duration <= 0:
            raise MediaError("video suresi okunamadi")
        return {
            "duration_s": duration,
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "fps": video.get("avg_frame_rate") or video.get("r_frame_rate"),
            "video_codec": video.get("codec_name"),
            "pixel_format": video.get("pix_fmt"),
            "streams": [
                {key: stream.get(key) for key in (
                    "index", "codec_type", "codec_name", "codec_long_name",
                    "width", "height", "sample_rate", "channels", "channel_layout",
                    "avg_frame_rate", "r_frame_rate", "time_base", "duration")}
                for stream in streams
            ],
            "format": {key: (raw.get("format") or {}).get(key) for key in (
                "format_name", "format_long_name", "duration", "size", "bit_rate")},
            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        }

    def prepare(self, source: Path, run_dir: Path, *,
                heartbeat: Callable[[], None] | None = None,
                should_cancel: Callable[[], bool] | None = None,
                on_process_start=None) -> dict[str, Any]:
        source = source.resolve()
        if not source.is_file():
            raise MediaError(f"video yok: {source}")
        final = run_dir / "media"
        manifest_path = final / "media.manifest.json"
        source_hash = sha256_file(source)
        input_fingerprint = sha256_json({"source_sha256": source_hash,
                                         "media_config": self.media})
        if manifest_path.is_file():
            try:
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
                if existing.get("input_fingerprint") == input_fingerprint:
                    self._verify_existing(final, existing)
                    return existing
            except (OSError, json.JSONDecodeError, AttributeError, TypeError,
                    ValueError, MediaError):
                pass

        final.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".media-", dir=final.parent))
        try:
            resource_usage: dict[str, Any] = {}
            metadata = self.probe(source, heartbeat=heartbeat, should_cancel=should_cancel,
                                  on_process_start=on_process_start,
                                  metrics_sink=resource_usage)
            result: dict[str, Any] = {
                "schema_version": "mitas.media/v1",
                "input_fingerprint": input_fingerprint,
                "created_at": now_iso(),
                "source": {"path": str(source), "sha256": source_hash,
                           "bytes": source.stat().st_size},
                "probe": metadata,
                "audio": {"status": "ABSENT", "path": None, "sha256": None},
                "sections": {},
                "resource_usage": resource_usage,
            }
            if metadata["has_audio"]:
                audio = temporary / "audio.wav"
                self._run_ffmpeg([
                    "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1",
                    "-ar", str(int(self.media["audio_sample_rate"])),
                    "-c:a", "pcm_s16le", str(audio),
                ], heartbeat=heartbeat, should_cancel=should_cancel,
                   on_process_start=on_process_start, metrics_sink=resource_usage)
                result["audio"] = {"status": "PRESENT", "path": "audio.wav",
                                   "sha256": sha256_file(audio),
                                   "bytes": audio.stat().st_size,
                                   "sample_rate": int(self.media["audio_sample_rate"]),
                                   "channels": 1, "codec": "pcm_s16le"}
            if heartbeat:
                heartbeat()

            duration = float(metadata["duration_s"])
            windows = {
                "giris": (0.0, min(duration, float(self.media["opening_seconds"]))),
                "cikis": (max(0.0, duration - float(self.media["closing_seconds"])),
                           min(duration, float(self.media["closing_seconds"]))),
            }
            for section, (start_s, length_s) in windows.items():
                result["sections"][section] = self._frames(
                    source, temporary, section, start_s, length_s,
                    heartbeat=heartbeat, should_cancel=should_cancel,
                    on_process_start=on_process_start, metrics_sink=resource_usage)
                if heartbeat:
                    heartbeat()

            atomic_write_json(temporary / "media.manifest.json", result)
            if final.exists():
                stale = final.with_name(f"media.stale-{os.getpid()}")
                stale.unlink(missing_ok=True) if stale.is_file() else None
                if stale.exists():
                    shutil.rmtree(stale)
                os.replace(final, stale)
                shutil.rmtree(stale, ignore_errors=True)
            os.replace(temporary, final)
            return result
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    def _frames(self, source: Path, root: Path, section: str, start_s: float,
                length_s: float, *, heartbeat=None, should_cancel=None,
                on_process_start=None, metrics_sink=None) -> dict[str, Any]:
        section_dir = root / "frames" / section
        section_dir.mkdir(parents=True, exist_ok=True)
        # `-frame_pts 1` makes ffmpeg's sampled output PTS observable without
        # scraping stderr. The temporary PTS filenames are then renamed to the
        # stable one-based sequence expected by the towers.
        pattern = section_dir / "pts_%012d.png"
        self._run_ffmpeg([
            "-ss", f"{start_s:.6f}", "-i", str(source), "-t", f"{length_s:.6f}",
            "-map", "0:v:0", "-an", "-vf",
            f"fps={float(self.media['fps']):g}",
            "-fps_mode", "vfr", "-frame_pts", "1", str(pattern),
        ], heartbeat=heartbeat, should_cancel=should_cancel,
           on_process_start=on_process_start, metrics_sink=metrics_sink)
        pts_paths = sorted(section_dir.glob("pts_*.png"))
        if not pts_paths:
            raise MediaError(f"{section}: ffmpeg kare uretmedi")
        fps = float(self.media["fps"])
        pts_values: list[int] = []
        paths: list[Path] = []
        for index, pts_path in enumerate(pts_paths, start=1):
            try:
                pts = int(pts_path.stem.removeprefix("pts_"))
            except ValueError as exc:
                raise MediaError(f"{section}: ffmpeg PTS dosya adi bozuk: {pts_path.name}") from exc
            target = section_dir / f"frame_{index:06d}.png"
            os.replace(pts_path, target)
            pts_values.append(pts)
            paths.append(target)
        pts_origin = pts_values[0]
        manifest = section_dir / "frames.jsonl"
        with manifest.open("w", encoding="utf-8") as handle:
            for index, path in enumerate(paths, start=1):
                width, height = png_size(path)
                output_pts = pts_values[index - 1]
                local_s = max(0.0, (output_pts - pts_origin) / fps)
                row = {
                    "schema_version": "mitas.frame/v1",
                    "section": section,
                    "filename": path.name,
                    "sequence": index,
                    "source_time_s": round(start_s + local_s, 6),
                    "section_time_s": round(local_s, 6),
                    "width": width,
                    "height": height,
                    "sha256": sha256_file(path),
                    "sampling": {"method": "ffmpeg_fps", "fps": fps,
                                 "timestamp_kind": "ffmpeg_output_pts",
                                 "ffmpeg_output_pts": output_pts,
                                 "output_pts_seconds_per_tick": round(1.0 / fps, 9)},
                }
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        pool_sha256 = verify_frame_pool(section_dir, expected_section=section)
        return {
            "status": "PRESENT",
            "directory": f"frames/{section}",
            "manifest": f"frames/{section}/frames.jsonl",
            "window_start_s": round(start_s, 6),
            "window_duration_s": round(length_s, 6),
            "fps": fps,
            "frame_count": len(paths),
            "manifest_sha256": sha256_file(manifest),
            "pool_sha256": pool_sha256,
            "native_width": png_size(paths[0])[0],
            "native_height": png_size(paths[0])[1],
        }

    def _run_ffmpeg(self, args: list[str], *, heartbeat=None, should_cancel=None,
                    loglevel: str = "error", on_process_start=None,
                    metrics_sink=None) -> str:
        threads = max(1, int(self.config.resource_profile(
            "cpu_media").get("cpu_threads", 1)))
        cmd = [str(self.media["ffmpeg"]), "-y", "-nostdin", "-v", loglevel,
               "-threads", str(threads), "-filter_threads", str(threads),
               *args[:-1], "-threads", str(threads), args[-1]]
        returncode, _, stderr = run_capture(
            cmd, timeout_s=int(self.media["ffmpeg_timeout_seconds"]),
            heartbeat=heartbeat, should_cancel=should_cancel,
            on_start=on_process_start, metrics_sink=metrics_sink)
        if returncode:
            raise MediaError(f"ffmpeg rc={returncode}: {stderr[-800:]}")
        return stderr

    @staticmethod
    def _verify_existing(root: Path, manifest: dict[str, Any]) -> None:
        if manifest.get("schema_version") != "mitas.media/v1":
            raise MediaError("mevcut media schema_version gecersiz")
        for section in ("giris", "cikis"):
            item = manifest.get("sections", {}).get(section) or {}
            directory = root / str(item.get("directory", ""))
            frame_manifest = root / str(item.get("manifest", ""))
            if not directory.is_dir() or not frame_manifest.is_file():
                raise MediaError(f"eksik yeniden-kullanilabilir medya: {section}")
            if int(item.get("frame_count", -1)) != len(list(directory.glob("frame_*.png"))):
                raise MediaError(f"kare sayisi uyusmuyor: {section}")
            pool_sha256 = verify_frame_pool(directory, expected_section=section)
            if (item.get("manifest_sha256") != sha256_file(frame_manifest)
                    or item.get("pool_sha256") != pool_sha256):
                raise MediaError(f"frame manifest/pool hash uyusmuyor: {section}")
        audio = manifest.get("audio") or {}
        if audio.get("status") == "PRESENT":
            path = root / str(audio.get("path", ""))
            if not path.is_file() or sha256_file(path) != audio.get("sha256"):
                raise MediaError("audio hash uyusmuyor")


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
