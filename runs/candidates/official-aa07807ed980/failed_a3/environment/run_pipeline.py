"""
run_pipeline.py - CLI driver for the CSV chunked ingestion pipeline.

Usage:
    python run_pipeline.py --input <input_csv> --output <output_csv>
                           [--chunk-size <n>] [--work-dir <dir>]
                           [--rejected <rejected_csv>]

The pipeline:
  1. Splits the input CSV into fixed-size chunk files (chunker).
  2. Passes the chunk file list to the assembler.
  3. The assembler reads, validates, transforms, and concatenates chunks.
  4. Writes rejected rows to the rejected CSV.
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path

import click

from pipeline.chunker import split_csv, DEFAULT_CHUNK_SIZE
from pipeline.assembler import Assembler
from pipeline.utils import get_logger, Timer

logger = get_logger("run_pipeline")


@click.command()
@click.option(
    "--input", "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the input CSV file.",
)
@click.option(
    "--output", "output_path",
    required=True,
    type=click.Path(dir_okay=False),
    help="Path for the assembled output CSV.",
)
@click.option(
    "--rejected", "rejected_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Path for the rejected-rows CSV (default: <output_dir>/rejected.csv).",
)
@click.option(
    "--chunk-size",
    default=DEFAULT_CHUNK_SIZE,
    show_default=True,
    type=click.IntRange(min=1),
    help="Number of data rows per chunk.",
)
@click.option(
    "--work-dir",
    default=None,
    type=click.Path(file_okay=False),
    help="Working directory for chunk files (default: auto temp dir).",
)
@click.option(
    "--keep-work-dir",
    is_flag=True,
    default=False,
    help="Do not delete the working directory after completion.",
)
def main(
    input_path,
    output_path,
    rejected_path,
    chunk_size,
    work_dir,
    keep_work_dir,
):
    """Run the CSV chunked ingestion pipeline.

    Exit code is 0 on success."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    if rejected_path is None:
        rejected_path = output_path.parent / "rejected.csv"
    else:
        rejected_path = Path(rejected_path)

    use_temp = work_dir is None
    if use_temp:
        work_dir = Path(tempfile.mkdtemp(prefix="pipeline_work_"))
    else:
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Pipeline start: input=%s output=%s", input_path, output_path)
    logger.info("chunk_size=%d  work_dir=%s", chunk_size, work_dir)

    with Timer("total") as total_timer:
        # ----------------------------------------------------------------
        # Step 1: Split input into chunk files on disk
        # ----------------------------------------------------------------
        with Timer("chunking"):
            chunk_paths = split_csv(input_path, work_dir, chunk_size=chunk_size)
        logger.info("Chunking done: %d chunk file(s)", len(chunk_paths))

        # ----------------------------------------------------------------
        # Step 2: Assemble (reads, transforms, and concatenates chunks)
        # ----------------------------------------------------------------
        with Timer("assembly"):
            assembler = Assembler(
                output_path=output_path,
                rejected_path=rejected_path,
            )
            n_written = assembler.assemble_from_files(chunk_paths)

    logger.info(
        "Pipeline complete in %s: %d chunk(s), %d rows written",
        total_timer,
        len(chunk_paths),
        n_written,
    )
    print(f"Processed {len(chunk_paths)} chunks, {n_written} rows written.")

    # ----------------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------------
    if use_temp and not keep_work_dir:
        shutil.rmtree(work_dir, ignore_errors=True)
    elif keep_work_dir:
        logger.info("Work directory retained: %s", work_dir)


if __name__ == "__main__":
    main()
