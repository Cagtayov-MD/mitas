# v7 vs v11 Decision Review

## Scope

- `1.mp4` through `5.mp4` plus `beyaz1.mp4` were tested with the requested `03:00-05:00` window where available.
- `1.mp4` is only `171.680s`, so the requested `03:00-05:00` window does not exist. It was tested as full-clip fallback and marked as `full_fallback_shorter_than_3min`.
- `trt_haber (1).mp4`, `trt_haber (2).mp4`, and `trt_haber (3).mp4` were tested in full.
- Every item was transcribed once with `out_v7` and once with `out_v11`.

## Summary Table

| Job | Window | v7 words | v11 words | v7 total | v11 total | Pair F1 | Review |
|---|---|---:|---:|---:|---:|---:|---|
| `1_03_05` | full fallback | 20 | 28 | 13.374s | 11.742s | 0.6250 | v11 adds stock artifacts: `Abone olmayı`, `Altyazı`. v7 cleaner. |
| `2_03_05` | 03:00-05:00 | 58 | 161 | 35.743s | 14.418s | 0.5205 | v11 adds long `Hıhı...` hallucination and extra unrelated dialogue. v7 cleaner. |
| `3_03_05` | 03:00-05:00 | 18 | 24 | 9.801s | 6.904s | 0.8571 | v11 catches an extra opening sentence; v11 slightly better here. |
| `4_03_05` | 03:00-05:00 | 4 | 9 | 9.476s | 6.899s | 0.0000 | Both look like low-speech/artifact output. Neither is reliable. |
| `5_03_05` | 03:00-05:00 | 216 | 217 | 24.044s | 10.746s | 0.9885 | v11 is almost identical and faster; v11 acceptable here. |
| `beyaz1_03_05` | 03:00-05:00 | 87 | 685 | 28.744s | 21.736s | 0.1969 | v11 has catastrophic repeated `ben` hallucination. v7 wins. |
| `trt_haber_1_full` | full | 137 | 139 | 18.857s | 9.029s | 0.9203 | v11 faster but adds `İzlediğiniz için teşekkür ederim` and mishears several terms. v7 wins for news quality. |
| `trt_haber_2_full` | full | 256 | 240 | 27.969s | 11.368s | 0.9556 | Both strong. v11 omits some detail but is much faster. v7 remains safer. |
| `trt_haber_3_full` | full | 135 | 134 | 18.318s | 8.309s | 0.9591 | Both strong. v11 has minor name/place slips; v7 slightly safer. |

## Decision

`v7` remains the production-quality default.

`v11` is fast and can be kept as a speed-mode candidate, especially for clean documentary/news narration, but it is not safe as the default yet. The failure mode is not small: on `beyaz1_03_05` it produced a huge repeated-token hallucination, and on `2_03_05` it injected a very long laughter-like token plus unrelated dialogue. These are exactly the kinds of errors that would be expensive to catch downstream.

Recommended policy for now:

- Default ASR model: `v7` / base `large-v3`.
- Optional fast mode: `v11` / base `large-v3-turbo`, behind a quality gate.
- Do not use Selimc `v10` as a production candidate for this media mix.

## Quality Gate Ideas Before Any v11 Production Use

- Reject transcript if `max_consecutive_token_run >= 8`.
- Reject transcript if `max_token_length >= 40`.
- Reject transcript if stock artifact phrases appear, especially `Altyazı`, `Abone olmayı`, or `İzlediğiniz için teşekkür ederim`.
- Reject or re-run with `v7` if v11 word count is more than 2x or less than 0.5x of a cheaper first-pass expectation for the same VAD speech duration.

## Control Questions

**Planla uyumlu mu?**
Evet. İstenen medya seti v7 ve v11 ile ayrı ayrı test edildi. Tek sapma `1.mp4`: istenen 03:00-05:00 aralığı dosyada olmadığı için tam klip fallback yapıldı ve rapora işlendi.

**Amaca hizmet ediyor mu?**
Evet. Bu test v11'in yalnızca hız değil, gerçek medya kalite riskini de görünür yaptı.

**Başka şeyi bozuyor mu?**
Ana pipeline değişmedi. Ancak A/B helper içinde gerçek medyada bulunan negatif/overlap chunk bug'ı düzeltildi ve test eklendi.

**Daha iyi olabilir miydi?**
Evet. Referans transcript olmadığı için otomatik doğruluk skoru yok. Bir sonraki sağlam adım, bu 9 çıktının küçük bir manuel referans setiyle WER/CER skorlanmasıdır.
