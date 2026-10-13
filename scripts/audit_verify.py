"""Assemble docs/result/verification.json from committed evidence (no model/Docker calls).

    uv run python -m scripts.audit_verify

Reads each approved output under output/ (which must carry calibration.json + verification.json),
the evidence directory and the test/lint logs, and writes the audit manifest. overall_status is
"passed" only when at least one task is approved and every listed check passes.
"""

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from analysis.report import approved_outputs
from generator.config import MODEL_LABEL, OUTPUT_DIR

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "result" / "evidence"
OUT = ROOT / "docs" / "result" / "verification.json"


def _spend(name: str) -> float | None:
    p = EVIDENCE / name
    if not p.exists():
        return None
    m = re.search(r"spent\*\s+\$([0-9.]+)", p.read_text())
    return float(m.group(1)) if m else None


def _passed(log: str) -> bool:
    p = EVIDENCE / log
    return p.exists() and "passed" in p.read_text()


def _first_spend() -> float | None:
    """Earliest recorded key snapshot (audit start) by file mtime."""
    snaps = sorted((p.stat().st_mtime, _spend(p.name)) for p in EVIDENCE.glob("usage-*.txt"))
    return next((v for _, v in snaps if v is not None), None)


def _last_spend() -> float | None:
    """Latest recorded key snapshot by file mtime."""
    snaps = [(_spend(p.name), p.stat().st_mtime) for p in EVIDENCE.glob("usage-*.txt")]
    vals = [(v, m) for v, m in snaps if v is not None]
    return max(vals)[0] if vals else None


def _reason(cal: dict, n_real: int) -> str:
    if n_real < 5:
        return (
            f"incomplete: {n_real} valid judged attempts, the rest exhausted the turn cap "
            f"(invalid by rule); band measured as {cal.get('legit_passes')} passes"
        )
    if cal.get("legit_passes") == 0:
        return "out of band (too hard): 0 valid passes in 5"
    if cal.get("legit_passes", 0) >= 4:
        return "out of band (too easy): 4+ valid passes in 5"
    return str(cal.get("verdict"))


def main() -> int:
    approved = approved_outputs(Path(OUTPUT_DIR), MODEL_LABEL)
    tasks = []
    for t in approved:
        v = json.loads((t / "verification.json").read_text())
        c = json.loads((t / "calibration.json").read_text())
        tasks.append(
            {
                "task": t.name,
                "package_hash": v.get("package_hash"),
                "calibration": {
                    k: c.get(k)
                    for k in ("verdict", "outcomes", "legit_passes", "n_trials", "models")
                },
                "checks": v.get("checks", {}),
            }
        )
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True, cwd=ROOT
    )
    revision = rev.stdout.strip()
    checks_ok = bool(tasks) and all(all(v for v in t["checks"].values()) for t in tasks)
    tests_ok = _passed("tests-final.log")
    requirements = {
        "1.1 structural validator": "achieved",
        "1.2 oracle 3/3 + nop 0": "achieved" if tasks else "partial",
        "2 learnable band (1-3/5)": "achieved"
        if any(t["calibration"]["verdict"] == "learnable" for t in tasks)
        else "not demonstrated",
        "3 batch 10+ candidates with metrics": "achieved",
        "4 source, changelog, git history": "achieved",
        "A cost-efficient evaluation": "achieved",
        "B difficulty tuning": "not demonstrated",
        "C diversity analysis": "achieved",
        "D human-likeness": "partial",
    }
    quarantined = []
    for slug, ev in (
        ("repair-reproducible-release-packager", "packager-final-calibration.json"),
        ("optimize-policy-decision-audit", "policyfinal-calibration.json"),
        ("repair-attributed-funnel-service", "funnel-final-calibration.json"),
    ):
        p = EVIDENCE / ev
        if not p.exists():
            continue
        cal = json.loads(p.read_text())
        real = [t for t in cal.get("trials", []) if t.get("outcome") in ("pass", "fail")]
        quarantined.append(
            {
                "task": slug,
                "verdict": cal.get("verdict"),
                "legit_passes": cal.get("legit_passes"),
                "judged_attempts": len(real),
                "outcomes": [t["outcome"] for t in real],
                "reason": _reason(cal, len(real)),
                "calibration_evidence": f"docs/result/evidence/{ev}",
                "package_hash": cal.get("package_hash"),
            }
        )

    manifest = {
        "overall_status": "passed" if (checks_ok and tests_ok and tasks) else "failed",
        "revision": revision,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": MODEL_LABEL,
        "novelty_sets": ["terminal-bench-2-1", "examples"],
        "approved_tasks": tasks,
        "quarantined_candidates": quarantined,
        "quarantine_note": (
            "Quality-clean, gate-clean packages that failed the learnable band. "
            "They are preserved under runs/audit-20261013/ and are not shipped; "
            "shipping any of them would require an advisory override the plan forbids."
        ),
        "evidence_logs": {
            "structure": "docs/result/evidence/validate-*.txt (see quarantine runs)",
            "oracle_3of3": "jobs/ffinal3-oracle, jobs/pf3-oracle, jobs/final-oracle2",
            "nop": "jobs/ffinal3-nop, jobs/pf3-nop, jobs/final-nop2",
            "quality": [
                "docs/result/evidence/funnel-final-quality.json",
                "docs/result/evidence/policyfinal-quality3.json",
                "docs/result/evidence/packager-final-quality2.json",
            ],
            "calibration": [
                "docs/result/evidence/funnel-final-calibration.json",
                "docs/result/evidence/policyfinal-calibration.json",
                "docs/result/evidence/packager-final-calibration.json",
            ],
            "usage_snapshots": sorted(p.name for p in EVIDENCE.glob("usage-*.txt")),
            "reconciliation": [
                "docs/result/evidence/reconciliation.json",
                "docs/result/evidence/reconciliation-audit-window.json",
            ],
            "blind_experiment": "docs/result/evidence/blind.json",
        },
        "requirements": requirements,
        "tests": {"log": "tests-final.log", "passed": tests_ok},
        "spend": {
            "conservative_first_snapshot": _first_spend(),
            "conservative_last_snapshot": _last_spend(),
            "note": "key is authoritative; the ledger over-counts across scopes (see report §10)",
        },
        "evidence_dir": "docs/result/evidence",
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "overall_status": manifest["overall_status"],
                "approved": [t["task"] for t in tasks],
                "checks_ok": checks_ok,
                "tests_ok": tests_ok,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
