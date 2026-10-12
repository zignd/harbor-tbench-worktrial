"""Control flow of generator.pipeline.build_candidate with every paid stage faked."""

import json
import shutil
from pathlib import Path

import pytest

from analysis.ledger import Ledger
from generator import pipeline
from generator.blueprint import Blueprint
from generator.spec import sample_specs

FIX = Path(__file__).parent / "fixtures"
TASK = FIX / "harbor_jobs/p0-metatask-sonnet/metatask-sonnet__XBQDvdF/artifacts/app/output"
BLUEPRINT = Blueprint(**json.loads((FIX / "blueprint_ledger.json").read_text()))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "CANDIDATES_DIR", tmp_path / "candidates")
    calls = {"author": [], "gates": 0}

    def fake_blueprint(cand, ledger):
        cand.blueprint = BLUEPRINT
        return True

    def fake_author(cand, ledger, attempt, feedback=None, previous=None):
        calls["author"].append({"attempt": attempt, "feedback": feedback, "previous": previous})
        if cand.task_dir.exists():
            shutil.rmtree(cand.task_dir)
        shutil.copytree(TASK, cand.task_dir)
        return True

    monkeypatch.setattr(pipeline, "stage_blueprint", fake_blueprint)
    monkeypatch.setattr(pipeline, "stage_author", fake_author)
    return calls, Ledger(tmp_path / "ledger.jsonl")


def test_first_attempt_passes(env, monkeypatch):
    calls, ledger = env
    monkeypatch.setattr(pipeline, "stage_gates", lambda c, l, a: [])
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=3)[0]), ledger)
    assert cand.status == "gated"
    assert [c["attempt"] for c in calls["author"]] == [1]
    assert json.loads((cand.dir / "status.json").read_text())["status"] == "gated"


def test_repair_gets_feedback_and_previous_package(env, monkeypatch):
    calls, ledger = env
    results = iter([["oracle passed 1/3"], []])
    monkeypatch.setattr(pipeline, "stage_gates", lambda c, l, a: next(results))
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=4)[0]), ledger)
    assert cand.status == "gated"
    second = calls["author"][1]
    assert second["feedback"] == ["oracle passed 1/3"]
    assert second["previous"].name == "failed_a1" and (second["previous"] / "task.toml").exists()


def test_repairs_then_one_regeneration_then_failed(env, monkeypatch):
    calls, ledger = env
    monkeypatch.setattr(pipeline, "stage_gates", lambda c, l, a: ["still broken"])
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=5)[0]), ledger)
    assert cand.status == "failed"
    # (1 build + MAX_REPAIRS repairs) x (original + one regeneration)
    assert len(calls["author"]) == 2 * (1 + pipeline.MAX_REPAIRS)
    fresh = [c for c in calls["author"] if c["previous"] is None]
    assert len(fresh) == 2  # the regeneration starts from the blueprint, not the failed package


def test_rejected_blueprint_stops_early(env, monkeypatch):
    calls, ledger = env

    def reject(cand, ledger):
        cand.status = "rejected"
        return False

    monkeypatch.setattr(pipeline, "stage_blueprint", reject)
    cand = pipeline.build_candidate(pipeline.Candidate(sample_specs(1, seed=6)[0]), ledger)
    assert cand.status == "rejected" and calls["author"] == []
