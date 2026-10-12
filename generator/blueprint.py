"""Spec -> Blueprint (Sonnet), then a rubric review and the novelty gate.

A blueprint is the plan a task is built from (CLI-Universe, SkillSynth): the
user-facing instruction draft, an internal hint (the resolution path, never
shown to the solver), the environment to build, the requirements the tests
must check, the trap, and the verifier knob. Reviewing it before any container
work rejects weak or derivative ideas for cents.
"""

from pydantic import BaseModel, Field

from analysis.llm import chat, extract_json
from generator.spec import LEVERS, VERIFIERS, TaskSpec
from validator import novelty

SYSTEM = (
    "You design tasks for Terminal-Bench, a benchmark of hard, realistic command-line work. "
    "Your tasks are judged by whether a frontier coding agent fails them for genuine reasons."
)

BLUEPRINT_PROMPT = """Design ONE original Terminal-Bench task from the coordinates below.

## Coordinates (treat domain, verifier kind and difficulty levers as fixed; adapt the persona,
## language and centerpiece if needed so the scenario is coherent and realistic)
{spec}

## Difficulty target
The solver is a frontier model (Claude Opus class) working alone in a Linux container for up to an
hour with full root access. The task must be solved in only 1-3 out of 5 attempts: hard enough that
it often fails, possible enough that it sometimes succeeds. Anything an average undergraduate could do
in a few days is too easy. Difficulty must come from the problem itself, never from format fussiness,
hidden resource limits, ambiguity or tricks.

What makes strong agents fail for valid reasons:
- They verify shallowly: they check the provided sample and stop. Make correctness hinge on cases the
  sample doesn't show, and have the tests check behaviour on fresh inputs generated at verify time.
- They implement partially: they fix the obvious issue and miss the second one. Make the levers
  interact so a partial fix looks done.
- They don't explore: put the key facts in the environment (code, data, logs), not the instruction.
Every requirement the tests check must still be stated in the instruction. The solver must be able to
succeed from the instruction plus what it can discover in the container.

## Hard constraints
- The environment is built from a Dockerfile `FROM python:3.13-slim-bookworm`, with apt/pip packages
  pinned. It has 1 CPU and 2 GB RAM, no GPU, and the solver needs no internet.
- You (the task author) write every file: code, data, configs. Never clone or vendor a public
  repository or reuse a published task.
- Deterministic: tests may not depend on wall-clock time, unseeded randomness or the network.
- Verification is outcome-based (run the program or inspect state), never grepping source code.
- The reference solution must be a deterministic shell script that investigates before fixing.

## Must NOT resemble any of these published Terminal-Bench tasks (or variants of them)
{concepts}

## Output
Return only JSON with exactly these keys:
{{
  "slug": "kebab-case-name, 3-6 words",
  "title": "short title",
  "scenario": "2-4 sentences: the realistic situation and what the environment contains",
  "instruction_draft": "what the solver is told, in the requested style: outcome-only, no hints",
  "requirements": ["each concrete, testable requirement stated by the instruction"],
  "environment": ["what the Dockerfile and files must set up, including the planted problems"],
  "internal_hint": "the resolution path: root causes and how a skilled engineer finds and fixes them",
  "trap": "the specific way a naive or shallowly verified solution fails the hidden tests",
  "tests": ["what each test checks, including the verify-time generated inputs"],
  "verifier_knob": {{"name": "...", "value": "...", "effect": "how raising/lowering it changes difficulty"}},
  "expected_failure_modes": ["valid reasons a strong agent fails"],
  "predicted_pass_rate": 0.0,
  "difficulty": "medium or hard",
  "category": "one word or kebab-case",
  "tags": ["3-6 tags"]
}}
predicted_pass_rate is your honest estimate (0-1) of how often a frontier agent solves it."""


