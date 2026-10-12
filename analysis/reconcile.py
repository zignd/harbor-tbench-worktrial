"""Reconcile recorded spend (ledger) with what OpenRouter actually charged.

The ledger records every pipeline stage. Phase 0 runs predate the ledger, so
`backfill_phase0()` adds them once from their Harbor job dirs. Whatever is
left (ad-hoc test calls made while developing) is reported as unattributed,
not hidden. A gap above 10% means the accounting is wrong (docs/plan.md,
"Spend discipline"), but only when nothing is in flight: stages record their
cost when they finish, so a running authoring or calibration job shows up as
a temporary gap.

    uv run --env-file .env python -m analysis.reconcile [--backfill]
"""

import argparse
from pathlib import Path

from analysis.ledger import Event, Ledger
from analysis.openrouter import current_spend
from evaluator.harbor_runner import parse_job
from generator.config import JOBS_DIR

# Phase 0 Harbor jobs that called a model (job dir name -> mode).
PHASE0_JOBS = {
    "p0-opus-fixgit": "official",
    "p0-metatask-sonnet": "official",
    "p0-metatask-dev": "dev",
    "p0-check-fixgit": "official",
    "p1-quality-spike": "official",
}


def backfill_phase0(ledger: Ledger, jobs_dir: Path | str = JOBS_DIR) -> float:
    """Add Phase 0 job costs to the ledger once (idempotent). Returns the amount added."""
    done = {e.inputs_hash for e in ledger.events(stage="phase0")} | {
        e.inputs_hash for e in ledger.events(stage="phase0", mode="dev")
    }
    added = 0.0
    for job, mode in PHASE0_JOBS.items():
        job_dir = Path(jobs_dir) / job
        if job in done or not job_dir.exists():
            continue
        cost = sum(t.priced_cost() for t in parse_job(job_dir))
        ledger.append(
            Event(
                "phase0",
                job,
                {"backfilled_from": str(job_dir)},
                cost_usd=cost,
                inputs_hash=job,
                mode=mode,
            )
        )
        added += cost
    return added


def reconcile(ledger: Ledger) -> dict:
    spend = current_spend()
    recorded = ledger.total_cost()
    gap = spend.spent - recorded
    return {
        "openrouter_spent": round(spend.spent, 4),
        "openrouter_used": round(spend.used, 4),
        "ledger_total": round(recorded, 4),
        "ledger_official": round(ledger.total_cost(mode="official"), 4),
        "ledger_dev": round(ledger.total_cost(mode="dev"), 4),
        "unattributed": round(gap, 4),
        "gap_pct": round(100 * gap / spend.spent, 1) if spend.spent else 0.0,
        "remaining": spend.remaining,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backfill", action="store_true", help="add Phase 0 job costs once")
    args = parser.parse_args()
    ledger = Ledger()
    if args.backfill:
        print(f"backfilled ${backfill_phase0(ledger):.4f} of Phase 0 job costs")
    for key, value in reconcile(ledger).items():
        print(f"{key:18} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
