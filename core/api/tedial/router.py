"""FastAPI adapter for the Tedial session broker POC.

The module is import-safe in lightweight environments: FastAPI/httpx are loaded
only when `create_tedial_router()` is called.
"""

from dataclasses import asdict
import asyncio
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from core.api.tedial.import_queue import TedialImportQueue
from core.api.tedial.job_runner import TedialJobRunner
from core.api.tedial.media_resolver import TedialMediaResolveError, keep_mpd_audio_track, safe_artifact_id, select_mpd_audio_video_urls
from core.api.tedial.parser import parse_search_results
from core.api.tedial.proxy import TedialProxyPlan, TedialProxyService, rewrite_mpd_base_urls
from core.api.tedial.session import TedialSessionNotConnected


def create_tedial_router(service: TedialProxyService | None = None, import_queue: TedialImportQueue | None = None):
    """Create the Tedial POC router.

    Runtime dependencies live in the ASR/service venv. Keeping this import lazy
    lets core unit tests exercise the pure broker/parser code without FastAPI.
    """

    try:
        import httpx
        from fastapi import APIRouter, HTTPException, Request
        from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
        from pydantic import BaseModel, Field
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("Tedial router requires fastapi, pydantic and httpx in the active runtime") from exc

    svc = service or TedialProxyService()
    queue = import_queue or TedialImportQueue()
    job_runner = TedialJobRunner(service=svc, queue=queue)
    router = APIRouter(prefix="/api/tedial", tags=["tedial"])

    class SessionStartRequest(BaseModel):
        remember: bool = False

    class DevCookieAttachRequest(BaseModel):
        cookie_header: str = Field(min_length=1)
        remember: bool = False

    class SearchRequest(BaseModel):
        searchField: str = Field(min_length=1)
        searchMode: str | None = None

    class PlaybackTokenRefreshRequest(BaseModel):
        token: str = Field(min_length=1)

    class TedialAssetImportRequest(BaseModel):
        repository_id: str = Field(min_length=1)
        sequence_id: str | None = None
        title: str | None = None
        asset_type: str | None = None

    class TedialJobRunRequest(BaseModel):
        modules: list[str] = Field(default_factory=lambda: ["asr"])
        background: bool = False
        asr_profile: str = "fast_with_fallback"
        max_seconds: float | None = Field(default=None, gt=0)
        ocr_interval_seconds: float = Field(default=10.0, gt=0)
        ocr_max_frames: int = Field(default=24, gt=0)

    async def send_plan_or_502(plan: TedialProxyPlan):
        try:
            return await _send_plan(plan, verify=svc.config.verify_tls, httpx=httpx)
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Tedial upstream connection failed: {type(exc).__name__}") from exc

    async def fetch_asset_manifest_text(*, user_id: str, repository_id: str, asset_id: str) -> str:
        try:
            plan = svc.plan_manifest(user_id, repository_id=repository_id, asset_id=asset_id)
        except TedialSessionNotConnected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        resp = await send_plan_or_502(plan)
        if resp.status_code in (401, 403):
            svc.broker.mark_checked(user_id, connected=False, error=f"Tedial manifest authorization failed ({resp.status_code})")
            raise HTTPException(status_code=409, detail="Tedial session expired; please reconnect")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Tedial manifest failed ({resp.status_code})")
        return resp.text

    @router.get("/session")
    async def session_status(request: Request) -> dict[str, Any]:
        return svc.session_status(_user_id_from_request(request)).to_dict()

    @router.post("/session/start")
    async def session_start(payload: SessionStartRequest, request: Request) -> dict[str, Any]:
        snapshot = svc.start_session(_user_id_from_request(request), remember=payload.remember)
        data = snapshot.to_dict()
        data["login_url"] = "/api/tedial/login/"
        data["note"] = "Open login_url in a browser tab, sign in to Tedial, then call session/health."
        return data

    @router.post("/session/forget")
    async def session_forget(request: Request) -> dict[str, Any]:
        return svc.forget_session(_user_id_from_request(request)).to_dict()

    @router.post("/session/dev-cookie")
    async def session_dev_cookie(payload: DevCookieAttachRequest, request: Request) -> dict[str, Any]:
        if not _dev_cookie_attach_enabled():
            raise HTTPException(status_code=404, detail="Dev cookie attach is disabled")
        snapshot = svc.broker.attach_cookie_header(
            _user_id_from_request(request),
            payload.cookie_header,
            remember=payload.remember,
        )
        return snapshot.to_dict()

    @router.get("/session/health")
    async def session_health(request: Request) -> dict[str, Any]:
        user_id = _user_id_from_request(request)
        try:
            cookie_header = svc.broker.cookie_header_for(user_id)
        except TedialSessionNotConnected:
            return svc.session_status(user_id).to_dict()
        url = svc.config.build_base_url(svc.config.load_default_search_path)
        plan = TedialProxyPlan(method="GET", url=url, headers={"Cookie": cookie_header, "Accept": "text/html"})
        resp = await send_plan_or_502(plan)
        connected = resp.status_code < 400 and not _looks_like_login(resp)
        snapshot = svc.broker.mark_checked(
            user_id,
            connected=connected,
            error=f"Tedial health check failed ({resp.status_code})" if not connected else None,
        )
        return snapshot.to_dict()

    @router.api_route("/login", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @router.api_route("/login/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def login_proxy(request: Request, path: str = "") -> Response:
        user_id = _user_id_from_request(request)
        if svc.session_status(user_id).status.value not in {"connected", "connecting"}:
            svc.start_session(user_id)
        target_path = "/" + path if path else svc.config.load_default_search_path
        target_url = _login_proxy_target_url(svc.config.base_url, target_path, request.url.query)
        if not svc.config.is_allowed_upstream_url(target_url):
            raise HTTPException(status_code=400, detail="Tedial login target is not allowed")

        headers = _forward_headers(request)
        cookie_header = svc.broker.cookie_header_if_any(user_id)
        if cookie_header:
            headers["Cookie"] = cookie_header
        body = await request.body()
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=90.0),
            follow_redirects=False,
            verify=svc.config.verify_tls,
            trust_env=False,
        ) as client:
            try:
                upstream = await client.request(request.method, target_url, headers=headers, content=body)
            except httpx.RequestError as exc:
                raise HTTPException(status_code=502, detail=f"Tedial upstream connection failed: {type(exc).__name__}") from exc

        set_cookie_headers = upstream.headers.get_list("set-cookie")
        if set_cookie_headers:
            svc.broker.attach_set_cookie_headers(user_id, set_cookie_headers, mark_connected=False)
        if _is_authenticated_default_page(request.method, target_path, svc.config.load_default_search_path, upstream):
            svc.broker.mark_checked(user_id, connected=True)
        if _should_return_to_poc_ui(request.method, target_path, svc.config.load_default_search_path, svc.session_status(user_id).status.value):
            return RedirectResponse(url="/tedial", status_code=303)

        response_headers = _login_response_headers(upstream.headers)
        status_code = upstream.status_code
        if status_code in (301, 302, 303, 307, 308):
            location = upstream.headers.get("location", "")
            response_headers["location"] = _rewrite_login_location(location, svc.config.base_url)

        content = upstream.content
        content_type = upstream.headers.get("content-type", "")
        if _is_rewritable_text(content_type):
            text = upstream.text
            text = rewrite_login_proxy_text(text, svc.config.base_url)
            content = text.encode(upstream.encoding or "utf-8", errors="replace")
            response_headers.pop("content-length", None)

        return Response(content=content, status_code=status_code, headers=response_headers, media_type=content_type or None)

    @router.post("/search")
    async def search(payload: SearchRequest, request: Request) -> JSONResponse:
        user_id = _user_id_from_request(request)
        try:
            trt_id_lookup = _search_mode_is_trt_id(payload.searchMode, payload.searchField)
            plan = svc.plan_search(user_id, payload.searchField, trt_id_lookup=trt_id_lookup)
        except TedialSessionNotConnected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        resp = await send_plan_or_502(plan)
        if resp.status_code in (401, 403):
            svc.broker.mark_checked(user_id, connected=False, error=f"Tedial search authorization failed ({resp.status_code})")
            raise HTTPException(status_code=409, detail="Tedial session expired; please reconnect")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Tedial search failed ({resp.status_code})")
        results = parse_search_results(resp.text)
        return JSONResponse(
            content={
                "count": len(results),
                "items": [_search_result_payload(item) for item in results],
                "upstream_content_type": resp.headers.get("content-type"),
                "search_mode": "trt_id" if trt_id_lookup else "default",
            }
        )

    @router.post("/playback-token/refresh")
    async def refresh_playback_token(payload: PlaybackTokenRefreshRequest, request: Request) -> JSONResponse:
        user_id = _user_id_from_request(request)
        try:
            plan = svc.plan_playback_token_refresh(user_id, payload.token)
        except TedialSessionNotConnected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        resp = await send_plan_or_502(plan)
        if resp.status_code in (401, 403):
            svc.broker.mark_checked(user_id, connected=False, error=f"Tedial token authorization failed ({resp.status_code})")
            raise HTTPException(status_code=409, detail="Tedial session expired; please reconnect")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Tedial token refresh failed ({resp.status_code})")
        return JSONResponse(content=_safe_json(resp))

    @router.get("/assets/{asset_id}/manifest")
    async def manifest(asset_id: str, request: Request, repository_id: str, audio_track: int = 0) -> Response:
        user_id = _user_id_from_request(request)
        try:
            plan = svc.plan_manifest(user_id, repository_id=repository_id, asset_id=asset_id)
        except TedialSessionNotConnected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        resp = await send_plan_or_502(plan)
        if resp.status_code in (401, 403):
            svc.broker.mark_checked(user_id, connected=False, error=f"Tedial manifest authorization failed ({resp.status_code})")
            raise HTTPException(status_code=409, detail="Tedial session expired; please reconnect")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Tedial manifest failed ({resp.status_code})")
        mpd = keep_mpd_audio_track(rewrite_mpd_base_urls(resp.text, svc.config), audio_track_index=audio_track)
        return Response(
            content=mpd,
            media_type="application/dash+xml",
        )

    @router.get("/assets/{asset_id}/stream")
    async def asset_stream(asset_id: str, request: Request, repository_id: str, audio_track: int = 0) -> StreamingResponse:
        user_id = _user_id_from_request(request)
        raw_mpd = await fetch_asset_manifest_text(
            user_id=user_id,
            repository_id=repository_id,
            asset_id=asset_id,
        )
        try:
            video_url, audio_url = select_mpd_audio_video_urls(raw_mpd, svc.config, audio_track_index=audio_track)
        except TedialMediaResolveError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        cookie_header = svc.broker.cookie_header_if_any(user_id)
        process = await _start_tedial_ffmpeg_mp4_stream(
            video_url=video_url,
            audio_url=audio_url,
            cookie_header=cookie_header,
            verify_tls=svc.config.verify_tls,
        )
        stderr_task = asyncio.create_task(process.stderr.read() if process.stderr else _empty_bytes())

        async def _body():
            try:
                if process.stdout is None:
                    return
                while True:
                    chunk = await process.stdout.read(1024 * 256)
                    if not chunk:
                        break
                    yield chunk
                return_code = await process.wait()
                if return_code != 0:
                    stderr = (await stderr_task).decode("utf-8", errors="replace").strip()
                    raise RuntimeError(stderr or f"Tedial stream ffmpeg failed ({return_code})")
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

        return StreamingResponse(
            _body(),
            media_type="video/mp4",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'inline; filename="{safe_artifact_id(asset_id)}.mp4"',
            },
        )

    @router.post("/assets/{asset_id}/asr")
    async def asset_asr(
        asset_id: str,
        request: Request,
        repository_id: str,
        title: str | None = None,
        profile: str = "fast_with_fallback",
        channel_mode: str = "auto",
        audio_track: int = 0,
    ) -> JSONResponse:
        user_id = _user_id_from_request(request)
        raw_mpd = await fetch_asset_manifest_text(
            user_id=user_id,
            repository_id=repository_id,
            asset_id=asset_id,
        )
        try:
            video_url, audio_url = select_mpd_audio_video_urls(raw_mpd, svc.config, audio_track_index=audio_track)
        except TedialMediaResolveError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        cookie_header = svc.broker.cookie_header_if_any(user_id)
        process = await _start_tedial_ffmpeg_mp4_stream(
            video_url=video_url,
            audio_url=audio_url,
            cookie_header=cookie_header,
            verify_tls=svc.config.verify_tls,
        )
        stderr_task = asyncio.create_task(process.stderr.read() if process.stderr else _empty_bytes())
        try:
            filename = _tedial_asset_filename(title=title, asset_id=asset_id)
            asr_response = await _post_ffmpeg_stream_to_asr(
                httpx=httpx,
                process=process,
                filename=filename,
                profile=profile,
                channel_mode=channel_mode,
            )
        except Exception as exc:
            if process.returncode is None:
                process.kill()
                await process.wait()
            stderr = (await stderr_task).decode("utf-8", errors="replace").strip()
            detail = str(exc) or stderr or "Tedial stream could not be sent to ASR"
            raise HTTPException(status_code=502, detail=detail) from exc
        else:
            if process.returncode is None:
                await process.wait()
            stderr = (await stderr_task).decode("utf-8", errors="replace").strip()
            if process.returncode not in (0, None):
                raise HTTPException(status_code=502, detail=stderr or f"Tedial stream ffmpeg failed ({process.returncode})")
            return JSONResponse(content=asr_response)

    @router.get("/assets/{asset_id}/import-plan")
    async def import_plan(
        asset_id: str,
        request: Request,
        repository_id: str,
        sequence_id: str | None = None,
        title: str | None = None,
        asset_type: str | None = None,
    ) -> JSONResponse:
        user_id = _user_id_from_request(request)
        try:
            plan = svc.build_import_plan(
                user_id,
                repository_id=repository_id,
                asset_id=asset_id,
                sequence_id=sequence_id,
                title=title,
                asset_type=asset_type,
            )
        except TedialSessionNotConnected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return JSONResponse(content=plan)

    @router.post("/assets/{asset_id}/enqueue")
    async def enqueue_asset(asset_id: str, payload: TedialAssetImportRequest, request: Request) -> JSONResponse:
        user_id = _user_id_from_request(request)
        try:
            plan = svc.build_import_plan(
                user_id,
                repository_id=payload.repository_id,
                asset_id=asset_id,
                sequence_id=payload.sequence_id,
                title=payload.title,
                asset_type=payload.asset_type,
            )
            result = queue.enqueue(plan)
        except TedialSessionNotConnected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(content=result.to_dict())

    @router.get("/jobs")
    async def jobs() -> JSONResponse:
        return JSONResponse(content={"items": [_job_payload(job) for job in queue.list_jobs()]})

    @router.get("/jobs/{job_id}")
    async def job(job_id: str) -> JSONResponse:
        try:
            item = queue.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JSONResponse(content=_job_payload(item))

    @router.post("/jobs/{job_id}/run")
    async def run_job(job_id: str, payload: TedialJobRunRequest, request: Request) -> JSONResponse:
        user_id = _user_id_from_request(request)

        async def _run_and_record_failure() -> None:
            try:
                await job_runner.run_job(
                    job_id=job_id,
                    user_id=user_id,
                    modules=payload.modules,
                    asr_profile=payload.asr_profile,
                    max_seconds=payload.max_seconds,
                    ocr_interval_seconds=payload.ocr_interval_seconds,
                    ocr_max_frames=payload.ocr_max_frames,
                )
            except Exception:
                pass

        try:
            queue.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if payload.background:
            asyncio.create_task(_run_and_record_failure())
            return JSONResponse(content={"accepted": True, "job": _job_payload(queue.get_job(job_id))})

        try:
            result = await job_runner.run_job(
                job_id=job_id,
                user_id=user_id,
                modules=payload.modules,
                asr_profile=payload.asr_profile,
                max_seconds=payload.max_seconds,
                ocr_interval_seconds=payload.ocr_interval_seconds,
                ocr_max_frames=payload.ocr_max_frames,
            )
        except TedialSessionNotConnected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        content = result.to_dict()
        content["job"] = _job_payload(result.job)
        return JSONResponse(content=content)

    @router.get("/jobs/{job_id}/artifacts/{artifact_name}")
    async def job_artifact(job_id: str, artifact_name: str):
        try:
            item = queue.get_job(job_id)
            path = _artifact_path_for_job(item, artifact_name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail=f"artifact not found: {artifact_name}")
        return FileResponse(path)

    @router.get("/keyframe")
    async def keyframe(url: str, request: Request) -> Response:
        user_id = _user_id_from_request(request)
        try:
            plan = svc.plan_keyframe(user_id, url)
        except TedialSessionNotConnected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        resp = await send_plan_or_502(plan)
        if resp.status_code in (401, 403):
            svc.broker.mark_checked(user_id, connected=False, error=f"Tedial keyframe authorization failed ({resp.status_code})")
            raise HTTPException(status_code=409, detail="Tedial session expired; please reconnect")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Tedial keyframe fetch failed ({resp.status_code})")
        passthrough = {
            key: value
            for key, value in resp.headers.items()
            if key.lower() in {"content-type", "content-length", "etag", "last-modified", "cache-control"}
        }
        return Response(content=resp.content, headers=passthrough, media_type=resp.headers.get("content-type"))

    @router.get("/media")
    async def media(url: str, request: Request) -> StreamingResponse:
        try:
            user_id = _user_id_from_request(request)
            plan = svc.plan_media(url, request.headers.get("range"), cookie_header=svc.broker.cookie_header_if_any(user_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0), verify=svc.config.verify_tls, trust_env=False)
        try:
            upstream = await client.send(client.build_request(plan.method, plan.url, headers=plan.headers), stream=True)
        except httpx.RequestError as exc:
            await client.aclose()
            raise HTTPException(status_code=502, detail=f"Tedial upstream connection failed: {type(exc).__name__}") from exc
        if upstream.status_code not in (200, 206):
            await upstream.aclose()
            await client.aclose()
            raise HTTPException(status_code=502, detail=f"Tedial media fetch failed ({upstream.status_code})")

        passthrough = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() in {"content-type", "content-length", "content-range", "accept-ranges", "etag", "last-modified"}
        }

        async def _body():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(_body(), status_code=upstream.status_code, headers=passthrough)

    return router


