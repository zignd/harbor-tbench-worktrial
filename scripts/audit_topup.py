"""Replace invalid calibration trials with fresh attempts under identical settings.

    uv run --env-file .env python -m scripts.audit_topup TASK_DIR RECORD.json

A trial is invalid when it exhausts the turn cap, errors, or is otherwise not a real attempt.
Such a trial carries no difficulty signal, so it is excluded and replaced by a fresh attempt with
the same model, agent and turn cap. The invalid trial is preserved in the record under
`excluded_trials`; nothing is deleted and the count of judged attempts is reported explicitly.
"""

import json
import sys
from pathlib import Path

from analysis import budget
from analysis.judge import analyze_failure, audit_pass
from analysis.package_evidence import package_hash
from evaluator.harbor_runner import run_with_retries
from generator.config import EVAL_MODEL, MODEL_LABEL
from scripts.audit_calibrate import MAX_TURNS_CAP, TRIALS


def _judge(task_dir: Path, t) -> dict:
    row = {
        "trial": t.trial_name,
        "outcome": t.outcome,
        "reward": t.reward,
        "turns": t.n_episodes,
        "max_turns": MAX_TURNS_CAP,
        "minutes": round(t.seconds / 60, 1),
        "trial_cost_usd": round(t.priced_cost(), 4),
    }
    if t.outcome == "pass":
        row["audit"] = audit_pass(task_dir, t.trajectory_path)
    elif t.outcome == "fail":
        row["failure"] = analyze_failure(task_dir, t.trial_dir, t.trajectory_path)
    return row


def _is_real(row: dict) -> bool:
    """A real attempt: a judged pass or a validly-judged failure within the turn cap."""
    if row.get("turns") and row.get("max_turns") and row["turns"] >= row["max_turns"]:
        return False
    if row["outcome"] == "pass":
        return bool(row.get("audit", {}).get("honest"))
    if row["outcome"] == "fail":
        return bool(row.get("failure", {}).get("valid"))
    return False


def main() -> int:
    task_dir, rec_path = Path(sys.argv[1]), Path(sys.argv[2])
    budget.check(2.0)
    rec = json.loads(rec_path.read_text())
    while True:
        pending = [r for r in rec["trials"] if not _is_real(r)]
        if not pending:
            break
        counted, _ = run_with_retries(
            task_dir,
            "terminus-2",
            f"audit-cal-{task_dir.name}",
            model=EVAL_MODEL,
            attempts=1,
            concurrent=1,
            agent_kwargs={"max_turns": MAX_TURNS_CAP},
        )
        if not counted:
            print("no attempt produced; stopping")
            return 1
        row = _judge(task_dir, counted[0])
        if _is_real(row):
            rec["trials"].append(row)
            rec["excluded_trials"] = rec.get("excluded_trials", []) + [
                {
                    "trial": r["trial"],
                    "outcome": r["outcome"],
                    "turns": r.get("turns"),
                    "reason": "turn cap or unaudited/unvalid trial",
                }
                for r in pending
            ]
        else:
            rec["excluded_trials"] = rec.get("excluded_trials", []) + [
                {
                    "trial": r["trial"],
                    "outcome": r["outcome"],
                    "turns": r.get("turns"),
                    "reason": "turn cap or unaudited/unvalid trial",
                }
                for r in rec["trials"]
                if not _is_real(r)
            ]
            rec["trials"] = [r for r in rec["trials"] if _is_real(r)] + [row]
            print(f"replacement also invalid ({row['outcome']}, turns {row['turns']}); retrying")

    real = [r for r in rec["trials"] if _is_real(r)]
    rec["trials"] = real[:TRIALS]
    passes = sum(1 for r in rec["trials"] if r["outcome"] == "pass")
    rec["legit_passes"] = passes
    rec["n_trials"] = len(rec["trials"])
    rec["verdict"] = (
        "learnable" if 1 <= passes <= 3 else ("too_easy" if passes >= 4 else "too_hard")
    )
    rec["package_hash"] = package_hash(task_dir)
    rec["models"] = MODEL_LABEL
    rec["topped_up"] = True
    rec["cost_usd"] = round(
        sum(r.get("trial_cost_usd", 0) for r in rec["trials"] + rec.get("excluded_trials", [])), 4
    )
    rec_path.write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({k: rec[k] for k in ("verdict", "legit_passes", "n_trials", "package_hash")}))
    print("excluded:", [e["trial"] for e in rec.get("excluded_trials", [])])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
