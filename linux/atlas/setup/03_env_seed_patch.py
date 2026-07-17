#!/usr/bin/env python3
"""ATLAS Faz C kod-fix: env-tohum + platform-dal yamalari (davranis-notr).
00_ATLAS_TASIMA_PLANI.md sS 3-B/C/D. Calisir: /opt/atlas icinde (ATLAS WSL distro).
Idempotent: her yama zaten uygulanmissa atlar; OLD bulunamazsa HATA basar (elle bak).
"""
from __future__ import annotations

ROOT = "/opt/atlas"
applied: list[str] = []
skipped: list[str] = []
errors: list[str] = []


def patch(relpath: str, old: str, new: str, *, marker: str | None = None):
    path = f"{ROOT}/{relpath}"
    with open(path, encoding="utf-8") as f:
        src = f.read()
    check = marker or new
    if check in src:
        skipped.append(f"{relpath} ({check[:40]!r})")
        return
    if old not in src:
        errors.append(f"{relpath}: OLD bulunamadi -> {old[:60]!r}")
        return
    src = src.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    applied.append(relpath)


# ═══ B/C: process_clip.py (ffmpeg env-tohum + venv-python platform-dal) ══════
patch(
    "scripts/process_clip.py",
    "import argparse\nimport json\nimport subprocess\n",
    "import argparse\nimport json\nimport os\nimport subprocess\n",
    marker="import json\nimport os\nimport subprocess",
)
patch(
    "scripts/process_clip.py",
    'FFMPEG_EXE = (\n'
    '    ATLAS_ROOT / "tools" / "ffmpeg-shared"\n'
    '    / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"\n'
    ')\n\n'
    'OCR_PY  = str(VENVS / "ocr"  / "Scripts" / "python.exe")\n'
    'ASR_PY  = str(VENVS / "asr"  / "Scripts" / "python.exe")\n'
    'CORE_PY = str(VENVS / "core" / "Scripts" / "python.exe")\n'
    'FACE_PY   = str(VENVS / "face"   / "Scripts" / "python.exe")\n'
    'VISUAL_PY = str(VENVS / "visual" / "Scripts" / "python.exe")\n'
    'NLP_PY    = str(VENVS / "nlp"    / "Scripts" / "python.exe")\n',

    'FFMPEG_EXE = os.environ.get("ATLAS_FFMPEG") or str(\n'
    '    ATLAS_ROOT / "tools" / "ffmpeg-shared"\n'
    '    / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"\n'
    ')\n\n\n'
    'def _venv_py(profile: str) -> str:\n'
    '    """Profil venv python yorumlayicisi (platform-dal: Win Scripts/, *nix bin/)."""\n'
    '    sub = "Scripts/python.exe" if os.name == "nt" else "bin/python"\n'
    '    return str(VENVS / profile / sub)\n\n\n'
    'OCR_PY    = _venv_py("ocr")\n'
    'ASR_PY    = _venv_py("asr")\n'
    'CORE_PY   = _venv_py("core")\n'
    'FACE_PY   = _venv_py("face")\n'
    'VISUAL_PY = _venv_py("visual")\n'
    'NLP_PY    = _venv_py("nlp")\n',
    marker="def _venv_py(profile: str) -> str:",
)

# ═══ B: make_proxy.py (ffmpeg) ═══════════════════════════════════════════════
patch(
    "scripts/make_proxy.py",
    "import argparse\nimport subprocess\nimport sys\nimport time\nfrom pathlib import Path\n",
    "import argparse\nimport os\nimport subprocess\nimport sys\nimport time\nfrom pathlib import Path\n",
    marker="import argparse\nimport os\nimport subprocess",
)
patch(
    "scripts/make_proxy.py",
    'FFMPEG_EXE = (\n'
    '    ATLAS_ROOT / "tools" / "ffmpeg-shared"\n'
    '    / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"\n'
    ')\n',
    'FFMPEG_EXE = os.environ.get("ATLAS_FFMPEG") or str(\n'
    '    ATLAS_ROOT / "tools" / "ffmpeg-shared"\n'
    '    / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"\n'
    ')\n',
)

