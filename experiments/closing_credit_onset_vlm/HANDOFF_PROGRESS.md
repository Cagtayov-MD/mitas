# Closing-credit onset VLM experiment — live handoff

Last updated: 2026-07-14 14:19:34 +03:00 (Europe/Istanbul)

This file is the durable continuation record. If another agent continues the
work, start here, then read `README.md`, `window_detector.py`, and
`ollama_client.py`. Do not infer production readiness from a single FOUND run.

## Current live checkpoint — 14:19 (supersedes status/counts below)

The objective is still active. All 51 sources under `D:\filmtest\aaaa` have
passed inventory, ffprobe, and decode-health checks. The detector has current
artifacts for 9 unique films: **1 FOUND and 8 REVIEW**. These are diagnostic
runs, not the final 51-film benchmark. Every artifact still hard-codes
`publishable=false` and `pool_may_be_replaced=false`; no production pool or
master PNG has been replaced.

### Verified result

ATTILA is now solved again by the latest code in **attempt 006**:

- exact onset: pos 539 / `c_0540.png`;
- previous pos 538 is black PRE;
- absolute time: `01:35:51.674`;
- detector: 32.471 seconds, 11 VLM calls;
- exact A/B both return pos 539 and both local support checks pass.

Artifact:
`E:\MITAS\outputs\closing_credit_onset_vlm\batches\filmtest_aaaa_20260714_v1\films\030_evoArcadmin_S_NEMA_F_LM4_2013_1015_1_0000_70_1_ATT_LA__794cdd13e9\attempt_006\result.json`.

### Dense human ground truth now fixed for all eight core pilots

- KULUBE: pos 887 / `c_0888.png`, `01:28:32.493`.
- DRAKULA: pos 859 / `c_0860.png`, `01:21:19.716`.
- BABAM: pos 415 / `c_0416.png`, `01:33:05.786`.
- CENNETIN RENGI: pos 726 / `c_0727.png`, `01:24:01.013`.
- DON KISOT: pos 379 / `c_0380.png`, `01:56:11.067`.
- MARIE CURRIE: pos 585 / `c_0586.png`, `01:29:15.184`.
- DIRILIS ERTUGRUL: pos 804 / `c_0805.png`, `02:14:15.120`.
- ATTILA: pos 539 / `c_0540.png`, `01:35:51.674`.

The current latest batch summary is at
`E:\MITAS\outputs\closing_credit_onset_vlm\batches\filmtest_aaaa_20260714_v1\summary.json`.
The eight non-ATTILA detector results remain REVIEW. This is intentionally
fail-closed: there is no known unsafe FOUND in this checkpoint.

### What is fixed in code

- rejected coarse hints are retained and adversarially rechecked on rescue;
- late candidates can trigger a chronology probe and recover an earlier onset;
- fine panels can expand left when the first visible credit is at the edge;
- sparse localization cannot let exact verification escape the proven gap;
- rescue evidence survives mid-rescue errors in artifacts and metrics;
- terminal-card exact validation remains EOF-aware and bounded;
- deadline expiry while writing `window_evidence.json` revokes FOUND.

ATTILA demonstrates these changes can reject earlier footage/diegetic-looking
hints and recover a faint French credit without assuming credits continue to
EOF.

### Open blockers before trusting FOUND or running the final 51

An independent read-only adversarial audit found no P0 and confirmed **189
tests passing**, but identified three P1 correctness gaps:

1. An earlier rejected transition can still bypass rescue when coarse decoding
   chooses the normal REFINE route. All earlier positive/rejected evidence must
   force chronology/rescue before a later FOUND.
2. Chronology handling is incomplete: earlier AMBIGUOUS/ACTIVE_FROM_LEFT
   evidence can be omitted, while two independent clean PRE_ONLY/non-credit
   results currently fail to clear a false early candidate. Required behavior
   is negative+negative = continue, positive+positive = recover earlier,
   disagreement = REVIEW.
3. A/B exact results one frame apart are currently accepted by tolerance and
   the earlier frame is selected even though the other view calls it PRE. Add a
   third high-resolution micro-boundary adjudication or require equality.

Secondary items: widen the true-terminal routing horizon to cover a long final
card plus blank tail; close the small post-publication deadline accounting gap;
remove or correctly use cross-window support hints.

Immediate continuation order:

1. Implement the three-way semantic-negative chronology clearance for BABAM
   and CENNETIN RENGI.
2. Route all earlier rejected/ambiguous positive evidence through rescue.
3. Add micro-boundary adjudication for KULUBE pos 887/888 and DRAKULA pos
   859/860; never choose the earlier frame from a contradiction by tolerance.
4. Run all four closing-credit test suites, compile, and diff checks.
5. Rerun the eight labelled pilots against exact ground truth, then audit
   FRANNY, MUMYA, KARDESIM ICIN DER'A, POROROCA, and the incidental BEN VE BABAM
   VATAN case.
6. Only after those gates pass, run and report the complete 51-film corpus.

Current observed detector latency is about 21–46 seconds per pilot plus roughly
2–4 seconds extraction, inside the 1–2 minute target. Accuracy, not speed, is
the remaining blocker.

## Earlier 13:42 checkpoint (historical detail; superseded above)

Input is `D:\filmtest\aaaa`: 51/51 videos were inventoried, ffprobed, and
decode-checked. The corpus is 42.88 GiB: 47 MP4 plus 4 MXF-named MOV/MP4
containers, all H.264/25 fps and longer than the 600-second tail contract.

The isolated batch runner is
`E:\MITAS\experiments\closing_credit_onset_vlm\batch_video_runner.py`.
Scratch frames are under
`D:\filmtest\closing_credit_onset_vlm_scratch\filmtest_aaaa_20260714_v1` and
results are under
`E:\MITAS\outputs\closing_credit_onset_vlm\batches\filmtest_aaaa_20260714_v1`.
It extracts exactly 900 lossless PNGs from the final 600 seconds at 1.5 fps,
fingerprints the source, validates the full sequence, publishes atomically,
and never overwrites an earlier attempt. All results remain
`publishable=false` and `pool_may_be_replaced=false`.

