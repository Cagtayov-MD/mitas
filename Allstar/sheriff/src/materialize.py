from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .config import SheriffConfig
from .runner import run_capture
from .media import verify_frame_pool
from .util import atomic_write_json, hardlink_or_copy, sha256_file, sha256_json


class MaterializeError(RuntimeError):
    pass


class Materializer:
    def __init__(self, config: SheriffConfig) -> None:
        self.config = config

    def build(self, task: dict[str, Any], boundary: dict[str, Any], run_dir: Path,
              source: Path, *, heartbeat=None, should_cancel=None,
              input_fingerprint: str | None = None,
              on_process_start=None) -> dict[str, Any]:
        document = boundary.get("result", {}).get("document") or {}
        if document.get("durum") != "BULUNDU":
            raise MaterializeError("materialize yalniz BULUNDU sinirinda calisir")
        if input_fingerprint is None:
            input_fingerprint = sha256_json({
                "source": sha256_file(source) if source.is_file() else str(source),
                "boundary": boundary.get("result"),
            })
        section = task["section"]
        final = run_dir / "materialized" / section
        final.parent.mkdir(parents=True, exist_ok=True)
        manifest_path = final / "material.manifest.json"
        if manifest_path.is_file():
            try:
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._verify_existing(final, existing, expected_section=section,
                                      expected_film_id=task["film_id"])
                if existing.get("input_fingerprint") == input_fingerprint:
                    return existing
            except (OSError, ValueError, json.JSONDecodeError, MaterializeError):
                pass
        temp = Path(tempfile.mkdtemp(prefix=f".material-{section}-", dir=final.parent))
        try:
            resource_usage: dict[str, Any] = {}
            selected = self._selected_frames(document, boundary)
            frame_dir = temp / "frames"
            frame_dir.mkdir(parents=True)
            frame_contract = self._copy_frame_contract(selected, frame_dir, section)
            raw_rows = self._frame_rows(run_dir, section)
            copied_rows = []
            for path in sorted(selected.glob("*.png")):
                target = frame_dir / path.name
                method = hardlink_or_copy(path, target)
                source_row = raw_rows.get(path.name)
                if not source_row:
                    raise MaterializeError(
                        f"secili kare kaynak manifestte yok: {path.name}")
                if sha256_file(path) != source_row.get("sha256"):
                    raise MaterializeError(
                        f"secili kare kaynak kareyle byte-ayni degil: {path.name}")
                row = dict(source_row)
                row.update({"filename": target.name, "sha256": sha256_file(target),
                            "transfer": method, "origin_path": str(path.resolve())})
                copied_rows.append(row)
            if not copied_rows:
                raise MaterializeError(f"Kobe secili kare vermedi: {selected}")
            with (frame_dir / "frames.jsonl").open("w", encoding="utf-8") as handle:
                for row in copied_rows:
                    handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            frames_manifest = frame_dir / "frames.jsonl"
            frames_pool_sha256 = verify_frame_pool(
                frame_dir, expected_section=section,
                require_contiguous_sequence=frame_contract["frames_contiguous"])
            lebron_input_sha256 = sha256_json({
                "frames_pool_sha256": frames_pool_sha256,
                "frames_contract_sha256": frame_contract["frames_contract_sha256"],
            })
            clip_start, clip_end = self._clip_interval(document, run_dir, section)
            jordan_frame_dir = temp / "jordan_frames"
            jordan_frame_dir.mkdir(parents=True)
            jordan_rows = []
            raw_frame_dir = run_dir / "media" / "frames" / section
            for source_row in sorted(raw_rows.values(), key=lambda row: row["sequence"]):
                source_time = float(source_row["source_time_s"])
                if source_time < clip_start or source_time >= clip_end:
                    continue
                source_path = raw_frame_dir / str(source_row["filename"])
                target = jordan_frame_dir / source_path.name
                method = hardlink_or_copy(source_path, target)
                if sha256_file(target) != source_row.get("sha256"):
                    raise MaterializeError(
                        f"Jordan kaynak karesi hash uyusmazligi: {source_path.name}")
                row = dict(source_row)
                row.update({"transfer": method, "origin_path": str(source_path.resolve())})
                jordan_rows.append(row)
            if not jordan_rows:
                raise MaterializeError(
                    f"Jordan araliginda frame yok: {clip_start}..{clip_end}")
            jordan_manifest = jordan_frame_dir / "frames.jsonl"
            with jordan_manifest.open("w", encoding="utf-8") as handle:
                for row in jordan_rows:
                    handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            jordan_pool_sha256 = verify_frame_pool(
                jordan_frame_dir, expected_section=section,
                require_contiguous_sequence=False)
            clip = temp / "credits.mp4"
            self._clip(source, clip, clip_start, clip_end, heartbeat=heartbeat,
                       should_cancel=should_cancel, on_process_start=on_process_start,
                       metrics_sink=resource_usage)
            result = {
                "schema_version": "mitas.material/v1",
                "input_fingerprint": input_fingerprint,
                "film_id": task["film_id"], "section": section,
                "boundary_task_id": boundary["task_id"],
                "frames_dir": "frames", "frames_manifest": "frames/frames.jsonl",
                "frames_manifest_sha256": sha256_file(frames_manifest),
                "frames_pool_sha256": frames_pool_sha256,
                **frame_contract,
                "lebron_input_sha256": lebron_input_sha256,
                "frame_count": len(copied_rows),
                "jordan_frames_dir": "jordan_frames",
                "jordan_frames_manifest": "jordan_frames/frames.jsonl",
                "jordan_frames_manifest_sha256": sha256_file(jordan_manifest),
                "jordan_frames_pool_sha256": jordan_pool_sha256,
                "jordan_frame_count": len(jordan_rows), "clip": "credits.mp4",
                "clip_sha256": sha256_file(clip), "clip_start_s": clip_start,
                "clip_end_s": clip_end, "boundary": document,
                "resource_usage": resource_usage,
            }
            atomic_write_json(temp / "material.manifest.json", result)
            if final.exists():
                stale = final.with_name(f"{final.name}.stale-{os.getpid()}")
                if stale.exists():
                    shutil.rmtree(stale)
                os.replace(final, stale)
                os.replace(temp, final)
                shutil.rmtree(stale, ignore_errors=True)
                return result
            os.replace(temp, final)
            return result
        except Exception:
            shutil.rmtree(temp, ignore_errors=True)
            raise

    @staticmethod
    def _selected_frames(document: dict[str, Any], boundary: dict[str, Any]) -> Path:
        result_path = Path(boundary["result"]["result_path"])
        for artifact in document.get("uretilen") or []:
            if artifact.get("tip") == "kare":
                return (result_path.parent / str(artifact["yol"])).resolve()
        raise MaterializeError("Kobe sonucunda kare artefakti yok")

    @staticmethod
    def _frame_rows(run_dir: Path, section: str) -> dict[str, dict[str, Any]]:
        path = run_dir / "media" / "frames" / section / "frames.jsonl"
        rows = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            rows[row["filename"]] = row
        return rows

    @staticmethod
    def _copy_frame_contract(selected: Path, frame_dir: Path,
                             section: str) -> dict[str, Any]:
        """Kobe'nin kare-serisi sözleşmesini LeBron girdisine byte-aynı taşı.

        Girişte bu dosya zorunludur: ``mod=ardisik_aralik`` LeBron'a hem
        karelerin boşluksuz olduğunu hem statik kartlarda akıllı bıçağın
        susması gerektiğini söyler. Sadece PNG'leri kopyalamak bu bilgiyi
        sessizce kaybedip doğrudan zincir ile Sheriff sonucunu ayrıştırırdı.
        """
        source = selected / "_sinif.json"
        if not source.is_file():
            if section == "giris":
                raise MaterializeError(f"Kobe giris kare sozlesmesi yok: {source}")
            return {"frames_contract": None, "frames_contract_sha256": None,
                    "frames_contiguous": False}
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MaterializeError(f"Kobe kare sozlesmesi okunamadi: {source}: {exc}") from exc
        if not isinstance(data, dict):
            raise MaterializeError(f"Kobe kare sozlesmesi sozluk degil: {source}")
        target = frame_dir / "_sinif.json"
        hardlink_or_copy(source, target)
        source_hash = sha256_file(source)
        if sha256_file(target) != source_hash:
            raise MaterializeError(f"Kobe kare sozlesmesi aktarimda degisti: {source}")
        return {"frames_contract": "frames/_sinif.json",
                "frames_contract_sha256": source_hash,
                "frames_contiguous": data.get("mod") == "ardisik_aralik"}

    @staticmethod
    def _clip_interval(document: dict[str, Any], run_dir: Path,
                       section: str) -> tuple[float, float]:
        media = json.loads((run_dir / "media" / "media.manifest.json").read_text(
            encoding="utf-8"))
        window_start = float(media["sections"][section]["window_start_s"])
        duration = float(media["probe"]["duration_s"])
        local_boundary = Materializer._boundary_frame_time(document, run_dir, section)
        local_start = max(0.0, local_boundary - 10.0)
        start = min(duration, window_start + local_start)
        if section == "giris" and document.get("bitis_sn") is not None:
            end = min(duration, window_start + float(document["bitis_sn"]))
        else:
            end = duration
        if end <= start:
            raise MaterializeError(f"gecersiz klip araligi: {start}..{end}")
        return round(start, 6), round(end, 6)

    @staticmethod
    def _boundary_frame_time(document: dict[str, Any], run_dir: Path,
                             section: str) -> float:
        frame_no = document.get("baslangic_kare")
        if isinstance(frame_no, int) and not isinstance(frame_no, bool):
            rows = Materializer._frame_rows(run_dir, section)
            for row in rows.values():
                if row.get("sequence") == frame_no:
                    return float(row["section_time_s"])
        return float(document.get("baslangic_sn") or 0.0)

    def _clip(self, source: Path, target: Path, start: float, end: float, *,
              heartbeat=None, should_cancel=None, on_process_start=None,
              metrics_sink=None) -> None:
        temporary = target.with_suffix(".mp4.tmp")
        threads = max(1, int(self.config.resource_profile(
            "cpu_media").get("cpu_threads", 1)))
        cmd = [str(self.config.raw["media"]["ffmpeg"]), "-y", "-nostdin", "-v", "error",
               "-threads", str(threads), "-filter_threads", str(threads),
               "-ss", f"{start:.6f}", "-i", str(source), "-t", f"{end-start:.6f}",
               "-map", "0:v:0", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
               "-c:v", "libx264", "-preset", "ultrafast",
               "-crf", "0", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart",
               "-f", "mp4", "-threads", str(threads), str(temporary)]
        returncode, _, stderr = run_capture(
            cmd, timeout_s=int(self.config.raw["media"]["ffmpeg_timeout_seconds"]),
            heartbeat=heartbeat, should_cancel=should_cancel,
            on_start=on_process_start, metrics_sink=metrics_sink)
        if returncode or not temporary.is_file() or temporary.stat().st_size == 0:
            temporary.unlink(missing_ok=True)
            raise MaterializeError(f"jenerik klibi kesilemedi: {stderr[-500:]}")
        os.replace(temporary, target)

    @staticmethod
    def _verify_existing(root: Path, manifest: dict[str, Any], *,
                         expected_section: str | None = None,
                         expected_film_id: str | None = None) -> None:
        if (manifest.get("schema_version") != "mitas.material/v1"
                or (expected_section is not None
                    and manifest.get("section") != expected_section)
                or (expected_film_id is not None
                    and manifest.get("film_id") != expected_film_id)):
            raise MaterializeError("mevcut material schema/film/section gecersiz")
        clip = root / str(manifest.get("clip", ""))
        if not clip.is_file() or sha256_file(clip) != manifest.get("clip_sha256"):
            raise MaterializeError("mevcut jenerik klibi hash uyusmazligi")
        frame_manifest = root / str(manifest.get("frames_manifest", ""))
        if not frame_manifest.is_file():
            raise MaterializeError("mevcut frame manifest eksik")
        rows = [json.loads(line) for line in frame_manifest.read_text(
            encoding="utf-8").splitlines() if line.strip()]
        if len(rows) != int(manifest.get("frame_count", -1)):
            raise MaterializeError("mevcut frame sayisi uyusmazligi")
        frame_dir = frame_manifest.parent
        for row in rows:
            frame = frame_dir / str(row.get("filename", ""))
            if not frame.is_file() or sha256_file(frame) != row.get("sha256"):
                raise MaterializeError(f"mevcut frame hash uyusmazligi: {frame}")
        section = manifest.get("section")
        try:
            pool_sha256 = verify_frame_pool(
                frame_dir, expected_section=section,
                require_contiguous_sequence=bool(manifest.get("frames_contiguous")))
        except Exception as exc:
            raise MaterializeError(str(exc)) from exc
        if (manifest.get("frames_manifest_sha256") != sha256_file(frame_manifest)
                or manifest.get("frames_pool_sha256") != pool_sha256):
            raise MaterializeError("mevcut frame manifest/pool hash uyusmazligi")
        contract_rel = manifest.get("frames_contract")
        contract_hash = manifest.get("frames_contract_sha256")
        if section == "giris" and (not contract_rel or not contract_hash):
            raise MaterializeError("mevcut giris frame sozlesmesi eksik")
        if contract_rel:
            contract = root / str(contract_rel)
            if not contract.is_file() or sha256_file(contract) != contract_hash:
                raise MaterializeError("mevcut frame sozlesmesi hash uyusmazligi")
        expected_input_hash = sha256_json({
            "frames_pool_sha256": pool_sha256,
            "frames_contract_sha256": contract_hash,
        })
        if manifest.get("lebron_input_sha256") != expected_input_hash:
            raise MaterializeError("mevcut LeBron girdi hash'i uyusmuyor")
        jordan_manifest = root / str(manifest.get("jordan_frames_manifest", ""))
        if not jordan_manifest.is_file():
            raise MaterializeError("mevcut Jordan frame manifest eksik")
        jordan_rows = [json.loads(line) for line in jordan_manifest.read_text(
            encoding="utf-8").splitlines() if line.strip()]
        if len(jordan_rows) != int(manifest.get("jordan_frame_count", -1)):
            raise MaterializeError("mevcut Jordan frame sayisi uyusmazligi")
        try:
            jordan_pool_sha256 = verify_frame_pool(
                jordan_manifest.parent, expected_section=section,
                require_contiguous_sequence=False)
        except Exception as exc:
            raise MaterializeError(str(exc)) from exc
        if (manifest.get("jordan_frames_manifest_sha256") != sha256_file(jordan_manifest)
                or manifest.get("jordan_frames_pool_sha256") != jordan_pool_sha256):
            raise MaterializeError("mevcut Jordan frame manifest/pool hash uyusmazligi")
