# ASR Child Exit Tur 3 Summary

**Önerilen karar: Karar B**

TA1 stayed dirty, so tqdm is not sufficient; process-per-clip baseline was measured.

Strict process-per-clip did not guarantee clean exit for every clip; Karar B is still the safer architecture, but it needs valid-JSON containment or CUDA/driver escalation before being treated as fully clean.

| Test | Clean Exit | Transcripts Valid | Status | Notes |
|---|---:|---:|---|---|
| TA1 | false | true | needs_review | child JSON valid; abnormal exit after output |
| TA2 | true | false | skipped | skipped by early-exit: TA1 dirty, so tqdm monkey-patch is not sufficient |
| TA3 | true | false | skipped | skipped by early-exit: native log_progress path cannot rescue a dirty TA1 monkey-patch |
| TB1 | false | true | needs_review | child JSON valid; abnormal exit after output |
| TB2 | true | false | skipped | procdump not available; no minidump captured |
| TB3 | false | true | failed | each clip executed in a separate child process |
| TC1 | true | false | skipped | TC1 skipped because TB2 did not identify ctranslate2.dll; child JSON valid; clean exit |

## Karar B Performans Metrikleri

- total_wall_seconds: `40.145`
- avg_load_seconds: `5.211`
- avg_transcribe_seconds: `7.346`
- all_clean_exits: `False`
