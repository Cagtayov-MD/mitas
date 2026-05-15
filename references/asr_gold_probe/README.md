# ASR Gold Probe References

Bu klasor fast/quality/hybrid kararini gercek WER/CER ile olcmek icin kucuk elle dogrulanmis referans setini tutar.

Yeni review akisi:

1. Once review paketi uretilir:

```powershell
python scripts/asr_model_final_benchmark.py --manifest benchmark_templates/asr_gold_probe_benchmark.yaml --out-root outputs/asr_gold_probe_benchmark --review
```

2. Kullanici `outputs/asr_gold_probe_benchmark/review_candidates/*.txt` aday ASR metnini dinler.
3. Bastan transcript yazmaz; sadece hatali kelime/ifadeleri bildirir.
4. Duzeltmeler bu klasordeki ayni isimli `.txt` dosyasina islenir.

Skor icin bu dosyalarda zaman damgasi, TODO satiri veya draft yorum satiri kalmamalidir.
