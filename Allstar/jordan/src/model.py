"""Qwen-VL modelini yükleyen ve soran TEK yer.

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
    """Yüklenmiş model + işlemci.

    Ana okuma yolu ayrı görüntülerden oluşan ``kareler`` listesidir. Native
    video girdi yolu bilerek yoktur. Metin-only çağrı, eski isteğe bağlı
    rol/isim türeticisinin kontrollü yoludur.
    """

    def __init__(self, model_yolu: str | Path, dtype: str = "bfloat16",
                 dusunme: bool = False, uretim: dict | None = None,
                 gorsel: dict | None = None) -> None:
        self.yol = str(model_yolu)
        self.dtype = dtype
        self.dusunme = dusunme
        self.uretim = uretim or {}
        # gorsel: islemci seviyesi token butcesi (min_pixels/max_pixels).
        self.gorsel = dict(gorsel or {})
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
            self._gorsel_uygula()
            self.model = self._model_sinifi().from_pretrained(
                self.yol,
                dtype=getattr(torch, self.dtype),
                device_map="cuda",
            )
            self.model.eval()
        except Exception as e:                      # noqa: BLE001
            raise self._sinifla(e) from e
        return self

    def _gorsel_uygula(self) -> None:
        """min_pixels/max_pixels'i alt islemcilere DOGRUDAN yaz.

        transformers 5.x'te bunlari from_pretrained'e kwarg olarak vermek
        SESSIZCE etkisiz kaliyor ("Kwargs passed to processor.__call__ have to
        be in processor_kwargs dict" uyarisi). Ayarladigini sanip ayarlamamak
        en kotu hata sinifi — o yuzden yazip GERI OKUYUP dogruluyoruz.
        """
        if not self.gorsel:
            return
        hedefler = [getattr(self.islemci, a, None)
                    for a in ("image_processor", "video_processor")]
        for h in hedefler:
            if h is None:
                continue
            for k, v in self.gorsel.items():
                setattr(h, k, v)
                if getattr(h, k, None) != v:
                    raise ModelHatasi(f"{k} islemciye yazilamadi ({type(h).__name__})")

    @staticmethod
    def _model_sinifi():
        """Mimarinin kendi Auto kaydını kullan; modeli yanlış sınıfa zorlama."""
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
    def sor(self, istem: str, kareler: list[str] | None = None) -> str:
        """Tek istek → ham metin.

        ``kareler`` her resmi ayrı ``image`` girdisi yapar; bu, KSK
        karşılaştırmasında ölçülen tek görsel besleme biçimidir.
        """
        if self.model is None:
            self.yukle()
        import torch

        icerik = []
        if kareler:
            icerik.extend({"type": "image", "image": str(k)} for k in kareler)
        icerik.append({"type": "text", "text": istem})
        mesajlar = [{"role": "user", "content": icerik}]

        try:
            girdi = self._hazirla(mesajlar).to(self.model.device)
            with torch.inference_mode():
                cikti = self.model.generate(**girdi, **self.uretim_kwargs())
            kirpik = [o[len(g):] for g, o in zip(girdi.input_ids, cikti)]
            ham = self.islemci.batch_decode(
                kirpik, skip_special_tokens=True,
                clean_up_tokenization_spaces=False)[0]
        except Exception as e:                      # noqa: BLE001
            raise self._sinifla(e) from e
        finally:
            self.bosalt()

        metin, sizdi = _dusunme_ayikla(ham)
        self.sizinti += int(sizdi)
        if not metin:
            raise CiktiBozuk("model bos cevap dondu")
        return metin

    def uretim_kwargs(self) -> dict:
        """config.yaml `uretim:` → generate() argumanlari.

        Config'te ne yazarsan generate'e o gider — burada beyaz liste ya da
        dogrulama YOK. Ayar alanini kisitlamak bu dosyanin isi degil.
        """
        kw = {"max_new_tokens": 1024, "do_sample": False,
              "repetition_penalty": 1.05, **self.uretim}
        # do_sample=False iken temperature/top_p/top_k transformers'ta uyari
        # uretir ve zaten etkisizdir — greedy'de orneklem yoktur.
        if not kw.get("do_sample"):
            for a in ("temperature", "top_p", "top_k", "min_p"):
                kw.pop(a, None)
        return kw

    def _sablon_metni(self, mesajlar) -> str:
        """Görsel işlemcisine verilecek sohbet metnini oluştur."""
        ortak = dict(tokenize=False, add_generation_prompt=True)
        if not self.dusunme:
            try:
                return self.islemci.apply_chat_template(
                    mesajlar, enable_thinking=False, **ortak)
            except TypeError:
                pass          # sürüm desteklemiyor → sızıntı kapısı yakalar
        return self.islemci.apply_chat_template(mesajlar, **ortak)

    def _hazirla(self, mesajlar):
        """KSK koşucusuyla aynı Qwen-VL görsel hazırlama yolunu kullan."""
        gorsel_var = any(
            oge.get("type") == "image"
            for mesaj in mesajlar for oge in mesaj.get("content", [])
            if isinstance(oge, dict))
        if not gorsel_var:
            ortak = dict(tokenize=True, add_generation_prompt=True,
                         return_dict=True, return_tensors="pt")
            if not self.dusunme:
                try:
                    return self.islemci.apply_chat_template(
                        mesajlar, enable_thinking=False, **ortak)
                except TypeError:
                    pass
            return self.islemci.apply_chat_template(mesajlar, **ortak)

        try:
            from qwen_vl_utils import process_vision_info
        except Exception as e:                      # noqa: BLE001
            raise ModelHatasi(f"qwen-vl-utils yuklenemedi: {e}") from e
        metin = self._sablon_metni(mesajlar)
        gorseller, videolar = process_vision_info(mesajlar)
        return self.islemci(
            text=[metin], images=gorseller, videos=videolar,
            padding=True, return_tensors="pt")

    @staticmethod
    def bosalt() -> None:
        """Kare grupları arası kullanılmayan CUDA önbelleğini bırak."""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:                            # noqa: BLE001
            pass
