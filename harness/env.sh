# MITAS künye-51 Linux test koşusu ortak env
set -a
source /opt/mitas/mitas.env 2>/dev/null
set +a
export MITAS_PROJECT_ROOT=/opt/mitas
export MITAS_RUN_ROOT=/opt/mitas/candidate_runs/kunye51_20260714
export JENERIK_PADDLE_MODEL_ROOT=/opt/mitas/models/ocr/paddle/official_models
export MITAS_JENERIK_PADDLE_MODEL_ROOT=/opt/mitas/models/ocr/paddle/official_models
export MITAS_JENERIK_OCR_ENGINE=paddle
export MITAS_JENERIK_ONEOCR_FALLBACK=0
export JENERIK_PADDLE_FAST_NO_DOC=1
export MITAS_FRAME_DEDUP=0
export MITAS_SHADOW_VL=0
export MITAS_OLLAMA=http://127.0.0.1:11434
export PY_OCR=/opt/mitas/venvs/ocr/bin/python
export FILMS_DIR=/opt/mitas/filmtest/aaaa
export HARNESS=/opt/mitas/harness
