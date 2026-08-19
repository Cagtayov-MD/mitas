from __future__ import annotations

import subprocess

from src.config import load_config
from src.materialize import Materializer


def test_jordan_klibi_tek_sayili_cozunurlukte_de_uretilir(tmp_path):
    source = tmp_path / "odd.mkv"
    subprocess.run([
        "ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
        "-i", "color=c=black:s=81x61:r=2:d=1", "-c:v", "ffv1", str(source),
    ], check=True, shell=False)
    target = tmp_path / "credit.mp4"
    Materializer(load_config())._clip(source, target, 0.0, 1.0)
    assert target.is_file() and target.stat().st_size > 0
