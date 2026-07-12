# -*- coding: utf-8 -*-
"""Eski run-manifest JSON'larındaki MITAS secret değerlerini atomik olarak maskeler.

Varsayılan dry-run'dır. Yalnız `config_snapshot` içindeki secret-isimli anahtarlar değişir;
değerin kısa SHA-256 izi aynı secret'ın tekrarını teşhis etmek için korunur.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

SECRET_RE = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|AUTH|CREDENTIAL|COOKIE|"
    r"DEEPSEEK|GEMINI|OMDB|TMDB)", re.IGNORECASE)


def redact_manifest(obj: dict) -> tuple[dict, int]:
    cfg = obj.get("config_snapshot")
    if not isinstance(cfg, dict):
        return obj, 0
    changed = 0
    for key, value in list(cfg.items()):
        if not SECRET_RE.search(str(key)):
            continue
        text = str(value or "")
        if text.startswith("<redacted:"):
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12] if text else "empty"
        cfg[key] = f"<redacted:{digest}>"
        changed += 1
    return obj, changed


def sanitize_file(path: Path, *, apply: bool) -> int:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — bozuk/JSON-olmayan dosyaya dokunma
        return 0
    if not isinstance(obj, dict):
        return 0
    obj, changed = redact_manifest(obj)
    if changed and apply:
        tmp = path.with_name(f".{path.name}.{os.getpid()}.sanitize.tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(str(tmp), str(path))
    return changed


def iter_manifests(root: Path):
    for path in root.rglob("*.json"):
        if path.name == "run_manifest.json" or path.parent.name == "manifests":
            yield path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    files = fields = 0
    for root in args.roots:
        if not root.exists():
            continue
        for path in iter_manifests(root):
            n = sanitize_file(path, apply=args.apply)
            if n:
                files += 1
                fields += n
    print(json.dumps({"apply": args.apply, "files": files, "fields": fields}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
