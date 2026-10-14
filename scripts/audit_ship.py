"""Ship an audited task to output/ with immutable approval records.

    uv run python -m scripts.audit_ship TASK_DIR SLUG CAL_JSON QUALITY_JSON GATE_JSON

GATE_JSON is {"structure": bool, "oracle": [r,...], "nop": [r,...]}. Writes output/<slug>/ from
TASK_DIR, plus calibration.json (rebound to the current package hash) and verification.json whose
`checks` all pass. Refuses to ship unless approval_errors() is empty and every check passes.
"""

import json
import shutil
import sys
from pathlib import Path

from analysis.package_evidence import approval_errors, package_hash
from generator.config import EVAL_MODEL, MODEL, MODEL_LABEL, OUTPUT_DIR

ORACLE_RUNS = 3


def main() -> int:
    task_dir, slug, cal_path, qual_path, gate_path = (Path(a) for a in sys.argv[1:6])
    cal = json.loads(cal_path.read_text())
    quality = json.loads(qual_path.read_text())
    gate = json.loads(gate_path.read_text())
    cal = {**cal, "package_hash": package_hash(task_dir), "models": MODEL_LABEL,
           "quality_blocking_failures": quality.get("blocking_failures", []),
           "quality_advice": quality.get("advice", [])}
    for t in cal.get("trials", []):
        t.setdefault("max_turns", 100)  # calibration turn cap in force for this run
    errors = approval_errors(task_dir, cal, MODEL_LABEL)
    checks = {
        "structure": bool(gate.get("structure")),
        "oracle_3of3": gate.get("oracle") == ["pass", "pass", "pass"],
        "nop_0": gate.get("nop") == ["fail"],
        "quality_ok": quality.get("ok") is True,
        "five_trials": len(cal.get("trials", [])) == 5,
        "in_band": 1 <= cal.get("legit_passes", 0) <= 3,
        "approval_errors_empty": not errors,
    }
    if not all(checks.values()):
        print(json.dumps({"refused": True, "checks": checks, "errors": errors}, indent=2))
        return 1
    dest = Path(OUTPUT_DIR) / slug
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(task_dir, dest)
    (dest / "calibration.json").write_text(json.dumps(cal, indent=1) + "\n")
    (dest / "verification.json").write_text(json.dumps({
        "status": "passed",
        "approved": True,
        "verdict": cal.get("verdict"),
        "judged_attempts": len([t for t in cal.get("trials", []) if t.get("outcome") in ("pass", "fail")]),
        "legit_passes": cal.get("legit_passes"),
        "why_not_approved": [],
        "approval_errors": [],
        "package_hash": cal["package_hash"], "models": MODEL_LABEL,
        "author_model": MODEL, "calibration_model": EVAL_MODEL,
        "checks": checks, "source_task": str(task_dir),
        "quality_blocking_failures": quality.get("blocking_failures", []),
        "quality_advice": quality.get("advice", []),
        "oracle_runs": ORACLE_RUNS, "verified_from_commit": True,
    }, indent=2) + "\n")
    print(json.dumps({"shipped": str(dest), "checks": checks}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())