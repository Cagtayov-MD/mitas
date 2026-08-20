"""
Tüm provider'ların ortak kullandığı retry sarmalayıcı.

Kural (kilitli - konuştuğumuz karar): bir model hata verirse ya da
timeout olursa 2 kez daha otomatik denenir (üstel bekleme ile),
üçü de başarısız olursa net bir hata fırlatılır.
"""

import asyncio
from typing import Awaitable, Callable, TypeVar

import httpx

T = TypeVar("T")

MAX_RETRIES = 2
BASE_DELAY_SECONDS = 2


def check_response(response: httpx.Response, provider_name: str) -> None:
    """response.raise_for_status() yerine kullan: httpx'in ürettiği hata
    mesajı istek URL'ini olduğu gibi içerir - Gemini gibi API key'i query
    string'de taşıyan sağlayıcılarda bu, key'in hata metninde (ve
    dolayısıyla council cevabında) açık şekilde sızmasına yol açar.
    """
    if response.is_error:
        raise RuntimeError(
            f"{provider_name} HTTP {response.status_code} döndü: {response.text[:500]}"
        )


async def with_retry(func: Callable[[], Awaitable[T]], provider_name: str) -> T:
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001 - kasıtlı geniş yakalama
            last_error = exc
            if attempt < MAX_RETRIES:
                await asyncio.sleep(BASE_DELAY_SECONDS * (2**attempt))
                continue

    # httpx.TimeoutException'ın str()'i BOŞtur: düz {last_error} yazınca hata
    # metni "...alınamadı: " diye biter ve tek teşhis bilgisi silinir (MiniMax
    # 2026-07'de tam bu yüzden "boş dönüyor" sanıldı). Boşsa tip adına düş.
    detay = str(last_error) or type(last_error).__name__
    raise RuntimeError(
        f"{provider_name}'dan {MAX_RETRIES + 1} denemede cevap alınamadı: {detay}"
    )
