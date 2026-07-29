# -*- coding: utf-8 -*-
"""mitas_guard PreToolUse hook testleri.

2026-07-29: git clean -fdx'in 1.1 TB'ı (models/ 587G, Mitas_Files/ 157G,
Database/ 119G, venvs/ 105G, mitas.env) sildiği tespit edildi; mevcut regex
\\b(rm|rmdir|shred)\\b onu yakalamıyordu. Ayrıca git gc/repack, dal ile
kurtarılmış 3 yetim commit'i yok ediyordu."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "mitas_guard.py"


def _cagir(tool, tool_input, cwd="/opt/mitas"):
    girdi = json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": cwd})
    p = subprocess.run([sys.executable, str(HOOK)], input=girdi,
                       capture_output=True, text=True, timeout=15)
    assert p.returncode == 0, f"hook exit {p.returncode}: {p.stderr}"
    if not p.stdout.strip():
        return None  # sessiz geçiş = izin
    return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize("cmd", [
    "git clean -fdx",
    "git clean -xdf",
    "cd /opt/mitas && git clean -fdX",
    "git clean --force -d -x",
    "git -C /opt/mitas clean -fdx",
])
def test_git_clean_x_reddedilir(cmd):
    """git clean -x/-X ignore'lu her şeyi siler: models/, Database/, mitas.env dahil."""
    assert _cagir("Bash", {"command": cmd}) == "deny", f"YAKALANMADI: {cmd}"


@pytest.mark.parametrize("cmd", [
    "git gc",
    "git gc --prune=now",
    "git gc --aggressive",
    "git repack -ad",
])
def test_git_gc_reddedilir(cmd):
    """gc/repack, kurtarma/* dallarıyla korunan yetim commit'leri yeniden paketlerken atar."""
    assert _cagir("Bash", {"command": cmd}) == "deny", f"YAKALANMADI: {cmd}"


@pytest.mark.parametrize("cmd", [
    "git clean -nd",
    "git clean -ndx",
    "git clean --dry-run -fdx",
    "git prune --dry-run",
    "git status",
    "git log --oneline -5",
    "ls -la",
])
def test_zararsiz_komutlar_gecer(cmd):
    """Kuru koşu ve okuma komutları engellenmemeli — guard iş akışını kilitlememeli."""
    assert _cagir("Bash", {"command": cmd}) is None, f"YANLIŞ ENGEL: {cmd}"


def test_uretim_kokunde_rm_hala_reddedilir():
    """Mevcut koruma bozulmamalı (regresyon)."""
    assert _cagir("Bash", {"command": "rm -rf /opt/mitas/Database/foo"}) == "deny"


def test_karantina_koku_de_korunur():
    """Taşınan veri kaynağı kadar korunmalı — KARANTINA/arsiv PROD_ROOTS'a girdi."""
    assert _cagir("Bash", {"command": "rm -rf KARANTINA_2026-07-29/venvs"}) == "deny"
    assert _cagir("Bash", {"command": "rm -rf /opt/mitas/arsiv/mutfak"}) == "deny"


def test_kilitli_dosya_ask_uretir():
    """Regresyon: LOCKED davranışı bozulmamalı."""
    assert _cagir("Edit", {"file_path": "/opt/mitas/scripts/mitas_roots.py"}) == "ask"


def test_env_okuma_reddedilir():
    """Regresyon: anahtar sızıntısı koruması bozulmamalı."""
    assert _cagir("Read", {"file_path": "/opt/mitas/mitas.env"}) == "deny"
