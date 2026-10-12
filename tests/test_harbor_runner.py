import json
import shutil
from pathlib import Path

import pytest

from analysis.openrouter import Price
from evaluator import harbor_runner as hr

FIXTURES = Path(__file__).parent / "fixtures" / "harbor_jobs"


def _only(job: str) -> hr.TrialResult:
    trials = hr.parse_job(FIXTURES / job)
    assert len(trials) == 1
    return trials[0]


def test_oracle_trial_passes():
    t = _only("p0-oracle")
    assert t.agent == "oracle"
    assert t.reward == 1.0
    assert t.outcome == "pass"
    assert t.cost_usd is None and t.priced_cost({}) == 0.0


def test_nop_trial_fails():
    t = _only("p0-nop")
    assert t.reward == 0.0
    assert t.outcome == "fail"


def test_opus_trial_fields():
    t = _only("p0-opus-fixgit")
    assert t.agent == "terminus-2"
    assert t.model == "openrouter/anthropic/claude-opus-4.8"
    assert t.outcome == "pass"
    assert t.n_episodes == 11
    assert t.max_turns == 200
    assert t.n_cache_tokens == 38595
    assert t.cost_usd == pytest.approx(0.1173, abs=1e-3)
    assert t.priced_cost({}) == t.cost_usd  # Harbor's estimate wins when present
    assert t.trajectory_path.name == "trajectory.json"


def test_metatask_trial_has_artifacts():
    t = _only("p0-metatask-sonnet")
    assert t.outcome == "pass"
    assert (t.artifacts_dir / "app" / "output" / "task.toml").exists()


def _with_result(tmp_path: Path, job: str, **changes) -> hr.TrialResult:
    src = next(p for p in (FIXTURES / job).iterdir() if p.is_dir())
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    result = json.loads((dst / "result.json").read_text())
    for dotted, value in changes.items():
        node = result
        *parents, leaf = dotted.split("__")
        for key in parents:
            if node.get(key) is None:
                node[key] = {}
            node = node[key]
        node[leaf] = value
    (dst / "result.json").write_text(json.dumps(result))
    return hr.parse_trial(dst)


@pytest.mark.parametrize(
    ("exception", "outcome"),
    [
        ("ApiRateLimitError", "infra"),
        ("SandboxBuildFailedError", "infra"),
        ("RewardFileNotFoundError", "infra"),
        ("AgentTimeoutError", "invalid"),
        ("VerifierTimeoutError", "invalid"),
        ("ApiKeyRejectedError", "fatal"),
    ],
)
def test_exception_classification(tmp_path, exception, outcome):
    t = _with_result(
        tmp_path,
        "p0-nop",
        exception_info={"exception_type": exception, "exception_message": "x"},
    )
    assert t.outcome == outcome


def test_missing_reward_is_infra(tmp_path):
    t = _with_result(tmp_path, "p0-nop", verifier_result=None)
    assert t.outcome == "infra"


def test_turn_cap_failure_is_invalid(tmp_path):
    t = _with_result(
        tmp_path,
        "p0-opus-fixgit",
        verifier_result={"rewards": {"reward": 0.0}},
        agent_result__metadata={"n_episodes": 200},
    )
    assert t.outcome == "invalid"


def test_unpriced_model_uses_token_prices(tmp_path):
    t = _with_result(
        tmp_path,
        "p0-opus-fixgit",
        agent_result__cost_usd=None,
    )
    price = Price(prompt=5e-6, completion=25e-6, cache_read=0.5e-6)
    expected = price.cost(t.n_input_tokens, t.n_cache_tokens, t.n_output_tokens)
    assert t.priced_cost({"anthropic/claude-opus-4.8": price}) == pytest.approx(expected)
    # Same order of magnitude as Harbor's own estimate for this trial.
    assert 0.05 < expected < 0.2


def test_run_with_retries_reruns_infra(monkeypatch):
    nop = _only("p0-nop")
    infra = hr.TrialResult(**{**nop.__dict__, "exception": "ApiError"})
    calls = []

    def fake_run_job(task_dir, agent, name, attempts=1, **kwargs):
        calls.append((name, attempts))
        return [infra] if len(calls) == 1 else [nop]

    monkeypatch.setattr(hr, "run_job", fake_run_job)
    counted, excluded = hr.run_with_retries(Path("x"), "nop", "job", attempts=1)
    assert calls == [("job", 1), ("job-retry1", 1)]
    assert counted == [nop] and excluded == []


def test_run_with_retries_excludes_persistent_infra(monkeypatch):
    nop = _only("p0-nop")
    infra = hr.TrialResult(**{**nop.__dict__, "exception": "ApiError"})
    monkeypatch.setattr(hr, "run_job", lambda *a, **k: [infra])
    counted, excluded = hr.run_with_retries(Path("x"), "nop", "job", attempts=1)
    assert counted == [] and excluded == [infra]
