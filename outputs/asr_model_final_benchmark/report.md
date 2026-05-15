# ASR Model Finalization Mini Benchmark

- Decision hint: `awaiting_reference_transcripts`
- Profiles: `fast, quality`

| Sample | Ref | Fast model | Fast WER | Quality model | Quality WER | Speedup | Fast safety | Quality safety |
|---|---|---|---:|---|---:|---:|---|---|
| trt_haber_1_full | no | large-v3-turbo | - | large-v3 | - | 2.001 | True | True |
| trt_haber_2_full | no | large-v3-turbo | - | large-v3 | - | 2.493 | True | True |
| trt_haber_3_full | no | large-v3-turbo | - | large-v3 | - | 2.201 | True | True |
| beyaz1_03_05 | no | large-v3-turbo | - | large-v3 | - | 1.375 | True | True |
| erd_test_full | no | large-v3-turbo | - | large-v3 | - | 2.64 | True | True |

## Next Manual Step

If `Ref` is `no`, correct the files under `draft_references` and copy the cleaned text into `references/asr_model_final/`.
Then rerun this script with `--score` or `--all`.
