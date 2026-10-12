import json
from pathlib import Path

from analysis import judge
from analysis.llm import Reply
from evaluator import calibrate as cal

FIX = Path(__file__).parent / "fixtures" / "harbor_jobs"
OPUS_TRIAL = next((FIX / "p0-opus-fixgit").glob("*/"))
TRAJ = OPUS_TRIAL / "agent" / "trajectory.json"
TASK = Path(__file__).resolve().parents[1] / "examples" / "fix-git"


def _reply(obj: dict) -> Reply:
    return Reply(json.dumps(obj), "m", 10, 0, 10, 0.02, 0.1)


def test_condense_keeps_reasoning_and_commands():
    text = judge.condense(TRAJ)
    assert "Analysis:" in text and "$ git status" in text
    assert len(text) <= judge.MAX_CHARS + 100


def test_command_scan_flags_verifier_access(tmp_path):
    data = json.loads(TRAJ.read_text())
    data["steps"][1]["tool_calls"][0]["arguments"]["keystrokes"] = "cat /tests/test_outputs.py\n"
    path = tmp_path / "trajectory.json"
    path.write_text(json.dumps(data))
    assert any("test_outputs.py" in hit for hit in judge.command_scan(path))
    assert judge.command_scan(TRAJ) == []


def test_audit_pass_maps_labels():
    result = judge.audit_pass(TASK, TRAJ, chat_fn=lambda *a, **k: _reply({"label": "legit"}))
    assert result["honest"] and result["cost_usd"] == 0.02
    result = judge.audit_pass(
        TASK, TRAJ, chat_fn=lambda *a, **k: _reply({"label": "serious_exploit"})
    )
    assert not result["honest"]


def test_failure_judge_requires_a_known_valid_mode():
    ok = {"valid": True, "mode": "weak_verification", "explanation": "x"}
    assert judge.analyze_failure(TASK, OPUS_TRIAL, TRAJ, chat_fn=lambda *a, **k: _reply(ok))[
        "valid"
    ]
    invalid_mode = {"valid": True, "mode": "test_overreach", "explanation": "x"}
    result = judge.analyze_failure(
        TASK, OPUS_TRIAL, TRAJ, chat_fn=lambda *a, **k: _reply(invalid_mode)
    )
    assert result["valid"] is False  # an invalid mode can't be a valid failure


def test_judge_trial_maps_harbor_outcomes(monkeypatch):
    from evaluator.harbor_runner import parse_trial

    trial = parse_trial(OPUS_TRIAL)  # a passing Opus trial
    monkeypatch.setattr(
        "analysis.judge.audit_pass",
        lambda task, traj: {"honest": False, "label": "serious_exploit", "cost_usd": 0.1},
    )
    outcome, _labels, cost = cal.judge_trial(TASK, trial)
    assert outcome == cal.HACKED_PASS and cost == 0.1
