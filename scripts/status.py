"""One-screen status of background pipeline work (`make status`).

Shows running batch/calibration/tuning processes, active task containers,
the current turn of each unfinished authoring run, recent ledger events, and
live spend. Read-only: it never starts or stops anything.
"""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from generator.config import JOBS_DIR, LEDGER_PATH

SCRIPTS = ("run_batch", "calibrate_candidates", "tune_candidates")


def _run(*cmd: str) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout


def processes() -> list[str]:
    out = []
    for line in _run("ps", "-eo", "etime=,command=").splitlines():
        # Only the interpreter itself, not the shell or `uv run` wrappers around it.
        if "/bin/python -m scripts." in line and any(s in line for s in SCRIPTS):
            etime, _, cmd = line.strip().partition(" ")
            out.append(f"{cmd.split('-m ', 1)[1][:90]}  (running {etime})")
    return out


def containers() -> list[str]:
    rows = _run("docker", "ps", "--format", "{{.Names}}\t{{.Status}}").splitlines()
    keep = ("author-", "gate-", "check-", "cal-", "redteam-", "quality-")
    return [r.replace("\t", "  ") for r in rows if r.startswith(keep)]


def authoring() -> list[str]:
    out = []
    for traj in sorted(Path(JOBS_DIR).glob("author-*/*/agent/trajectory.json")):
        trial = traj.parent.parent
        if (trial / "result.json").exists():
            continue
        steps = json.loads(traj.read_text()).get("steps", [])
        last = (steps[-1].get("message") or "")[:80].replace("\n", " ") if steps else ""
        out.append(f"{trial.parent.name}: turn {len(steps)}  {last}")
    return out


def recent_events(n: int = 8) -> list[str]:
    path = Path(LEDGER_PATH)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines()[-n:]:
        e = json.loads(line)
        result = {k: v for k, v in e["result"].items() if k not in ("audit", "failure", "plan")}
        rows.append(
            f"{e['ts'][11:16]}Z {e['stage']:18} {e['task'][-24:]:24} ${e['cost_usd']:.2f}  "
            f"{json.dumps(result)[:70]}"
        )
    return rows


def main() -> int:
    print(f"status at {datetime.now(UTC):%H:%M} UTC")
    for title, rows in [
        ("pipeline processes", processes()),
        ("task containers", containers()),
        ("authoring in progress", authoring()),
        ("recent ledger events", recent_events()),
    ]:
        print(f"\n== {title}")
        print("\n".join(f"  {r}" for r in rows) if rows else "  (none)")
    print("\n== spend")
    usage = _run(
        "uv", "run", "--quiet", "--env-file", ".env", "python", "-m", "scripts.openrouter_usage"
    )
    print("\n".join(f"  {line}" for line in usage.splitlines()[:4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
