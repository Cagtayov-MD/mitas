"""
GLM-5.2 provider (Zhipu AI / Z.ai, OpenAI-uyumlu uç).

DİKKAT: DEFAULT_BASE_URL genel Zhipu adresi. Z.ai üzerinden global
erişim kullanıyorsan farklı bir base URL gerekebilir - key'i eklemeden
önce sağlayıcı panelinden doğru adresi teyit et. Gerekirse .env'e
GLM_BASE_URL olarak override edebilirsin, kod değişmeden çalışır.

Not: GLM-5.2 MIT lisanslı açık ağırlıklı bir model - ileride API
maliyetinden kurtulmak istersen kendi donanımında (RTX Pro 6000)
barındırıp bu dosyayı yerel bir endpoint'e (örn. vLLM) yönlendirmek
de mümkün, sadece BASE_URL'i değiştirmek yeterli olur.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "GLM_API_KEY"
BASE_URL_ENV = "GLM_BASE_URL"
MODEL_ENV = "GLM_MODEL"  # .env'den model override - kod degismeden
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
MODEL = "glm-5.2"
TIMEOUT_SECONDS = 180.0  # 2026-07-10: qwen.py'deki 2026-07-09 fix'inin aynısı - 60sn uzun konsey sorularinda yetmiyor (reasoning uzun), 3-deneme hep bos-mesajli ReadTimeout'tu


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
            check_response(response, provider_name="GLM-5.2")
            data = response.json()

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Beklenmeyen GLM-5.2 cevap formatı: {data}") from exc

        # Thinking-modeli kemeri (minimax.py/nemotron.py ile ayni): content bos
        # gelirse cevap reasoning_content'te kalmis olabilir.
        content = message.get("content") or ""
        if not content.strip():
            content = message.get("reasoning_content") or ""
        if not content.strip():
            raise RuntimeError(f"GLM-5.2 boş cevap döndü: {data}")
        return content

    return await with_retry(_call, provider_name="GLM-5.2")
