# MITAS MT Eval Set v0.2

> Tarih: 2026-05-15
> Faz: A.5 - EN->TR benchmark veri seti

## Ozet

FLORES-200 devtest uzerinden deterministik 100 cumlelik EN->TR eval seti olusturuldu.

- Kaynak: `https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz`
- Cache: `cache/external_datasets/flores200/`
- Cikti: `data/translate_eval/flores_en_tr_100.jsonl`
- Seed: `42`
- Satir sayisi: `100`
- Bos `src` / `ref`: `0`

## Uretim

Script:

```text
python scripts/translate_build_eval.py
```

Rapor:

```text
outputs/translate_eval/flores_en_tr_100_report.json
```

## Not

Bu set hizli Faz A karar setidir. TRT-domain gercek benchmark daha sonra ayri eklenmelidir.
