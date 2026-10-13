"""Exploratory study: who writes the task, who solves it (docs/study-report.md).

NOT part of the work trial's pipeline. A weak and a strong model (same family) each write a
task from the SAME spec; every valid task is solved 5x by each of the two models with plain
terminus-2. Same harness, only the models change. Runs and ledger events are tagged
`study`, everything lives under runs/study/, nothing is shipped, calibrated against the
official models or counted in the report's funnel. Resumable: finished steps are skipped.

    uv run --env-file .env python -m scripts.study gap          # do the two solvers differ?
    uv run --env-file .env python -m scripts.study run --specs 8
    uv run python -m scripts.study summary
"""

import argparse
import json
import os
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from analysis import budget
from analysis.judge import analyze_failure
from analysis.ledger import Event, Ledger, hash_dir
from analysis.study import summarize
from evaluator.harbor_runner import run_with_retries
from evaluator.slots import machine_slots
from generator.author import collect_package, make_task_toml, render_metatask
from generator.blueprint import Blueprint, make_blueprint
from generator.config import (
    GATE_CONCURRENCY,
    JOBS_DIR,
    METATASK_MAX_TURNS,
    METATASK_REPAIR_MAX_TURNS,
    METATASK_SUMMARIZE_THRESHOLD,
    RUNS_DIR,
)
from generator.pipeline import gate_functional, gate_static
from generator.spec import TaskSpec, sample_specs

# Pair 1 (deepseek-v4.1-flash / deepseek-v4-pro) was abandoned for speed: flash spent 12-27k
# hidden reasoning tokens per authoring step (3-6 min each). Partial evidence is archived in
# runs/study-deepseek-partial/. Override with STUDY_WEAK / STUDY_STRONG.
MODELS = {
    "weak": os.environ.get("STUDY_WEAK", "google/gemini-2.5-flash-lite"),
    "strong": os.environ.get("STUDY_STRONG", "google/gemini-3-flash-preview"),
}
SEED = 2026
SOLVE_TRIALS = 5
SOLVE_MAX_TURNS = 100
ACCOUNT_CEILING_USD = 400.0  # user limit: total key spend never passes $400 of $500
CAP_USD = 40.0  # user-approved hard cap for the whole study (estimate ~$25)
GAP_CAP_USD = 8.0
EXPECTED_USD = {"author": {"weak": 0.8, "strong": 2.0}, "solve": {"weak": 0.8, "strong": 2.0}}
MAX_REPAIRS = int(os.environ.get("STUDY_REPAIRS", "3"))  # same for both authors
BLUEPRINT_TRIES = 5  # a reply that is not valid blueprint JSON is retried, for both authors
STUDY_DIR = Path(RUNS_DIR) / "study"
PILOT_PACKAGES = [
    ("p0-ledger-reconcile", "task"),
    ("2f505f92f1c8", "before_tune_r1"),
    ("31ca491030e9", "task"),
    ("b540d2ce9b80", "task"),
    ("3bbd19e55510", "before_tune_r1"),
]

_lock = threading.Lock()


class CapReached(RuntimeError):
    pass


def study_spent(ledger: Ledger) -> float:
    return ledger.total_cost(mode="study")


def guard(ledger: Ledger, expected: float, cap: float = CAP_USD) -> None:
    """Refuse a paid step that would pass the study cap or the account's reserve."""
    spent = study_spent(ledger)
    if spent + expected > cap:
        raise CapReached(f"study spend ${spent:.2f} + ~${expected:.2f} would pass ${cap:.2f}")
    budget.check(expected, authorized_usd=ACCOUNT_CEILING_USD)


def record(ledger: Ledger, task: str, stage: str, result: dict, cost=0.0, t0=None, h="") -> None:
    seconds = time.monotonic() - t0 if t0 else 0.0
    ledger.append(
        Event(stage, task, result, cost_usd=cost, seconds=seconds, inputs_hash=h, mode="study")
    )


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, default=str))


def _load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


# --- building: the author's blueprint and package, then the free gates ----------------------


