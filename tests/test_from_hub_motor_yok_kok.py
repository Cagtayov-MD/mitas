# -*- coding: utf-8 -*-
"""test_from_hub_motor_yok_kok.py — from-hub sahte-MOTOR_YOK kök-sebep zinciri regresyon testleri.

Kanıt (2026-07-30): candidate_runs/fitz_dogrulama/.../YAĞMACILAR .../ocr/ altında iki run —
GUVENILIR hub-kopyası (ocr-427199b1, 42 satır) ve MOTOR_YOK candidate re-OCR (ocr-4ec119de,
0 satır, "No module named 'core'") — sahte 'Kontrol' kararı. Üç katmanlı defect:

  A) from-hub GÖRELİ ``--from-hub`` → os.symlink göreli hedef → dangling → 0 kare
     (mitas_pipeline: _link_hub_frames helper'ı mutlak hedefli link üretmeli)
  B) _pipe_credit_text._find_ocr en-yeni mtime'ı seçer, BOŞ/MOTOR_YOK/-fb elemez → iyi veriyi
     gölgeler (frames_rerun.py:87-88 zaten st_size>0 + -fb eler; üretim karar-okuyucusu elemiyordu)
  C) _pipe_ocr 0-kare → run_pipeline100 atlanır → build_engine core importu path'te core yokken
     patlar → MOTOR_YOK (motor yüklenebilse 0-kare BOS olurdu)
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pct = _load("pct_kok", "_pipe_credit_text.py")
roots = _load("roots_kok", "mitas_roots.py")  # saf modül: ağır import yok, güvenle yüklenir


def _mk_ocr(clip, name, kunye_text, bucket, mtime):
    """clip/ocr/<name>/ altında kunye.txt + ocr_summary.json üret, mtime damgala. kunye yolunu döndür."""
    d = clip / "ocr" / name
    d.mkdir(parents=True)
    kp = d / "kunye.txt"
    kp.write_text(kunye_text, encoding="utf-8")
    (d / "ocr_summary.json").write_text(json.dumps({"bucket": bucket}), encoding="utf-8")
    os.utime(kp, (mtime, mtime))
    return kp


# ── Defect B: _find_ocr BOŞ/MOTOR_YOK dizini GÖLGELETMEMELİ ──────────────────

def test_find_ocr_prefers_guvenilir_over_newer_motor_yok(tmp_path):
    """Reprodüksiyon: eski GUVENILIR(42) + yeni MOTOR_YOK(boş) → GUVENILIR seçilmeli."""
    clip = tmp_path / "YAGMACILAR"
    good = _mk_ocr(clip, "ocr-427199b1", "YÖNETMEN AHMET\n" * 42, "GUVENILIR", 1000)
    _mk_ocr(clip, "ocr-4ec119de", "", "MOTOR_YOK", 2000)  # daha yeni ama boş + MOTOR_YOK
    assert pct._find_ocr(str(clip)) == str(good)


def test_find_ocr_skips_empty_kunye_even_without_summary(tmp_path):
    """Summary yoksa bile boş kunye.txt (0 bayt) elenmeli — non-boş eskiye düş."""
    clip = tmp_path / "X"
    good = _mk_ocr(clip, "ocr-aaa", "İSİM BİR\nİSİM İKİ\n", "GUVENILIR", 1000)
    d = clip / "ocr" / "ocr-bbb"
    d.mkdir(parents=True)
    kp = d / "kunye.txt"
    kp.write_text("", encoding="utf-8")  # summary YOK, boş dosya
    os.utime(kp, (2000, 2000))
    assert pct._find_ocr(str(clip)) == str(good)


def test_find_ocr_skips_fb_sibling(tmp_path):
    """-fb (fallback) kardeş dizin otoriter kunye sayılmaz (frames_rerun.py:88 deseni)."""
    clip = tmp_path / "Y"
    good = _mk_ocr(clip, "ocr-ccc", "AD SOYAD\n", "GUVENILIR", 1000)
    _mk_ocr(clip, "ocr-ccc-fb", "GARBLE\n", "GUVENILIR", 3000)  # -fb, daha yeni
    assert pct._find_ocr(str(clip)) == str(good)


def test_find_ocr_falls_back_to_newest_when_all_bad(tmp_path):
    """Hepsi boş/MOTOR_YOK ise None DEĞİL, en-yeniye düş (eski davranış korunur, regresyon yok)."""
    clip = tmp_path / "Z"
    _mk_ocr(clip, "ocr-old", "", "MOTOR_YOK", 1000)
    newest = _mk_ocr(clip, "ocr-new", "", "MOTOR_YOK", 2000)
    assert pct._find_ocr(str(clip)) == str(newest)


def test_find_ocr_none_when_no_ocr(tmp_path):
    """Hiç ocr dizini yoksa None (mevcut sözleşme korunur)."""
    clip = tmp_path / "empty"
    (clip / "ocr").mkdir(parents=True)
    assert pct._find_ocr(str(clip)) is None


# ── Defect A: from-hub GÖRELİ --from-hub → symlink MUTLAK hedefli, dangling DEĞİL ────

def _mk_hub(tmp_path, name="FILM"):
    hub = tmp_path / "Database" / name
    for fd in ("giris", "cikis"):
        (hub / "frames" / fd).mkdir(parents=True)
        (hub / "frames" / fd / "0001.png").write_bytes(b"\x89PNG\r\n")
    return hub


def test_link_hub_frames_absolute_target_when_relative_from_hub(tmp_path, monkeypatch):
    """Reprodüksiyon: göreli ``--from-hub`` verilince symlink hedefi MUTLAK olmalı; aksi halde
    link kendi dizinine göre çözülüp DANGLING olur → 0 kare → sahte-MOTOR_YOK (fitz_dogrulama)."""
    _mk_hub(tmp_path)
    clip = tmp_path / "candidate" / "Database" / "FILM"
    (clip / "frames").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)  # cwd=tmp_path → --from-hub GÖRELİ "Database/FILM"

    roots.link_hub_frames(os.path.join("Database", "FILM"), str(clip))

    link = clip / "frames" / "giris"
    assert link.is_symlink(), "giris symlink olarak kurulmadı"
    assert os.path.exists(link), "symlink DANGLING (göreli hedef) — kök-sebep geri geldi"
    assert len(list(link.glob("*.png"))) == 1, "hub kareleri link üzerinden görülemiyor"
    assert os.path.isabs(os.readlink(link)), "symlink hedefi mutlak değil (göreli = kırılgan)"


def test_link_hub_frames_idempotent(tmp_path, monkeypatch):
    """İkinci çağrı mevcut linki bozmamalı (not _dst.exists() koruması)."""
    _mk_hub(tmp_path)
    clip = tmp_path / "cand" / "Database" / "FILM"
    (clip / "frames").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    roots.link_hub_frames("Database/FILM", str(clip))
    roots.link_hub_frames("Database/FILM", str(clip))  # ikinci kez — patlamamalı
    assert os.path.exists(clip / "frames" / "cikis")
    assert len(list((clip / "frames" / "cikis").glob("*.png"))) == 1


# ── Defect C1: fallback build_engine core'u bulabilmeli (PROJECT_ROOT path'e eklenmeli) ──

def test_ensure_project_root_on_path_adds_root(monkeypatch, tmp_path):
    """EK_TAKS-sınıfı: pipeline100 atlanınca/patlayınca build_engine paddle core'u aramalı.
    core yalnız pipeline100 zincirinin YAN-ETKİSİYLE path'e giriyordu; deterministik olmalı."""
    po = _load("pipeocr_c1", "_pipe_ocr.py")
    assert hasattr(po, "_ensure_project_root_on_path"), "C1 helper yok"
    monkeypatch.setenv("MITAS_PROJECT_ROOT", str(tmp_path))
    saved = list(sys.path)
    try:
        while str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))
        po._ensure_project_root_on_path()
        assert str(tmp_path) in sys.path, "PROJECT_ROOT sys.path'e eklenmedi → core bulunamaz"
    finally:
        sys.path[:] = saved


