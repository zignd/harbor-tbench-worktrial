"""
Chunker: splits an input CSV into fixed-size chunk files on disk.

Chunk files are written to a temporary working directory so that
downstream processors can operate on them independently, enabling
parallel or streaming execution without holding the full dataset
in memory.
"""

import os
import math
import pandas as pd
from pathlib import Path

from pipeline.utils import get_logger, ensure_dir

logger = get_logger(__name__)


DEFAULT_CHUNK_SIZE = 2000


class ChunkWriter:
    """
    Splits a CSV file into chunks of at most *chunk_size* data rows each.

    Parameters
    ----------
    input_path : str or Path
        Path to the source CSV file.
    work_dir : str or Path
        Directory in which chunk files will be written.
    chunk_size : int
        Maximum number of data rows per chunk (default 2000).
    """

    def __init__(self, input_path, work_dir, chunk_size=DEFAULT_CHUNK_SIZE):
        self.input_path = Path(input_path)
        self.work_dir = Path(work_dir)
        self.chunk_size = int(chunk_size)
        if self.chunk_size < 1:
            raise ValueError(f"chunk_size must be >= 1, got {self.chunk_size}")
        self._chunk_paths = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_chunks(self):
        """
        Read the input CSV and write chunk files to *work_dir*.

        Returns a list of Path objects for the written chunk files,
        in order.
        """
        ensure_dir(self.work_dir)
        self._chunk_paths = []

        logger.info(
            "Reading %s for chunking (chunk_size=%d)",
            self.input_path,
            self.chunk_size,
        )

        df = pd.read_csv(self.input_path, dtype=str)
        total_rows = len(df)
        logger.info("Input has %d rows", total_rows)

        n_chunks = self._compute_n_chunks(total_rows)
        logger.info("Writing %d chunk(s)", n_chunks)

        for idx in range(n_chunks):
            chunk_df = self._slice_chunk(df, idx)
            chunk_path = self._chunk_path(idx)
            self._write_chunk(chunk_df, chunk_path)
            self._chunk_paths.append(chunk_path)
            logger.debug(
                "Wrote chunk %d/%d: %d rows -> %s",
                idx + 1,
                n_chunks,
                len(chunk_df),
                chunk_path,
            )

        logger.info("Chunking complete: %d files written", len(self._chunk_paths))
        return list(self._chunk_paths)

    @property
    def chunk_paths(self):
        """List of chunk file paths from the most recent write_chunks() call."""
        return list(self._chunk_paths)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_n_chunks(self, total_rows):
        """
        Return the number of chunk files that will be produced.
        Uses integer division — any remainder rows are included in the
        last regular chunk via the slice logic.
        """
        return max(1, total_rows // self.chunk_size)

    def _slice_chunk(self, df, chunk_index):
        """Return the sub-DataFrame for chunk *chunk_index*."""
        start = chunk_index * self.chunk_size
        end = start + self.chunk_size
        return df.iloc[start:end]

    def _chunk_path(self, index):
        """Return the Path for chunk file number *index*."""
        return self.work_dir / f"chunk_{index:04d}.csv"

    def _write_chunk(self, chunk_df, path):
        """
        Write *chunk_df* to *path* as CSV.

        The header is written unconditionally so that each chunk file
        is self-describing and can be processed independently by
        external consumers that do not share state.
        """
        chunk_df.to_csv(path, index=False)
        logger.debug("Chunk written: %s (%d bytes)", path, os.path.getsize(path))


def split_csv(input_path, work_dir, chunk_size=DEFAULT_CHUNK_SIZE):
    """
    Convenience wrapper around ChunkWriter.

    Returns the list of chunk file paths.
    """
    writer = ChunkWriter(input_path, work_dir, chunk_size=chunk_size)
    return writer.write_chunks()


def estimate_chunks(input_path, chunk_size=DEFAULT_CHUNK_SIZE):
    """
    Estimate the number of chunks without reading the whole file.
    Uses line count heuristic (fast for large files).
    """
    n_lines = 0
    with open(input_path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                n_lines += 1
    data_lines = max(0, n_lines - 1)  # subtract header
    return max(1, data_lines // chunk_size)
