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


HIGHLIGHT_SEC = 3.0  # how long a changed line stays highlighted


def watch(every: int) -> int:
    """Curses viewer: scroll with arrows/PgUp/PgDn/Home/End, q quits; changed lines are highlighted."""
    import contextlib
    import curses
    import io
    import threading
    import time

    state = {"lines": [], "changed": {}, "updated": 0.0, "busy": False}

    def refresh_loop() -> None:
        while True:
            state["busy"] = True
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    main()
            except Exception as exc:  # noqa: BLE001  keep the viewer alive on transient errors
                buf.write(f"error: {exc}\n")
            lines = buf.getvalue().splitlines()
            now = time.time()
            if state["lines"]:
                old = set(state["lines"])
                for ln in lines:
                    if ln not in old:
                        state["changed"][ln] = now
            state["lines"], state["updated"], state["busy"] = lines, now, False
            time.sleep(every)

    def ui(scr: curses.window) -> None:
        curses.curs_set(0)
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        scr.timeout(200)
        top = 0
        threading.Thread(target=refresh_loop, daemon=True).start()
        while True:
            h, w = scr.getmaxyx()
            lines = state["lines"]
            page = max(h - 1, 1)
            top = max(0, min(top, len(lines) - page))
            scr.erase()
            now = time.time()
            for row, ln in enumerate(lines[top : top + page]):
                hot = now - state["changed"].get(ln, 0) < HIGHLIGHT_SEC
                scr.addnstr(row, 0, ln, w - 1, curses.color_pair(1) if hot else 0)
            end = min(top + page, len(lines))
            foot = f" {top + 1}-{end}/{len(lines)}  ↑↓ PgUp/PgDn Home/End scroll · q quit"
            foot += "  · refreshing…" if state["busy"] else ""
            scr.addnstr(h - 1, 0, foot, w - 1, curses.A_REVERSE)
            scr.refresh()
            key = scr.getch()
            if key in (ord("q"), 27):
                return
            top += {
                curses.KEY_UP: -1, ord("k"): -1, curses.KEY_DOWN: 1, ord("j"): 1,
                curses.KEY_PPAGE: -page, curses.KEY_NPAGE: page,
                curses.KEY_HOME: -10**9, ord("g"): -10**9,
                curses.KEY_END: 10**9, ord("G"): 10**9,
            }.get(key, 0)  # fmt: skip

    try:
        curses.wrapper(ui)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    import sys

    if "--watch" in sys.argv:  # scrollable TUI, refreshed every N seconds (default 30)
        args = sys.argv[sys.argv.index("--watch") + 1 :]
        every = int(args[0]) if args and args[0].isdigit() else 30
        raise SystemExit(watch(every))
    raise SystemExit(main())
