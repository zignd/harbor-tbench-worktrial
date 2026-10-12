from collections import Counter
from pathlib import Path

import pytest

from analysis import diversity
from generator.spec import DOMAINS, sample_specs

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_balance_bounds():
    assert diversity.balance(Counter({"a": 5}), 4) == pytest.approx(0.25)
    assert diversity.balance(Counter({"a": 1, "b": 1, "c": 1, "d": 1}), 4) == pytest.approx(1.0)


def test_coverage_counts_every_axis():
    cov = diversity.coverage(sample_specs(12, seed=2))
    assert set(cov) == set(diversity.AXES)
    assert cov["domain"]["of"] == len(DOMAINS) and cov["domain"]["covered"] >= 8
    assert 0 < cov["domain"]["balance"] <= 1


def test_vendi_identical_vs_distinct():
    same = ["fix the backup script so every table is saved"] * 4
    assert diversity.vendi(same) == pytest.approx(1.0, abs=1e-6)
    texts = [(d / "instruction.md").read_text() for d in sorted(EXAMPLES.iterdir()) if d.is_dir()]
    v = diversity.vendi(texts)
    assert 4.0 < v <= len(texts) + 1e-6  # six unrelated examples are mostly distinct


def test_uniqueness_reports_pairwise_stats():
    texts = [(d / "instruction.md").read_text() for d in sorted(EXAMPLES.iterdir()) if d.is_dir()]
    stats = diversity.uniqueness(texts)
    assert 0 <= stats["mean_pairwise_cosine"] <= stats["max_pairwise_cosine"] < 0.7
