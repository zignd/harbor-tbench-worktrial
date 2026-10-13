"""Difficulty tuning (stretch goal B): move a too-easy or too-hard task into the band.

An ACCEL-style mutation loop (Foster & Foerster's suggested follow-up; Tmax's
verifier knobs). Each round makes ONE change, in this order of preference:

1. knob:  the blueprint's verifier knob (more/fewer verify-time cases, a
          stricter/looser *stated* threshold, a larger/smaller hidden corpus);
2. lever: add a difficulty lever (too easy) or remove one / surface a symptom
          in the environment (too hard);
3. regenerate: re-author from the (updated) blueprint.

The change is applied as a repair-style authoring round on the current
package, then the task goes through every gate and is recalibrated. Fairness
is never traded for difficulty: the instruction must still state everything
the tests check, and a too-hard task is never made easier by weakening the
check on its core requirement.
"""

import json
import shutil
from pathlib import Path

from analysis.llm import chat, extract_json
from generator.config import TUNE_BREADTH
from generator.spec import LEVERS

PLAN_PROMPT = """You tune the difficulty of a Terminal-Bench task. A frontier agent (Claude Opus class) must solve
it in exactly 1-3 of 5 attempts. Current result: {summary} -> the task is {verdict}.

Blueprint:
{blueprint}

Why the agent failed in failed runs (from a judge), if any:
{failures}

How passing runs went, if any:
{passes}

Changes earlier tuning rounds already made (the blueprint above predates them), and their results:
{history}

Propose exactly ONE change, preferring (1) the verifier knob, then (2) a difficulty lever, then (3) regenerate.
Available levers: {levers}

Rules:
- The instruction must still state every requirement the tests check. No hidden traps, no format fussiness,
  no hidden resource or time limits.
- To make it HARDER: more or nastier verify-time cases, a stricter threshold that is stated in the
  instruction, an extra interacting cause, or removing a hint the environment gives away.
- To make it EASIER: fewer interacting causes, a clearer symptom in the environment (log line, error
  message), or a looser stated threshold. Never stop testing the core requirement.
- Aim for a pass rate of about 2/5.
- Don't repeat an earlier round's change. If it didn't move the pass rate, the difficulty must come from
  somewhere else (e.g. a symptom that points away from the cause, or a cause found only by exploring).

Return only JSON: {{"kind": "knob|lever|regenerate", "direction": "harder|easier",
"change": "precise description of what to change in the environment, instruction and tests",
"expected_effect": "one sentence"}}"""


def _failures(calibration: dict) -> str:
    rows = [t.get("failure", {}) for t in calibration.get("trials", []) if t.get("failure")]
    return "\n".join(f"- {r.get('mode')}: {r.get('explanation')}" for r in rows) or "(none)"


def _passes(calibration: dict) -> str:
    rows = [t for t in calibration.get("trials", []) if t.get("outcome") == "pass"]
    return (
        "\n".join(
            f"- passed in {r.get('turns')} turns, {r.get('minutes')} min: "
            f"{r.get('audit', {}).get('reason', '')}"
            for r in rows
        )
        or "(none)"
    )


def _history(rounds: list[dict]) -> str:
    return (
        "\n".join(
            f"- round {r['round']}: {(r.get('plan') or {}).get('change', '?')} -> {r.get('result')} "
            f"({r.get('outcomes')})"
            for r in rounds
        )
        or "(none)"
    )


def plan_mutation(
    blueprint_md: str, calibration: dict, rounds: list[dict] | None = None, chat_fn=chat
) -> tuple[dict, float]:
    outcomes = calibration["outcomes"]
    summary = f"{outcomes.count('pass')}/{len(outcomes)} judged runs passed"
    reply = chat_fn(
        PLAN_PROMPT.format(
            summary=summary,
            verdict=calibration["verdict"].replace("_", " "),
            blueprint=blueprint_md,
            failures=_failures(calibration),
            passes=_passes(calibration),
            history=_history(rounds or []),
            levers="; ".join(f"{k} ({v})" for k, v in LEVERS.items()),
        ),
        system="You adjust benchmark task difficulty without making tasks unfair.",
        max_tokens=1500,
        temperature=0.3,
    )
    plan = extract_json(reply.text)
    if plan.get("kind") not in {"knob", "lever", "regenerate"}:
        plan["kind"] = "knob"
    return plan, reply.cost_usd


