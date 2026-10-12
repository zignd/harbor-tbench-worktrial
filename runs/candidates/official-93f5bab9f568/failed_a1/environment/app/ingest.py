"""
Ingestion module: reads CSV files from an input directory,
validates columns and types, and returns a combined DataFrame.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from config import (
    get_logger,
    CSV_REQUIRED_COLUMNS,
    CSV_COLUMN_TYPES,
    CHUNK_SIZE,
)
from utils import (
    list_data_files,
    coerce_numeric,
    rename_columns_lower,
    strip_string_columns,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_columns(df: pd.DataFrame, path: Path) -> None:
    """Raise ValueError if required columns are missing."""
    missing = set(CSV_REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"{path}: missing required columns: {sorted(missing)}"
        )


def _cast_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Cast columns to their declared types where possible."""
    df = df.copy()
    for col, typ in CSV_COLUMN_TYPES.items():
        if col not in df.columns:
            continue
        if typ is float:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif typ is str:
            df[col] = df[col].astype(str)
    return df


def _drop_bad_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with null values in required columns."""
    before = len(df)
    df = df.dropna(subset=CSV_REQUIRED_COLUMNS)
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d row(s) with null required fields", dropped)
    return df


def _read_single_file(path: Path) -> Optional[pd.DataFrame]:
    """Read one CSV file and return a validated DataFrame, or None on error."""
    logger.info("Reading %s", path)
    try:
        chunks = []
        for chunk in pd.read_csv(
            path,
            dtype=str,  # read everything as str first
            chunksize=CHUNK_SIZE,
            skip_blank_lines=True,
        ):
            chunk = rename_columns_lower(chunk)
            chunk = strip_string_columns(chunk)
            _validate_columns(chunk, path)
            chunk = _cast_columns(chunk)
            chunk = _drop_bad_rows(chunk)
            chunks.append(chunk)

        if not chunks:
            logger.warning("%s produced no valid rows", path)
            return None

        df = pd.concat(chunks, ignore_index=True)
        logger.info("%s: loaded %d rows", path, len(df))
        return df

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read %s: %s", path, exc)
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_directory(directory: str | Path) -> pd.DataFrame:
    """
    Read all supported data files in *directory* and return a single
    concatenated DataFrame with validated, type-cast columns.

    Raises ValueError if no data files are found or none yield rows.
    """
    files = list_data_files(directory)
    if not files:
        raise ValueError(f"No supported data files found in {directory}")

    frames: List[pd.DataFrame] = []
    for path in files:
        df = _read_single_file(path)
        if df is not None and len(df) > 0:
            frames.append(df)

    if not frames:
        raise ValueError(f"All files in {directory} produced empty DataFrames")

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        "Ingestion complete: %d file(s), %d total row(s)",
        len(frames),
        len(combined),
    )
    return combined


def ingest_file(path: str | Path) -> pd.DataFrame:
    """
    Read a single CSV file and return a validated DataFrame.
    Convenience wrapper around the internal helper.
    """
    df = _read_single_file(Path(path))
    if df is None or len(df) == 0:
        raise ValueError(f"{path} produced no valid rows")
    return df
