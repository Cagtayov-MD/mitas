# ASR Archive Full Benchmark References

Bu klasor TRT arsiv WAV tam kapsamli ASR testi icin elle hazirlanmis referans transcriptleri tutar.

Beklenen dosyalar:

- `baris_manco_7den_77ye_full.txt`
- `neretva_ustune_dusen_hilal_full.txt`
- `merakli_momolar_full.txt`

Akis:

1. `scripts/asr_model_final_benchmark.py --manifest benchmark_templates/asr_archive_full_benchmark.yaml --out-root outputs/asr_archive_full_benchmark --all` kosulur.
2. Elle hazirlanmis tam transcriptler bu klasordeki ilgili `.txt` dosyalarina yazilir.
3. Script `--score` ile tekrar kosulur; `wer`, `cer`, hiz ve safety raporu uretilir.

Kurallar:

- Noktalama ve buyuk/kucuk harf model kararini tek basina etkilemez.
- Kisi, kurum, yer, sayi, tarih ve teknik terimler elle ozellikle kontrol edilir.
- Emin olunmayan bolum `[inaudible]` ile isaretlenir; tahmin uydurulmaz.
