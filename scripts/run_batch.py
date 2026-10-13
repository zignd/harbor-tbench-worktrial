"""Generate and gate a batch of candidate tasks.

    uv run --env-file .env python -m scripts.run_batch --n 3 --seed 1 --budget 20
    DEV_MODE=1 uv run --env-file .env python -m scripts.run_batch --n 2 --seed 7
    uv run python -m scripts.run_batch --n 1 --dry-run     # no model calls at all

Specs are sampled inverse-frequency against every earlier candidate's spec, so
successive batches keep spreading across the taxonomy. `--budget` caps what
this batch may spend (on top of the global authorization and reserve in
generator/config.py); no new candidate starts once it's used up. `--workers`
candidates build in parallel (default 3); a rerun resumes the saved batch plan.

--dry-run replaces every model call with fixtures (the Phase 0 blueprint and
authored package) but runs the real gates, so the plumbing can be exercised
for free.
"""

import argparse
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from analysis.ledger import Event, Ledger
from generator import pipeline
from generator.blueprint import Blueprint
from generator.spec import TaskSpec, sample_specs
from scripts.calibrate_candidates import calibrate_one
from scripts.tune_candidates import tune_one

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
FIXTURE_TASK = (
    FIXTURES / "harbor_jobs/p0-metatask-sonnet/metatask-sonnet__XBQDvdF/artifacts/app/output"
)


def _history() -> list[TaskSpec]:
    specs = []
    for path in sorted(pipeline.CANDIDATES_DIR.glob("*/spec.json")):
        specs.append(TaskSpec(**json.loads(path.read_text())))
    return specs


def _status(cand: pipeline.Candidate) -> dict:
    path = cand.dir / "status.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _batch_specs(n: int, seed: int, plan_dir: Path) -> list[TaskSpec]:
    """The batch's specs, sampled once and saved so a rerun resumes the same candidates.

    Sampling depends on the history of earlier candidates, which grows as the
    batch runs; without the saved plan a restart would draw different specs.
    """
    plan = plan_dir / f"seed{seed}-n{n}.json"
    if plan.exists():
        return [TaskSpec(**d) for d in json.loads(plan.read_text())]
    specs = sample_specs(n, seed=seed, history=_history())
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(json.dumps([s.model_dump() for s in specs], indent=1))
    return specs


