"""Novelty against published Terminal-Bench tasks (docs/plan.md, delta 11).

The reference corpus is every published TB set on the Harbor hub (`make
tb-reference` -> data/tb-reference/<set>/<task>/) plus examples/. Three uses:

- `concept_list()`: one line per reference task, put in the blueprint prompt
  so the author avoids those ideas in the first place.
- `nearest()` / `lexical_flags()`: word 13-gram overlap and TF-IDF cosine,
  which catch copied wording.
- `judge_same_task()`: a Sonnet judge over the top-k nearest references,
  which catches the same task reworded.

TF-IDF is implemented here (no embedding model: only Sonnet/Opus are allowed).
"""

import math
import re
import tomllib
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from generator.config import EXAMPLES_DIR, TB_REFERENCE_DIR

NGRAM = 13
_WORD = re.compile(r"[a-z0-9_]+")
_CANARY = re.compile(r"^\s*(<!--.*?-->|#.*canary.*)\s*$", re.IGNORECASE | re.MULTILINE)
_STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "by",
        "is",
        "are",
        "be",
        "as",
        "at",
        "it",
        "this",
        "that",
        "from",
        "your",
        "you",
        "can",
        "should",
        "must",
        "will",
        "not",
        "all",
        "any",
        "each",
        "into",
        "than",
        "then",
        "so",
        "if",
        "when",
        "which",
        "their",
        "there",
    ]
)


def tokens(text: str) -> list[str]:
    return _WORD.findall(_CANARY.sub("", text).lower())


def ngrams(words: list[str], n: int = NGRAM) -> set[tuple[str, ...]]:
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


@dataclass(frozen=True)
class RefTask:
    ref_id: str  # "<set>/<task>"
    instruction: str
    gist: str


def _gist(instruction: str, toml_path: Path) -> str:
    if toml_path.exists():
        desc = tomllib.loads(toml_path.read_text()).get("task", {}).get("description", "")
        if desc:
            return re.sub(r"^Evaluates (the|an agent's|the agent's) ability to ", "", desc)[:200]
    text = _CANARY.sub("", instruction).strip()
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return " ".join(first.split()[:30])


@cache
def load_reference(tb_dir: str = TB_REFERENCE_DIR, examples_dir: str = EXAMPLES_DIR) -> tuple:
    refs, seen = [], set()
    sources = [(p, f"{p.parent.name}/{p.name}") for p in sorted(Path(tb_dir).glob("*/*"))]
    sources += [(p, f"examples/{p.name}") for p in sorted(Path(examples_dir).glob("*"))]
    for task_dir, ref_id in sources:
        inst = task_dir / "instruction.md"
        if inst.exists():
            text = inst.read_text()
            key = " ".join(tokens(text))
            if key in seen:  # same task published in several sets (and the examples)
                continue
            seen.add(key)
            refs.append(RefTask(ref_id, text, _gist(text, task_dir / "task.toml")))
    if not refs:
        raise FileNotFoundError(f"no reference tasks under {tb_dir}; run `make tb-reference`")
    return tuple(refs)


class Index:
    """TF-IDF + 13-gram index over the reference instructions."""

    def __init__(self, refs: tuple[RefTask, ...]):
        self.refs = refs
        docs = [tokens(r.instruction) for r in refs]
        self._ngrams = [ngrams(d) for d in docs]
        df = Counter(w for d in docs for w in set(d) if w not in _STOP)
        self._idf = {w: math.log((1 + len(docs)) / (1 + c)) + 1 for w, c in df.items()}
        self._vecs = [self._vector(d) for d in docs]

    def _vector(self, words: list[str]) -> dict[str, float]:
        tf = Counter(w for w in words if w not in _STOP)
        vec = {w: c * self._idf.get(w, math.log(1 + len(self.refs)) + 1) for w, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {w: v / norm for w, v in vec.items()}

    def cosine_all(self, text: str) -> list[float]:
        q = self._vector(tokens(text))
        return [sum(q[w] * v.get(w, 0.0) for w in q) for v in self._vecs]

    def nearest(self, text: str, k: int = 3) -> list[tuple[RefTask, float]]:
        scores = self.cosine_all(text)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self.refs[i], scores[i]) for i in order]

    def shared_ngrams(self, text: str) -> list[tuple[RefTask, int]]:
        q = ngrams(tokens(text))
        hits = [(self.refs[i], len(q & g)) for i, g in enumerate(self._ngrams)]
        return [(r, n) for r, n in hits if n]


