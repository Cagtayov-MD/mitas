"""Subprocess entry point used by the local WebUI API for translations."""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.pipelines.translate.service import translate_batch


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty list")
    cache_dir = Path(str(payload.get("cache_dir") or "outputs/webui_translate_cache"))
    target_lang = str(payload.get("target_lang") or "tr")
    model_override = payload.get("model_override")
    if model_override is not None:
        model_override = str(model_override)

    results = translate_batch(
        items,
        target_lang=target_lang,
        cache_dir=cache_dir,
        model_override=model_override,
    )
    response = {
        "items": [
            {
                "segment_id": str(item["segment_id"]),
                "translation": result.__dict__,
            }
            for item, result in zip(items, results)
        ],
        "cache_dir": str(cache_dir),
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
