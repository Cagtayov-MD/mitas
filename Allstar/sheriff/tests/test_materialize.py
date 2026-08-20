from __future__ import annotations

import json
import subprocess

import pytest

from src.config import load_config
from src.materialize import MaterializeError, Materializer
from src.util import sha256_file


def test_jordan_klibi_tek_sayili_cozunurlukte_de_uretilir(tmp_path):
    source = tmp_path / "odd.mkv"
    subprocess.run([
        "ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
        "-i", "color=c=black:s=81x61:r=2:d=1", "-c:v", "ffv1", str(source),
    ], check=True, shell=False)
    target = tmp_path / "credit.mp4"
    Materializer(load_config())._clip(source, target, 0.0, 1.0)
    assert target.is_file() and target.stat().st_size > 0


def test_kobe_giris_sozlesmesi_lebron_girdisine_tasinir(tmp_path):
    selected, frame_dir = tmp_path / "selected", tmp_path / "frames"
    selected.mkdir()
    frame_dir.mkdir()
    source = selected / "_sinif.json"
    source.write_text(json.dumps({"surum": 1, "mod": "ardisik_aralik",
                                  "ilk_kare": 1, "son_kare": 4,
                                  "kareler": {}}), encoding="utf-8")

    result = Materializer._copy_frame_contract(selected, frame_dir, "giris")

    target = frame_dir / "_sinif.json"
    assert target.read_bytes() == source.read_bytes()
    assert result == {"frames_contract": "frames/_sinif.json",
                      "frames_contract_sha256": sha256_file(source),
                      "frames_contiguous": True}


def test_kobe_giris_sozlesmesi_yoksa_sessiz_dusmez(tmp_path):
    selected, frame_dir = tmp_path / "selected", tmp_path / "frames"
    selected.mkdir()
    frame_dir.mkdir()
    with pytest.raises(MaterializeError, match="sozlesmesi yok"):
        Materializer._copy_frame_contract(selected, frame_dir, "giris")
