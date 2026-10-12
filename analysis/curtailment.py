"""Cost-efficient evaluation analysis (stretch goal A).

Exact curtailment (evaluator.calibrate.decide) stops the 5-run band test as
soon as the verdict is certain: lossless. This module quantifies its savings
for any true pass rate p, and compares it with an *aggressive* rule that also
rejects after 0 passes in the first 3 runs: cheaper, but it wrongly rejects
learnable tasks that would have passed run 4 or 5.
"""

from itertools import product

from evaluator.calibrate import LEGIT_PASS, VALID_FAIL, decide


def _decide_aggressive(outcomes: list[str]) -> str | None:
    if len(outcomes) >= 3 and LEGIT_PASS not in outcomes[:3]:
        return "too_hard"
    return decide(outcomes)


def simulate(p: float, rule=decide, n: int = 5) -> dict:
    """Exact expectation over all 2^n pass/fail sequences for true pass rate p."""
    expected_trials = 0.0
    p_learnable_true = 0.0
    p_learnable_found = 0.0
    for seq in product([LEGIT_PASS, VALID_FAIL], repeat=n):
        prob = 1.0
        for s in seq:
            prob *= p if s == LEGIT_PASS else 1 - p
        stop = next((k for k in range(1, n + 1) if rule(list(seq[:k]))), n)
        verdict = rule(list(seq[:stop]))
        expected_trials += prob * stop
        truly = 1 <= seq.count(LEGIT_PASS) <= 3
        p_learnable_true += prob * truly
        p_learnable_found += prob * (truly and verdict == "learnable")
    return {
        "p": p,
        "expected_trials": round(expected_trials, 3),
        "saved_pct": round(100 * (1 - expected_trials / n), 1),
        "p_in_band": round(p_learnable_true, 3),
        "recall": round(p_learnable_found / p_learnable_true, 3) if p_learnable_true else 1.0,
    }


def table(ps=(0.05, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9)) -> list[dict]:
    rows = []
    for p in ps:
        exact = simulate(p)
        aggressive = simulate(p, rule=_decide_aggressive)
        rows.append(
            {
                **exact,
                "aggressive_trials": aggressive["expected_trials"],
                "aggressive_saved_pct": aggressive["saved_pct"],
                "aggressive_recall": aggressive["recall"],
            }
        )
    return rows
