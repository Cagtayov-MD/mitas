#!/usr/bin/env python3
"""Özgün 27B beslemesini sıfat/isim JSON sözleşmesiyle ölçen deney.

Bu dosya Jordan üretim yoluna bağlı değildir. Eski koşucunun komut satırını
birebir yeniden kurabilir: 24 karelik her pencere ``--image`` tekrarlanarak tek
çağrıda verilir. ``pencere_sonu`` modu ise yalnız teşhis amacıyla vardır.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any


BASE = Path("/home/cagatay/Programlar/mitas/CagatayBox")
IKILI = BASE / "llama.cpp/build/bin/llama-mtmd-cli"
MODEL = BASE / "models/Qwen3.6-27B-GGUF/Qwen3.6-27B-Q4_K_M.gguf"
MMPROJ = BASE / "models/Qwen3.6-27B-GGUF/mmproj-F16.gguf"


SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["credits", "subtitles"],
    "properties": {
        "credits": {
            "type": "array",
            "maxItems": 160,
            "items": {"type": "string", "maxLength": 500},
        },
        "subtitles": {
            "type": "array",
            "maxItems": 80,
            "items": {"type": "string", "maxLength": 500},
        },
    },
}


PROMPT = """## Rules
- Use ONLY the text visible in these frames. Do not use prior knowledge
  about the film, cast, crew, or production.
- Do not guess, infer, autocomplete, or correct names or words.
- If a character is unclear, replace only that character with "?".
  Keep all clearly readable characters unchanged.
- If a word or name is cut off at the frame edge, transcribe the visible
  part followed by "…".
- Transcribe text only. Do not describe logos, graphics, or visual elements.

## Discrimination & Categorization Rule
- Categorize extracted text into two distinct sections:
  1. [CREDITS]: Film title, cast, crew, production roles, company logos.
  2. [SUBTITLES]: Burnt-in dialogue subtitles visible at the bottom of the frame.

## Output Format (STRICT)
- You MUST use exactly these two headers, spelled exactly as shown:
  [CREDITS]
  [SUBTITLES]
- Do NOT modify, abbreviate, or misspell these headers.

## Script & Direction
- Preserve the original script exactly. Do not transliterate or romanize.
- For RTL scripts (Arabic, Hebrew, Persian, Urdu), preserve script and reading direction.
- Preserve diacritics and vowel marks as they appear.

## Turkish-Specific & Special Characters
- Preserve Turkish special characters exactly: Ç, Ğ, İ, I, Ö, Ş, Ü, ç, ğ, i, ı, ö, ş, ü.
- Do NOT replace Ç with C, Ğ with G, Ş with S, Ö with O, Ü with U.

## Formatting
- Preserve original text order and line breaks under [CREDITS] or [SUBTITLES].
- If the same text appears across multiple frames, transcribe it only once.
- Preserve role/title + name groupings as they appear.

