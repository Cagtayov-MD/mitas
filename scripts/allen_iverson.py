# -*- coding: utf-8 -*-
"""ALLEN IVERSON (scripts/allen_iverson.py).

GÖREVİ: Frame Bindirme & Temporal Super-Frame Composite Generator.
Kullanıcının 'Frame Bindirme' stratejisi.

NOT: Bu modül saklanmış bağımsız bir motor bileşenidir (aktife entegre edilmemiştir).
"""
import sys
from pathlib import Path

# Forwarding to harness/track_kunye/allen_iverson.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "harness" / "track_kunye"))

from allen_iverson import uret_super_kare, generate_super_frame_from_files

__all__ = ["uret_super_kare", "generate_super_frame_from_files"]
