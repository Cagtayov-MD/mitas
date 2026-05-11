# v7 vs v11 Media Batch Report

- Output root: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality`
- Elapsed seconds: `289.329`
- Nonzero exits after complete outputs: `0`

| Job | Mode | Window | v7 words | v11 words | v7 total | v11 total | Speedup | Pair F1 | v7 bad | v11 bad |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1_03_05 | full_fallback_shorter_than_3min | 0.000-171.680s | 33 | 16 | 12.002s | 9.574s | 1.254x | 0.6122 | 0 | 0 |
| 2_03_05 | requested_03_05 | 180.000-300.000s | 156 | 160 | 36.029s | 13.875s | 2.597x | 0.8861 | 0 | 0 |
| 3_03_05 | requested_03_05 | 180.000-300.000s | 24 | 24 | 9.611s | 6.776s | 1.418x | 1.0000 | 0 | 0 |
| 4_03_05 | requested_03_05 | 180.000-300.000s | 0 | 0 | 9.278s | 6.654s | 1.394x | 0.0000 | 0 | 0 |
| 5_03_05 | requested_03_05 | 180.000-300.000s | 216 | 217 | 22.808s | 10.392s | 2.195x | 0.9885 | 0 | 0 |
| beyaz1_03_05 | requested_03_05 | 180.000-300.000s | 297 | 237 | 27.428s | 21.027s | 1.304x | 0.8427 | 0 | 0 |
| trt_haber_1_full | full_requested | 0.000-95.660s | 137 | 135 | 18.927s | 9.156s | 2.067x | 0.9338 | 0 | 0 |
| trt_haber_2_full | full_requested | 0.000-146.744s | 256 | 240 | 27.910s | 11.407s | 2.447x | 0.9556 | 0 | 0 |
| trt_haber_3_full | full_requested | 0.000-75.452s | 135 | 134 | 18.144s | 8.327s | 2.179x | 0.9591 | 0 | 0 |

## Per Job Files

### 1_03_05

- Source: `E:\MITAS\testklipler\1.mp4`
- Mode: `full_fallback_shorter_than_3min`
- Audio: `0.000-171.680s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\1_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\1_03_05\out_v11\clean_transcript.txt`

### 2_03_05

- Source: `E:\MITAS\testklipler\2.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\2_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\2_03_05\out_v11\clean_transcript.txt`

### 3_03_05

- Source: `E:\MITAS\testklipler\3.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\3_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\3_03_05\out_v11\clean_transcript.txt`

### 4_03_05

- Source: `E:\MITAS\testklipler\4.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\4_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\4_03_05\out_v11\clean_transcript.txt`

### 5_03_05

- Source: `E:\MITAS\testklipler\5.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\5_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\5_03_05\out_v11\clean_transcript.txt`

### beyaz1_03_05

- Source: `E:\MITAS\testklipler\beyaz1.mp4`
- Mode: `requested_03_05`
- Audio: `180.000-300.000s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\beyaz1_03_05\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\beyaz1_03_05\out_v11\clean_transcript.txt`

### trt_haber_1_full

- Source: `E:\MITAS\testklipler\trt_haber (1).mp4`
- Mode: `full_requested`
- Audio: `0.000-95.660s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\trt_haber_1_full\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\trt_haber_1_full\out_v11\clean_transcript.txt`

### trt_haber_2_full

- Source: `E:\MITAS\testklipler\trt_haber (2).mp4`
- Mode: `full_requested`
- Audio: `0.000-146.744s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\trt_haber_2_full\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\trt_haber_2_full\out_v11\clean_transcript.txt`

### trt_haber_3_full

- Source: `E:\MITAS\testklipler\trt_haber (3).mp4`
- Mode: `full_requested`
- Audio: `0.000-75.452s`
- v7 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\trt_haber_3_full\out_v7\clean_transcript.txt`
- v11 transcript: `E:\MITAS\outputs\asr_ab\v7_v11_fixed_03_05_quality\trt_haber_3_full\out_v11\clean_transcript.txt`


## Artifact And Repetition Flags

- No artifact/repetition flags.

## Safety Decisions