class Blueprint(BaseModel):
    slug: str
    title: str
    scenario: str
    instruction_draft: str
    requirements: list[str]
    environment: list[str]
    internal_hint: str
    trap: str
    tests: list[str]
    verifier_knob: dict
    expected_failure_modes: list[str]
    predicted_pass_rate: float = Field(ge=0, le=1)
    difficulty: str
    category: str
    tags: list[str]

    def to_markdown(self, spec: TaskSpec) -> str:
        """Blueprint as the meta-task author sees it."""

        def bullets(items: list[str]) -> str:
            return "\n".join(f"  - {x}" for x in items)

        knob = self.verifier_knob
        return "\n".join(
            [
                (
                    f"- Title: {self.title} (slug `{self.slug}`; difficulty {self.difficulty}; "
                    f"category {self.category}; tags {', '.join(self.tags)})"
                ),
                f"- Scenario: {self.scenario}",
                (
                    f"- Instruction draft (keep its style and brevity; tighten wording if needed): "
                    f"{self.instruction_draft}"
                ),
                f"- Requirements the instruction states and the tests check:\n{bullets(self.requirements)}",
                f"- Environment to build:\n{bullets(self.environment)}",
                f"- Internal hint (never reveal to the solver): {self.internal_hint}",
                f"- Trap: {self.trap}",
                f"- Tests:\n{bullets(self.tests)}",
                (
                    f"- Verifier: {spec.verifier} ({VERIFIERS[spec.verifier][0]}); knob "
                    f"{knob.get('name')} = {knob.get('value')}"
                ),
                "- Difficulty levers: " + "; ".join(f"{lv} ({LEVERS[lv]})" for lv in spec.levers),
                f"- Expected valid failure modes: {'; '.join(self.expected_failure_modes)}",
            ]
        )

    def novelty_text(self) -> str:
        return "\n".join([self.title, self.scenario, self.instruction_draft, *self.requirements])


REVIEW_PROMPT = """You review a proposed Terminal-Bench task blueprint before it is built.

{blueprint}

Score each criterion 1-5 and explain briefly:
- clarity: the instruction states an unambiguous end state; every tested requirement is stated.
- solvability: a skilled engineer can solve it in under an hour in the described container; the
  environment is buildable as described (pinned packages, no internet needed, 1 CPU / 2 GB).
- verifiability: the tests can check outcomes deterministically on verify-time inputs, and a wrong
  or hollow solution cannot pass.
- genuine_difficulty: a frontier agent would fail it often for real reasons (shallow verification,
  partial fixes, missed exploration), not because of format fussiness, hidden limits or ambiguity.
- realism: it reads like a real engineering problem someone would actually have.

Also list any way a failure could be *invalid* (ambiguity, test overreach, flaky environment).

Return only JSON: {{"scores": {{"clarity": n, "solvability": n, "verifiability": n,
"genuine_difficulty": n, "realism": n}}, "invalid_failure_risks": ["..."],
"verdict": "accept|reject", "reasons": "2-3 sentences", "fixes": ["concrete improvements"]}}
Accept only if every score is at least 3 and the average is at least 3.6."""


def make_blueprint(spec: TaskSpec, concepts: str | None = None) -> tuple[Blueprint, float]:
    concepts = concepts if concepts is not None else novelty.concept_list()
    reply = chat(
        BLUEPRINT_PROMPT.format(spec=spec.to_prompt(), concepts=concepts),
        system=SYSTEM,
        max_tokens=6000,
        temperature=0.9,
    )
    return Blueprint(**extract_json(reply.text)), reply.cost_usd


def review_blueprint(bp: Blueprint, spec: TaskSpec) -> tuple[dict, float]:
    reply = chat(
        REVIEW_PROMPT.format(blueprint=bp.to_markdown(spec)),
        system="You are a strict Terminal-Bench task reviewer.",
        max_tokens=2000,
        temperature=0.0,
    )
    review = extract_json(reply.text)
    scores = review.get("scores", {})
    values = [float(v) for v in scores.values()] or [0.0]
    # Enforce the rule ourselves rather than trusting the model's verdict.
    review["accepted"] = min(values) >= 3 and sum(values) / len(values) >= 3.6
    return review, reply.cost_usd


def gate_blueprint(bp: Blueprint, spec: TaskSpec) -> dict:
    """Rubric review + novelty (lexical + Sonnet judge). Returns a decision record."""
    review, review_cost = review_blueprint(bp, spec)
    text = bp.novelty_text()
    lexical = novelty.lexical_flags(text)
    judged = novelty.judge_same_task(text) if not lexical else None
    novel = not lexical and bool(judged and judged["novel"])
    return {
        "accepted": review["accepted"] and novel,
        "review": review,
        "novelty": {"lexical_flags": lexical, "judge": judged, "novel": novel},
        "cost_usd": review_cost + (judged["cost_usd"] if judged else 0.0),
    }
