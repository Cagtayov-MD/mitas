#!/bin/bash
# mitas.env üretici — şablon + Windows registry'den sırlar (değerler asla stdout'a yazılmaz)
set -uo pipefail
NT="/run/media/cagatay/46F0903AF0903263/Users/TRT03/NTUSER.DAT"
ENVF=/opt/mitas/mitas.env
reg() { hivexget "$NT" '\Environment' "$1" 2>/dev/null | tr -d '\r' ; }

mkdir -p /opt/mitas/seriler /opt/mitas/models/hf_cache /opt/mitas/cache/staging

cat > "$ENVF" <<EOF
# MITAS Linux ortam dosyası — bare-metal (F kökü, /opt/mitas)
# Kullanım: set -a; source /opt/mitas/mitas.env; set +a
# chmod 600 — içinde sırlar var, git'e COMMIT ETME.

# ── Yollar ─────────────────────────────────────────────
MITAS_PROJECT_ROOT=/opt/mitas
MITAS_FFMPEG=/usr/bin/ffmpeg
MITAS_FFPROBE=/usr/bin/ffprobe
MITAS_PDF_PYTHON=/opt/mitas/venvs/asr/bin/python
MITAS_PDFMITAS_DIR=/opt/mitas/OCR-worktree/pdf-mitas
MITAS_FLOW_STAGING=/opt/mitas/cache/staging
MITAS_WEB_CACHE_DIR=/opt/mitas/cache/web
MITAS_DUCKDB_CACHE=/opt/mitas/cache/duckdb
MITAS_SERILER_ROOT=/opt/mitas/seriler
MITAS_MSFONT_DIR=/usr/share/fonts/truetype/msttcorefonts

# ── DuckDB'ler ─────────────────────────────────────────
MITAS_KB_DUCKDB=/opt/mitas/cache/duckdb/mitas.duckdb
MITAS_IMDB_DUCKDB=/opt/mitas/cache/duckdb/imdb.duckdb
MITAS_WIKIDATA_DUCKDB=/opt/mitas/cache/duckdb/mitas.duckdb

# ── OCR ────────────────────────────────────────────────
MITAS_PADDLEOCR_TEXT_DET_MODEL_DIR=/opt/mitas/models/ocr/paddle/official_models/PP-OCRv5_server_det
MITAS_PADDLEOCR_TEXT_REC_MODEL_DIR=/opt/mitas/models/ocr/paddle/official_models/latin_PP-OCRv5_mobile_rec
MITAS_JENERIK_PADDLE_MODEL_ROOT=/opt/mitas/models/ocr/paddle/official_models
MITAS_TESSERACT_TESSDATA_DIR=/usr/share/tesseract-ocr/5/tessdata
MITAS_OCR_ENGINE=glm
MITAS_JENERIK_OCR_ENGINE=paddle

# ── LLM / ollama ───────────────────────────────────────
MITAS_OLLAMA_URL=http://127.0.0.1:11434
MITAS_OLLAMA_KEEP_ALIVE=15m
OPENAI_BASE_URL=$(reg OPENAI_BASE_URL)
OPENAI_API_KEY=$(reg OPENAI_API_KEY)
MITAS_SUMMARY_MODEL=$(reg MITAS_SUMMARY_MODEL)

# ── HF ─────────────────────────────────────────────────
HF_HOME=/opt/mitas/models/hf_cache
HF_TOKEN=$(reg HF_TOKEN)

# ── Üretim bayrakları (Windows üretim + registry birebir) ──
MITAS_QC2=1
MITAS_QC2_WEB=1
MITAS_QC_BLOCK=1
MITAS_SES_DIL_KONTROL=0
MITAS_QC_DIRECTOR_ANCHOR=1
MITAS_CREDIT_DETECT=1
MITAS_CREDIT_VALIDATE=1
MITAS_KB_CAST_ADD=1
MITAS_GEMMA_FULLCOVER=1
MITAS_SHADOW_VL=0
MITAS_JENERIK_PARALLEL_DEBUG=0
MITAS_OCR_GLM_CONSENSUS=0
MITAS_FRAME_DEDUP=0
MITAS_QC_OTORITE_AUDIT=1
MITAS_QC_FLOORFILL_OCRGUARD=1
MITAS_QC_FUZZY_DEDUP=1
MITAS_QC_OTORITE_ROUTE=1
MITAS_QC_PRODUCER_STRONGID=1
MITAS_XMLCAST_GATE_RELAX=1
MITAS_POSTER_VER_GATE=1
MITAS_LID_TR_VETO=1
MITAS_GARBLE_NGRAM=1
MITAS_GARBLE_NGRAM_ROUTE=0
MITAS_CAST_OCR_KEEP=1
MITAS_CAST_CAP=18
MITAS_QC_NONCAST_FILTER=1
MITAS_QC_ROLE_FILTER=1
MITAS_DIRECTOR_RESCUE=1
MITAS_OZET_GEMINI=1
MITAS_OZET_CLOUD=1
MITAS_FLOW_PREFETCH=1

# ── Sırlar (Windows registry'den taşındı) ──────────────
ANTHROPIC_API_KEY=$(reg ANTHROPIC_API_KEY)
MITAS_TMDB=$(reg MITAS_TMDB)
MITAS_OMDB=$(reg MITAS_OMDB)
MITAS_DEEPSEEK=$(reg MITAS_DEEPSEEK)
MITAS_GEMINI=$(reg MITAS_GEMINI)

# ── Tedial pilotu ──────────────────────────────────────
MITAS_TEDIAL_AUTO_LOGIN=$(reg MITAS_TEDIAL_AUTO_LOGIN)
MITAS_TEDIAL_USERNAME=$(reg MITAS_TEDIAL_USERNAME)
MITAS_TEDIAL_PASSWORD=$(reg MITAS_TEDIAL_PASSWORD)
EOF
chmod 600 "$ENVF"
# Doğrulama: sır DEĞERLERİNİ yazmadan doluluk kontrolü
BOS=$(grep -cE '^[A-Z_]+=$' "$ENVF" || true)
echo "ENV-OLUSTU satir=$(wc -l < "$ENVF") bos-deger=$BOS"
grep -E '^[A-Z_]+=' "$ENVF" | awk -F= '{print $1"="((length($2)>0)?"DOLU":"BOS")}' | grep -E 'KEY|TOKEN|TMDB|OMDB|DEEPSEEK|GEMINI|TEDIAL|OPENAI|SUMMARY'
