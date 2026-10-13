"""Exploratory pilot: how do cheaper OpenRouter models fare on our too-easy packages?

NOT part of the work trial's pipeline: nothing here is shipped, calibrated against the
official models, or used by the report's funnel. It answers one question before any plan
change: do tasks Opus 4.8 solves 4/4-5/5 land in the 1-3 of 5 band for a weaker model?
Each (model, package) runs N plain terminus-2 trials (turn-capped) and records
pass / fail / invalid (turn cap, timeout, infra) counts and cost. Stops when --cap-usd is spent.

    uv run --env-file .env python -m scripts.pilot_models --models qwen/qwen3.7-max z-ai/glm-5.1
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from analysis import budget
from analysis.ledger import Event, Ledger
from evaluator.harbor_runner import run_with_retries
from generator.config import RUNS_DIR

CANDIDATES = Path(RUNS_DIR) / "candidates"
# (candidate, package dir): the exact package Opus calibrated, all past the functional gate.
PACKAGES = [
    ("p0-ledger-reconcile", "task"),
    ("2f505f92f1c8", "before_tune_r1"),
    ("31ca491030e9", "task"),
    ("b540d2ce9b80", "task"),
    ("3bbd19e55510", "before_tune_r1"),
]
OPUS_RESULT = {  # what Opus 4.8 did on the same package (passes / runs)
    "p0-ledger-reconcile": "4/4", "2f505f92f1c8": "4/5", "31ca491030e9": "4/4",
    "b540d2ce9b80": "5/5", "3bbd19e55510": "5/5",
}  # fmt: skip
OUT = Path(RUNS_DIR) / "pilot" / "pilot_models.json"


def run_pair(model: str, cand: str, sub: str, trials: int, max_turns: int) -> dict:
    task_dir = CANDIDATES / f"official-{cand}" / sub
    name = f"pilot-{model.replace('/', '_')}-{cand}"
    budget.check(2.0)
    counted, excluded = run_with_retries(
        task_dir, "terminus-2", name, model=f"openrouter/{model}", attempts=trials, concurrent=3,
        agent_kwargs={"max_turns": max_turns},
    )  # fmt: skip
    rows = [
        {"outcome": t.outcome, "reward": t.reward, "turns": t.n_episodes,
         "minutes": round(t.seconds / 60, 1), "cost_usd": round(t.priced_cost(), 4)}
        for t in counted
    ]  # fmt: skip
    return {
        "model": model, "candidate": cand, "package": sub, "opus": OPUS_RESULT[cand],
        "passes": sum(r["outcome"] == "pass" for r in rows),
        "fails": sum(r["outcome"] == "fail" for r in rows),
        "invalid": sum(r["outcome"] == "invalid" for r in rows),
        "infra_excluded": len(excluded), "trials": rows,
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
    }  # fmt: skip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--cap-usd", type=float, default=8.0)
    parser.add_argument("--only", nargs="*", help="candidate ids to include")
    args = parser.parse_args()
    ledger, spent = Ledger(), 0.0
    results = json.loads(OUT.read_text()) if OUT.exists() else []
    done = {(r["model"], r["candidate"]) for r in results}
    for model in args.models:
        for cand, sub in PACKAGES:
            if (args.only and cand not in args.only) or (model, cand) in done:
                continue
            if spent >= args.cap_usd:
                print(f"pilot cap ${args.cap_usd:.2f} reached (spent ${spent:.2f}); stopping")
                return 0
            r = run_pair(model, cand, sub, args.trials, args.max_turns)
            spent += r["cost_usd"]
            r["at"] = datetime.now(UTC).isoformat(timespec="seconds")
            results.append(r)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(results, indent=1))
            ledger.append(Event("pilot_trial", f"pilot-{cand}", {k: r[k] for k in (
                "model", "package", "opus", "passes", "fails", "invalid")}, cost_usd=r["cost_usd"]))  # fmt: skip
            print(
                f"{model:24} {cand:14} opus {r['opus']:>4} | model {r['passes']}p {r['fails']}f "
                f"{r['invalid']}inv | ${r['cost_usd']:.2f} (pilot total ${spent:.2f})",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
