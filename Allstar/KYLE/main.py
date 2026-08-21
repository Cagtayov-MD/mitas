from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sozlesme import Cikti, Girdi, GirdiHatasi
from src.eslesme import cluster_unknown
from src.girdi import InputError, read_source
from src.hafiza import ProfileError, create_profile, load_profile
from src.hizalama import annotate_sources
from src.karar import decide
from src.memory_patch import apply_patch, build_patch
from src.rapor import build_actor_roster, build_public_changes, write_json_atomic, write_pdf
from src.roller import load_roles


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def default_profile_path(series_id: str) -> Path:
    return HERE / "data" / "series" / series_id / "profile.json"


def run_one(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    sources = {k: v for k, v in {
        "jordan": args.jordan,
        "nash": args.nash,
        "lebron": args.lebron,
    }.items() if v}
    profile_path = Path(args.profile) if args.profile else default_profile_path(args.series_id)
    out_root = Path(args.out) if args.out else HERE / "out"

    try:
        girdi = Girdi(args.series_id, args.episode_id, sources, str(profile_path))
        memory = load_profile(profile_path, args.series_id)
        source_obs = {name: read_source(name, path) for name, path in girdi.sources.items()}
        if sum(bool(v) for v in source_obs.values()) < 2:
            raise InputError("en az iki kaynak bos olmayan observation vermeli")

        roles = load_roles(cfg)
        annotated = annotate_sources(source_obs, memory, roles, cfg)
        unknown = [x for x in annotated
                   if not x.is_metadata and not x.is_role_heading and not x.known_person_id]
        clusters = cluster_unknown(
            unknown,
            threshold=float(cfg["matching"]["unknown_cluster_threshold"]),
            min_chars=int(cfg["matching"]["min_name_chars"]),
        )
        decisions, review = decide(
            memory, roles, annotated, clusters,
            min_sources=int(cfg["matching"]["min_independent_sources"]),
        )
        decision_dicts = [d.as_dict() for d in decisions]

        evidence = {
            "source_counts": {k: len(v) for k, v in source_obs.items()},
            "known_matches": [
                {
                    "observation_id": x.observation.observation_id,
                    "source": x.observation.source,
                    "raw_text": x.observation.raw_text,
                    "role": x.known_role,
                    "canonical_name": x.known_name,
                    "score": round(x.known_score, 4),
                }
                for x in annotated if x.known_person_id
            ],
            "role_headings": [
                {
                    "observation_id": x.observation.observation_id,
                    "source": x.observation.source,
                    "raw_text": x.observation.raw_text,
                    "canonical_role": x.role,
                }
                for x in annotated if x.is_role_heading
            ],
            "ignored_metadata": [
                {
                    "observation_id": x.observation.observation_id,
                    "source": x.observation.source,
                    "raw_text": x.observation.raw_text,
                    "reason": x.review_reason,
                }
                for x in annotated if x.is_metadata
            ],
            "unresolved": review,
        }
        status = "DEGISIKLIK_VAR" if decision_dicts else "DEGISIKLIK_YOK"
        result = Cikti(args.series_id, args.episode_id, status,
                       changes=decision_dicts, review_candidates=review, evidence=evidence)
        result_path = result.write(out_root)
        out_dir = result_path.parent

        actors = build_actor_roster(annotated, decision_dicts)
        public = build_public_changes(
            args.series_id, args.episode_id, memory.title, decision_dicts, actors=actors)
        write_json_atomic(out_dir / "degisiklikler.json", public)
        write_json_atomic(out_dir / "kanit.json", evidence)
        patch = build_patch(memory, args.episode_id, decision_dicts)
        write_json_atomic(out_dir / "memory_patch.json", patch)
        if bool(cfg.get("report", {}).get("pdf", True)):
            write_pdf(out_dir / "rapor.pdf", public)

        (out_dir / "_TAMAM").write_text("", encoding="utf-8")
        print(result_path)
        return 0
    except (GirdiHatasi, InputError, ProfileError, ValueError, OSError) as exc:
        result = Cikti(args.series_id, args.episode_id, "ARIZA", sinif="GIRDI_HATASI", mesaj=str(exc))
        result_path = result.write(out_root)
        (result_path.parent / "_TAMAM").write_text("", encoding="utf-8")
        print(result_path)
        return 2
    except Exception as exc:
        result = Cikti(args.series_id, args.episode_id, "ARIZA", sinif="KYLE", mesaj=f"{type(exc).__name__}: {exc}")
        result_path = result.write(out_root)
        (result_path.parent / "_TAMAM").write_text("", encoding="utf-8")
        print(result_path)
        return 3


def cmd_profile_create(args: argparse.Namespace) -> int:
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    path = Path(args.profile) if args.profile else default_profile_path(args.series_id)
    create_profile(path, args.series_id, args.title or args.series_id, seed)
    print(path)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    profile = Path(args.profile) if args.profile else default_profile_path(args.series_id)
    patch = json.loads(Path(args.patch).read_text(encoding="utf-8"))
    apply_patch(profile, patch)
    print(profile)
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="KYLE - dizi jenerigi yeni kisi / degisiklik kulesi")
    p.add_argument("--config", default=str(HERE / "config.yaml"))
    sub = p.add_subparsers(dest="cmd", required=True)

    one = sub.add_parser("tek", help="tek bolumu karsilastir")
    one.add_argument("--series-id", required=True)
    one.add_argument("--episode-id", required=True)
    one.add_argument("--jordan")
    one.add_argument("--nash")
    one.add_argument("--lebron")
    one.add_argument("--profile")
    one.add_argument("--out")
    one.set_defaults(func=run_one)

    pc = sub.add_parser("profil-olustur", help="manuel ilk cast/crew seed'inden dizi hafizasi olustur")
    pc.add_argument("--series-id", required=True)
    pc.add_argument("--title")
    pc.add_argument("--seed", required=True, help="roles JSON dosyasi")
    pc.add_argument("--profile")
    pc.set_defaults(func=cmd_profile_create)

    ap = sub.add_parser("uygula", help="onaylanan memory_patch.json'u profile uygula")
    ap.add_argument("--series-id", required=True)
    ap.add_argument("--patch", required=True)
    ap.add_argument("--profile")
    ap.set_defaults(func=cmd_apply)
    return p


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
