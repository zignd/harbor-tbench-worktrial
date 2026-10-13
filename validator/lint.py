"""Task lints beyond the structural validator (docs/plan.md, deltas 6 and 10).

Each finding is (level, message). "error" findings block a task; "warn"
findings are reported but don't block. The rules encode the task-quality
guidance from the research (Bercovich; Meta-Task; Terminal Wrench):
outcome-based tests, no answer leakage, terse instructions, an oracle that
investigates before it fixes.
"""

import re
import tomllib
from pathlib import Path

Finding = tuple[str, str]

INSTRUCTION_MAX_WORDS = 300
MAX_ENV_BYTES = 20_000_000
VENDOR_NAMES = {"node_modules", "vendor", "site-packages"}
FETCH_PINNED = "commit the lockfile and fetch pinned versions in the Dockerfile instead"
VENDORED_DIRS = {"node_modules", "vendor", "site-packages", ".git", "target"}
SUGGESTIVE = re.compile(
    r"#.*\b(BUG|FIXME|XXX|HACK|fix:|intentional(ly)?|the bug|bug here|hint)\b"
    r"|//.*\b(BUG|FIXME|fix:|intentional(ly)?|the bug|hint)\b",
    re.IGNORECASE,
)
ANSWER_FILENAME = re.compile(r"(expected|answer|solution|golden|correct|fixed)", re.IGNORECASE)
SOURCE_GREP = re.compile(
    r"(inspect\.getsource|\.read_text\(\)[^\n]*\bin\b|open\([^)]*\.(py|c|go|rs|js|sh)['\"]\))"
)
PACKAGE_CHECK = re.compile(
    r"(pip\s+(show|list|freeze)|importlib\.metadata|pkg_resources|dpkg\s+-l)"
)
INSPECT_CMD = re.compile(
    r"^\s*(cat|ls|grep|find|head|tail|less|diff|file|stat|sqlite3|git\s+(log|diff|show|status)"
    r"|python3?\s+(-m|-c)|wc|strings|objdump|readelf|ps|ss|netstat|curl)\b"
)
WRITE_CMD = re.compile(
    r"(sed\s+-i|\bpatch\b|\btee\b|cat\s*>|>\s*/|cp\s|mv\s|python3?\s+-\s*<<|apply|git\s+apply)"
)


# Interfaces the tests rely on must be stated: `harbor check` fails a package whose tests use
# a path, port or flag the instruction never mentions (it measured behavior_in_task_description
# failures on most luna-authored packages, each costing a ~6 minute repair round and a recalibration).
_TEST_PATH = re.compile(
    r"(?<![\w.\-/])(/(?:opt|usr/local|srv|app|var/lib|var/log|etc|home|root)/[\w.\-/]*[\w.\-])"
)
_TEST_PORT = re.compile(
    r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d{4,5})\b|\bport\W{1,4}(\d{4,5})\b", re.IGNORECASE
)
_TEST_FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z0-9]*(?:-[a-z0-9]+)*)")
PATH_SKIP = ("/tests", "/logs", "/tmp", "/proc", "/dev")


def unstated_interfaces(
    instruction: str, tests: str, env_text: str, env_names: set[str]
) -> list[str]:
    """Paths, ports and flags that tests/test_outputs.py uses but neither instruction.md nor the
    environment (file names, contents, Dockerfile) mentions, so the solver cannot know them."""
    known = instruction + "\n" + env_text
    out = []
    for m in sorted(set(_TEST_PATH.findall(tests))):
        if m.startswith(PATH_SKIP) or m in known or Path(m).name in env_names:
            continue
        if any(m.startswith(k.rstrip("/") + "/") for k in re.findall(r"/[\w.\-/]*[\w\-/]", instruction)):
            continue  # inside a directory the instruction names
        out.append(f"path {m}")
    for groups in sorted(set(_TEST_PORT.findall(tests))):
        port = next(g for g in groups if g)
        if port not in known:
            out.append(f"port {port}")
    for flag in sorted(set(_TEST_FLAG.findall(tests))):
        if flag not in known:
            out.append(f"flag {flag}")
    return out


def _read(path: Path) -> str:
    return path.read_text(errors="replace") if path.exists() else ""


