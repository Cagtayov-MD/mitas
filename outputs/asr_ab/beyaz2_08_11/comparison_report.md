# beyaz2 08:00-11:00 ASR A/B Comparison

- Reference: `C:\Users\TRT03\Downloads\beyaz2 08 11.txt`
- Output root: `E:\MITAS\outputs\asr_ab\beyaz2_08_11`

| Variant | Raw | Clean | Dropped | Bad hits | Code-switch | Similarity | Word F1 | Calls | Total s | Drop reasons | Languages |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| out_v0 | 58 | 56 | 2 | 1 | 4 | 0.0728 | 0.8585 | 28 | 44.652 | `{'no_speech': 2}` | `{'tr': 55, 'en': 1}` |
| out_v1 | 43 | 43 | 0 | 1 | 4 | 0.0806 | 0.7851 | 28 | 37.089 | `{}` | `{'tr': 43}` |
| out_v2 | 28 | 27 | 1 | 1 | 4 | 0.0421 | 0.6703 | 8 | 28.874 | `{'no_speech': 1}` | `{'tr': 27}` |
| out_v3 | 13 | 7 | 6 | 1 | 0 | 0.0092 | 0.3750 | 7 | 21.993 | `{'overlap_duplicate': 6}` | `{'tr': 7}` |
| out_v4 | 36 | 32 | 4 | 0 | 3 | 0.0430 | 0.7864 | 1 | 31.420 | `{'no_speech': 4}` | `{'tr': 32}` |
| out_v5 | 13 | 7 | 6 | 1 | 0 | 0.0092 | 0.3750 | 7 | 21.271 | `{'overlap_duplicate': 6}` | `{'tr': 7}` |
| out_v6 | 28 | 27 | 1 | 1 | 4 | 0.0421 | 0.6703 | 8 | 28.724 | `{'no_speech': 1}` | `{'tr': 27}` |
| out_v7 | 56 | 56 | 0 | 0 | 4 | 0.0836 | 0.8814 | 8 | 32.733 | `{}` | `{'tr': 56}` |
| out_v8 | 55 | 55 | 0 | 0 | 4 | 0.0908 | 0.8696 | 1 | 28.679 | `{}` | `{'tr': 55}` |
| out_v9 | 8 | 8 | 0 | 0 | 4 | 0.1683 | 0.8783 | 1 | 15.103 | `{}` | `{'tr': 8}` |
| out_v10 | 29 | 28 | 1 | 0 | 4 | 0.0069 | 0.8037 | 8 | 16.440 | `{'low_logprob': 1}` | `{'tr': 28}` |

## Token Checks

### out_v0 - v0_baseline_current

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': True, 'Konuklar Türkçe sohbet ediyor': False}`
- Code-switch hits: `{'Dancin': True, 'Dancing': True, 'Beer': False, 'Bear': True, 'Ayılar Dans': True}`

### out_v1 - v1_minimal_patch_filter_language

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': True}`
- Code-switch hits: `{'Dancin': True, 'Dancing': True, 'Beer': False, 'Bear': True, 'Ayılar Dans': True}`

### out_v2 - v2_vad_guided_merged_chunks

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': True}`
- Code-switch hits: `{'Dancin': True, 'Dancing': True, 'Beer': False, 'Bear': True, 'Ayılar Dans': True}`

### out_v3 - v3_fixed_28s_windows

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': True}`
- Code-switch hits: `{'Dancin': False, 'Dancing': False, 'Beer': False, 'Bear': False, 'Ayılar Dans': False}`

### out_v4 - v4_full_audio_single_pass

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': False}`
- Code-switch hits: `{'Dancin': True, 'Dancing': True, 'Beer': False, 'Bear': False, 'Ayılar Dans': True}`

### out_v5 - v5_fixed_28s_multilingual_code_switch

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': True}`
- Code-switch hits: `{'Dancin': False, 'Dancing': False, 'Beer': False, 'Bear': False, 'Ayılar Dans': False}`

### out_v6 - v6_vad_merged_multilingual_code_switch

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': True}`
- Code-switch hits: `{'Dancin': True, 'Dancing': True, 'Beer': False, 'Bear': True, 'Ayılar Dans': True}`

### out_v7 - v7_vad_merged_no_prompt

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': False}`
- Code-switch hits: `{'Dancin': True, 'Dancing': True, 'Beer': False, 'Bear': True, 'Ayılar Dans': True}`

### out_v8 - v8_full_audio_no_prompt

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': False}`
- Code-switch hits: `{'Dancin': True, 'Dancing': True, 'Beer': False, 'Bear': True, 'Ayılar Dans': True}`

### out_v9 - v9_whisperx_precomputed_vad

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': False}`
- Code-switch hits: `{'Dancin': True, 'Dancing': True, 'Beer': False, 'Bear': True, 'Ayılar Dans': True}`

### out_v10 - v10_selimc_turkish_turbo_ct2_vad_merged

- Bad token hits: `{'É': False, "I don't know": False, 'Are the days': False, 'Konuklar Türkçe sohbet ediyor': False}`
- Code-switch hits: `{'Dancin': True, 'Dancing': True, 'Beer': True, 'Bear': False, 'Ayılar Dans': True}`
