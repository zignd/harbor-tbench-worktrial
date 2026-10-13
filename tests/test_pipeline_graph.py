"""The watch TUI's pipeline graph: node states and time estimates from ledger events."""

from datetime import UTC, datetime, timedelta

from scripts import pipeline_graph as pg

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
SECS = pg.node_seconds({})


def ev(stage, result=None, secs=0.0, ago_min=1.0):
    ts = (NOW - timedelta(minutes=ago_min)).isoformat()
    return {"stage": stage, "task": "c", "result": result or {}, "seconds": secs, "ts": ts,
            "cost_usd": 0.0, "mode": "official"}  # fmt: skip


def states(events, live=None, status="building"):
    got, repair, attempts = pg.node_states(events, live, status)
    return {s.key: s.state for s in got}, repair, attempts


def test_new_candidate_is_in_blueprint():
    s, repair, _ = states([])
    assert s["blueprint"] == "running" and not repair
    assert all(s[k] == "pending" for k in ("author", "static", "calibration", "verdict"))


def test_live_authoring_is_the_current_node():
    events = [ev("blueprint_gate", {"accepted": True})]
    s, _, attempts = states(events, live=12)
    assert (s["blueprint"], s["author"], s["static"]) == ("done", "running", "pending")
    assert attempts == 0


def test_passed_gates_move_on_to_the_parallel_pair():
    events = [ev("blueprint_gate"), ev("author", {"attempt": 1, "turns": 40}, 800),
              ev("gate_static", {"problems": []}, 5), ev("gate_functional", {"problems": []}, 50)]  # fmt: skip
    s, repair, _ = states(events)
    assert (s["functional"], s["quality"], s["novelty"]) == ("done", "running", "running")
    assert not repair


def test_failed_gate_means_repair_and_reestimates_from_authoring():
    events = [ev("blueprint_gate"), ev("author", {"attempt": 1}, 800),
              ev("gate_static", {"problems": ["lint: x"]}, 5)]  # fmt: skip
    got, repair, attempts = pg.node_states(events, None, "building")
    assert repair and attempts == 1
    assert {s.key: s.state for s in got}["static"] == "failed"
    eta = pg.estimate(got, SECS, repair, 0, 0)
    assert eta > SECS["author"] + SECS["calibration"]


def test_calibration_progress_and_verdict():
    base = [ev("blueprint_gate"), ev("author", {"attempt": 1}, 800),
            ev("gate_static", {"problems": []}), ev("gate_functional", {"problems": []}),
            ev("gate_quality", {"ok": True, "problems": []}),
            ev("gate_novelty", {"novel": True}), ev("gate_redteam", {"hackable": False})]  # fmt: skip
    s, _, _ = states(base + [ev("calibration_trial")])
    assert s["calibration"] == "running" and s["novelty"] == "done"
    done = base + [ev("calibration", {"passes": 4, "trials": 4, "verdict": "too_easy"})]
    s, _, _ = states(done, status="gated")
    assert s["calibration"] == "done" and s["verdict"] == "done"


def test_hackable_red_team_fails_the_node():
    events = [ev("author", {"attempt": 1}), ev("gate_novelty", {"novel": True}),
              ev("gate_redteam", {"hackable": True})]  # fmt: skip
    s, repair, _ = states(events)
    assert s["novelty"] == "failed" and repair


def test_estimate_counts_pending_work_and_shrinks_as_time_passes():
    got, repair, _ = pg.node_states([ev("blueprint_gate")], 5, "building")
    full = pg.estimate(got, SECS, repair, 0, 0)
    later = pg.estimate(got, SECS, repair, 0, 600)
    assert full > later > 0
    assert full >= SECS["author"] + SECS["static"] + SECS["functional"] + SECS["calibration"]


def test_candidate_eta_only_for_building_candidates():
    assert pg.candidate_eta([], None, "shipped", SECS, NOW) is None
    assert pg.candidate_eta([], None, "building", SECS, NOW) > 0


def test_render_marks_the_current_node():
    got, repair, attempts = pg.node_states([ev("blueprint_gate")], 7, "building")
    text = pg.render_graph(got, SECS, repair, attempts, 900.0, NOW).plain
    assert "you are here" in text and "estimate: ~15m left" in text
    assert "in parallel" in text
