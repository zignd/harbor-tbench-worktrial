"""Batch claims: a candidate being built elsewhere is skipped; a dead builder's claim is resumed."""

import os
import subprocess
import sys

from scripts.run_batch import _alive


def test_alive_tells_live_and_dead_builders_apart():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    assert _alive(os.getpid())
    assert not _alive(proc.pid)  # exited: its claim can be taken over
    assert not _alive(None)