def make_bp(author: str, spec: TaskSpec, d: Path, ledger: Ledger, task: str) -> Blueprint | None:
    saved = _load(d / "blueprint.json")
    if saved:
        return Blueprint(**saved)
    for attempt in range(BLUEPRINT_TRIES):
        guard(ledger, 0.3)
        t0 = time.monotonic()
        try:
            bp, cost = make_blueprint(
                spec, model=MODELS[author], max_tokens=12000 * min(attempt + 1, 3)
            )
        except Exception as e:  # noqa: BLE001  # unparseable reply or API error: the same retry for both authors
            record(ledger, task, "study_blueprint", {"ok": False, "error": str(e)[:300]}, t0=t0)
            continue
        record(ledger, task, "study_blueprint", {"ok": True, "slug": bp.slug}, cost, t0)
        _write(d / "blueprint.json", bp.model_dump())
        return bp
    return None


def author_once(author, bp, spec, d, ledger, task, attempt, feedback=None, previous=None) -> bool:
    guard(ledger, EXPECTED_USD["author"][author])
    t0 = time.monotonic()
    name = f"study-author-{author}-{d.name}-a{attempt}"
    meta_dir = Path(JOBS_DIR) / "metatasks" / name
    toml = make_task_toml(bp.slug, bp.title, bp.difficulty, bp.category, bp.tags)
    render_metatask(
        bp.to_markdown(spec), bp.slug, meta_dir, toml, previous=previous, feedback=feedback
    )
    counted, excluded = run_with_retries(
        meta_dir,
        "terminus-2",
        name,
        model=f"openrouter/{MODELS[author]}",
        agent_kwargs={
            "max_turns": METATASK_REPAIR_MAX_TURNS if previous else METATASK_MAX_TURNS,
            "proactive_summarization_threshold": METATASK_SUMMARIZE_THRESHOLD,
        },
    )
    trials = counted + excluded
    cost = sum(t.priced_cost() for t in trials)
    result = {"attempt": attempt, "outcome": counted[0].outcome if counted else "infra"}
    ok = False
    if counted:
        try:
            collect_package(counted[0].trial_dir, d / "task", toml)
            ok = True
        except FileNotFoundError as e:
            result["error"] = str(e)
    record(ledger, task, "study_author", result, cost, t0)
    return ok


def gates(author, d, ledger, task, attempt) -> list[str]:
    """Structure, lint, leak scan, build, oracle 3/3, nop 0 (all free)."""
    h = hash_dir(d / "task")
    tag = f"study-gate-{author}-{d.name}-a{attempt}".lower()
    t0 = time.monotonic()
    with machine_slots(1, GATE_CONCURRENCY, Path(JOBS_DIR) / ".gate-slots"):
        try:
            problems, _, built = gate_static(d / "task", tag)
        except FileNotFoundError as e:  # a package too incomplete to scan is an invalid task
            problems, built = [f"structure: {e.filename or e}: missing"], False
        result = {"problems": list(problems)}
        if built:
            found, functional = gate_functional(
                d / "task", f"study-gate-{author}-{d.name}-a{attempt}"
            )
            problems += found
            result |= functional | {"problems": list(problems)}
    record(ledger, task, "study_gate", result, 0.0, t0, h)
    return problems


def build(author: str, i: int, spec: TaskSpec, ledger: Ledger) -> dict:
    d = STUDY_DIR / "tasks" / f"{author}-{i:02d}"
    task = f"study-{author}-{i:02d}"
    done = _load(d / "record.json")
    if done:
        return done
    _write(d / "spec.json", spec.model_dump())
    rec = {"author": author, "spec_idx": i, "task_id": task, "built": False, "valid": False,
           "valid_first_try": False, "repairs": 0, "problems": []}  # fmt: skip
    cost0 = sum(e.cost_usd for e in ledger.events(task=task, mode="study"))
    try:
        bp = make_bp(author, spec, d, ledger, task)
        if bp is None:
            rec["problems"] = ["no parseable blueprint"]
        else:
            rec["slug"] = bp.slug
            feedback = None
            for attempt in range(MAX_REPAIRS + 1):
                previous = None
                if attempt and (d / "task").exists():
                    shutil.rmtree(d / "prev", ignore_errors=True)
                    shutil.copytree(d / "task", d / "prev")
                    previous = d / "prev"
                if not author_once(author, bp, spec, d, ledger, task, attempt, feedback, previous):
                    feedback = ["no package was produced in /app/output"]
                    rec["problems"] = feedback
                    continue
                rec["built"] = True
                problems = gates(author, d, ledger, task, attempt)
                rec["problems"] = problems
                rec["repairs"] = attempt
                if not problems:
                    rec["valid"], rec["valid_first_try"] = True, attempt == 0
                    break
                feedback = problems
    except CapReached as e:
        rec["problems"].append(f"stopped: {e}")
        rec["capped"] = True
    rec["author_cost"] = round(
        sum(e.cost_usd for e in ledger.events(task=task, mode="study")) - cost0, 4
    )
    if not rec.get("capped"):
        _write(d / "record.json", rec)
    return rec


