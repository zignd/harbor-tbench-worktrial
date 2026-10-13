"""Pool independent calibration batches for one package and apply the pre-registered rule.

    uv run --env-file .env python -m scripts.audit_pool TASK_DIR OUT.json RECORD.json [RECORD.json ...]

A five-trial band verdict is a noisy estimate of a pass probability: at a true p of 0.2 the chance of
observing 0/5 is 33%, and at p = 0.8 the chance of observing 4/5 is 41%. When a package sits near a
band edge, the honest move is more independent samples, not a different threshold.

Pre-registered approval rule (strictly harder to satisfy than a single batch):
  * every record must be for the same package hash and model pair;
  * at least one complete batch of five attempts must have 1-3 passes with every failure valid and
    every pass audited honest;
  * the pooled pass rate over all valid trials of all batches must lie in [0.2, 0.8].

Writes the decision record to OUT.json and prints it. Exits 0 only when the rule is satisfied.
"""

import json
import sys
from pathlib import Path

from analysis.package_evidence import package_hash
from generator.config import MODEL_LABEL

BAND_LOW, BAND_HIGH = 1, 3


def valid_trials(record: dict) -> list[dict]:
    out = []
    for t in record.get("trials", []):
        if t.get("turns") and t.get("max_turns") and t["turns"] >= t["max_turns"]:
            continue
        if (t.get("outcome") == "pass" and t.get("audit", {}).get("honest")) or (
            t.get("outcome") == "fail" and t.get("failure", {}).get("valid")
        ):
            out.append(t)
    return out


def main() -> int:
    task_dir, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    paths = [Path(p) for p in sys.argv[3:]]
    h = package_hash(task_dir)
    batches, total_pass, total = [], 0, 0
    for p in paths:
        rec = json.loads(p.read_text())
        if rec.get("package_hash") != h:
            print(f"refusing: {p.name} was measured on hash {rec.get('package_hash')[:12]}, "
                  f"task is {h[:12]}")
            return 1
        if rec.get("models") != MODEL_LABEL:
            print(f"refusing: {p.name} has model label {rec.get('models')}")
            return 1
        vs = valid_trials(rec)
        passes = sum(1 for t in vs if t["outcome"] == "pass")
        batches.append({
            "batch": p.name, "verdict": rec.get("verdict"),
            "outcomes": [t["outcome"] for t in vs],
            "valid_trials": len(vs), "excluded": len(rec.get("trials", [])) - len(vs),
            "honest_passes": passes, "passes_over_valid": f"{passes}/{len(vs)}" if vs else "-",
        })
        total_pass += passes
        total += len(vs)

    pooled = (total_pass / total) if total else 0.0
    in_band_batch = any(
        b["valid_trials"] == 5 and BAND_LOW <= b["honest_passes"] <= BAND_HIGH for b in batches
    )
    pooled_ok = 0.2 <= pooled <= 0.8
    decision = {
        "package_hash": h, "models": MODEL_LABEL, "batches": batches,
        "pooled_passes": total_pass, "pooled_valid_trials": total, "pooled_pass_rate": round(pooled, 3),
        "rule": ("approve only if one complete 5-attempt batch has 1-3 honest passes with valid "
                 "failures AND the pooled pass rate over all batches is in [0.2, 0.8]"),
        "has_in_band_batch": in_band_batch, "pooled_in_band": pooled_ok,
        "approved": bool(in_band_batch and pooled_ok),
    }
    out_path.write_text(json.dumps(decision, indent=1) + "\n")
    print(json.dumps(decision, indent=1))
    return 0 if decision["approved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
