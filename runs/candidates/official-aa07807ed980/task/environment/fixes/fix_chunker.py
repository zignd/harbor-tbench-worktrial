import pathlib

path = pathlib.Path('pipeline/chunker.py')
src = path.read_text()

old_a = '    num_complete_chunks = total_rows // chunk_size\n\n    for chunk_index in range(num_complete_chunks):\n        start = chunk_index * chunk_size\n        end = start + chunk_size\n'
new_a = '    num_complete_chunks = total_rows // chunk_size\n    has_remainder = (total_rows % chunk_size) != 0\n    total_chunks = num_complete_chunks + (1 if has_remainder else 0)\n\n    for chunk_index in range(total_chunks):\n        start = chunk_index * chunk_size\n        end = min(start + chunk_size, total_rows)\n'

if old_a not in src:
    print('ERROR: chunker pattern not found')
    raise SystemExit(1)

path.write_text(src.replace(old_a, new_a, 1))
print('chunker.py fixed: remainder chunk now included')