# --- solving: 5 plain terminus-2 trials per solver, failures judged -------------------------


def solve(task_dir: Path, solver: str, name: str, ledger: Ledger, task: str, cap=CAP_USD,
          judge: bool = True) -> dict:  # fmt: skip
    guard(ledger, EXPECTED_USD["solve"][solver], cap)
    t0 = time.monotonic()
    counted, excluded = run_with_retries(
        task_dir, "terminus-2", name, model=f"openrouter/{MODELS[solver]}",
        attempts=SOLVE_TRIALS, concurrent=3, agent_kwargs={"max_turns": SOLVE_MAX_TURNS},
    )  # fmt: skip
    trials, judge_cost = [], 0.0
    for t in counted:
        row = {"outcome": t.outcome, "turns": t.n_episodes, "cost": round(t.priced_cost(), 4),
               "minutes": round(t.seconds / 60, 1), "judge_valid": None, "mode": ""}  # fmt: skip
        if t.outcome == "fail" and judge:
            try:
                j = analyze_failure(task_dir, t.trial_dir, t.trajectory_path)
                row |= {
                    "judge_valid": j["valid"],
                    "mode": j["mode"],
                    "quote": j["instruction_quote"],
                }
                judge_cost += j["cost_usd"]
            except Exception as e:  # noqa: BLE001  # an unjudged failure can't be called valid
                row |= {"judge_valid": False, "mode": "judge_error", "error": str(e)[:200]}
        trials.append(row)
    passes = sum(r["outcome"] == "pass" for r in trials)
    fails_valid = sum(r["outcome"] == "fail" and r["judge_valid"] is not False for r in trials)
    invalid = sum(r["outcome"] == "invalid" or r["judge_valid"] is False for r in trials)
    cost = sum(r["cost"] for r in trials) + judge_cost
    result = {"passes": passes, "fails_valid": fails_valid, "invalid": invalid,
              "excluded": len(excluded), "trials": trials, "cost": round(cost, 4)}  # fmt: skip
    record(ledger, task, "study_solve", {"solver": solver, **{k: v for k, v in result.items()
           if k != "trials"}}, cost, t0)  # fmt: skip
    return result


def solve_task(author: str, i: int, solver: str, ledger: Ledger) -> None:
    d = STUDY_DIR / "tasks" / f"{author}-{i:02d}"
    out = d / f"solve-{solver}.json"
    if out.exists():
        return
    try:
        res = solve(d / "task", solver, f"study-solve-{solver}-{author}-{i:02d}", ledger,
                    f"study-{author}-{i:02d}")  # fmt: skip
    except CapReached as e:
        print(f"{author}-{i:02d} x {solver}: skipped, {e}", flush=True)
        return
    _write(out, res)
    print(f"{author}-{i:02d} solved by {solver}: {res['passes']}p {res['fails_valid']}f "
          f"{res['invalid']}inv ${res['cost']:.2f}", flush=True)  # fmt: skip


# --- results --------------------------------------------------------------------------------


def collect() -> list[dict]:
    tasks = []
    for rec_path in sorted((STUDY_DIR / "tasks").glob("*/record.json")):
        rec = json.loads(rec_path.read_text())
        rec["solves"] = {s: _load(rec_path.parent / f"solve-{s}.json")
                         for s in MODELS if (rec_path.parent / f"solve-{s}.json").exists()}  # fmt: skip
        tasks.append(rec)
    # A task stopped at the deadline mid-rerun keeps its earlier, shorter-policy outcome
    # (flagged), so the weak author's tasks are not silently dropped from the counts.
    have = {t["task_id"] for t in tasks}
    for old in sorted((STUDY_DIR / "superseded").glob("*-record-1repair.json")):
        rec = json.loads(old.read_text())
        if rec["task_id"] not in have:
            rec |= {"solves": {}, "policy": "1 repair (rerun with 3 repairs not finished)"}
            tasks.append(rec)
    return tasks


