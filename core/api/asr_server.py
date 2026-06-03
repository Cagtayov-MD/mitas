"""ASR-only local API for the MITAS WebUI.

This server intentionally exposes only the ASR workflow. OCR, face, tag, and
logo analysis are not started from here.
"""

from __future__ import annotations

import asyncio
import base64
import ctypes
import sys
import ctypes.wintypes
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import traceback
import tempfile
from typing import Any, Literal
import urllib.error
import urllib.request
from uuid import uuid4
import wave

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from core.api.access import add_mitas_access_gate, is_websocket_authorized
from core.api.live_stt_text import LIVE_STT_INITIAL_PROMPT, repair_live_text
from core.observability import system_events
from core.pipelines.translate.dialect import detect_arabic_variant, normalize_source_variant
from core.pipelines.asr.align import AlignmentMode
from core.pipelines.asr.models import DEFAULT_TRANSCRIBE_PARAMS, FAST_MODEL, ProfileName, load_model
from core.pipelines.asr.normalize import PROJECT_ROOT
from core.pipelines.asr.pipeline import ASR_PIPELINE_VERSION, run_asr_pipeline
from core.pipelines.asr.profiles import ContentProfileName
from core.pipelines.asr.version import get_code_version


JobState = Literal["queued", "running", "done", "partial", "failed"]
LiveSessionState = Literal["ready", "listening", "resolving", "paused", "error"]
DiarizeMode = Literal["auto", "on", "off"]

API_VERSION = "asr-api-v0.1"
# Klip-merkezli hub artik E:\MITAS\Database altinda (Cagatay karari 2026-06):
# yeni/gercek veriler buraya gelir; eski outputs/clips test artiklari terk edildi.
# UI /api/clips bu koku okur. Sunucu restart sonrasi aktif olur.
CLIPS_ROOT = PROJECT_ROOT / "Database"
INCOMING_ROOT = CLIPS_ROOT / "_incoming"
# Legacy roots kept only for reading old development jobs created before the
# clip-centric layout. New uploads always go under CLIPS_ROOT.
LEGACY_UPLOAD_ROOT = PROJECT_ROOT / "outputs" / "webui_uploads"
LEGACY_JOB_ROOT = PROJECT_ROOT / "outputs" / "webui_asr_jobs"
ASR_MODULE_DIR = "asr"
SOURCE_DIR = "source"
TRANSLATIONS_DIR = "translations"
FLOW_QUEUE_ROOT = PROJECT_ROOT / "outputs" / "flow_queue"
FLOW_QUEUE_MEDIA_DIR = FLOW_QUEUE_ROOT / "media"
FLOW_QUEUE_STATE_PATH = FLOW_QUEUE_ROOT / "queue.json"
DELETABLE_GENERATED_MODULES = {"asr", "ocr", "face", "tag"}
GENERATED_MODULE_ALIASES = {
    "asr": "asr",
    "stt": "asr",
    "transcript": "asr",
    "ocr": "ocr",
    "face": "face",
    "yuz": "face",
    "yüz": "face",
    "tag": "tag",
    "tags": "tag",
    "label": "tag",
    "labels": "tag",
    "etiket": "tag",
    "visual_tag": "tag",
}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024 * 1024
LIVE_STT_SAMPLE_RATE = 16_000
LIVE_STT_MAX_CHUNK_BYTES = LIVE_STT_SAMPLE_RATE * 2 * 15
TRANSLATE_PYTHON = PROJECT_ROOT / "venvs" / "translate" / "Scripts" / "python.exe"
TRANSLATE_API_SCRIPT = PROJECT_ROOT / "scripts" / "translate_api_call.py"
TRANSLATE_TIMEOUT_SECONDS = 600
SUMMARY_TIMEOUT_SECONDS = 90
SUMMARY_MAX_SOURCE_CHARS = 60000
SUMMARY_MAX_TOKENS = 1500
TURKISH_SUMMARY_STOPWORDS = {
    "acaba", "ama", "ancak", "artık", "aslında", "az", "bazı", "belki", "ben", "beni", "benim", "beri",
    "bir", "biraz", "birçok", "biz", "bizim", "bu", "buna", "bunu", "burada", "böyle", "çok", "çünkü",
    "daha", "da", "de", "değil", "diye", "en", "gibi", "hem", "hep", "her", "hiç", "ile", "için",
    "ise", "işte", "kadar", "ki", "mı", "mi", "mu", "mü", "nasıl", "ne", "neden", "olarak", "olan",
    "oldu", "oluyor", "sonra", "şimdi", "şu", "ve", "veya", "ya", "yani", "yine",
}

app = FastAPI(title="MITAS ASR API", version=API_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
add_mitas_access_gate(app)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mitas-asr")
_live_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mitas-stt-live")
_translate_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mitas-translate")

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
MITAS_PIPELINE = SCRIPTS_DIR / "mitas_pipeline.py"
_pipeline_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mitas-pipeline")
PIPELINE_PROFILE_MAP: dict[str, str] = {
    "film_dizi": "film_dizi",
    "documentary": "belgesel",
    "music_entertainment": "muzik",
    "studio": "studio",
    "sports": "spor",
    "news": "haber",
    "stt": "stt",
}
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_media_remux_lock = threading.Lock()

import logging as _logging
_server_logger = _logging.getLogger("mitas.asr.server")


@app.on_event("startup")
async def _log_startup_version() -> None:
    _server_logger.info(
        "MITAS ASR server started: code_version=%s pipeline_version=%s",
        get_code_version(),
        ASR_PIPELINE_VERSION,
    )


@app.get("/version")
def get_version() -> dict[str, Any]:
    """Return the running server's code and pipeline versions."""
    return {
        "code_version": get_code_version(),
        "pipeline_version": ASR_PIPELINE_VERSION,
    }


@app.get("/api/flow-queue")
def get_flow_queue() -> dict[str, Any]:
    state = _read_json(FLOW_QUEUE_STATE_PATH)
    if isinstance(state, dict):
        return state
    raise HTTPException(status_code=404, detail="flow_queue_not_found")


@app.put("/api/flow-queue")
async def put_flow_queue(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid_json") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid_payload")
    state = {
        "id": "main",
        "updatedAt": _now_iso(),
        "bulkProfile": payload.get("bulkProfile") or "stt",
        "items": payload.get("items") if isinstance(payload.get("items"), list) else [],
    }
    _write_json(FLOW_QUEUE_STATE_PATH, state)
    return state


@app.post("/api/flow-queue/uploads/{item_id}")
async def put_flow_queue_upload(item_id: str, request: Request, filename: str = Query(default="media")) -> dict[str, Any]:
    safe_item_id = _safe_artifact_id(item_id)
    safe_name = _safe_filename(filename)
    item_dir = FLOW_QUEUE_MEDIA_DIR / safe_item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    staging_path = item_dir / f"{uuid4().hex}.upload"
    size, content_hash = await _write_request_body(request, staging_path)
    if size == 0:
        staging_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="empty_upload")
    target_path = item_dir / safe_name
    if target_path.exists():
        target_path.unlink()
    shutil.move(str(staging_path), str(target_path))
    return {
        "item_id": safe_item_id,
        "filename": safe_name,
        "size_bytes": size,
        "content_hash": content_hash,
        "stored_media_url": f"/api/flow-queue/uploads/{safe_item_id}/media",
        "stored_media_path": str(target_path),
    }


@app.get("/api/flow-queue/uploads/{item_id}/media")
def get_flow_queue_upload_media(item_id: str) -> FileResponse:
    safe_item_id = _safe_artifact_id(item_id)
    item_dir = FLOW_QUEUE_MEDIA_DIR / safe_item_id
    if not item_dir.exists():
        raise HTTPException(status_code=404, detail="queue_media_not_found")
    files = [path for path in item_dir.iterdir() if path.is_file()]
    if not files:
        raise HTTPException(status_code=404, detail="queue_media_not_found")
    media_path = max(files, key=lambda path: path.stat().st_mtime)
    return FileResponse(
        media_path,
        media_type=mimetypes.guess_type(media_path.name)[0] or "application/octet-stream",
        filename=media_path.name,
    )


# ---------------------------------------------------------------------------
# System resource monitor — polls every 5 s in a daemon thread
# ---------------------------------------------------------------------------
class _MEMSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength",               ctypes.wintypes.DWORD),
        ("dwMemoryLoad",           ctypes.wintypes.DWORD),
        ("ullTotalPhys",           ctypes.c_uint64),
        ("ullAvailPhys",           ctypes.c_uint64),
        ("ullTotalPageFile",       ctypes.c_uint64),
        ("ullAvailPageFile",       ctypes.c_uint64),
        ("ullTotalVirtual",        ctypes.c_uint64),
        ("ullAvailVirtual",        ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]

