# MITAS env-bayrak envanteri (ÜRETİLMİŞ DOSYA — elle düzenleme!)

Üretici: `python scripts/bayrak_envanteri.py` — bayrak ekleyen/söken işten sonra yeniden koş.
Toplam bayrak: **307**

| Bayrak | Varsayılan(lar) | Dosya sayısı | Dosyalar |
|---|---|---|---|
| `MITAS_ACCESS_COOKIE_SECURE` | — | 1 | `core/api/access.py` |
| `MITAS_ACCESS_SECRET` | — | 1 | `core/api/access.py` |
| `MITAS_ACCESS_SECRET_FILE` | — | 1 | `core/api/access.py` |
| `MITAS_AFIS_CACHE_DIR` | — | 2 | `scripts/mitas_roots.py`, `scripts/tek_film_kunye.py` |
| `MITAS_ANTHROPIC_MODEL` | claude-sonnet-4-6 | 3 | `core/api/asr_server.py`, `scripts/_health_probe.py`, `scripts/mitas_pipeline.py` |
| `MITAS_API_STATUS_DIR` | — | 1 | `scripts/mitas_roots.py` |
| `MITAS_ASR_FOREIGN_BEAM` | 1 | 1 | `scripts/_pipe_asr.py` |
| `MITAS_ASR_LLM_VALVE` | 1 | 2 | `scripts/_pipe_asr.py`, `scripts/mitas_pipeline.py` |
| `MITAS_ASR_MIN_COMMIT_GB` | 8 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_ASR_P` | — | 1 | `core/pipelines/asr/profiles.py` |
| `MITAS_ASR_PRE_VALVE` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_ASR_SERVER_8787` | — | 1 | `core/api/asr_server.py` |
| `MITAS_ASR_TIMEOUT` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_ASR_TRANSCRIBE_URL` | http://127.0.0.1:8787/api/asr/transcribe | 1 | `core/api/tedial/router.py` |
| `MITAS_BATCH_MODE` | — | 3 | `scripts/from_hub_batch.py`, `scripts/mitas_pipeline.py`, `scripts/run_manifest.py` |
| `MITAS_BEKCI_TEXT_OR` | 1 | 1 | `scripts/_pipe_ocr.py` |
| `MITAS_CAST_CAP` | 10 | 6 | `scripts/_pipe_pdf.py`, `scripts/credit_qc_block.py`, `scripts/credit_text_read.py`, `scripts/credit_video_read.py` +2 |
| `MITAS_CAST_CASING_GATE` | 1 | 1 | `scripts/credit_text_read.py` |
| `MITAS_CAST_OCR_KEEP` | — | 2 | `scripts/credit_qc_block.py`, `scripts/mitas_pipeline.py` |
| `MITAS_CAST_RESCUE_DROPPED` | 1 | 1 | `scripts/credit_qc_block.py` |
| `MITAS_CIKIS_FALLBACK_POOL` | 0 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CIKIS_FALLBACK_TIMEOUT` | 900 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CLONE_COLLAPSE` | 1 | 1 | `scripts/credit_text_read.py` |
| `MITAS_CREDIT_CAST_BLOCK_FAST` | 0 | 1 | `scripts/credit_text_read.py` |
| `MITAS_CREDIT_DEFERENCE` | 1 | 3 | `scripts/_pipe_pdf.py`, `scripts/credit_qc_block.py`, `scripts/tek_film_kunye.py` |
| `MITAS_CREDIT_DETECT` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_DETECT_CLOSE_BACK` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_DETECT_LOWCONF_MERGE` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_DETECT_LOWCONF_MERGE_MINCONF` | 0.40 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_DETECT_LOWCONF_MINCONF` | 0.45 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_DETECT_LOWCONF_MIN_DUR` | 180 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_DETECT_MINCONF` | 0.60 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_DETECT_TIGHT_CLOSE` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_MODELS` | gemma4:26b | 1 | `scripts/credit_video_read.py` |
| `MITAS_CREDIT_PARSE_V2` | — | 2 | `OCR-worktree/pdf-mitas/credit_parse.py`, `scripts/kok_neden_fix1_harness.py` |
| `MITAS_CREDIT_PREFER_TEXT` | — | 1 | `scripts/kok_neden_fix2_harness.py` |
| `MITAS_CREDIT_TEXT_DILIM` | 1 | 1 | `scripts/_pipe_credit_text.py` |
| `MITAS_CREDIT_TEXT_MODEL` |  / gemma-4-31b-it-qat-vision:latest | 3 | `scripts/_pipe_credit_text.py`, `scripts/credit_text_read.py`, `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_VALIDATE` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_CREDIT_VLM_MODEL` | qwen3-vl:30b | 1 | `scripts/credit_start_vlm.py` |
| `MITAS_CVLM_STRIDE` | 12 | 1 | `scripts/credit_start_vlm.py` |
| `MITAS_DB` | — | 1 | `OCR-worktree/pdf-mitas/name_normalize.py` |
| `MITAS_DEBUG_TRACE_CLIP_ID` | — | 1 | `scripts/debug_trace.py` |
| `MITAS_DEBUG_TRACE_DIR` | — | 1 | `scripts/debug_trace.py` |
| `MITAS_DEBUG_TRACE_ID` | — | 1 | `scripts/debug_trace.py` |
| `MITAS_DEBUG_TRACE_RUN_ID` | — | 1 | `scripts/debug_trace.py` |
| `MITAS_DEDUP_HI_SIZE` | 16 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_DEDUP_TDIFF` | 40 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_DEEPSEEK` | — | 3 | `OCR-worktree/pdf-mitas/name_normalize.py`, `scripts/_deepseek.py`, `scripts/_health_probe.py` |
| `MITAS_DEEPSEEK_BASE` | https://api.deepseek.com | 1 | `scripts/_deepseek.py` |
| `MITAS_DEEPSEEK_MODEL` | deepseek-chat | 2 | `scripts/_health_probe.py`, `scripts/mitas_pipeline.py` |
| `MITAS_DEEPSEEK_TIMEOUT` | 120 | 1 | `scripts/_deepseek.py` |
| `MITAS_DILIM_BLANK_FRAC` | — | 1 | `scripts/master_png_dilimle.py` |
| `MITAS_DILIM_FG_DELTA` | — | 1 | `scripts/master_png_dilimle.py` |
| `MITAS_DILIM_MAX` | — | 1 | `scripts/master_png_dilimle.py` |
| `MITAS_DILIM_MIN` | — | 1 | `scripts/master_png_dilimle.py` |
| `MITAS_DILIM_OVERLAP` | — | 1 | `scripts/master_png_dilimle.py` |
| `MITAS_DILIM_TARGET` | — | 1 | `scripts/master_png_dilimle.py` |
| `MITAS_DILIM_VL_BACKEND` | ollama | 1 | `scripts/_pipe_dilim_vl.py` |
| `MITAS_DILIM_VL_MODEL` | qwen2.5vl:7b / qwen3-vl:8b | 2 | `harness/kunye_stages.py`, `scripts/_pipe_dilim_vl.py` |
| `MITAS_DILIM_VL_NUM_CTX` | 16384 | 1 | `scripts/_pipe_dilim_vl.py` |
| `MITAS_DILIM_VL_TIMEOUT` | 180 | 1 | `scripts/_pipe_dilim_vl.py` |
| `MITAS_DIRECTOR_RESCUE` | 1 | 3 | `scripts/_pipe_ocr.py`, `scripts/credit_text_read.py`, `scripts/mitas_pipeline.py` |
| `MITAS_DISABLE_ASR` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_DIZI_VL_DILIM` | 1 | 1 | `scripts/dizi_credit_parse.py` |
| `MITAS_DIZI_VL_MODEL` | glm-ocr:latest | 1 | `scripts/dizi_credit_parse.py` |
| `MITAS_DIZI_VL_TIMEOUT` | 120 | 1 | `scripts/dizi_credit_parse.py` |
| `MITAS_DUCKDB_CACHE` | — | 1 | `scripts/sync_duckdb_local.py` |
| `MITAS_EKRAN_KB_YON` | 1 | 1 | `scripts/tek_film_kunye.py` |
| `MITAS_EXTRACT_GATE_BEFORE_CAP` | 1 | 1 | `scripts/credit_text_read.py` |
| `MITAS_FFMPEG` | — | 7 | `core/pipelines/ocr/credit_experiment.py`, `core/pipelines/ocr/simple.py`, `scripts/_channel_lang.py`, `scripts/_pipe_video_vl.py` +3 |
| `MITAS_FFMPEG_DLL_DIR` | — | 1 | `scripts/alignment_subprocess.py` |
| `MITAS_FFMPEG_EXTRACT_PARALLEL` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_FFPROBE` | — | 4 | `scripts/_channel_lang.py`, `scripts/_pipe_video_vl.py`, `scripts/_subtitle_detect.py`, `scripts/mitas_pipeline.py` |
| `MITAS_FLOW_PREFETCH` | 1 | 1 | `core/api/asr_server.py` |
| `MITAS_FLOW_STAGING` | — | 1 | `core/api/asr_server.py` |
| `MITAS_FRAMEGATE` | — | 2 | `OCR-worktree/py/20260601_pipeline100.py`, `OCR-worktree/py/_ab_master.py` |
| `MITAS_FRAME_DEDUP` | 0 | 2 | `scripts/_pipe_ocr.py`, `scripts/mitas_pipeline.py` |
| `MITAS_FRAME_DEDUP_HAM` | 4 | 1 | `scripts/_pipe_ocr.py` |
| `MITAS_FRAME_DEDUP_KEEP` | 3 | 1 | `scripts/_pipe_ocr.py` |
| `MITAS_FROM_HUB` | — | 2 | `scripts/mitas_pipeline.py`, `scripts/promote_hub.py` |
| `MITAS_FROM_HUB_PATH` | — | 3 | `scripts/from_hub_batch.py`, `scripts/mitas_pipeline.py`, `scripts/run_manifest.py` |
| `MITAS_FROM_HUB_SPECS` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_FUZZY_DBQC` | 1 | 1 | `scripts/tek_film_kunye.py` |
| `MITAS_FUZZY_KANONIK` | 1 | 1 | `scripts/credit_text_read.py` |
| `MITAS_GARBLE_NGRAM` | 0 | 2 | `scripts/mitas_pipeline.py`, `scripts/tek_film_kunye.py` |
| `MITAS_GARBLE_NGRAM_ROUTE` | 0 | 2 | `scripts/mitas_pipeline.py`, `scripts/tek_film_kunye.py` |
| `MITAS_GEMINI` | — | 3 | `scripts/_gemini.py`, `scripts/_health_probe.py`, `scripts/mitas_pipeline.py` |
| `MITAS_GEMINI_BASE` | https://generativelanguage.googleapis.com | 2 | `scripts/_gemini.py`, `scripts/_health_probe.py` |
| `MITAS_GEMINI_MODEL` | gemini-2.5-flash / gemma-4-31b-it | 3 | `scripts/_gemini.py`, `scripts/_health_probe.py`, `scripts/mitas_pipeline.py` |
| `MITAS_GEMINI_THINK` | 512 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_GEMINI_TIMEOUT` | 120 | 1 | `scripts/_gemini.py` |
| `MITAS_GEMMA_BATCH` | 24 | 1 | `scripts/credit_video_read.py` |
| `MITAS_GEMMA_FULLCOVER` | — | 2 | `scripts/credit_video_read.py`, `scripts/mitas_pipeline.py` |
| `MITAS_GEMMA_PERSEG` | 120 | 1 | `scripts/credit_video_read.py` |
| `MITAS_GIRIS_DEDUP_HAM` | — | 1 | `scripts/giris_jenerik_havuzu.py` |
| `MITAS_GIRIS_DEDUP_HI` | — | 1 | `scripts/giris_jenerik_havuzu.py` |
| `MITAS_GIRIS_JENERIK_POOL` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_GIRIS_JENERIK_POOL_TIMEOUT` | 900 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_GIRIS_MIN_LINES` | — | 1 | `scripts/giris_jenerik_havuzu.py` |
| `MITAS_GIRIS_SCAN_CAP` | — | 1 | `scripts/giris_jenerik_havuzu.py` |
| `MITAS_GIRIS_SUB_FRAC` | 0.82 | 2 | `scripts/giris_jenerik_havuzu.py`, `scripts/giris_master_cropstack.py` |
| `MITAS_GLOBAL_PERSON_GATE` | 0 | 1 | `scripts/tek_film_kunye.py` |
| `MITAS_IMDB_DUCKDB` | — | 6 | `scripts/_name_ngram_garble.py`, `scripts/credit_crosscheck.py`, `scripts/credit_video_read.py`, `scripts/kok_neden_lock_olcum.py` +2 |
| `MITAS_IMDB_DUCKDB_SRC` | — | 1 | `scripts/sync_duckdb_local.py` |
| `MITAS_JENERIK_BACK_EXTEND` | 1 | 1 | `scripts/_jenerik_pool.py` |
| `MITAS_JENERIK_CLIP_MODEL` | siglip | 1 | `core/pipelines/ocr/jenerik_detector.py` |
| `MITAS_JENERIK_DEBUG_SHEET` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_JENERIK_DETECT` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_JENERIK_FOOTAGE_TRIM` | 1 | 1 | `scripts/_jenerik_pool.py` |
| `MITAS_JENERIK_GLM_MAX_FRAMES` | 16 | 1 | `scripts/_jenerik_parallel_debug.py` |
| `MITAS_JENERIK_GLM_MAX_SIDE` | 960 | 1 | `scripts/_jenerik_parallel_debug.py` |
| `MITAS_JENERIK_GLM_MODEL` | glm-ocr:latest | 1 | `scripts/_jenerik_parallel_debug.py` |
| `MITAS_JENERIK_GLM_NUM_PREDICT` | 768 | 1 | `scripts/_jenerik_parallel_debug.py` |
| `MITAS_JENERIK_GLM_OV` | 100 | 1 | `scripts/_jenerik_parallel_debug.py` |
| `MITAS_JENERIK_GLM_TILE` | 1200 | 1 | `scripts/_jenerik_parallel_debug.py` |
| `MITAS_JENERIK_GLM_TIMEOUT` | 45 | 1 | `scripts/_jenerik_parallel_debug.py` |
| `MITAS_JENERIK_LATIN_LC_NAMES` | — | 3 | `core/pipelines/ocr/jenerik_frame_pool_detector.py`, `scripts/_jenerik_pool.py`, `scripts/giris_jenerik_havuzu.py` |
| `MITAS_JENERIK_NONLATIN_NAMES` | — | 3 | `core/pipelines/ocr/jenerik_frame_pool_detector.py`, `scripts/_jenerik_pool.py`, `scripts/giris_jenerik_havuzu.py` |
| `MITAS_JENERIK_OCR_ENGINE` | paddle | 1 | `scripts/_pipe_ocr.py` |
| `MITAS_JENERIK_OCR_GATE` | — | 1 | `core/pipelines/ocr/jenerik_detector.py` |
| `MITAS_JENERIK_OCR_REFINE` | 1 | 1 | `scripts/_jenerik_detect.py` |
| `MITAS_JENERIK_ONEOCR_FALLBACK` | 1 | 1 | `scripts/_jenerik_pool.py` |
| `MITAS_JENERIK_OPEN_BACK_CAP` | 400 | 1 | `core/pipelines/ocr/jenerik_detector.py` |
| `MITAS_JENERIK_OPEN_BACK_GAP` | 200 | 1 | `core/pipelines/ocr/jenerik_detector.py` |
| `MITAS_JENERIK_OPEN_BRIDGE` | — | 1 | `core/pipelines/ocr/jenerik_detector.py` |
| `MITAS_JENERIK_PADDLE_MODEL_ROOT` | — | 4 | `core/pipelines/ocr/jenerik_frame_pool_detector.py`, `harness/apply_trim.py`, `harness/cikis_tail_scan.py`, `harness/giris_trailing_trim.py` |
| `MITAS_JENERIK_PARALLEL_DEBUG` | 1 | 2 | `scripts/jenerik_debug_batch.py`, `scripts/mitas_pipeline.py` |
| `MITAS_JENERIK_PARALLEL_DEBUG_TIMEOUT` | 1800 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_JENERIK_PARALLEL_POOL` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_JENERIK_POOL_ACCEPT_REVIEW` | 1 | 1 | `scripts/_jenerik_pool.py` |
| `MITAS_JENERIK_POOL_TIMEOUT` | 900 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_JENERIK_PROSE_CREDIT_EXEMPT` | — | 1 | `core/pipelines/ocr/jenerik_frame_pool_detector.py` |
| `MITAS_JENERIK_VLM_RESCUE` | 1 | 1 | `scripts/_jenerik_pool.py` |
| `MITAS_JENERIK_VL_TIMEOUT` | 180 | 1 | `scripts/_jenerik_parallel_debug.py` |
| `MITAS_KB_CAST_ADD` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_KB_DUCKDB` | — | 1 | `scripts/credit_validate.py` |
| `MITAS_KB_INITIAL_TOLERANS` | 1 | 2 | `scripts/credit_text_read.py`, `scripts/test_kb_initial_tolerans.py` |
| `MITAS_KB_SUFFIX_SPLIT` | 1 | 1 | `scripts/_pipe_ocr.py` |
| `MITAS_KISI_TEYIT` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_KOK_NEDEN_RAPORU_2026` | — | 1 | `scripts/kok_neden_rapor.py` |
| `MITAS_LANGUAGE_INTELLIGENCE` | off | 1 | `core/pipelines/asr/language_intelligence.py` |
| `MITAS_LANGUAGE_INTELLIGENCE_DEVICE` | cuda | 1 | `core/pipelines/asr/language_intelligence.py` |
| `MITAS_LID_TR_VETO` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_LID_TR_VOTE_MIN` | 1 | 1 | `scripts/_pipe_asr.py` |
| `MITAS_LMR_MININST` | 3 | 1 | `OCR-worktree/py/20260601_pipeline100.py` |
| `MITAS_MANIFEST_DIR` | — | 3 | `scripts/mitas_roots.py`, `scripts/retry_planner.py`, `scripts/run_manifest.py` |
| `MITAS_MASTER_DEDUP_HIRES` | 1 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_MASTER_DILIM_AUTO` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_MASTER_DILIM_TIMEOUT` | 180 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_MASTER_PNG` | — | 1 | `scripts/_pipe_ocr.py` |
| `MITAS_MASTER_PNG_AUTO` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_MASTER_PNG_TIMEOUT` | 300 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_MSEG` | cikis | 3 | `harness/fine_strip.py`, `harness/master_montage.py`, `harness/montage_audit.py` |
| `MITAS_MSFONT_DIR` | — | 3 | `OCR-worktree/pdf-mitas/_make_cikti_diagram.py`, `OCR-worktree/pdf-mitas/_make_pdf.py`, `OCR-worktree/pdf-mitas/_make_profil_diagram.py` |
| `MITAS_MT_B` | — | 1 | `scripts/translate_benchmark.py` |
| `MITAS_NGRAM_MODEL` | — | 1 | `scripts/_name_ngram_garble.py` |
| `MITAS_NGRAM_PAIR` | -3.2 | 1 | `scripts/_name_ngram_garble.py` |
| `MITAS_NGRAM_SOLO` | -4.3 | 1 | `scripts/_name_ngram_garble.py` |
| `MITAS_NONLATIN_LLM_ROMANIZE` | 1 | 1 | `scripts/credit_text_read.py` |
| `MITAS_NONLATIN_MIN_RATIO` | 0.02 | 1 | `scripts/credit_text_read.py` |
| `MITAS_NONLATIN_TRANSLIT` | 1 | 1 | `scripts/credit_text_read.py` |
| `MITAS_NO_V4_FINAL` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_NO_VIDEO_CREDITS` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_NO_VL_FALLBACK` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OCR_ALLOW_MODEL_DOWNLOAD` | — | 2 | `core/pipelines/ocr/credit_experiment.py`, `scripts/profile_kj_dataset.py` |
| `MITAS_OCR_FALLBACK` | — | 1 | `core/pipelines/ocr/fallback_strategy.py` |
| `MITAS_OCR_FORM_KEEP` | — | 2 | `scripts/credit_qc_block.py`, `scripts/mitas_pipeline.py` |
| `MITAS_OCR_GLM_CONSENSUS` | 1 | 2 | `scripts/_pipe_ocr.py`, `scripts/mitas_pipeline.py` |
| `MITAS_OCR_MIN_LINES` | 30 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OCR_PADDLE` | 0 | 1 | `scripts/_pipe_ocr.py` |
| `MITAS_OCR_PYTHON` | — | 1 | `core/api/tedial/job_runner.py` |
| `MITAS_OCR_T` | — | 1 | `core/pipelines/ocr/manifest_profiles.py` |
| `MITAS_OCR_TIMEOUT` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OLLAMA` | http://127.0.0.1:11434 | 6 | `scripts/_pipe_asr.py`, `scripts/_pipe_dilim_vl.py`, `scripts/credit_start_vlm.py`, `scripts/credit_text_read.py` +2 |
| `MITAS_OLLAMA_BEKCI` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OLLAMA_KEEP_ALIVE` | 15m / 5m | 4 | `scripts/_kunye_qwen_check.py`, `scripts/credit_text_read.py`, `scripts/mitas_pipeline.py`, `scripts/run_manifest.py` |
| `MITAS_OLLAMA_NUM_CTX` | 8192 | 1 | `scripts/credit_text_read.py` |
| `MITAS_OLLAMA_NUM_CTX_RETRY` | 12288 | 1 | `scripts/credit_text_read.py` |
| `MITAS_OLLAMA_NUM_PREDICT` | 2048 | 1 | `scripts/credit_text_read.py` |
| `MITAS_OLLAMA_SEED` | 42 | 1 | `scripts/credit_text_read.py` |
| `MITAS_OLLAMA_TIMEOUT` | 300 | 2 | `scripts/_ollama.py`, `scripts/credit_text_read.py` |
| `MITAS_OLLAMA_URL` | http://127.0.0.1:11434 / http://localhost:11434 | 2 | `scripts/dizi_credit_parse.py`, `scripts/run_manifest.py` |
| `MITAS_OMDB` | — | 1 | `OCR-worktree/pdf-mitas/poster_fetch.py` |
| `MITAS_ONEOCR_CONFIG_DIR` | — | 1 | `core/pipelines/ocr/credit_experiment.py` |
| `MITAS_OUTPUTS_DIR` | — | 6 | `scripts/_api_status.py`, `scripts/_channel_lang.py`, `scripts/_pipe_asr.py`, `scripts/mitas_roots.py` +2 |
| `MITAS_OZET_CLOUD` | 0 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OZET_GEMINI` | 0 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OZET_KONTROL` | 0 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OZET_OLLAMA_MODEL` | gemma4:26b | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OZET_RETRIES` | 3 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OZET_RETRY_BACKOFF` | 6 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_OZET_STRIP_TS` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_PADDLEOCR_DEVICE` | — | 1 | `core/pipelines/ocr/credit_experiment.py` |
| `MITAS_PADDLEOCR_TEXT_DET_MODEL_DIR` | — | 2 | `core/pipelines/ocr/credit_experiment.py`, `scripts/jenerik_tek_png.py` |
| `MITAS_PADDLEOCR_TEXT_DET_MODEL_NAME` | PADDLE_DETECTION_MODEL_NAME | 2 | `core/pipelines/ocr/credit_experiment.py`, `scripts/jenerik_tek_png.py` |
| `MITAS_PADDLEOCR_TEXT_REC_MODEL_DIR` | — | 2 | `core/pipelines/ocr/credit_experiment.py`, `scripts/jenerik_tek_png.py` |
| `MITAS_PADDLEOCR_TEXT_REC_MODEL_NAME` | PADDLE_RECOGNITION_MODEL_NAME | 2 | `core/pipelines/ocr/credit_experiment.py`, `scripts/jenerik_tek_png.py` |
| `MITAS_PADDLEOCR_USE_REAL_MODELSCOPE` | — | 1 | `core/pipelines/ocr/credit_experiment.py` |
| `MITAS_PARENT_RUN_ID` | — | 3 | `scripts/from_hub_batch.py`, `scripts/mitas_pipeline.py`, `scripts/run_manifest.py` |
| `MITAS_PDFMITAS_DIR` | — | 3 | `scripts/_pipe_pdf.py`, `scripts/credit_qc_block.py`, `scripts/tek_film_kunye.py` |
| `MITAS_PDF_PYTHON` | — | 3 | `core/api/asr_server.py`, `scripts/mitas_pipeline.py`, `scripts/regresyon_golden.py` |
| `MITAS_PDF_RENDER_AUDIT` | 1 | 2 | `scripts/credit_qc_block.py`, `scripts/mitas_pipeline.py` |
| `MITAS_PDF_TIMEOUT` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_PERSEG` | 48 | 1 | `OCR-worktree/_vlm_fullcover.py` |
| `MITAS_PIPELINE` | — | 1 | `core/api/asr_server.py` |
| `MITAS_PIPELINE_RUN_URL` | http://127.0.0.1:8787/api/pipeline/run | 1 | `core/api/tedial/router.py` |
| `MITAS_POOL_PARALLEL` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_POSTER_ERA_GATE` | 1 | 1 | `OCR-worktree/pdf-mitas/poster_fetch.py` |
| `MITAS_POSTER_VER_GATE` | 1 | 2 | `OCR-worktree/pdf-mitas/poster_fetch.py`, `scripts/mitas_pipeline.py` |
| `MITAS_PREFLIGHT` | 1 | 2 | `scripts/mitas_pipeline.py`, `scripts/run_manifest.py` |
| `MITAS_PREFLIGHT_GENERATE` | 1 | 1 | `scripts/run_manifest.py` |
| `MITAS_PREFLIGHT_MIN_DISK_GB` | 20 | 1 | `scripts/run_manifest.py` |
| `MITAS_PREFLIGHT_MODEL` | gemma-4-31b-it-qat-vision:latest | 1 | `scripts/run_manifest.py` |
| `MITAS_PRODUCER_IDENTITY_GATE` | 1 | 2 | `scripts/credit_kb_lookup.py`, `scripts/tek_film_kunye.py` |
| `MITAS_PROD_DEFAULTS` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_PROJECT_ROOT` |  / /opt/mitas | 27 | `OCR-worktree/master_png_monitor.py`, `OCR-worktree/pdf-mitas/_make_cikti_diagram.py`, `OCR-worktree/pdf-mitas/_make_pdf.py`, `OCR-worktree/pdf-mitas/_make_profil_diagram.py` +23 |
| `MITAS_QC2` | — | 3 | `scripts/credit_qc_gates.py`, `scripts/mitas_pipeline.py`, `scripts/tek_film_kunye.py` |
| `MITAS_QC2_WEB` | 1 | 2 | `scripts/mitas_pipeline.py`, `scripts/tek_film_kunye.py` |
| `MITAS_QC_BLOCK` | — | 3 | `scripts/mitas_pipeline.py`, `scripts/rerender_pdf_only.py`, `scripts/tek_film_kunye.py` |
| `MITAS_QC_DIRECTOR_ANCHOR` | 1 | 2 | `scripts/credit_qc_block.py`, `scripts/mitas_pipeline.py` |
| `MITAS_QC_FLOORFILL_OCRGUARD` | — | 3 | `scripts/credit_qc_otorite_audit_test.py`, `scripts/mitas_pipeline.py`, `scripts/tek_film_kunye.py` |
| `MITAS_QC_FUZZY_DEDUP` | — | 3 | `scripts/credit_qc_block.py`, `scripts/credit_qc_otorite_audit_test.py`, `scripts/mitas_pipeline.py` |
| `MITAS_QC_NONCAST_FILTER` | — | 3 | `scripts/credit_qc_block.py`, `scripts/mitas_pipeline.py`, `scripts/tek_film_kunye.py` |
| `MITAS_QC_OTORITE_AUDIT` | — | 3 | `scripts/credit_qc_block.py`, `scripts/mitas_pipeline.py`, `scripts/tek_film_kunye.py` |
| `MITAS_QC_OTORITE_ROUTE` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_QC_PRODUCER_STRONGID` | 1 | 2 | `scripts/credit_qc_block.py`, `scripts/mitas_pipeline.py` |
| `MITAS_QC_ROLE_FILTER` | 0 | 2 | `scripts/credit_text_read.py`, `scripts/mitas_pipeline.py` |
| `MITAS_READING_CARD_MIN_HOLD` | 3 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_READING_CARD_SAME_THR` | 7 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_READING_EARLY_SPLIT_FRAMES` | 45 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_READING_OPENING_CARD_MIN_HOLD` | 2 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_READING_OPENING_FRAMES` | 10 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_READING_PASSTHROUGH_SCROLL_FRAC` | 0.75 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_REASONING` | 0 | 1 | `scripts/credit_text_read.py` |
| `MITAS_RUN_ROOT` |  / /opt/mitas/candidate_runs/kunye51_20260714 | 24 | `core/api/asr_server.py`, `harness/adaptive_dense.py`, `harness/apply_trim.py`, `harness/asama1_v2.py` +20 |
| `MITAS_SERILER_ROOT` | — | 2 | `scripts/dizi_isle.py`, `scripts/seri_kayit.py` |
| `MITAS_SES_DIL_KONTROL` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_SHADOW_VL` | 1 | 2 | `scripts/dizi_isle.py`, `scripts/mitas_pipeline.py` |
| `MITAS_SHADOW_VL_CAP` | CAP_DEFAULT | 1 | `scripts/_pipe_shadow_vl.py` |
| `MITAS_SHADOW_VL_CARD_STEP` | 8 | 1 | `scripts/_pipe_shadow_vl.py` |
| `MITAS_SHADOW_VL_MODEL` | MODEL_DEFAULT | 1 | `scripts/_pipe_shadow_vl.py` |
| `MITAS_SHADOW_VL_OV` | OV_DEFAULT | 1 | `scripts/_pipe_shadow_vl.py` |
| `MITAS_SHADOW_VL_TILE` | TILE_DEFAULT | 1 | `scripts/_pipe_shadow_vl.py` |
| `MITAS_SHADOW_VL_TIMEOUT` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_SKIP_SPECIAL_GENRE` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_SLIT_DY_HYBRID` | 0 | 2 | `OCR-worktree/db_compose_master.py`, `scripts/dizi_isle.py` |
| `MITAS_SLIT_HY_COV_THR` | 0.40 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_SLIT_HY_SKIP_THR` | 0.5 | 1 | `OCR-worktree/db_compose_master.py` |
| `MITAS_STITCH_COLRESCUE` | 1 | 2 | `OCR-worktree/py/20260601_stitch.py`, `scripts/ocr_worktree_canli_yedek/20260601_stitch.py` |
| `MITAS_STITCH_FREQVOTE` | 1 | 2 | `OCR-worktree/py/20260601_stitch.py`, `scripts/ocr_worktree_canli_yedek/20260601_stitch.py` |
| `MITAS_SUMMARY_MODEL` | — | 1 | `core/api/asr_server.py` |
| `MITAS_TEDIAL_AUTO_LOGIN` | — | 1 | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_DEV_COOKIE_ATTACH` | — | 1 | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_JOB_STORE` | — | 1 | `core/api/tedial/import_queue.py` |
| `MITAS_TEDIAL_LOGIN_PATH` | — | 1 | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_PASSWORD` | — | 1 | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_PASSWORD_FIELD` | — | 1 | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_REMEMBER_FIELD` | — | 1 | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_REMEMBER_VALUE` | — | 1 | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_SESSION_DIR` | — | 1 | `core/api/tedial/session.py` |
| `MITAS_TEDIAL_USERNAME` | — | 1 | `core/api/tedial/router.py` |
| `MITAS_TEDIAL_USERNAME_FIELD` | — | 1 | `core/api/tedial/router.py` |
| `MITAS_TESSERACT_CMD` | — | 1 | `core/pipelines/ocr/credit_experiment.py` |
| `MITAS_TESSERACT_LANG` | default_lang / tur+eng | 2 | `core/pipelines/ocr/credit_experiment.py`, `core/pipelines/ocr/simple.py` |
| `MITAS_TESSERACT_TESSDATA_DIR` | — | 1 | `core/pipelines/ocr/credit_experiment.py` |
| `MITAS_TEXTMASK` | — | 2 | `OCR-worktree/py/20260601_pipeline100.py`, `OCR-worktree/py/_ab_master.py` |
| `MITAS_TEYITSIZ_DUS` | 1 | 1 | `scripts/tek_film_kunye.py` |
| `MITAS_TMDB` | — | 8 | `OCR-worktree/pdf-mitas/poster_fetch.py`, `core/api/asr_server.py`, `scripts/credit_identity.py`, `scripts/credit_identity_test.py` +4 |
| `MITAS_TR_QIDS` | — | 1 | `OCR-worktree/pdf-mitas/name_normalize.py` |
| `MITAS_USE_CROSSCHECK` | — | 2 | `scripts/credit_export.py`, `scripts/credit_qc.py` |
| `MITAS_V4_TIMEOUT` | 900 | 2 | `scripts/mitas_pipeline.py`, `scripts/rerender_pdf_only.py` |
| `MITAS_VIDEO_CREDIT_TIMEOUT` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_VIDEO_VL` | 0 | 2 | `scripts/_pipe_video_vl.py`, `scripts/mitas_pipeline.py` |
| `MITAS_VIDEO_VL_BINDIRME` | 5 | 1 | `scripts/_pipe_video_vl.py` |
| `MITAS_VIDEO_VL_MODEL` | qwen3-vl-8b | 1 | `scripts/_pipe_video_vl.py` |
| `MITAS_VIDEO_VL_PAY` | 5 | 1 | `scripts/_pipe_video_vl.py` |
| `MITAS_VIDEO_VL_PENCERE` | 60 | 1 | `scripts/_pipe_video_vl.py` |
| `MITAS_VIDEO_VL_TIMEOUT` | 1800 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_VIDEO_VL_URL` | http://127.0.0.1:8100 | 1 | `scripts/_pipe_video_vl.py` |
| `MITAS_VL_CAST` | 0 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_CORPUS_DILIM` | 1 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_CORPUS_MANIFEST` | 1 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_CORPUS_RUNSCOPE` | 1 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_FALLBACK_TIMEOUT` | — | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_VL_KB_ANCHOR` | 1 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_MODEL` | gemma4:26b | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_OPENAI_BASE` | http://127.0.0.1:8000 | 1 | `scripts/_pipe_dilim_vl.py` |
| `MITAS_VL_RAW_ADJACENCY` | 1 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_RAW_CROSSLINE` | 1 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_RAW_FUZZY` | 1 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_RAW_FUZZY_RATIO` | 0.87 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_TEMP` | 0 | 1 | `scripts/credit_video_read.py` |
| `MITAS_VL_TOPP` | 1 | 1 | `scripts/credit_video_read.py` |
| `MITAS_VL_USE_GIRIS_POOL` | 1 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_VL_USE_JENERIK_POOL` | 1 | 1 | `scripts/_pipe_credit_vl.py` |
| `MITAS_WEB_CACHE` | 1 | 1 | `scripts/web_cache.py` |
| `MITAS_WEB_CACHE_DIR` | — | 4 | `scripts/mitas_roots.py`, `scripts/retry_planner.py`, `scripts/web_cache.py`, `scripts/web_isit.py` |
| `MITAS_WEB_CACHE_TTL` | 21600 | 1 | `scripts/web_cache.py` |
| `MITAS_WEB_ISIT` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_WIKIDATA_DUCKDB` | — | 4 | `OCR-worktree/pdf-mitas/name_normalize.py`, `scripts/credit_crosscheck.py`, `scripts/run_manifest.py`, `scripts/sync_duckdb_local.py` |
| `MITAS_WIKIDATA_DUCKDB_SRC` | — | 1 | `scripts/sync_duckdb_local.py` |
| `MITAS_WRITER_LOCK_PATH` | — | 1 | `scripts/run_manifest.py` |
| `MITAS_X` | def | 1 | `scripts/bayrak_envanteri.py` |
| `MITAS_XMLCAST_GATE_RELAX` | 1 | 1 | `scripts/mitas_pipeline.py` |
| `MITAS_YAPIMCI_OCR_CORROB` | 1 | 1 | `scripts/tek_film_kunye.py` |
| `MITAS_YON_TEYIT_KURTAR` | 1 | 1 | `scripts/tek_film_kunye.py` |
