from __future__ import annotations

from common import CLIPS_5, disable_tqdm_monkeypatch, same_instance


if __name__ == "__main__":
    disable_tqdm_monkeypatch()
    raise SystemExit(same_instance("TA2", CLIPS_5, monkeypatch_tqdm=True))