def _ram_percent() -> int:
    """Instant RAM read via Windows kernel API — no subprocess needed."""
    try:
        stat = _MEMSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return int(stat.dwMemoryLoad)
    except Exception:
        return -1

_NO_WIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def _cpu_percent() -> int:
    # 1) typeperf — fastest Windows perf counter reader, always available
    try:
        r = subprocess.run(
            ["typeperf", r"\Processor(_Total)\% Processor Time", "-sc", "1"],
            capture_output=True, text=True, timeout=6, creationflags=_NO_WIN,
        )
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines()[1:]:
                parts = line.split(",")
                if len(parts) >= 2:
                    try:
                        return round(float(parts[-1].strip().strip('"')))
                    except ValueError:
                        pass
    except Exception:
        pass
    # 2) wmic (plain, no /format:value — more portable across Win versions)
    try:
        r = subprocess.run(
            ["wmic", "cpu", "get", "LoadPercentage"],
            capture_output=True, text=True, timeout=5, creationflags=_NO_WIN,
        )
        for line in r.stdout.strip().splitlines():
            stripped = line.strip()
            if stripped.isdigit():
                return int(stripped)
    except Exception:
        pass
    # 3) PowerShell last resort
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "(Get-CimInstance Win32_Processor).LoadPercentage"],
            capture_output=True, text=True, timeout=10, creationflags=_NO_WIN,
        )
        val = r.stdout.strip()
        if r.returncode == 0 and val.isdigit():
            return int(val)
    except Exception:
        pass
    return -1

_NVIDIA_SMI_PATHS = [
    "nvidia-smi",
    r"C:\Windows\System32\nvidia-smi.exe",
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
]

def _gpu_percent() -> int:
    for cmd in _NVIDIA_SMI_PATHS:
        try:
            r = subprocess.run(
                [cmd, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, creationflags=_NO_WIN,
            )
            if r.returncode == 0:
                val = r.stdout.strip().splitlines()[0].strip()
                if val.isdigit():
                    return int(val)
                return -1
        except FileNotFoundError:
            continue
        except Exception:
            return -1
    return -1

_sysinfo_cache: dict[str, int] = {"cpu": -1, "gpu": -1}
_sysinfo_lock = threading.Lock()

def _sysinfo_worker() -> None:
    while True:
        cpu = _cpu_percent()
        gpu = _gpu_percent()
        with _sysinfo_lock:
            _sysinfo_cache.update({"cpu": cpu, "gpu": gpu})
        time.sleep(5)

threading.Thread(target=_sysinfo_worker, daemon=True, name="sysinfo-poller").start()

@app.get("/api/sysinfo")
def get_sysinfo() -> dict[str, int]:
    with _sysinfo_lock:
        result = dict(_sysinfo_cache)
    result["ram"] = _ram_percent()   # always fresh — ctypes call is instant
    return result


@app.post("/api/restart")
def restart_server() -> dict[str, str]:
    """Replace the current process with a fresh uvicorn instance."""
    def _restart_argv() -> list[str]:
        argv = list(sys.argv)
        scripts_dir = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
        uvicorn_exe = scripts_dir / ("uvicorn.exe" if os.name == "nt" else "uvicorn")

        if argv:
            first = Path(argv[0])
            launched_with_uvicorn_module = first.name == "__main__.py" and first.parent.name == "uvicorn"
            launched_with_uvicorn_exe = first.name.lower() in {"uvicorn", "uvicorn.exe"}
            if uvicorn_exe.exists() and (launched_with_uvicorn_module or launched_with_uvicorn_exe):
                return [str(uvicorn_exe), *argv[1:]]

        return [sys.executable, *argv]

    def _do_restart() -> None:
        time.sleep(0.4)
        os.chdir(PROJECT_ROOT)
        argv = _restart_argv()
        os.execv(argv[0], argv)
    threading.Thread(target=_do_restart, daemon=True, name="restart").start()
    return {"status": "restarting"}


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
    profile: ProfileName | None = Query(default=None),
    content_profile: ContentProfileName | None = Query(default="bulten_haber"),
    diarize: DiarizeMode = Query(default="auto"),
    channel_mode: Literal["mono", "split", "auto"] = Query(default="auto"),
    word_alignment_mode: AlignmentMode = Query(default="whisperx"),
    force: Literal["none", "full"] = Query(default="none"),
    original_source_path: str | None = Query(default=None),
    ocr: Literal["auto", "off"] = Query(default="off"),
) -> dict[str, Any]:
    """Store uploaded media and start an ASR job in the background.

    Dedup: if an existing clip has the same sha256 content hash, the upload
    is reused (no new clip, no new ASR run) unless ``force=full`` is set.
    ``force=full`` attaches a fresh ASR job under the existing clip.
    """
    job_id = f"asr-{uuid4().hex[:12]}"
    safe_name = _safe_filename(filename)
    media_id = Path(safe_name).stem or "media"
    staging_path = INCOMING_ROOT / f"{job_id}.bin"

    size, content_hash = await _write_request_body(request, staging_path)
    if size == 0:
        staging_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="empty_upload")

    existing_clip = _find_clip_by_hash(content_hash)
    existing_asr_job_id = _clip_latest_module_job_id(existing_clip, ASR_MODULE_DIR) if existing_clip is not None else None

    if existing_clip is not None and force != "full" and existing_asr_job_id:
        staging_path.unlink(missing_ok=True)
        return _build_reused_response(existing_clip, content_hash=content_hash)

    if existing_clip is not None:
        clip_id = str(existing_clip["clip_id"])
        clip_dir = CLIPS_ROOT / clip_id
        source_dir = clip_dir / SOURCE_DIR
        input_path = Path(str(existing_clip.get("source_path") or (source_dir / safe_name)))
        previous_job_id = (
            (existing_clip.get("modules") or {})
            .get("asr", {})
            .get("latest_job_id")
        )
        staging_path.unlink(missing_ok=True)
        reprocessed = True
    else:
        clip_id = _allocate_clip_id(media_id)
        clip_dir = CLIPS_ROOT / clip_id
        source_dir = clip_dir / SOURCE_DIR
        source_dir.mkdir(parents=True, exist_ok=True)
        input_path = source_dir / safe_name
        shutil.move(str(staging_path), str(input_path))
        previous_job_id = None
        reprocessed = False

    job_dir = clip_dir / ASR_MODULE_DIR / job_id
    run_dir = job_dir / "run"
    job_dir.mkdir(parents=True, exist_ok=True)

    _ensure_clip_record(
        clip_id=clip_id,
        filename=safe_name,
        media_id=media_id,
        size_bytes=size,
        source_path=input_path,
        content_hash=content_hash,
    )

    job = {
        "job_id": job_id,
        "clip_id": clip_id,
        "media_id": media_id,
        "content_hash": content_hash,
        "status": "queued",
        "filename": safe_name,
        "input_path": str(input_path),
        "output_dir": str(run_dir),
        "job_dir": str(job_dir),
        "clip_dir": str(clip_dir),
        "module": "asr",
        "profile": profile or "fast_with_fallback",
        "model_profile_override": profile,
        "content_profile": content_profile,
        "diarize": diarize,
        "channel_mode": channel_mode,
        "word_alignment_mode": word_alignment_mode,
        "ocr_intent": ocr,
        "size_bytes": size,
        "reprocessed": reprocessed,
        "previous_job_id": previous_job_id,
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
        "message": "ASR işi kuyruğa alındı.",
        "error": None,
        "original_source_path": original_source_path,
        "progress_percent": 0,
        "progress_label": "Kuyrukta",
        "log_path": str(job_dir / "job_log.jsonl"),
    }
    _save_job(job)
    _attach_job_to_clip(clip_id, module=ASR_MODULE_DIR, job_id=job_id)
    _append_job_log(job_id, "Medya yüklendi.", stage="upload", progress_percent=3)
    _append_job_log(job_id, "ASR işi kuyruğa alındı.", stage="queued", progress_percent=5)
    if reprocessed:
        system_events.log_event(
            "asr_reprocess_started",
            summary=f"{safe_name} için ASR tekrar işleniyor (force=full).",
            module="asr",
            media_id=media_id,
            filename=safe_name,
            job_id=job_id,
            detail={
                "clip_id": clip_id,
                "previous_job_id": previous_job_id,
                "profile": profile,
                "content_profile": content_profile,
                "diarize": diarize,
                "word_alignment_mode": word_alignment_mode,
            },
        )
    else:
        system_events.log_event(
            "media_imported",
            summary=f"{safe_name} içe aktarıldı ({_format_size(size)}).",
            module="upload",
            media_id=media_id,
            filename=safe_name,
            job_id=job_id,
            detail={
                "clip_id": clip_id,
                "size_bytes": size,
                "profile": profile,
                "content_profile": content_profile,
                "diarize": diarize,
                "channel_mode": channel_mode,
                "word_alignment_mode": word_alignment_mode,
            },
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
    response = _public_job(_load_job(job_id) or job)
    response["reused"] = False
    response["content_hash"] = content_hash
    return response


@app.post("/api/clips/prepare")
async def prepare_clip(
    request: Request,
    filename: str = Query(default="media"),
    original_source_path: str | None = Query(default=None),
) -> dict[str, Any]:
    """Store an uploaded file as a clip (dedup-aware) without starting any job.

    Returns clip metadata including ``clip_id``.  Use this to obtain a
    ``clip_id`` before calling a range-ASR endpoint when no prior job exists.
    """
    safe_name = _safe_filename(filename)
    media_id = Path(safe_name).stem or "media"
    job_id = f"prep-{uuid4().hex[:12]}"
    staging_path = INCOMING_ROOT / f"{job_id}.bin"

    size, content_hash = await _write_request_body(request, staging_path)
    if size == 0:
        staging_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="empty_upload")

    existing_clip = _find_clip_by_hash(content_hash)
    if existing_clip is not None:
        staging_path.unlink(missing_ok=True)
        return _public_clip(existing_clip)

    clip_id = _allocate_clip_id(media_id)
    clip_dir = CLIPS_ROOT / clip_id
    source_dir = clip_dir / SOURCE_DIR
    source_dir.mkdir(parents=True, exist_ok=True)
    input_path = source_dir / safe_name
    shutil.move(str(staging_path), str(input_path))

    _ensure_clip_record(
        clip_id=clip_id,
        filename=safe_name,
        media_id=media_id,
        size_bytes=size,
        source_path=input_path,
        content_hash=content_hash,
    )
    record = _load_clip_record(clip_id) or {}
    if original_source_path:
        record["original_source_path"] = original_source_path
    return _public_clip(record)


