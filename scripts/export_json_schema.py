from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Type

from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.schemas import CandidateRelation, Evidence, JobRun, MediaItem, ModuleRun, TimelineEvent  # noqa: E402


SCHEMA_DIR = ROOT / "schemas"
SCHEMAS: list[tuple[str, Type[BaseModel]]] = [
    ("media_item.schema.json", MediaItem),
    ("timeline_event.schema.json", TimelineEvent),
    ("evidence.schema.json", Evidence),
    ("candidate_relation.schema.json", CandidateRelation),
    ("job_run.schema.json", JobRun),
    ("module_run.schema.json", ModuleRun),
]


def main() -> int:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, model in SCHEMAS:
        schema = model.model_json_schema(ref_template="#/$defs/{model}")
        (SCHEMA_DIR / filename).write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(SCHEMA_DIR / filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