Eight films currently have detector results: **1 FOUND, 7 REVIEW, 0 unsafe
FOUND**. This is a safe but recall-poor checkpoint, not production readiness.
The seven-film pilot took 223.5 seconds serially. Detector times were 21.366 to
41.684 seconds, about 29.5 seconds mean, inside the per-film 1-2 minute target.

### ATTILA is solved

ATTILA attempt 002 is visually and mechanically correct:

- pos 538 / `c_0539.png`: pure black PRE;
- pos 539 / `c_0540.png`: first red `Avec` credit;
- absolute video time: `01:35:51.674`;
- 11 VLM calls, 27.264 detector seconds;
- primary and adversarial compact views both resolve exact pos 539;
- an earlier pos-360 footage false positive was rejected chronologically.

ATTILA also proves credits need not continue to EOF: its real credits end near
pos 858 and a post-credit beach scene follows. The red dedication and subtitles
in that beach scene are not a new credit onset.

Authoritative experimental artifact:
`E:\MITAS\outputs\closing_credit_onset_vlm\batches\filmtest_aaaa_20260714_v1\films\030_evoArcadmin_S_NEMA_F_LM4_2013_1015_1_0000_70_1_ATT_LA__794cdd13e9\attempt_002\result.json`.

### Pilot visual ground truth and failures

- KULUBE: true pos 887 / `c_0888.png`, absolute `01:28:32.493`.
  It is a valid THE END-only terminal case followed by an RKO logo. Current
  code leaves terminal-card rescue unresolved, so this is a false-negative
  REVIEW.
- DRAKULA: true pos 859 / `c_0860.png`, absolute `01:21:19.716`.
  Low-contrast red credits fade in over a burning tower. Two exact views chose
  859 and 860; zero-tolerance agreement caused REVIEW.
- BABAM: true pos 415 / `c_0416.png`, absolute `01:33:05.786`.
  Static black credit/name cards contain intentional black gaps. A contradictory
  pos-180 terminal hallucination (`reject=NO_VISIBLE_ATTRIBUTION`) preempted the
  real supported credit evidence near pos 428.
- CENNETIN RENGI: true pos 726 / `c_0727.png`, absolute `01:24:01.013`.
  Persian/RTL two-column scrolling credits were ignored; the model latched onto
  a late company logo around pos 882/885. This needs a chronology plus
  non-Latin guard, not merely a looser fine gate.
- DON KISOT: onset is inside pos 360..383; pos 383 visibly contains the first
  observed `In Memory of` credit card. Exact dense ground truth is pending.
  A false terminal seam at pos 360 currently blocks the later supported regime.
- MARIE CURRIE: onset is inside pos 563..585; pos 585 is the first observed
  blue credit over moving fabric. Earlier frames are epilogue story text.
  Exact dense ground truth is pending.
- DIRILIS ERTUGRUL: onset is inside pos 787..810; pos 810 is the first observed
  producer credit over footage and pos 832 has full scrolling credits. Fine
  detected around pos 833, but the search window began too late and the local
  support gate was too short. Exact dense ground truth is pending.

### Current code status and required fixes before the full 51

The ATTILA chronological rescue is implemented in `window_detector.py`, with
adversarial prompt routing in `ollama_client.py`. Current source compiles.
Targeted suites at 13:40 +03:00 are green: window protocol 65/65 and batch
runner 6/6 (71 total). These tests do not yet cover all newly discovered pilot
failures.

An independent adversarial review found no P0, but two P1 items must be fixed:

1. An earlier candidate may currently be skipped after one primary PRE_ONLY
   call. Require a second shifted adversarial negative before later FOUND.
2. If rescue fails mid-call, already successful rescue evidence must remain in
   manifest/metrics, not only `calls.jsonl`.

The live WIP has only begun candidate support/wide-left metadata; it compiles
and old tests pass, but the behavior changes below are not complete yet:

1. Send terminal-card seams through fine/exact instead of immediately refusing
   them; contradictory rejected proposals must not preempt later evidence.
2. Add the double-negative chronology gate and persistent rescue trace.
3. Expand fine search left when the first positive is at the left edge.
4. Allow later coarse support to complete a locally short but confirmed credit
   transition without requiring credits to last to EOF.
5. Handle one-frame faint fade disagreement without converting an uncertain
   boundary into an unsafe exact FOUND.
6. Add a script/layout-aware Persian/non-Latin chronology guard.
7. Raise the four-candidate cap to cover all five coarse panels and make the
   boundary-family metric naming honest.
8. Rerun ATTILA and all seven pilots, then add FRANNY, MUMYA, KARDEŞİM İÇİN
   DER'A, and POROROCA before authorizing the full 51-film run.

Do not run the remaining 43 as a final benchmark until these gates are fixed;
otherwise the batch would mostly measure already-understood false-negative
mechanisms. Preserve every old attempt for comparison.

## Scope and hard safety contract

- Implementation: `E:\MITAS\experiments\closing_credit_onset_vlm`.
- Tests: the three `tests\test_closing_credit_onset_*.py` files.
- Run artifacts: only `E:\MITAS\outputs\closing_credit_onset_vlm`.
- Never write/replace `frames\cikis_jenerik`, master PNGs, production
  manifests, `scripts\mitas_pipeline.py`, or `scripts\_jenerik_pool.py`.
- Every result/manifest is non-authoritative:
  `publishable=false`, `pool_may_be_replaced=false`.
- No staging or commit has been requested or performed.

## Current architecture and decisions

The rejected first prototype classified individual cells in small mosaics.
Real logs showed scenery, faces, and diegetic Arabic text becoming high-confidence
CREDIT. Its apparently correct `c_0319.png` result came from unsafe CV backtrack,
not reliable VLM semantics. It remains only as legacy/test code.

The CLI now uses `window-boundary-v1`:

1. CV scans every frame at low resolution only for high-recall proposal anchors.
   It cannot decide CREDIT or move the final semantic boundary.
2. Coarse VLM panels cover about 120 seconds with 9 regular anchors. The real
   final panel densely samples the last 15 seconds and is capped at 24 cells.
3. Each call returns one aggregate state: `PRE_ONLY`, `TRANSITION`,
   `ACTIVE_FROM_LEFT`, or `AMBIGUOUS`, plus first/support cells, boundary kind,
   continuity, and semantic reject.