def rewrite_login_proxy_text(text: str, base_url: str) -> str:
    """Rewrite Tedial UI references so the browser stays inside local login proxy."""
    replacements = {
        base_url + "/": "/api/tedial/login/",
        base_url: "/api/tedial/login",
        'href="/iTClient/': 'href="/api/tedial/login/iTClient/',
        'src="/iTClient/': 'src="/api/tedial/login/iTClient/',
        'action="/iTClient/': 'action="/api/tedial/login/iTClient/',
        "href='/iTClient/": "href='/api/tedial/login/iTClient/",
        "src='/iTClient/": "src='/api/tedial/login/iTClient/",
        "action='/iTClient/": "action='/api/tedial/login/iTClient/",
    }
    rewritten = text
    for old, new in replacements.items():
        rewritten = rewritten.replace(old, new)
    return rewritten


def _job_payload(job: Any) -> dict[str, Any]:
    payload = job.model_dump(mode="json")
    artifact_urls = {}
    for artifact in payload.get("output_artifacts", []):
        name = Path(str(artifact)).name
        if name:
            artifact_urls[name] = f"/api/tedial/jobs/{quote(str(job.job_id), safe='')}/artifacts/{quote(name, safe='')}"
    payload["artifact_urls"] = artifact_urls
    return payload