@cache
def default_index() -> Index:
    return Index(load_reference())


def own_tasks(candidates_dir: Path, exclude: str = "") -> tuple[RefTask, ...]:
    """Our earlier generated tasks, so the gate also rejects near-duplicates of our own work."""
    refs = []
    for inst in sorted(Path(candidates_dir).glob("*/task/instruction.md")):
        cand_id = inst.parent.parent.name
        if cand_id != exclude:
            text = inst.read_text()
            refs.append(RefTask(f"ours/{cand_id}", text, _gist(text, inst.parent / "task.toml")))
    return tuple(refs)


def gate_index(candidates_dir: Path, exclude: str = "") -> Index:
    """Published TB tasks + examples + our other candidates (rebuilt per call, ~0.2 s)."""
    return Index(load_reference() + own_tasks(candidates_dir, exclude))


def concept_list(index: Index | None = None) -> str:
    index = index or default_index()
    return "\n".join(f"- {r.ref_id}: {r.gist}" for r in index.refs)


# Calibrated on the de-duplicated TB corpus (calibrate(), 2026-10-12): the median
# nearest-neighbour cosine between distinct published tasks is 0.24 and p90 is 0.52,
# while every pair above ~0.75 is a genuine variant (polyglot-rust-c vs
# polyglot-c-py 0.83, two broken-pip repairs 0.75, a TB 4.0 rewording of a 2.1
# task 0.97). Below this, the Sonnet judge decides.
COSINE_REJECT = 0.70


def lexical_flags(text: str, index: Index | None = None) -> list[str]:
    """Reasons the text looks copied from a reference task (empty = clean)."""
    index = index or default_index()
    flags = [
        f"shares {n} word {NGRAM}-gram(s) with {r.ref_id}" for r, n in index.shared_ngrams(text)
    ]
    flags += [
        f"TF-IDF cosine {s:.2f} with {r.ref_id}"
        for r, s in index.nearest(text, k=3)
        if s >= COSINE_REJECT
    ]
    return flags


def calibrate(index: Index | None = None) -> dict[str, float]:
    """Nearest-neighbour cosine among distinct reference tasks (sets thresholds)."""
    index = index or default_index()
    nn = []
    for i, ref in enumerate(index.refs):
        scores = index.cosine_all(ref.instruction)
        scores[i] = -1.0
        nn.append(max(scores))
    nn.sort()

    def pick(q: float) -> float:
        return nn[min(int(q * len(nn)), len(nn) - 1)]

    return {"p50": pick(0.5), "p90": pick(0.9), "p99": pick(0.99), "max": nn[-1]}


JUDGE_SYSTEM = (
    "You review candidate benchmark tasks for novelty against published Terminal-Bench tasks. "
    "Be strict about the underlying problem, not the wording."
)

JUDGE_PROMPT = """Candidate task (draft):
<<<
{candidate}
>>>

Published reference tasks (nearest by text similarity):
{refs}

For each reference, decide whether the candidate is:
- "same": the same core problem, solvable by essentially the same approach;
- "variant": a reworded or lightly modified version of it (same central idea, artifact, or trick);
- "distinct": a different problem, even if the domain or tools overlap.

Return only JSON: {{"verdicts": [{{"ref_id": "...", "verdict": "same|variant|distinct",
"reason": "one sentence"}}]}}"""


def judge_same_task(candidate: str, index: Index | None = None, k: int = 3, chat=None) -> dict:
    """Sonnet verdicts against the k nearest references. Returns verdicts, cost, novel flag."""
    from analysis.llm import chat as default_chat
    from analysis.llm import extract_json

    chat = chat or default_chat
    index = index or default_index()
    near = index.nearest(candidate, k=k)
    refs = "\n\n".join(
        f"[{r.ref_id}] (cosine {s:.2f})\n{_CANARY.sub('', r.instruction).strip()[:1500]}"
        for r, s in near
    )
    reply = chat(
        JUDGE_PROMPT.format(candidate=candidate, refs=refs),
        system=JUDGE_SYSTEM,
        max_tokens=1500,
        temperature=0.0,
    )
    verdicts = extract_json(reply.text).get("verdicts", [])
    novel = all(v.get("verdict") == "distinct" for v in verdicts) and len(verdicts) == len(near)
    return {
        "novel": novel,
        "verdicts": verdicts,
        "nearest": [(r.ref_id, round(s, 3)) for r, s in near],
        "cost_usd": reply.cost_usd,
    }