def lint_task(task_dir: Path, canary_line: str) -> list[Finding]:
    task_dir = Path(task_dir)
    findings: list[Finding] = []
    instruction = _read(task_dir / "instruction.md")
    dockerfile = _read(task_dir / "environment" / "Dockerfile")
    solve = _read(task_dir / "solution" / "solve.sh")
    tests = _read(task_dir / "tests" / "test_outputs.py")

    # Canary placement.
    guid = canary_line.split("GUID")[-1].strip()
    if guid in instruction or "canary" in instruction.lower():
        findings.append(("error", "instruction.md contains the canary"))
    for name, text in [("solve.sh", solve), ("Dockerfile", dockerfile), ("test_outputs.py", tests)]:
        if guid not in text:
            findings.append(("error", f"{name} is missing the canary GUID"))

    # task.toml rules the README insists on.
    try:
        cfg = tomllib.loads(_read(task_dir / "task.toml"))
    except tomllib.TOMLDecodeError as e:
        return [*findings, ("error", f"task.toml does not parse: {e}")]
    if cfg.get("environment", {}).get("docker_image"):
        findings.append(("error", "task.toml sets docker_image; tasks must build from Dockerfile"))
    if cfg.get("agent", {}).get("timeout_sec", 0) < 3600:
        findings.append(("error", "[agent].timeout_sec < 3600"))

    # Instruction style (Bercovich: short, outcome-only, no prompt-style scaffolding).
    words = len(instruction.split())
    if words > INSTRUCTION_MAX_WORDS:
        findings.append(("warn", f"instruction is {words} words (> {INSTRUCTION_MAX_WORDS})"))
    if re.search(r"^\s*#{1,6}\s", instruction, re.MULTILINE):
        findings.append(("warn", "instruction uses markdown headers"))
    if "**" in instruction or "IMPORTANT" in instruction or "MUST" in instruction:
        findings.append(("warn", "instruction uses bold/shouting emphasis"))

    # Dockerfile hygiene.
    for m in re.finditer(r"^\s*(COPY|ADD)\s+(.+)$", dockerfile, re.MULTILINE):
        parts = [p for p in m.group(2).split() if not p.startswith("--")]
        for src in parts[:-1]:
            if re.search(r"(^|/)(solution|tests)(/|$)", src):
                findings.append(("error", f"Dockerfile copies {src} into the image"))
            elif not (task_dir / "environment" / src.rstrip("/")).exists():
                findings.append(("error", f"Dockerfile COPY source missing: environment/{src}"))
    if "FROM python:3.13-slim-bookworm" not in dockerfile:
        findings.append(("warn", "Dockerfile base is not python:3.13-slim-bookworm"))

    # Vendored third-party code: `harbor check` reads the whole environment (one vendored
    # node_modules made a $0.13 check cost $2.24), and it bloats the repo.
    env = task_dir / "environment"
    for vendored in sorted(p for p in env.rglob("*") if p.is_dir() and p.name in VENDOR_NAMES):
        if not VENDOR_NAMES & set(vendored.relative_to(env).parts[:-1]):  # outermost only
            findings.append(
                (
                    "error",
                    f"vendored dependencies in {vendored.relative_to(task_dir)}: {FETCH_PINNED}",
                )
            )

    # Vendored dependencies bloat the build context and the repo; fetch pinned ones at build time.
    env_bytes = sum(f.stat().st_size for f in (task_dir / "environment").rglob("*") if f.is_file())
    if env_bytes > MAX_ENV_BYTES:
        size = f"environment/ is {env_bytes / 1e6:.0f} MB (limit {MAX_ENV_BYTES / 1e6:.0f} MB)"
        findings.append(("error", f"{size}: don't vendor dependencies; {FETCH_PINNED}"))

    # Environment leakage: answer-named files and comments that give away the fix.
    for path in sorted((task_dir / "environment").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        # Third-party code the author vendored (not wrote): its comments aren't hints.
        if VENDORED_DIRS & set(path.parts):
            continue
        rel = path.relative_to(task_dir)
        if ANSWER_FILENAME.search(path.name):
            findings.append(("error", f"answer-like file name in environment: {rel}"))
        if path.suffix in {".py", ".sh", ".c", ".go", ".rs", ".js", ".sql", ".cfg", ".conf", ""}:
            for lineno, line in enumerate(_read(path).splitlines(), 1):
                if SUGGESTIVE.search(line):
                    findings.append(("error", f"suggestive comment {rel}:{lineno}: {line.strip()}"))

    # Every interface the tests use must be stated (or discoverable in the environment).
    env_files = [p for p in env.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    env_text = dockerfile + "\n".join(_read(p) for p in env_files if p.stat().st_size < 400_000)
    missing = unstated_interfaces(instruction, tests, env_text, {p.name for p in env_files})
    if missing:
        findings.append(
            (
                "error",
                "tests use interfaces the instruction never states (add each to instruction.md as "
                "an observable requirement, or make the environment show it): "
                + "; ".join(missing[:8]),
            )
        )

    # Tests check outcomes, not implementation.
    if SOURCE_GREP.search(tests):
        findings.append(
            ("warn", "tests appear to read solver source code (check outcomes instead)")
        )
    if PACKAGE_CHECK.search(tests):
        findings.append(("error", "tests check installed packages instead of behavior"))
    if not re.search(r"def test_", tests):
        findings.append(("error", "test_outputs.py has no test functions"))

    # The oracle should investigate before it writes (Bercovich: no hidden knowledge).
    first_inspect = first_write = None
    for i, line in enumerate(solve.splitlines()):
        if line.strip().startswith("#") or not line.strip():
            continue
        if first_inspect is None and INSPECT_CMD.search(line):
            first_inspect = i
        if first_write is None and WRITE_CMD.search(line):
            first_write = i
    if first_write is not None and (first_inspect is None or first_inspect > first_write):
        findings.append(("warn", "solve.sh writes before inspecting anything"))

    return findings


def errors(findings: list[Finding]) -> list[str]:
    return [msg for level, msg in findings if level == "error"]
