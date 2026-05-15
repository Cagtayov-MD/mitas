# ASR Model Final Benchmark References

Bu klasor ASR model final karari icin elle duzeltilmis referans transcriptleri tutar.

Akis:

1. `scripts/asr_model_final_benchmark.py --all` kosulur.
2. `outputs/asr_model_final_benchmark/draft_references/` altindaki taslaklar dinlenerek duzeltilir.
3. Duzeltilen metinler bu klasordeki ilgili `.txt` dosyasina yazilir.
4. Script tekrar kosulur; `wer`, `cer`, hiz ve safety raporu uretilir.

Kurallar:

- Noktalama ve buyuk/kucuk harf model kararini tek basina etkilemez.
- Kisi, kurum, yer, sayi, tarih ve teknik terimler elle ozellikle kontrol edilir.
- Emin olunmayan bolum `[inaudible]` ile isaretlenir; tahmin uydurulmaz.
