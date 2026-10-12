# Work Trial: Task Generation Pipeline

## Context

Terminal-Bench 2 evaluates AI agents on coding tasks. An agent gets an instruction, works in a terminal, and a verifier decides whether it solved the problem. You've seen how this works from the take-home, which used the similar Terminal-Bench 1.

Now build the other side: **a pipeline that generates the tasks themselves.**

A generated task is only useful if it sits in the right difficulty band. Too easy and every model solves it. Too hard and none do. The sweet spot is a **learnable** task: when run 5 times with `terminus-2` using `claude-opus-4.8`, exactly 1 to 3 out of 5 runs pass all tests. Generate tasks with `claude-sonnet-4.6` and benchmark difficulty only against `claude-opus-4.8`. Use no other models for either. Your pipeline should produce tasks that consistently land in this range.

## What's Provided

- `generator/generate.py`: a task generator stub, currently incomplete.
- `validator/validate.py`: a structural validator that checks the task layout and that `task.toml` parses and validates against Harbor's schema.
- `examples/`: 6 reference tasks in the standard Harbor format. Study these carefully, though they likely aren't in the target difficulty band themselves.
- `harbor/`: the Harbor framework source. This is the harness that runs agents against tasks. Read it to understand how it works: the `task.toml` schema, the agents, the verifier. Install the framework itself with `pip install harbor`.
- `scripts/`: helper scripts for generation and validation.

This is a template, feel free to change any of it as you see fit, but try to maintain the general structure.

### Task Format

Each task directory contains:

```
task-name/
├── task.toml            # Task config: difficulty, timeouts, metadata
├── instruction.md       # The instruction the agent sees
├── environment/
│   ├── Dockerfile       # Container environment setup
│   └── [task files]     # Anything copied into the container
├── solution/
│   └── solve.sh         # Deterministic reference solution
└── tests/
    ├── test.sh          # Runs the checks, writes the reward
    └── test_outputs.py  # Pytest tests that verify the task was solved
```

`tests/test.sh` writes `1` (pass) or `0` (fail) to `/logs/verifier/reward.txt`. Your generated tasks must follow this format exactly.

### What Makes a Good Task

A well-crafted task has:

- A clear, unambiguous instruction that describes what needs to be fixed or built
- Tests that pass when the task is correctly solved. The oracle agent verifies this.
- Tests that fail on an unsolved container (if the tests pass without anyone doing anything, the task is broken). The nop agent verifies this.
- A working reference solution (`solution/solve.sh`) that makes all tests pass
- A Dockerfile that installs all necessary dependencies
- Appropriate difficulty. Not trivially solvable, not impossibly hard.
- Valid failure modes: a run fails because the model can't solve it, not because of a timeout or an unclear spec (see Caveats for details)

## Requirements

### Part 1: Generate Valid Tasks

Implement the generator so that generated tasks:

1. Pass the structural validator
2. Are functionally correct: the reference solution passes all tests (`harbor run -a oracle`), and an unsolved container fails (`harbor run -a nop`)

Verify by running the structural validator and by checking generated tasks against the examples.

### Part 2: Hit the Target Distribution

This is the core deliverable.

A task is learnable if, when run 5 times with `terminus-2` using `claude-opus-4.8`, exactly 1 to 3 runs pass all tests. Tasks where 0 runs pass are too hard. Tasks where 4-5 runs pass are too easy.

Build a pipeline that produces learnable tasks. Your system should:

- Generate a task
- Evaluate it (run it against the agent)
- Report the pass distribution
- Only output tasks that land in the 1-3 out of 5 range

### Part 3: Pipeline Metrics

Generate a batch of tasks (aim for 10+). Report:

- How many pass structural validation
- How many are functionally correct
- How many land in the 1-3/5 learnable range
- Total cost and time

### Stretch Goals

If you keep going:

A. Cost-efficient evaluation. Running 5 agent attempts per task adds up. Design a strategy that reduces total evaluation cost while still reliably identifying learnable tasks.

B. Difficulty tuning. Given a task that's too easy or too hard, can your pipeline adjust it to land in the target band?

C. Diversity analysis. Analyze your generated tasks for category coverage, difficulty spread, and instruction uniqueness. How would you ensure your pipeline doesn't keep generating the same kind of task?

D. Human-likeness. Compare your generated tasks side-by-side with the hand-crafted examples in `examples/`. How close are they on instruction clarity, test thoroughness, Dockerfile quality, and overall polish? Can your pipeline produce tasks indistinguishable from human-written ones?

## Caveats

