"""Aggregate the "who writes the task, who solves it" study (exploratory; docs/study-report.md).

Pure functions over `runs/study/results.json` task records, so every number in the report
traces to that file. Nothing here ships a task or feeds the work-trial funnel.

A task record has: author ("weak" | "strong"), valid (passed every free gate), valid_first_try,
author_cost, and `solves[solver]` = {passes, fails_valid, invalid, trials, cost}. A solve's
verdict follows the trial's rule: any invalid failure voids the measurement, otherwise the
pass count decides (0 too hard, 1-3 in band, 4-5 too easy).
"""

import json
import sys
from pathlib import Path

from generator.config import BAND_HIGH, BAND_LOW, RUNS_DIR

RESULTS = Path(RUNS_DIR) / "study" / "results.json"
ROLES = ("weak", "strong")
VERDICTS = ("in_band", "too_easy", "too_hard", "invalid")


def raw_band(passes: int) -> str:
    """The band from the pass count alone, ignoring validity."""
    if passes == 0:
        return "too_hard"
    return "in_band" if BAND_LOW <= passes <= BAND_HIGH else "too_easy"


def verdict(solve: dict) -> str:
    """Task verdict for one solver: an invalid failure voids it, else the pass count decides."""
    if solve["invalid"] > 0:
        return "invalid"
    return raw_band(solve["passes"])


def _counted(solve: dict) -> int:
    return solve["passes"] + solve["fails_valid"] + solve["invalid"]


def cell(tasks: list[dict], author: str, solver: str) -> dict:
    """Metrics for one author -> solver cell."""
    mine = [t for t in tasks if t["author"] == author]
    valid = [t for t in mine if t["valid"] and solver in t.get("solves", {})]
    solves = [t["solves"][solver] for t in valid]
    counts = {v: sum(verdict(s) == v for s in solves) for v in VERDICTS}
    raw = {v: sum(raw_band(s["passes"]) == v for s in solves) for v in VERDICTS[:3]}
    rates = [s["passes"] / _counted(s) for s in solves if _counted(s)]
    histogram = [sum(s["passes"] == k for s in solves) for k in range(6)]
    author_cost = sum(t.get("author_cost", 0.0) for t in mine)
    solve_cost = sum(s.get("cost", 0.0) for s in solves)
    n_band = counts["in_band"]
    return {
        "author": author,
        "solver": solver,
        "attempted": len(mine),
        "valid": len(valid),
        "valid_share": len(valid) / len(mine) if mine else 0.0,
        "verdicts": counts,
        "raw_band": raw,
        "in_band_share_of_valid": n_band / len(valid) if valid else 0.0,
        "in_band_share_of_attempted": n_band / len(mine) if mine else 0.0,
        "mean_pass_rate": sum(rates) / len(rates) if rates else None,
        "pass_histogram": histogram,
        "author_cost": round(author_cost, 4),
        "solve_cost": round(solve_cost, 4),
        "cost_per_task": round((author_cost + solve_cost) / len(mine), 4) if mine else None,
        "cost_per_in_band": round((author_cost + solve_cost) / n_band, 4) if n_band else None,
    }


def validity(tasks: list[dict], author: str) -> dict:
    mine = [t for t in tasks if t["author"] == author]
    return {
        "attempted": len(mine),
        "built": sum(bool(t.get("built")) for t in mine),
        "valid_first_try": sum(bool(t.get("valid_first_try")) for t in mine),
        "valid": sum(bool(t["valid"]) for t in mine),
        "author_cost": round(sum(t.get("author_cost", 0.0) for t in mine), 4),
    }


def summarize(tasks: list[dict]) -> dict:
    cells = {f"{a}->{s}": cell(tasks, a, s) for a in ROLES for s in ROLES}
    return {"cells": cells, "validity": {a: validity(tasks, a) for a in ROLES}}


def markdown_table(summary: dict) -> str:
    """The per-cell table used in the report and the findings."""
    rows = [
        (
            "| Author -> solver | Valid tasks | In band | Too easy | Too hard | Invalid | "
            "Mean pass rate | Pass counts 0..5 | $/in-band task |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, c in summary["cells"].items():
        v = c["verdicts"]
        mean = f"{c['mean_pass_rate']:.2f}" if c["mean_pass_rate"] is not None else "n/a"
        cost = f"${c['cost_per_in_band']:.2f}" if c["cost_per_in_band"] else "n/a"
        rows.append(
            f"| {name} | {c['valid']}/{c['attempted']} | {v['in_band']} | {v['too_easy']} | "
            f"{v['too_hard']} | {v['invalid']} | {mean} | {c['pass_histogram']} | {cost} |"
        )
    return "\n".join(rows)


def main() -> int:
    data = json.loads(RESULTS.read_text())
    summary = summarize(data["tasks"])
    print(markdown_table(summary))
    print(json.dumps(summary["validity"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
