"""Candidate pipeline: spec -> blueprint -> authored task -> gates (cheapest first).

Each candidate lives in runs/candidates/<id>/ (spec, blueprint, decisions, the
authored task) and every stage records a ledger event. Gate order is by cost:

    structural validator, lint, leak scan        free, seconds
    functional: docker build, oracle 3/3, nop 0  free, ~1-3 min
    quality: `harbor check` with our rubric      ~$0.13
    novelty re-check of the final instruction    ~$0.02

A failed gate feeds its findings into a repair round of the authoring
meta-task (at most MAX_REPAIRS); after that the candidate is regenerated from
its blueprint once, then dropped. Calibration against Opus is a separate stage
(evaluator/calibrate.py) that only sees candidates that passed every gate.
"""

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from analysis import budget
from analysis.ledger import Event, Ledger, hash_dir
from evaluator.harbor_runner import run_with_retries
from evaluator.quality import run_check
from generator.author import collect_package, make_task_toml, render_metatask
from generator.blueprint import Blueprint, gate_blueprint, make_blueprint
from generator.config import (
    CANARY_LINE,
    DEV_MODE,
    JOBS_DIR,
    METATASK_MAX_TURNS,
    METATASK_SUMMARIZE_THRESHOLD,
    MODEL,
    OUTPUT_DIR,
    RUN_MODE,
    RUNS_DIR,
)
from generator.spec import TaskSpec
from validator import leak_scan, novelty
from validator.lint import errors as lint_errors
from validator.lint import lint_task
from validator.validate import validate_task

MAX_REPAIRS = 2
ORACLE_RUNS = 3
EXPECTED_AUTHOR_USD = 3.0
EXPECTED_CHECK_USD = 0.2
# Dev-mode candidates are plumbing only: keep them out of the committed evidence.
CANDIDATES_DIR = Path(OUTPUT_DIR if DEV_MODE else RUNS_DIR) / "candidates"


@dataclass
class Candidate:
    spec: TaskSpec
    cand_id: str = ""
    blueprint: Blueprint | None = None
    status: str = "new"  # new | rejected | authored | gated | failed
    history: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self.cand_id = self.cand_id or f"{RUN_MODE}-{self.spec.spec_id}"

    @property
    def dir(self) -> Path:
        return CANDIDATES_DIR / self.cand_id

    @property
    def task_dir(self) -> Path:
        return self.dir / "task"

    def save(self, name: str, data) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / name).write_text(json.dumps(data, indent=1, default=str))


def _record(
    ledger: Ledger, cand: Candidate, stage: str, result: dict, cost=0.0, t0=None, inputs_hash=""
) -> None:
    seconds = time.monotonic() - t0 if t0 else 0.0
    ledger.append(
        Event(stage, cand.cand_id, result, cost_usd=cost, seconds=seconds, inputs_hash=inputs_hash)
    )
    cand.history.append({"stage": stage, **result})


def stage_blueprint(cand: Candidate, ledger: Ledger) -> bool:
    budget.check(0.3)
    t0 = time.monotonic()
    bp, cost = make_blueprint(cand.spec)
    cand.blueprint = bp
    cand.save("spec.json", cand.spec.model_dump())
    cand.save("blueprint.json", bp.model_dump())
    _record(
        ledger,
        cand,
        "blueprint",
        {"slug": bp.slug, "predicted": bp.predicted_pass_rate},
        cost,
        t0,
        cand.spec.spec_id,
    )
    t0 = time.monotonic()
    decision = gate_blueprint(bp, cand.spec)
    cand.save("blueprint_gate.json", decision)
    _record(
        ledger,
        cand,
        "blueprint_gate",
        {
            "accepted": decision["accepted"],
            "scores": decision["review"].get("scores"),
            "novel": decision["novelty"]["novel"],
        },
        decision["cost_usd"],
        t0,
        cand.spec.spec_id,
    )
    if not decision["accepted"]:
        cand.status = "rejected"
    return decision["accepted"]


def stage_author(
    cand: Candidate,
    ledger: Ledger,
    attempt: int,
    feedback: list[str] | None = None,
    previous: Path | None = None,
) -> bool:
    budget.check(EXPECTED_AUTHOR_USD)
    t0 = time.monotonic()
    name = f"author-{cand.cand_id}-a{attempt}"
    meta_dir = Path(JOBS_DIR) / "metatasks" / name
    bp = cand.blueprint
    task_toml = make_task_toml(bp.slug, bp.title, bp.difficulty, bp.category, bp.tags)
    render_metatask(
        bp.to_markdown(cand.spec),
        bp.slug,
        meta_dir,
        task_toml,
        previous=previous,
        feedback=feedback,
    )
    if (Path(JOBS_DIR) / name).exists():
        shutil.rmtree(Path(JOBS_DIR) / name)
    counted, excluded = run_with_retries(
        meta_dir,
        "terminus-2",
        name,
        model=f"openrouter/{MODEL}",
        agent_kwargs={
            "max_turns": METATASK_MAX_TURNS,
            "proactive_summarization_threshold": METATASK_SUMMARIZE_THRESHOLD,
        },
    )
    trials = counted + excluded
    cost = sum(t.priced_cost() for t in trials)
    trial = counted[0] if counted else None
    result = {
        "attempt": attempt,
        "repair": previous is not None,
        "outcome": trial.outcome if trial else "infra",
        "turns": trial.n_episodes if trial else None,
    }
    ok = False
    if trial is not None:
        try:
            collect_package(trial.trial_dir, cand.task_dir, task_toml)
            ok = True
        except FileNotFoundError as e:
            result["error"] = str(e)
    _record(ledger, cand, "author", result, cost, t0)
    cand.status = "authored" if ok else "failed"
    return ok


