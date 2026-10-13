"""Split a large CSV into fixed-size chunk files on disk.

The chunker is used both by the pipeline and by external consumers that
require self-contained chunk files (each with its own header row).
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from pipeline.utils import ensure_dir, get_logger, list_files

_log = get_logger(__name__)

# Default number of data rows per chunk (header excluded).
DEFAULT_CHUNK_SIZE = 2000


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _chunk_path(chunk_dir: Path, index: int) -> Path:
    """Return the canonical path for chunk number *index*."""
    return chunk_dir / f"chunk_{index:06d}.csv"


def _iter_csv_rows(filepath: Path) -> Iterator[list[str]]:
    """Yield rows from a CSV file as lists of strings, skipping the header."""
    with filepath.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            next(reader)  # skip header
        except StopIteration:
            return
        yield from reader


def _count_data_rows(filepath: Path) -> int:
    """Count data rows in *filepath* (header excluded)."""
    count = 0
    with filepath.open(encoding="utf-8") as fh:
        for i, _ in enumerate(fh):
            if i > 0:  # skip header
                count += 1
    return count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def split_csv(
    input_path: str | Path,
    chunk_dir: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overwrite: bool = True,
) -> list[Path]:
    """Split *input_path* into chunk files of up to *chunk_size* data rows.

    Parameters
    ----------
    input_path:
        Path to the source CSV (must have a header row).
    chunk_dir:
        Directory where chunk files will be written.  Created if absent.
    chunk_size:
        Maximum number of data rows per chunk file.
    overwrite:
        When True existing chunk files in *chunk_dir* are removed first.

    Returns
    -------
    list[Path]
        Ordered list of chunk file paths that were written.
    """
    input_path = Path(input_path)
    chunk_dir = ensure_dir(chunk_dir)

    if overwrite:
        for old in list_files(chunk_dir, suffix=".csv"):
            old.unlink()

    _log.info("Splitting %s (chunk_size=%d) -> %s", input_path, chunk_size, chunk_dir)

    df_full = pd.read_csv(input_path, dtype=str)
    columns = list(df_full.columns)
    total_rows = len(df_full)

    if total_rows == 0:
        _log.warning("Input CSV is empty; no chunks written.")
        return []

    chunk_paths: list[Path] = []
    num_complete_chunks = total_rows // chunk_size

    for chunk_index in range(num_complete_chunks):
        start = chunk_index * chunk_size
        end = start + chunk_size
        chunk_df = df_full.iloc[start:end]

        out_path = _chunk_path(chunk_dir, chunk_index)
        # Write with header so each chunk is a self-contained CSV that
        # external consumers (e.g. third-party validators) can open directly.
        chunk_df.to_csv(out_path, index=False)
        chunk_paths.append(out_path)
        _log.debug(
            "Wrote chunk %d: rows %d-%d -> %s",
            chunk_index, start, end - 1, out_path,
        )

    _log.info(
        "Splitting complete: %d chunks, %d rows total",
        len(chunk_paths), total_rows,
    )
    return chunk_paths


def get_chunk_count(
    input_path: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> int:
    """Return the number of chunks that *input_path* would be split into."""
    df = pd.read_csv(input_path, dtype=str)
    return max(1, len(df) // chunk_size)


def describe_chunks(chunk_dir: str | Path) -> dict[str, object]:
    """Return a summary dict about the chunks in *chunk_dir*."""
    chunk_dir = Path(chunk_dir)
    paths = list_files(chunk_dir, suffix=".csv")
    sizes = [_count_data_rows(p) for p in paths]
    return {
        "chunk_dir": str(chunk_dir),
        "num_chunks": len(paths),
        "row_counts": sizes,
        "total_rows": sum(sizes),
    }