## Stop
- Transcribe ALL visible text, including small font and edge text.
- After all visible text is transcribed, end your response."""


def sha256_dosya(yol: Path) -> str:
    ozet = hashlib.sha256()
    with yol.open("rb") as akis:
        for parca in iter(lambda: akis.read(1024 * 1024), b""):
            ozet.update(parca)
    return ozet.hexdigest()


def kareleri_bul(dizin: Path) -> list[Path]:
    kareler = sorted(dizin.glob("frame_*.jpg"))
    if not kareler:
        raise ValueError(f"Kare bulunamadi: {dizin}")
    return kareler


def pencere_sonlarini_sec(kareler: list[Path], grup_boyu: int) -> list[Path]:
    """Eski tekrarlı --image davranışını bilinçli tek-kare seçimine çevir."""
    if grup_boyu <= 0:
        raise ValueError("grup_boyu pozitif olmali")
    return [kareler[min(i + grup_boyu, len(kareler)) - 1]
            for i in range(0, len(kareler), grup_boyu)]


def pencerelere_ayir(kareler: list[Path], grup_boyu: int) -> list[list[Path]]:
    if grup_boyu <= 0:
        raise ValueError("grup_boyu pozitif olmali")
    return [kareler[i:i + grup_boyu] for i in range(0, len(kareler), grup_boyu)]


def json_nesnesini_al(stdout: str) -> dict[str, Any]:
    temiz = stdout
    for isaret in ("<|im_start|>assistant", "</think>"):
        if isaret in temiz:
            temiz = temiz.split(isaret)[-1]
    cozumleyici = json.JSONDecoder()
    adaylar: list[tuple[int, dict[str, Any]]] = []
    for eslesme in re.finditer(r"\{", temiz):
        try:
            deger, uzunluk = cozumleyici.raw_decode(temiz[eslesme.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(deger, dict):
            adaylar.append((uzunluk, deger))
    if not adaylar:
        raise ValueError("Model stdout icinde JSON nesnesi yok")
    nesne = max(adaylar, key=lambda oge: oge[0])[1]
    dogrula(nesne)
    return nesne


def dogrula(nesne: dict[str, Any]) -> None:
    if set(nesne) != {"credits", "subtitles"}:
        raise ValueError("JSON ust alanlari sozlesmeyle uyusmuyor")
    if not all(isinstance(nesne[alan], list) for alan in ("credits", "subtitles")):
        raise ValueError("JSON liste alanlarindan biri liste degil")
    if not all(isinstance(x, str) for alan in ("credits", "subtitles")
               for x in nesne[alan]):
        raise ValueError("JSON metin listesinde string olmayan oge var")


def komut(kareler: list[Path]) -> list[str]:
    if not kareler:
        raise ValueError("27B cagrisi karesiz olamaz")
    schema = json.dumps(SCHEMA, ensure_ascii=False, separators=(",", ":"))
    istem = f"<|im_start|>user\n{PROMPT}<|im_end|>\n<|im_start|>assistant\n"
    sonuc = [
        str(IKILI), "-m", str(MODEL), "--mmproj", str(MMPROJ),
        "-p", istem, "-ngl", "99", "-n", "1024",
        # Özgün koşucunun üretim ayarları da aynen korunur. Deneyde değişen
        # yalnız promptun yapı talebi ve runtime JSON schema'sıdır.
        "--temp", "0.01", "--top-p", "0.10", "--repeat-penalty", "1.05",
        "--json-schema", schema,
    ]
    # Özgün koşucunun davranışı: her kare için ayrı --image anahtarı.
    for kare in kareler:
        sonuc.extend(["--image", str(kare.resolve())])
    return sonuc


def kareleri_oku(kareler: list[Path], timeout_s: int) -> tuple[dict[str, Any], float, str]:
    baslangic = time.monotonic()
    sonuc = subprocess.run(komut(kareler), capture_output=True, text=True,
                           timeout=timeout_s, check=False)
    sure = round(time.monotonic() - baslangic, 3)
    if sonuc.returncode != 0:
        raise RuntimeError(f"27B rc={sonuc.returncode}: {sonuc.stderr[-1500:]}")
    return json_nesnesini_al(sonuc.stdout), sure, sonuc.stderr[-1500:]


def kesin_birlestir(gruplar: list[dict[str, Any]]) -> dict[str, Any]:
    """Grupları kayıpsız sırala; tekrar dahil hiçbir model satırını düşürme."""
    credits: list[str] = []
    subtitles: list[str] = []
    for grup in gruplar:
        for alan, hedef in (("credits", credits), ("subtitles", subtitles)):
            for satir in grup[alan]:
                # Model tek string içinde newline döndürürse satırları yalnız
                # mekanik olarak ayır; karakterleri veya yazımı değiştirme.
                for alt_satir in (x.strip() for x in satir.splitlines() if x.strip()):
                    hedef.append(alt_satir)
    return {"credits": credits, "subtitles": subtitles}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kare-dizini", type=Path, required=True)
    parser.add_argument("--cikti", type=Path, required=True)
    parser.add_argument("--grup-boyu", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--besleme", choices=("ozgun_tekrarli", "pencere_sonu"),
                        default="ozgun_tekrarli")
    parser.add_argument("--yalniz-pencere", type=int,
                        help="1 tabanli tek pencereyi kos; OOM izolasyonu icin")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    kareler = kareleri_bul(args.kare_dizini)
    pencereler = pencerelere_ayir(kareler, args.grup_boyu)
    cagrilar = (pencereler if args.besleme == "ozgun_tekrarli"
                else [[pencere[-1]] for pencere in pencereler])
    pencere_numaralari = list(range(1, len(cagrilar) + 1))
    if args.yalniz_pencere is not None:
        if not 1 <= args.yalniz_pencere <= len(cagrilar):
            raise ValueError("yalniz-pencere mevcut pencere araliginda olmali")
        indis = args.yalniz_pencere - 1
        cagrilar = [cagrilar[indis]]
        pencere_numaralari = [args.yalniz_pencere]
    if args.dry_run:
        for sira, cagri in enumerate(cagrilar, 1):
            print(f"{sira}:" + ",".join(kare.name for kare in cagri))
        return 0

    for yol in (IKILI, MODEL, MMPROJ):
        if not yol.is_file():
            raise FileNotFoundError(yol)

    grup_sonuclari: list[dict[str, Any]] = []
    toplam_baslangic = time.monotonic()
    for kosu_sirasi, (pencere_no, cagri) in enumerate(
            zip(pencere_numaralari, cagrilar), 1):
        print(f"[{kosu_sirasi}/{len(cagrilar)}] pencere={pencere_no} "
              f"{cagri[0].name}..{cagri[-1].name} "
              f"({len(cagri)} kare)", flush=True)
        veri, sure, stderr = kareleri_oku(cagri, args.timeout)
        toplam_parcalar = [int(n) for n in re.findall(r"total\s*=\s*(\d+)", stderr)]
        grup_sonuclari.append({
            "pencere": pencere_no,
            "istenen_kareler": [str(kare.resolve()) for kare in cagri],
            "kare_sha256": [sha256_dosya(kare) for kare in cagri],
            "runtime_parca_sayisi": max(toplam_parcalar) if toplam_parcalar else None,
            "sure_sn": sure,
            "sonuc": veri,
            "runtime_stderr_tail": stderr,
        })

    belge = {
        "deney": "orijinal_27b_sifat_isim/v1",
        "besleme": {
            "toplam_kare": len(kareler),
            "grup_boyu": args.grup_boyu,
            "politika": args.besleme,
            "cagri_sayisi": len(cagrilar),
            "cagri_basina_kare": [len(cagri) for cagri in cagrilar],
        },
        "model": str(MODEL),
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "schema_sha256": hashlib.sha256(json.dumps(
            SCHEMA, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "toplam_sure_sn": round(time.monotonic() - toplam_baslangic, 3),
        "sonuc": kesin_birlestir([x["sonuc"] for x in grup_sonuclari]),
        "gruplar": grup_sonuclari,
    }
    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    gecici = args.cikti.with_suffix(args.cikti.suffix + ".tmp")
    gecici.write_text(json.dumps(belge, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    gecici.replace(args.cikti)
    print(f"YAZILDI: {args.cikti}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