- A failing run should mean the model failed, not the task. Not an ambiguous instruction, not a broken environment, not the agent running out of time. Timeouts especially don't count: give the agent a full hour by setting `timeout_sec = 3600.0` under `[agent]` in `task.toml` (the examples already do this). For every task you ship, you should understand why the model fails it.
- Tasks must be novel. Don't reuse or adapt any public task, including the examples here, and don't build the environment around public source, such as cloning an open-source repo for the agent to patch. The generator writes each problem, environment, and solution itself.
- Make tasks worth training on. Aim for tasks where a scaled-up version would plausibly improve a model trained on it with RL or SFT. Also understand what this kind of scaling might entail. Reward hacking is something you should keep in mind too here.
- Your API key has 500 dollars on it. Track spend and use catiously as agent runs can get expensive. You can cap max turns to 200 if you feel like it to prevent an agent from spiraling, but an agent running out of turns would not be a valid failure mode.

## Setup

### Prerequisites

- Docker (running)
- Python 3.12+
- `uv` (recommended) or `pip`

### Install Harbor

```bash
uv tool install harbor
```

Or with pip:

```bash
pip install harbor
```

Verify: `harbor --help`

### Install Generator Dependencies

```bash
pip install -r generator/requirements.txt
```

### Environment

You'll be given an inference API key. Harbor calls models through LiteLLM, which routes any `openrouter/...` model through `OPENROUTER_API_BASE` using `OPENROUTER_API_KEY`. Point both at the inference gateway:

```bash
export OPENROUTER_API_KEY="<your inference key>"
export OPENROUTER_API_BASE="https://api.aqinference.com/v1"
```

The generator reads the same two variables.

### Running the Generator

```bash
bash scripts/generate.sh "fix a broken Python script"
```

### Running the Validator

```bash
bash scripts/validate.sh output/fix-a-broken-python-script
```

### Evaluating a Task

```bash
harbor run -p output/<task> -a oracle    # reward 1 = the reference solution passes
harbor run -p output/<task> -a nop       # reward 0 = an unsolved container fails
harbor run -p output/<task> -a terminus-2 -m openrouter/anthropic/claude-opus-4.8 --n-attempts 5
```

## Evaluation Criteria

In order of importance:

1. Do your tasks hit the target distribution? What fraction of generated tasks are learnable (1-3 out of 5)? Do these have valid failure modes (reason why the agent failed and your task landed in the learnable band)?
2. Pipeline design. How did you decompose generation, validation, and evaluation?
3. How do you know your tasks are good? What's your validation and evaluation strategy?
4. Reliability and throughput. Can you generate calibrated tasks consistently?
5. Code quality. Clean, readable, well-structured.

Include:

- All source code
- `CHANGELOG.md` describing what you did, why, and any design tradeoffs
- Your git commit history (we read it)


---

## Running this implementation

Everything below was added for the work trial; the sections above are AfterQuery's spec. **Start with `docs/architecture.md`** (diagrams, decisions, Q&A). Design, decisions and measured results are in `docs/plan.md`, `docs/harbor-notes.md`, `CHANGELOG.md` and `reports/summary.md`.

### Setup

```bash
uv sync                      # Python 3.13 + pinned harbor==0.24.0 (see pyproject.toml)
cp .env.example .env         # then set OPENROUTER_API_KEY (an OpenRouter key)
make tb-reference            # download the 425 published Terminal-Bench tasks used by the novelty gate
make usage                   # live spend / remaining credit on the key
```

### Generate, gate and calibrate

```bash
make batch N=3 SEED=1 BUDGET=20             # blueprint -> authoring meta-task -> gates, N candidates
uv run --env-file .env python -m scripts.run_batch --n 8 --seed 3 --workers 4 --calibrate   # parallel builds; calibrate each task as soon as it passes the gates (resumable after a crash)
uv run --env-file .env python -m scripts.calibrate_candidates   # red-team + Opus calibration; ship learnable tasks to output/
uv run --env-file .env python -m analysis.report                # reports/summary.md (funnel, cost, distribution, diversity)
bash scripts/generate.sh "fix a memory bug in a C ring buffer"  # one gated task from a topic (template entry point)
```

Cheaper ways to exercise the code: `make dry-run` (fixtures, no model calls, real gates) and `DEV_MODE=1 make batch` (every model call goes to a cheap dev model; results stay in `output-dev/` and are never shipped or reported).

### Pipeline in one picture

```
spec (inverse-frequency over a 10-axis taxonomy)
  -> blueprint (Sonnet) -> rubric review + novelty gate (425 published TB tasks + our own)
  -> authoring meta-task (terminus-2 + Sonnet in a container; artifacts=/app/output)
  -> gates: structure, lint, leak scan -> oracle 3/3 + nop -> harbor check (16 criteria)
            -> novelty re-check -> red-team (hack elicitation)      [failures feed repair rounds]
  -> calibration: terminus-2 + Opus 4.8, exact curtailment of the 5-run band, every trial judged
  -> output/<task>/ (learnable only) + README with why the model fails it
```

### Evidence

- `runs/ledger.jsonl`: every stage of every candidate (cost, time, result, inputs hash).
- `runs/candidates/<id>/`: spec, blueprint, gate decisions, the authored task, calibration with per-trial judge labels.
- `output/`: shipped (learnable) tasks. `make test` / `make lint` / `make plan` for checks and checklist progress.
