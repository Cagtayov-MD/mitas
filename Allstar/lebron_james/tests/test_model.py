from pathlib import Path

import pytest
import requests

import model


def _adapter(tmp_path: Path) -> model.PrivateOllama:
    adapter = object.__new__(model.PrivateOllama)
    adapter.settings = {"max_new_tokens": 2048, "num_ctx": 8192,
                        "request_seconds": 30, "istem": "Free OCR."}
    adapter.tower = tmp_path
    adapter.store = tmp_path / "store"
    adapter.library = tmp_path / "lib"
    adapter.model = "deepseek-ocr:latest"
    adapter.call_count = 0
    adapter.call_seconds = 0.0
    adapter.max_call_seconds = 0.0
    return adapter


def test_private_ortam_global_servise_ve_homea_dokunmaz(tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    monkeypatch.setenv("HOME", "/keep/me")
    env = adapter._environment(43210)
    assert env["OLLAMA_HOST"] == "127.0.0.1:43210"
    assert env["OLLAMA_MODELS"] == str(adapter.store)
    assert env["OLLAMA_NO_CLOUD"] == "1"
    assert env["HOME"] == "/keep/me"


def test_generate_payload_token_sure_ve_istem_sinirlarini_zorlar(tmp_path):
    adapter = _adapter(tmp_path)
    image = tmp_path / "band.png"
    image.write_bytes(b"png")
    seen = {}

    def post(payload, timeout):
        seen.update({"payload": payload, "timeout": timeout})
        return {"response": "YONETMEN\nAHMET"}

    adapter._post = post
    assert adapter(image) == "YONETMEN\nAHMET"
    assert seen["timeout"] == 30
    assert seen["payload"]["prompt"] == "Free OCR."
    assert seen["payload"]["stream"] is False
    assert seen["payload"]["options"] == {
        "temperature": 0, "num_predict": 2048, "num_ctx": 8192}
    assert adapter.call_count == 1


def test_http_timeout_acik_hata_olur(tmp_path):
    adapter = _adapter(tmp_path)

    class Session:
        def post(self, *_args, **_kwargs):
            raise requests.Timeout("gecikti")

    adapter.session = Session()
    adapter.base_url = "http://127.0.0.1:43210"
    with pytest.raises(TimeoutError, match="30s zaman asimi"):
        adapter._post({"model": adapter.model}, 30)


def test_bes_port_yarisi_sonra_acik_ariza_ve_global_11434_yok(
        tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)
    adapter.settings["_host_ollama_home"] = str(tmp_path / "host" / ".ollama")
    Path(adapter.settings["_host_ollama_home"]).mkdir(parents=True)
    adapter.binary = tmp_path / "runtime/bin/ollama"
    adapter.library.mkdir(parents=True)
    adapter.binary.parent.mkdir(parents=True)
    adapter.binary.write_text("fake", encoding="utf-8")
    adapter.process = None
    adapter.process_created = None
    adapter.port = None
    adapter.base_url = ""
    adapter.log_handle = None
    adapter.session = object()
    adapter._monitor_stop = __import__("threading").Event()
    adapter._monitor_thread = None
    adapter._closed = False

    ports = iter([40101, 40102, 40103, 40104, 40105])
    monkeypatch.setattr(model, "_free_port", lambda: next(ports))
    cagrilar = []

    class DeadProcess:
        returncode = 98

        def __init__(self, pid):
            self.pid = pid

        def poll(self):
            return self.returncode

    def popen(command, **kwargs):
        cagrilar.append((command, kwargs))
        return DeadProcess(5000 + len(cagrilar))

    class Ps:
        def __init__(self, pid):
            self.pid = pid

        def create_time(self):
            return 123.0

    monkeypatch.setattr(model.subprocess, "Popen", popen)
    monkeypatch.setattr(model.psutil, "Process", Ps)

    def stop():
        adapter.process = None

    adapter._stop_process = stop
    with pytest.raises(model.ModelYok, match="5 port denemesinde"):
        adapter._start()

    assert len(cagrilar) == 5
    assert [x[1]["env"]["OLLAMA_HOST"] for x in cagrilar] == [
        f"127.0.0.1:{p}" for p in range(40101, 40106)]
    assert all("11434" not in x[1]["env"]["OLLAMA_HOST"] for x in cagrilar)
    for command, kwargs in cagrilar:
        assert command[0] == "/usr/bin/bwrap"
        assert "--bind" in command
        assert str(tmp_path / "scratch/ollama/home") in command
        assert kwargs["stdout"] is not model.subprocess.PIPE
        assert kwargs["stderr"] is model.subprocess.STDOUT


def test_cleanup_create_time_dogrulanmis_alt_surec_agacini_kapatir(
        tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)

    class Handle:
        pid = 7001

        def wait(self, timeout):
            assert timeout == 2

    olaylar = []

    class Node:
        def __init__(self, pid, children=()):
            self.pid = pid
            self._children = list(children)

        def create_time(self):
            return 456.0

        def children(self, recursive):
            assert recursive is True
            return self._children

        def terminate(self):
            olaylar.append(("terminate", self.pid))

        def kill(self):
            olaylar.append(("kill", self.pid))

    child = Node(7002)
    root = Node(7001, [child])
    monkeypatch.setattr(model.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(
        model.psutil, "wait_procs",
        lambda processes, timeout: (processes, []))
    adapter.process = Handle()
    adapter.process_created = 456.0
    adapter._stop_process()
    assert olaylar == [("terminate", 7002), ("terminate", 7001)]
    assert adapter.process is None


def test_cleanup_pid_yeniden_kullanildiysa_yabanci_sureci_oldurmez(
        tmp_path, monkeypatch):
    adapter = _adapter(tmp_path)

    class Handle:
        pid = 8001

        def wait(self, timeout):
            pass

    class Reused:
        def create_time(self):
            return 999.0

        def terminate(self):
            raise AssertionError("yeniden kullanilan PID oldurulmemeli")

    monkeypatch.setattr(model.psutil, "Process", lambda pid: Reused())
    adapter.process = Handle()
    adapter.process_created = 123.0
    adapter._stop_process()
    assert adapter.process is None
