"""
GPT-OSS-120B provider (NVIDIA Build / NIM üzerinden, OpenAI-uyumlu uç).

Model: openai/gpt-oss-120b — OpenAI'nin açık-ağırlıklı MoE modeli.
Konsey gerekçesi (2026-08-14): konseyin en yüksek KÖR NOKTA değeri olan üye.
Kalan üyeler (GLM=Zhipu, Nemotron=NVIDIA) ile tamamen farklı bir eğitim
geleneğinden geliyor — CLAUDE.md "aynı soruyu 3 özdeş gözle sordurma"
kuralının doğrudan karşılığı. Ayrıca OPENAI_API_KEY koltuğu boş olduğu için
GPT ailesi konseyde hiç temsil edilmiyordu; bu üye o boşluğu NVIDIA
anahtarıyla, ayrı abonelik gerekmeden dolduruyor.

Yoklama (2026-08-14): 141−(20+20+7) aritmetik testini geçti → "94".

Erişim: Nemotron ile AYNI NVIDIA_API_KEY. Model GPTOSS_MODEL ile,
uç NVIDIA_BASE_URL ile override edilebilir.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "NVIDIA_API_KEY"     # Nemotron ile paylasilan anahtar
BASE_URL_ENV = "NVIDIA_BASE_URL"
MODEL_ENV = "GPTOSS_MODEL"         # .env'den model override - kod degismeden
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "openai/gpt-oss-120b"      # /models + canli cagri ile teyitli (2026-08-14)
# minimax.py/kimi.py ile ayni gerekce: dusunen modeller ~8 KB konsey
# brifinglerinde 180sn'yi asabiliyor -> ReadTimeout -> tur "bos cevap" gorunuyor.
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
            check_response(response, provider_name="GPT-OSS-120B")
            data = response.json()

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Beklenmeyen GPT-OSS cevap formatı: {data}") from exc

        # Thinking-modeli kemeri (nemotron.py ile ayni): content bos gelirse
        # cevap reasoning_content'te kalmis olabilir.
        content = message.get("content") or ""
        if not content.strip():
            content = message.get("reasoning_content") or ""
        if not content.strip():
            raise RuntimeError(f"GPT-OSS boş cevap döndü: {data}")
        return content

    return await with_retry(_call, provider_name="GPT-OSS-120B")
