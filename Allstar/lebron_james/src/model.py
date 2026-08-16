"""DeepSeek-OCR — transformers'a dokunan TEK yer.

Dışarıya tek şey verir: `sor(png) -> str`. Model BİR KEZ yüklenir; toplu koşuda
film başına yeniden yükleme YOKTUR.

NEDEN KULE İÇİNDE (Çağatay, 2026-08-15): üretimdeki okuyucu
(`_pipe_hibrit_okuma.ollama_oku`) Ollama'ya HTTP atıyor. Dışarıdaki bir servise
bağlı kule kendi kendine yeten bir kule değildir; ayrıca Ollama açıkken Kobe
skoru %94.5 → %93.6 düşüyor (ölçüldü). Model, istem ve bant geometrisi AYNI
kalır — yalnız taşıyıcı değişir.

API notları (model/deepseek-ocr/modeling_deepseekocr.py'den okundu, tahmin YOK
— Nash'in aynı geçişte çıkardığı notlar):
  * `infer(...)` **`eval_mode=True` olmadan metni DÖNDÜRMEZ** — stdout'a akıtır
    ve None döner (streamer kolu). Üretim için eval_mode zorunlu.
  * İstem `<image>` ön-ekini AÇIKÇA taşımalı: `"<image>\\nFree OCR."`
    Ollama tarafında bu ön-eki llama.cpp handler'ı kendi ekliyordu; "aynı istem"
    derken kastedilen budur.
  * `output_path` zorunlu — `infer` içinde `os.makedirs` çağrılıyor. Kulenin
    scratch'ine verilir, dışarı yazılmaz.
  * Çözücü `skip_special_tokens=False` ile decode ediyor → çıktı sonunda EOS
    damgası kalıyor; burada temizlenir.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from okuyucu import Bellek, ModelYok

# Cikti sonunda kalan ozel damgalar. Metne karisirsa satir sayilir ve kunyeye
# sizar.
_DAMGA = ("<|end▁of▁sentence|>", "<｜end▁of▁sentence｜>", "<|EOT|>", "</s>")


def _attn_secimi() -> str:
    """flash_attention_2 kurulu degilse EAGER'a dus — sdpa'ya DEGIL.

    Nash'te olculdu (2026-08-14): DeepseekOCRForCausalLM sdpa'yi reddediyor
    ("does not support an attention implementation through
    torch.nn.functional.scaled_dot_product_attention yet"). Eager her mimarinin
    referans uygulamasidir; yavas ama DOGRU secim.

    Hangi yolun secildigi sessizce gecilmez, cagrana basilir (yigin muhru).
    """
    try:
        import flash_attn  # noqa: F401
        return "flash_attention_2"
    except ImportError:
        return "eager"


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
        model = model.eval().cuda().to(torch.bfloat16)
    except torch.cuda.OutOfMemoryError as e:
        raise Bellek(f"model yuklenirken OOM: {e}") from e
    except Exception as e:  # noqa: BLE001
        raise ModelYok(f"{type(e).__name__}: {e}") from e

    print(f"[model] {yol.name} yuklendi · attn={attn} · dtype=bfloat16", flush=True)

    def sor(p: Path) -> str:
        try:
            with torch.inference_mode():
                cevap = model.infer(
                    tokenizer, prompt=tam_istem, image_file=str(p),
                    output_path=str(scratch),
                    base_size=int(ayar.get("base_size", 1024)),
                    image_size=int(ayar.get("image_size", 640)),
                    crop_mode=bool(ayar.get("crop_mode", True)),
                    save_results=False,
                    eval_mode=True)          # ZORUNLU: aksi halde None doner
        except torch.cuda.OutOfMemoryError as e:
            torch.cuda.empty_cache()
            raise Bellek(str(e)) from e
        s = cevap if isinstance(cevap, str) else ""
        for d in _DAMGA:
            s = s.replace(d, "")
        return s.strip()

    return sor