def gate_static(task_dir: Path, tag: str) -> list[str]:
    problems = [f"structure: {e}" for e in validate_task(str(task_dir))["errors"]]
    problems += [f"lint: {e}" for e in lint_errors(lint_task(task_dir, CANARY_LINE))]
    if not problems:
        scan = leak_scan.scan(task_dir, tag)
        if not scan["built"]:
            problems.append(f"docker build failed: {scan.get('error', '')[-600:]}")
        problems += [f"leak: {leak}" for leak in scan["leaks"]]
    return problems


def gate_functional(task_dir: Path, name: str) -> tuple[list[str], dict]:
    oracle, oracle_x = run_with_retries(
        task_dir, "oracle", f"{name}-oracle", attempts=ORACLE_RUNS, concurrent=ORACLE_RUNS
    )
    nop, nop_x = run_with_retries(task_dir, "nop", f"{name}-nop")
    result = {
        "oracle": [t.outcome for t in oracle],
        "nop": [t.outcome for t in nop],
        "excluded": len(oracle_x) + len(nop_x),
    }
    problems = []
    passes = sum(t.outcome == "pass" for t in oracle)
    if passes < ORACLE_RUNS:
        tail = ""
        failing = next((t for t in oracle if t.outcome != "pass"), None)
        if failing is not None:
            out = failing.trial_dir / "verifier" / "test-stdout.txt"
            tail = out.read_text()[-1500:] if out.exists() else failing.exception_message
        problems.append(f"oracle passed {passes}/{ORACLE_RUNS} (must be deterministic): {tail}")
    if any(t.outcome == "pass" for t in nop):
        problems.append("nop passed: tests pass on the unsolved environment")
    if oracle_x or nop_x or not oracle or not nop:
        problems.append("infrastructure errors during oracle/nop runs")
    return problems, result


def stage_gates(cand: Candidate, ledger: Ledger, attempt: int) -> list[str]:
    """Run gates cheapest-first; stop at the first failing group. Returns problems."""
    h = hash_dir(cand.task_dir)
    tag = f"claude-gate-{cand.cand_id}-a{attempt}".lower()
    t0 = time.monotonic()
    problems = gate_static(cand.task_dir, tag)
    _record(ledger, cand, "gate_static", {"problems": problems}, 0.0, t0, h)
    if problems:
        return problems
    t0 = time.monotonic()
    problems, result = gate_functional(cand.task_dir, f"gate-{cand.cand_id}-a{attempt}")
    _record(ledger, cand, "gate_functional", {**result, "problems": problems}, 0.0, t0, h)
    if problems:
        return problems
    budget.check(EXPECTED_CHECK_USD)
    t0 = time.monotonic()
    check = run_check(cand.task_dir, f"check-{cand.cand_id}-a{attempt}")
    cand.save(f"quality_a{attempt}.json", check)
    problems = check["blocking_failures"] or ([check["error"]] if "error" in check else [])
    _record(
        ledger,
        cand,
        "gate_quality",
        {"ok": check["ok"], "outcomes": check["outcomes"], "problems": problems},
        check["cost_usd"],
        t0,
        h,
    )
    if problems:
        return problems + check["advice"]
    t0 = time.monotonic()
    instruction = (cand.task_dir / "instruction.md").read_text()
    lexical = novelty.lexical_flags(instruction)
    judged = None if lexical else novelty.judge_same_task(instruction)
    novel = not lexical and bool(judged and judged["novel"])
    _record(
        ledger,
        cand,
        "gate_novelty",
        {"novel": novel, "lexical": lexical, "nearest": judged and judged["nearest"]},
        judged["cost_usd"] if judged else 0.0,
        t0,
        h,
    )
    if not novel:
        return [
            (
                "novelty: the final task resembles a published Terminal-Bench task "
                f"({lexical or (judged and judged['verdicts'])})"
            )
        ]
    return []


def build_candidate(cand: Candidate, ledger: Ledger) -> Candidate:
    """Blueprint (if needed) -> author -> gates, with repair rounds and one regeneration."""
    if cand.blueprint is None and not stage_blueprint(cand, ledger):
        cand.save("status.json", {"status": cand.status, "history": cand.history})
        return cand
    attempt = 0
    for regeneration in range(2):
        feedback, previous = None, None
        for _ in range(MAX_REPAIRS + 1):
            attempt += 1
            if not stage_author(cand, ledger, attempt, feedback, previous):
                break
            problems = stage_gates(cand, ledger, attempt)
            if not problems:
                cand.status = "gated"
                cand.save(
                    "status.json",
                    {"status": cand.status, "attempts": attempt, "history": cand.history},
                )
                return cand
            feedback, previous = problems, cand.dir / f"failed_a{attempt}"
            if previous.exists():
                shutil.rmtree(previous)
            shutil.copytree(cand.task_dir, previous)
        _ = regeneration  # second pass = fresh authoring from the same blueprint
    cand.status = "failed"
    cand.save("status.json", {"status": cand.status, "attempts": attempt, "history": cand.history})
    return cand
