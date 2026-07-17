#!/usr/bin/env bash
PY=/root/.pyenv/versions/3.10.11/bin/python
cd /opt/atlas
FILES="scripts/process_clip.py scripts/make_proxy.py scripts/segment_stories.py \
       scripts/jenerik_discover.py src/atlas/segment/vlm_arbiter.py scripts/search_server.py \
       src/atlas/llm/ollama_client.py src/atlas/llm/embed.py src/atlas/llm/vlm_ocr.py \
       src/atlas/analyze/jenerik.py src/atlas/analyze/layer_a.py src/atlas/visual/production_type.py \
       scripts/enrich_event_tags.py scripts/enrich_facets.py"
ok=0; bad=0
for f in $FILES; do
  if $PY -m py_compile "$f" 2>/tmp/synerr.log; then
    ok=$((ok+1))
  else
    bad=$((bad+1))
    echo "SYNTAX HATASI: $f"
    cat /tmp/synerr.log
  fi
done
echo "OK=$ok BAD=$bad"