@app.post("/api/pipeline/run")
async def create_pipeline_job(
    request: Request,
    filename: str = Query(default="media"),
    profile: str = Query(default="film_dizi"),
) -> dict[str, Any]:
    """Store uploaded media and start a full MITAS pipeline job in the background.

    Only künye-producing profiles (film_dizi, documentary, music_entertainment, studio)
    should be routed here. The ASR-only path is untouched.
    """
    job_id = f"pipe-{uuid4().hex[:12]}"
    safe_name = _safe_filename(filename)
    job_incoming_dir = INCOMING_ROOT / job_id
    job_incoming_dir.mkdir(parents=True, exist_ok=True)
    # Write to a staging path then rename to keep the real filename
    staging_path = job_incoming_dir / f"{job_id}.bin"

    size, _content_hash = await _write_request_body(request, staging_path)
    if size == 0:
        staging_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="empty_upload")

    input_path = job_incoming_dir / safe_name
    if input_path.exists():
        input_path.unlink()
    shutil.move(str(staging_path), str(input_path))

    pipeline_profile = PIPELINE_PROFILE_MAP.get(profile, "film_dizi")
    job_log_path = job_incoming_dir / "job_log.jsonl"
    job: dict[str, Any] = {
        "job_id": job_id,
        "module": "pipeline",
        "status": "queued",
        "clip_id": None,
        "analysis_profile": profile,
        "pipeline_profile": pipeline_profile,
        "filename": safe_name,
        "input_path": str(input_path),
        "size_bytes": size,
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
        "message": "Pipeline işi kuyruğa alındı.",
        "error": None,
        "progress_percent": 0,
        "progress_label": "Kuyrukta",
        "log_path": str(job_log_path),
        # Pipeline-specific output fields (populated by worker)
        "karar": None,
        "neden": None,
        "hub": None,
        "teslim": None,
        "pdf_path": None,
        # output_dir placeholder so _public_job can safely skip artifact reads
        "output_dir": str(job_incoming_dir),
        "job_dir": str(job_incoming_dir),
    }
    _save_job(job)
    _append_job_log(job_id, "Medya yüklendi.", stage="upload", progress_percent=3)
    _append_job_log(job_id, "Pipeline işi kuyruğa alındı.", stage="queued", progress_percent=5)
    system_events.log_event(
        "media_imported",
        summary=f"{safe_name} pipeline için içe aktarıldı ({_format_size(size)}).",
        module="pipeline",
        filename=safe_name,
        job_id=job_id,
        detail={
            "size_bytes": size,
            "analysis_profile": profile,
            "pipeline_profile": pipeline_profile,
        },
    )
    _pipeline_executor.submit(_run_pipeline_job, job_id)
    response = _public_job(_load_job(job_id) or job)
    response["reused"] = False
    return response


