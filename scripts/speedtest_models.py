"""Speed test: which model gets through authoring and the free gates fastest?

Each model authors the SAME accepted blueprints (copied from existing candidates) through the real
authoring meta-task with a turn cap and a wall-clock cap, then the package goes through the static
gate (structure, lint, leak scan) and oracle 3/3 + nop. One repair round is allowed if time remains.
Measures time to a valid package, turns and cost. Results: runs/speedtest/results.json and the
write-up docs/model-speedtest.md (built by this script). Exploratory: nothing here ships.

    uv run --env-file .env python -m scripts.speedtest_models
"""

import json
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from analysis import budget
from analysis.ledger import Event, Ledger
from evaluator.harbor_runner import run_with_retries
from evaluator.slots import machine_slots
from generator.author import collect_package, make_task_toml, render_metatask
from generator.blueprint import Blueprint
from generator.config import (
    GATE_CONCURRENCY,
    JOBS_DIR,
    METATASK_SUMMARIZE_THRESHOLD,
    RUNS_DIR,
)
from generator.pipeline import gate_functional, gate_static
from generator.spec import TaskSpec

MODELS = [
    "google/gemini-3.8-flash",  # baseline (the model used so far)
    "google/gemini-3.7-flash",
    "xiaomi/mimo-v2.6-pro",
    "z-ai/glm-5.3-flash",
    "openai/gpt-5.6-luna",
]
BLUEPRINT_CANDIDATES = ["official-d993c25003e5", "official-db27baf4dd3c", "official-f821c68cb15f"]
MAX_TURNS = 60
AUTHOR_CAP_S = 1200  # wall clock for the first authoring round
REPAIR_CAP_S = 600
TOTAL_CAP_S = 2100  # no repair after this
OUT = Path(RUNS_DIR) / "speedtest"
REPORT = Path(RUNS_DIR).parent / "docs" / "model-speedtest.md"
_lock = threading.Lock()


def _author(model, key, bp, spec, toml, cap, attempt, previous=None, feedback=None):
    meta = Path(JOBS_DIR) / "metatasks" / f"speed-{key}-a{attempt}"
    render_metatask(bp.to_markdown(spec), bp.slug, meta, toml, previous=previous, feedback=feedback)
    conf = meta / "task.toml"
    conf.write_text(
        re.sub(r"timeout_sec = 7200\.0", f"timeout_sec = {float(cap)}", conf.read_text())
    )
    t0 = time.monotonic()
    counted, excluded = run_with_retries(
        meta, "terminus-2", f"speed-{key}-a{attempt}", model=f"openrouter/{model}", retries=0,
        agent_kwargs={"max_turns": MAX_TURNS, "proactive_summarization_threshold": METATASK_SUMMARIZE_THRESHOLD},
    )  # fmt: skip
    trials = counted + excluded
    cost = sum(t.priced_cost() for t in trials)
    trial = trials[0] if trials else None
    return trial, cost, time.monotonic() - t0


