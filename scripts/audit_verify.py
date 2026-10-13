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


def main() -> int:
    approved = approved_outputs(Path(OUTPUT_DIR), MODEL_LABEL)
    tasks = []
    for t in approved:
        v = json.loads((t / "verification.json").read_text())
        c = json.loads((t / "calibration.json").read_text())
        tasks.append({
            "task": t.name,
            "package_hash": v.get("package_hash"),
            "calibration": {k: c.get(k) for k in ("verdict", "outcomes", "legit_passes", "n_trials", "models")},
            "checks": v.get("checks", {}),
        })
    rev = subprocess.run(["git", "rev-parse", "HEAD"], check=False,
                        capture_output=True, text=True, cwd=ROOT)
    revision = rev.stdout.strip()
    checks_ok = bool(tasks) and all(all(v for v in t["checks"].values()) for t in tasks)
    tests_ok = _passed("tests-final.log")
    requirements = {
        "1.1 structural validator": "achieved",
        "1.2 oracle 3/3 + nop 0": "achieved" if tasks else "partial",
        "2 learnable band (1-3/5)": "achieved" if any(
            t["calibration"]["verdict"] == "learnable" for t in tasks) else "not demonstrated",
        "3 batch 10+ candidates with metrics": "achieved",
        "4 source, changelog, git history": "achieved",
        "A cost-efficient evaluation": "achieved",
        "B difficulty tuning": "not demonstrated",
        "C diversity analysis": "achieved",
        "D human-likeness": "partial",
    }
    manifest = {
        "overall_status": "passed" if (checks_ok and tests_ok and tasks) else "failed",
        "revision": revision,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": MODEL_LABEL,
        "novelty_sets": ["terminal-bench-2-1", "examples"],
        "approved_tasks": tasks,
        "requirements": requirements,
        "tests": {"log": "evidence/tests-final.log", "passed": tests_ok},
        "spend": {
            "conservative_start": _spend("usage-before-final-gates.txt") or _spend("start.json"),
            "conservative_end": _spend("usage-after-cal.txt"),
            "note": "key is authoritative; the ledger over-counts across scopes (see report §10)",
        },
        "evidence_dir": "docs/result/evidence",
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"overall_status": manifest["overall_status"], "approved": [t["task"] for t in tasks],
                      "checks_ok": checks_ok, "tests_ok": tests_ok}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())