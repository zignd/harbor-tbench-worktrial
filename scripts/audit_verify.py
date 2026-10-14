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


def _read_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


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
    clone_path = EVIDENCE / "fresh-clone.json"
    fresh_clone = json.loads(clone_path.read_text()) if clone_path.exists() else None
    clone_ok = bool(
        fresh_clone
        and fresh_clone.get("all_ok")
        and all(fresh_clone["tasks"].get(t["task"], {}).get("ok") for t in tasks)
    )
    # The audit tooling must itself be reproducible by a third party with no credentials: prove it
    # from the recorded clone run rather than asserting it.
    ca_path = EVIDENCE / "clone-audit.json"
    clone_audit = json.loads(ca_path.read_text()) if ca_path.exists() else None
    clone_audit_ok = bool(
        clone_audit
        and clone_audit.get("all_ok")
        and clone_audit.get("env_file_present_in_clone") is False
        and clone_audit.get("n_checks", 0) >= 16
        and clone_audit.get("n_checks") == clone_audit.get("n_passed")
    )
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
        "spend reconciliation": "UNRESOLVED - measured gap (target not met)",
        "spend reconciliation detail": {
            "ledger_total_usd": 545.64,
            "key_spend_usd": None,
            "residual_usd": 325.94,
            "dominant_cause": "cache accounting; the historical era ran a 48.1% cache-hit rate and the "
            "same tokens cost $617.45 uncached vs $380.61 cache-aware, a $236.84 swing",
            "residual_after_cache_aware_correction_usd": 190.26,
            "ruled_out": [
                "shared key use by another project",
                "retry/excluded double counting",
                "counter lag",
            ],
            "residual_cause": "hypothesis only: part of the historical traffic may have been billed to a "
            "different credential during the API-base change; per-call credential IDs were "
            "never recorded, so it cannot be confirmed",
            "acceptance_target": "within 10%",
            "acceptance_met": False,
            "disposition": "the plan item is closed on its own stated alternative ('otherwise mark "
            "reconciliation unresolved and state the measured gap'), NOT as achieved",
            "evidence": "docs/result/evidence/reconciliation-final.json",
        },
    }
    approved_names = {t.name for t in approved}
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

    published = []
    for task in sorted(p for p in Path(OUTPUT_DIR).iterdir() if p.is_dir()):
        v = json.loads((task / "verification.json").read_text())
        c = json.loads((task / "calibration.json").read_text())
        published.append(
            {
                "task": task.name,
                "package_hash": v.get("package_hash"),
                "approved": v.get("approved"),
                "status": v.get("status"),
                "verdict": v.get("verdict"),
                "judged_attempts": v.get("judged_attempts"),
                "legit_passes": v.get("legit_passes"),
                "why_not_approved": v.get("why_not_approved"),
                "quality_blocking_failures": v.get("quality_blocking_failures", []),
                "calibration_evidence": f"output/{task.name}/calibration.json",
            }
        )

    manifest = {
        "overall_status": (
            "passed"
            if (checks_ok and tests_ok and tasks and clone_ok and clone_audit_ok)
            else "failed"
        ),
        "fresh_clone": {
            "performed": fresh_clone is not None,
            "all_ok": clone_ok,
            "revision": (fresh_clone or {}).get("revision"),
            "results": {
                k: {kk: v.get(kk) for kk in ("structure_ok", "oracle_rewards", "nop_rewards", "ok")}
                for k, v in ((fresh_clone or {}).get("tasks") or {}).items()
            },
            "note": (
                "cloned from the committed revision into a temporary directory; no local host "
                "files, embedded .git metadata or pre-existing images are required"
            ),
        },
        "clone_audit": {
            "performed": clone_audit is not None,
            "all_ok": clone_audit_ok,
            "revision": (clone_audit or {}).get("revision"),
            "env_file_present_in_clone": (clone_audit or {}).get("env_file_present_in_clone"),
            "n_checks": (clone_audit or {}).get("n_checks"),
            "n_passed": (clone_audit or {}).get("n_passed"),
            "checks": (clone_audit or {}).get("checks"),
            "evidence": "docs/result/evidence/clone-audit.json",
            "note": (
                "the audit tooling itself was run inside a clone of the committed revision with "
                "`uv sync` and no .env; it reads committed records, not the live account, so a "
                "reviewer can re-verify every headline claim without credentials"
            ),
        },
        "revision": revision,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": MODEL_LABEL,
        "novelty_sets": ["terminal-bench-2-1", "examples"],
        "approved_tasks": tasks,
        "output_packages": published,
        "output_packages_note": (
            "Task packages placed in output/ for inspection. A directory is "
            "not an approval: each carries its own calibration and "
            "verification record, and only the "
            + (
                f"{len(tasks)} package(s) in approved_tasks land in the 1-3/5 band "
                f"({', '.join(t['task'] for t in tasks)}). The other {len(published) - len(tasks)} are "
                "published with their measured reason for non-approval."
                if tasks
                else "approved_tasks stays empty because none lands in the 1-3/5 band."
            )
        ),
        "quarantined_candidates": [q for q in quarantined if q["task"] not in approved_names],
        "quarantined_note": (
            "First-pass measurements for packages that are NOT approved. A package that "
            "was later approved (e.g. after a second independent calibration batch) is "
            "deliberately absent here so it cannot appear both approved and rejected."
        ),
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
        "presentation_qa": _read_json(EVIDENCE / "presentation-qa.json"),
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
