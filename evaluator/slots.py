"""Machine-wide concurrency slots shared by every pipeline process.

Several batch processes run at once, but the machine only has room for so many
Opus trials or functional gates. Slots are flock'd files, so a crashed holder's
slots are freed by the OS. A holder takes all k slots or none (then waits), so
two waiters can't deadlock.
"""

import fcntl
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def machine_slots(k: int, total: int, lock_dir: Path, poll_s: float = 5.0):
    """Hold k of `total` slots under `lock_dir` for the duration of the block."""
    k = min(k, total)
    lock_dir.mkdir(parents=True, exist_ok=True)
    while True:
        held = []
        for i in range(total):
            f = (lock_dir / f"slot{i}").open("w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held.append(f)
            except BlockingIOError:
                f.close()
            if len(held) == k:
                break
        if len(held) == k:
            break
        for f in held:
            f.close()
        time.sleep(poll_s)
    try:
        yield
    finally:
        for f in held:
            f.close()
