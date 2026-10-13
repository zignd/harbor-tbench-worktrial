#!/bin/bash
set -e
cd /home/developer/workspace
git init
git config user.email "dev@example.com"
git config user.name "IoT Developer"

# Create the protocol documentation
cat > protocol.md <<'PROTO'
# IoT Sensor Protocol v1.0

## Packet Format
- Header: 2 bytes
  - Byte 0: Sync (0xAA)
  - Byte 1: Type (0x51 for Type A, 0x52 for Type B)
- Length: 1 byte (Payload size)
- Payload: N bytes
- Checksum: 2 bytes (16-bit, big-endian)

## Checksum Calculation
The checksum is a 16-bit one's complement sum of the length byte and payload bytes.

### Type B Special Handling
For Type B packets (0x52), the sum must be initialized with IV 0xBEEF. 
Before the final one's complement fold, the 16-bit sum must be left-circularly shifted by 3 bits.
PROTO

# Initial correct version (supporting both types)
cat > capture.sh <<'SH'
#!/bin/bash
# IoT Frame Validator

validate() {
    local hex=($1)
    [ "${hex[0]}" != "AA" ] && return 1
    
    local type=${hex[1]}
    local len=$(( 16#${hex[2]} ))
    
    local sum=0
    if [ "$type" == "52" ]; then
        sum=$(( 16#BEEF ))
    fi
    
    sum=$(( sum + len ))
    for (( i=0; i<len; i++ )); do
        sum=$(( sum + 16#${hex[$((3+i))]} ))
    done

    while [ $sum -gt 65535 ]; do
        sum=$(( (sum & 0xFFFF) + (sum >> 16) ))
    done

    if [ "$type" == "52" ]; then
        # Type B: 3-bit left circular shift
        sum=$(( ((sum << 3) & 0xFFFF) | (sum >> 13) ))
    fi

    local calculated=$(( sum ^ 0xFFFF ))
    local expected=$(( (16#${hex[$((3+len))]} << 8) | 16#${hex[$((4+len))]} ))

    [ $calculated -eq $expected ]
}

while read -r line; do
    validate "$line" && echo "VALID" || echo "INVALID"
done
SH

git add .
git commit -m "Initial protocol implementation"

# Now introduce the broken version
cat > capture.sh <<'SH'
#!/bin/bash
# IoT Frame Validator (Optimized)

validate() {
    local hex=($1)
    if [ "${hex[0]}" != "AA" ]; then return 1; fi
    
    local len=$(( 16#${hex[2]} ))
    local sum=0

    # Sum length and payload
    sum=$(( sum + len ))
    for (( i=0; i<len; i++ )); do
        sum=$(( sum + 16#${hex[$(( 3 + i ))]} ))
    done

    # Fold into 16 bits
    while [ $sum -gt 65535 ]; do
        sum=$(( (sum & 0xFFFF) + (sum >> 16) ))
    done

    local calculated=$(( sum ^ 0xFFFF ))

    # Read expected checksum (Big Endian)
    # BUG: The logic here was accidentally swapped to little-endian during cleanup
    local e_low=${hex[$(( 3 + len ))]}
    local e_high=${hex[$(( 4 + len ))]}
    local expected=$(( (16#${e_high} << 8) | 16#${e_low} ))

    if [ $calculated -eq $expected ]; then
        return 0
    else
        return 1
    fi
}

while read -r line; do
    if validate "$line"; then
        echo "VALID"
    else
        echo "INVALID"
    fi
done
SH

git add capture.sh
git commit -m "Cleanup capture script and optimize loops"

# Create some Type A samples. 
# Type A, Len 3, Payload 01 02 03. Sum = 3+1+2+3 = 9. Fold=9. ~9 = 0xFFF6. BE = FF F6.
# Current broken script expects LE: F6 FF -> (FF << 8) | F6 = FF F6. 
# Wait, if e_low = F6, e_high = FF, expected = (FF << 8) | F6 = FFF6. 
# So AA 51 03 01 02 03 F6 FF will be VALID in the broken script.
mkdir -p data
echo "AA 51 03 01 02 03 F6 FF" > data/sample_a.txt
