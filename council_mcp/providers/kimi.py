"""
Kimi K3 provider (Moonshot AI, OpenAI-uyumlu uç).

DİKKAT: DEFAULT_BASE_URL, Moonshot'un uluslararası ucu. Çin-bölgesi
hesap kullanıyorsan api.moonshot.cn gerekebilir - key'i eklemeden önce
Moonshot konsolundan kendi hesabın için doğru base URL'i teyit et.
Gerekirse .env'e KIMI_BASE_URL olarak override edebilirsin, kod
değişmeden çalışır. Model adı da KIMI_MODEL ile override edilebilir.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "KIMI_API_KEY"
BASE_URL_ENV = "KIMI_BASE_URL"
MODEL_ENV = "KIMI_MODEL"
FALLBACK_MODEL_ENV = "KIMI_FALLBACK_MODEL"
DEFAULT_BASE_URL = "https://api.moonshot.ai/v1"
DEFAULT_MODEL = "kimi-k3"
# k3 Moonshot tarafında sık "engine overloaded" (429) veriyor (2026-07-21..23 boyunca
# konsey turlarını kaçırdı). Cevapsız kalmaktansa bir alt modele düş — k3 BİRİNCİL kalır.
DEFAULT_FALLBACK_MODEL = "kimi-k2.6"
TIMEOUT_SECONDS = 180.0  # qwen.py/glm.py ile ayni gerekce: uzun konsey sorularinda 60sn yetmiyor


def is_configured() -> bool:
    return bool(os.getenv(API_KEY_ENV))


async def ask(question: str, context: str = "") -> str:
    api_key = os.getenv(API_KEY_ENV)
    base_url = os.getenv(BASE_URL_ENV, DEFAULT_BASE_URL)
    model = os.getenv(MODEL_ENV, DEFAULT_MODEL)
    fallback = os.getenv(FALLBACK_MODEL_ENV, DEFAULT_FALLBACK_MODEL)
    prompt = f"{context}\n\n{question}" if context else question

    def _yap(kullanilacak_model: str):
        async def _call() -> str:
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": kullanilacak_model,
                "messages": [{"role": "user", "content": prompt}],
            }

            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{base_url}/chat/completions", headers=headers, json=payload
                )
                check_response(response, provider_name="Kimi K3")
                data = response.json()

            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as exc:
                raise RuntimeError(f"Beklenmeyen Kimi cevap formatı: {data}") from exc

        return _call

    try:
        return await with_retry(_yap(model), provider_name="Kimi K3")
    except Exception as exc:
        # yalnız aşırı-yük/429 durumunda alt modele tek şans; başka hatalar aynen yükselir
        if fallback and fallback != model and ("429" in str(exc) or "overload" in str(exc).lower()):
            cevap = await with_retry(_yap(fallback), provider_name=f"Kimi ({fallback} yedek)")
            return f"[not: kimi-k3 aşırı yüklü, cevap {fallback} yedeğinden]\n\n{cevap}"
        raise
