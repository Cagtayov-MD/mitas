from __future__ import annotations

from common import CLIP_NEWS, same_instance


if __name__ == "__main__":
    raise SystemExit(same_instance("T2", [CLIP_NEWS, CLIP_NEWS, CLIP_NEWS]))
