"""27B llama-mtmd motoru: GPU/model çalıştırmadan protokol testleri."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

from model import BellekHatasi, CiktiBozuk, ModelHatasi  # noqa: E402
from model_27b import LlamaMtmdMotor                    # noqa: E402


def motor_ve_kareler(tmp_path, monkeypatch, stdout=None, stderr="", rc=0):
    binary = tmp_path / "llama-mtmd-cli"
    model = tmp_path / "model.gguf"
    mmproj = tmp_path / "mmproj.gguf"
    for path in (binary, model, mmproj):
        path.write_bytes(b"x")
    binary.chmod(0o755)
    kareler = [tmp_path / "frame_0001.jpg", tmp_path / "frame_0002.jpg"]
    for path in kareler:
        path.write_bytes(b"jpg")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command, rc,
            stdout=stdout if stdout is not None else
            'log\n<|im_start|>assistant\n{"credits":["AS SYMES","STU PHILLIPS"],"subtitles":[]}',
            stderr=stderr,
        )

    monkeypatch.setattr("model_27b.subprocess.run", fake_run)
    motor = LlamaMtmdMotor(model, mmproj, binary)
    return motor, [str(path) for path in kareler], captured


def test_ozgun_coklu_image_her_kare_icin_ayri_bayraktir(tmp_path, monkeypatch):
    motor, kareler, captured = motor_ve_kareler(tmp_path, monkeypatch)
    metin = motor.sor("LITERAL OCR", kareler=kareler)
    command = captured["command"]
    assert command.count("--image") == 2
    image_values = [command[i + 1] for i, value in enumerate(command)
                    if value == "--image"]
    assert image_values == [str(Path(path).resolve()) for path in kareler]
    assert metin == "[CREDITS]\nAS SYMES\nSTU PHILLIPS\n[SUBTITLES]"


def test_json_schema_ve_ozgun_sampling_ayarlari_zorunlu(tmp_path, monkeypatch):
    motor, kareler, captured = motor_ve_kareler(tmp_path, monkeypatch)
    motor.sor("OCR", kareler=kareler)
    command = captured["command"]
    schema = json.loads(command[command.index("--json-schema") + 1])
    assert schema["required"] == ["credits", "subtitles"]
    assert schema["additionalProperties"] is False
    for flag, value in (("--temp", "0.01"), ("--top-p", "0.10"),
                        ("--repeat-penalty", "1.05")):
        assert command[command.index(flag) + 1] == value
    for olmayan in ("--top-k", "--min-p", "--seed", "--no-warmup"):
        assert olmayan not in command


def test_prompta_schema_talimati_eklenmez(tmp_path, monkeypatch):
    motor, kareler, captured = motor_ve_kareler(tmp_path, monkeypatch)
    motor.sor("OZGUN PROMPT", kareler=kareler)
    prompt = captured["command"][captured["command"].index("-p") + 1]
    assert "OZGUN PROMPT<|im_end|>" in prompt
    assert "Machine-enforced" not in prompt
    assert "credits and subtitles" not in prompt


def test_ham_json_ve_transport_kanita_girer(tmp_path, monkeypatch):
    motor, kareler, _ = motor_ve_kareler(tmp_path, monkeypatch)
    motor.sor("OCR", kareler=kareler)
    kanit = motor.son_cagri_kaniti()
    assert kanit["image_count"] == 2
    assert kanit["image_transport"] == "repeated_image_flags"
    assert json.loads(kanit["raw_json"])["credits"] == ["AS SYMES", "STU PHILLIPS"]
    assert len(kanit["raw_json_sha256"]) == 64
    assert kanit["runtime_multi_image_verified"] is None


def test_schema_disi_cikti_sessizce_kabul_edilmez(tmp_path, monkeypatch):
    motor, kareler, _ = motor_ve_kareler(
        tmp_path, monkeypatch, stdout="Here is the answer: AS SYMES")
    with pytest.raises(CiktiBozuk, match="JSON"):
        motor.sor("OCR", kareler=kareler)


def test_oom_ayri_siniflanir(tmp_path, monkeypatch):
    motor, kareler, _ = motor_ve_kareler(
        tmp_path, monkeypatch, rc=1, stderr="cudaMalloc failed: out of memory")
    with pytest.raises(BellekHatasi):
        motor.sor("OCR", kareler=kareler)


def test_gecici_cuda_kaynak_hatasi_bir_kez_retry_alir(tmp_path, monkeypatch):
    motor, kareler, _ = motor_ve_kareler(tmp_path, monkeypatch)
    cagrilar = 0

    def fake_run(command, **kwargs):
        nonlocal cagrilar
        cagrilar += 1
        if cagrilar == 1:
            return subprocess.CompletedProcess(
                command, -6, stdout="", stderr="CUDA error: resource allocation failed")
        return subprocess.CompletedProcess(
            command, 0,
            stdout='{"credits":["AS SYMES"],"subtitles":[]}',
            stderr="total = 3")

    monkeypatch.setattr("model_27b.subprocess.run", fake_run)
    monkeypatch.setattr("model_27b.time.sleep", lambda _: None)
    metin = motor.sor("OCR", kareler=kareler)
    assert metin.startswith("[CREDITS]\nAS SYMES")
    assert cagrilar == 2
    assert motor.son_cagri_kaniti()["attempt_count"] == 2
