"""Aggregation of the author x solver study (analysis/study.py)."""

from analysis.study import cell, markdown_table, raw_band, summarize, verdict


def solve(passes, fails_valid=0, invalid=0, cost=1.0):
    return {"passes": passes, "fails_valid": fails_valid, "invalid": invalid, "cost": cost}


def task(author, valid, **solves):
    return {"author": author, "valid": valid, "valid_first_try": valid, "built": True,
            "author_cost": 2.0, "solves": solves}  # fmt: skip


def test_band_boundaries():
    assert [raw_band(p) for p in range(6)] == ["too_hard"] + ["in_band"] * 3 + ["too_easy"] * 2


def test_invalid_failure_voids_the_verdict():
    assert verdict(solve(2, fails_valid=2, invalid=1)) == "invalid"
    assert verdict(solve(2, fails_valid=3)) == "in_band"


def test_cell_counts_only_valid_tasks_and_costs_everything():
    tasks = [
        task("weak", True, strong=solve(5), weak=solve(2, 3)),
        task("weak", True, strong=solve(0, 5), weak=solve(0, 5)),
        task("weak", False),
        task("strong", True, strong=solve(3, 2), weak=solve(1, 4)),
    ]
    c = cell(tasks, "weak", "strong")
    assert (c["attempted"], c["valid"]) == (3, 2)
    assert c["verdicts"] == {"in_band": 0, "too_easy": 1, "too_hard": 1, "invalid": 0}
    assert c["mean_pass_rate"] == 0.5
    assert c["pass_histogram"] == [1, 0, 0, 0, 0, 1]
    assert c["cost_per_in_band"] is None
    assert cell(tasks, "strong", "weak")["cost_per_in_band"] == 3.0  # (2 author + 1 solve) / 1


def test_summary_has_four_cells_and_a_table():
    summary = summarize([task("weak", True, strong=solve(4, 1), weak=solve(2, 3))])
    assert set(summary["cells"]) == {"weak->weak", "weak->strong", "strong->weak", "strong->strong"}
    assert summary["validity"]["weak"]["valid"] == 1
    assert markdown_table(summary).count("\n") == 5
