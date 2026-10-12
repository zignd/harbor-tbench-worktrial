"""
Unit tests for pipeline.transform.
All tests pass in the initial (buggy) state; they only exercise
the transform module in isolation.
"""

import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.transform import transform_chunk, ChunkTransformer
from pipeline.schema import SchemaValidationError


def _make_df(rows):
    cols = ["record_id", "name", "amount", "date", "status"]
    return pd.DataFrame(rows, columns=cols)


def test_valid_rows_pass_through():
    df = _make_df([
        ["1", "Alice Smith", "10.50", "2023-01-15", "active"],
        ["2", "Bob Jones", "200.00", "2023-06-01", "pending"],
    ])
    result = transform_chunk(df)
    assert len(result) == 2


def test_invalid_amount_rejected():
    df = _make_df([
        ["1", "Alice Smith", "not_a_number", "2023-01-15", "active"],
        ["2", "Bob Jones", "50.00", "2023-06-01", "inactive"],
    ])
    rejected = []
    result = transform_chunk(df, rejected_rows=rejected)
    assert len(result) == 1
    assert len(rejected) == 1
    assert rejected[0]["record_id"] == "1"


def test_invalid_status_rejected():
    df = _make_df([
        ["3", "Carol Williams", "75.25", "2022-12-31", "UNKNOWN"],
    ])
    rejected = []
    result = transform_chunk(df, rejected_rows=rejected)
    assert len(result) == 0
    assert len(rejected) == 1


def test_invalid_date_rejected():
    df = _make_df([
        ["4", "Dave Brown", "5.00", "31-12-2023", "active"],
    ])
    rejected = []
    result = transform_chunk(df, rejected_rows=rejected)
    assert len(result) == 0
    assert len(rejected) == 1


def test_amount_coerced_to_float():
    df = _make_df([
        ["5", "Eve Davis", "100", "2023-03-10", "completed"],
    ])
    result = transform_chunk(df)
    assert len(result) == 1


def test_status_normalised_to_lowercase():
    df = _make_df([
        ["6", "Frank Miller", "30.00", "2023-07-04", "Active"],
    ])
    result = transform_chunk(df)
    assert len(result) == 1
    assert result.iloc[0]["status"] == "active"


def test_empty_dataframe():
    df = _make_df([])
    result = transform_chunk(df)
    assert len(result) == 0


def test_negative_amount_rejected():
    df = _make_df([
        ["7", "Grace Wilson", "-1.00", "2023-05-20", "active"],
    ])
    rejected = []
    result = transform_chunk(df, rejected_rows=rejected)
    assert len(result) == 0
    assert len(rejected) == 1
