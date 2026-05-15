# MITAS Translate Runtime C1 v0.2

> Tarih: 2026-05-15
> Faz: C.1 - Translation service skeleton

## Ozet

`core/pipelines/translate/` paketi eklendi. Ilk surum otomatik pipeline cagrisi yapmaz; yalnizca kullanici/CLI/API tarafindan tetiklenecek servis API'sini hazirlar.

## Public API

```python
from core.pipelines.translate import translate_segment, translate_batch
```

`translate_segment(...)`:

- `segment_id`
- `source_text`
- `source_lang`
- `target_lang="tr"`
- `model_override=None`
- `cache_dir`

`translate_batch(...)` ayni sozlesmeyi liste uzerinden uygular.

## Moduller

- `cache.py` - append-only `cache.jsonl`, SHA1 anahtar
- `router.py` - default route: `en -> opus-mt-tc-big-en-tr`, `* -> nllb-200-3.3b`
- `models.py` - CT2 model registry, lazy load, LRU/idle unload hazirligi
- `runtime.py` - OPUS ve NLLB CT2 adapter'lari
- `service.py` - public API, cache + router + runtime birlesimi

## Dogrulama

Hafif test:

```text
E:\MITAS\venvs\core\Scripts\python.exe -m pytest tests/translate/test_translate_runtime_skeleton.py
```

Sonuc: `4 passed`.

Gercek runtime smoke:

```text
translate_segment("Mr. Prime Minister, one minute please.", source_lang="en")
```

Sonuc:

```text
Sayin Basbakan, bir dakika lutfen.
```

Ilk cagri OPUS modelini yukledi, ikinci cagri cache hit verdi (`latency_ms=0`).

## Notlar

- CUDA DLL arama yolu icin `asr` venv torch DLL dizini eklenir; bu onceki subprocess sleeve kararina uygundur.
- `config/translation_router.yaml` henuz eklenmedi; C.2 adiminda KN-3 kararina gore kalici config yazilacak.
- `pipeline.run_asr_pipeline` icinde otomatik ceviri yoktur; otomatik tetikleme brief disidir.
