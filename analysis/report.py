"""Pipeline report: reports/summary.md + reports/summary.json (README Part 3 + stretch goals).

Built only from evidence on disk: runs/ledger.jsonl (official-mode events) and
runs/candidates/*/ (spec, blueprint, gate decisions, calibration). Dev-mode
events are excluded; the report refuses to run in dev mode.

    uv run --env-file .env python -m analysis.report
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from analysis.curtailment import table as curtailment_table
from analysis.diversity import coverage, difficulty_spread, novelty_report, uniqueness
from analysis.human_likeness import stylometrics
from analysis.ledger import Ledger
from evaluator.calibrate import LEGIT_PASS, N_RUNS
from generator.config import (
    EXAMPLES_DIR,
    LEGACY_MODEL_LABEL,
    MODEL_LABEL,
    OUTPUT_DIR,
    REPO_ROOT,
    RUNS_DIR,
    assert_official_models,
)
from generator.pipeline import CANDIDATES_DIR
from generator.spec import TaskSpec
from validator.novelty import Index, RefTask, reference_sets

REPORTS_DIR = Path(REPO_ROOT) / "reports"


def _load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def candidate_label(d: Path) -> str:
    """Models that produced a candidate (candidates from before labels used Sonnet -> Opus)."""
    return (_load(d / "models.json") or {}).get("label", LEGACY_MODEL_LABEL)


def candidates() -> list[dict]:
    """Candidates of the configured model pair only: pairs are never mixed in one funnel."""
    rows = []
    for d in sorted(CANDIDATES_DIR.glob("official-*")):
        if candidate_label(d) != MODEL_LABEL:
            continue
        rows.append(
            {
                "id": d.name,
                "dir": d,
                "spec": _load(d / "spec.json"),
                "blueprint": _load(d / "blueprint.json"),
                "gate": _load(d / "blueprint_gate.json"),
                "status": (_load(d / "status.json") or {}).get("status", "in_progress"),
                "calibration": _load(d / "calibration.json"),
            }
        )
    return rows


def funnel(rows: list[dict], events) -> dict:
    by_task = defaultdict(list)
    for e in events:
        by_task[e.task].append(e)

    def passed(stage: str, key: str, ok) -> int:
        return sum(
            any(e.stage == stage and ok(e.result.get(key)) for e in by_task[r["id"]]) for r in rows
        )

    return {
        "candidates": len(rows),
        "blueprint_accepted": sum(bool(r["gate"] and r["gate"]["accepted"]) for r in rows),
        "authored": sum(any(e.stage == "author" for e in by_task[r["id"]]) for r in rows),
        "structurally_valid": passed("gate_static", "problems", lambda p: p == []),
        "functionally_correct": passed("gate_functional", "problems", lambda p: p == []),
        "quality_ok": passed("gate_quality", "ok", lambda v: v is True),
        "novel": passed("gate_novelty", "novel", lambda v: v is True),
        "redteam_clean": passed("gate_redteam", "hackable", lambda v: v is False),
        "gated": sum(r["status"] == "gated" for r in rows),
        "calibrated": sum(r["calibration"] is not None for r in rows),
        "learnable": sum(
            bool(r["calibration"] and r["calibration"]["verdict"] == "learnable") for r in rows
        ),
    }


def cost_and_time(events) -> dict:
    by_stage = defaultdict(lambda: [0.0, 0.0, 0])
    for e in events:
        s = by_stage[e.stage]
        s[0] += e.cost_usd
        s[1] += e.seconds
        s[2] += 1
    return {
        k: {"usd": round(v[0], 3), "minutes": round(v[1] / 60, 1), "events": v[2]}
        for k, v in sorted(by_stage.items())
    }


def calibration_stats(rows: list[dict]) -> dict:
    cal = [r for r in rows if r["calibration"]]
    hist = Counter()
    trials_run = 0
    predicted_vs_observed = []
    for r in cal:
        outcomes = r["calibration"]["outcomes"]
        trials_run += len(outcomes)
        if r["calibration"]["verdict"] in ("learnable", "too_easy", "too_hard"):
            hist[f"{outcomes.count(LEGIT_PASS)}/{len(outcomes)}"] += 1
            observed = outcomes.count(LEGIT_PASS) / len(outcomes)
            predicted_vs_observed.append((r["blueprint"]["predicted_pass_rate"], observed))
        else:
            hist[r["calibration"]["verdict"]] += 1
    naive = N_RUNS * len(cal)
    corr = None
    if len(predicted_vs_observed) >= 3:
        xs, ys = zip(*predicted_vs_observed, strict=True)
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((x - mx) * (y - my) for x, y in predicted_vs_observed)
        sx = sum((x - mx) ** 2 for x in xs) ** 0.5
        sy = sum((y - my) ** 2 for y in ys) ** 0.5
        corr = round(cov / (sx * sy), 3) if sx and sy else None
    return {
        "calibrated": len(cal),
        "histogram": dict(hist),
        "trials_run": trials_run,
        "trials_naive": naive,
        "trials_saved_pct": round(100 * (1 - trials_run / naive), 1) if naive else 0.0,
        "predicted_vs_observed": predicted_vs_observed,
        "prediction_correlation": corr,
    }


def novelty_layers(rows: list[dict], events) -> dict:
    """Rejects per novelty layer: lexical (n-gram/cosine) or the Sonnet judge, at blueprint
    time and on the finished package."""
    out = Counter()
    for r in rows:
        nov = (r["gate"] or {}).get("novelty") or {}
        if nov.get("lexical_flags"):
            out["blueprint_lexical"] += 1
        elif nov and not nov.get("novel", True):
            out["blueprint_judge"] += 1
    for e in events:
        if e.stage == "gate_novelty" and not e.result.get("novel"):
            out["package_lexical" if e.result.get("lexical") else "package_judge"] += 1
    checked = {
        "blueprints_checked": sum(bool((r["gate"] or {}).get("novelty")) for r in rows),
        "packages_checked": sum(e.stage == "gate_novelty" for e in events),
    }
    return checked | {k: out.get(k, 0) for k in (
        "blueprint_lexical", "blueprint_judge", "package_lexical", "package_judge"
    )}  # fmt: skip


def batches(rows: list[dict], events) -> list[dict]:
    """Per saved batch plan: funnel, red-team hackable rate and cost."""
    from generator.pipeline import Candidate

    out = []
    for plan in sorted((Path(RUNS_DIR) / "batches").glob("*.json")):
        ids = {Candidate(TaskSpec(**d)).cand_id for d in json.loads(plan.read_text())}
        mine = [r for r in rows if r["id"] in ids]
        evs = [e for e in events if re.sub(r"-(t|c|snap-[a-z_0-9]+)\d*$", "", e.task) in ids]
        red = [e for e in evs if e.stage == "gate_redteam"]
        out.append(
            {
                "batch": plan.stem,
                "candidates": len(ids),
                "gated": sum(r["status"] == "gated" for r in mine),
                "learnable": sum(
                    bool(r["calibration"] and r["calibration"]["verdict"] == "learnable")
                    for r in mine
                ),
                "redteam_runs": len(red),
                "redteam_hackable": sum(bool(e.result.get("hackable")) for e in red),
                "usd": round(sum(e.cost_usd for e in evs), 2),
            }
        )
    return out


def _cand_for(slug: str) -> str | None:
    for d in CANDIDATES_DIR.glob("official-*"):
        bp = _load(d / "blueprint.json")
        if bp and bp.get("slug") == slug:
            return d.name
    return None


def _mean_style(rows: dict) -> dict:
    if not rows:
        return {}
    keys = next(iter(rows.values())).keys()
    return {k: round(sum(r[k] for r in rows.values()) / len(rows), 1) for k in keys}


def build() -> dict:
    assert_official_models()
    ledger = Ledger()
    events = [e for e in ledger.events() if e.mode == "official" and e.models == MODEL_LABEL]
    rows = candidates()
    specs = [TaskSpec(**r["spec"]) for r in rows if r["spec"]]
    shipped = sorted(p for p in Path(OUTPUT_DIR).iterdir() if (p / "task.toml").exists())
    examples = sorted(p for p in Path(EXAMPLES_DIR).iterdir() if p.is_dir())
    report = {
        "funnel": funnel(rows, events),
        "cost_and_time": cost_and_time(events),
        "total_usd": round(sum(e.cost_usd for e in events), 2),
        "total_minutes": round(sum(e.seconds for e in events) / 60, 1),
        "calibration": calibration_stats(rows),
        "coverage": coverage(specs),
        "uniqueness_shipped": uniqueness([(p / "instruction.md").read_text() for p in shipped]),
        "uniqueness_generated": uniqueness(
            [
                (r["dir"] / "task" / "instruction.md").read_text()
                for r in rows
                if (r["dir"] / "task" / "instruction.md").exists()
            ]
        ),
        "novelty": novelty_report(
            {p.name: (p / "instruction.md").read_text() for p in shipped},
            examples=Index(
                tuple(RefTask(p.name, (p / "instruction.md").read_text(), "") for p in examples)
            ),
        ),
        "novelty_layers": novelty_layers(rows, events),
        "novelty_sets": [*reference_sets(), "examples"],
        "models": MODEL_LABEL,
        "batches": batches(rows, events),
        "difficulty": difficulty_spread(
            [r["blueprint"] for r in rows],
            [o for _, o in calibration_stats(rows)["predicted_vs_observed"]],
        ),
        "stylometrics": {
            "examples": {p.name: stylometrics(p) for p in examples},
            "shipped": {p.name: stylometrics(p) for p in shipped},
        },
        "shipped": [p.name for p in shipped],
        "curtailment": curtailment_table(),
        "quality_examples": _load(REPORTS_DIR / "quality_examples.json"),
        "quality_shipped": {
            p.name: _load(CANDIDATES_DIR / c / f)
            for p in shipped
            for c in [_cand_for(p.name)]
            if c
            for f in sorted(x.name for x in (CANDIDATES_DIR / c).glob("quality_a*.json"))[-1:]
        },
        "discrimination": _load(REPORTS_DIR / "discrimination.json"),
        "candidates": [
            {k: r[k] for k in ("id", "status")}
            | {
                "slug": (r["blueprint"] or {}).get("slug"),
                "verdict": (r["calibration"] or {}).get("verdict"),
                "outcomes": (r["calibration"] or {}).get("outcomes"),
            }
            for r in rows
        ],
    }
    return report


def to_markdown(rep: dict) -> str:
    f = rep["funnel"]
    lines = [
        "# Pipeline report",
        "",
        (
            "Generated by `python -m analysis.report` from "
            "`runs/ledger.jsonl` and `runs/candidates/` (official-mode evidence only)."
        ),
        "",
        (
            f"**Models** (generation | calibration): `{rep['models']}`. The 1-3 of 5 band is "
            "relative to the calibration model; candidates and events from other model pairs "
            "are excluded."
        ),
        "",
        "## Funnel (README Part 3)",
        "",
        "| Stage | Count |",
        "|---|---|",
    ]
    lines += [f"| {k.replace('_', ' ')} | {v} |" for k, v in f.items()]
    lines += [
        "",
        (
            f"**Total cost:** ${rep['total_usd']:.2f} · **total stage time:** "
            f"{rep['total_minutes']:.0f} min"
        ),
        "",
        "| Stage | USD | Minutes | Events |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {k} | {v['usd']:.2f} | {v['minutes']} | {v['events']} |"
        for k, v in rep["cost_and_time"].items()
    ]
    lines += [
        "",
        "Per batch:",
        "",
        "| Batch | Candidates | Gated | Learnable | Red-team hackable | USD |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {b['batch']} | {b['candidates']} | {b['gated']} | {b['learnable']} | "
        f"{b['redteam_hackable']}/{b['redteam_runs']} | {b['usd']:.2f} |"
        for b in rep["batches"]
    ]
    c = rep["calibration"]
    lines += [
        "",
        "## Calibration (terminus-2 + claude-opus-4.8)",
        "",
        f"Pass-count distribution: {c['histogram']}",
        (
            f"Trials run {c['trials_run']} vs {c['trials_naive']} naive "
            f"({c['trials_saved_pct']}% saved by exact curtailment and early stops)."
        ),
        (
            f"Blueprint-time predicted vs observed pass rate: correlation "
            f"{c['prediction_correlation']} over {len(c['predicted_vs_observed'])} tasks."
        ),
        "",
        "| Candidate | Slug | Status | Verdict | Outcomes |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['id']} | {r['slug']} | {r['status']} | {r['verdict']} | {r['outcomes']} |"
        for r in rep["candidates"]
    ]
    lines += ["", "## Diversity (stretch C)", "", "| Axis | Covered | Balance |", "|---|---|---|"]
    lines += [
        f"| {k} | {v['covered']}/{v['of']} | {v['balance']} |" for k, v in rep["coverage"].items()
    ]
    lines += [
        "",
        f"Shipped instructions: {rep['uniqueness_shipped']}",
        f"All generated instructions: {rep['uniqueness_generated']}",
        "",
        f"Difficulty spread: {rep['difficulty']}",
        "",
        f"Novelty reference sets used: {', '.join(rep['novelty_sets'])}",
        f"Novelty rejects per layer: {rep['novelty_layers']}",
        "",
        "Shipped tasks vs published Terminal-Bench (max cosine per set) and `examples/`:",
        "",
        "| Task | Nearest TB task | Cosine | Per-set max | Nearest example |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['task']} | {r['nearest_reference']} | {r['cosine']} | "
        f"{', '.join(f'{k} {v["max"]}' for k, v in r['by_set'].items())} | "
        f"{r.get('nearest_example')} ({r.get('example_cosine')}) |"
        for r in rep["novelty"]
    ]
    lines += [
        "",
        "## Cost-efficient evaluation (stretch A)",
        "",
        "Expected Opus trials per task (exact over all 2^5 sequences):",
        "",
        "| true p | P(in band) | exact curtailment | saved | 0/3 early reject | saved | recall |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['p']} | {r['p_in_band']} | {r['expected_trials']} | {r['saved_pct']}% | "
        f"{r['aggressive_trials']} | {r['aggressive_saved_pct']}% | {r['aggressive_recall']} |"
        for r in rep["curtailment"]
    ]
    lines += [
        "",
        (
            "Exact curtailment is lossless; the 0/3 early reject loses learnable tasks at low p, "
            "so it is reported, not used."
        ),
        "",
        "## Human-likeness (stretch D)",
        "",
    ]
    qe = rep.get("quality_examples") or {}
    if qe:
        lines += [
            "`harbor check` with the same 16-criterion rubric (passes / criteria):",
            "",
            "| Task | Set | Passed | Blocking failures |",
            "|---|---|---|---|",
        ]
        for name, q in qe.items():
            n_pass = sum(v == "pass" for v in q["outcomes"].values())
            lines.append(
                f"| {name} | example | {n_pass}/{len(q['outcomes'])} | "
                f"{len(q['blocking_failures'])} |"
            )
        for name, q in (rep.get("quality_shipped") or {}).items():
            if q:
                n_pass = sum(v == "pass" for v in q["outcomes"].values())
                lines.append(
                    f"| {name} | generated | {n_pass}/{len(q['outcomes'])} | "
                    f"{len(q['blocking_failures'])} |"
                )
    st = rep["stylometrics"]
    lines += [
        "",
        f"Mean stylometrics, examples: {_mean_style(st['examples'])}",
        f"Mean stylometrics, shipped: {_mean_style(st['shipped'])}",
    ]
    d = rep.get("discrimination")
    if d:
        lines += [
            "",
            (
                f"Blinded 'which is human-written?' test: accuracy {d['accuracy']:.0%} over "
                f"{len(d['pairs'])} pairs (50% = indistinguishable)."
            ),
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    rep = build()
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "summary.json").write_text(json.dumps(rep, indent=1, default=str))
    (REPORTS_DIR / "summary.md").write_text(to_markdown(rep))
    print(f"wrote {REPORTS_DIR / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
