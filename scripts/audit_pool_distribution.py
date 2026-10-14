"""Recompute the pool's outcome distribution under the approval standard, from evidence.

    uv run python -m scripts.audit_pool_distribution OUT.json

The audited report and the deck both quote a distribution of candidate calibration verdicts
(`too_easy` / `too_hard` / `invalid` / `learnable`). A verdict label alone is not the standard the
rest of the submission applies: `approval_errors()` requires **five judged attempts** with 1-3 honest
passes. So this script re-derives the distribution from the recorded trials under that same rule, and
reports both counts side by side.

It exists because the two disagree. One candidate carries the label `learnable` on the strength of
**one pass out of three judged attempts** - a curtailed record, which is exactly the defect the report
uses to disqualify `repair-log-replay-sql` (1/3) elsewhere - and a second carries the label while its
overall pipeline status is `failed`. Quoting the label count would overstate the in-band yield.

Writes both distributions, the per-candidate table and the discrepancy to OUT.json.
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/result/evidence"
# The approval standard, in one place: five judged attempts, 1-3 of them honest passes.
FULL_ATTEMPTS = 5
BAND = (1, 3)


def classify(cal: dict) -> tuple[str, int, int]:
    """Return (label, judged_attempts, honest_passes) for one candidate's calibration record."""
    outcomes = cal.get("outcomes") or []
    judged = [o for o in outcomes if o in ("pass", "fail")]
    passes = sum(1 for o in judged if o == "pass")
    return cal.get("verdict"), len(judged), passes


def main() -> int:
    out_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else EVIDENCE / "pool-distribution.json"
    )
    hist = json.loads((EVIDENCE / "historical-data.json").read_text())
    candidates = hist.get("candidates") or []

    rows = []
    for idx, cand in enumerate(candidates):
        cal = cand.get("calibration") or {}
        label, judged, passes = classify(cal)
        in_band = bool(label) and judged == FULL_ATTEMPTS and BAND[0] <= passes <= BAND[1]
        rows.append(
            {
                "index": idx,
                "candidate": cand.get("candidate"),
                "origin": "reused" if cand.get("reused_from") else "fresh",
                "pipeline_status": cand.get("status"),
                "label": label,
                "judged_attempts": judged,
                "passes": passes,
                "full_five_trial_record": judged == FULL_ATTEMPTS,
                "in_band_by_approval_standard": in_band,
            }
        )

    labelled = [r for r in rows if r["label"]]
    label_counts = dict(Counter(r["label"] for r in labelled))
    standard_counts = dict(Counter(r["label"] for r in labelled if r["full_five_trial_record"]))
    in_band = [r for r in labelled if r["in_band_by_approval_standard"]]
    mislabelled = [
        {
            "candidate": r["candidate"],
            "label": r["label"],
            "passes": r["passes"],
            "judged_attempts": r["judged_attempts"],
            "pipeline_status": r["pipeline_status"],
            "why": (
                f"labelled {r['label']} on {r['passes']}/{r['judged_attempts']} judged attempts, which is a "
                f"curtailed record, not a full {BAND[0]}-{BAND[1]}/{FULL_ATTEMPTS} statement"
            ),
        }
        for r in labelled
        if r["label"] == "learnable" and not r["full_five_trial_record"]
    ]
    failed_but_in_band = [
        r["candidate"] for r in in_band if r["pipeline_status"] == "failed"
    ]

    manifest = {
        "source": "docs/result/evidence/historical-data.json",
        "standard": {
            "judged_attempts_required": FULL_ATTEMPTS,
            "passes_in_band": list(BAND),
            "note": "the same rule `analysis/package_evidence.approval_errors` applies to an approval",
        },
        "candidate_records": len(rows),
        "candidates_with_a_calibration_label": len(labelled),
        "candidates_without_any_calibration": len(rows) - len(labelled),
        "by_label": label_counts,
        "by_label_restricted_to_full_five_trial_records": standard_counts,
        "in_band_by_approval_standard": [
            {"candidate": r["candidate"], "passes": r["passes"], "pipeline_status": r["pipeline_status"]}
            for r in in_band
        ],
        "n_in_band_by_approval_standard": len(in_band),
        "n_labelled_learnable": label_counts.get("learnable", 0),
        "labelled_learnable_without_a_full_record": mislabelled,
        "in_band_but_pipeline_status_failed": failed_but_in_band,
        "discrepancy": (
            f"{label_counts.get('learnable', 0)} candidates carry the label `learnable`, but only "
            f"{len(in_band)} have the full {FULL_ATTEMPTS}-attempt record the approval standard requires"
            + (f"; {len(failed_but_in_band)} of those also has pipeline status `failed`" if failed_but_in_band else "")
        ),
        "candidates": rows,
    }
    out_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "label_learnable": manifest["n_labelled_learnable"],
                "in_band_by_standard": manifest["n_in_band_by_approval_standard"],
                "records": manifest["candidate_records"],
                "with_label": manifest["candidates_with_a_calibration_label"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
