"""Difficulty review of a *built* package (instruction, environment, solution).

The blueprint review judges the plan; the authoring agent then builds it and can quietly
lose the difficulty the plan was approved for (31ca: an "opaque binary regression" became
two readable SQL sort-direction bugs, solved 5/5 in 4-5 turns). This runs the same
speedrun on what was actually built, before the red-team and Opus calibration, so a task
Opus would obviously solve goes back to repair instead of costing trials.
"""

from pathlib import Path

from analysis.llm import chat, extract_json
from generator.blueprint import MIN_DIFFICULTY

SKIP_DIRS = {"node_modules", "vendor", "site-packages", ".git", "target", "__pycache__"}
MAX_FILES = 120

PROMPT = """You review a finished Terminal-Bench task package for difficulty. A frontier agent (Claude
Opus class) must solve it in only 1-3 of 5 attempts. Measured on our own tasks: when the defects
are visible by reading the source, Opus solves them in 4-25 commands, 4/4 to 5/5 times.

What the blueprint promised as the source of difficulty:
{intended}

Instruction the solver sees:
<<<
{instruction}
>>>

Files the solver's environment contains (path, lines):
{listing}

Reference solution (never shown to the solver):
<<<
{solution}
>>>

Play a strong agent that has read only the instruction and listed the environment. Write the shortest
plausible command-by-command path to a passing solution and count the commands. If ~20 commands or
fewer would likely work, typically because the defect is in readable source, difficulty is at most 2.
Also say whether the promised source of difficulty actually exists in the environment.

Return only JSON: {{"speedrun": ["step", "..."], "speedrun_commands": n, "difficulty": 1-5,
"promised_difficulty_present": true|false, "reasons": "2-3 sentences",
"fixes": ["concrete changes that restore real difficulty without hiding requirements"]}}"""


def environment_listing(task_dir: Path) -> str:
    rows = []
    for path in sorted((Path(task_dir) / "environment").rglob("*")):
        if not path.is_file() or SKIP_DIRS & set(path.parts):
            continue
        try:
            lines = path.read_bytes().count(b"\n")
        except OSError:
            lines = 0
        rows.append(f"{path.relative_to(Path(task_dir) / 'environment')}  ({lines} lines)")
    extra = f"\n... {len(rows) - MAX_FILES} more files" if len(rows) > MAX_FILES else ""
    return "\n".join(rows[:MAX_FILES]) + extra


def review_package(task_dir: Path, intended: str, chat_fn=chat) -> dict:
    """Accept if the built package is not a ~20-command task. Returns the verdict and cost."""
    task_dir = Path(task_dir)
    solution = (task_dir / "solution" / "solve.sh").read_text()[:6000]
    reply = chat_fn(
        PROMPT.format(
            intended=intended,
            instruction=(task_dir / "instruction.md").read_text(),
            listing=environment_listing(task_dir),
            solution=solution,
        ),
        system="You are a strict Terminal-Bench task reviewer.",
        max_tokens=4000,
        temperature=0.0,
    )
    review = extract_json(reply.text)
    difficulty = float(review.get("difficulty", 0))
    commands = int(review.get("speedrun_commands") or 0)
    review["accepted"] = difficulty >= MIN_DIFFICULTY and not (0 < commands <= 12)
    review["cost_usd"] = reply.cost_usd
    return review


def feedback(review: dict, intended: str) -> str:
    fixes = "; ".join(review.get("fixes") or [])
    return (
        "difficulty: the built package is too easy for a frontier agent: "
        f"{review.get('reasons', '')} (speedrun ~{review.get('speedrun_commands')} commands). "
        f"The blueprint promised: {intended} "
        + (
            "That difficulty source is missing from the environment. "
            if not review.get("promised_difficulty_present", True)
            else ""
        )
        + f"Restore it without hiding any requirement the tests check. Suggested: {fixes}"
    )
