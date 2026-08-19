"""Qwen3.6-27B GGUF için ölçülmüş özgün multi-image + JSON-schema motoru.

Bu motor transformers koluna dokunmaz. Kamuya açık yüzü aynıdır:
``sor(istem, kareler=[...]) -> str``. Dönen metin mevcut Jordan okuyucusunun
anladığı [CREDITS]/[SUBTITLES] görünümüdür; modelin asıl cevabı ise zorunlu
JSON'dur ve ``son_cagri_kaniti`` ile kayıpsız biçimde dışarı verilir.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from model import BellekHatasi, CiktiBozuk, ModelHatasi


SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["credits", "subtitles"],
    "properties": {
        "credits": {
            "type": "array", "minItems": 0, "maxItems": 160,
            "items": {"type": "string", "maxLength": 500},
        },
        "subtitles": {
            "type": "array", "minItems": 0, "maxItems": 80,
            "items": {"type": "string", "maxLength": 500},
        },
    },
}


def _json_nesnesi(ham: str) -> tuple[dict[str, Any], str]:
    """Llama log/özel-token gürültüsünden tek geçerli schema nesnesini al."""
    temiz = ham
    for isaret in ("<|im_start|>assistant", "</think>"):
        if isaret in temiz:
            temiz = temiz.split(isaret)[-1]
    cozumleyici = json.JSONDecoder()
    adaylar: list[tuple[int, dict[str, Any], str]] = []
    for eslesme in re.finditer(r"\{", temiz):
        parca = temiz[eslesme.start():]
        try:
            deger, uzunluk = cozumleyici.raw_decode(parca)
        except json.JSONDecodeError:
            continue
        if isinstance(deger, dict) and set(deger) == {"credits", "subtitles"}:
            adaylar.append((uzunluk, deger, parca[:uzunluk]))
    if not adaylar:
        raise CiktiBozuk("27B stdout icinde zorunlu JSON nesnesi bulunamadi")
    _, deger, json_metni = max(adaylar, key=lambda oge: oge[0])
    return deger, json_metni


def _satirlar(deger: Any, alan: str) -> list[str]:
    if not isinstance(deger, list) or not all(isinstance(oge, str) for oge in deger):
        raise CiktiBozuk(f"27B JSON {alan} string listesi degil")
    sonuc: list[str] = []
    for oge in deger:
        # Schema stringi zorlar fakat model tek stringe newline koyabilir.
        # Satır yapısını deterministik şekilde geri aç; metni düzeltme.
        sonuc.extend(satir.strip() for satir in oge.splitlines() if satir.strip())
    return sonuc


def _sha256_metin(metin: str) -> str:
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()


class LlamaMtmdMotor:
    """llama-mtmd-cli kullanan Qwen3.6-27B motoru."""

    # KSK'de ölçülen özgün etiketli prompt transformers koluyla ortaktır.
    # JSON biçimi prompta ek talimat katmadan runtime schema ile zorlanır.
    istem_anahtari = "okuma"
    # Aynı grupta yalnız bitişik birebir tekrar güvenle düşer. Böylece gerçek
    # `STU PHILLIPS / MUSIC BY / STU PHILLIPS` yapısı kaybolmaz.
    tekrar_modu = "ayni_grupta_yalniz_komsu"

    def __init__(self, model_yolu: str | Path, mmproj: str | Path,
                 llama_cli: str | Path, *, timeout_s: int = 600,
                 max_new_tokens: int = 1024,
                 image_min_tokens: int | None = None,
                 image_max_tokens: int | None = None,
                 gpu_layers: int = 99,
                 oom_retry: int = 1,
                 retry_cooldown_s: float = 2.0) -> None:
        self.yol = str(Path(model_yolu).expanduser())
        self.mmproj = str(Path(mmproj).expanduser())
        self.llama_cli = str(Path(llama_cli).expanduser())
        self.timeout_s = int(timeout_s)
        self.max_new_tokens = int(max_new_tokens)
        self.image_min_tokens = image_min_tokens
        self.image_max_tokens = image_max_tokens
        self.gpu_layers = int(gpu_layers)
        self.oom_retry = int(oom_retry)
        self.retry_cooldown_s = float(retry_cooldown_s)
        self.sizinti = 0
        self._son_kanit: dict[str, Any] | None = None

    def yukle(self) -> "LlamaMtmdMotor":
        for etiket, yol in (("llama-mtmd-cli", self.llama_cli),
                            ("model", self.yol), ("mmproj", self.mmproj)):
            if not Path(yol).is_file():
                raise ModelHatasi(f"27B {etiket} bulunamadi: {yol}")
        if not os.access(self.llama_cli, os.X_OK):
            raise ModelHatasi(f"27B llama-mtmd-cli calistirilabilir degil: {self.llama_cli}")
        if self.timeout_s <= 0 or self.max_new_tokens <= 0:
            raise ModelHatasi("27B timeout/max_new_tokens pozitif olmali")
        if self.oom_retry < 0 or self.retry_cooldown_s < 0:
            raise ModelHatasi("27B retry degerleri negatif olamaz")
        if (self.image_min_tokens is not None and self.image_max_tokens is not None
                and self.image_min_tokens > self.image_max_tokens):
            raise ModelHatasi("image_min_tokens image_max_tokens'i asamaz")
        return self

    @staticmethod
    def _gorsel_argumanlari(kareler: list[str]) -> list[str]:
        """KSK kazananı: her kare için ayrı ``--image <yol>`` çifti."""
        if not kareler:
            raise ModelHatasi("27B multi-image cagrisi karesiz olamaz")
        yollar = [str(Path(yol).resolve()) for yol in kareler]
        eksik = [yol for yol in yollar if not Path(yol).is_file()]
        if eksik:
            raise ModelHatasi(f"27B karesi bulunamadi: {eksik[0]}")
        sonuc: list[str] = []
        for yol in yollar:
            sonuc.extend(["--image", yol])
        return sonuc

    def _komut(self, istem: str, kareler: list[str]) -> list[str]:
        schema = json.dumps(SCHEMA, ensure_ascii=False, separators=(",", ":"))
        # Özgün koşucunun prompt kabuğu birebir; schema hakkında prompta yorum
        # eklenmez. Deneyde kaliteyi koruyan ayrım budur.
        prompt = (f"<|im_start|>user\n{istem.rstrip()}<|im_end|>\n"
                  "<|im_start|>assistant\n")
        komut = [
            self.llama_cli, "-m", self.yol, "--mmproj", self.mmproj,
            "-p", prompt, "-ngl", str(self.gpu_layers),
            "-n", str(self.max_new_tokens), "--temp", "0.01",
            "--top-p", "0.10", "--repeat-penalty", "1.05",
            "--json-schema", schema,
        ]
        komut.extend(self._gorsel_argumanlari(kareler))
        if self.image_min_tokens is not None:
            komut.extend(["--image-min-tokens", str(int(self.image_min_tokens))])
        if self.image_max_tokens is not None:
            komut.extend(["--image-max-tokens", str(int(self.image_max_tokens))])
        return komut

    def sor(self, istem: str, kareler: list[str] | None = None) -> str:
        self.yukle()
        kare_listesi = list(kareler or [])
        komut = self._komut(istem, kare_listesi)
        denemeler: list[dict[str, Any]] = []
        sonuc = None
        for deneme in range(1, self.oom_retry + 2):
            baslangic = time.monotonic()
            try:
                sonuc = subprocess.run(komut, capture_output=True, text=True,
                                       timeout=self.timeout_s, check=False)
            except subprocess.TimeoutExpired as exc:
                raise ModelHatasi(f"27B zaman asimi ({self.timeout_s} sn)") from exc
            except OSError as exc:
                raise ModelHatasi(f"27B baslatilamadi: {exc}") from exc
            sure = round(time.monotonic() - baslangic, 3)
            stderr_kucuk = sonuc.stderr[-1200:]
            denemeler.append({"attempt": deneme, "returncode": sonuc.returncode,
                              "duration_s": sure, "stderr_tail": stderr_kucuk})
            if sonuc.returncode == 0:
                break
            mesaj = f"27B rc={sonuc.returncode}: {stderr_kucuk[-1000:]}"
            hata = sonuc.stderr.casefold()
            bellek = any(isaret in hata for isaret in (
                "out of memory", "cudamalloc failed", "resource allocation failed"))
            if not bellek:
                raise ModelHatasi(mesaj)
            if deneme > self.oom_retry:
                raise BellekHatasi(mesaj)
            if self.retry_cooldown_s:
                time.sleep(self.retry_cooldown_s)
        assert sonuc is not None
        sure = sum(float(x["duration_s"]) for x in denemeler)
        stderr_kucuk = sonuc.stderr[-1200:]

        nesne, json_metni = _json_nesnesi(sonuc.stdout)
        krediler = _satirlar(nesne.get("credits"), "credits")
        altyazilar = _satirlar(nesne.get("subtitles"), "subtitles")
        toplam_parcalar = [int(n) for n in re.findall(r"total\s*=\s*(\d+)", sonuc.stderr)]
        runtime_parca = max(toplam_parcalar) if toplam_parcalar else None
        self._son_kanit = {
            "backend": "llama_mtmd",
            "model": self.yol,
            "mmproj": self.mmproj,
            "image_transport": "repeated_image_flags",
            "image_count": len(kare_listesi),
            "runtime_chunk_count": runtime_parca,
            "runtime_multi_image_verified": (
                runtime_parca >= len(kare_listesi) + 1 if runtime_parca is not None else None),
            "json_schema_sha256": _sha256_metin(json.dumps(
                SCHEMA, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
            "prompt_sha256": _sha256_metin(istem.rstrip()),
            "decoding": {"temperature": 0.01, "top_p": 0.10,
                         "repeat_penalty": 1.05},
            "duration_s": round(sure, 3),
            "attempt_count": len(denemeler),
            "attempts": denemeler,
            "returncode": sonuc.returncode,
            "raw_json": json_metni,
            "raw_json_sha256": _sha256_metin(json_metni),
            "stderr_tail": stderr_kucuk,
        }
        # Mevcut okuyucu protokolüne yalnız biçim dönüşümü; metin değişmez.
        return ("[CREDITS]\n" + "\n".join(krediler)
                + "\n[SUBTITLES]\n" + "\n".join(altyazilar)).strip()

    def son_cagri_kaniti(self) -> dict[str, Any] | None:
        return dict(self._son_kanit) if self._son_kanit else None

    @staticmethod
    def bosalt() -> None:
        """Alt süreç her çağrı sonunda zaten kapanır."""
