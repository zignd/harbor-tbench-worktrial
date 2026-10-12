"""
Task generator: produce one gated Harbor (Terminal-Bench 2) task from a topic string.

    bash scripts/generate.sh "fix a memory bug in a C ring buffer"

The topic becomes a hint on a sampled spec (generator/spec.py); the candidate
then goes through the full pipeline (generator/pipeline.py): blueprint and its
review + novelty gate, authoring as a Harbor meta-task with repair rounds, and
the static, functional, quality and novelty gates. On success the task is
copied to output_dir. Calibration against Opus is a separate stage
(scripts/run_batch.py); this entry point only guarantees a *valid* task.

The task layout (study examples/ and harbor/src/harbor/cli/template-task/):

    <task-name>/
    ├── task.toml            # [task] / [metadata] / [verifier] / [agent] / [environment]
    ├── instruction.md       # the prompt the agent sees (no canary)
    ├── environment/
    │   └── Dockerfile       # builds the task environment (no pre-built docker_image)
    ├── solution/
    │   └── solve.sh         # deterministic reference solution (the Oracle runs this)
    └── tests/
        ├── test.sh          # pipeline-owned verifier entry point (writes the reward)
        └── test_outputs.py  # pytest checks over the final container state

The reward contract: tests/test.sh writes `1` (pass) or `0` (fail) to
`/logs/verifier/reward.txt`. See harbor/src/harbor/verifier/verifier.py.
"""

import hashlib
import os
import shutil
import sys

from analysis.ledger import Ledger
from generator.config import OUTPUT_DIR
from generator.pipeline import Candidate, build_candidate
from generator.spec import sample_specs


def generate_task(topic: str, output_dir: str | None = None) -> dict:
    """Generate a gated Harbor task for the given topic.

    Args:
        topic: A short description of the task to generate
            (e.g. "fix a memory bug in a C ring buffer").
        output_dir: Where to write the generated task files.
            Defaults to output/<slugified-topic>.

    Returns:
        dict with {"task_dir": <path or None>, "status": <str>, "candidate": <id>}.
    """
    slug = topic.lower().replace(" ", "-").replace("/", "-")[:60]
    if output_dir is None:
        output_dir = os.path.join(OUTPUT_DIR, slug)

    seed = int(hashlib.sha256(topic.encode()).hexdigest()[:8], 16)
    spec = sample_specs(1, seed=seed)[0].model_copy(update={"topic": topic})
    cand = build_candidate(Candidate(spec), Ledger())
    if cand.status != "gated":
        return {"task_dir": None, "status": cand.status, "candidate": cand.cand_id}

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    shutil.copytree(cand.task_dir, output_dir)
    return {"task_dir": output_dir, "status": cand.status, "candidate": cand.cand_id}


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "fix a broken Python CLI"
    result = generate_task(topic)
    if result["task_dir"]:
        print(f"Generated task at: {result['task_dir']}")
    else:
        print(f"No task produced (status: {result['status']}, candidate {result['candidate']})")
        sys.exit(1)
