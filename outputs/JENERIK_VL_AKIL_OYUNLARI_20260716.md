# Jenerik VL Okuma Raporu — /opt/mitas/testklipler/2.mp4

## 1. Sıklık testi (aynı 60s pencere, 768px)
| kare | fps | prompt-token | üretim-token | süre |
|---|---|---|---|---|
| 12 | 0.20 | 2533 | 6000 | 141.9s |
| 30 | 0.50 | 6178 | 6000 | 135.2s |
| 60 | 1.00 | 12253 | 6000 | 141.5s |

## 2. Süre testi — tüm jenerik TEK video girdisi
- 400s @ 0.5fps (200 kare): **SIĞMADI/HATA** — ValueError: The decoder prompt (length 40560) is longer than the maximum model length of 32768. Make sure that `max_model_len` is no smaller than the number of te
- 400s @ 1.0fps (400 kare): **SIĞMADI/HATA** — ValueError: The decoder prompt (length 81060) is longer than the maximum model length of 32768. Make sure that `max_model_len` is no smaller than the number of te

## 3. Tam jenerik okuma (kayan pencere, kare-bölümlü, 1fps)

### Pencere 1 — HATA: EngineDeadError

### Pencere 2 — HATA: EngineDeadError

### Pencere 3 — HATA: EngineDeadError

### Pencere 4 — HATA: EngineDeadError

### Pencere 5 — HATA: EngineDeadError