4. Qwen repeatedly reports a new TRANSITION inside an already continuous credit
   regime. Therefore repeated positives without intervening PRE are one regime;
   the earliest supported candidate goes to fine/exact. PRE-separated positive
   regimes remain REVIEW. Supported coarse views must agree on boundary kind.
5. Hard DIEGETIC/STORY_TEXT/MIXED rejection conflicting with a supported credit
   at a shared panel seam is REVIEW. `NO_VISIBLE_ATTRIBUTION` on a preceding
   all-footage panel is not allowed to hide the later real transition.
6. Fine uses a 9-cell 512 px panel. For short EOF terminal cards it uses bounded
   dense onset and EOF-relative context, capped at 28 cells.
7. Exact A/B include every real frame in the sparse fine gap. A uses 3 columns;
   B uses 2 columns and an adversarial rejection prompt. They are same-model
   transport/context corroboration, not independent model probability.
8. Exact prompt/schema/parser/provenance carry `boundary_search_cells`. Cells
   after that range are SUPPORT ONLY and cannot be returned as `first`. This was
   required because real Qwen v3 selected the final sparse support cell instead
   of the onset.
9. If fine overlooks a faint credit in its sampled predecessor, exact search
   extends one real frame left: `exact_pre = fine_semantic_pre - 1`. Exact first
   must lie in `(exact_pre, fine_approximate]`; coarse sampled bracket is kept as
   a diagnostic but no longer falsely blocks sub-anchor refinement.
10. Verification tiles have a 640 px upper bound, but a 2.4 MP composed-mosaic
    budget steps them down by 32 px to at least 384. The real 14-cell A/B views
    use 512 px. This fixed an Ollama HTTP 400 at 4561 prompt tokens with
    `num_ctx=4096`.
11. FOUND for ordinary credits requires coarse and fine future support; both
    exact views must be TRANSITION/CONFIRMED/reject NONE, agree at tolerance 0,
    agree on kind, and have an adjacent real PRE frame. At least one exact view
    must also carry >=8 seconds of support. Requiring both same-model exact
    views to duplicate the distant support index was empirically brittle. If
    neither exact view has long support, result is REVIEW.
12. `TERMINAL_END_CARD` stays stricter: real EOF only, both exact views must see
    at least two card cells, and blank/black tail is bounded to <=15 seconds.
13. Every call is bound to requested stage, positions/files, call ID, EOF flag,
    boundary range, captured JPEG SHA-256, prompt protocol/variant/hash, and
    evidence index/position invariants. Source signature and post-call deadline
    are checked before FOUND.

## Current files

- `models.py`: aggregate window enums/evidence and result models.
- `ollama_client.py`: indexed mosaic encoding, strict schema/prompt/parser,
  boundary-range enforcement, capture/provenance records, Ollama transport.
- `window_detector.py`: coarse grammar, fine/exact builders, verification gates,
  safety allowlist, source drift/deadline checks, artifacts and manifests.
- `cli.py`: active test entrypoint using `WindowClosingCreditOnsetDetector`.
- `detector.py` and `temporal.py`: retained for legacy tests; not the active CLI
  decision path.
- `README.md`: operator/design guide; adaptive exact resolution, candidate vs
  support cells, support-chain gate, and the v6 timing are current.

## Real-film evidence

Film: `13. SAVAŞÇI 1999-0394-1-0000-90-1`, 720 frames at 1.5 fps.

Human/visual ground truth used for this smoke test:

- `c_0318.png` / pos 317: completely black PRE frame.
- `c_0319.png` / pos 318: first visible `UNIT PRODUCTION MANAGER` credit.

Run history (all old outputs retained; never overwrite them):

- Old per-cell v7: appeared to find 319 but semantic evidence was invalid; do
  not cite it as success.
- `window_v1_13_savasci_20260714_1205`: safe REVIEW at about 33 s. Qwen called
  panels 2/3/4 separate TRANSITIONs inside one continuous credit regime.
- `..._v2`: MODEL_ERROR after 31.764 detector seconds. Exact A, 13 cells at
  640 px, produced 4561 prompt tokens and exceeded `num_ctx=4096`.
- `..._v3`: safe REVIEW. Adaptive 512 px exact transport worked, but Qwen chose
  sparse support cells 346/344 as onset.
- `..._v4` and `..._v5`: safe REVIEW. Boundary-range enforcement made both
  exact views agree on the correct pos 318, but exact A reported only 3.33 s of
  support while exact B reported about 17 s.
- `E:\MITAS\outputs\closing_credit_onset_vlm\window_v1_13_savasci_20260714_v6`:
  **FOUND, correct pos 318 / frame 319 / `c_0319.png`, onset timestamp 212.0 s,
  `CREDIT_SEQUENCE`, confidence 1.0**. Detector time 18.761 s (shell 19.5 s),
  CV 10.684 s, 7 VLM calls = 4 coarse + 1 fine + 2 exact. Warm-model panel
  calls were about 1.0-1.5 s each. Exact first positions `[318,318]`, adjacent
  PRE true, same kind true, exact support flags `[false,true]`, support chain
  true. Output remains non-publishable and cannot replace a pool.

This is only one real-film smoke test, not a style/language benchmark. The
19-second figure is a warm-model measurement and is not a 1-2 minute guarantee
under GPU contention.

## Verification at this checkpoint

- Window suite: **62 passed** at 12:35 +03:00.
- Combined legacy/client + temporal + window suites: **164 passed in 16.89 s**
  at 12:38 +03:00. An independent adversarial agent also reported 164/164.
- Final independent audit on the stable detector/client/test hashes found no
  remaining P0/P1 blocker and independently verified all seven v6 call records
  against capture hashes, stages, frame lists, call IDs, boundary ranges, and
  evidence provenance (zero mismatches).
- `compileall`, CLI `--help`, scoped `git diff --check`, and a direct trailing
  whitespace scan passed. Current source signature equals the v6 recorded
  signature (`d7d9aff...c18c91f`), 720/720 files. Production tracked diff count
  for `scripts\mitas_pipeline.py` and `scripts\_jenerik_pool.py` is zero.
