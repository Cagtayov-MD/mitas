"""
MiniMax-M3 provider (NVIDIA Build / NIM üzerinden, OpenAI-uyumlu uç).

Model: minimaxai/minimax-m3 — multimodal MoE, reasoning/coding/tool-use güçlü;
LM Arena ~1491 (2026-07). Konsey gerekçesi (Çağatay 2026-07-23): Qwen sık
sorunlu, Gemini şimdilik yok — üyelerin hepsi tam aktif çalışmadığı için
elde ciddi alternatifler bulunsun.

Erişim: Nemotron ile AYNI NVIDIA_API_KEY (build.nvidia.com kataloğu tek
anahtarla çalışır) — anahtar girildiyse iki üye birden katılır, ayrı anahtar
gerekmez. Model MINIMAX_MODEL ile, uç NVIDIA_BASE_URL ile override edilebilir.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "NVIDIA_API_KEY"     # Nemotron ile paylasilan anahtar
BASE_URL_ENV = "NVIDIA_BASE_URL"
MODEL_ENV = "MINIMAX_MODEL"        # .env'den model override - kod degismeden
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "minimaxai/minimax-m3"     # anahtar_test /models ciktisindan teyitli (2026-07-23)
# kimi.py ile ayni gerekce (2026-07-31): m3 dusunen model, ~8 KB konsey
# brifinglerinde akil yurutme 180sn'yi asiyordu -> httpx ReadTimeout -> str()'i
# bos -> tur "boş cevap" gibi gorunuyordu. Kimi'ye uygulanan 420sn burada da.
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
            check_response(response, provider_name="MiniMax-M3")
            data = response.json()

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Beklenmeyen MiniMax-M3 cevap formatı: {data}") from exc

        # Thinking-modeli kemeri (nemotron.py ile ayni): content bos gelirse
        # cevap reasoning_content'te kalmis olabilir.
        content = message.get("content") or ""
        if not content.strip():
            content = message.get("reasoning_content") or ""
        if not content.strip():
            raise RuntimeError(f"MiniMax-M3 boş cevap döndü: {data}")
        return content

    return await with_retry(_call, provider_name="MiniMax-M3")
