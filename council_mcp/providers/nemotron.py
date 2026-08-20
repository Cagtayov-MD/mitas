"""
Nemotron-3 Ultra provider (NVIDIA Build / NIM, OpenAI-uyumlu uç).

Model: nvidia/nemotron-3-ultra-550b-a55b — 550B hibrit Mamba-Transformer MoE,
1M bağlam. Konseydeki değeri: mevcut üyelerin hiçbiriyle mimari akrabalığı yok
(farklı mimari = farklı kör nokta).

Erişim: build.nvidia.com ücretsiz katmanı (nvapi- anahtarı). Kota rate-limit
tabanlı (~40 istek/dk/model, resmi taahhüt değil); aşımda HTTP 402/429 döner —
_retry zaten 3 deneme yapar, kalıcı aşımda üye o tur hata olarak raporlanır.

DİKKAT: Ücretsiz uçlar NVIDIA kataloğunda kalıcı değil — model kaldırılır ya da
ücretliye geçerse NVIDIA_MODEL ile katalogdaki başka bir modele geçilebilir,
kod değişmez.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "NVIDIA_API_KEY"
BASE_URL_ENV = "NVIDIA_BASE_URL"
MODEL_ENV = "NVIDIA_MODEL"  # .env'den model override - kod degismeden
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
TIMEOUT_SECONDS = 180.0  # glm/qwen ile ayni gerekce: reasoning uzun, 60sn yetmiyor


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
            check_response(response, provider_name="Nemotron")
            data = response.json()

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Beklenmeyen Nemotron cevap formatı: {data}") from exc

        # Thinking-modeli kemeri (Kimi/Qwen dersi): content boş gelirse cevap
        # reasoning_content'te kalmış olabilir — boş dönmektense onu kullan.
        content = message.get("content") or ""
        if not content.strip():
            content = message.get("reasoning_content") or ""
        if not content.strip():
            raise RuntimeError(f"Nemotron boş cevap döndü: {data}")
        return content

    return await with_retry(_call, provider_name="Nemotron")
