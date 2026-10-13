import pathlib

path = pathlib.Path('pipeline/assembler.py')
src = path.read_text()

# Fix 1: replace buggy text-concat reader with proper pd.read_csv
old1 = ('def _concat_chunk_results(result_paths: list[Path]) -> pd.DataFrame:\n'
        '    """Concatenate per-chunk result CSVs into a single DataFrame.\n'
        '\n'
        '    Reads each result file as text and joins them for a single parse pass.\n'
        '    """\n'
        '    segments: list[str] = []\n'
        '    for path in result_paths:\n'
        '        with open(path, encoding="utf-8") as fh:\n'
        '            segments.append(fh.read())\n'
        '    combined = "".join(segments)\n'
        '    if not combined.strip():\n'
        '        return pd.DataFrame()\n'
        '    return pd.read_csv(io.StringIO(combined), dtype=str)')

new1 = ('def _concat_chunk_results(result_paths: list[Path]) -> pd.DataFrame:\n'
        '    """Concatenate per-chunk result CSVs into a single DataFrame.\n'
        '\n'
        '    Each result file has exactly one header row; pd.read_csv handles it\n'
        '    correctly so repeated headers do not appear as data rows.\n'
        '    """\n'
        '    frames = [pd.read_csv(p, dtype=str) for p in result_paths if p.stat().st_size > 0]\n'
        '    if not frames:\n'
        '        return pd.DataFrame()\n'
        '    return pd.concat(frames, ignore_index=True)')

if old1 not in src:
    print('ERROR: assembler concat pattern not found')
    raise SystemExit(1)

src2 = src.replace(old1, new1, 1)
src2 = src2.replace('import io\n', '', 1)

# Fix 2: add global dedup on record_id after concatenation
old2 = ('        output_df = _concat_chunk_results(valid_paths)\n'
        '        output_df.to_csv(output_path, index=False)')

new2 = ('        output_df = _concat_chunk_results(valid_paths)\n'
        '        if "record_id" in output_df.columns:\n'
        '            output_df = output_df.drop_duplicates(subset=["record_id"], keep="first")\n'
        '        output_df.to_csv(output_path, index=False)')

if old2 not in src2:
    print('ERROR: assembler dedup pattern not found')
    raise SystemExit(1)

src2 = src2.replace(old2, new2, 1)
path.write_text(src2)
print('assembler.py fixed: proper pd.read_csv and global record_id dedup')
