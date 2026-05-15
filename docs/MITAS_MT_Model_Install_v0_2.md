# MITAS MT Model Install v0.2

> Tarih: 2026-05-15
> Faz: A.3 - MT modellerini indirme ve CTranslate2 donusumu

## Ozet

Faz A benchmark havuzu icin uc MT adayi indirildi ve CTranslate2 formatina donusturuldu:

| Kisa ad | HF model | CT2 cikti | Quant | model.bin |
|---|---|---|---|---|
| `nllb_3b` | `facebook/nllb-200-3.3B` | `models/translate/nllb-200-3.3B-ct2-int8` | `int8_float16` | 3.13 GB |
| `nllb_1b` | `facebook/nllb-200-distilled-1.3B` | `models/translate/nllb-200-distilled-1.3B-ct2-int8` | `int8_float16` | 1.28 GB |
| `opus` | `Helsinki-NLP/opus-mt-tc-big-en-tr` | `models/translate/opus-mt-tc-big-en-tr-ct2-int8` | `int8` | 0.22 GB |

Raw Hugging Face snapshot'lari tekrar uretilebilirlik icin `models/translate/_hf_snapshots/` altinda tutuldu. `models/` git disi oldugu icin repo sismez.

## Uygulama Notlari

- Kurulum scripti: `scripts/translate_install_models.py`
- Denetim raporu: `outputs/translate_model_install_report.json`
- `nllb_3b`, `nllb_1b`, `opus` ve `all` hedefleri desteklenir.
- Script idempotent davranir; `model.bin` varsa ayni hedefi tekrar donusturmez. Zorunlu tekrar icin `--force` kullanilir.

## Converter Uyumluluk Notu

Ilk donusum denemesinde `ctranslate2==4.7.1` converter, `transformers==4.46.3` ile NLLB yuklerken `dtype=` argumani nedeniyle durdu:

```text
M2M100ForConditionalGeneration.__init__() got an unexpected keyword argument 'dtype'
```

Paket pinleri degistirilmedi. Bunun yerine script icinde kucuk bir `CompatTransformersConverter` katmani eklendi ve `dtype` argumani `torch_dtype` olarak normalize edildi. Bu, izole `translate` venv icinde kalir; ASR venv'e dokunmaz.

## Dogrulama

- `nllb-200-3.3B-ct2-int8/model.bin` mevcut.
- `nllb-200-distilled-1.3B-ct2-int8/model.bin` mevcut.
- `opus-mt-tc-big-en-tr-ct2-int8/model.bin` mevcut.
- Tum hedeflerde tokenizer dosyalari eksiksiz kopyalandi.

Sonraki adim: Faz A.4 smoke test scripti ile uc modelin EN->TR ornek cikti verdigini dogrulamak.
