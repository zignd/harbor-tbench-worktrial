"""Calibrate every built package whose build and oracle/nop already passed.

Opus calibration is the only real signal for "learnable", and it is cheap, while the
repair gates (lint, quality, novelty, red-team) cost a 20-40 min authoring round per
finding. So instead of repairing every candidate toward a prediction, find the packages
that already work functionally (the task, `failed_a*` repair snapshots and `before_tune_*`
snapshots) and calibrate them. A learnable one then only needs its remaining gates fixed.

    uv run --env-file .env python -m scripts.calibrate_snapshots [--dry-run] [--workers 3]
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from analysis.ledger import Event, Ledger, hash_dir
from evaluator.calibrate import calibrate
from generator.pipeline import CANDIDATES_DIR


def functional_hashes(ledger: Ledger) -> set[str]:
    """Package hashes whose gate_functional (build + oracle 3/3 + nop 0) passed."""
    return {
        e.inputs_hash
        for e in ledger.events(stage="gate_functional")
        if e.mode == "official" and e.inputs_hash and not e.result.get("problems")
    }


def calibrated_hashes(ledger: Ledger) -> set[str]:
    return {e.inputs_hash for e in ledger.events(stage="snapshot_calibration") if e.inputs_hash}


def snapshots(cand_dir: Path) -> list[Path]:
    """The task, then repair snapshots newest first. `before_tune_*` snapshots are skipped:
    they are the packages the pipeline already calibrated before tuning them."""
    repairs = sorted(cand_dir.glob("failed_a*"), key=lambda p: int(p.name.removeprefix("failed_a")),
                     reverse=True)  # fmt: skip
    return [p for p in (cand_dir / "task", *repairs) if (p / "task.toml").exists()]


def todo(ledger: Ledger, all_versions: bool = False) -> list[tuple[str, Path, str]]:
    """One package per candidate (its newest functionally-passing, uncalibrated version), or
    every distinct version with `all_versions`."""
    ok, done, seen, out = functional_hashes(ledger), calibrated_hashes(ledger), set(), []
    for cand_dir in sorted(CANDIDATES_DIR.glob("official-*")):
        calibrated_task = (cand_dir / "calibration.json").exists()
        for sub in snapshots(cand_dir):
            if sub.name == "task" and calibrated_task:
                continue  # the pipeline already calibrated this package
            h = hash_dir(sub)
            if h in ok and h not in done and h not in seen:
                seen.add(h)
                out.append((cand_dir.name, sub, h))
                if not all_versions:
                    break
    return out


def run_one(item: tuple[str, Path, str], ledger: Ledger) -> dict:
    cand_id, sub, h = item
    cal = calibrate(sub, f"{cand_id}-snap-{sub.name}", ledger)
    record = {"snapshot": sub.name, "hash": h, "verdict": cal.verdict, "outcomes": cal.outcomes,
              "trials": cal.trials, "cost_usd": round(cal.cost_usd, 4)}  # fmt: skip
    path = CANDIDATES_DIR / cand_id / "snapshots.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    records[sub.name] = record
    path.write_text(json.dumps(records, indent=1, default=str))
    ledger.append(Event("snapshot_calibration", cand_id,
                        {"snapshot": sub.name, "verdict": cal.verdict, "outcomes": cal.outcomes},
                        inputs_hash=h))  # fmt: skip
    print(f"{cand_id}/{sub.name}  {cal.summary}", flush=True)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--all-versions", action="store_true", help="every repair version, not just the newest"
    )
    args = parser.parse_args()
    ledger = Ledger()
    items = todo(ledger, args.all_versions)
    print(f"{len(items)} functionally-passing packages to calibrate", flush=True)
    for cand_id, sub, _ in items:
        print(f"  {cand_id}/{sub.name}")
    if args.dry_run:
        return 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(lambda item: run_one(item, ledger), items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