- Newly locked regressions include:
  - continuous repeated Qwen TRANSITION drift uses earliest supported regime;
  - hard diegetic seam conflict remains REVIEW;
  - coarse kind mismatch remains REVIEW;
  - terminal fine cap and exact 15-second blank-tail context;
  - adaptive exact mosaic pixel budget;
  - support-only cells forbidden as exact `first` by schema/parser;
  - real-like fine drift resolves 318 even when fine nominates 323;
  - boundary-search range is present in call and evidence provenance;
  - one exact long support plus coarse/fine chain passes ordinary credits;
  - zero exact long-support views remains REVIEW.

Current WIP hashes (recompute after any edit):

- `window_detector.py`:
  `B1C76987BB3AFA34FE27FF0DBE4F8D7770BC23833129C70A3457CE474C9E4992`
- `ollama_client.py`:
  `A41E9F916870ABDF2B54C9E58723D8477C9E25674822528512682AE7EF1ACDE3`
- `test_closing_credit_onset_window_protocol.py`:
  `48276385A09A5CD228DB9AA7A994D24F730EE1FD1CF4C5A446052505E62C2F5A`

## Immediate continuation steps

1. Do not integrate with production yet. Next meaningful validation is a
   labelled, style-stratified corpus: black scroll, footage overlay, static
   cards, two columns, RTL/Persian, Cyrillic, low contrast, diegetic text,
   subtitles/story cards, terminal END card, and credits-at-very-end.
2. Measure recall, exact-frame error, false-positive rate, REVIEW rate, and
   cold/warm latency. Tune only from captured panels/calls, never from an
   unlogged intuition.
3. If production integration is later approved, add an explicit promotion step
   outside this experiment; never silently change `pool_may_be_replaced` here.

## 2026-07-14 15:00 +03:00 checkpoint — 51-film test corpus

Scope and safety:

- Input corpus is `D:\filmtest\aaaa`: 51/51 videos passed ffprobe/decode
  preflight. Each film has an exact 900-frame, 1.5 fps, final-600-second tail
  under `D:\filmtest\closing_credit_onset_vlm_scratch\filmtest_aaaa_20260714_v1`.
- Detector outputs are under
  `E:\MITAS\outputs\closing_credit_onset_vlm\batches\filmtest_aaaa_20260714_v1`.
- Full 51-film detector run has deliberately NOT started yet. Current work is
  evidence-first labelled pilot hardening. Every result remains
  `publishable=false` and `pool_may_be_replaced=false`; production pipeline
  files remain out of scope.

Human-checked pilot boundaries (zero-based `start_pos`):

- ATTILA: 539; latest known correct pilot was FOUND 539 (`attempt_006` before
  the current WIP edits).
- KULUBE: 887; faint terminal THE END.
- DRAKULA: 859; faint red credit over textured footage.
- BABAM: 415; static name cards separated by black gaps.
- CENNETIN RENGI: 726; Persian/RTL credit after a nearly black predecessor.
- DON KISOT: 379.
- MARIE CURRIE: 585; preceding prose is epilogue, not credits.
- DIRILIS: 804.

Current code direction:

- Review rescue now preserves full unresolved chronology groups instead of
  sampling history, blocks earlier rejected/ambiguous evidence from being
  silently skipped, and uses bounded sequential A/B chronology checks.
- Sparse localisation uses a conservative union bracket and can run a second
  narrowing pass. Exact verification is followed by a full-resolution micro
  boundary adjudicator with distinct A/B transports and tolerance zero.
- Micro panels explicitly ask for the first coherent glyph/stroke and reject
  grain, fire, texture, and support-only cells. A raw full-resolution blank
  veto now excludes physically blank predecessor frames without requiring a
  brittle CV text-score threshold.
- Terminal END-card rescue is tied to real source EOF, bounded blank tail, and
  compatible semantic kinds. Cross-window support hints cannot authorise a
  candidate.

Latest real-film evidence:

- BABAM `attempt_006`: REVIEW. The detector reached the real card sequence but
  a fine pass drifted to an internal later card because of intervening black
  gaps. WIP now preserves the coarse bracket left edge so the next rerun can
  still search the true pos 415.
- CENNETIN RENGI `attempt_005`: FOUND 727, one frame late.
- CENNETIN RENGI `attempt_006`: FOUND 725, one frame early and therefore
  unsafe. Human/pixel check shows pos 725 is essentially black (max grey 1),
  while pos 726 contains the first Persian glyphs. This directly motivated the
  raw blank veto. Attempt 006 is experimental/non-publishable and must not be
  treated as a success. Rerun must return exactly 726 or fail closed.

Latest automated verification:

- Protocol suite at 15:00: **86 passed, 2 failed** in 16.96 s.
- Failure 1: an old test expects a one-frame exact A/B disagreement to stay
  REVIEW, while the new micro adjudicator currently resolves it to FOUND.
- Failure 2: an old assertion expects an exact result to be outside the former
  sparse intersection; the implementation now intentionally carries a union
  search bracket. Do not merely edit expectations: inspect call evidence and
  lock the desired safety invariant with new micro-boundary regressions.
- The previous checkpoint before the two newest WIP edits was 88/88 green.

Immediate next actions:

1. Resolve the two red tests from evidence; add explicit raw-blank/micro and
   chronology regressions.
2. Rerun BABAM and CENNETIN RENGI. Require BABAM pos 415 or REVIEW; require
   CENNETIN RENGI pos 726 or REVIEW. Never accept an early FOUND.
3. Integrate the same micro safety gate into the ordinary non-rescue REFINE
   route; it still contains the older tolerance/minimum shortcut.
4. Rerun KULUBE, DRAKULA, ATTILA and the remaining labelled pilots, then run
   the full four closing-credit test suites.
5. Only after those gates are green, expand to style pilots and finally all 51
   films, followed by a human/evidence audit and final metrics report.

## 2026-07-15 08:30 +03:00 checkpoint — live-state correction and current pilot status

This checkpoint supersedes the 2026-07-14 15:00 execution counts where they
conflict. It was rebuilt from the live scratch tree, `results.csv`, per-film
attempt directories, and the current source/test files.

Corpus and execution truth:

- `D:\filmtest\aaaa` contains 51 videos (47 MP4 and 4 MXF), and the batch
  runner discovers all 51.
