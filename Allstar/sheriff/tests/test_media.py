from __future__ import annotations

import json
import subprocess

import pytest

from src.config import load_config
from src.media import MediaError, MediaPreparer, verify_frame_pool


def test_kisa_sessiz_turkce_video_iki_zaman_haritasi_uretir(tmp_path):
    source = tmp_path / "İlk Film.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=160x90:r=25:d=2", "-an", str(source)],
                   check=True, shell=False)
    cfg = load_config()
    result = MediaPreparer(cfg).prepare(source, tmp_path / "run")
    assert result["audio"]["status"] == "ABSENT"
    assert result["sections"]["giris"]["frame_count"] == 4
    assert result["sections"]["cikis"]["frame_count"] == 4
    opening = (tmp_path / "run/media/frames/giris/frames.jsonl").read_text(
        encoding="utf-8").splitlines()
    closing = (tmp_path / "run/media/frames/cikis/frames.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert json.loads(opening[0])["source_time_s"] == 0
    assert json.loads(closing[0])["source_time_s"] == 0
    assert json.loads(opening[-1])["width"] == 160


def test_media_restart_hash_ayniysa_yeniden_kullanir(tmp_path):
    source = tmp_path / "x.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=80x60:r=10:d=1", "-an", str(source)],
                   check=True, shell=False)
    prep = MediaPreparer(load_config())
    first = prep.prepare(source, tmp_path / "run")
    second = prep.prepare(source, tmp_path / "run")
    assert first == second


def test_bozuk_mevcut_media_manifesti_temiz_yeniden_uretilir(tmp_path):
    source = tmp_path / "x.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=80x60:r=10:d=1", "-an", str(source)],
                   check=True, shell=False)
    prep = MediaPreparer(load_config())
    prep.prepare(source, tmp_path / "run")
    manifest = tmp_path / "run/media/media.manifest.json"
    manifest.write_text("{bozuk", encoding="utf-8")
    rebuilt = prep.prepare(source, tmp_path / "run")
    assert rebuilt["source"]["sha256"]
    assert json.loads(manifest.read_text(encoding="utf-8"))["input_fingerprint"]


def test_uzun_video_240_ve_480_saniye_pencerelerini_ayri_tutar(tmp_path):
    source = tmp_path / "long.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=16x16:r=1:d=500", "-an",
                    "-c:v", "libx264", "-preset", "ultrafast", str(source)],
                   check=True, shell=False)
    result = MediaPreparer(load_config()).prepare(source, tmp_path / "run")
    assert result["sections"]["giris"]["window_start_s"] == 0
    assert result["sections"]["giris"]["window_duration_s"] == 240
    assert result["sections"]["cikis"]["window_start_s"] == 20
    assert result["sections"]["cikis"]["window_duration_s"] == 480
    assert abs(result["sections"]["giris"]["frame_count"] - 480) <= 1
    assert abs(result["sections"]["cikis"]["frame_count"] - 960) <= 1
    closing_rows = (tmp_path / "run/media/frames/cikis/frames.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert json.loads(closing_rows[0])["source_time_s"] == 20
    assert json.loads(closing_rows[1])["source_time_s"] == 20.5


def test_sesli_vfr_girdi_pcm16_mono_ve_native_frame_uretir(tmp_path):
    source = tmp_path / "vfr-audio.mkv"
    subprocess.run([
        "ffmpeg", "-y", "-nostdin", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=96x54:rate=12:d=2",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
        "-vf", "select=not(mod(n\\,3))", "-fps_mode", "vfr", "-c:v", "ffv1",
        "-c:a", "pcm_s16le", str(source)], check=True, shell=False)
    result = MediaPreparer(load_config()).prepare(source, tmp_path / "run")
    assert result["audio"]["status"] == "PRESENT"
    assert result["audio"]["sample_rate"] == 16000
    assert result["audio"]["channels"] == 1
    assert result["sections"]["giris"]["native_width"] == 96
    assert result["sections"]["giris"]["native_height"] == 54


def test_ffmpeg_yarida_kalirsa_final_media_gorunmez(tmp_path, monkeypatch):
    source = tmp_path / "x.mp4"
    source.write_bytes(b"not-important-because-probe-is-stubbed")
    prep = MediaPreparer(load_config())
    monkeypatch.setattr(prep, "probe", lambda *a, **k: {
        "duration_s": 2.0, "has_audio": False, "width": 16, "height": 16,
        "fps": "1/1", "video_codec": "fake", "pixel_format": "yuv420p",
        "streams": [], "format": {}})
    monkeypatch.setattr(prep, "_run_ffmpeg",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ffmpeg coktu")))
    with pytest.raises(RuntimeError, match="ffmpeg coktu"):
        prep.prepare(source, tmp_path / "run")
    assert not (tmp_path / "run/media").exists()


def test_frame_havuzu_manifest_sonrasi_degistirilirse_kuleye_gecmez(tmp_path):
    source = tmp_path / "x.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=80x60:r=10:d=1", "-an", str(source)],
                   check=True, shell=False)
    MediaPreparer(load_config()).prepare(source, tmp_path / "run")
    pool = tmp_path / "run/media/frames/giris"
    verify_frame_pool(pool)
    (pool / "frame_000001.png").write_bytes(b"degistirildi")
    with pytest.raises(MediaError):
        verify_frame_pool(pool)


def test_frame_manifest_sectioni_baska_bolum_olarak_degistirilemez(tmp_path):
    source = tmp_path / "x.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=80x60:r=10:d=1", "-an", str(source)],
                   check=True, shell=False)
    MediaPreparer(load_config()).prepare(source, tmp_path / "run")
    pool = tmp_path / "run/media/frames/giris"
    manifest = pool / "frames.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    rows[0]["section"] = "cikis"
    manifest.write_text("\n".join(json.dumps(row) for row in rows) + "\n",
                        encoding="utf-8")
    with pytest.raises(MediaError, match="schema/section"):
        verify_frame_pool(pool, expected_section="giris")


def test_kobe_alt_havuzu_orijinal_ve_atlamali_sequence_koruyabilir(tmp_path):
    source = tmp_path / "x.mp4"
    subprocess.run(["ffmpeg", "-y", "-nostdin", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=80x60:rate=4:duration=1", "-an", str(source)],
                   check=True, shell=False)
    MediaPreparer(load_config()).prepare(source, tmp_path / "run")
    pool = tmp_path / "run/media/frames/giris"
    rows = [json.loads(line) for line in (pool / "frames.jsonl").read_text(
        encoding="utf-8").splitlines()]
    (pool / rows[0]["filename"]).unlink()
    (pool / "frames.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows[1:]) + "\n", encoding="utf-8")
    with pytest.raises(MediaError, match="sequence"):
        verify_frame_pool(pool, expected_section="giris")
    verify_frame_pool(pool, expected_section="giris",
                      require_contiguous_sequence=False)
