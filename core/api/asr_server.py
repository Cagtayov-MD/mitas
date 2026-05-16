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
from core.observability import system_events
from core.pipelines.asr.models import DEFAULT_TRANSCRIBE_PARAMS, FAST_MODEL, ProfileName, load_model
from core.pipelines.asr.normalize import PROJECT_ROOT
from core.pipelines.asr.pipeline import run_asr_pipeline


JobState = Literal["queued", "running", "done", "partial", "failed"]
LiveSessionState = Literal["ready", "listening", "resolving", "paused", "error"]

API_VERSION = "asr-api-v0.1"
CLIPS_ROOT = PROJECT_ROOT / "outputs" / "clips"
# Legacy roots kept only for reading old development jobs created before the
# clip-centric layout. New uploads always go under CLIPS_ROOT.
LEGACY_UPLOAD_ROOT = PROJECT_ROOT / "outputs" / "webui_uploads"
LEGACY_JOB_ROOT = PROJECT_ROOT / "outputs" / "webui_asr_jobs"
ASR_MODULE_DIR = "asr"
SOURCE_DIR = "source"
TRANSLATIONS_DIR = "translations"
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
    media_id = Path(safe_name).stem or "media"
    clip_id = _allocate_clip_id(media_id)
    clip_dir = CLIPS_ROOT / clip_id
    source_dir = clip_dir / SOURCE_DIR
    job_dir = clip_dir / ASR_MODULE_DIR / job_id
    run_dir = job_dir / "run"
    input_path = source_dir / safe_name
    source_dir.mkdir(parents=True, exist_ok=True)
    job_dir.mkdir(parents=True, exist_ok=True)

    size = await _write_request_body(request, input_path)
    if size == 0:
        raise HTTPException(status_code=400, detail="empty_upload")

    _ensure_clip_record(
        clip_id=clip_id,
        filename=safe_name,
        media_id=media_id,
        size_bytes=size,
        source_path=input_path,
    )

    job = {
        "job_id": job_id,
        "clip_id": clip_id,
        "media_id": media_id,
        "status": "queued",
        "filename": safe_name,
        "input_path": str(input_path),
        "output_dir": str(run_dir),
        "job_dir": str(job_dir),
        "clip_dir": str(clip_dir),
        "module": "asr",
        "profile": profile,
        "channel_mode": channel_mode,
        "size_bytes": size,
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
        "message": "ASR işi kuyruğa alındı.",
        "error": None,
        "progress_percent": 0,
        "progress_label": "Kuyrukta",
        "log_path": str(job_dir / "job_log.jsonl"),
    }
    _save_job(job)
    _attach_job_to_clip(clip_id, module=ASR_MODULE_DIR, job_id=job_id)
    _append_job_log(job_id, "Medya yüklendi.", stage="upload", progress_percent=3)
    _append_job_log(job_id, "ASR işi kuyruğa alındı.", stage="queued", progress_percent=5)
    system_events.log_event(
        "media_imported",
        summary=f"{safe_name} içe aktarıldı ({_format_size(size)}).",
        module="upload",
        media_id=media_id,
        filename=safe_name,
        job_id=job_id,
        detail={"clip_id": clip_id, "size_bytes": size, "profile": profile, "channel_mode": channel_mode},
    )
    system_events.log_event(
        "asr_queued",
        summary=f"{safe_name} için ASR kuyruğa alındı.",
        module="asr",
        media_id=media_id,
        filename=safe_name,
        job_id=job_id,
        detail={"clip_id": clip_id},
    )
    _executor.submit(_run_job, job_id)
    return _public_job(_load_job(job_id) or job)


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


