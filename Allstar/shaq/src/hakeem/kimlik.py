"""HAKEEM icin film-ID kapsamli, surumlenebilir yerel kimlik adaptoru."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class JsonKimlikSaglayici:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        self.data = json.loads(raw)
        if not isinstance(self.data, dict):
            raise ValueError("kimlik JSON kok nesnesi olmali")
        self.version = f"local-json:{hashlib.sha256(raw).hexdigest()}"

    def candidates(self, external_ids: dict[str, str], role: str) -> list[str]:
        found: list[str] = []
        for namespace, external_id in sorted(external_ids.items()):
            # V2 onerilen bicim: {"imdb:tt123": {...}}. Geriye uyum icin yalın
            # ID de okunur; namespace'li anahtar cakismalari engeller.
            for key in (f"{namespace}:{external_id}", external_id):
                item = self.data.get(key, {})
                if isinstance(item, dict) and isinstance(item.get(role, []), list):
                    found.extend(item.get(role, []))
        return list(dict.fromkeys(value for value in found if isinstance(value, str) and value.strip()))
