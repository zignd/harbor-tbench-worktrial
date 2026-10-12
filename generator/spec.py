"""Task specs: the sampled design coordinates a blueprint is written from.

Axes follow CLI-Universe (domain, skill type, capability, engineering pillar)
and Tmax (persona, language, fixture kind, verifier kind), plus named
difficulty levers aimed at strong agents' documented failure modes (shallow
self-verification, partial implementation) and Meta-Task's writing styles
(restricted to terse-compatible ones). See docs/plan.md, deltas 3-5.

Sampling is inverse-frequency (SkillSynth): each value is drawn with weight
1 / (count + 1), where count is how often it has already been used, so
coverage spreads out over a batch instead of piling onto common cells.
"""

import hashlib
import json
import random
from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel

DOMAINS = [
    "software engineering",
    "debugging",
    "system administration",
    "file formats and recovery",
    "security",
    "data processing",
    "data querying (SQL)",
    "scientific computing",
    "build and packaging",
    "networking and services",
    "performance optimization",
    "text and log processing",
]
SKILL_TYPES = [
    "algorithmic",
    "data processing",
    "systems",
    "configuration",
    "shell scripting",
    "mathematical",
    "deployment",
    "cryptography",
]
CAPABILITIES = [
    "exploration",
    "decomposition",
    "error recovery",
    "specification adherence",
    "working memory",
    "long-horizon planning",
    "constraint satisfaction",
    "modality translation",
    "reverse engineering",
    "mathematical derivation",
    "adversarial reasoning",
]
PILLARS = [
    "new feature creation",
    "debugging",
    "systems programming",
    "devops",
    "feature iteration",
    "large-scale refactoring",
]
PERSONAS = [
    "on-call SRE paged at 3am",
    "data engineer inheriting a pipeline",
    "security engineer auditing a service",
    "research scientist reproducing a result",
    "backend developer chasing a production bug",
    "platform engineer migrating infrastructure",
    "analyst whose numbers stopped adding up",
    "release engineer fixing a broken build",
    "database administrator after an incident",
    "embedded/systems developer on a tight budget",
    "open-source maintainer triaging a regression",
    "finance-ops engineer reconciling records",
]
LANGUAGES = ["python", "bash", "c", "go", "rust", "sql", "javascript", "any"]
LANGUAGE_WEIGHTS = [5, 3, 2, 1, 1, 2, 1, 2]
FIXTURES = [
    "data files",
    "sqlite database",
    "compiled binary built in the Dockerfile",
    "small in-house codebase",
    "running services in one container",
    "git repository with history",
    "logs and metrics",
]
VERIFIERS = {
    # kind: (description, knob that tunes difficulty)
    "fuzz_equivalence": (
        (
            "tests generate fresh inputs at verify time and compare against a reference "
            "computation inside the tests"
        ),
        "number and variety of generated inputs",
    ),
    "metric_threshold": (
        "a stated, measurable threshold (speed, size, accuracy) checked on hidden inputs",
        "the threshold value",
    ),
    "adversarial_corpus": (
        "a hidden corpus of malicious and benign inputs; reject all bad, keep all good",
        "corpus size and coverage of tricky cases",
    ),
    "service_protocol": (
        "a service the solver fixes or builds answers real protocol requests correctly",
        "number of request scenarios",
    ),
    "state_check": (
        "the final system state (files, db rows, config) matches the required end state",
        "number of independent state properties checked",
    ),
}
LEVERS = {
    "misleading_symptom": "the obvious symptom points at the wrong component",
    "two_interacting_causes": "two bugs/causes that interact; fixing one hides the other",
    "hidden_invariant": "a rule the solver must discover by exploring data or code",
    "shallow_check_trap": "a naive fix passes the provided samples but fails hidden cases",
    "cross_component_consistency": "state must stay consistent across several components",
    "edge_case_inputs": "correctness hinges on edge cases the samples don't show",
    "performance_threshold": "a working but slow solution fails a stated performance bar",
    "no_repro_given": "no reproduction is provided; the solver must find a failing case",
}
STYLES = {
    "minimal": "one to three plain sentences stating the goal",
    "casual": "an informal request from a colleague, a few sentences",
    "terminal_dump": "starts with a short pasted error/output, then the ask",
    "short_narrative": "two short paragraphs of workplace context with the requirement woven in",
}


class TaskSpec(BaseModel):
    domain: str
    skill_type: str
    capabilities: list[str]
    pillar: str
    persona: str
    language: str
    fixture: str
    verifier: str
    levers: list[str]
    style: str

    @property
    def spec_id(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:12]

    def to_prompt(self) -> str:
        verifier_desc, knob = VERIFIERS[self.verifier]
        lines = [
            f"- Domain: {self.domain}",
            f"- Load-bearing skill: {self.skill_type}",
            f"- Capabilities the task should demand: {', '.join(self.capabilities)}",
            f"- Engineering pillar: {self.pillar}",
            f"- Requester persona: {self.persona}",
            f"- Main language: {self.language}",
            f"- Environment centerpiece: {self.fixture}",
            f"- Verifier kind: {self.verifier}: {verifier_desc} (difficulty knob: {knob})",
            "- Difficulty levers: "
            + "; ".join(f"{name} ({LEVERS[name]})" for name in self.levers),
            f"- Instruction style: {self.style}: {STYLES[self.style]}",
        ]
        return "\n".join(lines)


def _pick(rng: random.Random, values: list[str], counts: Counter, k: int = 1,
          base: list[int] | None = None) -> list[str]:
    """Draw k distinct values with weight base / (count + 1)."""
    pool = list(values)
    weights = [(base[i] if base else 1) / (counts[v] + 1) for i, v in enumerate(values)]
    chosen = []
    for _ in range(k):
        v = rng.choices(pool, weights=weights)[0]
        i = pool.index(v)
        chosen.append(v)
        pool.pop(i)
        weights.pop(i)
    return chosen


def sample_specs(n: int, seed: int, history: Iterable[TaskSpec] = ()) -> list[TaskSpec]:
    """Sample n specs, steering each axis away from values already used in history."""
    rng = random.Random(seed)
    counts: dict[str, Counter] = {axis: Counter() for axis in TaskSpec.model_fields}
    for spec in history:
        for axis, value in spec.model_dump().items():
            counts[axis].update(value if isinstance(value, list) else [value])
    specs = []
    for _ in range(n):
        spec = TaskSpec(
            domain=_pick(rng, DOMAINS, counts["domain"])[0],
            skill_type=_pick(rng, SKILL_TYPES, counts["skill_type"])[0],
            capabilities=_pick(rng, CAPABILITIES, counts["capabilities"], k=2),
            pillar=_pick(rng, PILLARS, counts["pillar"])[0],
            persona=_pick(rng, PERSONAS, counts["persona"])[0],
            language=_pick(rng, LANGUAGES, counts["language"], base=LANGUAGE_WEIGHTS)[0],
            fixture=_pick(rng, FIXTURES, counts["fixture"])[0],
            verifier=_pick(rng, list(VERIFIERS), counts["verifier"])[0],
            levers=_pick(rng, list(LEVERS), counts["levers"], k=2),
            style=_pick(rng, list(STYLES), counts["style"])[0],
        )
        for axis, value in spec.model_dump().items():
            counts[axis].update(value if isinstance(value, list) else [value])
        specs.append(spec)
    return specs


def dumps(specs: list[TaskSpec]) -> str:
    return json.dumps([s.model_dump() for s in specs], indent=1)