- Only 10 distinct films currently have extracted tails in the scratch tree.
  Every one of those 10 has exactly 900 PNG frames, `c_0001.png` through
  `c_0900.png`. The earlier statement that all 51 already had extracted tails
  was incorrect.
- Therefore the full 51-film run has NOT happened. Current completion is 10/51
  distinct films (19.6%); 41 films remain untouched by the detector.
- The live aggregate is 4 `FOUND`, 6 `REVIEW`, 0 batch/decode failures. All
  remain `publishable=false` and `pool_may_be_replaced=false`.

Human-labelled pilot truth (zero-based `start_pos`):

- BABAM: `FOUND 415`, exactly equal to human GT 415 (`c_0416.png`).
- CENNETIN RENGI: `FOUND 726`, exactly equal to human GT 726
  (`c_0727.png`, Persian/RTL).
- ATTILA: `FOUND 539`, exactly equal to human GT 539 (`c_0540.png`).
- DRAKULA: safe `REVIEW`; human GT is 859. Latest failed because exact A/B
  proposed 860/859 and the old micro candidate range allowed footage frame
  858 to become an answer.
- KULUBE (the 1952 MXF, not KAZANANLAR KULUBU): safe `REVIEW`; human GT is
  887. Fine evidence sees the terminal card family around 887/888 but the old
  terminal-kind gate rejected `END_CARD_THEN_CREDITS` compatibility.
- DON KISOT: safe `REVIEW`; human GT 379.
- MARIE CURRIE: safe `REVIEW`; human GT 585. Earlier prose is epilogue and must
  not be promoted as credit.
- DIRILIS ERTUGRUL: safe `REVIEW`; human GT 804.
- On the eight labelled films this is 3 exact `FOUND`, 5 fail-closed `REVIEW`,
  and zero known wrong/early `FOUND` results.

Additional unlabelled pilots:

- KAZANANLAR KULUBU: `FOUND 517`; manual panel inspection shows a real rolling
  English credit sequence, but no exact human GT has yet been locked.
- BEN VE BABAM VATAN: `REVIEW`.

Latest pilot latency from the ten live aggregate rows:

- Minimum 30.937 s, median 54.847 s, mean 50.510 s, maximum 73.549 s.
- This is inside the requested 1–2 minute ceiling for the current pilots, but
  throughput/VRAM measurements still require the full corpus run.

Current WIP after the latest real-film failures:

- Terminal rescue now treats `TERMINAL_END_CARD` and
  `END_CARD_THEN_CREDITS` as a compatible terminal family only at real EOF and
  only with the bounded terminal blank-tail rules. This is intended to solve
  KULUBE without opening a generic end-card shortcut.
- Micro candidate construction no longer lets the unclaimed predecessor become
  an answer when exact A/B disagree. For a 859/860 disagreement, 858 remains
  context-only; unanimous exact claims still retain one predecessor candidate
  for boundary auditing. This is intended to solve DRAKULA without authorising
  footage frame 858.
- Ordinary non-rescue `REFINE` uses the same two-view micro adjudicator as the
  rescue route. Raw blank veto remains conservative enough to protect faint
  gray and chromatic glyphs.
- Boundary-panel JSON schema limits `first` to the actual candidate cells, so
  the VLM cannot return arbitrary left context.

Verification at this checkpoint:

- `py_compile` passed for `window_detector.py` and `ollama_client.py`.
- All four scoped suites passed together: **209 passed in 20.83 s**.
- The protocol suite alone passed: **101 passed in 22.13 s**.
- Current hashes:
  - `window_detector.py`:
    `9A928C426175B14795AAEB3C2171E1F6BF28B1D5288716AF4ECF2FD70C784032`
  - `ollama_client.py`:
    `AFED9E088E08F1330D3965A47D2E08C125C673E718468AC42345796A5678924E`
  - `test_closing_credit_onset_window_protocol.py`:
    `D4506AA487F0DA1FFCAEEE5DE49B85D8C938DA5F063B7608BDE8FAE530B52FAD`

Important verification boundary:

- The latest KULUBE terminal-family patch and DRAKULA micro-range patch are
  unit-suite green, but neither has yet been rerun against its real film.
  They are hypotheses backed by captured evidence, not claimed real-film
  successes.
- The DRAKULA candidate-range behavior still needs a dedicated small regression
  test that asserts 858 is context-only for exact claims 859/860.

Next actions, in order:

1. Add the explicit DRAKULA micro-range regression (disagreement and unanimous
   cases), then rerun the four suites.
2. Rerun real KULUBE and DRAKULA. Accept only exact GT or `REVIEW`; never an
   early `FOUND`.
3. Audit captured evidence for DON KISOT, MARIE CURRIE, and DIRILIS; implement
   only bounded fixes with matching regressions.
4. Rerun all eight labelled pilots on one stable source hash.
5. Expand through style-stratified pilots, then extract/run the remaining 41
   films and produce the final human/evidence audit and metrics report.

## 2026-07-15 13:06 +03:00 checkpoint — all eight labelled pilots exact

This checkpoint supersedes the unresolved DON KISOT and DIRILIS rows above.
The full 51-film corpus has still not run yet; the clean expansion is the next
milestone.

Implementation and regression status:

- The exact-rescue gate now distinguishes semantic localization from final
  proof. One source view may be `UNVERIFIABLE` only as a position witness, and
  at least one source view must remain `CONFIRMED`; FOUND then requires two
  fresh micro views, both `CONFIRMED`, with different image and prompt hashes.
- `CREDIT_SEQUENCE` and `END_CARD_THEN_CREDITS` are compatible only inside the
  sustained-credit family and only after that fresh two-view micro audit. A
  cross-family mismatch still fails closed before any micro promotion.
- A multi-frame fade miss can now use a raw persistent-edge proposal only
  inside the already bounded dense localization gap. The relaxed ratio gate is
  offset by a higher absolute edge-density floor; it never authorizes FOUND.
  The proposal becomes context for two fresh semantic micro views, and only the
  earliest proposed frame may be accepted.
