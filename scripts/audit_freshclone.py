"""Fresh-clone verification of every approved task (plan item 4).

    uv run --env-file .env python -m scripts.audit_freshclone OUT.json

Clones the repository at the current committed revision into a temporary directory, then for each
directory under output/ runs scripts/validate.sh, `harbor run -a oracle -k 3` and `harbor run -a nop`
from the clone. Nothing outside the clone is read except the repository history itself: no local
host files, no embedded .git from this workspace, no pre-existing images or unpinned caches are
required, because every task builds from its own committed Dockerfile.

Writes the results (per-task rewards, validate verdict, clone path, revision) to OUT.json.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORACLE_RUNS = 3


def _run(cmd, cwd):
    return subprocess.run(cmd, check=False, cwd=cwd, capture_output=True, text=True, timeout=5400)


def _rewards(jobs: Path) -> list[float]:
    out = []
    for f in sorted(jobs.glob("*/result.json")):
        out.append((json.loads(f.read_text()).get("verifier_result") or {}).get("rewards", {}).get("reward"))
    return out


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/result/evidence/fresh-clone.json"
    revision = _run(["git", "rev-parse", "HEAD"], ROOT).stdout.strip()
    clone_parent = Path(tempfile.mkdtemp(prefix="fresh-clone-"))
    clone = clone_parent / "repo"
    sh = _run(["git", "clone", "--no-hardlinks", "--quiet", str(ROOT), str(clone)], ROOT)
    if sh.returncode != 0:
        print(json.dumps({"error": "clone failed", "stderr": sh.stderr[-2000:]}))
        return 1
    _run(["git", "-C", str(clone), "checkout", "--quiet", revision], clone)

    results = {}
    for task in sorted(p for p in (clone / "output").iterdir() if p.is_dir()):
        name = task.name
        entry = {"package_hash": json.loads((task / "verification.json").read_text())["package_hash"]}
        v = _run(["bash", "scripts/validate.sh", f"output/{name}"], clone)
        entry["structure_ok"] = "PASSED" in v.stdout
        entry["structure_tail"] = v.stdout.strip().splitlines()[-1:] or v.stderr.strip().splitlines()[-1:]
        o = _run(["uv", "run", "--env-file", ".env", "harbor", "run", "-p", f"output/{name}",
                  "-a", "oracle", "-k", str(ORACLE_RUNS), "-n", "1", "-o", "jobs",
                  "--job-name", f"clone-{name}-oracle", "-y", "-q"], clone)
        entry["oracle_rewards"] = _rewards(clone / "jobs" / f"clone-{name}-oracle")
        entry["oracle_ok"] = entry["oracle_rewards"] == [1.0] * ORACLE_RUNS
        n = _run(["uv", "run", "--env-file", ".env", "harbor", "run", "-p", f"output/{name}",
                  "-a", "nop", "-k", "1", "-n", "1", "-o", "jobs",
                  "--job-name", f"clone-{name}-nop", "-y", "-q"], clone)
        entry["nop_rewards"] = _rewards(clone / "jobs" / f"clone-{name}-nop")
        entry["nop_ok"] = entry["nop_rewards"] == [0.0]
        if o.returncode or n.returncode:
            entry["harbor_stderr_tail"] = (o.stderr + n.stderr).strip().splitlines()[-3:]
        entry["ok"] = entry["structure_ok"] and entry["oracle_ok"] and entry["nop_ok"]
        results[name] = entry

    manifest = {
        "revision": revision, "clone": str(clone), "tasks": results,
        "all_ok": bool(results) and all(t["ok"] for t in results.values()),
        "note": "clone is disposable; only committed files and Docker build caches from the clone are used",
    }
    out_path.write_text(json.dumps(manifest, indent=2) + "\n")
    shutil.rmtree(clone_parent, ignore_errors=True)
    print(json.dumps({"all_ok": manifest["all_ok"], "tasks": list(results)}))
    return 0 if manifest["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
