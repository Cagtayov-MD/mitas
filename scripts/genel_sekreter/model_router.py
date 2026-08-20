"""Model yönlendirici — görev adına göre model seçimi ve çağrı dispatch.

Tier sistemi:
  NONE   = saf Python (regex/istatistik), model çağrılmaz
  LIGHT  = qwen3:8b (5.2GB) — metin sınıflandırma
  MEDIUM = gemma4:26b (17GB) görsel, mistral-small3.2 metin
  HEAVY  = qwen3-vl:32b (20GB) — karmaşık analiz
  API    = council_mcp üzerinden bulut modeli
"""
from __future__ import annotations

import json
import urllib.request
from enum import Enum
from typing import Any

from genel_sekreter.config import OLLAMA_BASE, COUNCIL_DIR


class Tier(str, Enum):
    NONE = "none"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"
    API = "api"


MODEL_TABLE: dict[str, dict[str, Any]] = {
    # KONTROL analiz
    "kontrol_parse": {"tier": Tier.NONE, "model": None},
    "kontrol_classify": {
        "tier": Tier.LIGHT, "model": "qwen3:8b",
        "num_ctx": 4096, "num_predict": 300, "temperature": 0.0,
    },
    "kontrol_root_cause": {
        "tier": Tier.HEAVY, "model": "qwen3-vl:32b",
        "num_ctx": 8192, "num_predict": 1000, "temperature": 0.1,
    },
    # ONAYLI QC
    "onayli_text_check": {
        "tier": Tier.LIGHT, "model": "qwen3:8b",
        "num_ctx": 4096, "num_predict": 300, "temperature": 0.0,
    },
    "onayli_visual_check": {
        "tier": Tier.MEDIUM, "model": "gemma4:26b",
        "num_ctx": 8192, "num_predict": 400, "temperature": 0.0,
    },
    # Performans (modelsiz)
    "performans_aggregation": {"tier": Tier.NONE, "model": None},
    # Hafıza
    "hafiza_lookup": {"tier": Tier.NONE, "model": None},
    "hafiza_similarity": {
        "tier": Tier.LIGHT, "model": "qwen3:8b",
        "num_ctx": 4096, "num_predict": 200, "temperature": 0.0,
    },
    # Araştırma
    "arastirma_api": {"tier": Tier.NONE, "model": None},
    # Secretary
    "gunluk_sentez": {
        "tier": Tier.API, "model": "qwen",
        "model_override": "qwen-plus",
        "api_hint": "Qwen-Plus — hafif, ucuz, sistem raporu özeti için yeterli",
    },
    "derin_kok_analiz": {
        "tier": Tier.API, "model": "qwen",
        "model_override": "qwen-plus",
        "api_hint": "Qwen-Plus — kök neden analizi, yaratıcılık gerektirmez",
    },
}


def resolve_model(task_name: str) -> dict[str, Any] | None:
    """Görev adına göre model bilgisi döndür. NONE/bilinmeyen → None."""
    entry = MODEL_TABLE.get(task_name)
    if entry is None or entry["tier"] == Tier.NONE:
        return None
    return entry


def call_model(
    task_name: str,
    prompt: str,
    context: str | None = None,
    images: list[str] | None = None,
) -> str:
    """Görev adına uygun modeli çağır, metin cevabı döndür.

    NONE tier → boş string (model çağrılmaz).
    """
    entry = resolve_model(task_name)
    if entry is None:
        return ""

    tier = entry["tier"]
    if tier in (Tier.LIGHT, Tier.MEDIUM, Tier.HEAVY):
        return _call_ollama(entry, prompt, context, images)
    elif tier == Tier.API:
        return _call_council_api(entry, prompt, context)
    return ""


def _call_ollama(
    entry: dict[str, Any],
    prompt: str,
    context: str | None,
    images: list[str] | None,
) -> str:
    """Ollama HTTP API üzerinden model çağrısı."""
    model = entry["model"]
    full_prompt = f"{context}\n\n{prompt}" if context else prompt

    message: dict[str, Any] = {"role": "user", "content": full_prompt}
    if images:
        message["images"] = images

    payload = {
        "model": model,
        "messages": [message],
        "stream": False,
        "think": False,
        "keep_alive": "5m",
        "options": {
            "temperature": entry.get("temperature", 0.0),
            "num_ctx": entry.get("num_ctx", 4096),
            "num_predict": entry.get("num_predict", 500),
        },
    }

    url = f"{OLLAMA_BASE}/api/chat"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("message", {}).get("content", "")
    except Exception as e:
        return f"[MODEL_HATA: {type(e).__name__}: {e}]"


def _call_council_api(
    entry: dict[str, Any],
    prompt: str,
    context: str | None,
) -> str:
    """Council MCP sağlayıcısı üzerinden API çağrısı."""
    import sys
    from pathlib import Path

    council_dir = Path(str(COUNCIL_DIR))
    if str(council_dir) not in sys.path:
        sys.path.insert(0, str(council_dir))

    provider_name = entry["model"]
    model_override = entry.get("model_override")
    try:
        from dotenv import load_dotenv
        load_dotenv(str(council_dir / ".env"), override=True)

        # Model override varsa env'e yaz (provider oradan okur)
        if model_override:
            import os
            os.environ["QWEN_MODEL"] = model_override

        providers_pkg = __import__("providers")
        provider_mod = getattr(providers_pkg, provider_name, None)
        if provider_mod is None:
            return f"[SAGLAYICI_BULUNAMADI: {provider_name}]"

        import asyncio
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        result = asyncio.run(provider_mod.ask(full_prompt, None))
        return result
    except Exception as e:
        return f"[API_HATA: {provider_name}: {type(e).__name__}: {e}]"
