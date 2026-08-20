"""
Inkling provider (NVIDIA Build / NIM üzerinden, OpenAI-uyumlu uç).

Model: thinkingmachines/inkling — Thinking Machines'in modeli.
Konsey gerekçesi (2026-08-14): TAZE AKIL koltuğu. CLAUDE.md dış konseyin
görevini "kör nokta yakalama, taze akıl, eleştiri" diye tanımlıyor; kalan
üyelerin hepsi (GLM, Nemotron, GPT-OSS, DeepSeek) tanıdık ailelerden. Bu üye
bilinçli olarak DENENMEMİŞ bir bakış — getirisi ölçülecek.

DENEME SÜRÜMÜ: katkısı iki-üç turda tartılacak. Sığ "evet bence de" üretirse
CLAUDE.md'nin "o tur başarısız sayılır" kuralı uyarınca koltuk boşaltılır;
yerine `meta/llama-3.3-70b-instruct` veya `stepfun-ai/step-3.7-flash` gelir
(ikisi de 2026-08-14 yoklamasında çalışır durumdaydı, aritmetiği geçtiler).

Yoklama (2026-08-14): 141−(20+20+7) aritmetik testini geçti → "94".

Erişim: Nemotron ile AYNI NVIDIA_API_KEY. Model INKLING_MODEL ile,
uç NVIDIA_BASE_URL ile override edilebilir.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "NVIDIA_API_KEY"     # Nemotron ile paylasilan anahtar
BASE_URL_ENV = "NVIDIA_BASE_URL"
MODEL_ENV = "INKLING_MODEL"        # .env'den model override - kod degismeden
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "thinkingmachines/inkling"  # canli cagri ile teyitli (2026-08-14)
TIMEOUT_SECONDS = 420.0


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
            check_response(response, provider_name="Inkling")
            data = response.json()

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Beklenmeyen Inkling cevap formatı: {data}") from exc

        # Thinking-modeli kemeri (nemotron.py ile ayni): content bos gelirse
        # cevap reasoning_content'te kalmis olabilir.
        content = message.get("content") or ""
        if not content.strip():
            content = message.get("reasoning_content") or ""
        if not content.strip():
            raise RuntimeError(f"Inkling boş cevap döndü: {data}")
        return content

    return await with_retry(_call, provider_name="Inkling")