def _run_pipeline_job(job_id: str) -> None:
    job = _load_job(job_id)
    if job is None:
        return

    filename = str(job.get("filename") or "")
    _append_job_log(job_id, "Pipeline worker başladı.", stage="worker", progress_percent=8)
    _update_job(
        job_id,
        status="running",
        started_at=_now_iso(),
        message="MITAS pipeline çalışıyor.",
        progress_percent=10,
        progress_label="Pipeline çalışıyor",
    )
    try:
        cmd = [
            sys.executable,
            str(MITAS_PIPELINE),
            "--video", job["input_path"],
            "--profile", job["pipeline_profile"],
        ]
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
            timeout=14400,
            check=False,
        )
        # Parse the last stdout line that starts with '{'
        result: dict[str, Any] | None = None
        for line in reversed(completed.stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                except json.JSONDecodeError:
                    pass
                else:
                    break

        if completed.returncode != 0 or result is None:
            tail = (completed.stderr or completed.stdout or "pipeline_failed")[-800:]
            raise RuntimeError(tail)

        hub = result.get("hub")
        clip_id = Path(hub).name if hub else None
        karar = result.get("karar")
        neden = result.get("neden")

        status: JobState
        if karar == "Hazır":
            status = "done"
        elif karar == "Kontrol":
            status = "partial"
        else:
            status = "done"

        # Read _DURUM.json for pdf and teslim paths
        pdf_path: str | None = None
        teslim: str | None = result.get("teslim")
        if hub:
            durum = _read_json(Path(hub) / "_DURUM.json")
            if isinstance(durum, dict):
                pdf_path = str(durum.get("pdf") or "") or None
                teslim = str(durum.get("teslim") or teslim or "") or teslim

        _update_job(
            job_id,
            status=status,
            completed_at=_now_iso(),
            clip_id=clip_id,
            message=f"Pipeline tamamlandı: {karar}." if karar else "Pipeline tamamlandı.",
            progress_percent=100,
            progress_label="Tamamlandı" if status == "done" else "Kontrol gerekli",
            karar=karar,
            neden=neden,
            hub=hub,
            teslim=teslim,
            pdf_path=pdf_path,
        )
        _append_job_log(
            job_id,
            f"Pipeline tamamlandı: {karar}." if karar else "Pipeline tamamlandı.",
            stage=status,
            progress_percent=100,
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(
            job_id,
            status="failed",
            completed_at=_now_iso(),
            message="Pipeline başarısız oldu.",
            error=str(exc),
            progress_percent=100,
            progress_label="Hata",
        )
        _append_job_log(
            job_id,
            f"Pipeline başarısız oldu: {exc}",
            stage="failed",
            level="error",
            progress_percent=100,
        )
        system_events.log_event(
            "pipeline_failed",
            summary=f"{filename or job_id} için pipeline başarısız oldu.",
            level="error",
            module="pipeline",
            filename=filename or None,
            job_id=job_id,
            error=str(exc),
        )


def _build_reused_response(existing_clip: dict[str, Any], *, content_hash: str) -> dict[str, Any]:
    """Build the API response for a duplicate upload that reuses an existing clip.

    Keep the response job-compatible when a latest ASR job exists. The WebUI
    upload path expects a ``job_id`` and can keep polling/opening transcripts
    without special-casing duplicate media.
    """
    clip_id = str(existing_clip["clip_id"])
    filename = str(existing_clip.get("filename") or "")
    media_id = str(existing_clip.get("media_id") or "")
    asr_state = (existing_clip.get("modules") or {}).get("asr") or {}
    latest_asr_job_id = asr_state.get("latest_job_id")
    asr_status = asr_state.get("status")
    latest_job = _load_job(str(latest_asr_job_id)) if latest_asr_job_id else None
    clip_payload = _public_clip(existing_clip)
    pub = _public_job(latest_job) if latest_job is not None else clip_payload
    pub.update(
        {
            "reused": True,
            "content_hash": content_hash,
            "latest_asr_job_id": latest_asr_job_id,
            "asr_status": asr_status or pub.get("status"),
            "message": "Bu klip daha önce işlenmiş, mevcut transkript kullanılıyor.",
            "module_summary": clip_payload.get("module_summary", {}),
            "reprocess_url": f"/api/asr/transcribe?filename={filename}&force=full",
        }
    )
    system_events.log_event(
        "media_reused",
        summary=f"{filename or media_id or clip_id} daha önce işlenmiş, mevcut transkript kullanılıyor.",
        module="upload",
        media_id=media_id or None,
        filename=filename or None,
        job_id=latest_asr_job_id,
        detail={"clip_id": clip_id, "content_hash": content_hash, "latest_asr_job_id": latest_asr_job_id, "asr_status": asr_status},
    )
    return pub


@app.get("/api/jobs")
def list_jobs(
    limit: int = Query(default=20, ge=1, le=500),
    compact: bool = Query(default=False),
    q: str | None = Query(default=None),
) -> dict[str, Any]:
    """List recent ASR jobs."""
    search_query = (q or "").strip()
    if compact:
        jobs = [_public_job_summary(job, search_query=search_query) for job in _load_recent_jobs(limit, search_query=search_query)]
    else:
        jobs = [_public_job(job) for job in _load_recent_jobs(limit, search_query=search_query)]
        if search_query:
            for job in jobs:
                match = _job_search_match(job, search_query)
                if match:
                    job["search_match"] = match
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    """Return job status and ASR artifacts when available."""
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return _public_job(job)


@app.post("/api/jobs/{job_id}/transcript-summary")
async def summarize_job_transcript(
    job_id: str,
    force: bool = Query(default=False),
) -> dict[str, Any]:
    """Generate or return the persisted human-readable transcript summary."""
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    public_job = _public_job(job)
    transcript = str(public_job.get("transcript") or "").strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="transcript_empty")

    summary_path = _transcript_summary_path(public_job)
    if summary_path.exists() and not force:
        cached = _read_json(summary_path)
        if isinstance(cached, dict):
            return cached

    started = datetime.now(timezone.utc)
    loop = asyncio.get_running_loop()
    try:
        summary = await loop.run_in_executor(_translate_executor, _generate_transcript_summary, public_job, transcript)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    payload = {
        "job_id": job_id,
        "filename": public_job.get("filename"),
        "created_at": _now_iso(),
        "elapsed_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 3),
        **summary,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    job["transcript_summary_path"] = str(summary_path)
    _save_job(job)
    system_events.log_event(
        "transcript_summary_completed",
        summary=f"{public_job.get('filename') or job_id} için transcript özeti üretildi.",
        module="summary",
        media_id=str(public_job.get("media_id") or "") or None,
        filename=str(public_job.get("filename") or "") or None,
        job_id=job_id,
        duration_seconds=payload["elapsed_seconds"],
        detail={"model": payload.get("model"), "provider": payload.get("provider")},
    )
    return payload


@app.get("/api/jobs/{job_id}/media")
def get_job_media(job_id: str) -> FileResponse:
    """Stream the original media for a persisted ASR job."""
    job = _load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    raw_path = job.get("input_path")
    if not raw_path:
        raise HTTPException(status_code=404, detail="media_not_found")
    media_path = Path(str(raw_path)).resolve()
    allowed_roots = [CLIPS_ROOT.resolve(), LEGACY_UPLOAD_ROOT.resolve()]
    if not any(_is_path_under(media_path, root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="media_path_not_allowed")
    if not media_path.exists() or not media_path.is_file():
        raise HTTPException(status_code=404, detail="media_not_found")
    media_path = _playback_media_path(media_path)
    media_type, _ = mimetypes.guess_type(str(media_path))
    return FileResponse(
        media_path,
        media_type=media_type or "application/octet-stream",
        filename=str(job.get("filename") or media_path.name),
        content_disposition_type="inline",
    )


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


@app.get("/api/clips/{clip_id}/media")
def get_clip_media(clip_id: str) -> FileResponse:
    """Stream the clip source media independently of any generated module data."""
    safe_clip_id = _safe_artifact_id(clip_id)
    record = _load_clip_record(safe_clip_id)
    if record is None:
        raise HTTPException(status_code=404, detail="clip_not_found")
    media_path = _clip_source_media_path(safe_clip_id, record)
    media_path = _playback_media_path(media_path)
    media_type, _ = mimetypes.guess_type(str(media_path))
    return FileResponse(
        media_path,
        media_type=media_type or "application/octet-stream",
        filename=str(record.get("filename") or media_path.name),
        content_disposition_type="inline",
    )


@app.delete("/api/clips/{clip_id}/modules/{module}")
def delete_clip_generated_module(
    clip_id: str,
    module: str,
    allow_running: bool = Query(default=False),
) -> dict[str, Any]:
    """Permanently remove generated data for one clip module while preserving source media."""
    safe_clip_id = _safe_artifact_id(clip_id)
    canonical_module = _normalize_generated_data_module(module)
    record = _load_clip_record(safe_clip_id)
    if record is None:
        raise HTTPException(status_code=404, detail="clip_not_found")

    module_state = (record.get("modules") or {}).get(canonical_module)
    job_ids = _module_job_ids(module_state)
    if not allow_running:
        active_job_id = _first_active_job_id(job_ids)
        if active_job_id:
            raise HTTPException(status_code=409, detail=f"module_job_running:{active_job_id}")

    clip_dir = (CLIPS_ROOT / safe_clip_id).resolve()
    module_dir = (clip_dir / canonical_module).resolve()
    if not _is_path_under(module_dir, clip_dir):
        raise HTTPException(status_code=403, detail="module_path_not_allowed")

    artifacts_deleted = False
    if module_dir.exists():
        shutil.rmtree(module_dir)
        artifacts_deleted = True

    modules = record.setdefault("modules", {})
    module_record_deleted = canonical_module in modules
    modules.pop(canonical_module, None)
    record["updated_at"] = _now_iso()
    _write_json(_clip_record_path(safe_clip_id), record)

    with _jobs_lock:
        for job_id in job_ids:
            _jobs.pop(job_id, None)

    system_events.log_event(
        "generated_data_deleted",
        summary=f"{record.get('filename') or safe_clip_id} için {canonical_module.upper()} verisi kalıcı silindi.",
        module=canonical_module,
        media_id=str(record.get("media_id") or "") or None,
        filename=str(record.get("filename") or "") or None,
        detail={
            "clip_id": safe_clip_id,
            "requested_module": module,
            "deleted_job_ids": job_ids,
            "artifacts_deleted": artifacts_deleted,
            "module_record_deleted": module_record_deleted,
        },
    )
    return {
        "clip_id": safe_clip_id,
        "module": canonical_module,
        "requested_module": module,
        "deleted": artifacts_deleted or module_record_deleted,
        "artifacts_deleted": artifacts_deleted,
        "module_record_deleted": module_record_deleted,
        "deleted_job_ids": job_ids,
    }


@app.post("/api/clips/{clip_id}/modules/asr/reprocess")
def reprocess_clip_asr(
    clip_id: str,
    profile: ProfileName | None = Query(default=None),
    content_profile: ContentProfileName | None = Query(default="bulten_haber"),
    diarize: DiarizeMode = Query(default="auto"),
    channel_mode: Literal["mono", "split", "auto"] = Query(default="auto"),
    word_alignment_mode: AlignmentMode = Query(default="whisperx"),
) -> dict[str, Any]:
    """Start a fresh ASR job from a clip's preserved source media."""
    safe_clip_id = _safe_artifact_id(clip_id)
    record = _load_clip_record(safe_clip_id)
    if record is None:
        raise HTTPException(status_code=404, detail="clip_not_found")

    input_path = _clip_source_media_path(safe_clip_id, record)
    content_hash = str(record.get("content_hash") or _hash_file(input_path))
    size = int(record.get("size_bytes") or input_path.stat().st_size)
    filename = _safe_filename(str(record.get("filename") or input_path.name))
    media_id = str(record.get("media_id") or Path(filename).stem or safe_clip_id)
    previous_job_id = _clip_latest_module_job_id(record, ASR_MODULE_DIR)
    job_id = f"asr-{uuid4().hex[:12]}"
    clip_dir = CLIPS_ROOT / safe_clip_id
    job_dir = clip_dir / ASR_MODULE_DIR / job_id
    run_dir = job_dir / "run"
    job_dir.mkdir(parents=True, exist_ok=True)

    _ensure_clip_record(
        clip_id=safe_clip_id,
        filename=filename,
        media_id=media_id,
        size_bytes=size,
        source_path=input_path,
        content_hash=content_hash,
    )
    job = {
        "job_id": job_id,
        "clip_id": safe_clip_id,
        "media_id": media_id,
        "content_hash": content_hash,
        "status": "queued",
        "filename": filename,
        "input_path": str(input_path),
        "output_dir": str(run_dir),
        "job_dir": str(job_dir),
        "clip_dir": str(clip_dir),
        "module": "asr",
        "profile": profile or "fast_with_fallback",
        "model_profile_override": profile,
        "content_profile": content_profile,
        "diarize": diarize,
        "channel_mode": channel_mode,
        "word_alignment_mode": word_alignment_mode,
        "size_bytes": size,
        "reprocessed": True,
        "previous_job_id": previous_job_id,
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
        "message": "ASR tekrar işi kuyruğa alındı.",
        "error": None,
        "original_source_path": str(record.get("source_path") or ""),
        "progress_percent": 0,
        "progress_label": "Kuyrukta",
        "log_path": str(job_dir / "job_log.jsonl"),
    }
    _save_job(job)
    _attach_job_to_clip(safe_clip_id, module=ASR_MODULE_DIR, job_id=job_id)
    _append_job_log(job_id, "ASR tekrar işi kuyruğa alındı.", stage="queued", progress_percent=5)
    system_events.log_event(
        "asr_reprocess_started",
        summary=f"{filename} için ASR tekrar işleniyor.",
        module="asr",
        media_id=media_id,
        filename=filename,
        job_id=job_id,
        detail={
            "clip_id": safe_clip_id,
            "previous_job_id": previous_job_id,
            "profile": profile,
            "content_profile": content_profile,
            "diarize": diarize,
            "channel_mode": channel_mode,
            "word_alignment_mode": word_alignment_mode,
        },
    )
    _executor.submit(_run_job, job_id)
    response = _public_job(_load_job(job_id) or job)
    response["reused"] = False
    response["content_hash"] = content_hash
    return response


@app.post("/api/clips/{clip_id}/modules/asr/range")
def process_clip_asr_range(
    clip_id: str,
    start_seconds: float = Query(ge=0),
    end_seconds: float = Query(gt=0),
    profile: ProfileName | None = Query(default=None),
    content_profile: ContentProfileName | None = Query(default="bulten_haber"),
    diarize: DiarizeMode = Query(default="auto"),
    channel_mode: Literal["mono", "split", "auto"] = Query(default="auto"),
    word_alignment_mode: AlignmentMode = Query(default="whisperx"),
) -> dict[str, Any]:
    """Start a fresh ASR job from a bounded time range of a preserved clip."""
    safe_clip_id = _safe_artifact_id(clip_id)
    record = _load_clip_record(safe_clip_id)
    if record is None:
        raise HTTPException(status_code=404, detail="clip_not_found")
    if end_seconds <= start_seconds:
        raise HTTPException(status_code=400, detail="invalid_range")

    source_path = _clip_source_media_path(safe_clip_id, record)
    source_filename = _safe_filename(str(record.get("filename") or source_path.name))
    media_id = str(record.get("media_id") or Path(source_filename).stem or safe_clip_id)
    previous_job_id = _clip_latest_module_job_id(record, ASR_MODULE_DIR)
    job_id = f"asr-{uuid4().hex[:12]}"
    clip_dir = CLIPS_ROOT / safe_clip_id
    job_dir = clip_dir / ASR_MODULE_DIR / job_id
    run_dir = job_dir / "run"
    job_dir.mkdir(parents=True, exist_ok=True)

    range_suffix = _range_media_suffix(source_path)
    range_filename = _safe_filename(
        f"{Path(source_filename).stem}_{_range_token(start_seconds)}_{_range_token(end_seconds)}{range_suffix}"
    )
    range_path = job_dir / "source" / range_filename
    try:
        _trim_media_range(source_path, range_path, start_seconds=start_seconds, end_seconds=end_seconds)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    content_hash = _hash_file(range_path)
    size = range_path.stat().st_size
    job = {
        "job_id": job_id,
        "clip_id": safe_clip_id,
        "media_id": media_id,
        "content_hash": content_hash,
        "status": "queued",
        "filename": range_filename,
        "input_path": str(range_path),
        "output_dir": str(run_dir),
        "job_dir": str(job_dir),
        "clip_dir": str(clip_dir),
        "module": "asr",
        "profile": profile or "fast_with_fallback",
        "model_profile_override": profile,
        "content_profile": content_profile,
        "diarize": diarize,
        "channel_mode": channel_mode,
        "word_alignment_mode": word_alignment_mode,
        "size_bytes": size,
        "reprocessed": True,
        "previous_job_id": previous_job_id,
        "range_source_path": str(source_path),
        "range_start_seconds": start_seconds,
        "range_end_seconds": end_seconds,
        "created_at": _now_iso(),
        "started_at": None,
        "completed_at": None,
        "message": "Aralık ASR işi kuyruğa alındı.",
        "error": None,
        "original_source_path": str(record.get("source_path") or source_path),
        "progress_percent": 0,
        "progress_label": "Kuyrukta",
        "log_path": str(job_dir / "job_log.jsonl"),
    }
    _save_job(job)
    _attach_job_to_clip(safe_clip_id, module=ASR_MODULE_DIR, job_id=job_id)
    _append_job_log(
        job_id,
        f"Aralık ASR işi kuyruğa alındı: {start_seconds:.3f}-{end_seconds:.3f}s.",
        stage="queued",
        progress_percent=5,
    )
    system_events.log_event(
        "asr_range_started",
        summary=f"{source_filename} için {start_seconds:.1f}-{end_seconds:.1f}s aralığında ASR kuyruğa alındı.",
        module="asr",
        media_id=media_id,
        filename=source_filename,
        job_id=job_id,
        detail={
            "clip_id": safe_clip_id,
            "previous_job_id": previous_job_id,
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "profile": profile,
            "content_profile": content_profile,
            "channel_mode": channel_mode,
            "word_alignment_mode": word_alignment_mode,
        },
    )
    _executor.submit(_run_job, job_id)
    response = _public_job(_load_job(job_id) or job)
    response["reused"] = False
    response["content_hash"] = content_hash
    return response


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
    if not is_websocket_authorized(websocket):
        await websocket.close(code=1008)
        return
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
        detail={
            "clip_id": clip_id,
            "profile": job.get("profile"),
            "model_profile_override": job.get("model_profile_override"),
            "content_profile": job.get("content_profile"),
            "diarize": job.get("diarize"),
            "channel_mode": job.get("channel_mode"),
            "word_alignment_mode": job.get("word_alignment_mode"),
        },
    )
    try:
        content_profile = job.get("content_profile") or None
        model_profile_override = job.get("model_profile_override") or None
        result = run_asr_pipeline(
            job["input_path"],
            content_profile=content_profile,
            profile=None if content_profile else model_profile_override,
            model_profile_override=model_profile_override if content_profile else None,
            diarize_override=_diarize_override(job.get("diarize")),
            channel_mode=job["channel_mode"],
            word_alignment_mode=job.get("word_alignment_mode") or "whisperx",
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


def _diarize_override(value: Any) -> bool | None:
    mode = str(value or "auto").strip().lower()
    if mode == "on":
        return True
    if mode == "off":
        return False
    return None


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
        source_lang = _normalize_translate_source_lang(raw_item.get("source_lang"), source_text=source_text)
        source_variant = _normalize_translate_source_variant(
            raw_item.get("source_variant"),
            source_lang=source_lang,
            source_text=source_text,
        )
        if not segment_id:
            raise ValueError(f"items[{index}].segment_id is required")
        if not source_text:
            raise ValueError(f"items[{index}].source_text is required")
        if source_lang is None:
            raise ValueError(f"items[{index}].source_lang is required")
        item = {
            "segment_id": segment_id,
            "source_text": source_text,
            "source_lang": source_lang,
        }
        if source_variant:
            item["source_variant"] = source_variant
        items.append(item)

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


def _normalize_translate_source_lang(value: Any, *, source_text: str = "") -> str | None:
    if _looks_like_arabic_text(source_text):
        return "ar"
    if value is None:
        return None
    source_lang = str(value).strip().lower().replace("_", "-")
    if not source_lang or source_lang in {"unknown", "und", "none", "null"}:
        return None
    if source_lang.startswith("en"):
        return "en"
    if source_lang.startswith("tr") or source_lang.startswith("tur"):
        return "tr"
    if source_lang in {"ar", "ara", "arabic"} or source_lang.startswith("arb"):
        return "ar"
    return source_lang.split("-")[0]


def _normalize_translate_source_variant(value: Any, *, source_lang: str | None, source_text: str = "") -> str | None:
    if source_lang != "ar":
        return None
    requested = normalize_source_variant(str(value)) if value is not None else "auto"
    if requested == "auto":
        return detect_arabic_variant(source_text)
    return requested


def _looks_like_arabic_text(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    arabic_letters = sum(1 for char in letters if _is_arabic_char(char))
    return arabic_letters / len(letters) >= 0.35


def _is_arabic_char(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x0600 <= codepoint <= 0x06FF
        or 0x0750 <= codepoint <= 0x077F
        or 0x08A0 <= codepoint <= 0x08FF
        or 0xFB50 <= codepoint <= 0xFDFF
        or 0xFE70 <= codepoint <= 0xFEFF
    )


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


async def _write_request_body(request: Request, destination: Path) -> tuple[int, str]:
    """Stream the request body to ``destination`` and return ``(size, sha256_hex)``."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="upload_too_large")
        except ValueError:
            pass

    written = 0
    hasher = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        async for chunk in request.stream():
            if not chunk:
                continue
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="upload_too_large")
            hasher.update(chunk)
            handle.write(chunk)
    return written, hasher.hexdigest()


def _parse_transcript_txt(path: Path) -> list[dict[str, Any]]:
    """[HH:MM:SS] satırlı transcript.txt → {start,end,text} segmentleri (segments.json yoksa yedek)."""
    segs: list[dict[str, Any]] = []
    try:
        for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\[(\d+):(\d+):(\d+)\]\s*(.*)", ln.strip())
            if not m:
                continue
            h, mi, s, txt = m.groups()
            start = float(int(h) * 3600 + int(mi) * 60 + int(s))
            if segs:
                segs[-1]["end"] = start
            segs.append({"start": start, "end": start + 3.0, "text": txt.strip()})
    except Exception:  # noqa: BLE001
        return []
    return segs


def _load_pipeline_transcript(hub: Any) -> tuple[list[dict[str, Any]], str]:
    """Pipeline klibinin en son ASR run'undan segment + transcript oku (webui timeline için).

    Önce segments.json (lean ASR start/end/text), yoksa transcript.txt çözümlenir. Yoksa ([], "")."""
    if not hub:
        return [], ""
    try:
        runs = sorted((Path(hub) / "asr").glob("*/run"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:  # noqa: BLE001
        return [], ""
    for run in runs:
        segs: list[dict[str, Any]] = []
        seg_file = run / "segments.json"
        if seg_file.exists():
            data = _read_json(seg_file)
            if isinstance(data, list):
                segs = data
        if not segs and (run / "transcript.txt").exists():
            segs = _parse_transcript_txt(run / "transcript.txt")
        if segs:
            plain = run / "transcript_plain.txt"
            if plain.exists():
                txt = plain.read_text(encoding="utf-8", errors="replace").strip()
            else:
                txt = "\n".join(str(s.get("text", "")).strip() for s in segs).strip()
            return segs, txt
    return [], ""


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    payload = dict(job)
    summary_path = payload.get("summary_path") or str(Path(payload["output_dir"]) / "summary.json")
    archive_path = payload.get("archive_path") or str(Path(payload["output_dir"]) / "archive.json")
    module_run_path = payload.get("module_run_path") or str(Path(payload["output_dir"]) / "module_run.json")
    timeline_path = payload.get("timeline_events_path") or str(Path(payload["output_dir"]) / "timeline_events.json")
    transcript_summary_path = payload.get("transcript_summary_path") or str(Path(payload["output_dir"]) / "transcript_summary.json")
    summary = _read_json(summary_path)
    archive = _read_json(archive_path)
    module_run = _read_json(module_run_path)
    timeline = _read_json(timeline_path)
    transcript_summary = _read_json(transcript_summary_path)

    if summary is not None:
        payload["summary"] = summary
    if module_run is not None:
        payload["module_run"] = module_run
    if archive is not None:
        payload["archive"] = archive
        transcript = archive.get("transcript") or {}
        payload["transcript"] = transcript.get("clean") or transcript.get("verbatim") or ""
        payload["segments"] = archive.get("segments") or []
    elif str(payload.get("module")) == "pipeline":
        # pipeline job: lean ASR transcript/segments'i klip hub'ından al → webui timeline + transcript
        p_segs, p_txt = _load_pipeline_transcript(payload.get("hub"))
        payload["segments"] = payload.get("segments") or p_segs
        payload["transcript"] = payload.get("transcript") or p_txt
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
    if transcript_summary is not None:
        payload["transcript_summary"] = transcript_summary
        payload["transcript_summary_path"] = str(transcript_summary_path)
    clip_id = str(payload.get("clip_id") or "").strip()
    if clip_id:
        clip_record = _load_clip_record(clip_id)
        if clip_record is not None:
            payload["module_summary"] = _public_clip(clip_record).get("module_summary", {})
    return payload


def _public_job_summary(job: dict[str, Any], *, search_query: str = "") -> dict[str, Any]:
    payload = dict(job)
    summary_path = payload.get("summary_path") or str(Path(payload["output_dir"]) / "summary.json")
    transcript_summary_path = payload.get("transcript_summary_path") or str(Path(payload["output_dir"]) / "transcript_summary.json")
    summary = _read_json(summary_path)
    transcript_summary = _read_json(transcript_summary_path)
    if summary is not None:
        payload["summary"] = summary
    if transcript_summary is not None:
        payload["transcript_summary"] = transcript_summary
        payload["transcript_summary_path"] = str(transcript_summary_path)
    payload["transcript"] = ""
    payload["segments"] = []
    payload["timeline_events"] = []
    payload["logs"] = []
    payload["elapsed_seconds"] = _job_elapsed_seconds(payload)
    payload["progress_percent"] = _job_progress_percent(payload)
    if search_query:
        match = _job_search_match(payload, search_query)
        if match:
            payload["search_match"] = match
    return payload


def _transcript_summary_path(job: dict[str, Any]) -> Path:
    explicit = job.get("transcript_summary_path")
    if explicit:
        return Path(str(explicit))
    return Path(str(job["output_dir"])) / "transcript_summary.json"


def _job_search_match(job: dict[str, Any], query: str) -> dict[str, Any] | None:
    needle = _normalize_search_text(query)
    if not needle:
        return None

    summary_path = job.get("summary_path") or str(Path(str(job["output_dir"])) / "summary.json")
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else _read_json(summary_path)
    metadata_parts = [
        job.get("job_id"),
        job.get("clip_id"),
        job.get("media_id"),
        job.get("filename"),
        job.get("status"),
        job.get("message"),
        job.get("error"),
        job.get("profile"),
        job.get("channel_mode"),
    ]
    if isinstance(summary, dict):
        metadata_parts.extend([
            summary.get("model_name"),
            summary.get("profile_used"),
            summary.get("profile_requested"),
            summary.get("fallback_reason"),
            summary.get("selection_reason"),
        ])
    metadata_text = " ".join(str(part) for part in metadata_parts if part)
    if needle in _normalize_search_text(metadata_text):
        return {"scope": "metadata", "label": "metadata", "count": 1, "snippet": _search_snippet(metadata_text, query)}

    transcript = _job_transcript_for_search(job)
    if transcript:
        count = _normalize_search_text(transcript).count(needle)
        if count > 0:
            return {"scope": "transcript", "label": "transcript", "count": count, "snippet": _search_snippet(transcript, query)}
    return None


def _job_transcript_for_search(job: dict[str, Any]) -> str:
    if isinstance(job.get("transcript"), str) and job.get("transcript"):
        return str(job["transcript"])
    archive_path = job.get("archive_path") or str(Path(str(job["output_dir"])) / "archive.json")
    archive = job.get("archive") if isinstance(job.get("archive"), dict) else _read_json(archive_path)
    if not isinstance(archive, dict):
        return ""
    transcript_block = archive.get("transcript")
    if isinstance(transcript_block, dict):
        text = transcript_block.get("clean") or transcript_block.get("verbatim")
        if isinstance(text, str):
            return text
    segments = archive.get("segments")
    if isinstance(segments, list):
        return " ".join(str(segment.get("text") or "") for segment in segments if isinstance(segment, dict))
    return ""


def _normalize_search_text(value: Any) -> str:
    return str(value or "").casefold()


def _search_snippet(text: str, query: str, *, radius: int = 90) -> str:
    needle = _normalize_search_text(query)
    haystack = _normalize_search_text(text)
    index = haystack.find(needle)
    if index < 0:
        return text[: radius * 2].strip()
    start = max(0, index - radius)
    end = min(len(text), index + len(query) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def _generate_transcript_summary(job: dict[str, Any], transcript: str) -> dict[str, Any]:
    is_film = job.get("content_profile") == "film"
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _summarize_with_anthropic(job, transcript)
        except RuntimeError:
            pass
    # Film/dizi ozetinde OpenAI-compat (yerel qwen35local) fallback'i KULLANMA:
    # terk edilen qwen film prompt'unu tutmuyor, bozuk ozet uretir. Sonnet
    # basarisizsa dogrudan local-extractive'e dus. Diger profiller eski zinciri korur.
    if not is_film:
        try:
            return _summarize_with_openai(job, transcript)
        except RuntimeError:
            pass
    return _summarize_locally(job, transcript)


def _summary_messages(job: dict[str, Any], transcript: str) -> list[dict[str, str]]:
    """Build the chat messages list for the summary LLM call.

    Branches on ``job["content_profile"]``:
    - ``"spor"``: futbol / diger-brans yapilandirilmis soru seti (transkriptte
      VARSA doldur, yoksa atla; uydurma yok).
    - Anything else / None (film, dizi, haber, ...): "alttaki metin ne anlatiyor"
      generic ozeti (Onemli Konular + gecen isim/kurum).

    NOT: Film/dizi olay-orgusu+SPOILER ozeti (ozet_film.txt) BURADA DEGIL; o
    yalniz PDF kunyede uretilir (scripts/mitas_pipeline.py _generate_ozet).
    WebUI log "icerik ozeti" film icin de generic "ne anlatiyor" verir.

    The ``transcript`` argument should already be the trimmed source text
    (i.e. the output of ``_summary_source_text()``).
    """
    summary_block = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    context_lines = (
        f"Dosya: {job.get('filename')}\n"
        f"Süre: {_format_summary_seconds(summary_block.get('audio_duration'))}\n\n"
    )

    if job.get("content_profile") == "spor":
        system_msg = (
            "Sen yayın arşivi spor müsabakası transkriptlerini analiz edip yapılandırılmış, "
            "doğru ve Türkçe özet çıkaran bir asistansın. SADECE transkriptte AÇIKÇA geçen "
            "bilgiyi yaz. Tahmin, hayal, uydurma KESİNLİKLE YOK (halüsinasyon sıfır). Bir "
            "bilgi transkriptte yoksa o başlığı HİÇ YAZMA (boş geç). Düşünme/akıl yürütme "
            "metni veya <think> bloğu üretme; doğrudan nihai Türkçe özeti ver."
        )
        user_msg = (
            "Aşağıdaki spor müsabakası transkriptini analiz et. Önce sporu belirle "
            "(futbol mu, başka branş mı).\n\n"
            "FUTBOL ise, aşağıdakilerden transkriptte AÇIKÇA geçenleri başlıklı yaz "
            "(geçmeyeni hiç yazma):\n"
            "   - Karşılaşma: hangi takımlar arasında\n"
            "   - Skor: maçın skoru\n"
            "   - Yer: nerede oynanıyor (şehir/stat)\n"
            "   - Lig: hangi ligde/kupada\n"
            "   - Hakemler: maçın hakemleri\n"
            "   - Kırmızı kart: kırmızı kart çıktı mı, çıktıysa kime\n"
            "   - Goller: golleri kim attı\n\n"
            "DİĞER BRANŞLAR ise, aşağıdakilerden transkriptte AÇIKÇA geçenleri yaz "
            "(geçmeyeni hiç yazma):\n"
            "   - Karşılaşma: hangi takımlar/sporcular arasında\n"
            "   - Skor: maçın skoru\n"
            "   - Yer: nerede oynanıyor\n"
            "   - Lig: hangi ligde/turnuvada\n\n"
            "KURAL: Yalnız transkriptte geçen bilgiyi yaz; geçmeyen başlığı atla. "
            "Tahmin/hayal/uydurma YOK. Çıktı Türkçe ve başlıklı.\n\n"
            f"{context_lines}"
            f"TRANSKRİPT:\n{transcript}"
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    # Generic / all other content profiles
    prompt = (
        "Aşağıdaki medya transkriptini Türkçe olarak özetle.\n"
        "İstenen çıktı:\n"
        "- 1 kısa genel özet paragrafı\n"
        "- 4-7 maddelik önemli konular\n"
        "- Varsa kişi/kurum/yer/spor takımı adları\n"
        "Halüsinasyon yapma; sadece transkriptte geçenleri yaz.\n\n"
        f"{context_lines}"
        f"TRANSKRİPT:\n{transcript}"
    )
    return [
        {"role": "system", "content": "Sen yayın arşivi transkriptlerini kısa, doğru ve Türkçe özetleyen bir asistansın."},
        {"role": "user", "content": prompt},
    ]


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CHAT_CONTROL_RE = re.compile(
    r"<\|(?:im_start|im_end|endoftext|eot_id|end|im_sep)\|>|</s>", re.IGNORECASE
)


def _clean_model_output(text: str) -> str:
    """Sanitize raw chat-model content into a clean summary.

    Handles two failure modes seen with locally imported GGUF models:
    - <think>…</think> reasoning blocks (Qwen-style) leaking into content.
    - A correct answer followed by chat control tokens and a re-echo of the
      prompt (imperfect chat template / stop tokens), e.g.
      ``…özet<|endoftext|><|im_start|>user …``.

    No-op for well-behaved models (hosted OpenAI never emits these). Falls
    back to the original text if cleaning would empty it, so the caller never
    gets a blank summary.
    """
    cleaned = _THINK_BLOCK_RE.sub("", text)
    if "</think>" in cleaned:  # unbalanced / truncated open tag
        cleaned = cleaned.rsplit("</think>", 1)[-1]
    cleaned = re.sub(r"</?think>", "", cleaned, flags=re.IGNORECASE)
    control = _CHAT_CONTROL_RE.search(cleaned)
    if control:  # truncate the prompt re-echo / junk after the answer
        cleaned = cleaned[: control.start()]
    cleaned = cleaned.strip()
    return cleaned or text.strip()


def _summarize_with_anthropic(job: dict[str, Any], transcript: str) -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("anthropic_api_key_not_set")
    model = os.environ.get("MITAS_ANTHROPIC_MODEL", "claude-sonnet-4-6")
    source = _summary_source_text(transcript)
    messages = _summary_messages(job, source)
    system_content = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_messages = [m for m in messages if m["role"] != "system"]
    body = {
        "model": model,
        "max_tokens": SUMMARY_MAX_TOKENS,
        "temperature": 0.2,
        "system": system_content,
        "messages": user_messages,
    }
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=SUMMARY_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"anthropic_summary_failed:{exc}") from exc
    content_blocks = payload.get("content", [])
    content = next((b.get("text") for b in content_blocks if b.get("type") == "text"), None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("anthropic_summary_empty")
    return {
        "provider": "anthropic",
        "model": payload.get("model", model),
        "summary": _clean_model_output(content),
        "source_chars": len(transcript),
        "used_chars": len(source),
    }


def _summarize_with_openai(job: dict[str, Any], transcript: str) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("MITAS_SUMMARY_MODEL") or os.environ.get("OPENAI_SUMMARY_MODEL")
    if not api_key or not model:
        raise RuntimeError("summary_model_not_configured")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    source = _summary_source_text(transcript)
    body = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": SUMMARY_MAX_TOKENS,
        "messages": _summary_messages(job, source),
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=SUMMARY_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"summary_model_failed:{exc}") from exc

    content = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content")
    )
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("summary_model_empty")
    return {
        "provider": "openai-compatible",
        "model": model,
        "summary": _clean_model_output(content),
        "source_chars": len(transcript),
        "used_chars": len(source),
    }


def _summarize_locally(job: dict[str, Any], transcript: str) -> dict[str, Any]:
    sentences = _split_summary_sentences(transcript)
    if not sentences:
        return {
            "provider": "local",
            "model": "local-extractive-summary",
            "summary": transcript[:1200],
            "source_chars": len(transcript),
            "used_chars": min(len(transcript), 1200),
        }
    frequencies = _summary_word_frequencies(transcript)
    scored: list[tuple[float, int, str]] = []
    for index, sentence in enumerate(sentences):
        words = _summary_words(sentence)
        if not words:
            continue
        score = sum(frequencies.get(word, 0) for word in words) / max(len(words), 1)
        if 45 <= len(sentence) <= 260:
            score *= 1.15
        scored.append((score, index, sentence))

    selected = sorted(scored, key=lambda item: item[0], reverse=True)[:6]
    selected_sentences = [sentence for _, _, sentence in sorted(selected, key=lambda item: item[1])]
    keywords = _summary_keywords(frequencies, limit=10)
    headline = selected_sentences[0] if selected_sentences else sentences[0]
    bullets = "\n".join(f"- {sentence}" for sentence in selected_sentences[1:]) or "- Öne çıkan ayrı bir madde bulunamadı."
    keyword_text = ", ".join(keywords) if keywords else "-"
    summary = (
        f"Genel özet: {headline}\n\n"
        f"Öne çıkanlar:\n{bullets}\n\n"
        f"Anahtar kelimeler: {keyword_text}"
    )
    return {
        "provider": "local",
        "model": "local-extractive-summary",
        "summary": summary,
        "source_chars": len(transcript),
        "used_chars": len(transcript),
        "note": "OPENAI_API_KEY ve MITAS_SUMMARY_MODEL ayarlı olmadığı için yerel extractive özet üretildi.",
    }


def _summary_source_text(transcript: str) -> str:
    if len(transcript) <= SUMMARY_MAX_SOURCE_CHARS:
        return transcript
    head = transcript[:25000]
    middle_start = max(0, len(transcript) // 2 - 7500)
    middle = transcript[middle_start:middle_start + 15000]
    tail = transcript[-20000:]
    return f"{head}\n\n[... orta bölümden seçki ...]\n\n{middle}\n\n[... son bölüm ...]\n\n{tail}"


def _split_summary_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?…])\s+", text.replace("\n", " "))
    return [re.sub(r"\s+", " ", chunk).strip() for chunk in chunks if len(chunk.strip()) >= 25]


def _summary_words(text: str) -> list[str]:
    words = re.findall(r"[\wçğıöşüÇĞİÖŞÜ'-]+", text.lower(), flags=re.UNICODE)
    return [
        word.strip("'-")
        for word in words
        if len(word.strip("'-")) >= 4 and word.strip("'-") not in TURKISH_SUMMARY_STOPWORDS
    ]


def _summary_word_frequencies(text: str) -> dict[str, int]:
    frequencies: dict[str, int] = {}
    for word in _summary_words(text):
        frequencies[word] = frequencies.get(word, 0) + 1
    return frequencies


def _summary_keywords(frequencies: dict[str, int], *, limit: int) -> list[str]:
    return [
        word
        for word, _count in sorted(frequencies.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def _format_summary_seconds(value: Any) -> str:
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return "-"
    hours, rem = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


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


def _load_recent_jobs(limit: int, *, search_query: str = "") -> list[dict[str, Any]]:
    CLIPS_ROOT.mkdir(parents=True, exist_ok=True)
    jobs: list[dict[str, Any]] = []
    query = search_query.strip()
    for path in _job_json_paths(limit=None if query else limit):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if query and _job_search_match(payload, query) is None:
            continue
        jobs.append(payload)
        if len(jobs) >= limit:
            break
    return jobs


def _find_job_json(job_id: str) -> Path | None:
    if not job_id:
        return None
    incoming = INCOMING_ROOT / job_id / "job.json"   # pipeline (pipe-*) işleri burada saklanır
    if incoming.exists():
        return incoming
    if CLIPS_ROOT.exists():
        for path in CLIPS_ROOT.glob(f"*/asr/{job_id}/job.json"):
            return path
    legacy = LEGACY_JOB_ROOT / job_id / "job.json"
    if legacy.exists():
        return legacy
    return None


def _is_path_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _playback_media_path(media_path: Path) -> Path:
    if not _is_playback_remux_candidate(media_path):
        return media_path
    try:
        return _ensure_playback_mp4(media_path)
    except Exception as exc:
        _server_logger.warning("playback remux failed for %s: %s", media_path, exc)
        return media_path


def _is_playback_remux_candidate(media_path: Path) -> bool:
    suffix = media_path.suffix.lower()
    if suffix not in {".mp4", ".m4v", ".mov"}:
        return False
    return not media_path.name.endswith(".mitas_playback.mp4")


def _ensure_playback_mp4(media_path: Path) -> Path:
    playback_path = media_path.with_name(f"{media_path.stem}.mitas_playback.mp4")
    if _playback_cache_is_fresh(playback_path, media_path):
        return playback_path
    with _media_remux_lock:
        if _playback_cache_is_fresh(playback_path, media_path):
            return playback_path
        _remux_media_for_playback(media_path, playback_path)
    return playback_path


def _playback_cache_is_fresh(playback_path: Path, source_path: Path) -> bool:
    return (
        playback_path.exists()
        and playback_path.is_file()
        and playback_path.stat().st_size > 0
        and playback_path.stat().st_mtime >= source_path.stat().st_mtime
    )


def _remux_media_for_playback(source_path: Path, playback_path: Path) -> None:
    from core.pipelines.asr.transcribe import DEFAULT_FFMPEG_EXECUTABLE

    playback_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = playback_path.with_suffix(playback_path.suffix + ".part.mp4")
    temp_path.unlink(missing_ok=True)
    command = [
        DEFAULT_FFMPEG_EXECUTABLE,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-map",
        "0:v:0?",
        "-map",
        "0:a:0?",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(temp_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=1800)
    if completed.returncode != 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError((completed.stderr or completed.stdout or "ffmpeg remux failed").strip())
    temp_path.replace(playback_path)


def _trim_media_range(source_path: Path, output_path: Path, *, start_seconds: float, end_seconds: float) -> None:
    from core.pipelines.asr.transcribe import DEFAULT_FFMPEG_EXECUTABLE

    duration = max(0.001, end_seconds - start_seconds)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".part" + output_path.suffix)
    temp_path.unlink(missing_ok=True)
    command = [
        DEFAULT_FFMPEG_EXECUTABLE,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_seconds:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source_path),
    ]
    if output_path.suffix.lower() == ".wav":
        command.extend(["-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1"])
    else:
        command.extend(["-map", "0:v:0?", "-map", "0:a:0?", "-c", "copy", "-movflags", "+faststart"])
    command.append(str(temp_path))
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=1800)
    if completed.returncode != 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError((completed.stderr or completed.stdout or "ffmpeg range trim failed").strip())
    if not temp_path.exists() or temp_path.stat().st_size <= 0:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg range trim produced an empty file")
    temp_path.replace(output_path)


def _range_media_suffix(source_path: Path) -> str:
    suffix = source_path.suffix.lower()
    if suffix in {".wav", ".mp3", ".m4a", ".aac", ".flac"}:
        return ".wav"
    return ".mp4"


def _range_token(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000)))
    return f"{millis}ms"


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
    content_hash: str | None = None,
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
    if content_hash and not record.get("content_hash"):
        record["content_hash"] = content_hash
    record.setdefault("modules", {})
    _write_json(path, record)
    return record


def _find_clip_by_hash(content_hash: str) -> dict[str, Any] | None:
    """Find an existing clip record by sha256 of its source content."""
    if not content_hash or not CLIPS_ROOT.exists():
        return None
    for record_path in CLIPS_ROOT.glob("*/clip.json"):
        record = _read_json(record_path)
        if isinstance(record, dict) and record.get("content_hash") == content_hash:
            return record
    return None


def _clip_latest_module_job_id(record: dict[str, Any] | None, module: str) -> str | None:
    if not isinstance(record, dict):
        return None
    module_state = (record.get("modules") or {}).get(module)
    if not isinstance(module_state, dict):
        return None
    latest = str(module_state.get("latest_job_id") or "").strip()
    return latest or None


def _normalize_generated_data_module(module: str) -> str:
    key = str(module or "").strip().lower()
    canonical = GENERATED_MODULE_ALIASES.get(key, key)
    if canonical not in DELETABLE_GENERATED_MODULES:
        raise HTTPException(status_code=400, detail=f"unsupported_generated_module:{module}")
    return canonical


def _module_job_ids(module_state: Any) -> list[str]:
    if not isinstance(module_state, dict):
        return []
    return [str(item) for item in module_state.get("jobs") or [] if str(item)]


def _first_active_job_id(job_ids: list[str]) -> str | None:
    for job_id in job_ids:
        job = _load_job(job_id)
        if job and job.get("status") in {"queued", "running"}:
            return job_id
    return None


def _clip_source_media_path(clip_id: str, record: dict[str, Any]) -> Path:
    raw_path = record.get("source_path")
    if not raw_path:
        raise HTTPException(status_code=404, detail="media_not_found")
    media_path = Path(str(raw_path))
    if not media_path.is_absolute():
        media_path = PROJECT_ROOT / media_path
    media_path = media_path.resolve()
    clip_dir = (CLIPS_ROOT / clip_id).resolve()
    if not _is_path_under(media_path, clip_dir):
        raise HTTPException(status_code=403, detail="media_path_not_allowed")
    if not media_path.exists() or not media_path.is_file():
        raise HTTPException(status_code=404, detail="media_not_found")
    return media_path


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


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


def _safe_artifact_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-") or "item"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
