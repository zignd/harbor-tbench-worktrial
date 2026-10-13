import json

from analysis.ledger import Event, hash_dir
from analysis.package_evidence import approval_errors, package_hash
from analysis.report import approved_outputs, funnel


def test_shipping_metadata_does_not_change_task_hash(tmp_path):
    (tmp_path / "instruction.md").write_text("Fix the service.")
    h = package_hash(tmp_path)
    (tmp_path / "calibration.json").write_text("{}")
    (tmp_path / "README.md").write_text("Shipping note")
    assert package_hash(tmp_path) == h
    (tmp_path / "instruction.md").write_text("Different task")
    assert package_hash(tmp_path) != h


def test_approval_requires_exact_package_and_valid_evidence(tmp_path):
    (tmp_path / "instruction.md").write_text("Fix the service.")
    passed = {"outcome": "pass", "audit": {"honest": True}}
    failed = {
        "outcome": "fail",
        "failure": {"valid": True, "instruction_quote": "Fix the service."},
    }
    record = {
        "package_hash": package_hash(tmp_path),
        "models": "a|b",
        "trials": [passed] * 2 + [failed] * 3,
        "quality_blocking_failures": [],
    }
    assert approval_errors(tmp_path, record, "a|b") == []
    assert "model label mismatch" in approval_errors(tmp_path, record, "other")
    record["trials"] = [passed] * 2 + [failed]
    assert "five judged trials required" in approval_errors(tmp_path, record, "a|b")
    record["package_hash"] = "stale"
    assert "package hash mismatch" in approval_errors(tmp_path, record, "a|b")


def test_report_does_not_use_a_success_from_an_older_package(tmp_path):
    task = tmp_path / "task"
    task.mkdir()
    (task / "instruction.md").write_text("Old instruction")
    old = hash_dir(task)
    (task / "instruction.md").write_text("New instruction")
    row = {
        "id": "c",
        "dir": tmp_path,
        "gate": {"accepted": True},
        "status": "failed",
        "calibration": None,
    }
    events = [Event("gate_static", "c", {"problems": []}, inputs_hash=old)]
    assert funnel([row], events)["structurally_valid"] == 0


def test_report_requires_an_immutable_approval_not_a_directory(tmp_path):
    task = tmp_path / "task1"
    task.mkdir()
    (task / "task.toml").write_text("schema_version='1.1'")
    (task / "instruction.md").write_text("Fix it.")
    assert approved_outputs(tmp_path, "a|b") == []
    record = {
        "package_hash": package_hash(task),
        "models": "a|b",
        "quality_blocking_failures": [],
        "trials": [{"outcome": "pass", "audit": {"honest": True}}]
        + [{"outcome": "fail", "failure": {"valid": True, "instruction_quote": "Fix it."}}] * 4,
    }
    (task / "calibration.json").write_text(json.dumps(record))
    (task / "verification.json").write_text(
        json.dumps({"status": "passed", "package_hash": record["package_hash"]})
    )
    assert approved_outputs(tmp_path, "a|b") == [task]
    assert approved_outputs(tmp_path, "other") == []
    (task / "instruction.md").write_text("Changed package")
    assert approved_outputs(tmp_path, "a|b") == []
