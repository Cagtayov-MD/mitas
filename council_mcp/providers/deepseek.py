"""
DeepSeek-V4-Flash provider (NVIDIA Build / NIM üzerinden, OpenAI-uyumlu uç).

Model: deepseek-ai/deepseek-v4-flash-0731 — matematik/kod odaklı MoE.
Konsey gerekçesi (2026-08-14): SAYISAL GÜVENİLİRLİK koltuğu. MiniMax-M3 aynı
gün yapılan yoklamada "20+20+7=47, 141−47=47" diyerek basit aritmetiği ıskaladı
ve konseyden çıkarıldı (Çağatay kararı). Önümüzdeki tur (H200'de MITAS+ATLAS
birlikte barındırma) baştan sona VRAM bütçesi aritmetiği — yanlış toplayan bir
üyenin "sığar/sığmaz" hükmü tehlikeli. Bu koltuk o riskin panzehiri.

NOT: eski `kimi` koltuğu deepseek-v4-PRO'ya bağlıydı ve 2026-08-07'de EOL oldu
(HTTP 410). Bu modül onun devamı DEĞİL, yerine geçen ayrı bir üyedir — flash
sürümü canlı ve teyitli. `moonshotai/kimi-k2.6` katalogda görünüyor ama hesaba
açık değil ("Not found for account", 404), o yüzden gerçek Kimi geri gelemedi.

Yoklama (2026-08-14): 141−(20+20+7) aritmetik testini geçti → "94".

Erişim: Nemotron ile AYNI NVIDIA_API_KEY. Model DEEPSEEK_MODEL ile,
uç NVIDIA_BASE_URL ile override edilebilir.
"""

import os

import httpx

from ._retry import check_response, with_retry

API_KEY_ENV = "NVIDIA_API_KEY"     # Nemotron ile paylasilan anahtar
BASE_URL_ENV = "NVIDIA_BASE_URL"
MODEL_ENV = "DEEPSEEK_MODEL"       # .env'den model override - kod degismeden
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL = "deepseek-ai/deepseek-v4-flash-0731"  # canli cagri ile teyitli (2026-08-14)
# Surum tarihi model ID'sinde SABIT tutuldu: v4-pro'nun EOL dersi (2026-08-07)
# tarihsiz/ustu-kapali ID'nin sessizce olebilecegini gosterdi.
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
            check_response(response, provider_name="DeepSeek-V4-Flash")
            data = response.json()

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Beklenmeyen DeepSeek cevap formatı: {data}") from exc

        # Thinking-modeli kemeri (nemotron.py ile ayni): content bos gelirse
        # cevap reasoning_content'te kalmis olabilir.
        content = message.get("content") or ""
        if not content.strip():
            content = message.get("reasoning_content") or ""
        if not content.strip():
            raise RuntimeError(f"DeepSeek boş cevap döndü: {data}")
        return content

    return await with_retry(_call, provider_name="DeepSeek-V4-Flash")