def _search_result_payload(item: Any) -> dict[str, Any]:
    payload = asdict(item)
    duration_units = item.duration_units
    payload["duration_seconds"] = None if duration_units is None else round(duration_units / 1000.0, 3)
    return payload


def _search_mode_is_trt_id(search_mode: str | None, search_field: str) -> bool:
    mode = (search_mode or "").strip().lower()
    if mode in {"trt_id", "trtid", "id"}:
        return True
    if mode in {"default", "text", "general"}:
        return False
    return re.match(r"^\d{2,4}-\d{3,}", search_field.strip()) is not None


def _artifact_path_for_job(job: Any, artifact_name: str) -> Path:
    safe_name = Path(artifact_name).name
    if safe_name != artifact_name:
        raise ValueError("artifact name must be a basename")
    for artifact in job.output_artifacts:
        candidate = Path(str(artifact))
        if candidate.name != safe_name:
            continue
        project_root = Path(__file__).resolve().parents[3]
        path = candidate if candidate.is_absolute() else (project_root / candidate)
        resolved = path.resolve()
        outputs_root = (project_root / "outputs").resolve()
        try:
            resolved.relative_to(outputs_root)
        except ValueError as exc:
            raise ValueError("artifact is outside the MITAS outputs directory") from exc
        return resolved
    raise KeyError(f"artifact not found in job: {artifact_name}")


