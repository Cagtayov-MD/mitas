"""Qwen3.5-9B'yi yükleyen ve soran TEK yer.

Kulenin geri kalanı transformers'ı bilmez. Model bir kez yüklenir, kuyruğun
tamamı o yüklemeyle işlenir — 14 GB'ı her film için yeniden okumak saçmadır.

Bu dosya sözleşmeyi (sozlesme.py) BİLMEZ. Kendi istisnalarını atar; Cikti'ya
çeviri main.py'de yapılır.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


class ModelHatasi(RuntimeError):
    """Model yüklenemedi / üretemedi. main.py bunu ARIZA'ya çevirir."""


class BellekHatasi(ModelHatasi):
    """CUDA OOM — ayrı sınıf, çünkü çaresi farklı (parça küçült)."""


class CiktiBozuk(ModelHatasi):
    """Model konuştu ama çıktısı kullanılamaz (bitmemiş düşünme, boş cevap)."""


def _dusunme_ayikla(ham: str) -> tuple[str, bool]:
    """Qwen3.5 akıl yürütür ve muhakemesi transkripte sızar.

    Gözlenen iki desen (sandbox 2026-08-12):
      ① `...düşünce...</think>\\ncevap`            → kurtarılabilir
      ② `...</think>cevap</think>cevap` (çift)     → SON `</think>`ten sonrası
      ③ `<think>...` (kapanmamış, cevap yok)       → kurtarılamaz

    Sessizce temizleyip "okundu" demiyoruz: sızıntı olduğu `kanit`e yazılır.
    """
    if "</think>" in ham:
        return ham.rsplit("</think>", 1)[-1].strip(), True
    if "<think" in ham:
        raise CiktiBozuk("dusunme bloku kapanmamis, cevap uretilmemis")
    return ham.strip(), False


class Motor:
    """Yüklenmiş model + işlemci. `sor()` iki modda çalışır: videolu / metin."""

    def __init__(self, model_yolu: str | Path, dtype: str = "bfloat16",
                 dusunme: bool = False, uretim: dict | None = None) -> None:
        self.yol = str(model_yolu)
        self.dtype = dtype
        self.dusunme = dusunme
        self.uretim = uretim or {}
        self.model = None
        self.islemci = None
        self.sizinti = 0          # düşünme sızıntısı sayacı (kanit'e gider)

    # ── yükleme ────────────────────────────────────────────────────────
    def yukle(self) -> "Motor":
        if self.model is not None:
            return self
        try:
            import torch
            from transformers import AutoProcessor
        except Exception as e:                      # noqa: BLE001
            raise ModelHatasi(f"transformers/torch yuklenemedi: {e}") from e

        if not Path(self.yol, "config.json").exists():
            raise ModelHatasi(f"model bulunamadi: {self.yol}/config.json yok")

        try:
            self.islemci = AutoProcessor.from_pretrained(self.yol)
            self.model = self._model_sinifi().from_pretrained(
                self.yol,
                dtype=getattr(torch, self.dtype),
                device_map="cuda",
            )
            self.model.eval()
        except Exception as e:                      # noqa: BLE001
            raise self._sinifla(e) from e
        return self

    @staticmethod
    def _model_sinifi():
        """Qwen3.5 çok-kipli; transformers sürümüne göre sınıf adı değişebilir."""
        import transformers
        for ad in ("AutoModelForImageTextToText", "AutoModelForMultimodalLM",
                   "AutoModelForCausalLM"):
            sinif = getattr(transformers, ad, None)
            if sinif is not None:
                return sinif
        raise ModelHatasi("uygun AutoModel sinifi bulunamadi")

    @staticmethod
    def _sinifla(e: Exception) -> ModelHatasi:
        m = str(e)
        if "out of memory" in m.lower() or type(e).__name__ == "OutOfMemoryError":
            return BellekHatasi(m[:300])
        return ModelHatasi(f"{type(e).__name__}: {m[:300]}")

    # ── sorma ──────────────────────────────────────────────────────────
    def sor(self, istem: str, video: str | None = None) -> str:
        """Tek istek → ham metin. `video` verilmezse GÖRÜNTÜSÜZ (geçiş 2)."""
        if self.model is None:
            self.yukle()
        import torch

        icerik = []
        if video:
            icerik.append({"type": "video", "video": str(video)})
        icerik.append({"type": "text", "text": istem})
        mesajlar = [{"role": "user", "content": icerik}]

        try:
            girdi = self._sablonla(mesajlar).to(self.model.device)
            with torch.inference_mode():
                cikti = self.model.generate(
                    **girdi,
                    max_new_tokens=self.uretim.get("max_new_tokens", 1024),
                    do_sample=self.uretim.get("do_sample", False),
                    temperature=self.uretim.get("temperature", 0.0) or None,
                    repetition_penalty=self.uretim.get("repetition_penalty", 1.05),
                )
            yeni = cikti[0][girdi["input_ids"].shape[-1]:]
            ham = self.islemci.decode(yeni, skip_special_tokens=True)
        except Exception as e:                      # noqa: BLE001
            raise self._sinifla(e) from e
        finally:
            self.bosalt()

        metin, sizdi = _dusunme_ayikla(ham)
        self.sizinti += int(sizdi)
        if not metin:
            raise CiktiBozuk("model bos cevap dondu")
        return metin

    def _sablonla(self, mesajlar):
        """Sohbet şablonu. `enable_thinking` her sürümde yok — varsa kullan."""
        ortak = dict(tokenize=True, add_generation_prompt=True,
                     return_dict=True, return_tensors="pt")
        if not self.dusunme:
            try:
                return self.islemci.apply_chat_template(
                    mesajlar, enable_thinking=False, **ortak)
            except TypeError:
                pass          # sürüm desteklemiyor → sızıntı kapısı yakalar
        return self.islemci.apply_chat_template(mesajlar, **ortak)

    @staticmethod
    def bosalt() -> None:
        """Parçalar arası VRAM'i bırak — 30/36 kare marjı jilet gibi."""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:                            # noqa: BLE001
            pass
