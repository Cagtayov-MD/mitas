"""
Qwen 3.7 Max provider (Alibaba Cloud / DashScope, OpenAI-uyumlu uç).

DİKKAT: DEFAULT_BASE_URL, DashScope'un OpenAI-uyumlu modu için genel
adres. Alibaba hesabının bölgesine (uluslararası / Çin) göre bu adres
değişebilir - key'i eklemeden önce Alibaba Cloud Model Studio
konsolundan kendi hesabın için doğru base URL'i teyit et. Gerekirse
.env'e QWEN_BASE_URL olarak override edebilirsin, kod değişmeden çalışır.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "QWEN_API_KEY"
BASE_URL_ENV = "QWEN_BASE_URL"
MODEL_ENV = "QWEN_MODEL"  # .env'den model override (orn. qwen3.8-max) - kod degismeden
DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3.7-max"
TIMEOUT_SECONDS = 180.0  # 2026-07-09: 60sn uzun konsey sorularında yetmiyor (model reasoning'i uzun); 3-deneme hep timeout'tu


def is_configured() -> bool:
    return bool(os.getenv(API_KEY_ENV))


async def ask(question: str, context: str = "") -> str:
    api_key = os.getenv(API_KEY_ENV)
    base_url = os.getenv(BASE_URL_ENV, DEFAULT_BASE_URL)
    model = os.getenv(MODEL_ENV, MODEL)
    prompt = f"{context}\n\n{question}" if context else question

    async def _call() -> str:
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base_url}/chat/completions", headers=headers, json=payload
            )
            check_response(response, provider_name="Qwen 3.7 Max")
            data = response.json()

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Beklenmeyen Qwen cevap formatı: {data}") from exc

        # Thinking-modeli kemeri (minimax.py/nemotron.py ile ayni): content bos
        # gelirse cevap reasoning_content'te kalmis olabilir.
        content = message.get("content") or ""
        if not content.strip():
            content = message.get("reasoning_content") or ""
        if not content.strip():
            raise RuntimeError(f"Qwen boş cevap döndü: {data}")
        return content

    return await with_retry(_call, provider_name="Qwen 3.7 Max")
