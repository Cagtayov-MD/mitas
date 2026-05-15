# ASR gold probe benchmark

- Decision hint: `awaiting_reference_transcripts`
- Benchmark id: `asr_gold_probe_v0_1`
- Profiles: `fast, quality`

| Sample | Ref | Fast model | Fast WER | Quality model | Quality WER | Speedup | Fast safety | Quality safety |
|---|---|---|---:|---|---:|---:|---|---|
| gold_h1_news_0000_0100 | needs_cleanup | large-v3-turbo | - | large-v3 | - | 1.766 | True | True |
| gold_neretva_bridge_0340_0440 | needs_cleanup | large-v3-turbo | - | large-v3 | - | 2.541 | True | True |
| gold_merakli_momolar_0000_0100 | needs_cleanup | large-v3-turbo | - | large-v3 | - | 1.814 | True | True |
| gold_baris_manco_children_0140_0340 | needs_cleanup | large-v3-turbo | - | large-v3 | - | 2.485 | True | True |
| gold_kuran_0000_0100 | needs_cleanup | large-v3-turbo | - | large-v3 | - | 1.778 | True | True |
| gold_mehmed_0000_0100 | needs_cleanup | large-v3-turbo | - | large-v3 | - | 3.033 | True | True |

## Next Manual Step

Run `--review` to generate candidate ASR text and suspect points.
Listen only for wrong words/phrases, apply those corrections to the configured `reference_path` files, then rerun with `--score`.

## Reference Hygiene

- `gold_h1_news_0000_0100`: placeholder_or_draft_text (`E:\MITAS\references\asr_gold_probe\gold_h1_news_0000_0100.txt`)
- `gold_neretva_bridge_0340_0440`: timestamp_markers_present (`E:\MITAS\references\asr_gold_probe\gold_neretva_bridge_0340_0440.txt`)
- `gold_merakli_momolar_0000_0100`: timestamp_markers_present (`E:\MITAS\references\asr_gold_probe\gold_merakli_momolar_0000_0100.txt`)
- `gold_baris_manco_children_0140_0340`: timestamp_markers_present (`E:\MITAS\references\asr_gold_probe\gold_baris_manco_children_0140_0340.txt`)
- `gold_kuran_0000_0100`: placeholder_or_draft_text (`E:\MITAS\references\asr_gold_probe\gold_kuran_0000_0100.txt`)
- `gold_mehmed_0000_0100`: placeholder_or_draft_text (`E:\MITAS\references\asr_gold_probe\gold_mehmed_0000_0100.txt`)
