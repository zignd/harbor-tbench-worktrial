"""
Transform: applies column-type coercion, schema validation, and
data-quality rules to a single chunk DataFrame.

Each chunk is processed independently so that validation errors
in one chunk do not abort processing of others.
"""

import pandas as pd
from pipeline.schema import (
    REQUIRED_COLUMNS,
    SchemaValidationError,
    check_columns,
    validate_row,
)
from pipeline.utils import get_logger

logger = get_logger(__name__)


class TransformError(Exception):
    """Raised when a chunk cannot be transformed at all (e.g. wrong schema)."""
    pass


# ---------------------------------------------------------------------------
# Type-coercion helpers
# ---------------------------------------------------------------------------

def _coerce_record_id(series):
    """Convert record_id column to nullable integer strings."""
    return pd.to_numeric(series, errors="coerce").astype("Int64").astype(str)


def _coerce_amount(series):
    """Round amount to two decimal places after coercing to float."""
    return pd.to_numeric(series, errors="coerce").round(2)


def _coerce_status(series):
    """Normalise status to lower-case."""
    return series.str.strip().str.lower()


def _coerce_date(series):
    """Strip whitespace from date strings."""
    return series.str.strip()


def _coerce_name(series):
    """Strip leading/trailing whitespace from name."""
    return series.str.strip()


COERCION_MAP = {
    "record_id": _coerce_record_id,
    "amount": _coerce_amount,
    "status": _coerce_status,
    "date": _coerce_date,
    "name": _coerce_name,
}


# ---------------------------------------------------------------------------
# Main transform logic
# ---------------------------------------------------------------------------

class ChunkTransformer:
    """
    Applies validation and transformation rules to a chunk DataFrame.

    Parameters
    ----------
    rejected_rows : list
        Accumulator list; rows that fail validation are appended here
        as dicts so that callers can write a rejected.csv file.
    """

    def __init__(self, rejected_rows=None):
        self.rejected_rows = rejected_rows if rejected_rows is not None else []
        self._stats = {"input": 0, "accepted": 0, "rejected": 0, "duplicates_removed": 0}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transform(self, df):
        """
        Transform *df* and return a cleaned DataFrame.

        Steps:
          1. Verify required columns are present.
          2. Coerce column types.
          3. Validate each row; invalid rows go to rejected_rows.
          4. Remove duplicate rows to avoid double-counting.
          5. Return cleaned DataFrame.
        """
        missing = check_columns(df)
        if missing:
            raise TransformError(f"Missing required columns: {missing}")

        self._stats["input"] += len(df)

        df = self._coerce_types(df.copy())
        df, rejected = self._validate_rows(df)
        self.rejected_rows.extend(rejected)
        self._stats["rejected"] += len(rejected)

        df = self._remove_duplicates(df)

        self._stats["accepted"] += len(df)
        return df

    @property
    def stats(self):
        """Return a copy of the running statistics dict."""
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _coerce_types(self, df):
        """Apply column-level type coercions."""
        for col, fn in COERCION_MAP.items():
            if col in df.columns:
                df[col] = fn(df[col])
        return df

    def _validate_rows(self, df):
        """
        Iterate rows and separate valid from invalid.
        Returns (valid_df, list_of_rejected_dicts).
        """
        valid_indices = []
        rejected = []
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            try:
                validate_row(row_dict)
                valid_indices.append(idx)
            except SchemaValidationError as exc:
                row_dict["_rejection_reason"] = str(exc)
                rejected.append(row_dict)
                logger.debug("Row %s rejected: %s", idx, exc)
        return df.loc[valid_indices], rejected

    def _remove_duplicates(self, df):
        """
        Remove duplicate rows from the chunk.

        Deduplication is performed on the business-key columns that
        identify logically equivalent records within a delivery batch.
        When duplicates are found, the first occurrence is kept.
        """
        before = len(df)
        df = df.drop_duplicates(subset=["name", "amount"], keep="first")
        removed = before - len(df)
        if removed:
            logger.debug("Removed %d duplicate row(s) in chunk", removed)
        self._stats["duplicates_removed"] += removed
        return df


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def transform_chunk(df, rejected_rows=None):
    """
    Apply all transformations to *df* and return the cleaned DataFrame.

    Rejected rows are appended to *rejected_rows* if provided.
    """
    transformer = ChunkTransformer(rejected_rows=rejected_rows)
    return transformer.transform(df)
