"""Diversity and novelty analysis of generated tasks (stretch goal C).

- Coverage and balance per taxonomy axis: balance = exp(H) / N (Tmax), the
  "effective number of categories" divided by how many exist; 1.0 is perfectly
  uniform, 1/N is everything in one bucket.
- Instruction uniqueness among our own tasks: pairwise TF-IDF cosine (max and
  mean) and the Vendi score (exp of the entropy of the similarity kernel's
  eigenvalues): the effective number of distinct instructions.
- Novelty against published Terminal-Bench tasks: nearest reference and cosine
  per task (validator/novelty.py).

No embedding model is used: only Sonnet 4.6 / Opus 4.8 are allowed.
"""

import math
from collections import Counter
from collections.abc import Iterable

from generator.spec import (
    CAPABILITIES,
    DOMAINS,
    FIXTURES,
    LANGUAGES,
    LEVERS,
    PILLARS,
    SKILL_TYPES,
    STYLES,
    VERIFIERS,
    TaskSpec,
)
from validator.novelty import Index, RefTask, default_index

AXES = {
    "domain": DOMAINS,
    "skill_type": SKILL_TYPES,
    "capabilities": CAPABILITIES,
    "pillar": PILLARS,
    "language": LANGUAGES,
    "fixture": FIXTURES,
    "verifier": list(VERIFIERS),
    "levers": list(LEVERS),
    "style": list(STYLES),
}


def balance(counts: Counter, n_buckets: int) -> float:
    total = sum(counts.values())
    if total == 0 or n_buckets == 0:
        return 0.0
    h = -sum((c / total) * math.log(c / total) for c in counts.values() if c)
    return math.exp(h) / n_buckets


def coverage(specs: Iterable[TaskSpec]) -> dict[str, dict]:
    specs = list(specs)
    out = {}
    for axis, values in AXES.items():
        counts = Counter()
        for spec in specs:
            v = getattr(spec, axis)
            counts.update(v if isinstance(v, list) else [v])
        out[axis] = {
            "covered": len(counts),
            "of": len(values),
            "balance": round(balance(counts, len(values)), 3),
            "counts": dict(counts.most_common()),
        }
    return out


def _cosine_matrix(texts: list[str]) -> list[list[float]]:
    index = Index(tuple(RefTask(str(i), t, "") for i, t in enumerate(texts)))
    return [index.cosine_all(t) for t in texts]


def _eigvals_symmetric(m: list[list[float]], sweeps: int = 60) -> list[float]:
    """Jacobi eigenvalues of a small symmetric matrix (avoids a numpy dependency)."""
    n = len(m)
    a = [row[:] for row in m]
    for _ in range(sweeps):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < 1e-12:
            break
        for p in range(n):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-12:
                    continue
                theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
    return [a[i][i] for i in range(n)]


def vendi(texts: list[str]) -> float:
    """Vendi score: effective number of distinct texts (1 = all identical, n = all distinct)."""
    n = len(texts)
    if n == 0:
        return 0.0
    k = _cosine_matrix(texts)
    eig = [max(e / n, 0.0) for e in _eigvals_symmetric(k)]
    return math.exp(-sum(e * math.log(e) for e in eig if e > 1e-12))


def uniqueness(texts: list[str]) -> dict:
    if len(texts) < 2:
        return {"max_pairwise_cosine": 0.0, "mean_pairwise_cosine": 0.0, "vendi": float(len(texts))}
    m = _cosine_matrix(texts)
    pairs = [m[i][j] for i in range(len(texts)) for j in range(i + 1, len(texts))]
    return {
        "max_pairwise_cosine": round(max(pairs), 3),
        "mean_pairwise_cosine": round(sum(pairs) / len(pairs), 3),
        "vendi": round(vendi(texts), 2),
    }


def novelty_report(named_texts: dict[str, str], index: Index | None = None) -> list[dict]:
    index = index or default_index()
    rows = []
    for name, text in named_texts.items():
        ref, score = index.nearest(text, k=1)[0]
        rows.append({"task": name, "nearest_reference": ref.ref_id, "cosine": round(score, 3)})
    return rows