# ═══ B: segment_stories.py (ffmpeg) ══════════════════════════════════════════
patch(
    "scripts/segment_stories.py",
    "import argparse\nimport io\nimport json\nimport subprocess\nimport sys\n",
    "import argparse\nimport io\nimport json\nimport os\nimport subprocess\nimport sys\n",
    marker="import json\nimport os\nimport subprocess\nimport sys",
)
patch(
    "scripts/segment_stories.py",
    'FFMPEG_EXE = (\n'
    '    ATLAS_ROOT / "tools" / "ffmpeg-shared"\n'
    '    / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"\n'
    ')\n',
    'FFMPEG_EXE = os.environ.get("ATLAS_FFMPEG") or str(\n'
    '    ATLAS_ROOT / "tools" / "ffmpeg-shared"\n'
    '    / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"\n'
    ')\n',
)

# ═══ B: jenerik_discover.py (ffmpeg; os zaten import edilmis) ════════════════
patch(
    "scripts/jenerik_discover.py",
    'FFBIN = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin"\n'
    'FFMPEG = FFBIN / "ffmpeg.exe"\n',
    '_ffmpeg_env = os.environ.get("ATLAS_FFMPEG")\n'
    'if _ffmpeg_env:\n'
    '    FFMPEG = Path(_ffmpeg_env)\n'
    '    FFBIN = FFMPEG.parent\n'
    'else:\n'
    '    FFBIN = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin"\n'
    '    FFMPEG = FFBIN / "ffmpeg.exe"\n',
    marker="_ffmpeg_env = os.environ.get",
)

# ═══ B/D: vlm_arbiter.py (ffmpeg default + ollama url; os zaten import) ══════
patch(
    "src/atlas/segment/vlm_arbiter.py",
    'FFMPEG_DEFAULT = (\n'
    '    r"E:\\ATLAS\\tools\\ffmpeg-shared\\ffmpeg-8.1.1-full_build-shared\\bin\\ffmpeg.exe"\n'
    ')\n'
    'OLLAMA_URL = "http://127.0.0.1:11434/api/chat"\n',
    'FFMPEG_DEFAULT = os.environ.get("ATLAS_FFMPEG") or (\n'
    '    r"E:\\ATLAS\\tools\\ffmpeg-shared\\ffmpeg-8.1.1-full_build-shared\\bin\\ffmpeg.exe"\n'
    ')\n'
    'OLLAMA_URL = os.environ.get("ATLAS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/chat"\n',
)

# ═══ C: search_server.py (venv python platform-dal; os zaten import) ════════
patch(
    "scripts/search_server.py",
    'CORE_PY = str(PROJECT_ROOT / "venvs" / "core" / "Scripts" / "python.exe")\n',
    'CORE_PY = str(PROJECT_ROOT / "venvs" / "core" /\n'
    '              ("Scripts/python.exe" if os.name == "nt" else "bin/python"))\n',
)
# retag.py: zaten .exists() fallback'li -> SORUNSUZ, dokunulmadi (plan sS3-C).

# ═══ D: Ollama host default'lari -> ATLAS_OLLAMA_URL (model adlari AYNEN) ════
patch(
    "src/atlas/llm/ollama_client.py",
    "import json\nimport urllib.request\nfrom typing import Any\n",
    "import json\nimport os\nimport urllib.request\nfrom typing import Any\n",
    marker="import json\nimport os\nimport urllib.request",
)
patch(
    "src/atlas/llm/ollama_client.py",
    '        model: str = "qwen35-35b-test",\n'
    '        host: str = "http://localhost:11434",\n',
    '        model: str = "qwen35-35b-test",\n'
    '        host: str = os.environ.get("ATLAS_OLLAMA_URL", "http://localhost:11434"),\n',
)