def run_one(model: str, cand: str, ledger: Ledger, results: list) -> None:
    key = f"{model.replace('/', '_')}-{cand[-6:]}"
    d = OUT / key
    d.mkdir(parents=True, exist_ok=True)
    src = Path(RUNS_DIR) / "candidates" / cand
    bp = Blueprint(**json.loads((src / "blueprint.json").read_text()))
    spec = TaskSpec(**json.loads((src / "spec.json").read_text()))
    toml = make_task_toml(bp.slug, bp.title, bp.difficulty, bp.category, bp.tags)
    row = {
        "model": model,
        "blueprint": bp.slug,
        "attempts": [],
        "valid_seconds": None,
        "cost_usd": 0.0,
    }
    start = time.monotonic()
    previous, feedback = None, None
    for attempt in range(2):
        cap = AUTHOR_CAP_S if attempt == 0 else REPAIR_CAP_S
        if attempt and time.monotonic() - start > TOTAL_CAP_S:
            break
        try:
            budget.check(1.5)
            trial, cost, secs = _author(
                model, key, bp, spec, toml, cap, attempt, previous, feedback
            )
        except Exception as e:  # noqa: BLE001 (record any harness failure as the test result)
            row["attempts"].append({"attempt": attempt, "error": str(e)[:200]})
            break
        a = {"attempt": attempt, "author_seconds": round(secs), "cost_usd": round(cost, 3),
             "turns": trial.n_episodes if trial else None,
             "outcome": trial.outcome if trial else "infra",
             "exception": (trial.exception or "") if trial else ""}  # fmt: skip
        row["cost_usd"] += cost
        problems = ["no package produced"]
        if trial:
            try:
                collect_package(trial.trial_dir, d / "task", toml)
                with machine_slots(1, GATE_CONCURRENCY, Path(JOBS_DIR) / ".gate-slots"):
                    g0 = time.monotonic()
                    problems, _, built = gate_static(d / "task", f"speed-{key}-a{attempt}".lower())
                    if built and not problems:
                        found, res = gate_functional(d / "task", f"speed-{key}-a{attempt}")
                        problems += found
                        a["oracle"], a["nop"] = res["oracle"], res["nop"]
                    a["gate_seconds"] = round(time.monotonic() - g0)
            except FileNotFoundError:
                problems = ["no package produced"]
        a["problems"] = [p[:160] for p in problems][:4]
        row["attempts"].append(a)
        if not problems:
            row["valid_seconds"] = round(time.monotonic() - start)
            break
        previous = d / "prev"
        shutil.rmtree(previous, ignore_errors=True)
        if (d / "task").exists():
            shutil.copytree(d / "task", previous)
        else:
            previous = None
        feedback = problems
    row["total_seconds"] = round(time.monotonic() - start)
    row["cost_usd"] = round(row["cost_usd"], 3)
    ledger.append(
        Event("speedtest", key, {k: v for k, v in row.items() if k != "attempts"}, mode="speedtest")
    )
    with _lock:
        results.append(row)
        (OUT / "results.json").write_text(json.dumps(results, indent=1))
    print(f"{model:26} {bp.slug[:30]:30} valid={row['valid_seconds']} total={row['total_seconds']}s ${row['cost_usd']}", flush=True)  # fmt: skip


def write_report(results: list) -> None:
    by_model: dict[str, list] = {}
    for r in results:
        by_model.setdefault(r["model"], []).append(r)
    lines = [
        "# Model speed test: authoring through the free gates",
        "",
        (
            "*Exploratory. Each model authored the same accepted blueprints with the real "
            "authoring meta-task (terminus-2, 60-turn cap, 20-minute wall clock for the first "
            "round, one repair round if time remained), then the package went through structure, "
            "lint, leak scan, oracle 3/3 and nop. Runs were parallel on one machine, so times "
            "include contention (equal for every model). Data: `runs/speedtest/results.json`.*"
        ),
        "",
        "| Model | Valid packages | Median time to valid | Mean turns (1st round) | Mean $ per blueprint |",
        "|---|---|---|---|---|",
    ]
    for m, rows in by_model.items():
        ok = [r for r in rows if r["valid_seconds"]]
        med = sorted(r["valid_seconds"] for r in ok)[len(ok) // 2] if ok else None
        turns = [
            r["attempts"][0].get("turns")
            for r in rows
            if r["attempts"] and r["attempts"][0].get("turns")
        ]
        lines.append(
            f"| `{m}` | {len(ok)}/{len(rows)} | {f'{med / 60:.1f} min' if med else 'n/a'} | "
            f"{(sum(turns) / len(turns)) if turns else 0:.0f} | ${sum(r['cost_usd'] for r in rows) / len(rows):.2f} |"
        )
    lines += [
        "",
        "## Per run",
        "",
        "| Model | Blueprint | Attempts | Valid after | Cost | First problems |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        first = next((p for a in r["attempts"] for p in a.get("problems", [])), "")
        lines.append(
            f"| `{r['model']}` | {r['blueprint'][:34]} | {len(r['attempts'])} | "
            f"{f'{r["valid_seconds"] / 60:.1f} min' if r['valid_seconds'] else 'never'} | ${r['cost_usd']:.2f} | {first[:70]} |"
        )
    REPORT.write_text("\n".join(lines) + "\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results: list = []
    ledger = Ledger()
    jobs = [(m, c) for c in BLUEPRINT_CANDIDATES for m in MODELS]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        for m, c in jobs:
            pool.submit(run_one, m, c, ledger, results)
    write_report(results)
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