def _user_id_from_request(request: Any) -> str:
    user_id = request.headers.get("X-MITAS-User", "").strip()
    return user_id or "dev-local"


def _login_proxy_target_url(base_url: str, path: str, query: str = "") -> str:
    parsed = urlsplit(base_url)
    normalized_path = path if path.startswith("/") else "/" + path
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, query, ""))


def _forward_headers(request: Any) -> dict[str, str]:
    blocked = {
        "host",
        "connection",
        "content-length",
        "accept-encoding",
        "cookie",
        "origin",
        "referer",
    }
    headers = {key: value for key, value in request.headers.items() if key.lower() not in blocked}
    headers["Origin"] = str(request.url).split("/api/tedial/login", 1)[0]
    headers["Referer"] = str(request.url)
    return headers


def _login_response_headers(headers: Any) -> dict[str, str]:
    blocked = {
        "connection",
        "content-length",
        "content-encoding",
        "transfer-encoding",
        "set-cookie",
        "location",
        "content-security-policy",
        "x-frame-options",
    }
    return {key: value for key, value in headers.items() if key.lower() not in blocked}


def _rewrite_login_location(location: str, base_url: str) -> str:
    if not location:
        return "/api/tedial/login/"
    if location.startswith(base_url):
        return "/api/tedial/login" + urlsplit(location).path + (("?" + urlsplit(location).query) if urlsplit(location).query else "")
    if location.startswith("/"):
        return "/api/tedial/login" + location
    return location