# ── Defect C2: 0-kare → BOS (MOTOR_YOK DEĞİL) ────────────────────────────────

def test_pipe_ocr_zero_frames_is_bos_not_motor_yok(tmp_path):
    """0 kare (footage/boş dizin) → BOS; MOTOR_YOK sahte-kırmızısı DEĞİL.
    Reprodüksiyon: 0-kare run_pipeline100'ü atlar → run_oneocr_fallback build_engine çağırır →
    Linux'ta core path'te yok → paddle patlar → MOTOR_YOK (byte-aynı: ocr-4ec119de)."""
    import subprocess as _sp
    py_ocr = "/opt/mitas/venvs/ocr/bin/python"
    if not os.path.exists(py_ocr):
        import pytest
        pytest.skip("OCR venv yok (CI)")
    empty = tmp_path / "bos_kareler"
    empty.mkdir()
    out = tmp_path / "ocr_out"
    _sp.run([py_ocr, os.path.join(SCRIPTS, "_pipe_ocr.py"), "--frames", str(empty), "--out", str(out)],
            capture_output=True, text=True, timeout=180)
    summary = json.load(open(out / "ocr_summary.json", encoding="utf-8"))
    assert summary["frame_count"] == 0
    assert summary["bucket"] == "BOS", \
        f"0-kare BOS olmalı, alınan: {summary['bucket']} / {summary.get('engine_error')}"