BREADTH_CHANGE = """Make the task harder by BREADTH, not by one more visible bug. Opus solved the current
version by reading the code and patching a few readable defects in 4-35 commands, 4-5 times out of 5
(adding a third or fourth readable bug changed nothing). Rework it so that a correct solution must
satisfy at least {n} INDEPENDENT requirements, each a different class of edge case that:
- appears only on verify-time inputs the solver never sees (the tests generate fresh inputs),
- is not visible by reading one file: it comes from how the data and the components behave
  (empty, duplicate or out-of-order records, boundary values, unit or encoding quirks, ordering of
  operations, idempotency, partial failures, large inputs),
- is stated in the instruction as one short observable rule (fairness: nothing the tests check may
  be unstated, and no rule may be a description of the defect),
- is checked by its own test(s) on at least 3 fresh inputs.
The environment must contain realistic data and code where those cases genuinely occur. A solution
that handles the obvious cases but misses any one of the {n} rules must fail. Keep the tests
deterministic, keep the instruction outcome-only and short per rule, and keep the oracle passing 3/3."""


def breadth_plan(rnd: int) -> dict:
    """A deterministic 'harder' plan: many independent hidden-input requirements.

    If Opus finds each with probability ~0.9, {n} of them leaves a pass rate of ~0.43
    (n=8) or ~0.23 (n=14): the band, with every failure traceable to a missed rule.
    """
    n = 8 if rnd == 1 else 14
    return {"kind": "breadth", "direction": "harder", "change": BREADTH_CHANGE.format(n=n),
            "n": n}  # fmt: skip


def fix_spec_plan(calibration: dict) -> dict:
    """A repair plan for a task whose calibration failed for the task's own reasons."""
    reasons = []
    for t in calibration.get("trials", []):
        f = t.get("failure") or {}
        if f and not f.get("valid", True):
            reasons.append(f"{f.get('mode')}: {f.get('requirement') or ''} {f.get('explanation')}")
        a = t.get("audit") or {}
        if a and not a.get("honest", True):
            reasons.append(f"hacked pass ({a.get('label')}): {a.get('reason')}")
    return {"kind": "fix_spec", "direction": "fix", "change": " | ".join(dict.fromkeys(reasons))}


def directive(plan: dict) -> str:
    if plan.get("kind") == "fix_spec":
        return (
            "Spec fix: calibration runs failed (or passed by cheating) because of the task, not "
            f"the agent: {plan.get('change')} Fix the tests, or state the requirement in the "
            "instruction, so every solution the instruction allows passes and a hollow one still "
            "fails. Don't change the task's difficulty otherwise; the oracle must still pass 3/3."
        )
    return (
        f"Difficulty tuning ({plan.get('direction')}, via {plan.get('kind')}): the task was "
        f"{'too easy' if plan.get('direction') == 'harder' else 'too hard'} for a frontier agent. "
        f"Change: {plan.get('change')} Keep everything else that works. The instruction must still "
        "state every requirement the tests check, and the oracle must still pass 3/3."
    )


def _resume_rounds(cand_id: str, ledger, offset: int = 0) -> tuple[list[dict], dict | None]:
    """Rounds a crashed tuning run already finished, and the calibration they left."""
    # A round whose authoring never ran (infra error: Docker out of networks, proxy down) is
    # not a tuning result: it is redone, not counted.
    rounds = [
        e.result
        for e in ledger.events(stage="tune", task=cand_id)
        if e.result.get("gate_problems") != ["authoring failed"]
        and e.result.get("offset", 0) == offset
    ]
    if not rounds:
        return [], None
    last = rounds[-1]
    name = f"{cand_id}-t{last['round'] + offset}"
    trials = [e.result for e in ledger.events(stage="calibration_trial", task=name)]
    return rounds, {
        "verdict": last["result"],
        "outcomes": last.get("outcomes", []),
        "trials": trials,
    }


AGAIN_OFFSET = 20  # a second tuning generation: keeps job names, files and records apart


