from itertools import product

import pytest

from evaluator.calibrate import (
    HACKED_PASS,
    INVALID_FAIL,
    LEGIT_PASS,
    VALID_FAIL,
    decide,
    next_wave_size,
)


def full_verdict(seq: tuple[str, ...]) -> str:
    passes = seq.count(LEGIT_PASS)
    if passes == 0:
        return "too_hard"
    if passes >= 4:
        return "too_easy"
    return "learnable"


@pytest.mark.parametrize("seq", list(product([LEGIT_PASS, VALID_FAIL], repeat=5)))
def test_curtailment_matches_the_full_five_run_verdict(seq):
    """Exhaustive over all 32 pass/fail sequences: stopping early never changes the verdict."""
    for k in range(1, 6):
        verdict = decide(list(seq[:k]))
        if verdict is not None:
            assert verdict == full_verdict(seq), (seq, k)
            break
    else:
        pytest.fail(f"no verdict after 5 runs for {seq}")


def test_curtailment_saves_trials_on_average():
    stops = []
    for seq in product([LEGIT_PASS, VALID_FAIL], repeat=5):
        stops.append(next(k for k in range(1, 6) if decide(list(seq[:k]))))
    assert sum(stops) / len(stops) < 4.5  # uniform p=0.5 over sequences


def test_invalid_or_hacked_stops_immediately():
    assert decide([LEGIT_PASS, INVALID_FAIL]) == "invalid"
    assert decide([HACKED_PASS]) == "invalid"


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        ([], 3),  # earliest verdict: learnable after 1 pass + 2 fails
        ([LEGIT_PASS], 2),
        ([LEGIT_PASS, VALID_FAIL], 1),
        ([VALID_FAIL, VALID_FAIL], 1),  # one pass would make it learnable
        ([LEGIT_PASS, LEGIT_PASS, LEGIT_PASS], 1),  # the next pass decides "too easy"
    ],
)
def test_waves_never_overshoot_the_earliest_verdict(outcomes, expected):
    assert next_wave_size(outcomes, concurrency=3) == expected


def test_wave_respects_concurrency():
    assert next_wave_size([], concurrency=1) == 1


def test_exact_curtailment_is_lossless_and_aggressive_rule_is_not():
    from analysis.curtailment import simulate, table

    for p in (0.1, 0.35, 0.65):
        assert simulate(p)["recall"] == 1.0  # exact curtailment never misses a learnable task
    rows = {r["p"]: r for r in table()}
    assert rows[0.2]["aggressive_recall"] < 1.0  # 0/3 early reject loses some learnable tasks
    assert rows[0.2]["aggressive_trials"] < rows[0.2]["expected_trials"]


def test_unfinished_trials_resume_only_a_run_without_a_verdict(tmp_path):
    from analysis.ledger import Event, Ledger
    from evaluator.calibrate import unfinished_trials

    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append(Event("calibration_trial", "t", {"outcome": "fail"}, cost_usd=0.3))
    ledger.append(Event("calibration", "t", {"verdict": "too_hard"}))
    assert unfinished_trials(ledger, "t") == []  # finished runs are never reused
    ledger.append(Event("calibration_trial", "t", {"outcome": "pass"}, cost_usd=0.25))
    ledger.append(Event("calibration_trial", "t", {"outcome": "pass"}, cost_usd=0.2))
    got = unfinished_trials(ledger, "t")
    assert [t["outcome"] for t in got] == ["pass", "pass"]
    assert sum(t["_ledger_cost"] for t in got) == 0.45


def test_opus_slots_cap_concurrent_trials_across_holders(tmp_path):
    import threading
    import time

    from evaluator.calibrate import opus_slots

    running, peak, lock = [0], [0], threading.Lock()

    def wave(k):
        with opus_slots(k, total=3, lock_dir=tmp_path, poll_s=0.01):
            with lock:
                running[0] += k
                peak[0] = max(peak[0], running[0])
            time.sleep(0.05)
            with lock:
                running[0] -= k

    threads = [threading.Thread(target=wave, args=(k,)) for k in (2, 2, 1, 3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert not any(t.is_alive() for t in threads)  # all-or-nothing: no deadlock
    assert peak[0] <= 3


def test_eager_waves_run_every_remaining_trial_at_once():
    assert next_wave_size([], concurrency=5, eager=True) == 5
    assert next_wave_size(["pass", "fail"], concurrency=5, eager=True) == 3
    assert next_wave_size([], concurrency=3, eager=True) == 3  # still capped by concurrency
