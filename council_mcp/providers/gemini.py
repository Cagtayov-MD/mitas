"""
Gemini 3.5 Flash provider.

Bu dosya "referans implementasyon" - Qwen/GLM/GPT için stub'ları
doldururken buradaki kalıbı (is_configured / ask / with_retry) aynen
takip et.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "GEMINI_API_KEY"
MODEL = "gemini-3.5-flash"
TIMEOUT_SECONDS = 60.0

_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
)


def is_configured() -> bool:
    return bool(os.getenv(API_KEY_ENV))


async def ask(question: str, context: str = "") -> str:
    api_key = os.getenv(API_KEY_ENV)
    prompt = f"{context}\n\n{question}" if context else question

    async def _call() -> str:
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        params = {"key": api_key}

        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(_ENDPOINT, params=params, json=payload)
            check_response(response, provider_name="Gemini")
            data = response.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Beklenmeyen Gemini cevap formatı: {data}") from exc

    return await with_retry(_call, provider_name="Gemini")
