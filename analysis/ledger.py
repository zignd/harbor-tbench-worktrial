"""Append-only JSONL ledger of pipeline stage results (runs/ledger.jsonl).

Every stage that does work records an Event: what ran, on which task, what it
cost, how long it took, and the result. The ledger is the evidence behind the
reported metrics, and it doubles as a cache: a stage whose inputs hash is
already recorded (in the same run mode) doesn't need to run again.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from generator.config import LEDGER_PATH, RUN_MODE

# Files that don't change a task's meaning, so they don't change its hash.
_HASH_IGNORE = {"__pycache__", ".pytest_cache", ".DS_Store", ".gitignore"}


def hash_dir(path: Path) -> str:
    """Content hash of a directory tree (relative paths + file bytes)."""
    digest = hashlib.sha256()
    for file in sorted(p for p in Path(path).rglob("*") if p.is_file()):
        rel = file.relative_to(path)
        if any(part in _HASH_IGNORE or part.endswith(".pyc") for part in rel.parts):
            continue
        digest.update(rel.as_posix().encode() + b"\0" + file.read_bytes() + b"\0")
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Event:
    stage: str
    task: str
    result: dict
    cost_usd: float = 0.0
    seconds: float = 0.0
    inputs_hash: str = ""
    mode: str = RUN_MODE
    ts: str = field(default_factory=_now)


class Ledger:
    def __init__(self, path: Path | str = LEDGER_PATH):
        self.path = Path(path)

    def append(self, event: Event) -> Event:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(event), sort_keys=True) + "\n")
        return event

    def events(
        self, stage: str | None = None, task: str | None = None, mode: str | None = None
    ) -> list[Event]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            e = Event(**json.loads(line))
            if (
                (stage is None or e.stage == stage)
                and (task is None or e.task == task)
                and (mode is None or e.mode == mode)
            ):
                out.append(e)
        return out

    def cached(self, stage: str, inputs_hash: str, mode: str = RUN_MODE) -> Event | None:
        """Latest event for this stage and inputs in this mode, if any."""
        matches = [e for e in self.events(stage=stage, mode=mode) if e.inputs_hash == inputs_hash]
        return matches[-1] if matches else None

    def total_cost(self, mode: str | None = None, stage: str | None = None) -> float:
        return sum(e.cost_usd for e in self.events(stage=stage, mode=mode))
