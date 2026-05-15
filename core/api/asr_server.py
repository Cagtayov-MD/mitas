"""ASR-only local API for the MITAS WebUI.

This server intentionally exposes only the ASR workflow. OCR, face, tag, and
logo analysis are not started from here.
"""

from __future__ import annotations

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import traceback
import tempfile
from typing import Any, Literal
from uuid import uuid4
import wave

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.api.live_stt_text import LIVE_STT_INITIAL_PROMPT, repair_live_text
from core.pipelines.asr.models import DEFAULT_TRANSCRIBE_PARAMS, FAST_MODEL, ProfileName, load_model
from core.pipelines.asr.normalize import PROJECT_ROOT
from core.pipelines.asr.pipeline import run_asr_pipeline


JobState = Literal["queued", "running", "done", "partial", "failed"]
LiveSessionState = Literal["ready", "listening", "resolving", "paused", "error"]

API_VERSION = "asr-api-v0.1"
UPLOAD_ROOT = PROJECT_ROOT / "outputs" / "webui_uploads"
JOB_ROOT = PROJECT_ROOT / "outputs" / "webui_asr_jobs"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024 * 1024
LIVE_STT_SAMPLE_RATE = 16_000
LIVE_STT_MAX_CHUNK_BYTES = LIVE_STT_SAMPLE_RATE * 2 * 15
TRANSLATE_PYTHON = PROJECT_ROOT / "venvs" / "translate" / "Scripts" / "python.exe"
TRANSLATE_API_SCRIPT = PROJECT_ROOT / "scripts" / "translate_api_call.py"
TRANSLATE_TIMEOUT_SECONDS = 600

