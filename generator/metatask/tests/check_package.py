"""In-container completeness check for an authored task package (stdlib only)."""

import sys
import tomllib
from pathlib import Path

REQUIRED = [
    "task.toml",
    "instruction.md",
    "environment/Dockerfile",
    "solution/solve.sh",
    "tests/test.sh",
    "tests/test_outputs.py",
]


def check(root: Path) -> list[str]:
    problems = [f"missing {rel}" for rel in REQUIRED if not (root / rel).is_file()]
    if problems:
        return problems

    try:
        cfg = tomllib.loads((root / "task.toml").read_text())
    except tomllib.TOMLDecodeError as e:
        return [f"task.toml does not parse: {e}"]
    if cfg.get("agent", {}).get("timeout_sec", 0) < 3600:
        problems.append("[agent].timeout_sec must be >= 3600")
    if cfg.get("environment", {}).get("docker_image"):
        problems.append("task.toml must not set [environment].docker_image")
    if "/" not in cfg.get("task", {}).get("name", ""):
        problems.append("[task].name must be org/name")

    if "canary" in (root / "instruction.md").read_text().lower():
        problems.append("instruction.md must not contain the canary")
    for rel in ("solution/solve.sh", "environment/Dockerfile", "tests/test_outputs.py"):
        if "canary" not in (root / rel).read_text().lower():
            problems.append(f"{rel} is missing the canary line")
    if "reward.txt" not in (root / "tests/test.sh").read_text():
        problems.append("tests/test.sh never writes /logs/verifier/reward.txt")
    if "python:3.13-slim-bookworm" not in (root / "environment/Dockerfile").read_text():
        problems.append("Dockerfile must use FROM python:3.13-slim-bookworm")
    return problems


if __name__ == "__main__":
    found = check(Path(sys.argv[1]))
    for p in found:
        print(f"FAIL: {p}")
    print("OK" if not found else f"{len(found)} problem(s)")
    sys.exit(1 if found else 0)
