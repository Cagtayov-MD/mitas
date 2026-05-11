Sonuç: multilingual=True default kullan, sorun tamamen çözüldü

| Test | Final exit | Transcript kalite | Süre | Not |
|---|---:|---|---|---|
| TM1 | 0x00000000 | reasonable=True | min=2.364, max=2.574, avg=2.439 | wav_erd 3x aynı instance |
| TM2 | 0x00000000 | reasonable=True | 2.582 | wav_erd tek transcribe |
| TM3 | 0x00000000 | regression_ok=True | - | news_trt_haber_1: sim=0.8794, slowdown=1.151; promo_1: sim=0.9508, slowdown=1.125 |

## TM2 Transcript

I mean, Mr. Prime Minister, I, with apologies to Prime Minister Erdogan. One minute. One minute. One minute. One minute. Well, you know... One minute. One minute. One minute. I'm going to hold you to the one minute, please.

## TM3 Regression

| Clip | Exact | Similarity | Ref sec | Multilingual sec | Slowdown |
|---|---:|---:|---:|---:|---:|
| news_trt_haber_1 | false | 0.8794 | 2.371 | 2.73 | 1.151 |
| promo_1 | false | 0.9508 | 0.906 | 1.019 | 1.125 |
