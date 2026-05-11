from __future__ import annotations

import faulthandler

from common import CLIPS_DIFFERENT, same_instance


if __name__ == "__main__":
    faulthandler.enable()
    raise SystemExit(same_instance("T7", CLIPS_DIFFERENT))
