# ASR archive full benchmark

- Decision hint: `awaiting_reference_transcripts`
- Benchmark id: `asr_archive_full_v0_1`
- Profiles: `fast, quality`

| Sample | Ref | Fast model | Fast WER | Quality model | Quality WER | Speedup | Fast safety | Quality safety |
|---|---|---|---:|---|---:|---:|---|---|
| baris_manco_7den_77ye_full | yes | large-v3-turbo | 0.702 | large-v3 | 0.7011 | 2.492 | True | True |
| neretva_ustune_dusen_hilal_full | no | large-v3-turbo | - | large-v3 | - | 2.211 | True | True |
| merakli_momolar_full | no | large-v3-turbo | - | large-v3 | - | 2.246 | True | True |

## Next Manual Step

If `Ref` is `no`, copy the manually corrected reference text into the configured `reference_path` files.
Then rerun this script with `--score` or `--all`.