- All four scoped suites passed together: **225 passed in 23.70 s**.
- Current source hashes:
  - `window_detector.py`:
    `F9367BD5714619F84CFC1E174CE6A4E823D72135839905B6DD97163C55EF8BB8`
  - `ollama_client.py`:
    `1ED77C936252BA818B58BE916E253BFF5222B900BDCDDCAD22881C0F67A32383`
  - `test_closing_credit_onset_window_protocol.py`:
    `ACB16FCFB5551F1BA1F3911239E8F0A5C29F68E3ADF835504A916526BA325A21`

New real-film evidence on that source hash:

- DON KISOT `attempt_005`: **FOUND 379 / c_0380.png**, exactly equal
  to human GT 379. Exact source positions were 379/379, but one source view was
  not strong enough for final support. Two new micro views independently
  returned 379/379 with `CONFIRMED` continuity; 15 VLM calls, detector wall
  59.812 s.
- DIRILIS ERTUGRUL `attempt_005`: **FOUND 804 / c_0805.png**, exactly
  equal to human GT 804. Dense exact views were late at 808/808. The bounded
  raw scan covered 803..806 and proposed 804 (ratio 1.9316, density 0.0073834).
  Candidate claims 804/805 kept frame 803 context-only; two fresh micro views
  returned 804/804 with different image and prompt hashes. 21 VLM calls,
  detector wall 80.566 s.
- Both results remain test-only: `publishable=false` and
  `pool_may_be_replaced=false`.

Labelled pilot truth is now 8/8 exact FOUND and zero known early/wrong FOUND:

- ATTILA 539
- KULUBE (1952 MXF) 887
- DRAKULA 859
- BABAM 415
- CENNETIN RENGI 726
- DON KISOT 379
- MARIE CURRIE 585
- DIRILIS ERTUGRUL 804

Immediate next actions:

1. Force-rerun all eight labelled films once on the source hash above and audit
   every result; this guards against stochastic/model-state regressions.
2. Start a clean 51-film batch ledger while reusing only validated extracted
   frames, then process the remaining 41 videos.
3. Audit every FOUND boundary panel plus all REVIEW/MODEL_ERROR cases; fix only
   bounded failures with matching regressions, then rerun affected films.
4. Produce corpus-level exact/review/error, latency, call-count, style and
   failure-mode reports. Never publish or replace a production pool from this
   experiment.

## 2026-07-15 13:27 +03:00 checkpoint — stable-hash gate passed 8/8

The two repeat-run instabilities were fixed before corpus expansion:

- KULUBE: a scene-to-dark fade at pos 886 produced a strong raw edge jump even
  though the first visible `The End` attribution is pos 887. The raw helper now
  records global luma change and vetoes large photometric cuts/fades. Real
  KULUBE then returned FOUND 887 again.
- CENNETIN RENGI: an early scene-text hint around pos 409 produced a short
  `NO_VISIBLE_ATTRIBUTION + UNVERIFIABLE` pseudo-transition in one transport.
  A rejected short regime may now be discarded only when two distinct shifted
  adversarial views both prove semantic non-credit. Real CENNETIN RENGI then
  continued chronologically and returned FOUND 726 again.

Verification after both fixes:

- All four scoped suites passed: **227 passed in 24.37 s**.
- Stable source hashes:
  - `window_detector.py`:
    `A0FB4B3455C86DB2FEA0D9E2E3A2B326A81D102D2F3F5BB28BE8C4AA78C45327`
  - `ollama_client.py`:
    `1ED77C936252BA818B58BE916E253BFF5222B900BDCDDCAD22881C0F67A32383`
  - `test_closing_credit_onset_window_protocol.py`:
    `5410AAEEACFE0F6860B6682A45FAD587885DFBCB6051401CB327FCD300538599`

One forced eight-film run was then completed without source changes. Every
labelled film was exact at tolerance zero:

- KULUBE 887 (34.520 s)
- DRAKULA 859 (73.391 s)
- BABAM 415 (58.782 s)
- CENNETIN RENGI 726 (71.881 s)
- DON KISOT 379 (53.772 s)
- ATTILA 539 (61.427 s)
- MARIE CURRIE 585 (64.652 s)
- DIRILIS ERTUGRUL 804 (82.271 s)

Stable-run latency: min 34.520 s, median 63.040 s, mean 62.587 s, max
82.271 s. All eight remain `publishable=false` and
`pool_may_be_replaced=false`.

Next active milestone: create clean batch ledger
`filmtest_aaaa_20260715_v2`, reuse only already validated extraction manifests,
and process all 51 videos on the stable hashes above. Audit and bounded fixes
continue before any final corpus claim.

## 2026-07-15 14:13 TRT checkpoint - 51-film discovery and new false-positive classes

`filmtest_aaaa_20260715_v2` is running as a discovery batch. It loaded the
previous stable module at process start, so results from this batch must not be
presented as the final ledger after source edits. At this checkpoint at least
42/51 films had completed (16 FOUND, the remainder REVIEW); the GPU runner remained the
only active runner. Production MITAS paths remain untouched and every result is
still non-publishable/non-replacing.

New human frame audits (zero-based positions):

- PINOKYO: pos 825 is footage, pos 826 (`c_0827`) contains the first partial
  credit entering from the bottom. The v2 REVIEW was safe but late/unresolved.
- FRANNY: pos 852 is the fading scene and pos 853 is the first credit card;
  v2 FOUND 853 is exact.
- KUKLA ADAM: pos 727 is an unchanged encoded-black frame; the first visible
  cast card is pos 728. v2 FOUND 727 is one frame early.
- JURASSIC PARK 2: v2 FOUND 190 is a serious semantic false positive: a CNN
  lower-third physically inside a television in the story world. The real
  closing credits begin at pos 283 (`DIRECTED BY / STEVEN SPIELBERG`).
- YABANDAN GELEN ADAM: pos 731 is only the full-screen film title `DUCK YOU
  SUCKER`; it is not THE END and therefore cannot be onset. The first visible
  role/name credit is in the later 737-738 area and still needs exact adjacent
  frame adjudication.
- OLUM ASANSORU: pos 877 is blank; `FIN` first appears at pos 878. v2 is one
  frame early.
- MAVZER pos 824, BARBARLARI BEKLERKEN pos 539, and KAZANANLAR KULUBU pos 517
  were visually confirmed exact. BEYAZ BIZON v2 FOUND 700 is one frame late;
  the first faint name text is visible at pos 699.

Bounded source changes made after the v2 process started:

