#!/usr/bin/env python3
"""HAKEEM — Shaq kulesindeki paralel kanit-grafi karar motoru."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

KULE = Path(__file__).resolve().parent
sys.path.insert(0, str(KULE))

from sozlesme import atomic_json, utc_now  # noqa: E402
from src.hakeem import ENGINE_VERSION  # noqa: E402
from src.hakeem.io import crop_requests, locked, read_requests, write_result  # noqa: E402
from src.hakeem.kimlik import JsonKimlikSaglayici  # noqa: E402
from src.hakeem.kontrol import (KontrolHatasi, merge_answers, read_answers,
                                resolve_group, verify_answer)  # noqa: E402
from src.hakeem.motor import aggregate_status, decide  # noqa: E402
from src.hakeem.sozlesme import GirdiCifti, cift_oku, run_id  # noqa: E402
from src.kimlik import BosKimlikSaglayici  # noqa: E402


OUT = KULE / "out_hakeem"
BOLUMLER = ("giris", "cikis")


def _safe_id(value: str) -> str:
    if not value or value in (".", "..") or Path(value).name != value or "/" in value or "\\" in value:
        raise ValueError("film_id tek, guvenli bir dizin adi olmali")
    return value


def _config() -> tuple[dict[str, Any], str]:
    import yaml
    raw = yaml.safe_load((KULE / "config.yaml").read_text(encoding="utf-8")) or {}
    selected = {
        "hizalama": raw.get("hizalama", {}),
        "kontrol": raw.get("kontrol", {}),
        "hakeem": raw.get("hakeem", {}),
    }
    encoded = json.dumps(selected, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode()
    return selected, hashlib.sha256(encoded).hexdigest()


def _code_digest() -> str:
    files = [Path(__file__), KULE / "sozlesme.py", KULE / "src" / "normalizasyon.py",
             KULE / "src" / "roller.py", KULE / "src" / "kimlik.py",
             *sorted((KULE / "src" / "hakeem").glob("*.py"))]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode()); digest.update(b"\0"); digest.update(path.read_bytes()); digest.update(b"\0")
    return digest.hexdigest()


def _runtime() -> tuple[dict[str, str], str]:
    import PIL
    import yaml
    value = {"python": platform.python_version(), "pillow": PIL.__version__, "pyyaml": yaml.__version__}
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return value, hashlib.sha256(encoded).hexdigest()


def _provider(path: str | None):
    return JsonKimlikSaglayici(path) if path else BosKimlikSaglayici()


def _target(film_id: str, bolum: str) -> Path:
    return OUT / _safe_id(film_id) / bolum


def _channels(cift: GirdiCifti) -> list[dict[str, Any]]:
    return [{"channel": channel.ad, "producer_id": channel.paket.producer_id,
             "engine_family": channel.paket.raw["producer"]["engine_family"],
             "model_digest": channel.paket.raw["producer"]["model_digest"],
             "independence_key": channel.independence_key,
             "packet_sha256": channel.packet_sha256, "source": str(channel.paket.path)}
            for channel in cift.kanallar]


def _error_output(film_id: str, bolum: str, exc: Exception) -> dict[str, Any]:
    error_id = hashlib.sha256(f"{film_id}\0{bolum}\0{type(exc).__name__}\0{exc}".encode()).hexdigest()[:24]
    return {"schema_version": "mitas.hakeem/v1", "engine_version": ENGINE_VERSION,
            "run_id": f"hk-error-{error_id}", "film_id": film_id, "bolum": bolum,
            "durum": "ARIZA", "uretim_zamani": utc_now(), "channels": [], "input_statuses": [],
            "config_digest": None, "kimlik_saglayici": "none", "groups": [],
            "ariza": {"sinif": "GIRDI_VEYA_KULE", "mesaj": f"{type(exc).__name__}: {exc}"}}


def tek(film_dir: str | Path, film_id: str, bolum: str, kimlik_json: str | None = None,
        *, force: bool = False) -> Path:
    film_id = _safe_id(film_id)
    if bolum not in BOLUMLER:
        raise ValueError(f"gecersiz bolum: {bolum}")
    target = _target(film_id, bolum)
    with locked(target):
        try:
            config, config_digest = _config()
            cift = cift_oku(film_dir, film_id, bolum)
            provider = _provider(kimlik_json)
            code_digest = _code_digest()
            runtime, runtime_digest = _runtime()
            current_run = run_id(cift, config_digest, ENGINE_VERSION, provider.version,
                                 code_digest, runtime_digest)
            result_path = target / "hakeem.json"
            if not force and (target / "_TAMAM").exists() and result_path.exists():
                existing = json.loads(result_path.read_text(encoding="utf-8"))
                if existing.get("run_id") == current_run:
                    return result_path
            max_edits = int(config.get("hizalama", {}).get("max_edit", 3))
            min_pad = int(config.get("kontrol", {}).get("context_min_pad_px", 20))
            if max_edits < 0 or min_pad < 0:
                raise ValueError("HAKEEM config esikleri negatif olamaz")
            raw_a, raw_b = cift.kanallar[0].paket.raw, cift.kanallar[1].paket.raw
            status, groups, requests, error = decide(
                film_id=film_id, bolum=bolum, run_id=current_run,
                raw_a=raw_a, raw_b=raw_b, provider=provider, max_edits=max_edits)
            crop_requests(requests, target, current_run, min_pad_px=min_pad)
            output = {
                "schema_version": "mitas.hakeem/v1", "engine_version": ENGINE_VERSION,
                "run_id": current_run, "film_id": film_id, "bolum": bolum, "durum": status,
                "uretim_zamani": utc_now(), "channels": _channels(cift),
                "input_statuses": [channel.paket.durum for channel in cift.kanallar],
                "config_digest": config_digest, "code_digest": code_digest,
                "runtime": runtime, "runtime_digest": runtime_digest,
                "kimlik_saglayici": provider.version,
                "groups": groups,
            }
            if error:
                output["ariza"] = error
        except Exception as exc:
            output, requests = _error_output(film_id, bolum, exc), []
        return write_result(target, output, requests)


def _manifest(film_id: str) -> Path:
    film_root = OUT / _safe_id(film_id)
    with locked(film_root):
        statuses: dict[str, dict[str, Any]] = {}
        for bolum in BOLUMLER:
            path = film_root / bolum / "hakeem.json"
            marker = film_root / bolum / "_TAMAM"
            if path.exists() and marker.exists():
                value = json.loads(path.read_text(encoding="utf-8"))
                statuses[bolum] = {"durum": value.get("durum"), "run_id": value.get("run_id")}
            else:
                statuses[bolum] = {"durum": "EKSIK", "run_id": None}
        qc1_ready = all(value["durum"] in ("GECTI", "METIN_YOK") for value in statuses.values())
        manifest = {"schema_version": "mitas.hakeem.film/v1", "film_id": film_id,
                    "uretim_zamani": utc_now(), "sections": statuses,
                    "qc1_ready": qc1_ready,
                    "durum": "GECTI" if qc1_ready else "BLOKE"}
        marker = film_root / "_TAMAM"
        marker.unlink(missing_ok=True)
        atomic_json(film_root / "manifest.json", manifest)
        marker.write_text("", encoding="utf-8")
    return film_root / "manifest.json"


def film(film_dir: str | Path, film_id: str, kimlik_json: str | None = None,
         *, force: bool = False) -> Path:
    film_id = _safe_id(film_id)
    # Dort dosya kapisi: iki bolum de cagrilir; eksik bolum acik ARIZA olur.
    for bolum in BOLUMLER:
        tek(film_dir, film_id, bolum, kimlik_json, force=force)
    return _manifest(film_id)


def tamamla(film_id: str, bolum: str, answers_path: str | Path) -> Path:
    film_id = _safe_id(film_id)
    target = _target(film_id, bolum)
    with locked(target):
        if not (target / "_TAMAM").exists():
            raise KontrolHatasi("HAKEEM sonucu tamamlanmis degil; _TAMAM yok")
        existing = json.loads((target / "hakeem.json").read_text(encoding="utf-8"))
        if existing.get("durum") != "KONTROL_BEKLIYOR":
            raise KontrolHatasi(f"sonuc kontrol beklemiyor: {existing.get('durum')}")
        config, current_config_digest = _config()
        if current_config_digest != existing.get("config_digest"):
            raise KontrolHatasi("HAKEEM config degismis; eski kontrol cevabi uygulanamaz, yeni run gerekir")
        if _code_digest() != existing.get("code_digest"):
            raise KontrolHatasi("HAKEEM kodu degismis; eski kontrol cevabi uygulanamaz, yeni run gerekir")
        _, current_runtime_digest = _runtime()
        if current_runtime_digest != existing.get("runtime_digest"):
            raise KontrolHatasi("HAKEEM calisma zamani degismis; yeni run gerekir")
        min_novel = int(config.get("hakeem", {}).get("min_novel_independent_control_answers", 2))
        if min_novel < 2:
            raise KontrolHatasi("yeni metin icin en az iki bagimsiz kontrol zorunlu")
        requests = read_requests(target)
        incoming = read_answers(answers_path)
        group_by_request = {request_id: group for group in existing.get("groups", [])
                            for request_id in group.get("control_request_ids", [])}
        source_models = {channel.get("model_digest") for channel in existing.get("channels", [])}
        prior_answers = {answer.get("answer_id"): answer
                         for group in existing.get("groups", [])
                         for bucket in group.get("control_answers", {}).values()
                         for answer in bucket}
        for answer in incoming:
            request_id = answer["request_id"]
            if request_id not in requests or request_id not in group_by_request:
                raise KontrolHatasi(f"bilinmeyen veya artik kapali request_id: {request_id}")
            if answer["producer"]["model_digest"] in source_models:
                raise KontrolHatasi("kontrol modeli kaynak okuma modellerinden bagimsiz olmali")
            previous = prior_answers.get(answer["answer_id"])
            if previous is not None and previous != answer:
                raise KontrolHatasi(f"answer_id farkli icerikle tekrar kullanildi: {answer['answer_id']}")
            verify_answer(answer, requests[request_id])
        for group in existing.get("groups", []):
            relevant = [answer for answer in incoming if answer["request_id"] in group.get("control_request_ids", [])]
            merge_answers(group, relevant)
            resolve_group(group, min_novel_independent_answers=min_novel)
        existing["durum"] = aggregate_status(existing.get("groups", []))
        existing["uretim_zamani"] = utc_now()
        if existing["durum"] == "ARIZA":
            existing["ariza"] = {"sinif": "KONTROL_MOTORU", "mesaj": "en az bir bbox kontrolu ARIZA"}
        else:
            existing.pop("ariza", None)
        pending_ids = {request_id for group in existing.get("groups", [])
                       if group.get("decision") == "KONTROL_GEREKLI"
                       for request_id in group.get("control_request_ids", [])}
        pending = [request for request_id, request in requests.items() if request_id in pending_ids]
        path = write_result(target, existing, pending)
    _manifest(film_id)
    return path


def start(input_root: str | Path, kimlik_json: str | None = None, *, limit: int | None = None,
          force: bool = False) -> list[Path]:
    root = Path(input_root)
    if not root.is_dir():
        raise ValueError(f"input dizini yok: {root}")
    films = sorted(path for path in root.iterdir() if path.is_dir())
    if limit is not None:
        films = films[:limit]
    return [film(path, path.name, kimlik_json, force=force) for path in films]


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    subs = root.add_subparsers(dest="command", required=True)
    one = subs.add_parser("tek")
    one.add_argument("--film-dir", required=True); one.add_argument("--film-id", required=True)
    one.add_argument("--bolum", choices=BOLUMLER, default="cikis"); one.add_argument("--kimlik-json")
    one.add_argument("--force", action="store_true")
    whole = subs.add_parser("film")
    whole.add_argument("--film-dir", required=True); whole.add_argument("--film-id", required=True)
    whole.add_argument("--kimlik-json"); whole.add_argument("--force", action="store_true")
    many = subs.add_parser("start")
    many.add_argument("--input", required=True); many.add_argument("--kimlik-json")
    many.add_argument("--limit", type=int); many.add_argument("--force", action="store_true")
    done = subs.add_parser("tamamla")
    done.add_argument("--film-id", required=True); done.add_argument("--bolum", choices=BOLUMLER, required=True)
    done.add_argument("--cevaplar", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "tek":
        print(tek(args.film_dir, args.film_id, args.bolum, args.kimlik_json, force=args.force)); return 0
    if args.command == "film":
        print(film(args.film_dir, args.film_id, args.kimlik_json, force=args.force)); return 0
    if args.command == "start":
        paths = start(args.input, args.kimlik_json, limit=args.limit, force=args.force)
        print(json.dumps({"film_sayisi": len(paths), "manifestler": [str(path) for path in paths]}, ensure_ascii=False)); return 0
    print(tamamla(args.film_id, args.bolum, args.cevaplar)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
