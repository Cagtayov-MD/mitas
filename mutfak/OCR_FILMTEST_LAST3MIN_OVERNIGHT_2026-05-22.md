# OCR Filmtest Last 3 Minute Overnight

- Started: 2026-05-22T00:31:33.0521805+03:00
- Manifest: E:\MITAS\data\ocr_filmtest_last3min_manifest_20260522.json
- Root: E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_overnight_20260522_v2
- EasyOCR: disabled
- Paddle: CPU, PP-OCRv5 detector + latin_PP-OCRv5_mobile_rec

## phase1_allmodels_fps1_raw
- Started: 2026-05-22T00:31:33.1381871+03:00
- Engines: paddle,oneocr,tesseract
- FPS: 1
- Preprocess: off
- Report: E:\MITAS\mutfak\OCR_FILMTEST_LAST3MIN_PHASE1_ALLMODELS_FPS1_RAW_2026-05-22.md
- Status: E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_overnight_20260522_v2\phase1_allmodels_fps1_raw\batch_status.json

- Note: Initial v1 launch was stopped because CLI fps override was not taking precedence over manifest fps. Code was corrected; v2 is the active run.
- Phase 1 is all models on CPU Paddle at fps=1/preprocess=off so every film can finish overnight; later phases continue with higher fps raw passes.
- Completed: 2026-05-22T07:17:58.1997286+03:00
- Exit code: 0

## phase2_fastmodels_fps6_raw
- Started: 2026-05-22T07:17:58.2497280+03:00
- Engines: oneocr,tesseract
- FPS: 6
- Preprocess: off
- Report: E:\MITAS\mutfak\OCR_FILMTEST_LAST3MIN_PHASE2_FASTMODELS_FPS6_RAW_2026-05-22.md
- Status: E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_overnight_20260522_v2\phase2_fastmodels_fps6_raw\batch_status.json

- Completed: 2026-05-22T10:55:05.6500230+03:00
- Exit code: 0

## phase3_paddle_fps6_raw
- Started: 2026-05-22T10:55:05.6880217+03:00
- Engines: paddle
- FPS: 6
- Preprocess: off
- Report: E:\MITAS\mutfak\OCR_FILMTEST_LAST3MIN_PHASE3_PADDLE_FPS6_RAW_2026-05-22.md
- Status: E:\MITAS\outputs\ocr_credit_experiments\filmtest_last3min_overnight_20260522_v2\phase3_paddle_fps6_raw\batch_status.json

- Completed: 2026-05-23T07:00:07.2938498+03:00
- Exit code: -1

- Overnight script completed: 2026-05-23T07:00:07.3158500+03:00
