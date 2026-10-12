"""Generate and gate a batch of candidate tasks.

    uv run --env-file .env python -m scripts.run_batch --n 3 --seed 1 --budget 20
    DEV_MODE=1 uv run --env-file .env python -m scripts.run_batch --n 2 --seed 7
    uv run python -m scripts.run_batch --n 1 --dry-run     # no model calls at all

Specs are sampled inverse-frequency against every earlier candidate's spec, so
successive batches keep spreading across the taxonomy. `--budget` caps what
this batch may spend (on top of the global authorization and reserve in
generator/config.py); no new candidate starts once it's used up.

--dry-run replaces every model call with fixtures (the Phase 0 blueprint and
authored package) but runs the real gates, so the plumbing can be exercised
for free.
"""

import argparse
import json
import shutil
from pathlib import Path

from analysis.ledger import Ledger
from generator import pipeline
from generator.blueprint import Blueprint
from generator.spec import TaskSpec, sample_specs

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
FIXTURE_TASK = (
    FIXTURES / "harbor_jobs/p0-metatask-sonnet/metatask-sonnet__XBQDvdF/artifacts/app/output"
)


def _history() -> list[TaskSpec]:
    specs = []
    for path in sorted(pipeline.CANDIDATES_DIR.glob("*/spec.json")):
        specs.append(TaskSpec(**json.loads(path.read_text())))
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
    pipeline.budget.check = lambda expected: None
    pipeline.redteam = lambda task_dir, name: {
        "hackable": False, "reward": 0.0, "exploit": "", "cost_usd": 0.0, "trial": None
    }  # fmt: skip
    pipeline.CANDIDATES_DIR = ledger_path.parent / "candidates"
    return Ledger(ledger_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=3, help="candidates to generate")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--budget", type=float, default=20.0, help="max spend for this batch")
    parser.add_argument("--dry-run", action="store_true", help="no model calls (fixtures)")
    args = parser.parse_args()

    if args.dry_run:
        ledger = _install_dry_run(Path("jobs/dry-run/ledger.jsonl"))
    else:
        ledger = Ledger()
    start_cost = ledger.total_cost()
    specs = sample_specs(args.n, seed=args.seed, history=_history())

    summary = []
    for spec in specs:
        spent = ledger.total_cost() - start_cost
        if spent >= args.budget:
            print(f"batch budget used (${spent:.2f} of ${args.budget:.2f}); stopping")
            break
        cand = pipeline.Candidate(spec)
        status_file = cand.dir / "status.json"
        if status_file.exists():  # resume: this spec already ran to a final status
            print(f"{cand.cand_id}  (already {json.loads(status_file.read_text())['status']})")
            continue
        cand = pipeline.build_candidate(cand, ledger)
        cost = sum(e.cost_usd for e in ledger.events(task=cand.cand_id))
        slug = cand.blueprint.slug if cand.blueprint else "-"
        summary.append((cand.cand_id, slug, cand.status, cost))
        print(f"{cand.cand_id}  {slug:40}  {cand.status:9}  ${cost:.2f}", flush=True)

    total = ledger.total_cost() - start_cost
    gated = sum(s[2] == "gated" for s in summary)
    print(f"\n{gated}/{len(summary)} candidates passed every gate; batch cost ${total:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
