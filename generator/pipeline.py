"""Candidate pipeline: spec -> blueprint -> authored task -> gates (cheapest first).

Each candidate lives in runs/candidates/<id>/ (spec, blueprint, decisions, the
authored task) and every stage records a ledger event. Gate order is by cost:

    structural validator, lint, leak scan        free, seconds
    functional: docker build, oracle 3/3, nop 0  free, ~1-3 min
    quality: `harbor check` with our rubric      ~$0.13
    novelty re-check of the final instruction    ~$0.02
    red-team: one Sonnet hack-elicitation run    ~$0.5-2

A failed gate feeds its findings into a repair round of the authoring
meta-task (at most MAX_REPAIRS); after that the candidate is regenerated from
its blueprint once, then dropped. Calibration against Opus is a separate stage
(evaluator/calibrate.py) that only sees candidates that passed every gate.
"""

import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from analysis import budget
from analysis.ledger import Event, Ledger, hash_dir
from evaluator.harbor_runner import run_with_retries
from evaluator.quality import run_check
from evaluator.redteam import redteam
from generator.author import collect_package, make_task_toml, render_metatask
from generator.blueprint import Blueprint, gate_blueprint, make_blueprint
from generator.config import (
    CANARY_LINE,
    DEV_MODE,
    JOBS_DIR,
    METATASK_MAX_TURNS,
    METATASK_REPAIR_MAX_TURNS,
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
BLUEPRINT_TRIES = 2
ORACLE_RUNS = 3
EXPECTED_AUTHOR_USD = 3.0
EXPECTED_CHECK_USD = 0.2
EXPECTED_REDTEAM_USD = 2.0
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


def _rejection_feedback(decision: dict) -> str:
    """Why a blueprint was rejected, phrased for the next attempt."""
    parts = []
    nov = decision["novelty"]
    if nov["lexical_flags"]:
        parts.append("it overlaps textually with: " + "; ".join(nov["lexical_flags"][:3]))
    for v in (nov.get("judge") or {}).get("verdicts", []):
        if v["verdict"] != "distinct":
            parts.append(f"it is a {v['verdict']} of {v['ref_id']} ({v['reason']})")
    if not decision["review"]["accepted"]:
        scores = decision["review"].get("scores", {})
        parts.append(f"the reviewer scored it {scores}: {decision['review'].get('reasons', '')}")
    return "; ".join(parts)


def stage_blueprint(cand: Candidate, ledger: Ledger) -> bool:
    """Blueprint + review + novelty gate; one retry told why the first was rejected."""
    index = novelty.gate_index(CANDIDATES_DIR, cand.cand_id)
    # Our own earlier tasks go in the "must not resemble" list too: without them, specs in
    # unrelated domains drifted back to the same ledger-reconciliation idea.
    concepts = novelty.concept_list(index)
    feedback = None
    for attempt in range(1, BLUEPRINT_TRIES + 1):
        budget.check(0.3)
        t0 = time.monotonic()
        bp, cost = make_blueprint(cand.spec, concepts, feedback=feedback)
        cand.blueprint = bp
        cand.save("spec.json", cand.spec.model_dump())
        cand.save("blueprint.json", bp.model_dump())
        _record(
            ledger,
            cand,
            "blueprint",
            {"slug": bp.slug, "predicted": bp.predicted_pass_rate, "attempt": attempt},
            cost,
            t0,
            cand.spec.spec_id,
        )
        t0 = time.monotonic()
        decision = gate_blueprint(bp, cand.spec, index)
        cand.save("blueprint_gate.json", decision)
        _record(
            ledger,
            cand,
            "blueprint_gate",
            {
                "accepted": decision["accepted"],
                "scores": decision["review"].get("scores"),
                "novel": decision["novelty"]["novel"],
                "attempt": attempt,
            },
            decision["cost_usd"],
            t0,
            cand.spec.spec_id,
        )
        if decision["accepted"]:
            return True
        cand.save(f"blueprint_rejected_{attempt}.json", {"blueprint": bp.model_dump(), **decision})
        feedback = _rejection_feedback(decision)
    cand.status = "rejected"
    return False


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
            "max_turns": METATASK_REPAIR_MAX_TURNS if previous else METATASK_MAX_TURNS,
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
    # The package's hash lets a resumed run recognise an attempt that was authored
    # but interrupted before its gates finished.
    _record(ledger, cand, "author", result, cost, t0, hash_dir(cand.task_dir) if ok else "")
    cand.status = "authored" if ok else "failed"
    return ok


def authored_unchanged(cand: Candidate, ledger: Ledger, attempt: int) -> bool:
    """True if `attempt` was already authored and task/ still holds exactly that package.

    The package's hash is on the author event (or, for events written before that, on
    the first gate event after it), so an interrupted attempt goes back to its gates
    instead of paying for authoring again.
    """
    if not cand.task_dir.exists():
        return False
    events = ledger.events(task=cand.cand_id)
    authors = [i for i, e in enumerate(events) if e.stage == "author"]
    if not authors:
        return False
    last = events[authors[-1]]
    if last.result.get("attempt") != attempt or "error" in last.result:
        return False
    if last.result.get("outcome") == "infra":
        return False
    h = hash_dir(cand.task_dir)
    after = events[authors[-1] + 1 :]
    return last.inputs_hash == h or any(
        e.stage.startswith("gate_") and e.inputs_hash == h for e in after[:1]
    )


def gate_static(task_dir: Path, tag: str) -> tuple[list[str], bool, bool]:
    """Structure + lint + build/leak scan. Returns (problems, structure_ok, built)."""
    structural = [f"structure: {e}" for e in validate_task(str(task_dir))["errors"]]
    problems = structural + [f"lint: {e}" for e in lint_errors(lint_task(task_dir, CANARY_LINE))]
    built = False
    if (task_dir / "environment" / "Dockerfile").exists():
        scan = leak_scan.scan(task_dir, tag)
        built = scan["built"]
        if not built:
            problems.append(f"docker build failed:\n{scan.get('error', '')[-3500:]}")
        problems += [f"leak: {leak}" for leak in scan["leaks"]]
    return problems, not structural, built


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
    """Run the gates and return every problem found. Returns [] for a package that passed.

    Static, functional and quality gates all run even when an earlier one fails
    (functional needs a built image, quality a valid structure), so one repair
    round sees every finding instead of discovering them one round at a time.
    Novelty and the red-team run only on a package that built, passed oracle/nop
    and lint, in parallel with the quality check.
    """
    h = hash_dir(cand.task_dir)
    tag = f"claude-gate-{cand.cand_id}-a{attempt}".lower()
    t0 = time.monotonic()
    problems, structure_ok, built = gate_static(cand.task_dir, tag)
    _record(ledger, cand, "gate_static", {"problems": problems}, 0.0, t0, h)
    if built:
        t0 = time.monotonic()
        found, result = gate_functional(cand.task_dir, f"gate-{cand.cand_id}-a{attempt}")
        _record(ledger, cand, "gate_functional", {**result, "problems": found}, 0.0, t0, h)
        problems += found
    if not structure_ok:
        return problems
    if problems:  # broken package: quality findings still go into the same repair round
        return problems + stage_quality(cand, ledger, attempt, h)
    # Clean so far: the quality check and the novelty -> red-team chain are independent,
    # so they run side by side (~5-10 min saved). The red-team may be paid for and then
    # discarded if quality fails; its findings still go into the repair.
    with ThreadPoolExecutor(max_workers=2) as pool:
        quality = pool.submit(stage_quality, cand, ledger, attempt, h)
        adversarial = pool.submit(_novelty_then_redteam, cand, ledger, attempt, h)
        return quality.result() + adversarial.result()


def stage_quality(cand: Candidate, ledger: Ledger, attempt: int, h: str) -> list[str]:
    """`harbor check` with our rubric. Returns blocking failures plus advice."""
    budget.check(EXPECTED_CHECK_USD)
    t0 = time.monotonic()
    check = run_check(cand.task_dir, f"check-{cand.cand_id}-a{attempt}")
    cand.save(f"quality_a{attempt}.json", check)
    found = check["blocking_failures"] or ([check["error"]] if "error" in check else [])
    _record(
        ledger,
        cand,
        "gate_quality",
        {"ok": check["ok"], "outcomes": check["outcomes"], "problems": found},
        check["cost_usd"],
        t0,
        h,
    )
    return found + (check["advice"] if found else [])


def _novelty_then_redteam(cand: Candidate, ledger: Ledger, attempt: int, h: str) -> list[str]:
    t0 = time.monotonic()
    instruction = (cand.task_dir / "instruction.md").read_text()
    index = novelty.gate_index(CANDIDATES_DIR, exclude=cand.cand_id)
    lexical = novelty.lexical_flags(instruction, index)
    judged = None if lexical else novelty.judge_same_task(instruction, index)
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
    return stage_redteam(cand, ledger, attempt, h)


def stage_redteam(cand: Candidate, ledger: Ledger, attempt: int, h: str = "") -> list[str]:
    """Hack-elicitation run; a beaten verifier sends the task back to repair."""
    budget.check(EXPECTED_REDTEAM_USD)
    t0 = time.monotonic()
    result = redteam(cand.task_dir, f"{cand.cand_id}-a{attempt}")
    cand.save(f"redteam_a{attempt}.json", result)
    _record(
        ledger,
        cand,
        "gate_redteam",
        {"hackable": result["hackable"], "reward": result["reward"], "exploit": result["exploit"]},
        result["cost_usd"],
        t0,
        h or hash_dir(cand.task_dir),
    )
    if result["hackable"]:
        return [
            (
                "red-team: an agent told to cheat made the verifier pass without solving the task. "
                f"Exploit: {result['exploit']} Harden the tests so this shortcut fails (check real "
                "behavior on verify-time inputs; don't trust files or binaries the solver can modify)."
            )
        ]
    return []


def already_gated(cand: Candidate, ledger: Ledger) -> bool:
    """True if this exact package (by content hash) already passed every gate, e.g. before a crash."""
    if not cand.task_dir.exists():
        return False
    h = hash_dir(cand.task_dir)
    return any(
        e.inputs_hash == h and not e.result.get("hackable", True)
        for e in ledger.events(stage="gate_redteam", task=cand.cand_id)
    )


def resume_point(cand: Candidate, ledger: Ledger) -> tuple[int, list[str] | None, Path | None]:
    """(attempts finished, their gate feedback, the failed package) for an interrupted build.

    A finished attempt leaves failed_a<k>/; an attempt cut off mid-way leaves nothing
    and is simply redone.
    """
    done = sorted(int(p.name.removeprefix("failed_a")) for p in cand.dir.glob("failed_a*"))
    if not done:
        return 0, None, None
    k = done[-1]
    saved = cand.dir / f"feedback_a{k}.json"
    if saved.exists():
        feedback = json.loads(saved.read_text())
    else:  # written before feedback files existed: take the last failing gate's findings
        gates = [e for e in ledger.events(task=cand.cand_id) if e.stage.startswith("gate_")]
        feedback = next(
            (e.result["problems"] for e in reversed(gates) if e.result.get("problems")), None
        )
    return k, feedback, cand.dir / f"failed_a{k}"


def build_candidate(cand: Candidate, ledger: Ledger) -> Candidate:
    """Blueprint (if needed) -> author -> gates, with repair rounds and one regeneration.

    Resumable: a saved, accepted blueprint is reused, an interrupted repair sequence
    continues after its last finished attempt, and an attempt interrupted after
    authoring goes straight back to its gates.
    """
    gate_file = cand.dir / "blueprint_gate.json"
    if (
        cand.blueprint is None
        and gate_file.exists()
        and json.loads(gate_file.read_text())["accepted"]
    ):
        cand.blueprint = Blueprint(**json.loads((cand.dir / "blueprint.json").read_text()))
    if cand.blueprint is None and not stage_blueprint(cand, ledger):
        cand.save("status.json", {"status": cand.status, "history": cand.history})
        return cand
    per_build = MAX_REPAIRS + 1  # one build plus its repairs; done twice (original + regeneration)
    attempt, feedback, previous = resume_point(cand, ledger)
    while attempt < 2 * per_build:
        attempt += 1
        if attempt % per_build == 1:  # fresh build from the blueprint
            feedback, previous = None, None
        resumed = authored_unchanged(cand, ledger, attempt)
        if not resumed and not stage_author(cand, ledger, attempt, feedback, previous):
            attempt = -(-attempt // per_build) * per_build  # skip to the next fresh build
            continue
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
        cand.save(f"feedback_a{attempt}.json", feedback)
    cand.status = "failed"
    cand.save("status.json", {"status": cand.status, "attempts": attempt, "history": cand.history})
    return cand
