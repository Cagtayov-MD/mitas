# -*- coding: utf-8 -*-
"""URL-düzeyi disk önbelleği (hız #2+#3, 2026-07-05).

Amaç: film başına gidilen TMDB/OMDb/Wikipedia/IMDb-suggestion sorguları OCR∥ASR boş
penceresinde ÖN-ISITILIR (web_isit.py doldurur); gerçek tüketiciler (poster_fetch,
credit_qc_gates.web_identity, credit_identity) aynı URL'yi diskten ~0 sn'de okur.

DOĞRULUK-NÖTR: yalnız HTTP yanıt gövdesi saklanır — kimlik/afiş KARAR mantığı değişmez.
Yalnız BAŞARILI yanıt cache'lenir (HTTP hata davranışı aynen korunur). Dosya adı = sha1(url)
→ api_key diske sızmaz. Atomik yazım (tmp + os.replace) → eşzamanlı süreçler güvenli.

Kapatma: MITAS_WEB_CACHE=0. TTL: MITAS_WEB_CACHE_TTL sn (default 21600 = 6 saat).
"""
from __future__ import annotations
import hashlib
import os
import time

_DIR = os.environ.get("MITAS_WEB_CACHE_DIR", r"E:\MITAS\cache\web")


def enabled() -> bool:
    return os.environ.get("MITAS_WEB_CACHE", "1").strip().lower() not in ("0", "false", "off", "no")


def _path(url: str) -> str:
    return os.path.join(_DIR, hashlib.sha1(url.encode("utf-8")).hexdigest() + ".bin")


def get(url: str):
    """Taze cache girdisi varsa bytes döndür; yoksa/bayatsa/kapalıysa None. ASLA raise etmez."""
    if not enabled():
        return None
    try:
        p = _path(url)
        ttl = int(os.environ.get("MITAS_WEB_CACHE_TTL", "21600") or 21600)
        if os.path.exists(p) and (time.time() - os.path.getmtime(p)) < ttl:
            with open(p, "rb") as f:
                return f.read()
    except Exception:  # noqa: BLE001 — cache hatası HTTP akışını ASLA bozmaz
        pass
    return None


def put(url: str, data: bytes) -> None:
    """Başarılı yanıt gövdesini cache'e yaz. ASLA raise etmez."""
    if not enabled() or data is None:
        return
    try:
        os.makedirs(_DIR, exist_ok=True)
        p = _path(url)
        tmp = f"{p}.tmp{os.getpid()}"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, p)
    except Exception:  # noqa: BLE001
        pass
