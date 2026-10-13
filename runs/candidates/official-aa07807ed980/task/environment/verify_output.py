"""Standalone checker: report duplicate keys and row-count mismatches."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import pandas as pd


def count_input_rows(input_path: Path) -> int:
    df = pd.read_csv(input_path, dtype=str)
    return len(df)


def check_output(output_path: Path, expected_rows: int | None = None) -> int:
    """Check *output_path* for duplicate record_ids and row-count issues.

    Returns 0 if all checks pass, 1 otherwise.
    """
    if not output_path.exists():
        click.echo(f"Output file not found: {output_path}", err=True)
        return 1

    df = pd.read_csv(output_path, dtype=str)
    exit_code = 0

    # Duplicate check
    if "record_id" in df.columns:
        dup_mask = df["record_id"].duplicated(keep=False)
        n_dups = dup_mask.sum()
        if n_dups:
            click.echo(f"Duplicate primary keys detected: {n_dups}")
            exit_code = 1
        else:
            click.echo("No duplicate primary keys.")
    else:
        click.echo("WARNING: record_id column not found in output.")
        exit_code = 1

    # Row count check
    if expected_rows is not None:
        actual = len(df)
        if actual != expected_rows:
            click.echo(
                f"Row count mismatch: expected {expected_rows}, got {actual}"
            )
            exit_code = 1
        else:
            click.echo(f"Row count OK: {actual}")

    return exit_code


@click.command()
@click.argument("output_csv", type=click.Path())
@click.option("--input", "input_csv", default=None, type=click.Path(exists=True),
              help="Original input CSV (used for expected row count).")
@click.option("--expected-rows", default=None, type=int,
              help="Expected row count (overrides --input).")
def main(output_csv: str, input_csv: str | None, expected_rows: int | None) -> None:
    """Check OUTPUT_CSV for data quality issues."""
    out = Path(output_csv)

    if expected_rows is None and input_csv is not None:
        expected_rows = count_input_rows(Path(input_csv))

    code = check_output(out, expected_rows)
    sys.exit(code)


if __name__ == "__main__":
    main()
