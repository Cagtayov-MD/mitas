# -*- coding: utf-8 -*-
"""UI 'Check' tusu icin AKTIF saglik probu: Anthropic + DeepSeek + KB(IMDb).

PY_PDF (global310) ile kosar — urllib + _deepseek + duckdb(KB) hepsi burada mevcut.
asr_server (venvs/asr) bunu subprocess ile cagirir (duckdb orada YOK).

Cikti: TEK-SATIR JSON
    {"anthropic":{ok,detail}, "deepseek":{ok,detail}, "kb":{ok,detail}}

ASLA anahtar DEGERI basmaz. Her prob bagimsiz try/except — biri patlasa digerleri doner.
Anthropic/DeepSeek pingleri MINIMAL (max_tokens=1) — kredi/kota/erisim dogrular, icerik degil."""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_CREDIT_SIGNALS = ("credit", "balance", "quota", "insufficient", "too low")


def probe_anthropic() -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"ok": False, "detail": "ANTHROPIC_API_KEY yok"}
    model = os.environ.get("MITAS_ANTHROPIC_MODEL", "claude-sonnet-4-6")
    body = {"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            json.loads(r.read().decode("utf-8"))
        return {"ok": True, "detail": "Claude API erisim OK"}
    except urllib.error.HTTPError as exc:
        code = int(getattr(exc, "code", 0) or 0)
        try:
            body_txt = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            body_txt = ""
        low = (str(getattr(exc, "reason", "")) + " " + body_txt).lower()
        if code == 401:
            return {"ok": False, "detail": "API anahtari gecersiz (401)"}
        if code in (402, 429) or any(s in low for s in _CREDIT_SIGNALS):
            return {"ok": False, "detail": f"kredi/kota sorunu (HTTP {code})"}
        return {"ok": False, "detail": f"HTTP {code}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"erisim hatasi: {type(exc).__name__}"}


def probe_deepseek() -> dict:
    if not (os.environ.get("MITAS_DEEPSEEK") or os.environ.get("DEEPSEEK_API_KEY")):
        return {"ok": False, "detail": "DeepSeek anahtari yok"}
    try:
        from _deepseek import deepseek_text  # kendi icinde api_status'a da yazar
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"_deepseek yuklenemedi: {type(exc).__name__}"}
    try:
        txt = deepseek_text(prompt="ping",
                            model=os.environ.get("MITAS_DEEPSEEK_MODEL", "deepseek-chat"),
                            temperature=0, max_tokens=1, timeout=15)
        if txt is not None:
            return {"ok": True, "detail": "DeepSeek API erisim OK"}
        # Basarisiz: _deepseek api_status'a GERCEK detayi yazdi (orn 'HTTP 402 Payment Required') -> oku.
        detail = "yanit yok (anahtar/kredi/kota?)"
        try:
            import _api_status  # type: ignore
            ds = _api_status.read_all().get("deepseek") or {}
            if ds.get("detail"):
                detail = str(ds["detail"])
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "detail": detail}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"erisim hatasi: {type(exc).__name__}"}


def probe_kb() -> dict:
    try:
        from credit_video_read import KB
        verdict = KB().verify("Steven Spielberg", "director")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"KB yuklenemedi: {type(exc).__name__}"}
    if verdict == "ONAY":
        return {"ok": True, "detail": "IMDb KB canli (Steven Spielberg -> director ONAY)"}
    if verdict == "kayit-yok":
        return {"ok": False, "detail": "KB OLU: baglanti yok (duckdb? Y: surucu? DB kilit/surum?)"}
    return {"ok": False, "detail": f"beklenmeyen KB yaniti: {verdict}"}


if __name__ == "__main__":
    print(json.dumps(
        {"anthropic": probe_anthropic(), "deepseek": probe_deepseek(), "kb": probe_kb()},
        ensure_ascii=False))
