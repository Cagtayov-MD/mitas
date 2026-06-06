# -*- coding: utf-8 -*-
"""MITAS merkezi Ollama HTTP wrapper — 1.6.

Kullanim:
    from _ollama import ollama_chat

    # /api/generate (tek-tur, GLM-OCR / qwen-QC / kunye-qwen gibi)
    resp = ollama_chat(model="glm-ocr:latest", prompt="...", images=[b64], timeout=120)

    # /api/chat (coklu kare / video-ensemble, credit_video_read gibi)
    resp = ollama_chat(model="gemma4:26b", messages=[{"role":"user","content":"...", "images":[...]}])

Donusler:
    dict  — basarili HTTP 200 JSON gövdesi
    None  — ollama erisilemediyse veya tum denemeler tukendiyse (cagiran skip/fallback yapar)

API secimi:
    messages  verildiyse  -> /api/chat     (resp["message"]["content"])
    prompt    verildiyse  -> /api/generate (resp["response"])

Retry politikasi:
    retries=2 (varsayilan): ilk + 1 tekrar
    Sadece baglanti / timeout hatasinda retry (OSError/URLError/socket.timeout).
    HTTP 4xx/5xx -> hemen None (retry etme; model yok / format hatasi).
    Denemeler arasi: 1s, 2s (exponential backoff).

Timeout:
    timeout parametresi yoksa os.environ["MITAS_OLLAMA_TIMEOUT"] (default 300 saniye).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import socket
from typing import Any


def ollama_chat(
    model: str,
    prompt: str | None = None,
    messages: list[dict] | None = None,
    images: list[str] | None = None,
    fmt: Any = None,           # format: "json" veya JSON-schema dict
    timeout: int | None = None,
    retries: int = 2,
    host: str = "http://localhost:11434",
    # ek payload alanlari (think, keep_alive, options …)
    **extra,
) -> dict | None:
    """Merkezi Ollama HTTP cagrisi. Basarisizsa None dondurur.

    Parametreler
    ------------
    model     : ollama model adi
    prompt    : /api/generate icin tek tur metin
    messages  : /api/chat icin mesaj listesi
    images    : base64-kodlu gorsel listesi
                  /api/generate'de payload["images"] olarak eklenir
                  /api/chat'te messages[-1]["images"] olarak eklenir (zaten yoksa)
    fmt       : format alani ("json" | schema dict)
    timeout   : HTTP timeout saniye; None ise MITAS_OLLAMA_TIMEOUT env (default 300)
    retries   : maksimum deneme sayisi (>=1)
    host      : ollama base URL
    **extra   : payload'a dogrudan eklenir (think, keep_alive, options, stream, ...)
    """
    _timeout = timeout if timeout is not None else int(
        os.environ.get("MITAS_OLLAMA_TIMEOUT", "300")
    )

    if messages is not None:
        url = host.rstrip("/") + "/api/chat"
        # images varsa son mesaja ekle (yoksa)
        payload: dict = {"model": model, "messages": messages, "stream": False}
        if images and not messages[-1].get("images"):
            payload["messages"] = list(messages)
            payload["messages"][-1] = dict(payload["messages"][-1], images=images)
    elif prompt is not None:
        url = host.rstrip("/") + "/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}
        if images:
            payload["images"] = images
    else:
        raise ValueError("ollama_chat: 'prompt' veya 'messages' gerekli")

    if fmt is not None:
        payload["format"] = fmt

    # extra alanlar (think, keep_alive, options, ...)
    payload.update(extra)

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )

    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with urllib.request.urlopen(req, timeout=_timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            # 4xx / 5xx: retry etme, hemen None
            _log_warn(
                f"[_ollama] HTTP {exc.code} {exc.reason} (model={model}, url={url}) — retry yok"
            )
            return None
        except (urllib.error.URLError, OSError, socket.timeout, TimeoutError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                wait = 2 ** attempt   # 1s, 2s
                _log_warn(
                    f"[_ollama] deneme {attempt + 1}/{retries} basarisiz "
                    f"({type(exc).__name__}: {exc}) — {wait}s bekle"
                )
                time.sleep(wait)

    _log_warn(
        f"[_ollama] tum denemeler tukendi ({retries}x) model={model}: "
        f"{type(last_exc).__name__}: {last_exc}"
    )
    return None


# ---------------------------------------------------------------------------
def _log_warn(msg: str) -> None:
    import sys
    print(msg, file=sys.stderr)
