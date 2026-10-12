import pytest

from analysis import budget
from analysis.ledger import Event, Ledger, hash_dir
from analysis.openrouter import Price, Spend


def test_ledger_roundtrip_filters_and_cache(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(Event("oracle", "t1", {"reward": 1.0}, cost_usd=0.0, inputs_hash="h1"))
    ledger.append(Event("opus", "t1", {"reward": 0.0}, cost_usd=1.5, inputs_hash="h1"))
    ledger.append(Event("opus", "t2", {"reward": 1.0}, cost_usd=0.5, inputs_hash="h2", mode="dev"))

    assert [e.stage for e in ledger.events(task="t1")] == ["oracle", "opus"]
    assert ledger.total_cost() == pytest.approx(2.0)
    assert ledger.total_cost(mode="official") == pytest.approx(1.5)
    assert ledger.cached("opus", "h1").result == {"reward": 0.0}
    assert ledger.cached("opus", "h2") is None  # recorded in dev mode only
    assert ledger.cached("opus", "h2", mode="dev") is not None


def test_hash_dir_ignores_caches_and_tracks_content(tmp_path):
    (tmp_path / "a.txt").write_text("one")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"junk")
    h1 = hash_dir(tmp_path)
    (tmp_path / "__pycache__" / "y.pyc").write_bytes(b"more junk")
    assert hash_dir(tmp_path) == h1
    (tmp_path / "a.txt").write_text("two")
    assert hash_dir(tmp_path) != h1


def test_spend_takes_the_larger_counter():
    assert Spend(limit=500, used=2.95, remaining=496.88).spent == pytest.approx(3.12)
    assert Spend(limit=500, used=4.0, remaining=497.0).spent == pytest.approx(4.0)
    assert Spend(limit=None, used=1.0, remaining=None).spent == 1.0


def test_budget_check_limits():
    spend = Spend(limit=500, used=300, remaining=200)
    assert budget.check(10, spend, authorized_usd=380, reserve_usd=75) is spend
    with pytest.raises(budget.BudgetExceeded, match="authorization"):
        budget.check(90, spend, authorized_usd=380, reserve_usd=75)
    with pytest.raises(budget.BudgetExceeded, match="reserve"):
        budget.check(130, spend, authorized_usd=1000, reserve_usd=75)


def test_price_cost_splits_cached_tokens():
    p = Price(prompt=1e-6, completion=2e-6, cache_read=0.1e-6)
    assert p.cost(n_input=1000, n_cache=800, n_output=100) == pytest.approx(
        200 * 1e-6 + 800 * 0.1e-6 + 100 * 2e-6
    )