def _install_dry_run(ledger_path: Path) -> Ledger:
    """Swap model-calling stages for fixtures; gates stay real."""
    blueprint = Blueprint(**json.loads((FIXTURES / "blueprint_ledger.json").read_text()))

    def fake_blueprint(cand, ledger):
        cand.blueprint = blueprint
        cand.save("spec.json", cand.spec.model_dump())
        cand.save("blueprint.json", blueprint.model_dump())
        return True

    def fake_author(cand, ledger, attempt, feedback=None, previous=None):
        if cand.task_dir.exists():
            shutil.rmtree(cand.task_dir)
        shutil.copytree(FIXTURE_TASK, cand.task_dir)
        shutil.copy(pipeline.collect_package.__globals__["STANDARD_TEST_SH"],
                    cand.task_dir / "tests" / "test.sh")  # fmt: skip
        bp = cand.blueprint
        (cand.task_dir / "task.toml").write_text(
            pipeline.make_task_toml(bp.slug, bp.title, bp.difficulty, bp.category, bp.tags)
        )
        return True

    pipeline.stage_blueprint = fake_blueprint
    pipeline.stage_author = fake_author
    pipeline.run_check = lambda task_dir, name: {
        "ok": True, "outcomes": {}, "blocking_failures": [], "advice": [], "cost_usd": 0.0
    }  # fmt: skip
    pipeline.novelty.judge_same_task = lambda text, index=None: {
        "novel": True, "verdicts": [], "nearest": [], "cost_usd": 0.0
    }  # fmt: skip
    # Every dry-run candidate is the same fixture package, so the novelty gate would
    # (rightly) reject each as a copy of its siblings: index only the published corpus.
    pipeline.novelty.gate_index = lambda candidates_dir, exclude="": (
        pipeline.novelty.default_index()
    )
    pipeline.budget.check = lambda expected: None
    pipeline.redteam = lambda task_dir, name: {
        "hackable": False, "reward": 0.0, "exploit": "", "cost_usd": 0.0, "trial": None
    }  # fmt: skip
    pipeline.CANDIDATES_DIR = ledger_path.parent / "candidates"
    # Gate jobs go under the dry-run dir too, so they can never collide with real runs.
    pipeline.JOBS_DIR = str(ledger_path.parent / "jobs")
    real_run = pipeline.run_with_retries
    pipeline.run_with_retries = lambda *a, **k: real_run(*a, **{"jobs_dir": pipeline.JOBS_DIR, **k})
    return Ledger(ledger_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=3, help="candidates to generate")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--budget", type=float, default=20.0, help="max spend for this batch")
    parser.add_argument("--workers", type=int, default=3, help="candidates built in parallel")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="calibrate each candidate against Opus as soon as it passes every gate",
    )
    parser.add_argument(
        "--tune",
        action="store_true",
        help="with --calibrate: tune a too-easy/too-hard task right away (up to 2 rounds)",
    )
    parser.add_argument("--dry-run", action="store_true", help="no model calls (fixtures)")
    args = parser.parse_args()

    if args.dry_run:
        ledger = _install_dry_run(Path("jobs/dry-run/ledger.jsonl"))
    else:
        ledger = Ledger()
    start_cost = ledger.total_cost()
    plan_dir = (
        Path("jobs/dry-run/batches") if args.dry_run else pipeline.CANDIDATES_DIR.parent / "batches"
    )
    specs = _batch_specs(args.n, args.seed, plan_dir)

    def build(spec: TaskSpec) -> tuple | None:
        spent = ledger.total_cost() - start_cost
        if spent >= args.budget:
            print(f"batch budget used (${spent:.2f} of ${args.budget:.2f}); skipping", flush=True)
            return None
        cand = pipeline.Candidate(spec)
        status = _status(cand)
        if status.get("status") == "building" and _alive(status.get("pid")):
            print(f"{cand.cand_id}  (being built by pid {status['pid']})", flush=True)
            return None
        if status.get("status") == "gated" and args.calibrate and not args.dry_run:
            if not (cand.dir / "calibration.json").exists():  # gated before a crash
                calibrate_one(cand.dir, ledger)
            if args.tune:  # no-op unless calibrated too easy/hard and not yet tuned
                tune_one(cand.dir, ledger)
            return None
        if status and status.get("status") != "building":  # resume: already ran to a final status
            print(f"{cand.cand_id}  (already {status['status']})")
            return None
        # Claim it: other batch processes skip a candidate with a status file, and a
        # claim whose process died (crash, reboot) is taken over and resumed.
        cand.save("status.json", {"status": "building", "pid": os.getpid()})
        try:
            cand = pipeline.build_candidate(cand, ledger)
        except pipeline.budget.BudgetExceeded as e:
            print(f"budget guard stopped {cand.cand_id}: {e}", flush=True)
            return None
        except Exception as e:  # noqa: BLE001 - one broken candidate must not stop the batch
            cand.status = "error"
            cand.save("status.json", {"status": "error", "error": f"{type(e).__name__}: {e}"})
            ledger.append(
                Event("error", cand.cand_id, {"error": f"{type(e).__name__}: {e}"[:2000]})
            )
        if args.calibrate and cand.status == "gated" and not args.dry_run:
            # Straight to calibration (and tuning): a gated task no longer waits for a run.
            calibrate_one(cand.dir, ledger)
            if args.tune:
                tune_one(cand.dir, ledger)
        cost = sum(e.cost_usd for e in ledger.events(task=cand.cand_id))
        slug = cand.blueprint.slug if cand.blueprint else "-"
        print(f"{cand.cand_id}  {slug:40}  {cand.status:9}  ${cost:.2f}", flush=True)
        return cand.cand_id, slug, cand.status, cost

    # Authoring is API-bound (its container idles), so candidates build in parallel;
    # each still runs its own stages in order.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        summary = [r for r in pool.map(build, specs) if r]

    total = ledger.total_cost() - start_cost
    gated = sum(s[2] == "gated" for s in summary)
    print(f"\n{gated}/{len(summary)} candidates passed every gate; batch cost ${total:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
