"""Model labels: every result records which models produced it, and pairs never mix."""

import json

import pytest

from analysis import report
from analysis.ledger import Event, Ledger
from generator import config
from scripts import pipeline_graph as pg


def test_guard_accepts_a_configured_pair_but_not_dev_mode(monkeypatch):
    monkeypatch.setattr(config, "DEV_MODE", False)
    monkeypatch.setattr(config, "MODEL", "google/gemini-3.8-flash")
    monkeypatch.setattr(config, "EVAL_MODEL", "openrouter/google/gemini-3.8-flash")
    config.assert_official_models()  # no error: models are open
    monkeypatch.setattr(config, "DEV_MODE", True)
    with pytest.raises(RuntimeError):
        config.assert_official_models()


def test_events_carry_the_model_label_and_old_ones_are_legacy(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    ledger.append(Event("author", "official-x", {"attempt": 1}))
    path.write_text(
        path.read_text()
        + json.dumps(
            {
                "stage": "author",
                "task": "old",
                "result": {},
                "cost_usd": 0.0,
                "seconds": 1.0,
                "inputs_hash": "",
                "mode": "official",
                "ts": "t",
            }
        )
        + "\n"
    )
    new, old = ledger.events()
    assert new.models == config.MODEL_LABEL
    assert old.models == config.LEGACY_MODEL_LABEL


def test_report_only_counts_candidates_of_the_configured_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "CANDIDATES_DIR", tmp_path)
    for name, label in [("official-a", config.MODEL_LABEL), ("official-b", "other|pair"),
                        ("official-c", None)]:  # fmt: skip
        d = tmp_path / name
        d.mkdir()
        if label:
            (d / "models.json").write_text(json.dumps({"label": label}))
    got = {r["id"] for r in report.candidates()}
    expected = {"official-a"} | (
        {"official-c"} if config.MODEL_LABEL == config.LEGACY_MODEL_LABEL else set()
    )
    assert got == expected


def test_stage_medians_use_only_the_configured_pair(tmp_path):
    path = tmp_path / "ledger.jsonl"
    rows = [("a", 10.0)] * 3 + [("b", 500.0)] * 3
    with path.open("w") as f:
        for models, secs in rows:
            f.write(json.dumps({"stage": "author", "mode": "official", "seconds": secs,
                                "models": models}) + "\n")  # fmt: skip
    assert pg.stage_medians(path, models="a") == {"author": 10.0}
    assert pg.stage_medians(path, models="b") == {"author": 500.0}