def write_results(ledger: Ledger, n_specs: int) -> None:
    with _lock:
        tasks = collect()
        summary = summarize(tasks)
        _write(STUDY_DIR / "results.json", {
            "meta": {"pair": "gemini", "models": MODELS, "seed": SEED, "n_specs": n_specs, "cap_usd": CAP_USD,
                     "solve_trials": SOLVE_TRIALS, "solve_max_turns": SOLVE_MAX_TURNS,
                     "study_spend_usd": round(study_spent(ledger), 4),
                     "updated": datetime.now(UTC).isoformat(timespec="seconds"),
                     "exploratory": "user-approved deviation; never shipped or counted",
                     "incomplete_at_deadline": ["weak-02 (authoring still running when the study was stopped)"]},
            "summary": summary, "tasks": tasks})  # fmt: skip


def cmd_gap(ledger: Ledger) -> None:
    """Both solvers on the 5 pilot packages: do their pass rates differ?"""
    out = STUDY_DIR / "gap.json"
    rows = _load(out) or []
    done = {(r["solver"], r["candidate"]) for r in rows}
    jobs = [(s, c, sub) for c, sub in PILOT_PACKAGES for s in MODELS if (s, c) not in done]

    def one(job):
        s, c, sub = job
        task_dir = Path(RUNS_DIR) / "candidates" / f"official-{c}" / sub
        try:
            r = solve(task_dir, s, f"study-gap-{s}-{c}", ledger, f"study-gap-{c}",
                      cap=GAP_CAP_USD, judge=False)  # fmt: skip
        except CapReached as e:
            print(f"gap {s} {c}: skipped, {e}", flush=True)
            return
        with _lock:
            rows.append({"solver": s, "model": MODELS[s], "candidate": c, "passes": r["passes"],
                         "fails": r["fails_valid"], "invalid": r["invalid"], "cost": r["cost"],
                         "turns": [t["turns"] for t in r["trials"]]})  # fmt: skip
            _write(out, rows)
        print(f"gap {s:6} {c:22} {r['passes']}p {r['fails_valid']}f {r['invalid']}inv ${r['cost']:.2f}",
              flush=True)  # fmt: skip

    with ThreadPoolExecutor(max_workers=1) as pool:  # authoring needs the environment slots
        list(pool.map(one, jobs))


def cmd_run(ledger: Ledger, n_specs: int, limit: int | None, first: int = 0,
            only: list[str] | None = None) -> None:  # fmt: skip
    specs = sample_specs(n_specs, SEED)
    _write(STUDY_DIR / "specs.json", [s.model_dump() for s in specs])
    chosen = list(enumerate(specs))[first:limit]
    wanted = {(o.split("-")[0], int(o.split("-")[1])) for o in only or []}
    solve_pool = ThreadPoolExecutor(max_workers=3)
    pending = []

    def pipeline(author: str, i: int, spec: TaskSpec) -> None:
        try:
            rec = build(author, i, spec, ledger)
            print(f"{author}-{i:02d}: built={rec['built']} valid={rec['valid']} "
                  f"repairs={rec['repairs']} author ${rec.get('author_cost', 0):.2f}", flush=True)  # fmt: skip
            if rec["valid"]:
                for solver in MODELS:
                    pending.append(solve_pool.submit(solve_task, author, i, solver, ledger))
        except Exception:  # noqa: BLE001 (one pipeline's crash must not stop the others)
            traceback.print_exc()
        write_results(ledger, n_specs)

    jobs = [(a, i, spec) for i, spec in chosen for a in MODELS if not wanted or (a, i) in wanted]
    with ThreadPoolExecutor(max_workers=max(len(jobs), 1)) as pool:
        for author, i, spec in jobs:
            pool.submit(pipeline, author, i, spec)
    for f in pending:
        f.result()
    solve_pool.shutdown()
    write_results(ledger, n_specs)
    print(f"study spend ${study_spent(ledger):.2f} of ${CAP_USD:.2f} cap")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gap")
    run = sub.add_parser("run")
    run.add_argument("--specs", type=int, default=8)
    run.add_argument("--limit", type=int, help="only the first N of the drawn specs")
    run.add_argument("--first", type=int, default=0, help="skip the first N drawn specs")
    run.add_argument("--only", nargs="*", help="author-index pairs, e.g. weak-03")
    sub.add_parser("summary")
    args = parser.parse_args()
    ledger = Ledger()
    if args.cmd == "gap":
        cmd_gap(ledger)
    elif args.cmd == "run":
        cmd_run(ledger, args.specs, args.limit, args.first, args.only)
    else:
        write_results(ledger, 8)
        from analysis.study import main as show

        show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
