from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess


TARGET_SAMPLE_RATE = 16_000
TARGET_CHANNELS = 1
TARGET_CODEC_NAME = "pcm_s16le"
TARGET_SAMPLE_FMT = "s16"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "asr_normalize"


class AudioNormalizeError(RuntimeError):
    """Raised when audio probing or normalization fails."""

    def __init__(self, message: str, *, command: tuple[str, ...] | None = None, stderr: str | None = None) -> None:
        super().__init__(message)
        self.command = command
        self.stderr = stderr


@dataclass(frozen=True)
class AudioStreamInfo:
    path: Path
    codec_name: str
    sample_rate: int
    channels: int
    sample_fmt: str | None

    @property
    def is_target_wav(self) -> bool:
        return (
            self.path.suffix.lower() == ".wav"
            and self.codec_name == TARGET_CODEC_NAME
            and self.sample_rate == TARGET_SAMPLE_RATE
            and self.channels == TARGET_CHANNELS
            and self.sample_fmt == TARGET_SAMPLE_FMT
        )


@dataclass(frozen=True)
class NormalizeResult:
    input_path: Path
    output_path: Path
    input_stream: AudioStreamInfo
    output_stream: AudioStreamInfo
    reused_input: bool
    command: tuple[str, ...] | None


def probe_audio_stream(input_path: str | Path, *, ffprobe_executable: str = "ffprobe") -> AudioStreamInfo:
    path = Path(input_path)
    if not path.exists():
        raise AudioNormalizeError(f"Audio input does not exist: {path}")

    command = (
        ffprobe_executable,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name,sample_rate,channels,sample_fmt",
        "-of",
        "json",
        str(path),
    )
    completed = _run_command(command)

    try:
        payload = json.loads(completed.stdout)
        stream = payload["streams"][0]
        return AudioStreamInfo(
            path=path,
            codec_name=str(stream["codec_name"]),
            sample_rate=int(stream["sample_rate"]),
            channels=int(stream["channels"]),
            sample_fmt=stream.get("sample_fmt"),
        )
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AudioNormalizeError(f"No readable audio stream found in: {path}", command=command, stderr=completed.stderr) from exc


def normalize_audio(
    input_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    ffmpeg_executable: str = "ffmpeg",
    ffprobe_executable: str = "ffprobe",
) -> NormalizeResult:
    source = Path(input_path)
    input_stream = probe_audio_stream(source, ffprobe_executable=ffprobe_executable)

    if input_stream.is_target_wav:
        return NormalizeResult(
            input_path=source,
            output_path=source,
            input_stream=input_stream,
            output_stream=input_stream,
            reused_input=True,
            command=None,
        )

    destination_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)
    output_path = destination_dir / _normalized_filename(source)

    command = (
        ffmpeg_executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        str(TARGET_CHANNELS),
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-acodec",
        TARGET_CODEC_NAME,
        str(output_path),
    )
    _run_command(command)
    output_stream = probe_audio_stream(output_path, ffprobe_executable=ffprobe_executable)

    if not output_stream.is_target_wav:
        raise AudioNormalizeError(f"Normalized output is not in target ASR format: {output_path}", command=command)

    return NormalizeResult(
        input_path=source,
        output_path=output_path,
        input_stream=input_stream,
        output_stream=output_stream,
        reused_input=False,
        command=command,
    )


def _normalized_filename(input_path: Path) -> str:
    resolved = str(input_path.resolve()).encode("utf-8", errors="surrogatepass")
    digest = hashlib.sha1(resolved).hexdigest()[:10]
    return f"{input_path.stem}_{digest}_16000hz_mono_s16.wav"


def _run_command(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise AudioNormalizeError(f"Failed to run command: {command[0]}", command=command, stderr=str(exc)) from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        raise AudioNormalizeError(f"Audio command failed: {stderr}", command=command, stderr=stderr)

    return completed
