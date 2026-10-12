"""Answer-leak scan of a task's built image (docs/plan.md, delta 3.7 item 2).

Anything in the image is visible to the solver; `tests/` and `solution/` only
arrive later (tests at verify time, solution only for the oracle). So the image
must not contain answer-bearing tokens from them. We build the image, pull
distinctive tokens out of tests/ and solution/, and search the container
filesystem (outside system directories) plus `docker history` for each.

Tokens that the instruction itself states, or that the environment files
legitimately contain (paths, function names, input data), are not leaks.
"""

import re
import subprocess
from pathlib import Path

HEX = re.compile(r"\b[0-9a-f]{16,}\b")
LONG_NUMBER = re.compile(r"(?<![\w.])-?\d{6,}(?:\.\d+)?(?![\w.])|(?<![\w.])-?\d+\.\d{4,}(?![\w.])")
QUOTED = re.compile(r"""(["'])((?:(?!\1).){12,120})\1""")
# Pruned from the search: OS and interpreter trees the task doesn't write answers into,
# and package-manager download caches (pip's http cache matched test tokens by chance).
SYSTEM_DIRS = (
    "/proc /sys /dev /usr /lib /lib64 /bin /sbin /etc /var/lib /var/cache /boot /run /tmp"
    " /root/.cache /root/.npm /root/.cargo/registry /root/go/pkg/mod"
)
# Shell snippet: candidate files (task-created areas, < 5 MB) for grep.
_FIND_FILES = (
    "find / -xdev \\( "
    + " -o ".join(f"-path {d}" for d in SYSTEM_DIRS.split())
    + " \\) -prune -o -type f -size -5M -print 2>/dev/null"
)


# A Rust image's file-name search ran 19 min unpruned and its container outlived the CLI
# timeout. Searches are pruned and time-boxed inside the container, so it always exits.
SCAN_TIMEOUT_S = 300
_FIND_NAMED = (
    f"timeout {SCAN_TIMEOUT_S} find / -xdev \\( "
    + " -o ".join(f"-path {d}" for d in SYSTEM_DIRS.split())
    + " \\) -prune -o \\( -name solve.sh -o -name test_outputs.py \\) -print 2>/dev/null"
)


def distinctive_tokens(task_dir: Path) -> dict[str, str]:
    """Answer-like literals from tests/ and solution/ -> kind ("answer" or "string").

    "answer" tokens (long hex, long or high-precision numbers) are what expected
    outputs look like; finding one in the image is a leak. Quoted strings are
    weaker evidence (they may be input data the tests regenerate) and are only
    reported. Tokens the instruction states, and path-like tokens, are skipped.
    """
    task_dir = Path(task_dir)
    sources = [task_dir / "tests" / "test_outputs.py", task_dir / "solution" / "solve.sh"]
    text = "\n".join(p.read_text(errors="replace") for p in sources if p.exists())
    stated = (task_dir / "instruction.md").read_text(errors="replace")
    tokens = {t: "answer" for t in HEX.findall(text) + LONG_NUMBER.findall(text)}
    for m in QUOTED.finditer(text):
        s = m.group(2)
        if not re.search(r"\s", s) and "/" not in s and "." not in s[-5:]:
            tokens.setdefault(s, "string")
    return {
        t: kind
        for t, kind in tokens.items()
        if t not in stated and "canary" not in t.lower() and len(t) >= 6
    }


def _docker(*args: str, timeout: int = 900) -> subprocess.CompletedProcess:
    # errors="replace": images contain binary files, and grep can match inside them.
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def scan(task_dir: Path, tag: str) -> dict:
    """Build the image and look for test/solution tokens in it.

    Returns {built, leaks (blocking), notes (non-blocking), tokens_checked}.
    """
    task_dir = Path(task_dir)
    build = _docker("build", "--progress=plain", "-t", tag, str(task_dir / "environment"))
    if build.returncode != 0:
        # Keep the failing step's own output (plain progress), not just BuildKit's summary.
        lines = [ln for ln in build.stderr.splitlines() if ln.strip()]
        error = "\n".join(lines[-60:])[-4000:]
        return {"built": False, "error": error, "leaks": [], "tokens_checked": 0}
    try:
        kinds = distinctive_tokens(task_dir)
        tokens = sorted(kinds)
        leaks: list[str] = []
        notes: list[str] = []
        history = _docker("history", "--no-trunc", "--format", "{{.CreatedBy}}", tag).stdout
        for tok in tokens:
            if tok in history:
                (leaks if kinds[tok] == "answer" else notes).append(
                    f"docker history contains {tok!r}"
                )
        listing = _docker(
            "run",
            "--rm",
            "--network=none",
            tag,
            "sh",
            "-c",
            "ls -d /solution /tests /app/solution /app/tests 2>/dev/null; "
            + _FIND_NAMED,
        ).stdout.split()
        leaks += [f"image contains {p}" for p in listing]
        if tokens:
            # The token list goes in on stdin, so no token appears on a command line.
            found = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network=none",
                    "-i",
                    tag,
                    "sh",
                    "-c",
                    (
                        "cat > /.leak-tokens && "
                        + f"timeout {SCAN_TIMEOUT_S} "
                        + _FIND_FILES
                        + " | grep -v '^/.leak-tokens$' | xargs -r grep -lF -f /.leak-tokens"
                        + " 2>/dev/null | head -20"
                    ),
                ],
                input="\n".join(tokens),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=600,
            )
            for path in found.stdout.split():
                hit = _docker("run", "--rm", "--network=none", tag, "cat", path).stdout
                answer = any(kinds[tok] == "answer" and tok in hit for tok in tokens)
                (leaks if answer else notes).append(f"token found in image file {path}")
        return {"built": True, "leaks": leaks, "notes": notes, "tokens_checked": len(tokens)}
    finally:
        _docker("rmi", "-f", tag)
