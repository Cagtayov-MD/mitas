# MITAS MT Smoke v0.2

> Tarih: 2026-05-15
> Faz: A.4 - MT smoke test

## Ozet

`scripts/translate_smoke.py` ile uc MT adayi CUDA uzerinde EN->TR smoke testinden gecti:

- `nllb_3b`
- `nllb_1b`
- `opus`

Rapor JSON: `outputs/translate_smoke_report.json`

## Ornek Sonuclar

| Model | EN | TR | Latency |
|---|---|---|---|
| `nllb_3b` | The press conference will start in five minutes. | Basin toplantisi bes dakika icinde baslayacak. | 398.0 ms |
| `nllb_1b` | The press conference will start in five minutes. | Basin toplantisi bes dakika sonra baslayacak. | 450.1 ms |
| `opus` | The press conference will start in five minutes. | Basin toplantisi bes dakika icinde baslayacak. | 76.6 ms |
| `nllb_3b` | Mr. Prime Minister, one minute please. | Sayin Basbakan, bir dakika lutfen. | 400.3 ms |
| `nllb_1b` | Mr. Prime Minister, one minute please. | Sayin Basbakan, bir dakika lutfen. | 438.5 ms |
| `opus` | Mr. Prime Minister, one minute please. | Sayin Basbakan, bir dakika lutfen. | 82.7 ms |

## Notlar

- CUDA icin `cublas64_12.dll` sistem PATH'inde degildi. Script, MITAS'in mevcut `asr` venv torch DLL dizinini import oncesi DLL arama yoluna ekliyor.
- Bu smoke kalite benchmark'i degildir. Yalnizca model yukleme, tokenizer uyumu, CT2 runtime ve kisa EN->TR cikti akisini dogrular.
- OPUS bu kisa EN->TR smoke setinde belirgin hizli. Kalite karari Faz A.6 COMET/CHRF benchmark'indan sonra verilecek.
