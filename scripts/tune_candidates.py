"""Tune calibrated near-misses (too easy / too hard) toward the band, and ship any that land.

    uv run --env-file .env python -m scripts.tune_candidates [--only ID ...] [--rounds 2]

Only candidates whose failures were all *valid* are tuned: a task that failed
for invalid reasons needs repair, not a difficulty change.
"""

import argparse
import json

from analysis.ledger import Ledger
from analysis.tuner import tune_candidate
from generator.pipeline import CANDIDATES_DIR
from scripts.calibrate_candidates import ship


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    ledger = Ledger()
    for cand_dir in sorted(CANDIDATES_DIR.iterdir()):
        cal_file = cand_dir / "calibration.json"
        if (args.only and cand_dir.name not in args.only) or not cal_file.exists():
            continue
        if (cand_dir / "tuning.json").exists():
            continue
        if json.loads(cal_file.read_text())["verdict"] not in ("too_easy", "too_hard"):
            continue
        record = tune_candidate(cand_dir, ledger, max_rounds=args.rounds)
        shipped = None
        if record["final"] == "learnable":
            shipped = ship(cand_dir, json.loads(cal_file.read_text()))
        rounds = " -> ".join([record["start"]] + [r["result"] for r in record["rounds"]])
        print(f"{cand_dir.name}  {rounds}" + (f"  -> {shipped}" if shipped else ""), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