def _is_rewritable_text(content_type: str) -> bool:
    lower = content_type.lower()
    return any(kind in lower for kind in ("text/html", "text/css", "application/javascript", "text/javascript"))


def _dev_cookie_attach_enabled() -> bool:
    value = os.environ.get("MITAS_TEDIAL_DEV_COOKIE_ATTACH", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _should_return_to_poc_ui(method: str, target_path: str, default_search_path: str, status: str) -> bool:
    return method.upper() == "GET" and target_path == default_search_path and status == "connected"


def _is_authenticated_default_page(method: str, target_path: str, default_search_path: str, resp: Any) -> bool:
    return method.upper() == "GET" and target_path == default_search_path and resp.status_code < 400 and not _looks_like_login(resp)


async def _send_plan(plan: TedialProxyPlan, verify: bool, httpx: Any):
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=90.0), verify=verify, trust_env=False) as client:
        return await client.request(plan.method, plan.url, headers=plan.headers, content=plan.body)


async def _start_tedial_ffmpeg_mp4_stream(
    *,
    video_url: str,
    audio_url: str | None,
    cookie_header: str | None,
    verify_tls: bool,
):
    from core.pipelines.asr.transcribe import DEFAULT_FFMPEG_EXECUTABLE

    command = [
        DEFAULT_FFMPEG_EXECUTABLE,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
    ]
    _append_ffmpeg_http_input_options(command, cookie_header=cookie_header, verify_tls=verify_tls)
    command.extend(["-i", video_url])
    if audio_url:
        _append_ffmpeg_http_input_options(command, cookie_header=cookie_header, verify_tls=verify_tls)
        command.extend(["-i", audio_url])
        command.extend(["-map", "0:v:0", "-map", "1:a:0"])
    else:
        command.extend(["-map", "0:v:0"])
    command.extend(
        [
            "-c",
            "copy",
            "-movflags",
            "frag_keyframe+empty_moov+default_base_moof",
            "-f",
            "mp4",
            "pipe:1",
        ]
    )
    return await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