patch(
    "src/atlas/llm/embed.py",
    "import json\nimport sys\nimport time\nimport urllib.request\nfrom typing import TYPE_CHECKING\n",
    "import json\nimport os\nimport sys\nimport time\nimport urllib.request\nfrom typing import TYPE_CHECKING\n",
    marker="import json\nimport os\nimport sys\nimport time\nimport urllib.request",
)
patch(
    "src/atlas/llm/embed.py",
    '    model: str = "bge-m3:atlas1",\n'
    '    host: str = "http://localhost:11434",\n',
    '    model: str = "bge-m3:atlas1",\n'
    '    host: str = os.environ.get("ATLAS_OLLAMA_URL", "http://localhost:11434"),\n',
)

patch(
    "src/atlas/llm/vlm_ocr.py",
    "import base64\nimport json\nimport urllib.request\nfrom pathlib import Path\n",
    "import base64\nimport json\nimport os\nimport urllib.request\nfrom pathlib import Path\n",
    marker="import json\nimport os\nimport urllib.request\nfrom pathlib import Path",
)
patch(
    "src/atlas/llm/vlm_ocr.py",
    '    model: str = "glm-ocr:atlas1",\n'
    '    prompt: str = "Bu görüntüdeki tüm metni oku, aynen yaz.",\n'
    '    host: str = "http://localhost:11434",\n',
    '    model: str = "glm-ocr:atlas1",\n'
    '    prompt: str = "Bu görüntüdeki tüm metni oku, aynen yaz.",\n'
    '    host: str = os.environ.get("ATLAS_OLLAMA_URL", "http://localhost:11434"),\n',
)

# jenerik.py: load_cfg cfg.update(data) SONRASI host'u env ile override et
patch(
    "src/atlas/analyze/jenerik.py",
    "import json\nimport re\nimport sys\nimport time\nfrom pathlib import Path\n",
    "import json\nimport os\nimport re\nimport sys\nimport time\nfrom pathlib import Path\n",
    marker="import json\nimport os\nimport re\nimport sys\nimport time",
)
patch(
    "src/atlas/analyze/jenerik.py",
    '    elif channels:\n'
    '        log(f"[jenerik] UYARI: \'{channel}\' kanalı için sözlük YOK "\n'
    '            f"(tanımlı: {list(channels)}) -> marka/program tespiti kısıtlı (yalnız rol kalıpları)")\n'
    '    return cfg\n',
    '    elif channels:\n'
    '        log(f"[jenerik] UYARI: \'{channel}\' kanalı için sözlük YOK "\n'
    '            f"(tanımlı: {list(channels)}) -> marka/program tespiti kısıtlı (yalnız rol kalıpları)")\n'
    '    _atlas_url = os.environ.get("ATLAS_OLLAMA_URL")\n'
    '    if _atlas_url:\n'
    '        cfg["host"] = _atlas_url\n'
    '    return cfg\n',
    marker='_atlas_url = os.environ.get("ATLAS_OLLAMA_URL")\n    if _atlas_url:\n        cfg["host"]',
)

# layer_a.py: load_cfg icinde host override
patch(
    "src/atlas/analyze/layer_a.py",
    "import json\nimport re\nimport sys\nimport time\nfrom collections import Counter\n",
    "import json\nimport os\nimport re\nimport sys\nimport time\nfrom collections import Counter\n",
    marker="import json\nimport os\nimport re\nimport sys\nimport time\nfrom collections import Counter",
)
patch(
    "src/atlas/analyze/layer_a.py",
    "def load_cfg(path: Path | None) -> dict:\n"
    "    cfg = dict(_DEF_CFG)\n"
    "    if path and path.exists():\n"
    "        import yaml  # type: ignore\n"
    "        cfg.update(yaml.safe_load(path.read_text(encoding=\"utf-8\")) or {})\n"
    "    return cfg\n",
    "def load_cfg(path: Path | None) -> dict:\n"
    "    cfg = dict(_DEF_CFG)\n"
    "    if path and path.exists():\n"
    "        import yaml  # type: ignore\n"
    "        cfg.update(yaml.safe_load(path.read_text(encoding=\"utf-8\")) or {})\n"
    "    _atlas_url = os.environ.get(\"ATLAS_OLLAMA_URL\")\n"
    "    if _atlas_url:\n"
    "        cfg[\"host\"] = _atlas_url\n"
    "    return cfg\n",
)

