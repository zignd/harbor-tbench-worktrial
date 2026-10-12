# CSV ingestion module

import os
from typing import List, Optional

import pandas as pd

from config import CSV_DTYPES, REQUIRED_COLUMNS, CHUNK_SIZE
from utils import get_logger, discover_csv_files, coerce_revenue, summarize_dataframe

logger = get_logger("ingest")


def _read_single_csv(path: str) -> Optional[pd.DataFrame]:
    """Read a single CSV file and return a DataFrame, or None on error."""
    try:
        df = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,
            skipinitialspace=True,
        )
    except Exception as exc:
        logger.error(f"Failed to read {path}: {exc}")
        return None

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        logger.error(f"File {path} missing columns: {missing}")
        return None

    # Keep only required columns
    df = df[list(REQUIRED_COLUMNS)].copy()

    # Coerce revenue to numeric
    df["revenue"] = coerce_revenue(df["revenue"])

    logger.debug(f"Read {path}: {summarize_dataframe(df)}")
    return df


def ingest_directory(input_dir: str) -> pd.DataFrame:
    """Read all CSV files in input_dir and return a combined DataFrame."""
    files = discover_csv_files(input_dir)
    if not files:
        logger.warning(f"No CSV files found in {input_dir}")
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))

    logger.info(f"Ingesting {len(files)} CSV file(s) from {input_dir}")

    frames = []
    for path in files:
        df = _read_single_csv(path)
        if df is not None and len(df) > 0:
            frames.append(df)
            logger.info(f"  {os.path.basename(path)}: {len(df)} rows")
        else:
            logger.warning(f"  {os.path.basename(path)}: skipped (empty or error)")

    if not frames:
        logger.warning("No data loaded from any CSV file")
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))

    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"Ingestion complete: {len(combined)} total rows")
    return combined


def ingest_files(file_paths: List[str]) -> pd.DataFrame:
    """Read a specific list of CSV file paths and return a combined DataFrame."""
    if not file_paths:
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))

    frames = []
    for path in file_paths:
        df = _read_single_csv(path)
        if df is not None and len(df) > 0:
            frames.append(df)

    if not frames:
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))

    return pd.concat(frames, ignore_index=True)


def validate_ingested(df: pd.DataFrame) -> pd.DataFrame:
    """Log a summary of what was ingested; return df unchanged."""
    if df.empty:
        logger.warning("Ingested DataFrame is empty")
        return df

    logger.info(f"Validated ingested data: {len(df)} rows")
    for col in ["region", "product_category", "date"]:
        n_unique = df[col].nunique()
        logger.debug(f"  {col}: {n_unique} unique values")

    rev_null = df["revenue"].isna().sum()
    if rev_null:
        logger.warning(f"  revenue: {rev_null} null values will be dropped")

    return df


def ingest_pipeline(input_dir: str) -> pd.DataFrame:
    """Full ingestion pipeline: read + validate."""
    raw = ingest_directory(input_dir)
    validated = validate_ingested(raw)
    return validated
