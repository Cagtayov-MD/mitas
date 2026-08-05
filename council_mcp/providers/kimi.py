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
TIMEOUT_SECONDS = 420.0  # k3 düşünen model: uzun kırmızı-takım brifinglerinde 180sn'de
# düşünme bitmiyor (boş-str'li httpx.ReadTimeout → tur boş dönüyordu, 2026-07-23 teşhisi)


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
                message = data["choices"][0]["message"]
            except (KeyError, IndexError) as exc:
                raise RuntimeError(f"Beklenmeyen Kimi cevap formatı: {data}") from exc

            # Thinking-modeli kemeri (minimax.py/nemotron.py ile ayni): content
            # bos gelirse cevap reasoning_content'te kalmis olabilir.
            content = message.get("content") or ""
            if not content.strip():
                content = message.get("reasoning_content") or ""
            if not content.strip():
                raise RuntimeError(f"Kimi boş cevap döndü: {data}")
            return content

        return _call

    try:
        return await with_retry(_yap(model), provider_name="Kimi K3")
    except Exception as exc:
        # aşırı-yük/429 VEYA zaman aşımı durumunda alt modele tek şans.
        # k3 düşünen model: uzun konsey brifinglerinde düşünme süresi timeout'u
        # aşıyor ve httpx.TimeoutException'ın str()'i BOŞ olduğundan eski
        # "429/overload" metin koşulu hiç tetiklenmiyordu → tur boş dönüyordu.
        s = str(exc)
        zaman_asimi = isinstance(exc, httpx.TimeoutException) or (
            exc.__cause__ is not None and isinstance(exc.__cause__, httpx.TimeoutException)
        ) or not s.strip() or "timeout" in s.lower() or "timed out" in s.lower()
        if fallback and fallback != model and ("429" in s or "overload" in s.lower() or zaman_asimi):
            cevap = await with_retry(_yap(fallback), provider_name=f"Kimi ({fallback} yedek)")
            sebep = "zaman aşımı (düşünme süresi)" if zaman_asimi else "aşırı yüklü"
            return f"[not: kimi-k3 {sebep}, cevap {fallback} yedeğinden]\n\n{cevap}"
        raise
