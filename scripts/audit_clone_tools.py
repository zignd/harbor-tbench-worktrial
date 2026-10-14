"""Fresh-clone verification of the verification tooling (clone-safety of the audit itself).

    uv run python -m scripts.audit_clone_tools OUT.json

Clones the repository at the current committed revision into a temporary directory and runs
`scripts/audit_all.sh` *inside the clone*. The point is narrow and easy to get wrong: the audit
tooling must derive its conclusions from committed records alone, because `.env` is deliberately
never committed. A tool that needs `.env` passes on the author's machine and fails for a reviewer.

Writes the result (revision, per-check verdicts, whether `.env` was present, all_ok) to OUT.json.
Costs nothing: no model calls, no Docker.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# audit_all.sh prints aligned verdicts as `ok   NAME` (three spaces) and `FAIL NAME` (one space),
# with any failure detail indented. Anchoring on the alignment means an indented detail line can never
# be read as a verdict, while both header shapes are matched.
VERDICT = re.compile(r"^(?:(ok)\s{2,}|(FAIL))\s+(\S.*)$")


def _run(cmd, cwd, timeout=3600):
    return subprocess.run(cmd, check=False, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _parse_checks(stdout: str) -> dict[str, bool]:
    """Recover the per-check verdicts audit_all.sh prints as `ok NAME` / `FAIL NAME`."""
    checks = {}
    for line in stdout.splitlines():
        m = VERDICT.match(line)
        if m:
            checks[m.group(3).strip()] = m.group(1) == "ok"
    return checks


def main() -> int:
    out_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/result/evidence/clone-audit.json"
    )
    revision = _run(["git", "rev-parse", "HEAD"], ROOT).stdout.strip()
    clone_parent = Path(tempfile.mkdtemp(prefix="clone-audit-"))
    clone = clone_parent / "repo"
    sh = _run(["git", "clone", "--no-hardlinks", "--quiet", str(ROOT), str(clone)], ROOT)
    if sh.returncode != 0:
        print(json.dumps({"error": "clone failed", "stderr": sh.stderr[-2000:]}))
        return 1
    _run(["git", "-C", str(clone), "checkout", "--quiet", revision], clone)

    # A reviewer runs `uv sync` first. Do the same; if that cannot work offline, fall back to the
    # already-synced project environment and say so, so the evidence records what actually happened.
    sync = _run(["uv", "sync", "--quiet", "--frozen"], clone, timeout=1800)
    env_mode = "uv sync in clone"
    if sync.returncode != 0 and (ROOT / ".venv").is_dir():
        (clone / ".venv").symlink_to(ROOT / ".venv")
        env_mode = "symlinked synced project environment (uv sync unavailable offline)"
    env_note = (sync.stderr or sync.stdout).strip().splitlines()[-1:] if sync.returncode else []

    env_present = (clone / ".env").exists()
    r = _run(["bash", "scripts/audit_all.sh"], clone)
    checks = _parse_checks(r.stdout)
    passed = sum(checks.values())
    manifest = {
        "revision": revision,
        "clone": str(clone),
        "env_file_present_in_clone": env_present,
        "environment": env_mode,
        "environment_note": env_note,
        "checks": checks,
        "n_checks": len(checks),
        "n_passed": passed,
        "exit_code": r.returncode,
        "all_ok": r.returncode == 0 and bool(checks) and all(checks.values()),
        "tail": r.stdout.strip().splitlines()[-3:],
        "note": (
            "proves the audit tooling itself needs no credentials: it reads committed records, not the "
            "live account. Costs nothing and starts no Docker."
        ),
    }
    out_path.write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.rmtree(clone_parent, ignore_errors=True)
    print(
        json.dumps(
            {
                "all_ok": manifest["all_ok"],
                "n_passed": passed,
                "n_checks": len(checks),
                "env_file_present": env_present,
                "environment": env_mode,
            }
        )
    )
    return 0 if manifest["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
