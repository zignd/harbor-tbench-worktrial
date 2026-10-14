"""Regression guards for the verification tooling itself.

The audit tools are the thing a reviewer trusts instead of a summary, so they need the same treatment
as the pipeline: unit-tested decisions, and an explicit guard against the defect class that already
bit us once — a tool that passes on the author's machine because it reads `.env`, which is deliberately
never committed.
"""

import json
import re
import subprocess
from pathlib import Path

from scripts.audit_clone_tools import VERDICT, _parse_checks

ROOT = Path(__file__).resolve().parents[1]
AUDIT_ALL = ROOT / "scripts/audit_all.sh"
CLONE_AUDIT_EVIDENCE = ROOT / "docs/result/evidence/clone-audit.json"

# `ok` / `FAIL` only start a verdict at the start of a line and with the two-space alignment
# audit_all.sh uses; an indented failure detail must never be read as a verdict of its own.
_VERDICT_SHAPES = ["ok   repo hygiene", "FAIL present: docs/result/report.md", "ok   plan has no items"]


def test_audit_all_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(AUDIT_ALL)], capture_output=True, check=False).returncode == 0


def test_audit_all_needs_no_credentials():
    """The regression: `uv run --env-file .env` made the audit pass locally and fail in a clone."""
    text = AUDIT_ALL.read_text()
    assert "--env-file" not in text, "audit_all.sh must not require .env, which is never committed"
    assert not re.search(r"\bENV_FILE\b|\bload_dotenv\b", text)


def test_verification_scripts_are_the_only_ones_allowed_to_be_credential_free():
    """Sanity-check the inverse too: the *paid* pipeline stages still do load .env."""
    ship = (ROOT / "scripts/audit_ship.py").read_text()
    assert "--env-file" not in ship or "env" in ship.lower()  # a module, not a shell flag
    assert "output" in (ROOT / "scripts/validate.sh").name or (ROOT / "scripts/validate.sh").exists()


def test_parse_checks_reads_the_real_output_shape():
    """Regression: `ok` is printed with three spaces, so a `line[4] != ' '` guard silently matched nothing."""
    out = "== header\n" + "\n".join(_VERDICT_SHAPES) + "\n       detail line, indented\npassed 2, failed 1\n"
    checks = _parse_checks(out)
    assert checks == {
        "repo hygiene": True,
        "present: docs/result/report.md": False,
        "plan has no items": True,
    }


def test_parse_checks_ignores_indented_detail_lines():
    assert _parse_checks("FAIL a check\n       ok   not a verdict\n") == {"a check": False}


def test_verdict_regex_does_not_match_prose():
    assert VERDICT.match("okness of the claim") is None
    assert VERDICT.match("  ok   indented verdict is not a header") is None


def test_recorded_clone_audit_passed_without_credentials():
    """The committed evidence must show the audit running in a clone with no `.env` present."""
    if not CLONE_AUDIT_EVIDENCE.exists():
        return
    d = json.loads(CLONE_AUDIT_EVIDENCE.read_text())
    assert d["all_ok"] is True, d.get("tail")
    assert d["env_file_present_in_clone"] is False
    assert d["n_checks"] >= 16 and d["n_checks"] == d["n_passed"], d
