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

# Kredi/erisim durumu kaydi (best-effort). Import patlarsa _deepseek calismaya devam eder.
try:
    import _api_status  # ayni scripts/ dizininde
except Exception:  # noqa: BLE001 - sys.path'te degilse modul-yolu ile dene
    try:
        import importlib.util as _ilu
        _asp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_api_status.py")
        _spec = _ilu.spec_from_file_location("_api_status", _asp)
        _api_status = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_api_status)
    except Exception:  # noqa: BLE001 - hala yoksa no-op stub (mark/read_all cokme yok)
        _api_status = None


def _status_mark(api: str, ok: bool, detail: str = "") -> None:
    """_api_status.mark guvenli sarmal — modul yoksa/patlarsa sessiz."""
    try:
        if _api_status is not None:
            _api_status.mark(api, ok, detail)
    except Exception:  # noqa: BLE001
        pass


# Kalici (retry'siz) HTTP kodlari: 401 yetki, 402 kredi-bitti, 403 yasak.
_PERMANENT_HTTP = {401, 402, 403}
# Yanit/gerekce metninde kredi-tukenmesi sinyalleri (kuckuk harf eslesme).
_CREDIT_SIGNALS = ("insufficient", "balance", "quota")

# NVIDIA Build yedek ucu (2026-07-23): DeepSeek ozet zincirinin BIRINCIL motoru
# yapildi; resmi uc kota/kesinti yasarsa ozet dogrudan gemma-yerel'e dusuyordu
# (bake-off: yerel modeller guvenilir Turkce ozet veremiyor). NVIDIA ayni model
# ailesini ucretsiz uctan sunuyor -> ikinci erisim yolu.
# Model secimi (anahtar_test /models teyidi 2026-07-23): katalogda v3.2 YOK;
# deepseek-v4-pro (amiral) ve deepseek-v4-flash (hizli) var. Varsayilan: v4-pro
# (birincil motora kalite paritesi). 90sn ozet timeout'unda pro gecikirse
# MITAS_DEEPSEEK_NVIDIA_MODEL=deepseek-ai/deepseek-v4-flash ile dusur.
# Anahtar yoksa fallback sessizce devre disi - davranis eskisiyle AYNI kalir.
_NVIDIA_DEFAULT_BASE = "https://integrate.api.nvidia.com/v1"
_NVIDIA_DEFAULT_MODEL = "deepseek-ai/deepseek-v4-pro"


def _nvidia_key() -> str | None:
    return os.environ.get("MITAS_NVIDIA") or os.environ.get("NVIDIA_API_KEY")


def _post_chat(url: str, key: str, payload: dict, timeout: int,
               retries: int, api_label: str) -> dict | None:
    """Tek uca chat/completions POST + retry. Basarisizsa None (cagiran fallback yapar)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )

    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read())
            _status_mark(api_label, True)   # basarili yanit -> ok
            return resp
        except urllib.error.HTTPError as exc:
            reason = str(getattr(exc, "reason", "") or "")
            # Gerekce + govde metninde kredi/kota sinyali var mi? (429 da kota olabilir)
            body_txt = ""
            try:
                body_txt = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                body_txt = ""
            credit_hit = any(sig in (reason + " " + body_txt).lower() for sig in _CREDIT_SIGNALS)
            detail = f"HTTP {exc.code} {reason}".strip()
            # KALICI hata (401/402/403 ya da kredi-sinyali): retry YOK, durumu error isaretle, hemen None.
            # 402 = kredi bitti -> burada yakalanir (eski liste 429/5xx idi, 402 yanlislikla "kalici-sessiz"di).
            if exc.code in _PERMANENT_HTTP or credit_hit:
                _log_warn(f"[{api_label}] {detail} — kalici hata (retry yok), durum: error")
                _status_mark(api_label, False, detail)
                return None
            # 429 / 5xx gecici -> retry; diger 4xx (400/404...) -> kalici ama kredi-disi, mark YOK.
            if exc.code not in (429, 500, 502, 503, 504):
                _log_warn(f"[{api_label}] {detail} — retry yok (kalici hata)")
                return None
            last_exc = exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last_exc = exc
        if attempt < retries - 1:
            time.sleep(2 ** attempt)   # 1s, 2s

    _log_warn(f"[{api_label}] tum denemeler tukendi ({retries}x): "
              f"{type(last_exc).__name__}: {last_exc}")
    return None


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

    Siralama: birincil uc (api.deepseek.com, MITAS_DEEPSEEK) -> basarisizsa
    NVIDIA Build yedek ucu (NVIDIA_API_KEY/MITAS_NVIDIA varsa). Ikisi de yoksa
    ya da ikisi de duserse None.
    """
    key = os.environ.get("MITAS_DEEPSEEK") or os.environ.get("DEEPSEEK_API_KEY")
    nv_key = _nvidia_key()
    if not key and not nv_key:
        return None

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

    if key:
        base = os.environ.get("MITAS_DEEPSEEK_BASE", "https://api.deepseek.com").rstrip("/")
        resp = _post_chat(base + "/chat/completions", key, payload,
                          _timeout, retries, "deepseek")
        if resp is not None:
            return resp

    if nv_key:
        if key:
            _log_warn("[_deepseek] birincil uc basarisiz — NVIDIA yedek uca geciliyor")
        nv_base = os.environ.get("MITAS_DEEPSEEK_NVIDIA_BASE", _NVIDIA_DEFAULT_BASE).rstrip("/")
        nv_payload = dict(payload)
        nv_payload["model"] = os.environ.get("MITAS_DEEPSEEK_NVIDIA_MODEL", _NVIDIA_DEFAULT_MODEL)
        return _post_chat(nv_base + "/chat/completions", nv_key, nv_payload,
                          _timeout, retries, "deepseek_nvidia")

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
