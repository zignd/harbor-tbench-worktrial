#!/bin/bash
set -e
mkdir -p /home/developer/repo
cd /home/developer/repo
git init
git config user.email "dev@iot-embedded.local"
git config user.name "IoT Developer"

cat > capture.sh <<'OUTER'
#!/bin/bash
# IoT Frame Validator

validate_frame() {
    local frame="$1"
    # Header: 2 bytes
    # Length: 2 bytes (Big Endian)
    # Checksum: 2 bytes
    # Payload: N bytes
    
    header=$(echo "$frame" | cut -c1-4)
    len_hex=$(echo "$frame" | cut -c5-8)
    check_hex=$(echo "$frame" | cut -c9-12)
    payload=$(echo "$frame" | cut -c13-)
    
    # Current logic: Simple 16-bit sum of all 16-bit words
    # Note: there was some debate about endianness and IVs in the past
    sum=0
    for (( i=0; i<${#frame}; i+=4 )); do
        word="0x${frame:$i:4}"
        if [ ${#frame} -le $((i+2)) ]; then
             # pad last byte if needed
             word="0x${frame:$i:2}00"
        fi
        sum=$(( (sum + word) & 0xFFFF ))
done

    if [ "$sum" -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

while read -r line; do
    if validate_frame "$line"; then
        echo "VALID: $line"
    else
        echo "CORRUPT: $line"
    fi
done
OUTER
chmod +x capture.sh
git add capture.sh
git commit -m "Initial commit: baseline validator"

# The "Working" Version in history
cat > capture.sh <<'OUTER'
#!/bin/bash
# IoT Frame Validator

# Protocol Specification v1.2:
# - All packets use 16-bit one's complement sum.
# - Type A (Header 0x4154): standard fold.
# - Type B (Header 0x5254): Initialize sum with 0xBEEF.
#   After summing all words, if Type B, perform a 3-bit left circular shift on the 16-bit result before final fold.
# - Endianness: All 16-bit fields are Big Endian.

validate_frame() {
    local hex_data="$1"
    # Implementation removed for brevity in this historical version
    return 0
}
OUTER
git commit -am "Update protocol spec documentation in capture.sh"

# The broken version
cat > capture.sh <<'OUTER'
#!/bin/bash

validate_frame() {
    local hex_data="$1"
    local sum=0
    
    # TODO: The rebase messed up the Type B logic and endianness
    # We are currently just summing bytes which is wrong
    for (( i=0; i<${#hex_data}; i+=2 )); do
        val="0x${hex_data:$i:2}"
        sum=$(( sum + val ))
    done
    
    # Fold to 16 bits
    while [ $sum -gt 65535 ]; do
        sum=$(( (sum & 0xFFFF) + (sum >> 16) ))
done

    [ $((sum ^ 0xFFFF)) -eq 0 ]
}

while read -r line; do
    if validate_frame "$line"; then
        echo "VALID: $line"
    else
        echo "CORRUPT: $line"
    fi
done
OUTER
git commit -am "Refactor validator for performance"

mkdir data
# Generate some Type A samples (valid and invalid)
# Type A: 4154 (Header) 0004 (Len) ? ? (Checksum) DEAD BEEF (Payload)
# 4154 + 0004 + DEAD + BEEF = 17C0C -> 7C0C + 1 = 7C0D. ~7C0D = 83F2
echo "4154000483F2DEADBEEF" > data/sample_a.txt
# Corrupt one
echo "4154000483F2DEADBEEE" >> data/sample_a.txt

git add data/
git commit -m "Add sample data"
