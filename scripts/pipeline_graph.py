"""Pipeline graph for one candidate (`make watch`, Graph tab): where it is, what comes next, and
a time estimate.

Everything here is a pure function over the candidate's ledger events, so it is unit-tested
without the TUI. Estimates use the median duration of each stage over the official ledger
(falling back to defaults), so they get better as the ledger grows. They assume no repair
round; a failed gate shows the loop back to authoring and re-estimates from there.
"""

import json
import math
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rich.text import Text

# key, label, ledger stages that belong to the node
NODES = [
    ("blueprint", "blueprint + review", ("blueprint", "blueprint_gate")),
    ("author", "authoring (meta-task)", ("author",)),
    ("static", "structure · lint · leak scan", ("gate_static",)),
    ("functional", "build · oracle 3/3 · nop", ("gate_functional",)),
    ("quality", "quality check (harbor check)", ("gate_quality",)),
    (
        "novelty",
        "novelty · difficulty · red-team",
        ("gate_novelty", "gate_difficulty", "gate_redteam"),
    ),
    ("calibration", "calibration (<=5 trials, waves of 3)", ("calibration_trial",)),
    ("verdict", "audit · verdict · ship or tune", ("calibration", "tune")),
]
PARALLEL = ("quality", "novelty")
DEFAULT_SECONDS = {
    "blueprint": 120, "author": 900, "static": 15, "functional": 60,
    "quality": 130, "novelty": 160, "calibration": 150, "verdict": 60,
}  # fmt: skip
MAX_REPAIRS = 2
EXPECTED_TRIALS = 4  # exact curtailment needs 3.85-4.3 of 5 on average
WAVE = 3
ICON = {"done": "✔", "running": "▶", "pending": "○", "failed": "✖"}
STYLE = {"done": "green", "running": "bold yellow", "pending": "dim", "failed": "bold red"}


@dataclass
class NodeState:
    key: str
    label: str
    state: str  # done | running | pending | failed
    detail: str = ""
    seconds: float = 0.0  # time the node took, when done


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def stage_medians(path: Path, mode: str = "official") -> dict[str, float]:
    """Median seconds per ledger stage (events with a recorded duration)."""
    by_stage: dict[str, list[float]] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            e = json.loads(line)
            if e["mode"] == mode and e["seconds"] > 0:
                by_stage.setdefault(e["stage"], []).append(e["seconds"])
    return {s: statistics.median(v) for s, v in by_stage.items() if len(v) >= 3}


def node_seconds(medians: dict[str, float]) -> dict[str, float]:
    """Typical duration of each node: its stages' medians summed, else the default."""
    out = {}
    for key, _, stages in NODES:
        if key == "calibration":
            out[key] = medians.get("calibration_trial", DEFAULT_SECONDS[key])  # one wave
        elif key == "verdict":
            out[key] = DEFAULT_SECONDS[key]
        else:
            known = [medians[s] for s in stages if s in medians]
            out[key] = sum(known) if known else DEFAULT_SECONDS[key]
    return out


def _problems(e: dict) -> bool:
    return bool(e["result"].get("problems"))


def node_states(events: list[dict], live_turns: int | None = None, status: str = "building"):
    """(states, needs_repair, attempts) from a candidate's ledger events, oldest first."""
    last_author = max((i for i, e in enumerate(events) if e["stage"] == "author"), default=-1)
    attempts = sum(e["stage"] == "author" for e in events)
    since = events[last_author + 1 :]

    def latest(stages, evs):
        found = [e for e in evs if e["stage"] in stages]
        return found[-1] if found else None

    states: dict[str, NodeState] = {}
    labels = {k: label for k, label, _ in NODES}
    for key, label in labels.items():
        states[key] = NodeState(key, label, "pending")

    if latest(("blueprint", "blueprint_gate"), events) or last_author >= 0:
        states["blueprint"].state = "done"
    if live_turns is not None:
        states["author"] = NodeState(
            "author", labels["author"], "running", f"turn {live_turns}, attempt {attempts + 1}"
        )
    elif last_author >= 0:
        a = events[last_author]
        turns = a["result"].get("turns")
        detail = f"attempt {attempts}" + (f", {turns} turns" if turns else "")
        states["author"] = NodeState("author", labels["author"], "done", detail, a["seconds"])

    for key, stage in (("static", "gate_static"), ("functional", "gate_functional"),
                       ("quality", "gate_quality")):  # fmt: skip
        e = latest((stage,), since)
        if e:
            bad = _problems(e)
            detail = "; ".join(map(str, e["result"].get("problems", [])))[:60] if bad else ""
            states[key] = NodeState(key, labels[key], "failed" if bad else "done", detail,
                                    e["seconds"])  # fmt: skip

    nov = latest(("gate_novelty",), since)
    red = latest(("gate_redteam",), since)
    if nov and not nov["result"].get("novel", True):
        states["novelty"] = NodeState("novelty", labels["novelty"], "failed", "not novel")
    elif red:
        bad = bool(red["result"].get("hackable"))
        secs = (nov["seconds"] if nov else 0) + red["seconds"]
        states["novelty"] = NodeState("novelty", labels["novelty"],
                                      "failed" if bad else "done", "hackable" if bad else "", secs)  # fmt: skip
    elif nov:
        states["novelty"] = NodeState("novelty", labels["novelty"], "running", "novelty done")

    trials = [e for e in events if e["stage"] == "calibration_trial"]
    cal = latest(("calibration",), events)
    if cal:
        res = cal["result"]
        states["calibration"] = NodeState("calibration", labels["calibration"], "done",
                                          f"{res.get('passes')}/{res.get('trials')} passed")  # fmt: skip
        states["verdict"] = NodeState("verdict", labels["verdict"], "done", str(res.get("verdict")))
    elif trials:
        states["calibration"] = NodeState("calibration", labels["calibration"], "running",
                                          f"{len(trials)} trials judged")  # fmt: skip

    ordered = [states[k] for k, _, _ in NODES]
    repair = any(s.state == "failed" for s in ordered)
    if not repair and status == "building" and live_turns is None:
        # The first node not done is what the candidate is working on now.
        for s in ordered:
            if s.state == "pending":
                s.state = "running"
                if s.key == "quality" and states["novelty"].state == "pending":
                    states["novelty"].state = "running"  # they run side by side
                break
    return ordered, repair, attempts