1. Added a fail-closed PINOKYO chronology fallback. Two independent sparse
   views may only open a bracket when they agree on the same final-cell
   sustained-credit transition, share the same PRE predecessor, all earlier
   chronology groups are independently non-credit, and a supported fine
   transition contains the sparse claim. Sparse evidence never authorizes
   FOUND; ordinary two-view localization, dense exact, and micro gates remain
   mandatory. Positive plus mismatched-first/rejected-view regressions pass.
2. Added a decoded-pixel micro-backtrack gate. A micro view may move a unanimous
   exact boundary one frame left only when that candidate differs physically
   from its own predecessor. The check uses interior RGB maximum delta plus a
   resolution-normalized changed-pixel density, preserving real faint/chromatic
   strokes. Real ATTILA pos 539 passes (density 0.00088577); KUKLA pos 727 fails
   (codec-speck density 0.00023262). Six targeted blank/faint/PINOKYO tests pass.

Still open before the final clean batch: implement and real-test a specialized
semantic disproof gate for story-world televisions/monitors and non-THE-END
title cards; finish auditing all v2 FOUND/REVIEW cases; rerun the four full test
suites; rerun every affected real film; then launch a clean v3 batch on one
recorded final source hash.

## 2026-07-15 15:44 TRT checkpoint - discovery complete, semantic gates active

The discovery ledger `filmtest_aaaa_20260715_v2` completed all 51 videos on
the older process-loaded module: **17 FOUND / 34 REVIEW**, approximately
3149.8 seconds wall time. It remains discovery evidence only and must not be
used as the final corpus result after the source edits below.

All 17 FOUND boundaries were visually audited. Confirmed exact examples include
KULUBE 887, FRANNY 853, DRAKULA 859, BABAM 415, CENNETIN RENGI 726, MAVZER 824,
DON KISOT 379, ATTILA 539, BARBARLARI BEKLERKEN 539, KAZANANLAR KULUBU 517,
MARIE CURRIE 585 and DIRILIS ERTUGRUL 804. Newly established human zero-based
targets are KUKLA ADAM 728, JURASSIC PARK 2 283, YABANDAN GELEN ADAM 737,
OLUM ASANSORU 878 and BEYAZ BIZON 699. PINOKYO 826 and YARI 759 are additional
hard REVIEW targets under active repair.

Implemented experimental protections since the prior checkpoint:

- mandatory two-view candidate-semantic audits with strict schema, image and
  prompt hashes, call-id independence and captured-input provenance;
- explicit semantic classes for attribution credit, THE END/FIN end cards,
  title/story text, diegetic story-world screens, other text and no text;
- a rejection-and-continue path, so a title card or television lower-third does
  not stop chronology before the later real credit candidate;
- active-left versus last-cell chronology conflict auditing;
- physical faint-text evidence requirements for asymmetric NO_TEXT/credit
  votes, preventing blank predecessor acceptance;
- decoded-pixel backtrack vetoes, exact/micro disagreement handling and
  adjacent one-frame micro adjudication;
- a candidate detail mosaic containing the full frame, lower-edge zoom and
  contrast-enhanced lower edge, improving partial and low-contrast evidence;
- the candidate-semantic reserve was reduced to a measured 14-second minimum
  while retaining the 10-second live floor per call, avoiding needless late
  MODEL_ERROR outcomes.

Real-film evidence already produced on affected reruns:

- JURASSIC PARK 2 is fixed exactly at 283. The false candidate 191 is rejected
  by two `DIEGETIC_SCREEN` votes; 283 receives two `ATTRIBUTION_CREDIT` votes.
  Evidence: `outputs/closing_credit_onset_vlm/batches/affected_semantic_20260715_v1/films/019_*/attempt_004/result.json`.
- KUKLA ADAM is fixed exactly at 728 in the affected-boundaries batch.
- OLUM ASANSORU is fixed exactly at 878 in
  `affected_fixes_20260715_v2`, source 024 attempt 003; blank 877 no longer
  authorizes an early result.
- YABANDAN standalone audits now reject title-only 731 and positively identify
  attribution at 737. A full detector rerun is still required.
- PINOKYO, YARI and BEYAZ BIZON remain fail-closed REVIEW in their latest full
  attempts; narrow evidence-backed fixes are in progress. No wrong FOUND has
  been accepted for these cases.

The four scoped suites last passed at **248 tests** before the newest small
localization regression was added; the next complete run is expected to contain
at least 249 tests. The final clean `v3` 51-film ledger has **not started**. It
will start only after the remaining four real cases, the stable eight-film set,
and all scoped suites pass on one recorded source hash. Every artifact remains
`publishable=false` and `pool_may_be_replaced=false`; production MITAS code and
production pools remain untouched.

## 2026-07-15 16:23 TRT checkpoint - three hard boundaries exact, YABANDAN narrowed

On the current experimental module, the first affected real rerun batch
`affected_finalrepairs_20260715_v1` produced three newly exact boundaries:

- YARI SERT: FOUND 759 / `c_0760.png`, 92.047 s;
- PINOKYO'NUN MACERALARI: FOUND 826 / `c_0827.png`, 104.455 s;
- BEYAZ BIZON: FOUND 699 / `c_0700.png`, 78.355 s.

All three remain non-publishable and non-replacing. YARI is closed by a strict
one-frame partial-entry rule: the primary micro view selects 759, the shifted
micro view selects 760, both exact views select 760, the contextual candidate
audit identifies END_CARD at 759, and decoded pixels prove a physical change.
PINOKYO is closed only because two micro views agree at 826, two exact views
agree one frame later, and an independent nearby same-run attribution audit at
832 proves the sustained credit family. BEYAZ BIZON is closed by the contextual
attribution vote plus a strong fixed-edge emergence at 699; the detail view no
longer mistakes the full-frame portrait montage for a story-world monitor.

YABANDAN GELEN ADAM is still REVIEW in attempts 001-005, but every attempt is
safe: the title-only 731 region is never accepted. The audit established the
exact failure chain and added regressions for each layer:

1. `TITLE_OR_STORY / OTHER_TEXT` now counts as two-view explicit non-credit
   consensus; taxonomic subclass equality is no longer required.
