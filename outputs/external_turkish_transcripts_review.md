# External Turkish Transcript Sources Review

Date: 2026-05-13

## Summary

This first pass focused on two Turkish transcript sources:

- MediaSpeech Turkish / OpenSLR108: downloaded and inspected locally.
- Mozilla Common Voice Turkish 25.0: user-provided archive copied from Downloads, extracted, and inspected locally.

The strongest immediate source is still MediaSpeech Turkish because it is media-derived speech with paired WAV and TXT files. It is much closer to the MITAS / TRT ASR problem than clean read-speech corpora.

## MediaSpeech Turkish / OpenSLR108

Source: https://huggingface.co/datasets/emre/Open_SLR108_Turkish_10_hours

Local paths:

- Archive: `E:\MITAS\cache\external_datasets\mediaspeech_tr\TR.zip`
- Extracted data: `E:\MITAS\cache\external_datasets\mediaspeech_tr\TR`

Download and integrity notes:

- Archive size: 917,632,692 bytes.
- Extracted successfully with Windows `tar`.
- File pairing is clean: 2,513 `.txt` files and 2,513 `.wav` files.
- No missing WAVs found for transcript files.
- No empty transcript files found.

Measured content:

| Metric | Value |
|---|---:|
| Segment count | 2,513 |
| Total audio | 10.003 hours |
| Avg segment duration | 14.329 s |
| Min / max segment duration | 3.4 s / 14.9 s |
| Avg words per transcript | 29.49 |
| Min / max words | 4 / 47 |
| Avg chars per transcript | 212.95 |
| Turkish character rows | 2,513 / 2,513 |
| Audio format observed in samples | 16 kHz mono WAV |

Qualitative notes:

- Text is lowercase and generally punctuation-light.
- It contains real media/news/political/public-affairs language.
- Named-entity and domain-like examples appear frequently: `ak parti`, `yargıtay`, `enis berberoğlu`, `cumhurbaşkanı`, `karaismailoğlu`, `putin`, `trump`, `ayasofya`, `mimar sinan`.
- This is useful for ASR fast/quality comparison because it has aligned audio and human transcript.
- It is less useful for final TRT archive scoring than tomorrow's internal TRT transcript source, but excellent for not staying idle today.

Good smoke candidates:

| ID | Duration | Why useful |
|---|---:|---|
| `0044ad54-892f-4d23-a75b-0e22eb837914` | 14.5 s | Ottoman/Turkish cultural names: Kanuni, Süleymaniye, Selimiye, Edirne, Mimar Sinan, Ayasofya |
| `004ebcc0-8263-4983-8c1f-ae1f4bcf79cd` | 14.8 s | Political/government vocabulary: local government law, AK Parti, municipality |
| `00963752-3348-4f84-9161-650d2743d007` | 14.5 s | Legal/political named entities: Yargıtay, Enis Berberoğlu |
| `00a38ecc-2a37-4c3f-803b-607031004e4f` | 14.3 s | News/economy: minimum wage, president |
| `0129959b-26b8-4b45-b9a0-c4d05596cb58` | 14.4 s | Conversational political speech and name mention: Ekrem |

Recommendation:

Use MediaSpeech Turkish immediately as a temporary ASR probe set. Start with 5-20 short segments, run `fast`, `quality`, and later selective-hybrid candidates, then compute lightweight WER/CER against the `.txt` references.

## Mozilla Common Voice Turkish 25.0

Source: https://mozilladatacollective.com/datasets/cmn2e7kbl01k2mm07gm5n1bc9

Local paths:

- User download: `C:\Users\TRT03\Downloads\1774205200568-cv-corpus-25.0-2026-03-09-tr.tar.gz`
- Cached archive: `E:\MITAS\cache\external_datasets\common_voice_tr_25\cv-corpus-25.0-2026-03-09-tr.tar.gz`
- Extracted data: `E:\MITAS\cache\external_datasets\common_voice_tr_25\cv-corpus-25.0-2026-03-09\tr`

Public metadata and local inspection:

- License: CC0-1.0.
- Format: MP3.
- Archive size copied locally: 2,982,022,981 bytes.
- 126,510 clips.
- 135.298 recorded hours from `clip_durations.tsv`.
- 1,816 speakers.
- Average clip duration: 3.85 s.
- Text field in TSV files is the supposed transcription.
- Source text is largely Wikipedia / sentence-collector / SETimes / community-generated sentences.

Extracted files:

| File | Rows |
|---|---:|
| `clip_durations.tsv` | 126,510 |
| `validated.tsv` | 120,832 physical data lines |
| `train.tsv` | 40,815 |
| `dev.tsv` | 11,797 |
| `test.tsv` | 11,819 |
| `invalidated.tsv` | 5,018 |
| `other.tsv` | 660 |
| `reported.tsv` | 486 |
| `validated_sentences.tsv` | 410,410 |
| `unvalidated_sentences.tsv` | 3,490 |
| MP3 files under `clips/` | 126,510 |

Clean-row parsing notes:

