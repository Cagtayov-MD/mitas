#!/usr/bin/env bash
cd /opt/atlas
for f in scripts/process_clip.py scripts/make_proxy.py scripts/segment_stories.py \
         src/atlas/segment/vlm_arbiter.py scripts/search_server.py \
         src/atlas/llm/ollama_client.py src/atlas/llm/embed.py src/atlas/llm/vlm_ocr.py \
         src/atlas/analyze/jenerik.py src/atlas/visual/production_type.py \
         src/atlas/analyze/layer_a.py scripts/enrich_event_tags.py scripts/enrich_facets.py \
         scripts/chunk_digest.py scripts/topic_report.py scripts/apply_hybrid.py \
         scripts/jenerik_discover.py; do
  n=$(grep -cE '^import os($| )' "$f" 2>/dev/null || echo 0)
  printf '%-45s import-os-count=%s\n' "$f" "$n"
done
