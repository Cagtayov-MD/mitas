# -*- coding: utf-8 -*-
"""MITAS — dis API durum kaydi (kredi/erisim uyarisi icin ortak temel).

Amac: DeepSeek / TMDB gibi dis servislerin son cagri durumunu (ok/hata) ATOMIK
JSON'a yazip UI/araclarin "anahtar bitti / kredi yok" uyarisi gosterebilmesi.

KURAL: bu modul ASLA cokmez — tum hatalar yutulur (mark sessizce dondurur,
read_all bos {} doner). Cagiran kod (_deepseek vb.) bunu best-effort kullanir.

Dosya: E:\\MITAS\\outputs\\api_status.json
  {api: {"ok": bool, "detail": str, "ts": "<ISO-UTC>"}}
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

# outputs/api_status.json — bu dosya scripts/ altinda, outputs kardes dizin.
_OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
_STATUS_PATH = os.path.join(_OUT_DIR, "api_status.json")


def read_all() -> dict:
    """api_status.json'u oku. Yoksa/bozuksa/hata -> {} (asla cokme)."""
    try:
        with open(_STATUS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - dosya yok/bozuk/izin -> bos
        return {}


def mark(api: str, ok: bool, detail: str = "") -> None:
    """api icin durumu ATOMIK (temp + os.replace) MERGE yaz. Tum hatalari yut.

    Mevcut diger api kayitlari korunur; yalniz verilen `api` anahtari guncellenir.
    """
    try:
        if not api:
            return
        cur = read_all()
        cur[api] = {
            "ok": bool(ok),
            "detail": str(detail or ""),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        os.makedirs(_OUT_DIR, exist_ok=True)
        # ayni dizine temp yaz -> os.replace ATOMIK (kismi/bozuk dosya birakmaz)
        fd, tmp = tempfile.mkstemp(dir=_OUT_DIR, prefix=".api_status_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(cur, f, ensure_ascii=False, indent=2)
            os.replace(tmp, _STATUS_PATH)
        finally:
            # replace basarisizsa temp'i temizle
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001 - durum kaydi best-effort; asla cokme
        return
