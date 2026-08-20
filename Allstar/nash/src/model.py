"""DeepSeek-OCR — transformers'a dokunan TEK yer.

Dışarıya tek şey verir: `sor(png) -> str`. Model BİR KEZ yüklenir; toplu koşuda
film başına yeniden yükleme YOKTUR.

API notları (model/deepseek-ocr/modeling_deepseekocr.py'den okundu, tahmin YOK):
  * `infer(...)` **`eval_mode=True` olmadan metni DÖNDÜRMEZ** — stdout'a akıtır
    ve None döner (satır 910-913: streamer kolu). Sondaj/üretim için eval_mode
    zorunlu.
  * İstem `<image>` ön-ekini AÇIKÇA taşımalı: `"<image>\\nFree OCR."`
    (README satır 126). Ollama tarafında bu ön-eki llama.cpp handler'ı kendi
    ekliyordu; "aynı istem" derken kastedilen budur.
  * `output_path` zorunlu — `infer` içinde `os.makedirs` çağrılıyor. Kulenin
    scratch'ine verilir, dışarı yazılmaz.
  * Çözücü `skip_special_tokens=False` ile decode ediyor → çıktı sonunda EOS
    damgası kalıyor; burada temizlenir.
"""
from __future__ import annotations

import os
import statistics
import time
import types
from pathlib import Path
from typing import Callable

from okuyucu import Bellek, ModelYok

# Cikti sonunda kalan ozel damgalar (tokenizer skip_special_tokens=False ile
# decode ediyor). Metne karisirsa satir sayilir ve kunyeye sizar.
_DAMGA = ("<|end▁of▁sentence|>", "<｜end▁of▁sentence｜>", "<|EOT|>", "</s>")


def _dtype():
    import torch
    return torch.bfloat16


def _attn_secimi() -> str:
    """flash_attention_2 kurulu degilse EAGER'a dus — sdpa'ya DEGIL.

    Olculdu (2026-08-14): DeepseekOCRForCausalLM sdpa'yi reddediyor
    ("does not support an attention implementation through
    torch.nn.functional.scaled_dot_product_attention yet"). Eager her mimarinin
    referans uygulamasidir; yavas ama sadakat sondaji icin DOGRU secim —
    fuzyonlu cekirdek sayisal fark katmaz.

    Hangi yolun secildigi sessizce gecilmez, cagrana basilir (yigin muhru).
    """
    try:
        import flash_attn  # noqa: F401
        return "flash_attention_2"
    except ImportError:
        return "eager"


def _generate_sinirla(model, tokenizer, ayar: dict, torch_mod) -> dict:
    """Uzak `infer` kodundaki 8192-token sabitini yerel ve olculebilir yap.

    Indirilen model dosyasi degistirilmez. `infer`, `self.generate(...)`
    cagirirken bu sarmalayici uzak kodun gonderdigi degerleri guvenli Nash
    sinirlariyla ezer. Tek model/tek is parcacigi oldugu icin instance duzeyi
    sarmalama yarissizdir.
    """
    max_yeni = min(2048, max(1, int(ayar.get("max_new_tokens", 1024))))
    max_sure = min(30.0, max(1.0, float(ayar.get("max_generation_seconds", 30))))
    # DeepSeek-OCR sozlesmesi sabit: uzak kod/tokenizer baska deger tasisa da
    # Nash uretimde EOS=1 ve pad=2 zorlar. Aksi halde modelin 8192 kacagi gibi
    # sonlandirma da indirilen kodun davranisina geri sizabilir.
    eos, pad = 1, 2
    asil_generate = model.generate

    def sinirli_generate(_self, *args, **kwargs):
        kwargs["max_new_tokens"] = max_yeni
        kwargs["max_time"] = max_sure
        kwargs["temperature"] = 0.0
        kwargs["do_sample"] = False
        kwargs["eos_token_id"] = eos
        kwargs["pad_token_id"] = pad
        if "attention_mask" not in kwargs and args:
            try:
                kwargs["attention_mask"] = torch_mod.ones_like(
                    args[0], dtype=torch_mod.long)
            except (AttributeError, TypeError):
                pass
        return asil_generate(*args, **kwargs)

    model.generate = types.MethodType(sinirli_generate, model)
    return {"max_new_tokens": max_yeni, "max_generation_seconds": max_sure,
            "eos_token_id": eos, "pad_token_id": pad}


def _yuzdelik95(degerler: list[float]) -> float:
    if not degerler:
        return 0.0
    sirali = sorted(degerler)
    return sirali[min(len(sirali) - 1, round(0.95 * (len(sirali) - 1)))]