# ── Q1: from-hub varsayılan REUSE + --force-ocr (canonical selector: find_usable_ocr) ──

def test_find_usable_ocr_returns_none_when_all_bad(tmp_path):
    """Kullanılabilir OCR yoksa None (reuse-kapısı: None → taze OCR koş)."""
    clip = tmp_path / "c"
    _mk_ocr(clip, "ocr-a", "", "MOTOR_YOK", 1000)
    _mk_ocr(clip, "ocr-b", "", "BOS", 2000)  # boş
    assert roots.find_usable_ocr(str(clip)) is None


def test_find_usable_ocr_returns_newest_usable(tmp_path):
    """GOZDEN_GECIR de gerçek okumadır (yalnız BOŞ/MOTOR_YOK/-fb elenir) → en-yeni kullanılabilir."""
    clip = tmp_path / "c2"
    _mk_ocr(clip, "ocr-old", "AD\n", "GUVENILIR", 1000)
    newest = _mk_ocr(clip, "ocr-new", "AD SOYAD\n", "GOZDEN_GECIR", 2000)
    assert roots.find_usable_ocr(str(clip)) == str(newest)


def test_should_reuse_true_when_from_hub_and_usable_copy(tmp_path):
    """from-hub + --force-ocr YOK + kullanılabilir kopya → taze OCR KOŞMA (hub GUVENILIR'i kullan)."""
    clip = tmp_path / "clip"
    _mk_ocr(clip, "ocr-427199b1", "YÖNETMEN\n" * 10, "GUVENILIR", 1000)
    assert roots.should_reuse_hub_ocr("Database/FILM", False, str(clip)) is True


def test_should_reuse_false_when_force_ocr(tmp_path):
    """--force-ocr → taze OCR koş (kullanıcı OCR değişikliğini test ediyor)."""
    clip = tmp_path / "clip"
    _mk_ocr(clip, "ocr-427199b1", "YÖNETMEN\n" * 10, "GUVENILIR", 1000)
    assert roots.should_reuse_hub_ocr("Database/FILM", True, str(clip)) is False


def test_should_reuse_false_when_not_from_hub(tmp_path):
    """Normal (from-hub olmayan) üretim koşusu reuse YAPMAZ — daima taze OCR."""
    clip = tmp_path / "clip"
    _mk_ocr(clip, "ocr-x", "AD\n", "GUVENILIR", 1000)
    assert roots.should_reuse_hub_ocr(None, False, str(clip)) is False


def test_should_reuse_false_when_no_usable_copy(tmp_path):
    """Kopya bozuk/boş/MOTOR_YOK ise reuse etme — taze OCR koş (fail-safe)."""
    clip = tmp_path / "clip"
    _mk_ocr(clip, "ocr-x", "", "MOTOR_YOK", 1000)
    assert roots.should_reuse_hub_ocr("Database/FILM", False, str(clip)) is False