- `validated.tsv` contains a small number of malformed/multiline TSV rows under Python `csv.DictReader`.
- Physical data lines: 120,832.
- Parsed `DictReader` rows: 119,620.
- Clean validated rows after filtering newline/tab-contaminated sentences and extreme word counts: 119,604.
- Clean validated average words: 4.91.
- Clean validated word range: 1-20.
- Clean validated average characters: 34.51.
- Clean rows containing Turkish-specific characters: 100,096.

Example clean sentences:

- "Dünyanın üçüncü büyük el yazması kütüphanesi de Kum şehrinde bulunmaktadır."
- "Tuğgeneral rütbesine yükseldi."
- "Siyasette temiz insanlara ihtiyacımız var."
- "İletişim protokolü analizinde ve bilgisayar güvenliği denetiminde kullanılabilir."
- "Referandum tarihi henüz belirlenmedi."

Recommendation:

Use Common Voice mostly for broad Turkish robustness and short utterance sanity checks. Do not use it as the primary TRT-domain ASR model decision source. Also respect Mozilla's restriction: do not attempt to determine speaker identity and do not re-host/re-share the dataset.

## Comparison

| Source | Current status | Best use | ASR gold value | Faz2 value |
|---|---|---|---|---|
| MediaSpeech Turkish | Downloaded, extracted, inspected | Temporary media-domain ASR probe | High for today | Medium |
| Common Voice Turkish 25.0 | Downloaded, extracted, inspected | General Turkish read-speech robustness | Medium-low for TRT domain | Low-medium |
| Tomorrow's TRT transcripts | Pending | Real domain gold set | Highest | Highest |

## First ASR Smoke On MediaSpeech

Output:

- JSON: `E:\MITAS\outputs\external_turkish_transcripts_asr_smoke\smoke_results.json`
- Markdown: `E:\MITAS\outputs\external_turkish_transcripts_asr_smoke\smoke_results.md`

Run shape:

- 5 MediaSpeech WAV/TXT pairs.
- Profiles: `fast` (`large-v3-turbo`) and `quality` (`large-v3`).
- Reference text: MediaSpeech `.txt`.
- Metric: lightweight word-level WER over normalized lowercase tokens.

Summary:

| Profile | Avg WER | Total decode seconds |
|---|---:|---:|
| `fast` | 0.1144 | 30.783 |
| `quality` | 0.1340 | 42.505 |

Per-sample WER:

| Sample | Fast WER | Quality WER |
|---|---:|---:|
| `0044ad54-892f-4d23-a75b-0e22eb837914` | 0.1379 | 0.2414 |
| `004ebcc0-8263-4983-8c1f-ae1f4bcf79cd` | 0.0000 | 0.0000 |
| `00963752-3348-4f84-9161-650d2743d007` | 0.1429 | 0.1071 |
| `00a38ecc-2a37-4c3f-803b-607031004e4f` | 0.2308 | 0.2308 |
| `0129959b-26b8-4b45-b9a0-c4d05596cb58` | 0.0606 | 0.0909 |

Interpretation:

This is too small for a model decision, but useful as a sanity check. On these five short MediaSpeech clips, `large-v3-turbo` was faster and slightly better by average WER. The result supports continuing the `fast-first selective quality` hypothesis, not declaring it final.

## Expanded ASR Benchmark On MediaSpeech

Output:

- Script: `E:\MITAS\scripts\asr_mediaspeech_benchmark.py`
- JSON: `E:\MITAS\outputs\external_turkish_transcripts_asr_smoke_20\benchmark_results.json`
- Markdown: `E:\MITAS\outputs\external_turkish_transcripts_asr_smoke_20\benchmark_results.md`
- Candidates: `E:\MITAS\outputs\external_turkish_transcripts_asr_smoke_20\candidates.json`

Run shape:

- 20 deterministic MediaSpeech WAV/TXT pairs.
- Profiles: `fast` (`large-v3-turbo`) and `quality` (`large-v3`).
- Reference text: MediaSpeech `.txt`.
- Metrics: lightweight WER and CER over normalized Turkish text.

Summary:

| Profile | Avg WER | Avg CER | Total decode seconds | Avg decode seconds |
|---|---:|---:|---:|---:|
| `fast` | 0.1853 | 0.0966 | 14.098 | 0.705 |
| `quality` | 0.1775 | 0.0961 | 48.773 | 2.439 |

Pairwise result:

- `quality` lower WER: 8 / 20.
- `fast` lower WER: 6 / 20.
- tie: 6 / 20.

Interpretation:

The 20-segment benchmark slightly favors `quality` on WER/CER, but the difference is small while decode time is much higher. This supports using `large-v3-turbo` as the default ASR pass and reserving `large-v3` for fallback, audit, or high-risk segments. The result is still not final for the archive because MediaSpeech is external media data; internal TRT transcripts should be the real decision set.

## Next Actions

1. Keep MediaSpeech as today's temporary model-decision probe set.
2. Use Common Voice only as auxiliary Turkish short-utterance sanity data.
3. Once internal TRT transcripts arrive, rerun the same benchmark shape on TRT-domain clips.
4. If TRT results look like MediaSpeech, choose `large-v3-turbo` as default and use `large-v3` for selective fallback / upper review.