def tune_candidate(cand_dir: Path, ledger, max_rounds: int = 2, again: bool = False) -> dict:
    """Mutate -> re-author -> gates -> recalibrate, up to max_rounds. Returns the tuning record.

    A too-easy task gets the breadth mutation (many independent hidden-input requirements);
    `again` starts a second generation of rounds for a task that was already tuned.

    Resumable: finished rounds come back from the ledger, and a round whose new
    package already passed every gate goes straight to calibration.
    """
    from analysis.ledger import Event, hash_dir
    from evaluator.calibrate import calibrate
    from generator import pipeline
    from generator.blueprint import Blueprint
    from generator.spec import TaskSpec

    cand_dir = Path(cand_dir)
    spec = TaskSpec(**json.loads((cand_dir / "spec.json").read_text()))
    cand = pipeline.Candidate(spec, cand_id=cand_dir.name)
    cand.blueprint = Blueprint(**json.loads((cand_dir / "blueprint.json").read_text()))
    calibration = json.loads((cand_dir / "calibration.json").read_text())
    record = {"start": calibration["verdict"], "rounds": []}
    offset = AGAIN_OFFSET if again else 0
    record["rounds"], resumed = _resume_rounds(cand.cand_id, ledger, offset)
    calibration = resumed or calibration

    for rnd in range(len(record["rounds"]) + 1, max_rounds + 1):
        if calibration["verdict"] not in ("too_easy", "too_hard", "invalid"):
            break
        rid = rnd + offset  # round id in file names, job names and calibration names
        previous = cand_dir / f"before_tune_r{rid}"
        plan_file = cand_dir / f"tune_plan_r{rid}.json"
        resuming = previous.exists() and plan_file.exists()
        if (
            resuming
            and hash_dir(cand.task_dir) != hash_dir(previous)
            and pipeline.already_gated(cand, ledger)
        ):
            plan, plan_cost, problems = json.loads(plan_file.read_text()), 0.0, []
        else:
            if resuming:  # interrupted mid-authoring: redo it from the saved snapshot and plan
                plan, plan_cost = json.loads(plan_file.read_text()), 0.0
            else:
                if calibration["verdict"] == "invalid":
                    plan, plan_cost = fix_spec_plan(calibration), 0.0
                elif calibration["verdict"] == "too_easy" and TUNE_BREADTH:
                    plan, plan_cost = breadth_plan(rnd), 0.0
                else:
                    plan, plan_cost = plan_mutation(
                        cand.blueprint.to_markdown(spec), calibration, record["rounds"]
                    )
                # The snapshot the repair patches, and the plan a resume reuses: both kinds
                # of round need them (the spec-fix branch once skipped them and crashed).
                if previous.exists():
                    shutil.rmtree(previous)
                shutil.copytree(cand.task_dir, previous)
                plan_file.write_text(json.dumps(plan, indent=1))
            problems = _retune(cand, ledger, rid, plan, previous)
        round_rec = {"round": rnd, "offset": offset, "plan": plan, "gate_problems": problems}
        if problems == ["authoring failed"]:
            # Infrastructure, not the task: log it, keep no final record, and let a later
            # run redo the round from the same snapshot and plan.
            ledger.append(
                Event("tune", cand.cand_id, {**round_rec, "result": "infra"}, cost_usd=plan_cost)
            )
            return {"start": record["start"], "rounds": record["rounds"], "final": "infra"}
        if problems:
            round_rec["result"] = "gates_failed"
            record["rounds"].append(round_rec)
            ledger.append(Event("tune", cand.cand_id, round_rec, cost_usd=plan_cost))
            break
        cal = calibrate(cand.task_dir, f"{cand.cand_id}-t{rid}", ledger)
        calibration = {
            "verdict": cal.verdict,
            "outcomes": cal.outcomes,
            "trials": cal.trials,
            "cost_usd": round(cal.cost_usd, 4),
        }
        round_rec["result"] = cal.verdict
        round_rec["outcomes"] = cal.outcomes
        record["rounds"].append(round_rec)
        ledger.append(Event("tune", cand.cand_id, round_rec, cost_usd=plan_cost))
    record["final"] = calibration["verdict"]
    tuning_file = "tuning_again.json" if again else "tuning.json"
    (cand_dir / tuning_file).write_text(json.dumps(record, indent=1, default=str))
    (cand_dir / "calibration.json").write_text(json.dumps(calibration, indent=1, default=str))
    return record


def _retune(cand, ledger, rnd: int, plan: dict, previous: Path) -> list[str]:
    """Apply the plan as a repair-style authoring round (one gate repair allowed)."""
    from generator import pipeline

    attempt = 100 + rnd  # keeps tuning job names apart from build attempts
    feedback = [directive(plan)]
    problems = ["authoring failed"]
    for repair in range(2):
        if not pipeline.stage_author(cand, ledger, attempt + 10 * repair, feedback, previous):
            break
        problems = pipeline.stage_gates(cand, ledger, attempt + 10 * repair)
        if not problems:
            break
        feedback = [directive(plan), *problems]
        shutil.rmtree(previous)
        shutil.copytree(cand.task_dir, previous)
    return problems
