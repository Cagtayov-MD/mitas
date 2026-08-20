"""Kule kokunu ve src/'yi test yoluna ekle — pytest'i dizinden bagimsiz kilar."""
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
for p in (KULE, KULE / "src", KULE / "tests"):
    sys.path.insert(0, str(p))
