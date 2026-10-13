import shutil
import subprocess
from pathlib import Path

import pytest

from generator.config import CANARY_LINE
from validator import leak_scan
from validator.lint import errors, lint_task

FIXTURE_TASK = (
    Path(__file__).parent
    / "fixtures/harbor_jobs/p0-metatask-sonnet/metatask-sonnet__XBQDvdF/artifacts/app/output"
)


@pytest.fixture
def task(tmp_path) -> Path:
    """A copy of the Phase 0 Sonnet-authored task (known good), safe to mutate."""
    dst = tmp_path / "task"
    shutil.copytree(FIXTURE_TASK, dst)
    return dst


def test_good_task_has_no_lint_errors(task):
    assert errors(lint_task(task, CANARY_LINE)) == []


def test_canary_in_instruction_is_an_error(task):
    inst = task / "instruction.md"
    inst.write_text(f"<!-- {CANARY_LINE} -->\n" + inst.read_text())
    assert any("canary" in e for e in errors(lint_task(task, CANARY_LINE)))


def test_docker_image_and_short_timeout_are_errors(task):
    toml = task / "task.toml"
    text = toml.read_text().replace("timeout_sec = 3600.0", "timeout_sec = 600.0")
    toml.write_text(text.replace("[environment]\n", '[environment]\ndocker_image = "x/y:1"\n'))
    errs = errors(lint_task(task, CANARY_LINE))
    assert any("docker_image" in e for e in errs) and any("3600" in e for e in errs)


def test_copying_tests_into_image_is_an_error(task):
    (task / "environment" / "Dockerfile").write_text(
        (task / "environment" / "Dockerfile").read_text() + "\nCOPY tests/ /tests/\n"
    )
    assert any("copies tests" in e for e in errors(lint_task(task, CANARY_LINE)))


def test_suggestive_comment_and_answer_file_are_errors(task):
    importer = task / "environment" / "ledger" / "importer.py"
    importer.write_text(importer.read_text() + "\n# BUG: should use integer cents here\n")
    (task / "environment" / "expected_report.txt").write_text("MERCHANT_01 45.50\n")
    errs = errors(lint_task(task, CANARY_LINE))
    assert any("suggestive comment" in e for e in errs)
    assert any("answer-like file" in e for e in errs)


def test_vendored_dependencies_are_an_error_but_not_hint_comments(task):
    lib = task / "environment" / "app" / "node_modules" / "ajv-formats" / "formats.js"
    lib.parent.mkdir(parents=True)
    lib.write_text("// hint to the UI to hide input strings\n")
    errs = errors(lint_task(task, CANARY_LINE))
    assert not any("suggestive comment" in e for e in errs)
    assert sum("vendored dependencies" in e for e in errs) == 1


def test_oversized_environment_is_an_error(task, monkeypatch):
    from validator import lint

    monkeypatch.setattr(lint, "MAX_ENV_BYTES", 10)
    assert any("don't vendor" in e for e in errors(lint_task(task, CANARY_LINE)))


def test_package_check_in_tests_is_an_error(task):
    t = task / "tests" / "test_outputs.py"
    t.write_text(t.read_text() + "\n\ndef test_pkg():\n    import importlib.metadata\n")
    assert any("installed packages" in e for e in errors(lint_task(task, CANARY_LINE)))


def test_distinctive_tokens_skip_values_the_environment_states(task):
    t = task / "tests" / "test_outputs.py"
    t.write_text(t.read_text() + '\nEXPECTED_HASH = "9f2c4e1b7a5d3c8e0f1a2b3c"\n')
    tokens = leak_scan.distinctive_tokens(task)
    assert "9f2c4e1b7a5d3c8e0f1a2b3c" in tokens
    assert "/app/ledger" not in tokens  # stated by the environment, not a leak


def _docker_ok() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, check=False).returncode == 0
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _docker_ok(), reason="needs Docker")
def test_leak_scan_finds_a_planted_answer(tmp_path):
    task = tmp_path / "leaky"
    (task / "environment").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "instruction.md").write_text("Compute the checksum of /app/data.bin.\n")
    (task / "environment" / "data.bin").write_text("payload\n")
    (task / "environment" / "Dockerfile").write_text(
        "FROM python:3.13-slim-bookworm\nCOPY data.bin /app/data.bin\n"
        "RUN echo 4c1f9e8d2b7a6c5e3f0d1a2b > /opt/.cache_value\n"
    )
    (task / "tests" / "test_outputs.py").write_text(
        'def test_sum():\n    assert open("/app/out").read().strip() == "4c1f9e8d2b7a6c5e3f0d1a2b"\n'
    )
    result = leak_scan.scan(task, "claude-leakscan-pytest")
    assert result["built"]
    assert any("/opt/.cache_value" in leak for leak in result["leaks"])
    assert any("docker history" in leak for leak in result["leaks"])


def test_generic_numbers_are_not_distinctive_tokens(tmp_path):
    from validator import leak_scan

    task = tmp_path / "t"
    (task / "tests").mkdir(parents=True)
    (task / "solution").mkdir()
    (task / "tests" / "test_outputs.py").write_text(
        "LIMIT = 1048576\nUS = 1000000\nNOW = 1700000000000\nANSWER = 482913657\n"
    )
    (task / "solution" / "solve.sh").write_text("echo hi")
    (task / "instruction.md").write_text("Fix it.")
    tokens = leak_scan.distinctive_tokens(task)
    assert set(tokens) == {"482913657"}


def test_unstated_interfaces_are_flagged():
    from validator.lint import unstated_interfaces

    tests = (
        'subprocess.run(["/usr/local/bin/audit", "--strict"])\n'
        'requests.get("http://127.0.0.1:8085/healthz")\n'
        'open("/opt/svc/out/report.json")\n'
    )
    instruction = "Run the audit tool at /usr/local/bin/audit and keep the report in /opt/svc/out."
    missing = unstated_interfaces(instruction, tests, "", set())
    assert "port 8085" in missing and "flag --strict" in missing
    assert not any(m.startswith("path") for m in missing)  # both paths are stated
    # discoverable in the environment is fine
    assert unstated_interfaces(instruction, tests, "usage: audit --strict  port 8085", set()) == []
