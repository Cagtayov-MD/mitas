# -*- coding: utf-8 -*-
"""MITAS Gemini (Google Generative Language API) wrapper — OpenAI-uyumlu DEĞİL, Gemini şeması.

Anahtar: MITAS_GEMINI / GEMINI_API_KEY / GOOGLE_API_KEY. Yoksa None döner — çağıran skip/fallback
yapar (asla çökmez). Anahtar KODA GÖMÜLMEZ; User env'de saklanır.

Kullanım:
    from _gemini import gemini_text
    txt = gemini_text(system="...", prompt="...", model="gemini-3.5-flash", max_tokens=1500)

Model: MITAS_GEMINI_MODEL (default "gemini-3.5-flash"). A/B jürisi (2026-06-09) birincil seçti:
4/4 filmde en tutarlı DOĞRU final + ucuz + 1M bağlam.
Endpoint: POST {base}/v1beta/models/{model}:generateContent?key=...

Env:
    MITAS_GEMINI / GEMINI_API_KEY / GOOGLE_API_KEY  — API anahtarı (zorunlu; yoksa None)
    MITAS_GEMINI_MODEL    — model (default gemini-3.5-flash)
    MITAS_GEMINI_BASE     — base URL (default https://generativelanguage.googleapis.com)
    MITAS_GEMINI_TIMEOUT  — HTTP timeout sn (default 120)

Retry: 429/503/5xx -> retry (exponential backoff 1s/2s/4s); 400(thinkingConfig) -> thinking'siz tek retry;
diğer 4xx / kota -> hemen None.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

# Kredi/erişim durumu kaydı (best-effort). Import patlarsa _gemini çalışmaya devam eder.
try:
    import _api_status  # aynı scripts/ dizininde
except Exception:  # noqa: BLE001
    try:
        import importlib.util as _ilu
        _asp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_api_status.py")
        _spec = _ilu.spec_from_file_location("_api_status", _asp)
        _api_status = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_api_status)
    except Exception:  # noqa: BLE001
        _api_status = None


def _status_mark(api: str, ok: bool, detail: str = "") -> None:
    try:
        if _api_status is not None:
            _api_status.mark(api, ok, detail)
    except Exception:  # noqa: BLE001
        pass


# Geçici (retry) HTTP kodları; gerisi kalıcı.
_RETRY_HTTP = {429, 500, 502, 503, 504}
# Yanıt metninde kalıcı kota/erişim sinyalleri (küçük harf eşleşme) — retry'siz.
_PERMANENT_SIGNALS = ("api key not valid", "permission_denied", "billing", "quota exceeded")


def _key() -> str | None:
    return (os.environ.get("MITAS_GEMINI")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY"))


def gemini_text(
    prompt: str | None = None,
    system: str | None = None,
    contents: list | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    thinking_budget: int | None = 0,   # 0 = düşünme kapalı (ucuz/temiz); None = config gönderme
    timeout: int | None = None,
    retries: int = 3,
    **extra,
) -> str | None:
    """Gemini generateContent çağrısı; yalnız metni döndürür. Başarısız/anahtar yoksa None."""
    key = _key()
    if not key:
        return None
    model = model or os.environ.get("MITAS_GEMINI_MODEL", "gemini-3.5-flash")
    base = os.environ.get("MITAS_GEMINI_BASE", "https://generativelanguage.googleapis.com").rstrip("/")
    url = f"{base}/v1beta/models/{model}:generateContent?key={key}"
    _timeout = timeout if timeout is not None else int(os.environ.get("MITAS_GEMINI_TIMEOUT", "120"))

    if contents is None:
        contents = [{"role": "user", "parts": [{"text": prompt or ""}]}]
    gen_cfg: dict[str, Any] = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if thinking_budget is not None:
        gen_cfg["thinkingConfig"] = {"thinkingBudget": thinking_budget}
    payload: dict[str, Any] = {"contents": contents, "generationConfig": gen_cfg}
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}
    payload.update(extra)

    last_exc: Exception | None = None
    thinking_dropped = False
    for attempt in range(max(1, retries)):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=_timeout) as r:
                resp = json.loads(r.read().decode("utf-8"))
            cand = (resp.get("candidates") or [{}])[0]
            parts = ((cand.get("content") or {}).get("parts") or [])
            txt = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if txt:
                _status_mark("gemini", True)
                return txt
            # Boş (safety blok / finishReason) — hata değil ama kullanılamaz.
            _status_mark("gemini", False, f"bos yanit ({cand.get('finishReason', '?')})")
            return None
        except urllib.error.HTTPError as exc:
            body_txt = ""
            try:
                body_txt = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                body_txt = ""
            low = body_txt.lower()
            detail = f"HTTP {exc.code}"
            # 400 + thinkingConfig uyumsuzluğu → thinking'i at, bir kez daha dene.
            if exc.code == 400 and "thinking" in low and not thinking_dropped:
                gen_cfg.pop("thinkingConfig", None)
                thinking_dropped = True
                continue
            permanent = (exc.code not in _RETRY_HTTP) or any(s in low for s in _PERMANENT_SIGNALS)
            if permanent:
                _status_mark("gemini", False, detail)
                _log_warn(f"[_gemini] {detail} — kalıcı (retry yok): {body_txt[:200]}")
                return None
            last_exc = exc  # geçici (429/503/5xx) → retry
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_exc = exc
        if attempt < retries - 1:
            time.sleep(2 ** attempt)  # 1s, 2s, 4s

    _log_warn(f"[_gemini] tüm denemeler tükendi ({retries}x): {type(last_exc).__name__}: {last_exc}")
    return None


def _log_warn(msg: str) -> None:
    import sys
    print(msg, file=sys.stderr)
