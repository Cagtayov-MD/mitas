import sys
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))
