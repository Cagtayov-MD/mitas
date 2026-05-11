# v7 vs v11 Media Batch Report

- Output root: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch`
- Elapsed seconds: `306.795`
- Nonzero exits after complete outputs: `6`

| Job | Mode | Window | v7 words | v11 words | v7 total | v11 total | Speedup | Pair F1 | v7 bad | v11 bad |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1_03_05 | full_fallback_shorter_than_3min | 0.000-171.680s | 20 | 28 | 13.374s | 11.742s | 1.139x | 0.6250 | 0 | 0 |
| 2_03_05 | requested_03_05 | 180.000-300.000s | 58 | 161 | 35.743s | 14.418s | 2.479x | 0.5205 | 0 | 0 |
| 3_03_05 | requested_03_05 | 180.000-300.000s | 18 | 24 | 9.801s | 6.904s | 1.420x | 0.8571 | 0 | 0 |
| 4_03_05 | requested_03_05 | 180.000-300.000s | 4 | 9 | 9.476s | 6.899s | 1.374x | 0.0000 | 0 | 0 |
| 5_03_05 | requested_03_05 | 180.000-300.000s | 216 | 217 | 24.044s | 10.746s | 2.237x | 0.9885 | 0 | 0 |
| beyaz1_03_05 | requested_03_05 | 180.000-300.000s | 87 | 685 | 28.744s | 21.736s | 1.322x | 0.1969 | 0 | 0 |
| trt_haber_1_full | full_requested | 0.000-95.660s | 137 | 139 | 18.857s | 9.029s | 2.088x | 0.9203 | 0 | 0 |
| trt_haber_2_full | full_requested | 0.000-146.744s | 256 | 240 | 27.969s | 11.368s | 2.460x | 0.9556 | 0 | 0 |
| trt_haber_3_full | full_requested | 0.000-75.452s | 135 | 134 | 18.318s | 8.309s | 2.205x | 0.9591 | 0 | 0 |

## Per Job Files

### 1_03_05

- Source: `E:\MITAS\testklipler\1.mp4`
- Mode: `full_fallback_shorter_than_3min`
- Audio: `0.000-171.680s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\1_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\1_03_05\out_v11\clean_transcript.txt`

### 2_03_05

- Source: `E:\MITAS\testklipler\2.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\2_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\2_03_05\out_v11\clean_transcript.txt`

### 3_03_05

- Source: `E:\MITAS\testklipler\3.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\3_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\3_03_05\out_v11\clean_transcript.txt`

### 4_03_05

- Source: `E:\MITAS\testklipler\4.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\4_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\4_03_05\out_v11\clean_transcript.txt`

### 5_03_05

- Source: `E:\MITAS\testklipler\5.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\5_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\5_03_05\out_v11\clean_transcript.txt`

### beyaz1_03_05

- Source: `E:\MITAS\testklipler\beyaz1.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\beyaz1_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\beyaz1_03_05\out_v11\clean_transcript.txt`

### trt_haber_1_full

- Source: `E:\MITAS\testklipler\trt_haber (1).mp4`
- Mode: `full_requested`
- Audio: `0.000-95.660s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\trt_haber_1_full\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\trt_haber_1_full\out_v11\clean_transcript.txt`

### trt_haber_2_full

- Source: `E:\MITAS\testklipler\trt_haber (2).mp4`
- Mode: `full_requested`
- Audio: `0.000-146.744s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\trt_haber_2_full\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\trt_haber_2_full\out_v11\clean_transcript.txt`

### trt_haber_3_full

- Source: `E:\MITAS\testklipler\trt_haber (3).mp4`
- Mode: `full_requested`
- Audio: `0.000-75.452s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\trt_haber_3_full\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_media_batch\trt_haber_3_full\out_v11\clean_transcript.txt`


## Artifact And Repetition Flags

- `1_03_05` / `out_v7`: artifacts=['İzlediğiniz için teşekkür ederim'], max_token_run=1, max_token_length=16
- `1_03_05` / `out_v11`: artifacts=['Abone olmayı', 'Altyazı'], max_token_run=1, max_token_length=16
- `2_03_05` / `out_v11`: artifacts=[], max_token_run=2, max_token_length=223
- `4_03_05` / `out_v7`: artifacts=['İzlediğiniz için teşekkür ederim'], max_token_run=1, max_token_length=12
- `4_03_05` / `out_v11`: artifacts=['Altyazı'], max_token_run=1, max_token_length=7
- `beyaz1_03_05` / `out_v11`: artifacts=['İzlediğiniz için teşekkür ederim'], max_token_run=444, max_token_length=13
- `trt_haber_1_full` / `out_v11`: artifacts=['İzlediğiniz için teşekkür ederim'], max_token_run=2, max_token_length=19

## Run Warnings

- `1_03_05` / `out_v11`: exit `3221226505` after all required outputs were written.
- `2_03_05` / `out_v7`: exit `3221226505` after all required outputs were written.
- `2_03_05` / `out_v11`: exit `3221226505` after all required outputs were written.
- `4_03_05` / `out_v7`: exit `3221226505` after all required outputs were written.
- `4_03_05` / `out_v11`: exit `3221226505` after all required outputs were written.
- `beyaz1_03_05` / `out_v11`: exit `3221226505` after all required outputs were written.

## Decision Notes

- Bu raporda referans transcript yok; `Pair F1`, v7 ve v11'in birbirine ne kadar benzediğini gösterir, doğruluk skoru değildir.
- Nihai karar için tam transcriptler `full_transcripts.md` içinde yan yana okunmalıdır.
