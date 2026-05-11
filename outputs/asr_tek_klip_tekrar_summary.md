wav_erd_test_sound: 10/10 kirli (deterministik patolojik klip)

| Test | Clip | Dirty/Clean | Transcript variance | Transcribe seconds |
|---|---|---:|---|---|
| TF1 | wav_erd_test_sound | 10/0 | all_identical=false, unique=10 | min=15.965, max=26.835, avg=22.246 |
| TF2 | news_trt_haber_1 | 0/10 | all_identical=true, unique=1 | min=2.319, max=2.452, avg=2.378 |
| TF3 | promo_1 | 0/10 | all_identical=true, unique=1 | min=0.873, max=0.96, avg=0.926 |

## Pipeline Karari

Tolerant containment + low_quality flag wav_erd benzeri için yeterli. Multi-clip aynı process güvenli; wav_erd exit 10/10 kirli, transcript varied.