@app.get("/api/clips")
def list_clips(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    """List clips (newest first) with their module statuses."""
    records = _list_clip_records(limit)
    clips = [_public_clip(record) for record in records]
    return {"clips": clips, "count": len(clips)}


@app.get("/api/clips/{clip_id}")
def get_clip(clip_id: str) -> dict[str, Any]:
    """Return clip metadata + every job recorded under it + recent events."""
    record = _load_clip_record(clip_id)
    if record is None:
        raise HTTPException(status_code=404, detail="clip_not_found")
    payload = _public_clip(record)
    payload["jobs"] = _public_clip_jobs(clip_id)
    payload["events"] = system_events.read_events(media_id=record.get("media_id"), limit=500)
    return payload


@app.get("/api/events")
def list_events(
    limit: int = Query(default=200, ge=1, le=2000),
    since: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    level: str | None = Query(default=None),
    module: str | None = Query(default=None),
    job_id: str | None = Query(default=None),
    media_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return system-wide events, newest-first. Used by the WebUI LOG panel."""
    events = system_events.read_events(
        limit=limit,
        since=since,
        kind=kind,
        level=level,
        module=module,
        job_id=job_id,
        media_id=media_id,
    )
    return {"events": events, "count": len(events)}


@app.get("/api/events/{event_id}")
def get_event(event_id: str) -> dict[str, Any]:
    """Return a single event plus the related per-job step log when available."""
    event = system_events.find_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    payload: dict[str, Any] = {"event": event, "job_logs": []}
    related_job_id = event.get("job_id")
    if related_job_id:
        job = _load_job(str(related_job_id))
        if job is not None:
            payload["job_logs"] = _read_job_logs(job)
            payload["job_status"] = job.get("status")
    return payload


@app.post("/api/translate/segments")
async def translate_segments(request: Request) -> dict[str, Any]:
    """Translate selected transcript segments through the isolated translate venv."""
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc
    translate_payload = _prepare_translate_payload(payload)
    job_id = str(payload.get("job_id") or "") if isinstance(payload, dict) else ""
    item_count = len(translate_payload["items"])
    target_lang = translate_payload["target_lang"]
    related_job = _load_job(job_id) if job_id else None
    media_filename = str(related_job.get("filename")) if related_job else None
    media_id = str(related_job.get("media_id")) if related_job and related_job.get("media_id") else (
        Path(media_filename).stem if media_filename else None
    )
    clip_id = str(related_job.get("clip_id")) if related_job and related_job.get("clip_id") else None
    system_events.log_event(
        "translate_started",
        summary=f"{item_count} segment için çeviri başladı (hedef: {target_lang}).",
        module="translate",
        media_id=media_id,
        filename=media_filename,
        job_id=job_id or None,
        detail={"clip_id": clip_id, "item_count": item_count, "target_lang": target_lang},
    )
    started = datetime.now(timezone.utc)
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(_translate_executor, _run_translate_subprocess, translate_payload)
    except ValueError as exc:
        system_events.log_event(
            "translate_failed",
            summary="Çeviri girişleri geçersiz.",
            level="error",
            module="translate",
            media_id=media_id,
            filename=media_filename,
            job_id=job_id or None,
            error=str(exc),
            detail={"clip_id": clip_id},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        system_events.log_event(
            "translate_failed",
            summary=f"{item_count} segment çevirisi başarısız oldu.",
            level="error",
            module="translate",
            media_id=media_id,
            filename=media_filename,
            job_id=job_id or None,
            error=str(exc),
            detail={"clip_id": clip_id},
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    system_events.log_event(
        "translate_completed",
        summary=f"{item_count} segment çevirisi tamamlandı ({elapsed:.1f} sn).",
        module="translate",
        media_id=media_id,
        filename=media_filename,
        job_id=job_id or None,
        duration_seconds=elapsed,
        detail={"clip_id": clip_id, "item_count": item_count, "target_lang": target_lang},
    )
    return result


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

    filename = str(job.get("filename") or "")
    media_id = str(job.get("media_id") or (Path(filename).stem if filename else "")) or None
    clip_id = str(job.get("clip_id") or "") or None
    _append_job_log(job_id, "ASR worker başladı.", stage="worker", progress_percent=8)
    _update_job(
        job_id,
        status="running",
        started_at=_now_iso(),
        message="Gerçek ASR modeli çalışıyor.",
        progress_percent=12,
        progress_label="ASR çalışıyor",
    )
    _append_job_log(job_id, "Normalizasyon, kanal kararı ve ASR pipeline başladı.", stage="pipeline", progress_percent=15)
    system_events.log_event(
        "asr_started",
        summary=f"{filename or media_id or job_id} için ASR başladı.",
        module="asr",
        media_id=media_id,
        filename=filename or None,
        job_id=job_id,
        detail={"clip_id": clip_id, "profile": job.get("profile"), "channel_mode": job.get("channel_mode")},
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
        _append_job_log(job_id, "ASR pipeline çıktı dosyalarını üretti.", stage="artifacts", progress_percent=95)
        summary = result.module_run.output_summary
        if summary.get("fallback_triggered"):
            fallback_chunk_count = summary.get("fallback_chunk_count")
            fallback_total_chunk_count = summary.get("fallback_total_chunk_count")
            fallback_mode = summary.get("fallback_mode") or "unknown"
            if fallback_chunk_count is not None and fallback_total_chunk_count is not None:
                fallback_detail = f"{fallback_chunk_count}/{fallback_total_chunk_count} chunk"
            else:
                fallback_detail = "chunk bilgisi yok"
            _append_job_log(
                job_id,
                f"Fallback çalıştı: {fallback_mode} ({fallback_detail}).",
                stage="fallback",
                progress_percent=96,
            )
        module_status = str(result.module_run.status)
        status: JobState = "partial" if module_status == "partial" else "done"
        _update_job(
            job_id,
            status=status,
            completed_at=_now_iso(),
            message="ASR tamamlandı." if status == "done" else "ASR kısmi sonuçla tamamlandı.",
            progress_percent=100,
            progress_label="Tamamlandı" if status == "done" else "Kısmi tamamlandı",
            archive_path=str(result.archive_path),
            module_run_path=str(result.module_run_path),
            summary_path=str(result.summary_path),
            transcript_review_path=str(result.transcript_review_path),
            timeline_events_path=str(result.timeline_events_path),
        )
        _append_job_log(
            job_id,
            "ASR tamamlandı." if status == "done" else "ASR kısmi sonuçla tamamlandı.",
            stage=status,
            progress_percent=100,
        )
        elapsed = _job_elapsed_seconds(_load_job(job_id) or job)
        if clip_id:
            _update_clip_module_status(clip_id, module=ASR_MODULE_DIR, status=status, job_id=job_id)
        system_events.log_event(
            "asr_completed" if status == "done" else "asr_partial",
            summary=(
                f"{filename or media_id or job_id} için ASR tamamlandı"
                f" ({elapsed} sn)." if status == "done"
                else f"{filename or media_id or job_id} için ASR kısmi sonuçla bitti ({elapsed} sn)."
            ),
            level="info" if status == "done" else "warn",
            module="asr",
            media_id=media_id,
            filename=filename or None,
            job_id=job_id,
            duration_seconds=elapsed,
            detail={
                "clip_id": clip_id,
                "profile": job.get("profile"),
                "fallback_triggered": bool(summary.get("fallback_triggered")) if isinstance(summary, dict) else None,
                "fallback_mode": summary.get("fallback_mode") if isinstance(summary, dict) else None,
            },
        )
    except Exception as exc:  # noqa: BLE001 - persisted local job error
        _update_job(
            job_id,
            status="failed",
            completed_at=_now_iso(),
            message="ASR başarısız oldu.",
            error=str(exc),
            traceback=traceback.format_exc(),
            progress_percent=100,
            progress_label="Hata",
        )
        _append_job_log(job_id, f"ASR başarısız oldu: {exc}", stage="failed", level="error", progress_percent=100)
        if clip_id:
            _update_clip_module_status(clip_id, module=ASR_MODULE_DIR, status="failed", job_id=job_id)
        system_events.log_event(
            "asr_failed",
            summary=f"{filename or media_id or job_id} için ASR başarısız oldu.",
            level="error",
            module="asr",
            media_id=media_id,
            filename=filename or None,
            job_id=job_id,
            error=str(exc),
            detail={"clip_id": clip_id},
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
            clip_id = str(job.get("clip_id") or "").strip()
            if clip_id:
                return CLIPS_ROOT / clip_id / TRANSLATIONS_DIR
            # Legacy fallback for pre-clip-layout jobs.
            return Path(str(job["output_dir"])) / TRANSLATIONS_DIR
        return CLIPS_ROOT / "_unknown" / TRANSLATIONS_DIR / _safe_filename(job_id)
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
    payload["elapsed_seconds"] = _job_elapsed_seconds(payload)
    payload["progress_percent"] = _job_progress_percent(payload)
    payload["logs"] = _read_job_logs(payload)
    return payload


def _job_json_paths(limit: int | None = None) -> list[Path]:
    """Collect job.json paths from the clip layout and the legacy layout."""
    candidates: list[Path] = []
    if CLIPS_ROOT.exists():
        candidates.extend(CLIPS_ROOT.glob("*/asr/*/job.json"))
    if LEGACY_JOB_ROOT.exists():
        candidates.extend(LEGACY_JOB_ROOT.glob("*/job.json"))
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    if limit is not None:
        return candidates[:limit]
    return candidates


def _load_recent_jobs(limit: int) -> list[dict[str, Any]]:
    CLIPS_ROOT.mkdir(parents=True, exist_ok=True)
    jobs: list[dict[str, Any]] = []
    for path in _job_json_paths(limit=limit):
        payload = _read_json(path)
        if isinstance(payload, dict):
            jobs.append(payload)
    return jobs


def _find_job_json(job_id: str) -> Path | None:
    if not job_id:
        return None
    if CLIPS_ROOT.exists():
        for path in CLIPS_ROOT.glob(f"*/asr/{job_id}/job.json"):
            return path
    legacy = LEGACY_JOB_ROOT / job_id / "job.json"
    if legacy.exists():
        return legacy
    return None


def _load_job(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        if job_id in _jobs:
            return dict(_jobs[job_id])
    path = _find_job_json(job_id)
    if path is None:
        return None
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else None


def _job_json_target(job: dict[str, Any]) -> Path:
    job_dir = job.get("job_dir")
    if job_dir:
        return Path(str(job_dir)) / "job.json"
    clip_id = job.get("clip_id")
    if clip_id:
        return CLIPS_ROOT / str(clip_id) / ASR_MODULE_DIR / str(job["job_id"]) / "job.json"
    return LEGACY_JOB_ROOT / str(job["job_id"]) / "job.json"


def _save_job(job: dict[str, Any]) -> None:
    with _jobs_lock:
        _jobs[job["job_id"]] = dict(job)
    _write_json(_job_json_target(job), job)


def _allocate_clip_id(media_id: str) -> str:
    """Allocate a unique clip folder name.

    Common case: ``er_vid`` → ``er_vid``. On collision, append ``_2``, ``_3``,
    … until a free slot is found. The numeric suffix is preferred over a
    random hash because most clips are uploaded once and short readable names
    make manual disk inspection easier.
    """
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (media_id or "media").strip()) or "media"
    if not (CLIPS_ROOT / base).exists():
        return base
    index = 2
    while (CLIPS_ROOT / f"{base}_{index}").exists():
        index += 1
    return f"{base}_{index}"


def _clip_record_path(clip_id: str) -> Path:
    return CLIPS_ROOT / clip_id / "clip.json"


def _ensure_clip_record(
    *,
    clip_id: str,
    filename: str,
    media_id: str,
    size_bytes: int,
    source_path: Path,
) -> dict[str, Any]:
    path = _clip_record_path(clip_id)
    existing = _read_json(path)
    record: dict[str, Any]
    if isinstance(existing, dict):
        record = existing
    else:
        record = {
            "clip_id": clip_id,
            "media_id": media_id,
            "filename": filename,
            "imported_at": _now_iso(),
            "size_bytes": size_bytes,
            "source_path": str(source_path),
            "modules": {},
        }
    record.setdefault("modules", {})
    _write_json(path, record)
    return record


def _attach_job_to_clip(clip_id: str, *, module: str, job_id: str) -> None:
    path = _clip_record_path(clip_id)
    record = _read_json(path)
    if not isinstance(record, dict):
        return
    modules = record.setdefault("modules", {})
    module_state = modules.setdefault(module, {"jobs": [], "latest_job_id": None, "status": None})
    if job_id not in module_state.get("jobs", []):
        module_state.setdefault("jobs", []).append(job_id)
    module_state["latest_job_id"] = job_id
    module_state["status"] = "queued"
    module_state["updated_at"] = _now_iso()
    _write_json(path, record)


def _update_clip_module_status(clip_id: str, *, module: str, status: str, job_id: str) -> None:
    path = _clip_record_path(clip_id)
    record = _read_json(path)
    if not isinstance(record, dict):
        return
    modules = record.setdefault("modules", {})
    module_state = modules.setdefault(module, {"jobs": [job_id], "latest_job_id": job_id})
    module_state["status"] = status
    module_state["latest_job_id"] = job_id
    module_state["updated_at"] = _now_iso()
    _write_json(path, record)


def _load_clip_record(clip_id: str) -> dict[str, Any] | None:
    record = _read_json(_clip_record_path(clip_id))
    return record if isinstance(record, dict) else None


def _public_clip(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    modules = out.get("modules") or {}
    summary: dict[str, Any] = {}
    for module, state in modules.items():
        if isinstance(state, dict):
            summary[module] = {
                "status": state.get("status"),
                "latest_job_id": state.get("latest_job_id"),
                "job_count": len(state.get("jobs") or []),
                "updated_at": state.get("updated_at"),
            }
    out["module_summary"] = summary
    return out


def _public_clip_jobs(clip_id: str) -> list[dict[str, Any]]:
    base = CLIPS_ROOT / clip_id
    if not base.exists():
        return []
    jobs: list[dict[str, Any]] = []
    for job_json in base.glob("*/*/job.json"):
        payload = _read_json(job_json)
        if isinstance(payload, dict):
            jobs.append(_public_job(payload))
    jobs.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return jobs


def _list_clip_records(limit: int) -> list[dict[str, Any]]:
    CLIPS_ROOT.mkdir(parents=True, exist_ok=True)
    paths = sorted(CLIPS_ROOT.glob("*/clip.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    records: list[dict[str, Any]] = []
    for path in paths[: max(1, min(limit, 500))]:
        record = _read_json(path)
        if isinstance(record, dict):
            records.append(record)
    return records


def _update_job(job_id: str, **updates: Any) -> None:
    job = _load_job(job_id)
    if job is None:
        return
    job.update(updates)
    _save_job(job)


def _append_job_log(
    job_id: str,
    message: str,
    *,
    stage: str,
    level: str = "info",
    progress_percent: int | None = None,
) -> None:
    job = _load_job(job_id)
    if job is None:
        return
    default_log = LEGACY_JOB_ROOT / job_id / "job_log.jsonl"
    job_dir = job.get("job_dir")
    if job_dir:
        default_log = Path(str(job_dir)) / "job_log.jsonl"
    log_path = Path(str(job.get("log_path") or default_log))
    event: dict[str, Any] = {
        "ts": _now_iso(),
        "level": level,
        "stage": stage,
        "message": message,
    }
    if progress_percent is not None:
        event["progress_percent"] = int(max(0, min(100, progress_percent)))
        job["progress_percent"] = event["progress_percent"]
    job["progress_label"] = message
    job["log_path"] = str(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    _save_job(job)


def _read_job_logs(job: dict[str, Any]) -> list[dict[str, Any]]:
    fallback = LEGACY_JOB_ROOT / str(job["job_id"]) / "job_log.jsonl"
    job_dir = job.get("job_dir")
    if job_dir:
        fallback = Path(str(job_dir)) / "job_log.jsonl"
    log_path = Path(str(job.get("log_path") or fallback))
    if not log_path.exists():
        return []
    logs: list[dict[str, Any]] = []
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                logs.append(payload)
    except (OSError, json.JSONDecodeError):
        return logs
    return logs[-500:]


def _job_elapsed_seconds(job: dict[str, Any]) -> int:
    started_at = _parse_iso_datetime(job.get("started_at"))
    if started_at is None:
        return 0
    completed_at = _parse_iso_datetime(job.get("completed_at"))
    end = completed_at or datetime.now(timezone.utc)
    return max(0, int((end - started_at).total_seconds()))


def _job_progress_percent(job: dict[str, Any]) -> int:
    status = str(job.get("status") or "")
    stored = int(max(0, min(100, int(job.get("progress_percent") or 0))))
    if status in {"done", "partial", "failed"}:
        return 100
    if status == "queued":
        return max(stored, 5)
    if status == "running":
        elapsed = _job_elapsed_seconds(job)
        # Pipeline içi callback yok; kullanıcıya bekleme hissi vermek için 15-92 arası tahmini akar.
        estimated_seconds = max(90, int(float(job.get("size_bytes") or 0) / (12 * 1024 * 1024)) * 60)
        estimated_progress = 15 + int(min(77, (elapsed / estimated_seconds) * 77))
        return max(stored, min(92, estimated_progress))
    return stored


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size_bytes} B"


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "media"
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name or "media"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
