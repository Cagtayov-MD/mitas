#!/usr/bin/env python3
"""Konseyi MCP sunucusunu ATLAYIP doğrudan çağır — tam kadro, taze .env.

Gerekçe (2026-07-24): çalışan MCP sunucu süreci eski kodla başladığında yeni
üyeler (nemotron/minimax/gemini/gpt) ve yeni anahtarlar restart'a kadar katılamıyor.
Bu script her koşuda .env'i taze yükler ve KAYITLI TÜM sağlayıcıları paralel sorgular.

Kullanım:
  .venv/bin/python konsey_dogrudan.py --soru soru.txt [--baglam baglam.txt] [--uyeler glm,kimi,...]
  (dosya yerine '-' verilirse stdin okunur; çıktı stdout'a markdown)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)

from dotenv import load_dotenv

load_dotenv(os.path.join(BURASI, ".env"), override=True)  # taze anahtarlar KAZANIR

from providers import gemini, glm, gpt, kimi, minimax, nemotron, qwen  # noqa: E402

UYELER = {
    "gemini": gemini,
    "glm": glm,
    "gpt": gpt,
    "kimi": kimi,
    "nemotron": nemotron,
    "minimax": minimax,
    "qwen": qwen,  # anahtarı kapalıysa zaten katılamaz
}


def _oku(yol: str) -> str:
    if yol == "-":
        return sys.stdin.read()
    return open(yol, encoding="utf-8").read()


def _anahtari_var(mod) -> bool:
    env = getattr(mod, "API_KEY_ENV", None)
    if env:
        return bool(os.environ.get(env))
    # modül sabiti yoksa yaygın adlandırmayı dene
    for aday in ("GEMINI_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY",
                 "KIMI_API_KEY", "NVIDIA_API_KEY", "QWEN_API_KEY"):
        if aday.lower().startswith(mod.__name__.split(".")[-1][:3]):
            return bool(os.environ.get(aday))
    return True  # emin değilsek dene; hata zaten raporlanır


async def _sor(ad: str, mod, soru: str, baglam: str | None) -> tuple[str, str]:
    try:
        cevap = await mod.ask(soru, baglam)
        return ad, cevap
    except Exception as exc:  # noqa: BLE001
        return ad, f"HATA: {type(exc).__name__}: {exc}"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--soru", required=True)
    ap.add_argument("--baglam", default=None)
    ap.add_argument("--uyeler", default=None, help="virgüllü alt-küme; varsayılan: anahtarı olan herkes")
    a = ap.parse_args()
    soru = _oku(a.soru)
    baglam = _oku(a.baglam) if a.baglam else ""  # sağlayıcı imzaları context: str = ""
    secili = (a.uyeler.split(",") if a.uyeler
              else [k for k, m in UYELER.items() if _anahtari_var(m)])
    secili = [s for s in secili if s in UYELER]
    print(f"# Konsey (doğrudan) — üyeler: {', '.join(secili)}\n", flush=True)
    sonuclar = await asyncio.gather(*[_sor(s, UYELER[s], soru, baglam) for s in secili])
    for ad, cevap in sonuclar:
        print(f"\n---\n\n## {ad}\n\n{cevap}\n", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