def fmt_secs(s: float) -> str:
    s = max(int(s), 0)
    if s < 90:
        return f"{s}s"
    if s < 5400:
        return f"{round(s / 60)}m"
    return f"{s / 3600:.1f}h"


def estimate(
    states: list[NodeState], secs: dict[str, float], repair: bool, trials_done: int,
    elapsed_in_node: float,
) -> float:  # fmt: skip
    """Seconds left, assuming no further repair (after a failed gate: a repair round, then
    everything from authoring on). `elapsed_in_node` is the time since the last ledger event."""
    by_key = {s.key: s for s in states}
    todo = {s.key for s in states if s.state in ("pending", "running")}
    if repair:
        todo = {k for k, _, _ in NODES if k not in ("blueprint",)}
    cost = dict(secs)
    waves = max(1, math.ceil((EXPECTED_TRIALS - trials_done) / WAVE))
    cost["calibration"] = secs["calibration"] * waves
    total = 0.0
    for key, _, _ in NODES:
        if key not in todo or key == "novelty":
            continue
        seconds = cost[key]
        if key == "quality":  # side by side with novelty/red-team: the slower one counts
            seconds = max(seconds, cost["novelty"] if "novelty" in todo else 0.0)
        if by_key[key].state == "running" and not repair:
            seconds = max(seconds - elapsed_in_node, seconds * 0.15)
        total += seconds
    if "quality" not in todo and "novelty" in todo:
        total += cost["novelty"]
    return total


def render_graph(
    states: list[NodeState], secs: dict[str, float], repair: bool, attempts: int,
    eta: float | None, now: datetime, idle_min: float = 0.0,
) -> Text:  # fmt: skip
    out = Text()
    if idle_min > 45 and not repair:
        out.append(f" no ledger activity for {fmt_secs(idle_min * 60)}: it may have stopped\n\n",
                   style="bold red")  # fmt: skip
    by_key = {s.key: s for s in states}

    def line(s: NodeState, prefix: str = "") -> None:
        style = STYLE[s.state]
        out.append(f" {prefix}{ICON[s.state]} {s.label:38}", style=style)
        if s.state == "done":
            out.append(f"  {fmt_secs(s.seconds) if s.seconds else '':>5}", style="green")
        elif s.state == "running":
            out.append(f"  ~{fmt_secs(secs[s.key])} typical", style="yellow")
            out.append("   ← you are here", style="bold yellow")
        elif s.state == "failed":
            out.append("   ↺ back to authoring", style="red")
        else:
            out.append(f"  ~{fmt_secs(secs[s.key])}", style="dim")
        if s.detail:
            out.append(f"  {s.detail}", style="dim italic")
        out.append("\n")

    keys = [k for k, _, _ in NODES]
    for k in keys:
        if k == "quality":
            out.append(" │\n ├─ in parallel ─┐\n", style="dim")
            line(by_key["quality"], "│ ")
            line(by_key["novelty"], "│ ")
            out.append(" ├───────────────┘\n", style="dim")
            continue
        if k == "novelty":
            continue
        if k != keys[0]:
            out.append(" │\n", style="dim")
        line(by_key[k])
    out.append("\n")
    if repair:
        if attempts > MAX_REPAIRS:
            out.append(" ↺ a gate failed and repairs are used up: regenerate from the blueprint\n",
                       style="red")  # fmt: skip
        else:
            out.append(f" ↺ a gate failed: repair round {attempts} of {MAX_REPAIRS}, then re-gate\n",
                       style="red")  # fmt: skip
    else:
        out.append(" ↺ if a gate fails: repair round (<=2) back to authoring, ~"
                   f"{fmt_secs(secs['author'])} each\n", style="dim")  # fmt: skip
    if eta is not None and eta < 1:
        out.append(" complete: nothing left to run\n", style="bold green")
    elif eta is not None:
        done_at = now.timestamp() + eta
        when = datetime.fromtimestamp(done_at, UTC).strftime("%H:%M")
        label = "after repair" if repair else "no repair assumed"
        out.append(f" estimate: ~{fmt_secs(eta)} left  (done ≈ {when}Z, {label})\n", style="bold")
    return out


def candidate_eta(
    events: list[dict], live_turns: int | None, status: str, secs: dict[str, float],
    now: datetime | None = None,
) -> float | None:  # fmt: skip
    """Seconds left for a building candidate (None for anything else)."""
    if status != "building":
        return None
    now = now or datetime.now(UTC)
    states, repair, _ = node_states(events, live_turns, status)
    trials = sum(e["stage"] == "calibration_trial" for e in events)
    last = _parse(events[-1]["ts"]) if events else now
    return estimate(states, secs, repair, trials, (now - last).total_seconds())