- `1_03_05` / `out_v7`: safe=`True`, failure=`None` diagnostics=`{'max_run': 2, 'repeated_token': 'Arda', 'max_token_length': 16, 'words_per_second': 1.95}`
- `1_03_05` / `out_v11`: safe=`True`, failure=`None` diagnostics=`{'max_run': 0, 'repeated_token': None, 'max_token_length': 17, 'words_per_second': 0.94}`
- `2_03_05` / `out_v7`: safe=`True`, failure=`None` diagnostics=`{'max_run': 2, 'repeated_token': 'Evet.', 'max_token_length': 17, 'words_per_second': 2.33}`
- `2_03_05` / `out_v11`: safe=`True`, failure=`None` diagnostics=`{'max_run': 2, 'repeated_token': 'Evet.', 'max_token_length': 17, 'words_per_second': 2.4}`
- `3_03_05` / `out_v7`: safe=`True`, failure=`None` diagnostics=`{'max_run': 1, 'repeated_token': 'Baba,', 'max_token_length': 9, 'words_per_second': 3.48}`
- `3_03_05` / `out_v11`: safe=`True`, failure=`None` diagnostics=`{'max_run': 1, 'repeated_token': 'Baba,', 'max_token_length': 9, 'words_per_second': 3.48}`
- `4_03_05` / `out_v7`: safe=`True`, failure=`None` diagnostics=`{'max_run': 0, 'repeated_token': None, 'max_token_length': 0, 'words_per_second': 0.0}`
- `4_03_05` / `out_v11`: safe=`True`, failure=`None` diagnostics=`{'max_run': 0, 'repeated_token': None, 'max_token_length': 0, 'words_per_second': 0.0}`
- `5_03_05` / `out_v7`: safe=`True`, failure=`None` diagnostics=`{'max_run': 2, 'repeated_token': 'çok', 'max_token_length': 15, 'words_per_second': 2.1}`
- `5_03_05` / `out_v11`: safe=`True`, failure=`None` diagnostics=`{'max_run': 2, 'repeated_token': 'çok', 'max_token_length': 15, 'words_per_second': 2.1}`
- `beyaz1_03_05` / `out_v7`: safe=`True`, failure=`None` diagnostics=`{'max_run': 1, 'repeated_token': 'Konusu', 'max_token_length': 13, 'words_per_second': 2.67}`
- `beyaz1_03_05` / `out_v11`: safe=`True`, failure=`None` diagnostics=`{'max_run': 3, 'repeated_token': 'Evet.', 'max_token_length': 13, 'words_per_second': 2.14}`
- `trt_haber_1_full` / `out_v7`: safe=`True`, failure=`None` diagnostics=`{'max_run': 2, 'repeated_token': 'tek', 'max_token_length': 20, 'words_per_second': 1.97}`
- `trt_haber_1_full` / `out_v11`: safe=`True`, failure=`None` diagnostics=`{'max_run': 2, 'repeated_token': 'tek', 'max_token_length': 20, 'words_per_second': 1.92}`
- `trt_haber_2_full` / `out_v7`: safe=`True`, failure=`None` diagnostics=`{'max_run': 1, 'repeated_token': 'Ben', 'max_token_length': 15, 'words_per_second': 2.02}`
- `trt_haber_2_full` / `out_v11`: safe=`True`, failure=`None` diagnostics=`{'max_run': 1, 'repeated_token': 'Ben', 'max_token_length': 15, 'words_per_second': 1.89}`
- `trt_haber_3_full` / `out_v7`: safe=`True`, failure=`None` diagnostics=`{'max_run': 1, 'repeated_token': "İstanbul'da", 'max_token_length': 14, 'words_per_second': 2.21}`
- `trt_haber_3_full` / `out_v11`: safe=`True`, failure=`None` diagnostics=`{'max_run': 1, 'repeated_token': "İstanbul'da", 'max_token_length': 14, 'words_per_second': 2.18}`
## Decision Notes

- Bu raporda referans transcript yok; `Pair F1`, v7 ve v11'in birbirine ne kadar benzediğini gösterir, doğruluk skoru değildir.
- Nihai karar için tam transcriptler `full_transcripts.md` içinde yan yana okunmalıdır.
