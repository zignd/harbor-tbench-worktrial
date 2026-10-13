"""Cross-check that every number in the deck and report traces to committed evidence.

    uv run python -m scripts.audit_deck_consistency

Run from `make lint` so deck drift fails the build. Compares deck_data.json (the single source the
PPTX and the HTML deck are both rendered from) against docs/result/verification.json and the raw
evidence files, and greps the report for the same figures. Exits non-zero on any mismatch.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs" / "result"
EV = RESULT / "evidence"


def _load(p: Path, default=None):
    return json.loads(p.read_text()) if p.exists() else (default if default is not None else {})


def main() -> int:
    deck = _load(RESULT / "deck_data.json")
    ver = _load(RESULT / "verification.json")
    blind = _load(EV / "blind.json")
    curtail = _load(EV / "stretchA-curtailment.json")
    tuning = _load(EV / "stretchB-tuning.json", [])
    rubric = _load(EV / "rubric-comparison.json")
    report = (RESULT / "report.md").read_text()
    js = (RESULT / "build_deck.js").read_text()
    html = (RESULT / "presentation.html").read_text()
    approved = ver.get("approved_tasks", [])
    learned = sum(1 for r in tuning if r.get("any_round_learnable"))
    pair = curtail.get("current_pair", {})

    checks = {
        "deck and manifest agree on approved tasks": [
            t["task"] for t in deck.get("approved_tasks", [])
        ]
        == [t["task"] for t in approved],
        "every approved task is in band with five trials": all(
            t["calibration"]["verdict"] == "learnable"
            and t["calibration"]["n_trials"] == 5
            and 1 <= t["calibration"]["legit_passes"] <= 3
            for t in approved
        ),
        "deck spend equals the audited key reading": abs(
            deck["spend"]["conservative"] - ver["spend"]["conservative_last_snapshot"]
        )
        < 0.01,
        "deck remaining equals 500 minus spend": abs(
            deck["spend"]["remaining"] - (500 - deck["spend"]["conservative"])
        )
        < 0.02,
        "deck blind result equals blind.json": deck["blind"]["accuracy"] == blind.get("accuracy")
        and [round(x, 3) for x in deck["blind"]["wilson"]]
        == [round(x, 3) for x in blind["wilson95"]],
        "report states the approved task and the pooled rate": bool(approved)
        and approved[0]["task"] in report
        and "0.70" in report,
        "report curtailment figures match evidence": f"{pair.get('trials_saved_pct')}%" in report
        and f"${pair.get('usd_saved_by_curtailment')}" in report,
        "report tuning counts match evidence": f"{len(tuning)} tuning experiments" in report,
        "tuning never reached the band (reported as negative)": learned == 0
        and "| **0** |" in report,
        "report rubric figures match evidence": f"{rubric.get('examples_mean_blocking')}" in report
        and f"{rubric.get('generated_mean_blocking')}" in report,
        "deck stretch rows use the audited figures": all(
            x in js
            for x in (
                f"{pair.get('trials_saved_pct')}%",
                f"{len(tuning)} hash-bound tuning experiments",
                f"examples {rubric.get('examples_pass_rate', 0) * 100:.0f}/6",
            )
        ),
        "html deck lists the approved task": all(t["task"] in html for t in approved),
        "html deck loads no external resources": not re.search(r'(src|href)="https?://', html),
        "manifest does not claim spend reconciliation met": ver.get("requirements", {})
        .get("spend reconciliation detail", {})
        .get("acceptance_met")
        is False,
    }
    for name, ok in checks.items():
        print(f"{'ok  ' if ok else 'FAIL'} deck/report consistency: {name}")
    failed = [n for n, ok in checks.items() if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} consistency checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
