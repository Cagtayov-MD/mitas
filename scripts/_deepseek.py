# -*- coding: utf-8 -*-
"""MITAS DeepSeek API wrapper (OpenAI-uyumlu chat/completions).

Anahtar: MITAS_DEEPSEEK env (yoksa DEEPSEEK_API_KEY). Anahtar yoksa None doner —
cagiran skip/fallback yapar (asla cokmez). Anahtar KODA GOMULMEZ; User env'de saklanir.

Kullanim (cagri yeri SONRA belirlenecek — bu sadece istemci):
    from _deepseek import deepseek_text, deepseek_chat

    txt = deepseek_text(prompt="...", model="deepseek-chat", max_tokens=800)
    # ya da ham yanit:
    resp = deepseek_chat(messages=[{"role":"user","content":"..."}], fmt={"type":"json_object"})

Modeller: "deepseek-chat" (V3, varsayilan), "deepseek-reasoner" (R1).
Endpoint OpenAI-uyumlu: POST {base}/chat/completions, Authorization: Bearer.

Env:
    MITAS_DEEPSEEK / DEEPSEEK_API_KEY  — API anahtari (zorunlu; yoksa None)
    MITAS_DEEPSEEK_BASE                — base URL (default https://api.deepseek.com)
    MITAS_DEEPSEEK_TIMEOUT             — HTTP timeout sn (default 120)

Retry: 429/5xx -> retry (exponential backoff 1s/2s); diger 4xx -> hemen None.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


def deepseek_chat(
    prompt: str | None = None,
    messages: list[dict] | None = None,
    model: str = "deepseek-chat",
    temperature: float | None = None,
    max_tokens: int | None = None,
    fmt: Any = None,            # response_format, orn {"type": "json_object"}
    timeout: int | None = None,
    retries: int = 2,
    **extra,
) -> dict | None:
    """DeepSeek chat/completions cagrisi. Basarisizsa / anahtar yoksa None.

    prompt verilirse tek-tur user mesajina cevrilir; messages dogrudan iletilir.
    Donus: OpenAI-uyumlu ham JSON (choices[0].message.content ...) veya None.
    """
    key = os.environ.get("MITAS_DEEPSEEK") or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None

    base = os.environ.get("MITAS_DEEPSEEK_BASE", "https://api.deepseek.com").rstrip("/")
    url = base + "/chat/completions"
    _timeout = timeout if timeout is not None else int(
        os.environ.get("MITAS_DEEPSEEK_TIMEOUT", "120")
    )

    if messages is None:
        if prompt is None:
            raise ValueError("deepseek_chat: 'prompt' veya 'messages' gerekli")
        messages = [{"role": "user", "content": prompt}]

    payload: dict = {"model": model, "messages": messages, "stream": False}
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if fmt is not None:
        payload["response_format"] = fmt
    payload.update(extra)

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )

    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with urllib.request.urlopen(req, timeout=_timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            # 429 / 5xx gecicidir -> retry; diger 4xx (400/401/403 ...) kalici -> hemen None
            if exc.code not in (429, 500, 502, 503, 504):
                _log_warn(f"[_deepseek] HTTP {exc.code} {exc.reason} — retry yok (kalici hata)")
                return None
            last_exc = exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_exc = exc
        if attempt < retries - 1:
            time.sleep(2 ** attempt)   # 1s, 2s

    _log_warn(f"[_deepseek] tum denemeler tukendi ({retries}x): "
              f"{type(last_exc).__name__}: {last_exc}")
    return None


def deepseek_text(
    prompt: str | None = None,
    messages: list[dict] | None = None,
    **kw,
) -> str | None:
    """Kolaylik: yalniz yanit metnini dondurur (choices[0].message.content) veya None."""
    resp = deepseek_chat(prompt=prompt, messages=messages, **kw)
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001
        return None


def _log_warn(msg: str) -> None:
    import sys
    print(msg, file=sys.stderr)
