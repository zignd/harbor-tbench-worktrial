"""One-screen status of background pipeline work (`make status`).

Shows running batch/calibration/tuning processes, active task containers,
the current turn of each unfinished authoring run, recent ledger events, and
live spend. Read-only: it never starts or stops anything.
"""

import json
import os
import re
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


def _pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError):
        return True
    return True


def candidate_records() -> tuple[dict[str, int], int, list[dict]]:
    """(status counts, shipped count, one record per candidate incl. held).

    Each record also says whether the candidate is really being worked on (`active`: its
    batch process is alive, or its last ledger event is recent), which models produced it
    (`label`), and how long it has been idle in minutes (`idle`).
    """
    from generator.config import LEGACY_MODEL_LABEL
    from generator.pipeline import CANDIDATES_DIR

    last: dict[str, dict] = {}
    path = Path(LEDGER_PATH)
    for line in path.read_text().splitlines() if path.exists() else []:
        e = json.loads(line)
        task = re.sub(r"-[tc]\d+$", "", e["task"])  # calibration/tuning names
        last[task] = e
    now = datetime.now(UTC)
    counts: dict[str, int] = {}
    records = []
    for d in sorted(CANDIDATES_DIR.glob("official-*")):
        status_file = (
            json.loads((d / "status.json").read_text()) if (d / "status.json").exists() else {}
        )
        status = status_file.get("status", "new")
        label = (
            json.loads((d / "models.json").read_text()).get("label", LEGACY_MODEL_LABEL)
            if (d / "models.json").exists()
            else LEGACY_MODEL_LABEL
        )
        counts[status] = counts.get(status, 0) + 1
        e = last.get(d.name)
        attempt = (e or {}).get("result", {}).get("attempt", "")
        age = ""
        idle = None
        if e:
            mins = (now - datetime.fromisoformat(e["ts"])).total_seconds() / 60
            idle = mins
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
        records.append(
            {
                "id": d.name,
                "path": d,
                "slug": slug,
                "status": status,
                "phase": phase,
                "attempt": str(attempt),
                "age": age,
                "verdict": verdict,
                "label": label,
                "idle": idle,
                "active": status == "building"
                and (_pid_alive(status_file.get("pid")) or (idle is not None and idle < 20)),
            }
        )
    shipped = (
        sum(1 for p in Path("output").iterdir() if (p / "task.toml").exists())
        if Path("output").exists()
        else 0
    )
    return counts, shipped, records


def candidate_rows() -> tuple[str, list[str]]:
    """One line per candidate that isn't held: status, phase, attempt, last activity, verdict."""
    counts, shipped, records = candidate_records()
    rows = []
    for r in records:
        if r["status"] == "held":
            continue
        line = (
            f"{r['id'][-12:]}  {r['slug'][:30]:30}  {r['status']:9}  {r['phase']:22} "
            f"a{r['attempt']:3} {r['age']:8} {r['verdict']}"
        )
        rows.append((r["status"] != "building", line))
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

    if "--watch" in sys.argv:  # interactive TUI, refreshed every N seconds (default 30)
        from scripts.watch_tui import run

        args = sys.argv[sys.argv.index("--watch") + 1 :]
        raise SystemExit(run(int(args[0]) if args and args[0].isdigit() else 30))
    raise SystemExit(main())
