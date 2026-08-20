"""LeBron-owned private Ollama adapter for the locked DeepSeek-OCR GGUF.

The public boundary stays ``yukle(settings, tower) -> ask(path, prompt=None)``.
No request is ever sent to the machine-wide Ollama service: this module owns a
loopback server, its model store, logs, lifetime and descendants.
"""
from __future__ import annotations

import atexit
import base64
import hashlib
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

import psutil
import requests

from okuyucu import Bellek, ModelYok

_VERIFIED: set[Path] = set()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_sha256(root: Path) -> str:
    """Digest compatible with the lock's sorted ``sha256sum`` tree."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*")
                       if p.is_file() and not p.is_symlink()):
        rel = path.relative_to(root).as_posix()
        digest.update(f"{_sha256(path)}  {rel}\n".encode())
    return digest.hexdigest()


def _resolve(base: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else base / path


def _verify_install(tower: Path, settings: dict) -> tuple[Path, Path, Path, str]:
    lock_path = tower / "model.lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ModelYok(f"model kilidi okunamadi: {type(exc).__name__}: {exc}") from exc

    runtime = _resolve(tower, str(settings.get(
        "ollama_runtime", "model/ollama-runtime")))
    binary = runtime / "bin/ollama"
    library = runtime / "lib/ollama"
    store = _resolve(tower, str(settings.get("ollama_store", "model/ollama")))
    manifest = store / "manifests/registry.ollama.ai/library/deepseek-ocr/latest"
    missing = [str(path) for path in (lock_path, binary, manifest)
               if not path.is_file()]
    if not library.is_dir():
        missing.append(str(library))
    if missing:
        raise ModelYok("yerel Ollama kurulumu eksik: " + ", ".join(missing)
                       + " — ./model_kur.sh calistirin")

    # The large tree is hashed once per CLI process, never once per band.
    key = lock_path.resolve()
    if key not in _VERIFIED:
        checks = [
            ("ollama binary", _sha256(binary), lock["ollama_binary_sha256"]),
            ("ollama library", _tree_sha256(library),
             lock["ollama_library_tree_sha256"]),
            ("model manifest", _sha256(manifest), lock["manifest_sha256"]),
        ]
        for blob in lock.get("blobs") or []:
            digest = str(blob["sha256"])
            path = store / "blobs" / f"sha256-{digest}"
            if not path.is_file():
                raise ModelYok(f"model blobu yok: {path}")
            if path.stat().st_size != int(blob["size"]):
                raise ModelYok(f"model blob boyutu uyusmuyor: {path.name}")
            checks.append((f"blob {blob.get('kind', '')}", _sha256(path), digest))
        bad = [f"{name}: {actual} != {expected}"
               for name, actual, expected in checks if actual != expected]
        if bad:
            raise ModelYok("yerel Ollama kilidi uyusmuyor: " + "; ".join(bad))
        _VERIFIED.add(key)
    return binary, library, store, str(lock["model"])


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class PrivateOllama:
    # DeepSeek-OCR'ın bu yerel Ollama yolu görüntü-geneli ``image[[...]]``
    # döndürebilir; güvenilir satır/ref/det grounding yeteneği sunmaz.
    line_grounding_supported = False

    def __init__(self, settings: dict, tower: Path) -> None:
        self.settings = dict(settings)
        self.tower = Path(tower)
        self.binary, self.library, self.store, self.model = _verify_install(
            self.tower, self.settings)
        self.process: subprocess.Popen | None = None
        self.process_created: float | None = None
        self.port: int | None = None
        self.base_url = ""
        self.log_handle = None
        self.session = requests.Session()
        self.session.trust_env = False
        self.call_count = 0
        self.call_seconds = 0.0
        self.max_call_seconds = 0.0
        self.warmup_seconds = 0.0
        self.peak_vram_mb = 0.0
        self._monitor_stop = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._closed = False
        self._start()
        atexit.register(self.close)

    def _environment(self, port: int) -> dict[str, str]:
        env = dict(os.environ)
        env.update({
            "OLLAMA_HOST": f"127.0.0.1:{port}",
            "OLLAMA_MODELS": str(self.store),
            "OLLAMA_NO_CLOUD": "1",
            "OLLAMA_MAX_LOADED_MODELS": "1",
            "OLLAMA_NUM_PARALLEL": "1",
            "OLLAMA_MAX_QUEUE": "1",
            "OLLAMA_LIBRARY_PATH": str(self.library),
            "OLLAMA_NOPRUNE": "1",
        })
        # HOME is deliberately untouched: OLLAMA_NO_CLOUD must prevent key state.
        return env

    def _start(self) -> None:
        log_dir = self.tower / "scratch/ollama"
        log_dir.mkdir(parents=True, exist_ok=True)
        private_home = log_dir / "home"
        private_home.mkdir(parents=True, exist_ok=True)
        host_ollama_home = Path(self.settings.get(
            "_host_ollama_home", Path.home() / ".ollama"))
        if not host_ollama_home.is_dir():
            raise ModelYok(f"bubblewrap hedefi yok: {host_ollama_home}")
        bubblewrap = Path("/usr/bin/bwrap")
        if not bubblewrap.is_file():
            raise ModelYok("bubblewrap yok: /usr/bin/bwrap")
        last_error = ""
        for attempt in range(1, 6):
            port = _free_port()
            log_path = log_dir / f"private-{os.getpid()}-{attempt}.log"
            self.log_handle = log_path.open("ab", buffering=0)
            try:
                command = [
                    str(bubblewrap), "--die-with-parent", "--ro-bind", "/", "/",
                    "--dev-bind", "/dev", "/dev", "--proc", "/proc",
                    "--bind", str(private_home), str(host_ollama_home),
                    "--chdir", str(self.tower), str(self.binary), "serve",
                ]
                process = subprocess.Popen(
                    command, cwd=self.tower,
                    env=self._environment(port), stdin=subprocess.DEVNULL,
                    stdout=self.log_handle, stderr=subprocess.STDOUT,
                    close_fds=True, start_new_session=False)
                self.process = process
                self.process_created = psutil.Process(process.pid).create_time()
                self.port = port
                self.base_url = f"http://127.0.0.1:{port}"
                deadline = time.monotonic() + 20.0
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise ModelYok(f"ozel Ollama erken kapandi rc={process.returncode}")
                    try:
                        response = self.session.get(self.base_url + "/api/version", timeout=1)
                        if response.ok:
                            break
                    except requests.RequestException:
                        pass
                    time.sleep(0.1)
                else:
                    raise ModelYok("ozel Ollama 20 saniyede hazir olmadi")
                self._start_monitor()
                self._warmup()
                return
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self._stop_process()
                if self.log_handle:
                    self.log_handle.close()
                    self.log_handle = None
        raise ModelYok(f"ozel Ollama 5 port denemesinde baslatilamadi: {last_error}")

    def _post(self, payload: dict, timeout: float) -> dict:
        try:
            response = self.session.post(
                self.base_url + "/api/generate", json=payload,
                timeout=(3.0, timeout))
            response.raise_for_status()
            data = response.json()
        except requests.Timeout as exc:
            raise TimeoutError(f"Ollama cagrisi {timeout:.0f}s zaman asimi") from exc
        except (requests.RequestException, ValueError) as exc:
            response = getattr(exc, "response", None)
            text = response.text[-500:] if response is not None else ""
            low = text.lower()
            if "out of memory" in low or ("cuda" in low and "memory" in low):
                raise Bellek(text or str(exc)) from exc
            raise ModelYok(f"ozel Ollama HTTP: {type(exc).__name__}: {exc} {text}".strip()) from exc
        if data.get("error"):
            message = str(data["error"])
            if "out of memory" in message.lower():
                raise Bellek(message)
            raise ModelYok(f"ozel Ollama: {message}")
        return data

    def _warmup(self) -> None:
        started = time.monotonic()
        self._post({
            "model": self.model, "prompt": "", "stream": False,
            "keep_alive": -1,
            "options": {"temperature": 0, "num_predict": 1, "num_ctx": 8192},
        }, float(self.settings.get("warmup_seconds", 90)))
        self.warmup_seconds = time.monotonic() - started

    def __call__(self, path: Path, prompt: str | None = None) -> str:
        try:
            encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        except OSError as exc:
            raise ModelYok(f"okuma gorseli acilamadi: {path}: {exc}") from exc
        payload = {
            "model": self.model,
            "prompt": prompt or str(self.settings.get("istem", "Free OCR.")),
            "images": [encoded],
            "stream": False,
            "keep_alive": -1,
            "options": {
                "temperature": 0,
                "num_predict": int(self.settings.get("max_new_tokens", 2048)),
                "num_ctx": int(self.settings.get("num_ctx", 8192)),
            },
        }
        started = time.monotonic()
        data = self._post(payload, float(self.settings.get("request_seconds", 30)))
        elapsed = time.monotonic() - started
        self.call_count += 1
        self.call_seconds += elapsed
        self.max_call_seconds = max(self.max_call_seconds, elapsed)
        return str(data.get("response") or "").strip()

    def _start_monitor(self) -> None:
        self._monitor_stop.clear()

        def monitor() -> None:
            while not self._monitor_stop.wait(0.2):
                self.peak_vram_mb = max(self.peak_vram_mb, self._tree_vram_mb())

        self._monitor_thread = threading.Thread(
            target=monitor, name="lebron-ollama-vram", daemon=True)
        self._monitor_thread.start()

    def _tree_pids(self) -> set[int]:
        if not self.process or self.process.poll() is not None:
            return set()
        try:
            root = psutil.Process(self.process.pid)
            if self.process_created is not None and abs(
                    root.create_time() - self.process_created) > 0.01:
                return set()
            return {root.pid, *(child.pid for child in root.children(recursive=True))}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return set()

    def _tree_vram_mb(self) -> float:
        pids = self._tree_pids()
        if not pids:
            return 0.0
        try:
            probe = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,used_memory",
                 "--format=csv,noheader,nounits"], capture_output=True,
                text=True, timeout=2, check=False)
            total = 0.0
            for line in probe.stdout.splitlines():
                fields = [field.strip() for field in line.split(",")]
                if len(fields) >= 2 and int(fields[0]) in pids:
                    total += float(fields[1])
            return total
        except Exception:
            return 0.0

    def metrics(self) -> dict:
        self.peak_vram_mb = max(self.peak_vram_mb, self._tree_vram_mb())
        return {
            "backend": "private-ollama",
            "model": self.model,
            "port": self.port,
            "warmup_seconds": round(self.warmup_seconds, 3),
            "call_count": self.call_count,
            "call_seconds": round(self.call_seconds, 3),
            "max_call_seconds": round(self.max_call_seconds, 3),
            "vram_peak_mb": round(self.peak_vram_mb, 1),
            "max_new_tokens": int(self.settings.get("max_new_tokens", 2048)),
            "num_ctx": int(self.settings.get("num_ctx", 8192)),
            "request_seconds": float(self.settings.get("request_seconds", 30)),
        }

    def _stop_process(self) -> None:
        process = self.process
        if process is None:
            return
        try:
            root = psutil.Process(process.pid)
            if self.process_created is not None and abs(
                    root.create_time() - self.process_created) > 0.01:
                return
            children = root.children(recursive=True)
            for item in reversed(children):
                try:
                    item.terminate()
                except psutil.NoSuchProcess:
                    pass
            try:
                root.terminate()
            except psutil.NoSuchProcess:
                pass
            _, alive = psutil.wait_procs([*children, root], timeout=5)
            for item in alive:
                try:
                    item.kill()
                except psutil.NoSuchProcess:
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        finally:
            try:
                process.wait(timeout=2)
            except Exception:
                pass
            self.process = None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self.process and self.process.poll() is None:
                try:
                    self._post({"model": self.model, "prompt": "", "stream": False,
                                "keep_alive": 0}, 10)
                except Exception:
                    pass
        finally:
            self._monitor_stop.set()
            if self._monitor_thread:
                self._monitor_thread.join(timeout=1)
            self._stop_process()
            self.session.close()
            if self.log_handle:
                self.log_handle.close()
                self.log_handle = None


def yukle(ayar: dict, kule: Path) -> Callable[[Path], str]:
    return PrivateOllama(ayar, Path(kule))