def yukle(ayar: dict, kule: Path) -> Callable[[Path], str]:
    """Modeli yükle → `sor(png) -> str`. Yoksa ModelYok (main ARIZA(MODEL) yapar)."""
    import torch
    from transformers import AutoModel, AutoTokenizer

    yol = Path(ayar.get("model_yol", "model/deepseek-ocr"))
    if not yol.is_absolute():
        yol = Path(kule) / yol
    if not (yol / "config.json").is_file():
        raise ModelYok(f"model agirligi yok: {yol} — once ./model_kur.sh")

    istem = ayar.get("istem", "Free OCR.")
    tam_istem = istem if istem.startswith("<image>") else f"<image>\n{istem}"
    scratch = Path(kule) / "scratch" / "model_cikti"
    scratch.mkdir(parents=True, exist_ok=True)
    attn = _attn_secimi()

    try:
        tokenizer = AutoTokenizer.from_pretrained(str(yol), trust_remote_code=True)
        model = AutoModel.from_pretrained(
            str(yol), trust_remote_code=True, use_safetensors=True,
            _attn_implementation=attn)
        model = model.eval().cuda().to(_dtype())
        sinirlar = _generate_sinirla(model, tokenizer, ayar, torch)
        torch.cuda.reset_peak_memory_stats()
    except torch.cuda.OutOfMemoryError as e:
        raise Bellek(f"model yuklenirken OOM: {e}") from e
    except Exception as e:  # noqa: BLE001
        raise ModelYok(f"{type(e).__name__}: {e}") from e

    print(f"[model] {yol.name} yuklendi · attn={attn} · dtype=bfloat16 · "
          f"max_new={sinirlar['max_new_tokens']} · "
          f"max_gen={sinirlar['max_generation_seconds']}s", flush=True)

    sureler: list[float] = []
    cikti_tokenleri: list[int] = []
    istemler: dict[str, int] = {}

    def sor(p: Path, prompt: str | None = None) -> str:
        t0 = time.monotonic()
        try:
            with torch.inference_mode():
                kullanilan_istem = prompt or tam_istem
                if not kullanilan_istem.startswith("<image>"):
                    kullanilan_istem = f"<image>\n{kullanilan_istem}"
                tur = "grounding" if "<|grounding|>" in kullanilan_istem else "free_ocr"
                istemler[tur] = istemler.get(tur, 0) + 1
                cevap = model.infer(
                    tokenizer, prompt=kullanilan_istem, image_file=str(p),
                    output_path=str(scratch),
                    base_size=int(ayar.get("base_size", 1024)),
                    image_size=int(ayar.get("image_size", 640)),
                    crop_mode=bool(ayar.get("crop_mode", True)),
                    save_results=False,
                    eval_mode=True)          # ZORUNLU: aksi halde None doner
        except torch.cuda.OutOfMemoryError as e:
            torch.cuda.empty_cache()
            raise Bellek(str(e)) from e
        finally:
            sureler.append(time.monotonic() - t0)
        s = cevap if isinstance(cevap, str) else ""
        for d in _DAMGA:
            s = s.replace(d, "")
        s = s.strip()
        try:
            cikti_tokenleri.append(len(tokenizer.encode(
                s, add_special_tokens=False)))
        except Exception:
            cikti_tokenleri.append(0)
        return s

    def metrikler() -> dict:
        peak = (torch.cuda.max_memory_reserved() / (1024 * 1024)
                if torch.cuda.is_available() else 0.0)
        return {"model_cagri_n": len(sureler),
                "model_cagri_basarili_n": len(cikti_tokenleri),
                "model_cagri_toplam_sn": round(sum(sureler), 3),
                "model_cagri_medyan_sn": round(statistics.median(sureler), 3)
                if sureler else 0.0,
                "model_cagri_p95_sn": round(_yuzdelik95(sureler), 3),
                "model_cagri_max_sn": round(max(sureler), 3) if sureler else 0.0,
                "cikti_token_toplam": sum(cikti_tokenleri),
                "cikti_token_medyan": round(statistics.median(cikti_tokenleri), 1)
                if cikti_tokenleri else 0.0,
                "cikti_token_max": max(cikti_tokenleri) if cikti_tokenleri else 0,
                "istemler": dict(istemler),
                "vram_peak_mb": round(peak, 1), **sinirlar,
                "attention": attn, "dtype": "bfloat16"}

    sor.metrics = metrikler  # type: ignore[attr-defined]
    sor.limits = dict(sinirlar)  # type: ignore[attr-defined]

    return sor
