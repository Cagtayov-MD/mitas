# -*- coding: utf-8 -*-
"""motor.py orkestrasyon testleri — faster_whisper FAKE ile (GPU/model gerekmez)."""
import sys
import types
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

import motor  # noqa: E402


class _FakeSeg:
    def __init__(self, start, text):
        self.start, self.text = start, text


class _FakeInfo:
    def __init__(self, duration=60.0, language=None):
        self.duration, self.language = duration, language


class _FakeWhisperModel:
    """Kurulum argümanlarını kaydeder; transcribe önceden yüklenmiş segmentleri döner."""
    son_kurulum = None
    son_transcribe = None

    def __init__(self, yol, device="cuda", compute_type="float16", local_files_only=False):
        # cuda istenmiş ama gerçek CUDA yoksa test makinesi CPU'ya düşsün — kaydet yeter
        _FakeWhisperModel.son_kurulum = {"yol": str(yol), "device": device,
                                         "compute": compute_type}
        self._segments = _FakeWhisperModel.kayitli_segmentler

    def transcribe(self, wav, language=None, beam_size=None, vad_filter=None,
                   vad_parameters=None, condition_on_previous_text=None,
                   word_timestamps=None):
        _FakeWhisperModel.son_transcribe = {"language": language, "beam": beam_size,
                                            "vad": vad_filter}
        return iter(list(self._segments)), _FakeInfo(language=language or "tr")


def _fw_fake(monkeypatch, segmentler):
    fake = types.ModuleType("faster_whisper")
    _FakeWhisperModel.kayitli_segmentler = segmentler
    _FakeWhisperModel.son_kurulum = None      # sınıf-durumu testler ARASINDA sıfırlanır
    _FakeWhisperModel.son_transcribe = None
    fake.WhisperModel = _FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    return fake


def _wav(tmp_path):
    # motor .wav girdide ffmpeg'e hiç gitmez — içerik önemsiz, var olması yeter
    w = tmp_path / "ses.wav"
    w.write_bytes(b"RIFF" + b"\x00" * 64)
    return w


def test_transkrist_uretilir(tmp_path, monkeypatch):
    _fw_fake(monkeypatch, [_FakeSeg(0.0, "Merhaba"), _FakeSeg(5.2, "dünya")])
    r = motor.calistir(_wav(tmp_path), tmp_path / "out" / "f1", {"dil": "tr"})
    assert r["durum"] == "TRANSKRIPT"
    assert r["segment_sayisi"] == 2
    assert r["dil"] == "tr"
    assert "large-v3-turbo" in _FakeWhisperModel.son_kurulum["yol"]
    t = Path(r["transkript"]["yol"]).read_text(encoding="utf-8")
    assert t.startswith("[00:00:00] Merhaba")
    assert Path(r["transkript"]["plain_yol"]).read_text(encoding="utf-8") == "Merhaba\ndünya\n"


def test_metin_yok_sessiz(tmp_path, monkeypatch):
    _fw_fake(monkeypatch, [])
    r = motor.calistir(_wav(tmp_path), tmp_path / "out" / "f2", {"dil": "tr"})
    assert r["durum"] == "METIN_YOK"
    assert r["segment_sayisi"] == 0 and r["transkript"] is None


def test_dil_desteksiz_kurtce(tmp_path, monkeypatch):
    _fw_fake(monkeypatch, [_FakeSeg(0.0, "x")])
    r = motor.calistir(_wav(tmp_path), tmp_path / "out" / "f3", {"dil": "ku"})
    assert r["durum"] == "DIL_DESTEKSIZ"
    assert r["dil"] == "ku" and r["model"] == "none"
    # model HİÇ yüklenmemeli (Kürtçe'de transkripsiyon yok — dürüst atlama)
    assert _FakeWhisperModel.son_kurulum is None
    assert not (tmp_path / "out" / "f3" / "transcript.txt").exists()


def test_yabanci_dil_large_v3_secer(tmp_path, monkeypatch):
    _fw_fake(monkeypatch, [_FakeSeg(0.0, "hello")])
    r = motor.calistir(_wav(tmp_path), tmp_path / "out" / "f4", {"dil": "en"})
    assert r["durum"] == "TRANSKRIPT"
    from pathlib import PurePath
    assert PurePath(_FakeWhisperModel.son_kurulum["yol"]).name == "large-v3"


def test_auto_dil_whisper_otespit(tmp_path, monkeypatch):
    _fw_fake(monkeypatch, [_FakeSeg(0.0, "bonjour")])
    r = motor.calistir(_wav(tmp_path), tmp_path / "out" / "f5", {"dil": "auto"})
    assert r["durum"] == "TRANSKRIPT"
    assert _FakeWhisperModel.son_transcribe["language"] is None   # whisper kendisi tespit eder
    assert r["dil"] == "tr"                                       # fake info dili


def test_girdi_yoksa_ariza(tmp_path, monkeypatch):
    _fw_fake(monkeypatch, [])
    try:
        motor.calistir(tmp_path / "yok.wav", tmp_path / "out" / "f6", {})
        assert False, "MotorArizasi beklenmisti"
    except motor.MotorArizasi as e:
        assert e.sinif == "GIRDI"


def test_model_yoksa_ariza(tmp_path, monkeypatch):
    _fw_fake(monkeypatch, [])
    try:
        motor.calistir(_wav(tmp_path), tmp_path / "out" / "f7", {"model": "bilinmeyen-model"})
        assert False, "MotorArizasi beklenmisti"
    except motor.MotorArizasi as e:
        assert e.sinif == "MODEL_YOK"
