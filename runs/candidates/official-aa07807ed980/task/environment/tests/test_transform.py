"""Unit tests for pipeline/transform.py."""

from __future__ import annotations

import pandas as pd
import pytest

from pipeline.transform import coerce_types, transform_chunk
from pipeline.schema import SchemaError


SAMPLE_ROW = {
    "record_id": "REC0000001",
    "name": "Alice",
    "amount": "99.99",
    "date": "2023-06-15",
    "status": "active",
}


def make_df(**overrides):
    row = {**SAMPLE_ROW, **overrides}
    return pd.DataFrame([row])


class TestCoerceTypes:
    def test_amount_becomes_float(self):
        df = coerce_types(make_df())
        assert df["amount"].dtype == float
        assert df["amount"].iloc[0] == pytest.approx(99.99)

    def test_bad_amount_becomes_nan(self):
        df = coerce_types(make_df(amount="not-a-number"))
        assert pd.isna(df["amount"].iloc[0])

    def test_status_lowercased(self):
        df = coerce_types(make_df(status="ACTIVE"))
        assert df["status"].iloc[0] == "active"

    def test_date_normalised(self):
        df = coerce_types(make_df(date="15/06/2023"))
        assert df["date"].iloc[0] == "2023-06-15"


class TestTransformChunk:
    def test_valid_row_accepted(self):
        df = make_df()
        valid, rejected = transform_chunk(df, run_dedup=False)
        assert len(valid) == 1
        assert len(rejected) == 0

    def test_invalid_status_rejected(self):
        df = make_df(status="unknown")
        valid, rejected = transform_chunk(df, run_dedup=False)
        assert len(valid) == 0
        assert len(rejected) == 1

    def test_missing_column_raises(self):
        df = pd.DataFrame([{"record_id": "REC0000001", "name": "Alice"}])
        with pytest.raises(Exception):
            transform_chunk(df, run_dedup=False)

    def test_negative_amount_rejected(self):
        df = make_df(amount="-5.00")
        valid, rejected = transform_chunk(df, run_dedup=False)
        assert len(rejected) == 1

    def test_empty_name_rejected(self):
        df = make_df(name="")
        valid, rejected = transform_chunk(df, run_dedup=False)
        assert len(rejected) == 1
