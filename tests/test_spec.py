from collections import Counter

from generator.spec import DOMAINS, LEVERS, VERIFIERS, TaskSpec, sample_specs


def test_specs_are_deterministic_per_seed():
    assert sample_specs(5, seed=7) == sample_specs(5, seed=7)
    assert sample_specs(5, seed=7) != sample_specs(5, seed=8)


def test_specs_use_valid_values_and_distinct_multi_picks():
    for spec in sample_specs(30, seed=1):
        assert spec.domain in DOMAINS
        assert spec.verifier in VERIFIERS
        assert len(set(spec.levers)) == 2 and all(lv in LEVERS for lv in spec.levers)
        assert len(set(spec.capabilities)) == 2


def test_inverse_frequency_spreads_coverage():
    specs = sample_specs(len(DOMAINS), seed=3)
    # With 1/(count+1) weighting, a batch the size of the axis covers most values.
    assert len({s.domain for s in specs}) >= len(DOMAINS) - 3


def test_history_steers_away_from_used_values():
    history = [s.model_copy(update={"domain": "debugging"}) for s in sample_specs(20, seed=4)]
    fresh = sample_specs(40, seed=5, history=history)
    counts = Counter(s.domain for s in fresh)
    assert counts["debugging"] <= min(counts[d] for d in DOMAINS if d != "debugging") + 1


def test_prompt_and_id():
    spec = sample_specs(1, seed=9)[0]
    text = spec.to_prompt()
    assert spec.domain in text and "Difficulty levers" in text
    assert len(spec.spec_id) == 12
    assert TaskSpec(**spec.model_dump()).spec_id == spec.spec_id


def test_construction_levers_exist_and_reach_the_blueprint_prompt():
    from generator import blueprint
    from generator.spec import LEVERS

    new = ("hidden_seed_instances", "multi_stage_dependency", "large_state_scale")
    assert all(k in LEVERS for k in new)
    assert "Difficulty by construction" in blueprint.BLUEPRINT_PROMPT
    spec = sample_specs(1, 3)[0].model_copy(update={"levers": list(new[:2])})
    assert "hidden_seed_instances" in spec.to_prompt()