2. A remembered semantic-rejection floor prevents later coarse candidates from
   reopening 731 during localization.
3. The floor is PRE-only in both sparse localization and compact exact panels.
4. The same floor is now a hard micro-candidate veto.
5. A bounded sequential semantic-successor refinement scans at most four
   seconds after a proven title edge. It requires every intervening frame to be
   independently non-credit, then requires two fresh micro views and the normal
   candidate-semantic gate on the first later attribution frame. This targets
   the real title-to-credit handoff at 737 without permitting a title card to
   authorize FOUND.

The next immediate action is real YABANDAN attempt 006 on this successor logic,
then targeted/full tests and an affected-film rerun. The stable eight-film set
and clean final 51-film v3 ledger have not yet been rerun on these newest hashes.

## 2026-07-15 17:25 TRT checkpoint - semantic repairs validated, two +1 edges open

The experimental source now contains four additional fail-closed repairs:

- a raw, headerless full-frame screen-disproof transport used only when the
  ordinary semantic A/B calls suspect a physical story-world screen;
- a localization-only terminal fine relaxation, while exact, micro and
  candidate-semantic proof remain mandatory;
- semantic disproof of sustained epilogue/story text before moving to a later
  coarse candidate;
- one-earlier-anchor localization for widely disagreeing sparse chronology
  views, without allowing sparse evidence itself to authorize FOUND.

All four scoped suites passed on this source: **259 passed in 30.08 s**.
Recorded hashes before the real-film run were:

- `window_detector.py`:
  `80158556BD5CFD72198C042997C13ADB087B9D70B45E24776A96B5607C643664`
- `ollama_client.py`:
  `192E42B9933B09074C260DDF08BE5AB4BF40E8CD90873B0B5A0F4184DD1B53F8`
- `test_closing_credit_onset_window_protocol.py`:
  `6B446860BCD9ADF4E0D5C8880A88B06879C31244330C15D3B5E9A0F517EBC0E5`
- `test_closing_credit_onset_detector.py`:
  `FD3958240B2C6F249D81F1AA38DA4AD4DDAD5A2FFDDCD576C1DB5F4601A7BF93`

The frozen-source real run is
`outputs/closing_credit_onset_vlm/batches/stable8_finalfix_20260715_v2`.
The selection regex also matched `BEN VE BABAM VATAN`, so nine films ran:

- KULUBE FOUND 887 exact, 63.064 s;
- DRAKULA FOUND 860, one frame late versus target 859, 88.599 s;
- BABAM FOUND 415 exact, 61.699 s;
- CENNETIN RENGI FOUND 726 exact, 71.689 s;
- DON KISOT FOUND 379 exact, 55.625 s;
- ATTILA FOUND 540, one frame late versus target 539, 95.426 s;
- BEN VE BABAM VATAN remained fail-closed REVIEW, 52.845 s;
- MARIE CURRIE FOUND 585 exact, 73.277 s;
- DIRILIS ERTUGRUL FOUND 804 exact, 105.572 s.

The key new real validations succeeded: KULUBE terminal localization recovered
887; CENNETIN RENGI recovered the dark Persian card at 726; the DON KISOT
memorial card recovered 379; MARIE rejected the sustained French epilogue text
near 539 then moved to the real 585 candidate; and DIRILIS widened localization
from 810 back to the source anchor 787 before exact proof recovered 804.

The clean final 51-film v3 ledger is still intentionally blocked. Immediate
work is to compare DRAKULA and ATTILA's exact/micro evidence, add a bounded
regression-backed first-faint-frame repair, rerun the two films plus the
JURASSIC story-TV control, rerun all scoped tests and affected/stable gates,
then start v3 on one newly recorded final source hash. Production remains
untouched and every result remains `publishable=false` and
`pool_may_be_replaced=false`.

## 2026-07-15 17:38 TRT checkpoint - faint first-frame gate passed 3/3

The two one-frame-late results were traced to different candidate-detail
failures, not repaired by unconditional backtracking:

- DRAKULA pos 859 contains real but extremely faint red cast names over moving
  fire. The detail view confused the telecine/scan artifacts with a physical
  screen while the contextual view saw attribution.
- ATTILA pos 539 contains only the tiny red closing-credit section heading
  `Avec` at the bottom; the previous semantic contract did not explicitly
  recognize a credit-section heading before its names entered.

Variant A now transports five views of the same candidate: full frame,
enhanced full frame, center zoom, lower zoom and contrast-enhanced bottom edge.
The semantic contract recognizes an isolated closing-credit section heading on
its first visible frame. Variant S now requires actual in-scene bezel/plane or
perspective evidence; scan lines, black borders, tape noise and telecine marks
cannot prove a story-world screen. This remains a semantic disproof only and
does not select the boundary itself.

All four scoped suites passed after the change: **260 passed in 29.13 s**.
The real three-film gate
`outputs/closing_credit_onset_vlm/batches/boundary3_finalfix_20260715_v1`
then produced:

- DRAKULA FOUND 859 exact, 84.085 s;
- JURASSIC PARK 2 FOUND 283 exact, 57.312 s; its television lower-third near
  191 remained `DIEGETIC_SCREEN` in A, B and raw-S audits;
- ATTILA FOUND 539 exact, 63.240 s.

Final frozen hashes for the next validation gate are:

- `window_detector.py`:
  `80158556BD5CFD72198C042997C13ADB087B9D70B45E24776A96B5607C643664`
- `ollama_client.py`:
  `6111BCD49B8A163B8F875886344DDF74BB383A3D9DE7207DF3A58E7F4DBFC935`
- `test_closing_credit_onset_window_protocol.py`:
  `2D3B7251F9D8514C35FF8166ADF9FD133B2E487861776B87AD526DA4924C4261`
- `test_closing_credit_onset_detector.py`:
  `8116EF90CA9970AA832F03B275CC69B8C82F647B48846708E8D65CABF5822F3B`

Next gate: one frozen-source batch containing the stable eight labelled films
plus YARI, PINOKYO, KUKLA ADAM, JURASSIC PARK 2, YABANDAN GELEN ADAM, OLUM
ASANSORU and BEYAZ BIZON. The clean 51-film v3 run remains blocked until this
15-film union is exact at every labelled boundary with no wrong FOUND.
