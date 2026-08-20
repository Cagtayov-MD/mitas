#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MITAS SessionStart Hook
------------------------
Her oturum acilisinda GUNLUK.md'nin en ust (en yeni) kaydini otomatik olarak
Claude'un baglamina enjekte eder — "dun nerede kalmistik" bilgisi elle
hatirlamaya gerek kalmadan gelir. (CLAUDE.md'deki gunluk kuralinin makinesi.)
"""

import json
import sys

GUNLUK = "/opt/mitas/docs/GUNLUK.md"
MAX_LINES = 60

try:
    with open(GUNLUK, encoding="utf-8") as f:
        lines = f.readlines()
except Exception:
    sys.exit(0)  # gunluk yoksa sessiz gec

# Basliktan sonra ilk kaydi (en yeni) al: ikinci '## ' basligina kadar
out_lines = []
entry_count = 0
for ln in lines[:MAX_LINES * 2]:
    if ln.startswith("## "):
        entry_count += 1
        if entry_count > 1:
            break
    out_lines.append(ln)
    if len(out_lines) >= MAX_LINES:
        break

tail = "".join(out_lines).strip()
if not tail:
    sys.exit(0)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": (
            "MITAS GUNLUK — son kayit (docs/GUNLUK.md, otomatik yuklendi):\n\n"
            + tail
        ),
    }
}, ensure_ascii=False))
