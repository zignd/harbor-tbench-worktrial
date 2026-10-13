"""Hash only executable task inputs, not shipping metadata or mutable candidate records."""

import hashlib
from pathlib import Path

TASK_PATHS = ("instruction.md", "task.toml", "environment", "solution", "tests")
IGNORE = {".git", "__pycache__", ".pytest_cache", ".DS_Store"}


def package_hash(task_dir: Path) -> str:
    digest = hashlib.sha256()
    files = []
    for name in TASK_PATHS:
        p = task_dir / name
        files.extend(p.rglob("*") if p.is_dir() else [p])
    for p in sorted(files):
        if not p.is_file() or IGNORE.intersection(p.relative_to(task_dir).parts):
            continue
        if p.suffix == ".pyc":
            continue
        digest.update(p.relative_to(task_dir).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return digest.hexdigest()


def approval_errors(task_dir: Path, record: dict, models: str) -> list[str]:
    problems = []
    if record.get("package_hash") != package_hash(task_dir):
        problems.append("package hash mismatch")
    if record.get("models") != models:
        problems.append("model label mismatch")
    trials = record.get("trials", [])
    if len(trials) != 5:
        problems.append("five judged trials required")
    passes = 0
    instruction = (task_dir / "instruction.md").read_text()
    for t in trials:
        if t.get("turns", 0) and t.get("max_turns") and t["turns"] >= t["max_turns"]:
            problems.append("turn cap exhausted")
        if t.get("outcome") == "pass":
            passes += 1
            if not t.get("audit", {}).get("honest"):
                problems.append("unaudited or hacked pass")
        elif t.get("outcome") == "fail":
            failure = t.get("failure", {})
            quote = failure.get("instruction_quote", "").strip()
            if not failure.get("valid") or not quote or quote not in instruction:
                problems.append("invalid or unsupported failure")
        else:
            problems.append("invalid trial outcome")
    if not 1 <= passes <= 3:
        problems.append("outside 1-3/5 band")
    if record.get("quality_blocking_failures") != []:
        problems.append("quality approval missing or blocked")
    return problems
