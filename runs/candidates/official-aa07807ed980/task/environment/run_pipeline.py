"""CLI driver: chunker -> per-chunk transform -> assembler pipeline."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import click
import pandas as pd

from pipeline.assembler import assemble
from pipeline.chunker import DEFAULT_CHUNK_SIZE, split_csv
from pipeline.transform import transform_chunk
from pipeline.utils import ensure_dir, get_logger, Timer

_log = get_logger("run_pipeline")


@click.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
@click.option("--output", "output_path", required=True, type=click.Path())
@click.option("--rejected", "rejected_path", default=None, type=click.Path())
@click.option("--chunk-size", default=DEFAULT_CHUNK_SIZE, show_default=True)
@click.option("--work-dir", default=None, type=click.Path())
@click.option("--keep-work", is_flag=True, default=False)
def main(
    input_path: str,
    output_path: str,
    rejected_path: str | None,
    chunk_size: int,
    work_dir: str | None,
    keep_work: bool,
) -> None:
    """Run the CSV ingestion pipeline."""
    inp = Path(input_path)
    out = Path(output_path)
    ensure_dir(out.parent)

    if rejected_path is None:
        rejected_path = str(out.parent / "rejected.csv")

    _tmp_owned = work_dir is None
    scratch = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="pipeline_"))
    chunk_dir = scratch / "chunks"
    result_dir = scratch / "results"
    ensure_dir(chunk_dir)
    ensure_dir(result_dir)

    try:
        with Timer() as total_timer:
            _log.info("=== Pipeline start: %s ===", inp)

            # Step 1: split input into chunk files
            with Timer() as t:
                chunk_paths = split_csv(inp, chunk_dir, chunk_size=chunk_size)
            _log.info("Chunking: %d chunks in %.2fs", len(chunk_paths), t.elapsed)

            # Step 2: transform each chunk independently
            total_valid = 0
            total_rejected_count = 0
            for idx, chunk_path in enumerate(chunk_paths):
                chunk_df = pd.read_csv(chunk_path, dtype=str)
                valid_df, rejected_df = transform_chunk(chunk_df)

                valid_out = result_dir / f"valid_chunk_{idx:06d}.csv"
                rejected_out = result_dir / f"rejected_chunk_{idx:06d}.csv"
                valid_df.to_csv(valid_out, index=False)
                rejected_df.to_csv(rejected_out, index=False)

                total_valid += len(valid_df)
                total_rejected_count += len(rejected_df)

            _log.info("Transform: %d valid, %d rejected", total_valid, total_rejected_count)

            # Step 3: assemble results
            stats = assemble(result_dir, out, rejected_path=rejected_path)

        click.echo(
            f"Processed {stats['num_chunks']} chunks, "
            f"{stats['total_written']} rows written."
        )
        _log.info("=== Pipeline complete in %.2fs ===", total_timer.elapsed)

    finally:
        if _tmp_owned and not keep_work:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