def _append_ffmpeg_http_input_options(command: list[str], *, cookie_header: str | None, verify_tls: bool) -> None:
    if not verify_tls:
        command.extend(["-tls_verify", "0"])
    if cookie_header:
        command.extend(["-headers", f"Cookie: {cookie_header}\r\n"])


async def _post_ffmpeg_stream_to_asr(
    *,
    httpx: Any,
    process: Any,
    filename: str,
    profile: str,
    channel_mode: str,
) -> dict[str, Any]:
    async def _body():
        if process.stdout is None:
            return
        while True:
            chunk = await process.stdout.read(1024 * 256)
            if not chunk:
                break
            yield chunk

    asr_url = os.environ.get("MITAS_ASR_TRANSCRIBE_URL", "http://127.0.0.1:8787/api/asr/transcribe")
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=180.0, write=1800.0), trust_env=False) as client:
        response = await client.post(
            asr_url,
            params={"filename": filename, "profile": profile, "channel_mode": channel_mode},
            headers={"content-type": "video/mp4"},
            content=_body(),
        )
    if not response.is_success:
        raise RuntimeError(f"MITAS ASR API failed ({response.status_code}): {_response_detail(response)}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("MITAS ASR API returned non-JSON response") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("MITAS ASR API returned unexpected response")
    return payload


def _response_detail(response: Any) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or response.reason_phrase
    if isinstance(payload, dict):
        return str(payload.get("detail") or payload.get("error") or payload)
    return str(payload)


def _tedial_asset_filename(*, title: str | None, asset_id: str) -> str:
    stem = safe_artifact_id(title or asset_id or "tedial_asset")
    return f"{stem}.mp4"


async def _empty_bytes() -> bytes:
    return b""


def _looks_like_login(resp: Any) -> bool:
    if resp.status_code in (401, 403):
        return True
    if resp.status_code in (302, 303):
        return "login" in resp.headers.get("location", "").lower()
    content_type = resp.headers.get("content-type", "")
    return "text/html" in content_type and "j_password" in resp.text


def _safe_json(resp: Any) -> Any:
    try:
        data = resp.json()
    except Exception:
        return {"_raw": resp.text}
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict) and "token" in data["data"]:
        data = dict(data)
        inner = dict(data["data"])
        inner["token"] = "<MASKED>"
        data["data"] = inner
    return data
