"""Build a reproducible EN->TR FLORES devtest slice for MT benchmarking."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import tarfile
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FLORES_URL = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "cache" / "external_datasets" / "flores200"
DEFAULT_OUT = PROJECT_ROOT / "data" / "translate_eval" / "flores_en_tr_100.jsonl"
DEFAULT_REPORT = PROJECT_ROOT / "outputs" / "translate_eval" / "flores_en_tr_100_report.json"


def download_archive(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive_path = cache_dir / "flores200_dataset.tar.gz"
    if archive_path.exists() and archive_path.stat().st_size > 0:
        return archive_path
    urllib.request.urlretrieve(FLORES_URL, archive_path)
    return archive_path


def extract_archive(archive_path: Path, cache_dir: Path) -> Path:
    dataset_dir = cache_dir / "flores200_dataset"
    if (dataset_dir / "devtest" / "eng_Latn.devtest").exists():
        return dataset_dir
    with tarfile.open(archive_path, "r:gz") as archive:
        safe_extract_all(archive, cache_dir)
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Expected extracted dataset directory missing: {dataset_dir}")
    return dataset_dir


def safe_extract_all(archive: tarfile.TarFile, destination: Path) -> None:
    destination_resolved = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if destination_resolved not in (target, *target.parents):
            raise ValueError(f"Unsafe path in archive: {member.name}")
    archive.extractall(destination)


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]


def build_slice(dataset_dir: Path, *, seed: int, count: int) -> list[dict[str, object]]:
    source_path = dataset_dir / "devtest" / "eng_Latn.devtest"
    target_path = dataset_dir / "devtest" / "tur_Latn.devtest"
    if not source_path.exists() or not target_path.exists():
        raise FileNotFoundError(f"Missing FLORES devtest pair: {source_path} / {target_path}")

    sources = read_lines(source_path)
    refs = read_lines(target_path)
    if len(sources) != len(refs):
        raise ValueError(f"FLORES source/ref length mismatch: {len(sources)} != {len(refs)}")
    if count > len(sources):
        raise ValueError(f"Requested count {count} exceeds FLORES devtest size {len(sources)}")

    rng = random.Random(seed)
    indices = sorted(rng.sample(range(len(sources)), count))
    rows: list[dict[str, object]] = []
    for index in indices:
        src = sources[index].strip()
        ref = refs[index].strip()
        if not src or not ref:
            raise ValueError(f"Empty source/ref at FLORES index {index}")
        rows.append(
            {
                "src": src,
                "ref": ref,
                "domain": "flores_devtest",
                "seed": seed,
                "index": index,
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_report(path: Path, *, out_path: Path, cache_dir: Path, archive_path: Path, rows: list[dict[str, object]]) -> None:
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_url": FLORES_URL,
        "cache_dir": str(cache_dir),
        "archive_path": str(archive_path),
        "output_path": str(out_path),
        "row_count": len(rows),
        "seed": rows[0]["seed"] if rows else None,
        "first_indices": [row["index"] for row in rows[:10]],
        "empty_rows": sum(1 for row in rows if not row["src"] or not row["ref"]),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_path = download_archive(args.cache_dir)
    dataset_dir = extract_archive(archive_path, args.cache_dir)
    rows = build_slice(dataset_dir, seed=args.seed, count=args.count)
    write_jsonl(args.out, rows)
    write_report(args.report, out_path=args.out, cache_dir=args.cache_dir, archive_path=archive_path, rows=rows)
    print(f"[ok] wrote {len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
