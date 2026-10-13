import pathlib

path = pathlib.Path('pipeline/transform.py')
src = path.read_text()

old = ('    # Use a stable subset of columns for deduplication; record_id alone\n'
       '    # would be too narrow because it may vary between otherwise-identical rows.\n'
       '    dedup_cols = [c for c in ["name", "amount"] if c in df.columns]')
new = ('    # Deduplicate on the primary key so each record_id appears only once.\n'
       '    dedup_cols = [c for c in ["record_id"] if c in df.columns]')

if old not in src:
    print('ERROR: transform dedup pattern not found')
    raise SystemExit(1)

path.write_text(src.replace(old, new, 1))
print('transform.py fixed: deduplication now uses record_id')
