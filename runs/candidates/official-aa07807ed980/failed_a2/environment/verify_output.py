"""
verify_output.py - standalone checker for pipeline output quality.

Usage:
    python verify_output.py <output_csv> [--input <input_csv>]

Prints:
  - Number of duplicate primary keys (record_id)
  - Row count vs expected (if --input is provided)
"""

import sys
from pathlib import Path

import click
import pandas as pd


@click.command()
@click.argument("output_csv", type=click.Path(exists=True))
@click.option(
    "--input", "input_csv",
    default=None,
    type=click.Path(exists=True),
    help="Original input CSV to compare row counts.",
)
@click.option(
    "--expected", "expected_rows",
    default=None,
    type=int,
    help="Expected row count (overrides --input count).",
)
def main(output_csv, input_csv, expected_rows):
    """Check output CSV for duplicate keys and row count accuracy."""
    df = pd.read_csv(output_csv, dtype=str)

    # ------------------------------------------------------------------
    # Duplicate primary key check
    # ------------------------------------------------------------------
    dup_mask = df["record_id"].duplicated(keep=False)
    n_dups = dup_mask.sum()
    if n_dups:
        print(f"Duplicate primary keys detected: {n_dups}")
    else:
        print("No duplicate primary keys.")

    # ------------------------------------------------------------------
    # Row count check
    # ------------------------------------------------------------------
    actual = len(df)
    if expected_rows is not None:
        expected = expected_rows
    elif input_csv is not None:
        input_df = pd.read_csv(input_csv, dtype=str)
        expected = len(input_df)
    else:
        print(f"Row count: {actual} (no expected count provided)")
        return

    if actual != expected:
        print(f"Row count mismatch: expected {expected}, got {actual}")
    else:
        print(f"Row count correct: {actual}")


if __name__ == "__main__":
    main()
