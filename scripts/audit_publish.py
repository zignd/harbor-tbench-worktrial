"""Place the audited task packages in output/ with their real calibration and verification records.

    uv run --env-file .env python -m scripts.audit_publish

A directory in output/ is NOT an approval. Each package is copied with:
  * calibration.json - the five-attempt record (outcomes, pass audits, failure labels and the
    verbatim instruction quotes) bound to the package hash it was measured on;
  * verification.json - the gate results for that exact package plus an explicit status.

`status` is "passed" only for a package that is genuinely approved (five valid judged attempts,
1-3 honest passes, valid failures only, no blocking quality finding). Everything else is recorded
as "failed" with a measured reason, so `analysis.report.approved_outputs()` keeps reporting the
truth and nothing here can be mistaken for a shipped task.
"""

import json
import shutil
from pathlib import Path

from analysis.package_evidence import approval_errors, package_hash
from generator.config import EVAL_MODEL, MODEL, MODEL_LABEL, OUTPUT_DIR

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "docs" / "result" / "evidence"

# destination slug -> (source task dir, calibration evidence, quality evidence or None)
PACKAGES = {
    "repair-attributed-funnel-service": (
        ROOT / "runs/audit-20261013/funnel-final",
        EV / "funnel-final-calibration.json",
        EV / "funnel-final-quality.json",
    ),
    "optimize-policy-decision-audit": (
        ROOT / "runs/audit-20261013/policy-final",
        EV / "policyfinal-calibration.json",
        EV / "policyfinal-quality3.json",
    ),
    "repair-reproducible-release-packager": (
        ROOT / "runs/audit-20261013/packager-final",
        EV / "packager-final-calibration.json",
        EV / "packager-final-quality2.json",
    ),
    "repair-log-replay-sql": (
        ROOT / "runs/candidates/official-37d13d3e2124-m/task",
        EV / "logrerplay-calibration.json",
        None,
    ),
    "global-settlement-reconciliation": (
        ROOT / "runs/candidates/official-e2bf5b4dd194/task",
        EV / "settlement-calibration.json",
        None,
    ),
}

WHY = {
    "repair-attributed-funnel-service": "measured 5/5 on a five-attempt rerun (78% pass rate over "
    "9 valid trials): too easy for GPT-5.4-mini",
    "optimize-policy-decision-audit": "measured 4/5 after its invalid wall-clock gate was removed: "
    "too easy for GPT-5.4-mini",
    "repair-reproducible-release-packager": "measured 0/5: too hard for GPT-5.4-mini",
    "repair-log-replay-sql": "historical record is a curtailed 1/3; not re-measured with five valid "
    "attempts on this package hash",
    "global-settlement-reconciliation": "measured 5/5: too easy for GPT-5.4-mini",
}


def main() -> int:
    out_root = Path(OUTPUT_DIR)
    out_root.mkdir(exist_ok=True)
    summary = []
    for slug, (src, cal_path, qual_path) in PACKAGES.items():
        if not cal_path.exists():
            summary.append({"task": slug, "placed": False, "reason": f"missing {cal_path.name}"})
            continue
        cal = json.loads(cal_path.read_text())
        quality = json.loads(qual_path.read_text()) if qual_path and qual_path.exists() else None
        cal = {**cal, "package_hash": package_hash(src), "models": MODEL_LABEL}
        if quality:
            cal["quality_blocking_failures"] = quality.get("blocking_failures", [])
            cal["quality_advice"] = quality.get("advice", [])
        errors = approval_errors(src, cal, MODEL_LABEL)
        real = [t for t in cal.get("trials", []) if t.get("outcome") in ("pass", "fail")]
        dest = out_root / slug
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        (dest / "calibration.json").write_text(json.dumps(cal, indent=1) + "\n")
        (dest / "verification.json").write_text(
            json.dumps(
                {
                    "status": "passed" if not errors else "failed",
                    "approved": not errors,
                    "package_hash": cal["package_hash"],
                    "models": MODEL_LABEL,
                    "author_model": MODEL,
                    "calibration_model": EVAL_MODEL,
                    "verdict": cal.get("verdict"),
                    "judged_attempts": len(real),
                    "legit_passes": cal.get("legit_passes"),
                    "why_not_approved": [] if not errors else WHY.get(slug, "see calibration.json"),
                    "approval_errors": errors,
                    "quality_blocking_failures": (quality or {}).get("blocking_failures", []),
                    "quality_advice": (quality or {}).get("advice", []),
                    "note": (
                        "A directory in output/ is not a shipped task. See docs/result/report.md "
                        "section 7 and docs/result/verification.json."
                    ),
                },
                indent=2,
            )
            + "\n"
        )
        summary.append(
            {
                "task": slug,
                "placed": True,
                "verdict": cal.get("verdict"),
                "judged_attempts": len(real),
                "legit_passes": cal.get("legit_passes"),
                "approved": not errors,
                "package_hash": cal["package_hash"][:12],
            }
        )
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
