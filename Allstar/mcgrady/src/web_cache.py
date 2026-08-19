# -*- coding: utf-8 -*-
"""URL-düzeyi disk önbelleği (hız #2+#3, 2026-07-05 kalıbının McGrady kule kopyası).

Amaç: film başına gidilen TMDB/OMDb/Wikipedia/IMDb-suggestion sorguları
gerektiğinde ÖN-ISITILABİLİR; gerçek tüketiciler (poster_fetch,
credit_qc_gates.web_identity) aynı URL'yi diskten ~0 sn'de okur.

DOĞRULUK-NÖTR: yalnız HTTP yanıt gövdesi saklanır — kimlik/afiş KARAR mantığı
değişmez. Yalnız BAŞARILI yanıt cache'lenir (HTTP hata davranışı aynen korunur).
Dosya adı = sha256(url) → api_key diske sızmaz. Atomik yazım (tmp +
os.replace) → eşzamanlı süreçler güvenli.

KULE FARKLARI (scripts/web_cache.py kopyasından bilinçli sapmalar):
  • önbellek dizini varsayılanı KULE-İÇİ cache/web (merkezi önbelleğe
    dosya-bağımlılık yok; main.py config değerini env'e yazar),
  • dosya adı sha1 → sha256 (güvenlik taraması; kule önbelleği yeni/boş
    olduğundan uyumluluk kaybı yok, doğruluk-nötr),
  • önbellek taban dizini env'den geliyorsa `..` içeremez; içerirse kule-içi
    varsayılana düşer (path-traversal kapalı).

Kapatma: MITAS_WEB_CACHE=0. TTL: MITAS_WEB_CACHE_TTL sn (default 21600 = 6 saat).
"""
from __future__ import annotations
import hashlib
import os
import time
from pathlib import Path

_KULE_KOKU = Path(__file__).resolve().parent.parent
_VARSAYILAN = _KULE_KOKU / "cache" / "web"


def _taban() -> Path:
    """Önbellek taban dizini: env'den gelen yol `..` parçası taşıyamaz."""
    aday = os.environ.get("MITAS_WEB_CACHE_DIR", "") or str(_VARSAYILAN)
    parcalar = Path(aday).parts
    if ".." in parcalar:
        return _VARSAYILAN
    return Path(aday).resolve()


_DIR = _taban()


def enabled() -> bool:
    return os.environ.get("MITAS_WEB_CACHE", "1").strip().lower() not in ("0", "false", "off", "no")


def _path(url: str) -> Path | None:
    """URL → önbellek dosya yolu. Yalnız sha256 hex adı; daima _DIR içinde kalır."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    aday = _DIR / (digest + ".bin")
    if not aday.is_relative_to(_DIR):
        return None
    return aday


def get(url: str):
    """Taze cache girdisi varsa bytes döndür; yoksa/bayatsa/kapalıysa None. ASLA raise etmez."""
    if not enabled():
        return None
    try:
        p = _path(url)
        if p is None:
            return None
        ttl = int(os.environ.get("MITAS_WEB_CACHE_TTL", "21600") or 21600)
        if p.exists() and (time.time() - p.stat().st_mtime) < ttl:
            return p.read_bytes()
    except Exception:  # noqa: BLE001 — cache hatası HTTP akışını ASLA bozmaz
        pass
    return None


def put(url: str, data: bytes) -> None:
    """Başarılı yanıt gövdesini cache'e yaz. ASLA raise etmez."""
    if not enabled() or data is None:
        return
    try:
        p = _path(url)
        if p is None:
            return
        _DIR.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f"{p.name}.tmp{os.getpid()}")
        tmp.write_bytes(data)
        os.replace(tmp, p)
    except Exception:  # noqa: BLE001
        pass