# production_type.py: load_cfg icinde nested canli.ocr_host override
patch(
    "src/atlas/visual/production_type.py",
    "import json\nimport sys\nimport time\nfrom collections import Counter\n",
    "import json\nimport os\nimport sys\nimport time\nfrom collections import Counter\n",
    marker="import json\nimport os\nimport sys\nimport time\nfrom collections import Counter",
)
patch(
    "src/atlas/visual/production_type.py",
    "            loaded = yaml.safe_load(Path(p).read_text(encoding=\"utf-8\")) or {}\n"
    "            cfg = _deep_merge(cfg, loaded)\n"
    "        except ImportError:\n"
    "            pass\n"
    "    return cfg\n",
    "            loaded = yaml.safe_load(Path(p).read_text(encoding=\"utf-8\")) or {}\n"
    "            cfg = _deep_merge(cfg, loaded)\n"
    "        except ImportError:\n"
    "            pass\n"
    "    _atlas_url = os.environ.get(\"ATLAS_OLLAMA_URL\")\n"
    "    if _atlas_url and isinstance(cfg.get(\"canli\"), dict):\n"
    "        cfg[\"canli\"][\"ocr_host\"] = _atlas_url\n"
    "    return cfg\n",
)

# enrich_event_tags.py: fonksiyon + argparse default
patch(
    "scripts/enrich_event_tags.py",
    "import argparse\nimport json\nimport sys\n",
    "import argparse\nimport json\nimport os\nimport sys\n",
    marker="import argparse\nimport json\nimport os\nimport sys",
)
patch(
    "scripts/enrich_event_tags.py",
    '    dry_run: bool = False,\n'
    '    host: str = "http://localhost:11434",\n'
    ') -> dict:',
    '    dry_run: bool = False,\n'
    '    host: str = os.environ.get("ATLAS_OLLAMA_URL", "http://localhost:11434"),\n'
    ') -> dict:',
)
patch(
    "scripts/enrich_event_tags.py",
    'ap.add_argument("--host", default="http://localhost:11434", help="Ollama host")',
    'ap.add_argument("--host", default=os.environ.get("ATLAS_OLLAMA_URL", "http://localhost:11434"), help="Ollama host")',
)

# enrich_facets.py: fonksiyon + argparse default
patch(
    "scripts/enrich_facets.py",
    "import argparse\nimport json\nimport sys\nfrom pathlib import Path\n",
    "import argparse\nimport json\nimport os\nimport sys\nfrom pathlib import Path\n",
    marker="import argparse\nimport json\nimport os\nimport sys\nfrom pathlib import Path",
)
patch(
    "scripts/enrich_facets.py",
    '    dry_run: bool = False,\n'
    '    host: str = "http://localhost:11434",\n'
    '    tail_trim: bool = True,\n',
    '    dry_run: bool = False,\n'
    '    host: str = os.environ.get("ATLAS_OLLAMA_URL", "http://localhost:11434"),\n'
    '    tail_trim: bool = True,\n',
)
patch(
    "scripts/enrich_facets.py",
    'ap.add_argument("--host", default="http://localhost:11434", help="Ollama host")',
    'ap.add_argument("--host", default=os.environ.get("ATLAS_OLLAMA_URL", "http://localhost:11434"), help="Ollama host")',
)

print(f"UYGULANDI ({len(applied)}):")
for a in applied:
    print(f"  + {a}")
print(f"ATLANDI/zaten-yamali ({len(skipped)}):")
for s in skipped:
    print(f"  = {s}")
print(f"HATA ({len(errors)}):")
for e in errors:
    print(f"  ! {e}")
if errors:
    raise SystemExit(1)
print("ENV_SEED_PATCH_DONE_OK")
