"""Task-quality gate: `harbor check` with our rubric (generator/quality_rubric.toml).

`harbor check` runs a reviewer agent (terminus-2 + config.MODEL) over the task in
a container and returns pass/fail/not_applicable per criterion. Criteria whose
failure means a run could fail for invalid reasons, or that the task can be
gamed, block the task; the rest are fed back to the repair round as advice.
"""

import json
import subprocess
from pathlib import Path

from evaluator.harbor_runner import _harbor_bin, parse_job
from generator.config import JOBS_DIR, MODEL

RUBRIC = Path(__file__).resolve().parents[1] / "generator" / "quality_rubric.toml"

# Only criteria tied to an invalid failure or a hackable task block a candidate:
# instruction/test alignment, determinism, anti-cheating and valid failure modes. Format
# criteria (structured_data_schema, file_reference_mentioned) are advisory: the full rubric
# blocks 5 of AfterQuery's own 6 example tasks, so it rejects tasks a human reviewer accepts.
BLOCKING = {
    "behavior_in_task_description",
    "behavior_in_tests",
    "anti_cheating_measures",
    "tests_or_solution_in_image",
    "hardcoded_solution",
    "deterministic_tests",
    "valid_failure_modes",
}


def run_check(task_dir: Path, job_name: str, jobs_dir: Path | str = JOBS_DIR) -> dict:
    """Run `harbor check` on one task. Returns outcomes, blocking failures and cost."""
    cmd = [
        _harbor_bin(),
        "check",
        str(task_dir),
        "-r",
        str(RUBRIC),
        "-a",
        "terminus-2",
        "-m",
        f"openrouter/{MODEL}",
        "--ak",
        "max_turns=40",
        "-o",
        str(jobs_dir),
        "--job-name",
        job_name,
        "-q",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    job_dir = Path(jobs_dir) / job_name
    report_path = job_dir / "check_report.json"
    if not report_path.exists():
        return {
            "ok": False,
            "error": (proc.stderr or proc.stdout)[-1500:],
            "cost_usd": 0.0,
            "outcomes": {},
            "blocking_failures": [],
            "advice": [],
        }
    checks = json.loads(report_path.read_text())["results"][0]["checks"]
    outcomes = {name: c["outcome"] for name, c in checks.items()}
    failed = {name: c["explanation"] for name, c in checks.items() if c["outcome"] == "fail"}
    cost = sum(t.priced_cost() for t in parse_job(job_dir))
    return {
        "ok": not (failed.keys() & BLOCKING),
        "outcomes": outcomes,
        "blocking_failures": [f"{n}: {e}" for n, e in failed.items() if n in BLOCKING],
        "advice": [f"{n}: {e}" for n, e in failed.items() if n not in BLOCKING],
        "cost_usd": cost,
    }
