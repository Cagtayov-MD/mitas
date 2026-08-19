#!/usr/bin/env python3
"""Konsey API anahtarı CANLI test.

Anahtarı EKRANA BASMADAN doğrular:
  1) .env yüklü mü, anahtar tanımlı mı
  2) /models ile hesabın erişebildiği modelleri listeler (auth doğrulaması + katalog)
  3) yapılandırılmış modelle küçük bir chat çağrısı yapar

KULLANIM:
    python3 anahtar_test.py                 # KIMI
    python3 anahtar_test.py --uye glm
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env", override=True)

UYELER = {
    "kimi": ("KIMI_API_KEY", "KIMI_MODEL", "KIMI_BASE_URL",
             "kimi-k3", "https://api.moonshot.ai/v1", "Moonshot Kimi"),
    "glm": ("GLM_API_KEY", "GLM_MODEL", "GLM_BASE_URL",
            "glm-5.2", "https://open.bigmodel.cn/api/paas/v4", "Zhipu GLM"),
    "qwen": ("QWEN_API_KEY", "QWEN_MODEL", "QWEN_BASE_URL",
             "qwen3.7-max", "https://dashscope.aliyun.com/compatible-mode/v1", "Alibaba Qwen"),
    "nvidia": ("NVIDIA_API_KEY", "NVIDIA_MODEL", "NVIDIA_BASE_URL",
               "nvidia/nemotron-3-ultra-550b-a55b", "https://integrate.api.nvidia.com/v1",
               "NVIDIA Build (Nemotron)"),
    "minimax": ("NVIDIA_API_KEY", "MINIMAX_MODEL", "NVIDIA_BASE_URL",
                "minimaxai/minimax-m3", "https://integrate.api.nvidia.com/v1",
                "MiniMax-M3 (NVIDIA Build üzerinden)"),
}


def maskele(s: str) -> str:
    return f"{s[:4]}…{s[-4:]} ({len(s)} kr)" if len(s) > 8 else "*" * len(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uye", default="kimi", choices=list(UYELER))
    a = ap.parse_args()
    key_env, model_env, base_env, def_model, def_base, gorunen = UYELER[a.uye]

    key = os.getenv(key_env)
    base = os.getenv(base_env, def_base)
    model = os.getenv(model_env, def_model)

    print(f"\n  === {gorunen} testi ===")
    if not key:
        print(f"  ✗ {key_env} tanımlı değil. Önce: python3 anahtar_gir.py --uye {a.uye}")
        return 1
    print(f"  anahtar : {maskele(key)}")
    print(f"  uç      : {base}")
    print(f"  model   : {model}")

    headers = {"Authorization": f"Bearer {key}"}

    # 1) model kataloğu — auth doğrulaması + hangi modeller erişilebilir
    print("\n  [1/2] /models sorgulanıyor (auth + katalog)...")
    try:
        r = httpx.get(f"{base}/models", headers=headers, timeout=30)
        if r.status_code == 401:
            print(f"  ✗ 401 YETKİSİZ — anahtar yanlış veya iptal edilmiş.\n      {r.text[:200]}")
            return 1
        if r.status_code == 404:
            print(f"  ! /models yok (bazı uçlar desteklemez), model testine geçiliyor")
        elif r.status_code >= 400:
            print(f"  ! /models HTTP {r.status_code}: {r.text[:200]}")
        else:
            data = r.json()
            adlar = [m.get("id") for m in data.get("data", []) if m.get("id")]
            print(f"  ✓ auth OK — {len(adlar)} model erişilebilir:")
            for ad in sorted(adlar):
                isaret = "  ← yapılandırılmış" if ad == model else ""
                mx = "  ★ MAX" if "max" in ad.lower() else ""
                print(f"      {ad}{mx}{isaret}")
            if model not in adlar and adlar:
                print(f"  ! DİKKAT: yapılandırılmış '{model}' listede YOK — model adını güncelle")
    except Exception as e:
        print(f"  ! /models başarısız ({type(e).__name__}: {str(e)[:120]}) — model testine geçiliyor")

    # 2) küçük chat çağrısı — gerçek uçtan uca test
    print("\n  [2/2] küçük chat çağrısı yapılıyor...")
    try:
        # Kimi/GLM thinking modelleri: düşük max_tokens content'i BOŞ bırakır (bütçe
        # reasoning_content'e gider). 400 yeterli tampon.
        r = httpx.post(f"{base}/chat/completions", headers=headers, timeout=120, json={
            "model": model,
            "messages": [{"role": "user", "content": "Sadece 'MITAS konsey testi başarılı' yaz."}],
            "max_tokens": 400,
        })
        if r.status_code == 401:
            print(f"  ✗ 401 YETKİSİZ\n      {r.text[:200]}")
            return 1
        if r.status_code == 429:
            print(f"  ✗ 429 — kota/bakiye bitmiş veya hız limiti.\n      {r.text[:200]}")
            return 1
        if r.status_code >= 400:
            print(f"  ✗ HTTP {r.status_code}\n      {r.text[:300]}")
            return 1
        cevap = r.json()["choices"][0]["message"]["content"]
        print(f"  ✓ CEVAP ALINDI: {cevap.strip()[:120]}")
        print(f"\n  ✓✓ {gorunen} ÇALIŞIYOR — konseye hazır.\n")
        return 0
    except Exception as e:
        print(f"  ✗ chat çağrısı başarısız: {type(e).__name__}: {str(e)[:200]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
