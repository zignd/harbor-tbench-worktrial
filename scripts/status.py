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


PHASE = {  # last ledger stage -> what the candidate is doing now
    "blueprint": "blueprint review",
    "blueprint_gate": "blueprint drafts",
    "author": "gates",
    "gate_static": "functional gates",
    "gate_functional": "quality / red-team",
    "gate_quality": "novelty / red-team",
    "gate_novelty": "red-team",
    "gate_redteam": "repair or calibration",
    "calibration_trial": "calibrating",
    "calibration": "tuning",
    "tune": "tuning",
}


def _live_authoring(cand_id: str) -> tuple[str, str] | None:
    """('authoring turn N', attempt) for an authoring run still in progress, if any."""
    for traj in sorted(Path(JOBS_DIR).glob(f"author-{cand_id}-a*/*/agent/trajectory.json")):
        trial = traj.parent.parent
        if not (trial / "result.json").exists():
            turns = len(json.loads(traj.read_text()).get("steps", []))
            return f"authoring turn {turns}", trial.parent.name.rsplit("-a", 1)[1]
    return None


def candidate_rows() -> tuple[str, list[str]]:
    """One line per candidate that isn't held: status, phase, attempt, last activity, verdict."""
    from generator.pipeline import CANDIDATES_DIR

    last: dict[str, dict] = {}
    path = Path(LEDGER_PATH)
    for line in path.read_text().splitlines() if path.exists() else []:
        e = json.loads(line)
        task = e["task"].rsplit("-t", 1)[0] if "-t" in e["task"][-3:] else e["task"]
        last[task] = e
    now = datetime.now(UTC)
    counts, rows = {}, []
    for d in sorted(CANDIDATES_DIR.glob("official-*")):
        status = (
            json.loads((d / "status.json").read_text())["status"]
            if (d / "status.json").exists()
            else "new"
        )
        counts[status] = counts.get(status, 0) + 1
        if status == "held":
            continue
        e = last.get(d.name)
        attempt = (e or {}).get("result", {}).get("attempt", "")
        age = ""
        if e:
            mins = (now - datetime.fromisoformat(e["ts"])).total_seconds() / 60
            age = f"{mins:.0f}m ago" if mins < 120 else f"{mins / 60:.0f}h ago"
        cal = (
            json.loads((d / "calibration.json").read_text())
            if (d / "calibration.json").exists()
            else None
        )
        verdict = f"{cal['verdict']} {''.join(o[0] for o in cal['outcomes'])}" if cal else ""
        phase = PHASE.get(e["stage"], e["stage"]) if e and status == "building" else ""
        if status in ("building", "gated"):
            live = _live_authoring(d.name)
            if live:
                phase, attempt = live
        slug = (
            json.loads((d / "blueprint.json").read_text())["slug"]
            if (d / "blueprint.json").exists()
            else "-"
        )
        line = f"{d.name[-12:]}  {slug[:30]:30}  {status:9}  {phase:22} a{attempt!s:3} {age:8} {verdict}"
        rows.append((status != "building", line))
    shipped = (
        sum(1 for p in Path("output").iterdir() if (p / "task.toml").exists())
        if Path("output").exists()
        else 0
    )
    summary = (
        ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        + f"  | shipped (learnable) {shipped}"
    )
    return summary, [r for _, r in sorted(rows)]


def main() -> int:
    print(f"status at {datetime.now(UTC):%H:%M} UTC")
    summary, rows = candidate_rows()
    print(f"\n== candidates: {summary}")
    print(
        "  id            slug                            status     phase                  att last     calibration (p=pass f=fail i=invalid)"
    )
    print("\n".join(f"  {r}" for r in rows) if rows else "  (none)")
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
    import sys
    import time

    if "--watch" in sys.argv:  # refresh every N seconds (default 30) until Ctrl-C
        args = sys.argv[sys.argv.index("--watch") + 1 :]
        every = int(args[0]) if args and args[0].isdigit() else 30
        while True:
            print("\033[2J\033[H", end="")
            main()
            time.sleep(every)
    raise SystemExit(main())
