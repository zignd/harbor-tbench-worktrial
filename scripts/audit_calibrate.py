"""Five full judged calibration attempts for one task (no curtailment), for the audit.

    uv run --env-file .env python -m scripts.audit_calibrate TASK_DIR OUT.json

Runs exactly five terminus-2 trials with the configured calibration model, audits passes and
judges failures, and writes an immutable record: outcomes, per-trial audit/failure evidence,
legit passes, verdict, model label and the task package hash. Used to replace curtailed records.
"""

import json
import sys
from pathlib import Path

from analysis import budget
from analysis.judge import analyze_failure, audit_pass
from analysis.package_evidence import package_hash
from evaluator.harbor_runner import run_with_retries
from generator.config import EVAL_MODEL, MODEL_LABEL

TRIALS = 5


def main() -> int:
    task_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    budget.check(5.0)
    counted, excluded = run_with_retries(
        task_dir,
        "terminus-2",
        f"audit-cal-{task_dir.name}",
        model=EVAL_MODEL,
        attempts=TRIALS,
        concurrent=3,
        agent_kwargs={"max_turns": 100},
    )
    trials, passes = [], 0
    for t in counted:
        row = {
            "trial": t.trial_name,
            "outcome": t.outcome,
            "reward": t.reward,
            "turns": t.n_episodes,
            "minutes": round(t.seconds / 60, 1),
            "trial_cost_usd": round(t.priced_cost(), 4),
        }
        if t.outcome == "pass":
            row["audit"] = audit_pass(task_dir, t.trajectory_path)
            if row["audit"].get("honest"):
                passes += 1
        elif t.outcome == "fail":
            row["failure"] = analyze_failure(task_dir, t.trial_dir, t.trajectory_path)
        trials.append(row)
    verdict = (
        "invalid"
        if any(
            r.get("outcome") not in ("pass", "fail")
            or (r.get("outcome") == "pass" and not r.get("audit", {}).get("honest"))
            or (r.get("outcome") == "fail" and not r.get("failure", {}).get("valid"))
            for r in trials
        )
        else ("learnable" if 1 <= passes <= 3 else ("too_easy" if passes >= 4 else "too_hard"))
    )
    record = {
        "verdict": verdict,
        "outcomes": [r["outcome"] for r in trials],
        "trials": trials,
        "legit_passes": passes,
        "n_trials": len(trials),
        "infra_excluded": len(excluded),
        "models": MODEL_LABEL,
        "calibration_model": EVAL_MODEL,
        "package_hash": package_hash(task_dir),
        "cost_usd": round(
            sum(r["trial_cost_usd"] for r in trials)
            + sum(
                r.get("audit", {}).get("cost_usd", 0) + r.get("failure", {}).get("cost_usd", 0)
                for r in trials
            ),
            4,
        ),
    }
    out.write_text(json.dumps(record, indent=1) + "\n")
    print(
        json.dumps(
            {
                k: record[k]
                for k in ("verdict", "outcomes", "legit_passes", "package_hash", "cost_usd")
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
