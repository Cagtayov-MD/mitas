# ASR Child Exit Test Paketi Summary

Status: `needs_review`

| Test | Clean Exit | Transcript Valid | Note |
|---|---:|---:|---|
| T1 | true | true | child stdout JSON parsed; clean exit |
| T2 | true | true | child stdout JSON parsed; clean exit |
| T3 | false | true | child stdout JSON parsed; abnormal exit after parseable child output |
| T4 | false | true | child stdout JSON parsed; abnormal exit after parseable child output |
| T5 | true | true | reference clean single-transcribe compared with first clip from dirty multi-clip baseline; dirty_baseline=T3 |
| T6a | true | true | child stdout JSON parsed; clean exit |
| T6b | true | true | child stdout JSON parsed; clean exit |
| T6c | true | true | child stdout JSON parsed; clean exit |
| T6d | true | false | skipped: api_candidates_not_called_in_diagnostic |
| T7 | false | true | child stdout JSON parsed; abnormal exit after parseable child output |
| T8 | true | false | skipped: requires isolated temporary venv package installs; not run in no-package-change pass |

## T4 Karari

{
  "result": "dirty",
  "containment": "process-per-clip is the safer containment",
  "interpretation": "problem is not only same-instance state; process-level CUDA lifecycle remains suspect"
}

## T5 Diff Ozeti

{
  "segments_count_match": true,
  "reference_segments_count": 3,
  "suspect_segments_count": 3,
  "segments_match": true,
  "text_mismatches": [],
  "numeric_mismatches": [],
  "tolerance": 0.0001
}

## Likely Cause

Fresh instances in one process still exit dirty; process-per-clip containment is favored.
