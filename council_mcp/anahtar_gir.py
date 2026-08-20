#!/usr/bin/env python3
"""Konsey API anahtarı GÜVENLİ giriş aracı.

Anahtar EKRANDA GÖRÜNMEZ (getpass), sohbete/loglara DÜŞMEZ, yalnız
`council_mcp/.env` dosyasına yazılır. Sadece hedef satır güncellenir,
diğer anahtarlar KORUNUR.

KULLANIM:
    python3 anahtar_gir.py            # KIMI (varsayılan)
    python3 anahtar_gir.py --uye qwen # başka üye
    python3 anahtar_gir.py --model kimi-k3-max   # anahtar + model birlikte

Anahtar girildikten sonra `python3 anahtar_test.py` ile doğrula.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = HERE / ".env"

UYELER = {
    "kimi": ("KIMI_API_KEY", "KIMI_MODEL", "Moonshot Kimi"),
    "glm": ("GLM_API_KEY", "GLM_MODEL", "Zhipu GLM"),
    "qwen": ("QWEN_API_KEY", "QWEN_MODEL", "Alibaba Qwen"),
    "gemini": ("GEMINI_API_KEY", None, "Google Gemini"),
    "openai": ("OPENAI_API_KEY", None, "OpenAI GPT"),
    "nvidia": ("NVIDIA_API_KEY", "NVIDIA_MODEL", "NVIDIA Build (Nemotron)"),
}


def maskele(s: str) -> str:
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:4]}{'*' * (len(s) - 8)}{s[-4:]}  ({len(s)} karakter)"


def satiri_guncelle(metin: str, anahtar: str, deger: str) -> str:
    """`.env` içinde `ANAHTAR=...` satırını değiştir; yoksa sona ekle.
    Yorum satırları (#ANAHTAR=) korunur, sadece aktif satır güncellenir."""
    satirlar = metin.splitlines()
    bulundu = False
    for i, s in enumerate(satirlar):
        if s.lstrip().startswith(f"{anahtar}=") and not s.lstrip().startswith("#"):
            satirlar[i] = f"{anahtar}={deger}"
            bulundu = True
            break
    if not bulundu:
        satirlar.append(f"{anahtar}={deger}")
    return "\n".join(satirlar) + "\n"


def atomik_yaz(yol: Path, icerik: str) -> None:
    """Geçici dosyaya yaz + rename → yarım yazım riski yok. İzin 0600."""
    fd, tmp = tempfile.mkstemp(dir=str(yol.parent), prefix=".env.", suffix=".tmp")
    try:
        os.write(fd, icerik.encode("utf-8"))
        os.close(fd)
        os.chmod(tmp, 0o600)
        os.replace(tmp, yol)
    except BaseException:
        os.close(fd) if not fd == -1 else None
        Path(tmp).unlink(missing_ok=True)
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description="Konsey API anahtarı güvenli giriş")
    ap.add_argument("--uye", default="kimi", choices=list(UYELER),
                    help="hangi üyenin anahtarı (varsayılan: kimi)")
    ap.add_argument("--model", default=None,
                    help="opsiyonel: model adını da ayarla (örn. kimi-k3-max)")
    a = ap.parse_args()

    anahtar_adi, model_adi, gorunen = UYELER[a.uye]

    if not ENV.exists():
        # şablondan türet
        sablon = HERE / ".env.example"
        if sablon.exists():
            atomik_yaz(ENV, sablon.read_text(encoding="utf-8"))
            print(f"[bilgi] .env yoktu, şablondan oluşturuldu: {ENV}")
        else:
            atomik_yaz(ENV, "")
            print(f"[bilgi] boş .env oluşturuldu: {ENV}")

    print(f"\n  {gorunen} anahtarı giriliyor ({anahtar_adi})")
    print("  Yapıştır ve Enter'a bas — GİRDİĞİN EKRANDA GÖRÜNMEYECEK.\n")

    try:
        deger = getpass.getpass("  Anahtar: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n  İptal edildi, değişiklik yapılmadı.")
        return 1

    if not deger:
        print("  Boş girdi — değişiklik yapılmadı.")
        return 1
    if " " in deger or "\t" in deger:
        print("  UYARI: anahtarda boşluk var — muhtemelen yanlış yapıştırıldı. İptal.")
        return 1

    metin = ENV.read_text(encoding="utf-8")
    metin = satiri_guncelle(metin, anahtar_adi, deger)
    if a.model and model_adi:
        metin = satiri_guncelle(metin, model_adi, a.model)

    atomik_yaz(ENV, metin)

    print(f"\n  ✓ {anahtar_adi} yazıldı → {maskele(deger)}")
    if a.model and model_adi:
        print(f"  ✓ {model_adi}={a.model}")
    print(f"  ✓ Dosya: {ENV}  (izin 0600, sadece sen okuyabilirsin)")
    print("\n  Doğrulamak için:  python3 anahtar_test.py --uye " + a.uye)
    return 0


if __name__ == "__main__":
    sys.exit(main())
