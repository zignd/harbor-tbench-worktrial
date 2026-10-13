"""Calibration against Opus 4.8: is a gated task learnable (1-3 of 5 runs pass)?

Exact sequential curtailment (docs/plan.md, "Spend discipline" 2): stop as soon
as the 5-run verdict can no longer change.

    accept (learnable)  at >= 1 legit pass and >= 2 valid fails
                        (at most 5 - fails <= 3 runs can pass)
    reject (too easy)   at 4 legit passes
    reject (too hard)   at 5 valid fails

Every trial is judged as soon as it finishes (analysis/judge.py): a hacked
pass or an *invalid* failure means the task can't ship as it stands, so
calibration stops immediately and the task goes back to repair.

Trials run in waves no larger than the fewest trials that could still reach a
verdict, so curtailment never pays for a trial whose result can't matter.
"""

from dataclasses import dataclass, field
from pathlib import Path

N_RUNS = 5
LEGIT_PASS, VALID_FAIL, HACKED_PASS, INVALID_FAIL = "pass", "fail", "hacked", "invalid"


def decide(outcomes: list[str], n_runs: int = N_RUNS) -> str | None:
    """Verdict from judged outcomes so far, or None if more trials are needed."""
    if HACKED_PASS in outcomes or INVALID_FAIL in outcomes:
        return "invalid"
    passes = outcomes.count(LEGIT_PASS)
    fails = outcomes.count(VALID_FAIL)
    if passes >= n_runs - 1:
        return "too_easy"
    if fails >= n_runs:
        return "too_hard"
    if passes >= 1 and fails >= 2:
        return "learnable"
    return None


def next_wave_size(
    outcomes: list[str], concurrency: int, n_runs: int = N_RUNS, eager: bool = False
) -> int:
    """Largest wave that can't overshoot the earliest possible verdict.

    With `eager`, every remaining trial up to `concurrency` (fastest wall clock).
    """
    if eager:
        return max(1, min(concurrency, n_runs - len(outcomes)))
    passes = outcomes.count(LEGIT_PASS)
    fails = outcomes.count(VALID_FAIL)
    to_easy = (n_runs - 1) - passes
    to_hard = n_runs - fails
    to_learnable = max(1 - passes, 0) + max(2 - fails, 0)
    return max(1, min(concurrency, to_easy, to_hard, to_learnable))


@dataclass
class Calibration:
    task: str
    outcomes: list[str] = field(default_factory=list)
    trials: list[dict] = field(default_factory=list)  # per-trial records (judge labels etc.)
    verdict: str | None = None
    cost_usd: float = 0.0

    @property
    def passes(self) -> int:
        return self.outcomes.count(LEGIT_PASS)

    @property
    def summary(self) -> str:
        return f"{self.passes}/{len(self.outcomes)} legit passes -> {self.verdict}"


# --- Runner ------------------------------------------------------------------

EXPECTED_OPUS_TRIAL_USD = 1.5  # budget pre-check per trial; actual cost comes from the trials


def judge_trial(task_dir, trial) -> tuple[str, dict, float]:
    """Map one Harbor trial to a calibration outcome using the judges."""
    from analysis.judge import analyze_failure, audit_pass

    if trial.outcome == "pass":
        audit = audit_pass(task_dir, trial.trajectory_path)
        return (LEGIT_PASS if audit["honest"] else HACKED_PASS), {"audit": audit}, audit["cost_usd"]
    if trial.outcome == "fail":
        failure = analyze_failure(task_dir, trial.trial_dir, trial.trajectory_path)
        outcome = VALID_FAIL if failure["valid"] else INVALID_FAIL
        return outcome, {"failure": failure}, failure["cost_usd"]
    # Harbor-level invalid (timeout, turn cap, context overflow): never a valid failure.
    return INVALID_FAIL, {"harbor": trial.outcome, "exception": trial.exception}, 0.0


def unfinished_trials(ledger, name: str) -> list[dict]:
    """Judged trials of a calibration run of `name` that never reached its verdict (a crash)."""
    trials: list[dict] = []
    for e in ledger.events(task=name):
        if e.stage == "calibration":
            trials = []
        elif e.stage == "calibration_trial":
            trials.append({**e.result, "_ledger_cost": e.cost_usd})
    return trials


def opus_slots(k: int, total: int, lock_dir: Path, poll_s: float = 5.0):
    """Hold k of `total` machine-wide Opus trial slots while a wave runs."""
    from evaluator.slots import machine_slots

    return machine_slots(k, total, lock_dir, poll_s)


def calibrate(task_dir, name: str, ledger, concurrency: int | None = None) -> Calibration:
    """Run Opus trials in waves until decide() returns a verdict.

    Resumable: trials already judged under `name` without a final verdict are
    kept, so an interrupted run only pays for the trials it still needs.
    """
    from analysis import budget
    from analysis.ledger import Event
    from evaluator.harbor_runner import run_with_retries
    from generator.config import (
        CALIBRATION_EAGER,
        EVAL_AGENT,
        EVAL_MODEL,
        JOBS_DIR,
        MAX_TURNS,
        OPUS_CONCURRENCY,
    )

    concurrency = concurrency or OPUS_CONCURRENCY
    cal = Calibration(task=name)
    for t in unfinished_trials(ledger, name):
        cal.outcomes.append(t["outcome"])
        cal.cost_usd += t.pop("_ledger_cost")
        cal.trials.append(t)
    wave = len(cal.outcomes)  # waves hold >= 1 trial, so new job names never collide
    while (verdict := decide(cal.outcomes)) is None:
        k = next_wave_size(cal.outcomes, concurrency, eager=CALIBRATION_EAGER)
        budget.check(EXPECTED_OPUS_TRIAL_USD * k)
        wave += 1
        with opus_slots(k, OPUS_CONCURRENCY, Path(JOBS_DIR) / ".opus-slots"):
            counted, excluded = run_with_retries(
                task_dir,
                EVAL_AGENT,
                f"cal-{name}-w{wave}",
                model=EVAL_MODEL,
                attempts=k,
                concurrent=k,
                agent_kwargs={"max_turns": MAX_TURNS},
            )
        if not counted:
            verdict = "infra"
            break
        for trial in counted:
            outcome, labels, judge_cost = judge_trial(task_dir, trial)
            trial_cost = trial.priced_cost()
            cal.outcomes.append(outcome)
            cal.cost_usd += trial_cost + judge_cost
            record = {
                "trial": trial.trial_name,
                "outcome": outcome,
                "reward": trial.reward,
                "turns": trial.n_episodes,
                "minutes": round(trial.seconds / 60, 1),
                "trial_cost_usd": round(trial_cost, 4),
                **labels,
            }
            cal.trials.append(record)
            ledger.append(
                Event(
                    "calibration_trial",
                    name,
                    record,
                    cost_usd=trial_cost + judge_cost,
                    seconds=trial.seconds,
                )
            )
        cal.trials += [{"trial": t.trial_name, "outcome": "excluded_infra"} for t in excluded]
    cal.verdict = verdict
    ledger.append(
        Event(
            "calibration",
            name,
            {
                "verdict": verdict,
                "outcomes": cal.outcomes,
                "passes": cal.passes,
                "trials": len(cal.outcomes),
            },
            cost_usd=0.0,
        )
    )
    return cal
