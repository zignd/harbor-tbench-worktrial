#!/usr/bin/env python3
import sys, struct, json, math

def crc32c(data):
    crc = 0xffffffff
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82f63b78 if crc & 1 else 0)
    return crc ^ 0xffffffff

def main():
    data = sys.stdin.buffer.read()
    pos = 0
    records = []
    while True:
        start = data.find(b'MAF2', pos)
        if start < 0 or start + 16 > len(data):
            break
        rows, cols, sequence, length = struct.unpack_from('<HHII', data, start + 4)
        expected = (rows * cols + rows + cols) * 8
        if not (1 <= rows <= 12 and 1 <= cols <= 12 and length == expected):
            pos = start + 1
            continue
        end = start + 20 + length
        if end > len(data):
            pos = start + 1
            continue
        body = data[start + 4:start + 16 + length]
        supplied = struct.unpack_from('<I', data, start + 16 + length)[0]
        if crc32c(body) != supplied:
            pos = start + 1
            continue
        count = rows * cols + rows + cols
        values = struct.unpack_from('<%dd' % count, data, start + 16)
        if not all(math.isfinite(value) for value in values):
            pos = start + 1
            continue
        basis = values[:rows * cols]
        eigenvalues = values[rows * cols:rows * cols + rows]
        physical = values[rows * cols + rows:]
        coefficients = [sum(basis[j * cols + i] * physical[i] for i in range(cols)) for j in range(rows)]
        if not all(math.isfinite(value) for value in coefficients):
            pos = start + 1
            continue
        energy = 0.0
        valid = True
        for coefficient, eigenvalue in zip(coefficients, eigenvalues):
            if eigenvalue == 0.0:
                if coefficient != 0.0:
                    valid = False
                    break
            elif eigenvalue > 0.0:
                energy += coefficient * coefficient / eigenvalue
            else:
                valid = False
                break
        if valid and math.isfinite(energy):
            records.append(json.dumps({'sequence': sequence, 'coefficients': coefficients, 'energy': energy}, separators=(',', ':'), allow_nan=False))
        pos = end
    if records:
        sys.stdout.write('\n'.join(records) + '\n')

if __name__ == '__main__':
    main()
