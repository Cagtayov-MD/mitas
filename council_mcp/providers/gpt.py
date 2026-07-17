"""
GPT-5.5 provider (OpenAI resmi API).

Endpoint sabit ve resmi - bölgeye göre değişmiyor, doğrulamana gerek yok.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "OPENAI_API_KEY"
MODEL = "gpt-5.5"
TIMEOUT_SECONDS = 60.0

_ENDPOINT = "https://api.openai.com/v1/chat/completions"


def is_configured() -> bool:
    return bool(os.getenv(API_KEY_ENV))


async def ask(question: str, context: str = "") -> str:
    api_key = os.getenv(API_KEY_ENV)
    prompt = f"{context}\n\n{question}" if context else question

    async def _call() -> str:
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(_ENDPOINT, headers=headers, json=payload)
            check_response(response, provider_name="GPT-5.5")
            data = response.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Beklenmeyen GPT-5.5 cevap formatı: {data}") from exc

    return await with_retry(_call, provider_name="GPT-5.5")
