"""Re-run existing candidates' authored packages under the current model label.

    uv run --env-file .env python -m scripts.recalibrate [--only ID ...] [--workers 6]

A package authored earlier by the same author model (but calibrated by another model) is copied into a
new candidate `<id>-m` carrying the current MODEL_LABEL, with a synthetic `author` ledger event
(`reused_from`) so the pipeline resumes at its gates: static, oracle 3/3 + nop, then the quality check,
novelty, red-team and calibration with the current calibration model, then shipping. Only packages that
already passed oracle + nop are taken. Results never mix with the source's label.
"""

import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from analysis.ledger import Event, Ledger, hash_dir
from generator import pipeline
from generator.config import MODEL, MODEL_LABEL
from generator.spec import TaskSpec
from scripts.calibrate_candidates import calibrate_one

COPY = ("spec.json", "blueprint.json", "blueprint_gate.json")


def eligible(ledger: Ledger) -> list[Path]:
    """Earlier candidates by the same author model whose current package passed oracle + nop."""
    out = []
    for d in sorted(pipeline.CANDIDATES_DIR.glob("official-*")):
        models = d / "models.json"
        if d.name.endswith("-m") or not models.exists() or not (d / "task").is_dir():
            continue
        label = json.loads(models.read_text()).get("label", "")
        if label == MODEL_LABEL or not label.startswith(MODEL + "|"):
            continue
        if not all((d / f).exists() for f in COPY):
            continue
        h = hash_dir(d / "task")
        # the package's oracle/nop result was recorded under the source's own label
        clean = [
            e for e in ledger.events(stage="gate_functional", task=d.name)
            if e.inputs_hash == h and not e.result.get("problems")
        ]  # fmt: skip
        if clean:
            out.append(d)
    return out


def clone(src: Path, ledger: Ledger) -> pipeline.Candidate:
    spec = TaskSpec(**json.loads((src / "spec.json").read_text()))
    cand = pipeline.Candidate(spec, cand_id=f"{src.name}-m")
    cand.dir.mkdir(parents=True, exist_ok=True)
    for name in COPY:
        shutil.copy(src / name, cand.dir / name)
    if cand.task_dir.exists():
        shutil.rmtree(cand.task_dir)
    shutil.copytree(src / "task", cand.task_dir)
    cand.save("models.json", {"label": MODEL_LABEL, "generator": MODEL, "reused_from": src.name})
    ledger.append(
        Event("author", cand.cand_id, {"attempt": 1, "outcome": "pass", "repair": False,
                                       "turns": None, "reused_from": src.name},
              inputs_hash=hash_dir(cand.task_dir))
    )  # fmt: skip
    return cand


def run_one(src: Path, ledger: Ledger) -> None:
    cand = clone(src, ledger)
    cand.save("status.json", {"status": "building"})
    cand = pipeline.build_candidate(cand, ledger)
    if cand.status == "gated":
        calibrate_one(cand.dir, ledger)
    print(f"{cand.cand_id}  {cand.status}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="*", help="source candidate ids")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    ledger = Ledger()
    sources = [d for d in eligible(ledger) if not args.only or d.name in args.only]
    print(f"{len(sources)} packages to re-run under {MODEL_LABEL}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(lambda d: run_one(d, ledger), sources))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
