from __future__ import annotations

from pathlib import Path

from core.pipelines.asr import normalize


def test_resolve_project_root_prefers_explicit_env(monkeypatch, tmp_path: Path) -> None:
    configured_root = tmp_path / "project"
    monkeypatch.setenv("MITAS_PROJECT_ROOT", str(configured_root))

    assert normalize._resolve_project_root() == configured_root


def test_resolve_project_root_climbs_from_worktree_to_model_root(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "models" / "asr" / "faster-whisper").mkdir(parents=True)
    fake_module = project_root / ".claude" / "worktrees" / "case" / "core" / "pipelines" / "asr" / "normalize.py"

    monkeypatch.delenv("MITAS_PROJECT_ROOT", raising=False)
    monkeypatch.setattr(normalize, "__file__", str(fake_module))

    assert normalize._resolve_project_root() == project_root
