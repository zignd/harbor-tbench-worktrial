import struct
import zlib

def vu(x):
    x = int(x)
    out = bytearray()
    while x >= 128:
        out.append((x & 127) | 128)
        x >>= 7
    out.append(x)
    return bytes(out)

def sv(x):
    return vu((int(x) << 1) ^ (int(x) >> ((int(x).bit_length() or 1))))

def make(records, damaged=(), reorder=False, duplicates=False, truncate=False):
    groups = [records[i:i + 3] for i in range(0, len(records), 3)]
    frames = []
    for group_number, group_records in enumerate(groups):
        members = [row[0] for row in group_records]
        coefficients = [row[1] for row in group_records]
        exponents = [row[2] for row in group_records]
        for sequence, coefficient, exponent in group_records:
            payload = sv(coefficient) + sv(exponent)
            crc = 0 if sequence in damaged else (zlib.crc32(payload) & 0xffffffff)
            frame = (b'D' + vu(group_number) + vu(sequence) + vu(len(payload)) +
                     payload + struct.pack('<I', crc))
            frames.append(frame)
        parity_body = (vu(len(members)) + b''.join(vu(x) for x in members) +
                       sv(sum(coefficients)) + sv(sum(exponents)))
        parity = (b'P' + vu(group_number) + vu(0) + vu(len(parity_body)) +
                  parity_body + struct.pack('<I', zlib.crc32(parity_body) & 0xffffffff))
        frames.append(parity)
    if duplicates:
        frames.extend(frames[:2])
    if reorder:
        frames.reverse()
    if truncate:
        frames = frames[:-2]
    return b'RFX1' + vu(1) + vu(len(records)) + b''.join(frames)
