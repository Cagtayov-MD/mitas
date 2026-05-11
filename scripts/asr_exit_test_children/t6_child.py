from __future__ import annotations

from common import CLIP_NEWS, ctranslate2_cleanup_api_probe, parse_variant_arg, same_instance


if __name__ == "__main__":
    variant = parse_variant_arg()
    if variant == "ct2_api":
        raise SystemExit(ctranslate2_cleanup_api_probe("T6d"))
    raise SystemExit(same_instance("T6", [CLIP_NEWS, CLIP_NEWS, CLIP_NEWS], cleanup_after_each=variant))
