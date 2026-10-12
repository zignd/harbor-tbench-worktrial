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
from generator.spec import LEVERS

PLAN_PROMPT = """You tune the difficulty of a Terminal-Bench task. A frontier agent (Claude Opus class) must solve
it in exactly 1-3 of 5 attempts. Current result: {summary} -> the task is {verdict}.

Blueprint:
{blueprint}

Why the agent failed in failed runs (from a judge), if any:
{failures}

How passing runs went, if any:
{passes}

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

Return only JSON: {{"kind": "knob|lever|regenerate", "direction": "harder|easier",
"change": "precise description of what to change in the environment, instruction and tests",
"expected_effect": "one sentence"}}"""


def _failures(calibration: dict) -> str:
    rows = [t.get("failure", {}) for t in calibration.get("trials", []) if t.get("failure")]
    return "\n".join(f"- {r.get('mode')}: {r.get('explanation')}" for r in rows) or "(none)"


def _passes(calibration: dict) -> str:
    rows = [t for t in calibration.get("trials", []) if t.get("outcome") == "pass"]
    return (
        "\n".join(f"- passed in {r.get('turns')} turns, {r.get('minutes')} min" for r in rows)
        or "(none)"
    )


def plan_mutation(blueprint_md: str, calibration: dict, chat_fn=chat) -> tuple[dict, float]:
    outcomes = calibration["outcomes"]
    summary = f"{outcomes.count('pass')}/{len(outcomes)} judged runs passed"
    reply = chat_fn(
        PLAN_PROMPT.format(
            summary=summary,
            verdict=calibration["verdict"].replace("_", " "),
            blueprint=blueprint_md,
            failures=_failures(calibration),
            passes=_passes(calibration),
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


def directive(plan: dict) -> str:
    return (
        f"Difficulty tuning ({plan.get('direction')}, via {plan.get('kind')}): the task was "
        f"{'too easy' if plan.get('direction') == 'harder' else 'too hard'} for a frontier agent. "
        f"Change: {plan.get('change')} Keep everything else that works. The instruction must still "
        "state every requirement the tests check, and the oracle must still pass 3/3."
    )


def tune_candidate(cand_dir: Path, ledger, max_rounds: int = 2) -> dict:
    """Mutate -> re-author -> gates -> recalibrate, up to max_rounds. Returns the tuning record."""
    from analysis.ledger import Event
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

    for rnd in range(1, max_rounds + 1):
        if calibration["verdict"] not in ("too_easy", "too_hard"):
            break
        plan, plan_cost = plan_mutation(cand.blueprint.to_markdown(spec), calibration)
        previous = cand_dir / f"before_tune_r{rnd}"
        if previous.exists():
            shutil.rmtree(previous)
        shutil.copytree(cand.task_dir, previous)
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
        round_rec = {"round": rnd, "plan": plan, "gate_problems": problems}
        if problems:
            round_rec["result"] = "gates_failed"
            record["rounds"].append(round_rec)
            ledger.append(Event("tune", cand.cand_id, round_rec, cost_usd=plan_cost))
            break
        cal = calibrate(cand.task_dir, f"{cand.cand_id}-t{rnd}", ledger)
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
    (cand_dir / "tuning.json").write_text(json.dumps(record, indent=1, default=str))
    (cand_dir / "calibration.json").write_text(json.dumps(calibration, indent=1, default=str))
    return record
