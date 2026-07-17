#!/usr/bin/env bash
set -uo pipefail
export OLLAMA_HOST=127.0.0.1:11435
echo "=== bge-m3:atlas1 embed testi ==="
curl -s http://127.0.0.1:11435/api/embed -d '{"model":"bge-m3:atlas1","input":"test cumlesi"}' \
  -H 'Content-Type: application/json' -m 60 -o /tmp/embed_resp.json -w "HTTP:%{http_code}\n"
/root/.pyenv/versions/3.10.11/bin/python -c "
import json
d = json.load(open('/tmp/embed_resp.json'))
emb = d.get('embeddings') or d.get('embedding')
if isinstance(emb, list) and emb and isinstance(emb[0], list):
    print('embed boyutu:', len(emb[0]))
elif isinstance(emb, list):
    print('embed boyutu:', len(emb))
else:
    print('BEKLENMEYEN YANIT:', str(d)[:300])
"
echo ""
echo "=== glm-ocr:atlas1 kucuk metin-uret testi (GPU bos-mi kontrol) ==="
nvidia-smi --query-gpu=memory.free --format=csv,noheader
timeout 90 curl -s http://127.0.0.1:11435/api/generate -d '{"model":"glm-ocr:atlas1","prompt":"Merhaba, sadece OK yaz.","stream":false}' \
  -H 'Content-Type: application/json' -o /tmp/glm_resp.json -w "HTTP:%{http_code}\n"
cat /tmp/glm_resp.json 2>&1 | head -c 500
echo ""
echo "KAPI_E_SMOKE_DONE"