app = FastAPI(title="MITAS ASR API", version=API_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mitas-asr")
_live_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mitas-stt-live")
_translate_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mitas-translate")
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Return local API health and model path availability."""
    return {
        "ok": True,
        "version": API_VERSION,
        "modules": {
            "asr": "enabled",
            "stt_preview": "enabled",
            "translation": "enabled" if TRANSLATE_PYTHON.exists() and TRANSLATE_API_SCRIPT.exists() else "disabled",
            "ocr": "disabled",
            "face": "disabled",
            "tag": "disabled",
            "logo": "disabled",
        },
        "models": {
            "large-v3": (PROJECT_ROOT / "models" / "asr" / "faster-whisper" / "large-v3").exists(),
            "large-v3-turbo": (PROJECT_ROOT / "models" / "asr" / "faster-whisper" / "large-v3-turbo").exists(),
            "mt-opus-en-tr": (PROJECT_ROOT / "models" / "translate" / "opus-mt-tc-big-en-tr-ct2-int8" / "model.bin").exists(),
            "mt-nllb-3b": (PROJECT_ROOT / "models" / "translate" / "nllb-200-3.3B-ct2-int8" / "model.bin").exists(),
        },
    }


@app.post("/api/asr/transcribe")
async def create_asr_job(
    request: Request,
    filename: str = Query(default="media"),
    profile: ProfileName = Query(default="fast_with_fallback"),
    channel_mode: Literal["mono", "split", "auto"] = Query(default="auto"),
) -> dict[str, Any]:
    """Store uploaded media and start an ASR job in the background."""
    job_id = f"asr-{uuid4().hex[:12]}"
    safe_name = _safe_filename(filename)
    job_dir = JOB_ROOT / job_id
    upload_dir = UPLOAD_ROOT / job_id
    input_path = upload_dir / safe_name
    run_dir = job_dir / "run"
    job_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    size = await _write_request_body(request, input_path)
    if size == 0:
        raise HTTPException(status_code=400, detail="empty_upload")

    job = {
        "job_id": job_id,
        "status": "queued",
        "filename": safe_name,
        "input_path": str(input_path),
        "output_dir": str(run_dir),
        "profile": profile,
        "channel_mode": channel_mode,
        "size_bytes": size,
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
        "message": "ASR işi kuyruğa alındı.",
        "error": None,
    }
    _save_job(job)
    _executor.submit(_run_job, job_id)
    return _public_job(job)


@app.get("/api/jobs")
def list_jobs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    """List recent ASR jobs."""
    jobs = [_public_job(job) for job in _load_recent_jobs(limit)]
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    """Return job status and ASR artifacts when available."""
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return _public_job(job)


@app.post("/api/translate/segments")
async def translate_segments(request: Request) -> dict[str, Any]:
    """Translate selected transcript segments through the isolated translate venv."""
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc
    translate_payload = _prepare_translate_payload(payload)
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(_translate_executor, _run_translate_subprocess, translate_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.websocket("/api/stt/preview/ws")
async def stt_preview_socket(websocket: WebSocket) -> None:
    """Stream small 16 kHz PCM16 chunks from the WebUI and return live transcript lines."""
    await websocket.accept()
    session_id = f"stt-preview-{uuid4().hex[:10]}"
    state: LiveSessionState = "ready"
    await websocket.send_json(
        {
            "type": "ready",
            "session_id": session_id,
            "version": API_VERSION,
            "sample_rate": LIVE_STT_SAMPLE_RATE,
            "model": FAST_MODEL.name,
        }
    )

    try:
        while True:
            payload = await websocket.receive_json()
            message_type = str(payload.get("type", "")).lower()

            if message_type == "start":
                state = "ready"
                await _send_live_status(websocket, state, "Hazır")
                continue

            if message_type == "pause":
                state = "paused"
                await _send_live_status(websocket, state, "Durakladı")
                continue

            if message_type == "resume":
                state = "listening"
                await _send_live_status(websocket, state, "Dinliyor")
                continue

            if message_type == "seek":
                state = "listening"
                await _send_live_status(websocket, state, "Yeni konum dinleniyor")
                continue

            if message_type == "stop":
                await _send_live_status(websocket, "ready", "Durduruldu")
                await websocket.close(code=1000)
                return

            if message_type != "chunk":
                await _send_live_error(websocket, "unknown_message", f"Bilinmeyen mesaj: {message_type or '-'}")
                continue

            if state == "paused":
                continue

            try:
                chunk = _parse_live_chunk(payload)
            except ValueError as exc:
                state = "error"
                await _send_live_error(websocket, "bad_chunk", str(exc))
                continue

            state = "resolving"
            await _send_live_status(websocket, state, "Çözümlüyor", chunk_id=chunk["chunk_id"])
            loop = asyncio.get_running_loop()
            try:
                segments = await loop.run_in_executor(
                    _live_executor,
                    _transcribe_live_pcm16,
                    chunk["audio_bytes"],
                    chunk["media_time_start"],
                    chunk["media_time_end"],
                    chunk["publish_after"],
                    chunk["publish_until"],
                )
            except Exception as exc:  # noqa: BLE001 - live preview must return socket error
                state = "error"
                await _send_live_error(websocket, "transcribe_failed", str(exc), chunk_id=chunk["chunk_id"])
                continue

            text = " ".join(str(segment.get("text", "")).strip() for segment in segments).strip()
            language = _dominant_language(segments)
            if text:
                await websocket.send_json(
                    {
                        "type": "partial",
                        "session_id": session_id,
                        "chunk_id": chunk["chunk_id"],
                        "media_time_start": chunk["publish_after"],
                        "media_time_end": chunk["publish_until"],
                        "publish_until": chunk["publish_until"],
                        "text": text,
                        "language": language,
                    }
                )
            await websocket.send_json(
                {
                    "type": "final",
                    "session_id": session_id,
                    "chunk_id": chunk["chunk_id"],
                    "media_time_start": chunk["publish_after"],
                    "media_time_end": chunk["publish_until"],
                    "publish_until": chunk["publish_until"],
                    "text": text,
                    "segments": segments,
                    "language": language,
                }
            )
            state = "listening"
            await _send_live_status(websocket, state, "Dinliyor", chunk_id=chunk["chunk_id"])
    except WebSocketDisconnect:
        return


def _run_job(job_id: str) -> None:
    job = _load_job(job_id)
    if job is None:
        return

    _update_job(
        job_id,
        status="running",
        started_at=_now_iso(),
        message="Gerçek ASR modeli çalışıyor.",
    )
    try:
        result = run_asr_pipeline(
            job["input_path"],
            profile=job["profile"],
            channel_mode=job["channel_mode"],
            output_dir=job["output_dir"],
            media_id=Path(job["filename"]).stem,
            job_id=job_id,
            module_run_id=f"{job_id}-module",
        )
        module_status = str(result.module_run.status)
        status: JobState = "partial" if module_status == "partial" else "done"
        _update_job(
            job_id,
            status=status,
            completed_at=_now_iso(),
            message="ASR tamamlandı." if status == "done" else "ASR kısmi sonuçla tamamlandı.",
            archive_path=str(result.archive_path),
            module_run_path=str(result.module_run_path),
            summary_path=str(result.summary_path),
            transcript_review_path=str(result.transcript_review_path),
            timeline_events_path=str(result.timeline_events_path),
        )
    except Exception as exc:  # noqa: BLE001 - persisted local job error
        _update_job(
            job_id,
            status="failed",
            completed_at=_now_iso(),
            message="ASR başarısız oldu.",
            error=str(exc),
            traceback=traceback.format_exc(),
        )


def _parse_live_chunk(payload: dict[str, Any]) -> dict[str, Any]:
    chunk_id = str(payload.get("chunk_id") or uuid4().hex[:8])
    try:
        media_time_start = max(0.0, float(payload["media_time_start"]))
        media_time_end = max(media_time_start, float(payload["media_time_end"]))
        publish_after = float(payload.get("publish_after", media_time_start))
        publish_until = float(payload.get("publish_until", media_time_end))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("chunk zaman bilgisi eksik veya hatalı") from exc
    publish_after = min(max(publish_after, media_time_start), media_time_end)
    publish_until = min(max(publish_until, publish_after), media_time_end)

    audio_b64 = payload.get("audio_b64")
    if not isinstance(audio_b64, str) or not audio_b64:
        raise ValueError("chunk audio_b64 alanı boş")
    try:
        audio_bytes = base64.b64decode(audio_b64, validate=True)
    except ValueError as exc:
        raise ValueError("chunk audio_b64 çözülemedi") from exc

    if len(audio_bytes) < 2:
        raise ValueError("chunk ses verisi boş")
    if len(audio_bytes) > LIVE_STT_MAX_CHUNK_BYTES:
        raise ValueError("chunk ses verisi çok büyük")
    if len(audio_bytes) % 2:
        audio_bytes = audio_bytes[:-1]
    return {
        "chunk_id": chunk_id,
        "media_time_start": media_time_start,
        "media_time_end": media_time_end,
        "publish_after": publish_after,
        "publish_until": publish_until,
        "audio_bytes": audio_bytes,
    }


def _transcribe_live_pcm16(
    audio_bytes: bytes,
    media_time_start: float,
    media_time_end: float,
    publish_after: float | None = None,
    publish_until: float | None = None,
) -> list[dict[str, Any]]:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary_file:
        chunk_path = Path(temporary_file.name)

    try:
        with wave.open(str(chunk_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(LIVE_STT_SAMPLE_RATE)
            wav_file.writeframes(audio_bytes)

        model = load_model(FAST_MODEL)
        params = DEFAULT_TRANSCRIBE_PARAMS
        raw_segments, info = model.transcribe(
            str(chunk_path),
            beam_size=FAST_MODEL.beam_size,
            language=params.language,
            multilingual=params.multilingual,
            initial_prompt=LIVE_STT_INITIAL_PROMPT,
            condition_on_previous_text=False,
            vad_filter=False,
            word_timestamps=True,
            temperature=list(params.temperature),
            compression_ratio_threshold=params.compression_ratio_threshold,
            log_prob_threshold=params.log_prob_threshold,
            no_speech_threshold=params.no_speech_threshold,
        )
        fallback_language = getattr(info, "language", None)
        mapped: list[dict[str, Any]] = []
        publish_after = media_time_start if publish_after is None else publish_after
        publish_until = media_time_end if publish_until is None else publish_until
        for index, raw_segment in enumerate(raw_segments):
            text = str(getattr(raw_segment, "text", "")).strip()
            if not text:
                continue
            text = repair_live_text(text)
            if not text:
                continue
            raw_start = float(getattr(raw_segment, "start", 0.0) or 0.0)
            raw_end = float(getattr(raw_segment, "end", 0.0) or 0.0)
            absolute_start = media_time_start + raw_start
            absolute_end = min(media_time_end, media_time_start + raw_end)

            word_result = _live_words_in_publish_window(
                raw_segment,
                media_time_start=media_time_start,
                publish_after=publish_after,
                publish_until=publish_until,
            )
            if word_result is not None:
                text, absolute_start, absolute_end = word_result
                text = repair_live_text(text)
                if not text:
                    continue
                mapped.append(
                    {
                        "id": f"live-{round(media_time_start, 3)}-{index}",
                        "start": round(absolute_start, 3),
                        "end": round(max(absolute_start + 0.001, absolute_end), 3),
                        "text": text,
                        "language": getattr(raw_segment, "language", None) or fallback_language,
                        "avg_logprob": float(getattr(raw_segment, "avg_logprob", 0.0) or 0.0),
                        "no_speech_prob": float(getattr(raw_segment, "no_speech_prob", 0.0) or 0.0),
                    }
                )
                continue

            if absolute_end <= publish_after + 0.15:
                continue
            if absolute_start >= publish_until - 0.05 or absolute_end > publish_until + 0.15:
                continue
            start = round(max(publish_after, absolute_start), 3)
            end = round(max(start + 0.001, min(publish_until, absolute_end)), 3)
            mapped.append(
                {
                    "id": f"live-{round(media_time_start, 3)}-{index}",
                    "start": start,
                    "end": end,
                    "text": text,
                    "language": getattr(raw_segment, "language", None) or fallback_language,
                    "avg_logprob": float(getattr(raw_segment, "avg_logprob", 0.0) or 0.0),
                    "no_speech_prob": float(getattr(raw_segment, "no_speech_prob", 0.0) or 0.0),
                }
            )
        return mapped
    finally:
        chunk_path.unlink(missing_ok=True)


def _live_words_in_publish_window(
    raw_segment: Any,
    *,
    media_time_start: float,
    publish_after: float,
    publish_until: float,
) -> tuple[str, float, float] | None:
    words = list(getattr(raw_segment, "words", None) or [])
    if not words:
        return None

    selected: list[Any] = []
    for word in words:
        word_start = media_time_start + float(getattr(word, "start", 0.0) or 0.0)
        word_end = media_time_start + float(getattr(word, "end", 0.0) or 0.0)
        if word_end <= publish_after + 0.05:
            continue
        if word_end > publish_until + 0.05:
            continue
        selected.append(word)

    if not selected:
        return None

    tokens = [str(getattr(word, "word", "") or "") for word in selected]
    text = "".join(tokens).strip() if any(token[:1].isspace() for token in tokens) else " ".join(tokens).strip()
    if not text:
        return None

    start = media_time_start + float(getattr(selected[0], "start", 0.0) or 0.0)
    end = media_time_start + float(getattr(selected[-1], "end", 0.0) or 0.0)
    return text, max(start, publish_after), min(end, publish_until)


async def _send_live_status(
    websocket: WebSocket,
    status: LiveSessionState,
    message: str,
    *,
    chunk_id: str | None = None,
) -> None:
    payload: dict[str, Any] = {"type": "status", "status": status, "message": message}
    if chunk_id is not None:
        payload["chunk_id"] = chunk_id
    await websocket.send_json(payload)


async def _send_live_error(
    websocket: WebSocket,
    code: str,
    message: str,
    *,
    chunk_id: str | None = None,
) -> None:
    payload: dict[str, Any] = {"type": "error", "code": code, "message": message}
    if chunk_id is not None:
        payload["chunk_id"] = chunk_id
    await websocket.send_json(payload)


def _dominant_language(segments: list[dict[str, Any]]) -> str | None:
    languages = [str(segment.get("language")) for segment in segments if segment.get("language")]
    if not languages:
        return None
    return max(set(languages), key=languages.count)


def _prepare_translate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("items must be a non-empty list")
    if len(raw_items) > 50:
        raise ValueError("too_many_items")

    items: list[dict[str, str]] = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise ValueError(f"items[{index}] must be an object")
        segment_id = str(raw_item.get("segment_id") or "").strip()
        source_text = str(raw_item.get("source_text") or "").strip()
        source_lang = _normalize_translate_source_lang(raw_item.get("source_lang"))
        if not segment_id:
            raise ValueError(f"items[{index}].segment_id is required")
        if not source_text:
            raise ValueError(f"items[{index}].source_text is required")
        if source_lang is None:
            raise ValueError(f"items[{index}].source_lang is required")
        items.append(
            {
                "segment_id": segment_id,
                "source_text": source_text,
                "source_lang": source_lang,
            }
        )

    target_lang = str(payload.get("target_lang") or "tr").strip().lower() or "tr"
    model_override = payload.get("model_override")
    job_id = str(payload.get("job_id") or "").strip()
    prepared: dict[str, Any] = {
        "items": items,
        "target_lang": target_lang,
        "cache_dir": str(_translation_cache_dir(job_id)),
    }
    if model_override:
        prepared["model_override"] = str(model_override)
    return prepared


def _normalize_translate_source_lang(value: Any) -> str | None:
    if value is None:
        return None
    source_lang = str(value).strip().lower().replace("_", "-")
    if not source_lang or source_lang in {"unknown", "und", "none", "null"}:
        return None
    if source_lang.startswith("en"):
        return "en"
    if source_lang.startswith("tr") or source_lang.startswith("tur"):
        return "tr"
    return source_lang.split("-")[0]


def _translation_cache_dir(job_id: str) -> Path:
    if job_id:
        job = _load_job(job_id)
        if job is not None:
            return Path(str(job["output_dir"])) / "translations"
        return JOB_ROOT / _safe_filename(job_id) / "translations"
    return PROJECT_ROOT / "outputs" / "webui_translate_cache"


def _run_translate_subprocess(payload: dict[str, Any]) -> dict[str, Any]:
    if not TRANSLATE_PYTHON.exists():
        raise RuntimeError("translate_venv_missing")
    if not TRANSLATE_API_SCRIPT.exists():
        raise RuntimeError("translate_api_script_missing")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    completed = subprocess.run(
        [str(TRANSLATE_PYTHON), str(TRANSLATE_API_SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(PROJECT_ROOT),
        env=env,
        timeout=TRANSLATE_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "translation_failed").strip()
        raise RuntimeError(detail[-4000:])
    return _parse_translate_stdout(completed.stdout)


def _parse_translate_stdout(stdout: str) -> dict[str, Any]:
    for line in reversed([candidate.strip() for candidate in stdout.splitlines() if candidate.strip()]):
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("translation_response_invalid")


async def _write_request_body(request: Request, destination: Path) -> int:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="upload_too_large")
        except ValueError:
            pass

    written = 0
    with destination.open("wb") as handle:
        async for chunk in request.stream():
            if not chunk:
                continue
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="upload_too_large")
            handle.write(chunk)
    return written


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    payload = dict(job)
    summary_path = payload.get("summary_path") or str(Path(payload["output_dir"]) / "summary.json")
    archive_path = payload.get("archive_path") or str(Path(payload["output_dir"]) / "archive.json")
    timeline_path = payload.get("timeline_events_path") or str(Path(payload["output_dir"]) / "timeline_events.json")
    summary = _read_json(summary_path)
    archive = _read_json(archive_path)
    timeline = _read_json(timeline_path)

    if summary is not None:
        payload["summary"] = summary
    if archive is not None:
        payload["archive"] = archive
        transcript = archive.get("transcript") or {}
        payload["transcript"] = transcript.get("clean") or transcript.get("verbatim") or ""
        payload["segments"] = archive.get("segments") or []
    else:
        payload["transcript"] = ""
        payload["segments"] = []
    if timeline is not None:
        payload["timeline_events"] = timeline.get("events") or []
    else:
        payload["timeline_events"] = []
    return payload


def _load_recent_jobs(limit: int) -> list[dict[str, Any]]:
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    paths = sorted(JOB_ROOT.glob("*/job.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    jobs: list[dict[str, Any]] = []
    for path in paths[:limit]:
        payload = _read_json(path)
        if isinstance(payload, dict):
            jobs.append(payload)
    return jobs


def _load_job(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        if job_id in _jobs:
            return dict(_jobs[job_id])
    path = JOB_ROOT / job_id / "job.json"
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else None


def _save_job(job: dict[str, Any]) -> None:
    with _jobs_lock:
        _jobs[job["job_id"]] = dict(job)
    _write_json(JOB_ROOT / job["job_id"] / "job.json", job)


def _update_job(job_id: str, **updates: Any) -> None:
    job = _load_job(job_id)
    if job is None:
        return
    job.update(updates)
    _save_job(job)


def _read_json(path_like: str | Path) -> Any | None:
    path = Path(path_like)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "media"
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name or "media"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
