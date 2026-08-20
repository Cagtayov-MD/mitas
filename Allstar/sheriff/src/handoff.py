from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .config import SheriffConfig
from .contracts import (ContractError, packet, read_packet, validate_packet,
                        write_packet)
from .util import (atomic_write_json, hardlink_or_copy, now_iso, safe_component,
                   sha256_file, sha256_json)


class HandoffError(RuntimeError):
    pass


class HandoffPublisher:
    def __init__(self, config: SheriffConfig) -> None:
        self.config = config

    def publish(self, task: dict[str, Any], readers: list[dict[str, Any]]) -> dict[str, Any]:
        expected_roles = {
            self.config.raw["dag"]["independent_reader_role"],
            self.config.raw["dag"]["boundary_frame_reader_role"],
            self.config.raw["dag"]["boundary_video_reader_role"],
        }
        actual_roles = {item.get("logical_role") for item in readers}
        if len(readers) != 3 or actual_roles != expected_roles:
            raise HandoffError(f"uc okuyucu rolu eksik/tekrarli: {actual_roles!r}")
        film_id = safe_component(task["film_id"], "film_id")
        run_id = safe_component(task["run_id"], "run_id")
        section = safe_component(task["section"], "section")
        final = self.config.shaq_inbox / film_id / run_id / section
        marker = final / "_TAMAM"
        manifest_path = final / "bundle.manifest.json"
        input_fingerprint = self._input_fingerprint(readers)
        if marker.is_file() and manifest_path.is_file():
            try:
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._verify_bundle(
                    final, existing,
                    expected={"film_id": film_id, "run_id": run_id,
                              "section": section, "handoff_task_id": task["task_id"]},
                    expected_roles=expected_roles)
                if existing.get("input_fingerprint") == input_fingerprint:
                    return existing
            except (OSError, json.JSONDecodeError, ContractError, HandoffError,
                    KeyError, TypeError, AttributeError, ValueError):
                pass
        final.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{section}-", dir=final.parent))
        try:
            channels: list[dict[str, Any]] = []
            for reader in sorted(readers, key=lambda item: item.get("logical_role") or ""):
                for key in ("film_id", "run_id", "section"):
                    if reader.get(key) != task.get(key):
                        raise HandoffError(
                            f"okuyucu {key} handoff goreviyle uyusmuyor: "
                            f"{reader.get(key)!r} != {task.get(key)!r}")
                producer = self._producer_name(reader)
                output_name = f"{producer}-{film_id}-{section}.okuma.json"
                source_packet = (reader.get("result") or {}).get("packet_path")
                if source_packet and Path(source_packet).is_file():
                    try:
                        document = read_packet(Path(source_packet), expected={
                            "film_id": film_id, "section": section,
                            "run_id": run_id, "task_id": reader["task_id"]},
                            verify_assets=True)
                    except ContractError as exc:
                        raise HandoffError(
                            f"okuyucu paketi sozlesme disi: {source_packet}: {exc}") from exc
                    expected_producer = self.config.tower(
                        reader["logical_role"])["producer_id"]
                    if (document.get("producer") or {}).get("id") != expected_producer:
                        raise HandoffError(
                            f"okuyucu producer kayitla uyusmuyor: {source_packet}")
                    bundled, transfers = self._bundle_packet(
                        document, Path(source_packet).parent, temporary, producer)
                    channel_note = None
                else:
                    bundled = self._missing_packet(reader, producer)
                    transfers = []
                    channel_note = "kule paketi uretmedi; Sheriff terminal durumu zarfa yazdi"
                output_path = temporary / output_name
                write_packet(output_path, bundled)
                channels.append({
                    "producer": producer,
                    "logical_role": reader.get("logical_role"),
                    "task_id": reader["task_id"],
                    "task_status": reader["status"],
                    "execution_status": bundled["status"]["execution"],
                    "content_status": bundled["status"]["content"],
                    "proof_status": bundled["status"]["proof"],
                    "packet": output_name,
                    "packet_sha256": sha256_file(output_path),
                    "asset_transfers": transfers,
                    "note": channel_note,
                })
            manifest = {
                "schema_version": "mitas.shaq.bundle/v1",
                "created_at": now_iso(),
                "film_id": film_id, "run_id": run_id, "section": section,
                "handoff_task_id": task["task_id"],
                "input_fingerprint": input_fingerprint,
                "decision_policy": "UNASSIGNED",
                "auto_started_shaq": False,
                "channels": channels,
                "proof_ready_channels": [c["producer"] for c in channels
                                         if c["proof_status"] == "COMPLETE"],
                "complete": True,
            }
            atomic_write_json(temporary / "bundle.manifest.json", manifest)
            self._verify_bundle(
                temporary, manifest,
                expected={"film_id": film_id, "run_id": run_id,
                          "section": section, "handoff_task_id": task["task_id"]},
                expected_roles=expected_roles)
            (temporary / "_TAMAM").write_text("", encoding="utf-8")
            if final.exists():
                stale = final.with_name(
                    f"{final.name}.stale-{os.getpid()}-{uuid.uuid4().hex[:8]}")
                if stale.exists():
                    shutil.rmtree(stale)
                os.replace(final, stale)
                os.replace(temporary, final)
                shutil.rmtree(stale, ignore_errors=True)
            else:
                os.replace(temporary, final)
            return manifest
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    def _bundle_packet(self, document: dict[str, Any], source_dir: Path,
                       bundle_dir: Path, producer: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        bundled = copy.deepcopy(document)
        transfers = []
        for asset in bundled.get("assets") or []:
            source = Path(str(asset["path"]))
            source = source if source.is_absolute() else source_dir / source
            source = source.resolve()
            if not source.is_file():
                raise HandoffError(f"asset yok: {source}")
            if sha256_file(source) != asset["sha256"]:
                raise HandoffError(f"asset hash uyusmuyor: {source}")
            safe_name = re.sub(r"[^\w.-]+", "_", source.name, flags=re.UNICODE).strip("._")
            safe_name = safe_name or "asset.bin"
            asset_id = safe_component(str(asset["asset_id"]), "asset_id")
            asset_root = (bundle_dir / "assets" / producer).resolve()
            target = asset_root / f"{asset_id}-{safe_name}"
            if target.resolve().parent != asset_root:
                raise HandoffError(f"guvensiz asset hedefi: {asset_id!r}")
            method = hardlink_or_copy(source, target)
            origin = asset.get("origin_path") or str(source)
            asset["origin_path"] = origin
            asset["path"] = target.relative_to(bundle_dir).as_posix()
            asset["bytes"] = target.stat().st_size
            transfers.append({"asset_id": asset["asset_id"], "method": method,
                              "sha256": asset["sha256"], "path": asset["path"]})
        try:
            validate_packet(bundled, base_dir=bundle_dir, verify_assets=True)
        except ContractError as exc:
            raise HandoffError(f"bundle paketi sozlesme disi: {exc}") from exc
        return bundled, transfers

    def _producer_name(self, reader: dict[str, Any]) -> str:
        result = reader.get("result") or {}
        name = result.get("producer")
        if name:
            return safe_component(str(name), "producer")
        role = reader.get("logical_role")
        if role:
            return safe_component(str(self.config.tower(role)["producer_id"]), "producer")
        return "unknown"

    @staticmethod
    def _missing_packet(reader: dict[str, Any], producer: str) -> dict[str, Any]:
        task_status = reader["status"]
        execution = "NO_CONTENT" if task_status == "NO_CONTENT" else "FAILED"
        return packet(
            film_id=reader["film_id"], section=reader["section"],
            run_id=reader["run_id"], task_id=reader["task_id"],
            attempt_id="not-produced", producer={
                "id": producer, "tower_version": None, "strategy": "not-run",
                "model": None, "prompt_digest": None, "runtime": None,
                "independence_group": reader.get("logical_role")},
            inputs=[], execution_status=execution,
            content_status="NO_TEXT" if execution == "NO_CONTENT" else "UNKNOWN",
            proof_status="NONE", diagnostics={"task_status": task_status,
                                               "task_result": reader.get("result")})

    def _verify_bundle(self, root: Path, manifest: dict[str, Any], *,
                       expected: dict[str, str] | None = None,
                       expected_roles: set[str] | None = None) -> None:
        if (manifest.get("schema_version") != "mitas.shaq.bundle/v1"
                or not manifest.get("complete")):
            raise HandoffError("bundle tamamlanmamis")
        for key, wanted in (expected or {}).items():
            if manifest.get(key) != wanted:
                raise HandoffError(f"bundle {key} uyusmuyor")
        channels = manifest.get("channels") or []
        roles = {channel.get("logical_role") for channel in channels}
        if len(channels) != 3 or (expected_roles is not None and roles != expected_roles):
            raise HandoffError(f"bundle kanal rolleri gecersiz: {roles!r}")
        if manifest.get("decision_policy") != "UNASSIGNED" or manifest.get(
                "auto_started_shaq") is not False:
            raise HandoffError("bundle karar/otomatik baslatma politikasi gecersiz")
        for channel in channels:
            packet_relative = Path(str(channel.get("packet") or ""))
            if (packet_relative.is_absolute() or len(packet_relative.parts) != 1
                    or packet_relative.name in {"", ".", ".."}):
                raise HandoffError(f"bundle packet yolu guvensiz: {packet_relative}")
            packet_path = root / packet_relative
            if not packet_path.is_file() or sha256_file(packet_path) != channel["packet_sha256"]:
                raise HandoffError(f"bundle packet bozuk: {packet_path}")
            try:
                document = read_packet(packet_path, expected={
                    "film_id": manifest["film_id"], "section": manifest["section"],
                    "run_id": manifest["run_id"], "task_id": channel["task_id"]},
                    verify_assets=True)
            except ContractError as exc:
                raise HandoffError(f"bundle packet sozlesme disi: {packet_path}: {exc}") from exc
            producer = (document.get("producer") or {}).get("id")
            expected_producer = self.config.tower(channel["logical_role"])["producer_id"]
            if producer != channel.get("producer") or producer != expected_producer:
                raise HandoffError(f"bundle producer uyusmuyor: {producer!r}")
            status = document["status"]
            if (status["execution"] != channel.get("execution_status")
                    or status["content"] != channel.get("content_status")
                    or status["proof"] != channel.get("proof_status")):
                raise HandoffError(f"bundle kanal statusu packet ile uyusmuyor: {producer}")
        proof_ready = [channel["producer"] for channel in channels
                       if channel["proof_status"] == "COMPLETE"]
        if manifest.get("proof_ready_channels") != proof_ready:
            raise HandoffError("bundle proof_ready_channels kanal durumlariyla uyusmuyor")

    @staticmethod
    def _input_fingerprint(readers: list[dict[str, Any]]) -> str:
        inputs = []
        for reader in sorted(readers, key=lambda item: item.get("logical_role") or ""):
            result = reader.get("result") or {}
            packet_path = result.get("packet_path")
            packet_hash = (sha256_file(Path(packet_path))
                           if packet_path and Path(packet_path).is_file() else None)
            inputs.append({
                "logical_role": reader.get("logical_role"),
                "task_id": reader.get("task_id"),
                "status": reader.get("status"),
                "packet_sha256": packet_hash,
                "result_sha256": sha256_json(result) if not packet_hash else None,
            })
        return sha256_json(inputs)
