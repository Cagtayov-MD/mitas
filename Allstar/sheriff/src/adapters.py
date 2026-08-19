from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from .config import SheriffConfig
from .contracts import (ContractError, asset_record, line_record, packet,
                        read_packet, validate_packet, write_packet)
from .runner import ProcessResult, run_process
from .util import safe_component, sha256_file


class TowerError(RuntimeError):
    def __init__(self, message: str, *, error_class: str = "TOWER", result: ProcessResult | None = None):
        super().__init__(message)
        self.error_class = error_class
        self.result = result


class TowerContractError(TowerError):
    pass


class TowerAdapter:
    """Config-driven process adapter. It never imports sibling tower code."""

    def __init__(self, config: SheriffConfig) -> None:
        self.config = config

    def execute(self, task: dict[str, Any], attempt_id: str, input_path: Path,
                run_dir: Path, *, heartbeat: Callable[[], None],
                should_cancel: Callable[[], bool],
                on_process_start: Callable[[int, int, float | None], None] | None = None,
                parent_tasks: list[str] | None = None) -> tuple[str, dict[str, Any], ProcessResult]:
        role = str(task["logical_role"])
        tower = self.config.tower(role)
        output_root = run_dir / "tower_outputs" / role / attempt_id
        values = {"film_id": task["film_id"], "section": task["section"],
                  "input": str(input_path.resolve()), "run_id": task["run_id"],
                  "task_id": task["task_id"], "attempt_id": attempt_id,
                  "output": str(output_root.resolve()), "role": role}
        executable = Path(tower["executable"])
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise TowerContractError(f"kule executable yok: {executable}",
                                     error_class="EXECUTABLE_MISSING")
        command = [str(executable), *[str(part).format(**values)
                                      for part in tower.get("command", [])]]
        result_path, marker_path, legacy_path = self._output_paths(tower, values, output_root)
        tower_result_path = result_path
        attempt_dir = run_dir / "attempts" / task["task_id"] / attempt_id
        if not tower.get("isolated_output"):
            self._archive_stale(result_path.parent, attempt_dir / "stale_tower_output")

        env = dict(os.environ)
        env.update({
            "MITAS_SHERIFF_RUN_ID": task["run_id"],
            "MITAS_SHERIFF_TASK_ID": task["task_id"],
            "MITAS_SHERIFF_ATTEMPT_ID": attempt_id,
            "MITAS_SHERIFF_FRAME_MANIFEST": str(self._frame_manifest(input_path)),
            "MITAS_OKUMA_V2": "1",
            "PYTHONUNBUFFERED": "1",
        })
        cpu_threads = max(1, int(self.config.resource_profile(
            tower["resource_profile"]).get("cpu_threads", 1)))
        env.update({"OMP_NUM_THREADS": str(cpu_threads),
                    "MKL_NUM_THREADS": str(cpu_threads),
                    "OPENBLAS_NUM_THREADS": str(cpu_threads),
                    "NUMEXPR_MAX_THREADS": str(cpu_threads)})
        process = run_process(
            command, cwd=executable.parent, env=env,
            stdout_path=attempt_dir / "stdout.log", stderr_path=attempt_dir / "stderr.log",
            timeout_s=float(tower.get("timeout_seconds", 3600)), heartbeat=heartbeat,
            should_cancel=should_cancel, on_start=on_process_start)
        if process.cancelled:
            raise TowerError("kule durduruldu", error_class="CANCELLED", result=process)
        if process.timed_out:
            raise TowerError("kule zaman asimina ugradi", error_class="TIMEOUT", result=process)
        if not marker_path.is_file():
            raise TowerContractError("taze _TAMAM bulunamadi", error_class="MARKER_MISSING",
                                     result=process)
        if not tower.get("isolated_output"):
            result_path, marker_path, legacy_path = self._snapshot_tower_output(
                result_path, marker_path, legacy_path, output_root, values)

        packet_reader_roles = {
            self.config.raw["dag"]["independent_reader_role"],
            self.config.raw["dag"]["boundary_frame_reader_role"],
        }
        video_reader_role = self.config.raw["dag"]["boundary_video_reader_role"]
        boundary_role = self.config.raw["dag"]["boundary_role"]
        if role in packet_reader_roles:
            if not result_path.is_file():
                detail = f"; legacy cikti var: {legacy_path}" if legacy_path and legacy_path.exists() else ""
                raise TowerContractError(f"mitas.okuma/v2 cikisi yok: {result_path}{detail}",
                                         error_class="V2_MISSING", result=process)
            try:
                document = read_packet(result_path, expected={
                    "film_id": task["film_id"], "section": task["section"],
                    "run_id": task["run_id"], "task_id": task["task_id"],
                    "attempt_id": attempt_id,
                }, verify_assets=bool(tower.get("isolated_output")))
                if not tower.get("isolated_output"):
                    self._rebase_packet_assets(
                        document, tower_result_path.parent, result_path.parent)
                    validate_packet(document, base_dir=result_path.parent,
                                    verify_assets=True)
                    write_packet(result_path, document)
                if (document.get("producer") or {}).get("id") != tower["producer_id"]:
                    raise ContractError("producer.id kayitli kuleyle uyusmuyor")
            except ContractError as exc:
                raise TowerContractError(str(exc), error_class="CONTRACT", result=process) from exc
            document["lineage"]["parent_tasks"] = parent_tasks or []
            document["resource_usage"] = {
                **(document.get("resource_usage") or {}), **process.metrics(),
                "subprocess_exit_code": process.exit_code,
                "stdout_path": process.stdout_path, "stderr_path": process.stderr_path,
            }
            packet_copy = run_dir / "packets" / task["section"] / (
                f"{tower['producer_id']}.okuma.json")
            write_packet(packet_copy, document)
            execution = document["status"]["execution"]
            content = document["status"]["content"]
            status = ("FAILED" if execution == "FAILED" else
                      "NO_CONTENT" if execution == "NO_CONTENT" or content == "NO_TEXT"
                      else "SUCCEEDED")
            return status, {"producer": tower["producer_id"], "packet_path": str(packet_copy),
                            "tower_packet_path": str(result_path),
                            "tower_origin_path": str(tower_result_path),
                            "tower_status": execution, "document": document}, process

        if not result_path.is_file():
            raise TowerContractError(f"sonuc JSON yok: {result_path}",
                                     error_class="RESULT_MISSING", result=process)
        try:
            legacy_document = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TowerContractError(f"bozuk kule JSON: {exc}", error_class="CONTRACT",
                                     result=process) from exc
        try:
            self._validate_legacy_identity(legacy_document, task, attempt_id)
        except TowerContractError as exc:
            exc.result = process
            raise
        if role == video_reader_role:
            if legacy_document.get("schema_version") != "mitas.jordan/v1":
                raise TowerContractError("Jordan schema_version eksik/gecersiz",
                                         error_class="CONTRACT", result=process)
            try:
                self._validate_jordan(legacy_document)
                packet_path, document = self._wrap_jordan(
                    task, attempt_id, input_path, legacy_document, run_dir, process,
                    parent_tasks or [], producer_id=tower["producer_id"],
                    independence_group=role)
            except ContractError as exc:
                raise TowerContractError(str(exc), error_class="CONTRACT",
                                         result=process) from exc
            execution = document["status"]["execution"]
            status = "SUCCEEDED" if execution == "SUCCEEDED" else (
                "NO_CONTENT" if execution == "NO_CONTENT" else "FAILED")
            return status, {"producer": tower["producer_id"], "packet_path": str(packet_path),
                            "legacy_path": str(result_path), "tower_status": execution,
                            "tower_origin_path": str(tower_result_path),
                            "document": document}, process

        if role != boundary_role:
            raise TowerContractError(f"adapter sinifi olmayan kule rolu: {role}",
                                     error_class="CONTRACT", result=process)
        try:
            self._validate_boundary(legacy_document, result_path, input_path)
        except TowerContractError as exc:
            exc.result = process
            raise
        tower_status = legacy_document.get("durum")
        status = {"BULUNDU": "SUCCEEDED", "KREDI_YOK": "NO_CONTENT",
                  "ARIZA": "FAILED"}.get(tower_status)
        if status is None:
            raise TowerContractError(f"boundary durum gecersiz: {tower_status!r}",
                                     error_class="CONTRACT", result=process)
        if process.exit_code not in (0, 2):
            status = "FAILED"
        return status, {"producer": tower["producer_id"], "result_path": str(result_path),
                        "tower_origin_path": str(tower_result_path),
                        "tower_status": tower_status, "document": legacy_document}, process

    def inspect_existing(self, task: dict[str, Any], attempt_id: str, input_path: Path,
                         run_dir: Path, parent_tasks: list[str]) -> tuple[str, dict[str, Any]] | None:
        """Validate a completed output left behind by a crashed Sheriff."""
        role = str(task["logical_role"])
        tower = self.config.tower(role)
        output_root = run_dir / "tower_outputs" / role / attempt_id
        values = {"film_id": task["film_id"], "section": task["section"],
                  "input": str(input_path.resolve()), "run_id": task["run_id"],
                  "task_id": task["task_id"], "attempt_id": attempt_id,
                  "output": str(output_root.resolve()), "role": role}
        result_path, marker_path, _ = self._output_paths(tower, values, output_root)
        tower_result_path = result_path
        if not tower.get("isolated_output"):
            archived = self._archived_output_paths(result_path, marker_path, None,
                                                   output_root, values)
            if archived[0].is_file() and archived[1].is_file():
                result_path, marker_path, _ = archived
            elif marker_path.is_file() and result_path.is_file():
                result_path, marker_path, _ = self._snapshot_tower_output(
                    result_path, marker_path, None, output_root, values)
        if not marker_path.is_file() or not result_path.is_file():
            return None
        try:
            packet_reader_roles = {
                self.config.raw["dag"]["independent_reader_role"],
                self.config.raw["dag"]["boundary_frame_reader_role"],
            }
            video_reader_role = self.config.raw["dag"]["boundary_video_reader_role"]
            boundary_role = self.config.raw["dag"]["boundary_role"]
            if role in packet_reader_roles:
                document = read_packet(result_path, expected={
                    "film_id": task["film_id"], "section": task["section"],
                    "run_id": task["run_id"], "task_id": task["task_id"],
                    "attempt_id": attempt_id},
                    verify_assets=bool(tower.get("isolated_output")))
                if not tower.get("isolated_output"):
                    self._rebase_packet_assets(
                        document, tower_result_path.parent, result_path.parent)
                    validate_packet(document, base_dir=result_path.parent,
                                    verify_assets=True)
                    write_packet(result_path, document)
                if (document.get("producer") or {}).get("id") != tower["producer_id"]:
                    return None
                document["lineage"]["parent_tasks"] = parent_tasks
                document["resource_usage"] = {
                    **(document.get("resource_usage") or {}), "recovered_after_crash": True}
                packet_copy = run_dir / "packets" / task["section"] / (
                    f"{tower['producer_id']}.okuma.json")
                write_packet(packet_copy, document)
                execution, content = document["status"]["execution"], document["status"]["content"]
                status = ("FAILED" if execution == "FAILED" else "NO_CONTENT"
                          if execution == "NO_CONTENT" or content == "NO_TEXT" else "SUCCEEDED")
                return status, {"producer": tower["producer_id"],
                                "packet_path": str(packet_copy),
                                "tower_packet_path": str(result_path),
                                "tower_origin_path": str(tower_result_path),
                                "tower_status": execution, "document": document,
                                "recovered": True}
            legacy = json.loads(result_path.read_text(encoding="utf-8"))
            self._validate_legacy_identity(legacy, task, attempt_id)
            if role == video_reader_role:
                if legacy.get("schema_version") != "mitas.jordan/v1":
                    return None
                packet_path = run_dir / "packets" / task["section"] / (
                    f"{safe_component(str(tower['producer_id']), 'producer_id')}.okuma.json")
                if not packet_path.is_file():
                    return None
                document = read_packet(packet_path, expected={
                    "film_id": task["film_id"], "section": task["section"],
                    "run_id": task["run_id"], "task_id": task["task_id"],
                    "attempt_id": attempt_id}, verify_assets=True)
                if (document.get("producer") or {}).get("id") != tower["producer_id"]:
                    return None
                execution, content = document["status"]["execution"], document["status"]["content"]
                status = ("FAILED" if execution == "FAILED" else "NO_CONTENT"
                          if execution == "NO_CONTENT" or content == "NO_TEXT" else "SUCCEEDED")
                return status, {"producer": tower["producer_id"],
                                "packet_path": str(packet_path), "legacy_path": str(result_path),
                                "tower_origin_path": str(tower_result_path),
                                "tower_status": execution, "document": document,
                                "recovered": True}
            if role != boundary_role:
                return None
            self._validate_boundary(legacy, result_path, input_path)
            tower_status = legacy.get("durum")
            status = {"BULUNDU": "SUCCEEDED", "KREDI_YOK": "NO_CONTENT",
                      "ARIZA": "FAILED"}.get(tower_status)
            if status is None:
                return None
            return status, {"producer": tower["producer_id"],
                            "result_path": str(result_path),
                            "tower_origin_path": str(tower_result_path),
                            "tower_status": tower_status,
                            "document": legacy, "recovered": True}
        except (OSError, json.JSONDecodeError, ContractError, TowerContractError):
            return None

    @staticmethod
    def _archive_stale(output_dir: Path, archive: Path) -> None:
        if not output_dir.exists():
            return
        if not any(output_dir.iterdir()):
            return
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists():
            shutil.rmtree(archive)
        os.replace(output_dir, archive)

    @classmethod
    def _snapshot_tower_output(cls, result_path: Path, marker_path: Path,
                               legacy_path: Path | None, output_root: Path,
                               values: dict[str, str]) -> tuple[Path, Path, Path | None]:
        """Kulenin kendi out/ bolumunu attempt'e atomik ve kalici olarak al.

        Kule cikisi yerinde kalir. Ayni dosya sisteminde dosyalar hardlink,
        degilse kopyadir. Tuketici bundan sonra paylasilan kule out'una degil,
        run/attempt snapshot'ina bakar.
        """
        source_root = result_path.parent.resolve()
        if marker_path.parent.resolve() != source_root or (
                legacy_path is not None and legacy_path.parent.resolve() != source_root):
            raise TowerContractError(
                "kule result/marker/legacy ayni bolum dizininde olmali",
                error_class="CONTRACT")
        archive_paths = cls._archived_output_paths(
            result_path, marker_path, legacy_path, output_root, values)
        final_root = archive_paths[0].parent
        final_root.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{final_root.name}-", dir=final_root.parent))
        try:
            for source in sorted(source_root.rglob("*")):
                relative = source.relative_to(source_root)
                target = temporary / relative
                if source.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif source.is_file() and not source.name.endswith(".tmp"):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        os.link(source, target)
                    except OSError:
                        shutil.copy2(source, target)
            if final_root.exists():
                stale = final_root.with_name(f".{final_root.name}.stale-{os.getpid()}")
                if stale.exists():
                    shutil.rmtree(stale)
                os.replace(final_root, stale)
                os.replace(temporary, final_root)
                shutil.rmtree(stale, ignore_errors=True)
            else:
                os.replace(temporary, final_root)
            return archive_paths
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    @staticmethod
    def _archived_output_paths(result_path: Path, marker_path: Path,
                               legacy_path: Path | None, output_root: Path,
                               values: dict[str, str]) -> tuple[Path, Path, Path | None]:
        final_root = (output_root
                      / safe_component(str(values["film_id"]), "film_id")
                      / safe_component(str(values["section"]), "section"))
        result = final_root / result_path.name
        marker = final_root / marker_path.name
        legacy = final_root / legacy_path.name if legacy_path is not None else None
        return result, marker, legacy

    @staticmethod
    def _rebase_packet_assets(document: dict[str, Any], source_root: Path,
                              archive_root: Path) -> None:
        """Kule out'u altindaki asset yollarini attempt snapshot'ina sabitle."""
        source_root = source_root.resolve()
        archive_root = archive_root.resolve()
        for asset in document.get("assets") or []:
            raw_path = Path(str(asset.get("path") or ""))
            source = raw_path.resolve() if raw_path.is_absolute() else (
                source_root / raw_path).resolve()
            try:
                relative = source.relative_to(source_root)
            except ValueError:
                continue
            archived = (archive_root / relative).resolve()
            if archive_root not in archived.parents:
                raise ContractError("snapshot asset yolu archive disina cikiyor")
            asset["origin_path"] = asset.get("origin_path") or str(source)
            asset["path"] = str(archived)

    @staticmethod
    def _frame_manifest(input_path: Path) -> Path:
        if input_path.is_dir():
            candidate = input_path / "frames.jsonl"
            if candidate.is_file():
                return candidate
        return Path("")

    @staticmethod
    def _validate_legacy_identity(value: dict[str, Any], task: dict[str, Any],
                                  attempt_id: str) -> None:
        if not isinstance(value, dict):
            raise TowerContractError("legacy sonuc nesne olmali", error_class="CONTRACT")
        if value.get("film_id") != task["film_id"]:
            raise TowerContractError("legacy film_id uyusmuyor", error_class="CONTRACT")
        if value.get("bolum") != task["section"]:
            raise TowerContractError("legacy bolum uyusmuyor", error_class="CONTRACT")
        identity = value.get("identity")
        if not isinstance(identity, dict):
            raise TowerContractError("legacy identity nesne olmali",
                                     error_class="CONTRACT")
        expected = {"run_id": task["run_id"], "task_id": task["task_id"],
                    "attempt_id": attempt_id}
        if any(identity.get(key) != wanted for key, wanted in expected.items()):
            raise TowerContractError("legacy run/task/attempt kimligi uyusmuyor",
                                     error_class="CONTRACT")

    @staticmethod
    def _validate_boundary(value: dict[str, Any], result_path: Path,
                           input_path: Path) -> None:
        if value.get("schema_version") != "mitas.boundary/v1":
            raise TowerContractError("boundary schema_version eksik/gecersiz",
                                     error_class="CONTRACT")
        status = value.get("durum")
        if status not in {"BULUNDU", "KREDI_YOK", "ARIZA"}:
            raise TowerContractError(f"boundary durum gecersiz: {status!r}",
                                     error_class="CONTRACT")
        if status != "BULUNDU":
            return
        start_frame = value.get("baslangic_kare")
        start_s = value.get("baslangic_sn")
        if (not isinstance(start_frame, int) or isinstance(start_frame, bool)
                or start_frame < 1 or not isinstance(start_s, (int, float))
                or isinstance(start_s, bool) or float(start_s) < 0):
            raise TowerContractError("boundary baslangic kare/zaman gecersiz",
                                     error_class="CONTRACT")
        frame_manifest = input_path / "frames.jsonl"
        try:
            frame_rows = [json.loads(line) for line in frame_manifest.read_text(
                encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError) as exc:
            raise TowerContractError(f"boundary kaynak frame manifest bozuk: {exc}",
                                     error_class="CONTRACT") from exc
        if not frame_rows or any(not isinstance(row, dict) for row in frame_rows):
            raise TowerContractError("boundary kaynak frame manifest satiri gecersiz",
                                     error_class="CONTRACT")
        sequences = {row.get("sequence") for row in frame_rows}
        if start_frame not in sequences:
            raise TowerContractError("boundary baslangic_kare kaynak manifestte yok",
                                     error_class="CONTRACT")
        end_frame, end_s = value.get("bitis_kare"), value.get("bitis_sn")
        if (end_frame is None) != (end_s is None):
            raise TowerContractError("boundary bitis kare/zaman birlikte verilmelidir",
                                     error_class="CONTRACT")
        if end_frame is not None:
            if (not isinstance(end_frame, int) or isinstance(end_frame, bool)
                    or end_frame < start_frame or end_frame not in sequences
                    or not isinstance(end_s, (int, float)) or isinstance(end_s, bool)
                    or float(end_s) < float(start_s)):
                raise TowerContractError("boundary bitis kare/zaman gecersiz",
                                         error_class="CONTRACT")
        confidence = value.get("guven")
        if confidence is not None and (not isinstance(confidence, (int, float))
                                       or isinstance(confidence, bool)
                                       or not 0 <= float(confidence) <= 1):
            raise TowerContractError("boundary guven 0..1 olmali",
                                     error_class="CONTRACT")
        artifact_values = value.get("uretilen")
        if not isinstance(artifact_values, list) or any(
                not isinstance(item, dict) for item in artifact_values):
            raise TowerContractError("boundary uretilen nesne listesi olmali",
                                     error_class="CONTRACT")
        artifacts = [item for item in artifact_values if item.get("tip") == "kare"]
        if len(artifacts) != 1:
            raise TowerContractError("boundary tam bir kare artefakti vermeli",
                                     error_class="CONTRACT")
        relative = Path(str(artifacts[0].get("yol") or ""))
        root = result_path.parent.resolve()
        selected = (root / relative).resolve()
        if relative.is_absolute() or selected == root or root not in selected.parents:
            raise TowerContractError("boundary kare yolu output disina cikiyor",
                                     error_class="CONTRACT")
        paths = sorted(selected.glob("*.png"))
        if not paths:
            raise TowerContractError("boundary kare artefakti bos",
                                     error_class="CONTRACT")
        declared_count = artifacts[0].get("adet")
        if declared_count is not None and declared_count != len(paths):
            raise TowerContractError("boundary kare artefakti adet uyusmuyor",
                                     error_class="CONTRACT")
        inputs = {path.name: path for path in input_path.glob("*.png")}
        for path in paths:
            source = inputs.get(path.name)
            if not source or sha256_file(source) != sha256_file(path):
                raise TowerContractError(
                    f"boundary secili kare girdiye baglanamiyor: {path.name}",
                    error_class="CONTRACT")

    @staticmethod
    def _output_paths(tower: dict[str, Any], values: dict[str, str],
                      output_root: Path) -> tuple[Path, Path, Path | None]:
        if tower.get("isolated_output"):
            result = output_root / str(tower["result_relative"]).format(**values)
            marker = output_root / str(tower["marker_relative"]).format(**values)
            legacy_value = tower.get("legacy_result_relative")
            legacy = output_root / str(legacy_value).format(**values) if legacy_value else None
            return result, marker, legacy
        result = Path(str(tower["result"]).format(**values))
        marker = Path(str(tower["marker"]).format(**values))
        legacy_value = tower.get("legacy_result")
        legacy = Path(str(legacy_value).format(**values)) if legacy_value else None
        return result, marker, legacy

    @staticmethod
    def _validate_jordan(value: dict[str, Any]) -> None:
        status = value.get("durum")
        if status not in {"OKUNDU", "METIN_YOK", "ARIZA"}:
            raise ContractError(f"Jordan durum gecersiz: {status!r}")
        if not isinstance(value.get("kanit"), dict):
            raise ContractError("Jordan kanit nesne olmali")
        # Bir kule arizasi metin sonucu degildir. Jordan'in hata zarfi bilerek
        # bloklar/ciftler uretmez; once onu kabul et ki Engine BELLEK/OOM
        # sinifini gorup exclusive tekrar yolunu calistirabilsin.
        if status == "ARIZA":
            if not (value.get("sinif") and value.get("mesaj")):
                raise ContractError("Jordan ARIZA sinif/mesaj ister")
            for key in ("bloklar", "ciftler"):
                if key in value and not isinstance(value[key], list):
                    raise ContractError(f"Jordan ARIZA {key} verilirse liste olmali")
            return
        blocks = value.get("bloklar")
        pairs = value.get("ciftler")
        if not isinstance(blocks, list) or not isinstance(pairs, list):
            raise ContractError("Jordan bloklar/ciftler liste olmali")
        for block in blocks:
            if not isinstance(block, dict) or not isinstance(block.get("satirlar"), list):
                raise ContractError("Jordan blok satirlari liste olmali")
            if any(not isinstance(text, str) or not text.strip()
                   for text in block["satirlar"]):
                raise ContractError("Jordan blokta bos/gecersiz satir")
        if status == "OKUNDU" and not any(block["satirlar"] for block in blocks):
            raise ContractError("Jordan OKUNDU en az bir satir ister")
        if status == "METIN_YOK" and blocks:
            raise ContractError("Jordan METIN_YOK blok tasiyamaz")

    @staticmethod
    def _wrap_jordan(task: dict[str, Any], attempt_id: str, input_path: Path,
                     legacy: dict[str, Any], run_dir: Path,
                     process: ProcessResult,
                     parent_tasks: list[str], *, producer_id: str,
                     independence_group: str) -> tuple[Path, dict[str, Any]]:
        durum = legacy.get("durum")
        execution = "SUCCEEDED" if durum == "OKUNDU" else (
            "NO_CONTENT" if durum == "METIN_YOK" else "FAILED")
        content = "READ" if durum == "OKUNDU" else (
            "NO_TEXT" if durum == "METIN_YOK" else "UNKNOWN")
        assets = []
        inputs = []
        if input_path.is_file():
            source = asset_record(input_path, asset_id="jordan-input-video")
            inputs.append({"path": str(input_path.resolve()), "sha256": source["sha256"],
                           "kind": "silent_credit_clip"})
            assets.append(source)
        lines = []
        for block_index, block in enumerate(legacy.get("bloklar") or []):
            for text in block.get("satirlar") or []:
                lines.append(line_record(str(text), len(lines), source_label=f"block:{block_index}"))
        document = packet(
            film_id=task["film_id"], section=task["section"], run_id=task["run_id"],
            task_id=task["task_id"], attempt_id=attempt_id,
            producer={"id": producer_id, "tower_version": legacy.get("motor_surumu"),
                      "strategy": "multi-image-frame-ocr",
                      "model": legacy.get("kanit", {}).get("model"),
                      "prompt_digest": None, "runtime": "tower-cli",
                      "independence_group": independence_group},
            inputs=inputs, execution_status=execution, content_status=content,
            proof_status="NONE", assets=assets, lines=lines,
            unread_regions=[{"reason": "Jordan henuz frame/bbox proof uretmiyor",
                             "scope": "all_lines"}] if lines else [],
            diagnostics={"legacy_result": legacy, "proof_limitation": "NO_BBOX_CLAIM"},
            resource_usage={**process.metrics(), "subprocess_exit_code": process.exit_code,
                            "stdout_path": process.stdout_path,
                            "stderr_path": process.stderr_path},
            parent_tasks=parent_tasks)
        packet_path = run_dir / "packets" / task["section"] / (
            f"{safe_component(str(producer_id), 'producer_id')}.okuma.json")
        write_packet(packet_path, document)
        return packet_path, document
