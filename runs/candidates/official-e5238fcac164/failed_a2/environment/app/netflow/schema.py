"""
schema.py - NetFlow v9 field type constants and helpers.

Field type IDs follow RFC 3954 (NetFlow Version 9 Flow-Record Format).
Only the subset relevant to settlement processing is defined here;
other field types may appear in captured records and are handled
generically by the parser.
"""

from typing import Dict

# ---------------------------------------------------------------------------
# Field type identifiers (RFC 3954, Section 8)
# ---------------------------------------------------------------------------

IN_BYTES            = 1   # Incoming counter for the number of bytes
IN_PKTS             = 2   # Incoming counter for the number of packets
FLOWS               = 3   # Number of flows
PROTOCOL            = 4   # IP protocol type
SRC_TOS             = 5   # Type of service byte
TCP_FLAGS           = 6   # Cumulative OR of TCP flags
L4_SRC_PORT         = 7   # TCP/UDP source port
IPV4_SRC_ADDR       = 8   # IPv4 source address
SRC_MASK            = 9   # Source address prefix mask
INPUT_SNMP          = 10  # SNMP index of input interface
L4_DST_PORT         = 11  # TCP/UDP destination port
IPV4_DST_ADDR       = 12  # IPv4 destination address
DST_MASK            = 13  # Destination address prefix mask
OUTPUT_SNMP         = 14  # SNMP index of output interface
IPV4_NEXT_HOP       = 15  # IPv4 address of next-hop router
SRC_AS              = 16  # Source BGP autonomous system number
DST_AS              = 17  # Destination BGP autonomous system number
BGP_IPV4_NEXT_HOP   = 18  # Next-hop router in BGP domain
MUL_DST_PKTS        = 19  # IP multicast outgoing packet counter
MUL_DST_BYTES       = 20  # IP multicast outgoing byte counter
LAST_SWITCHED       = 21  # SysUptime at flow end
FIRST_SWITCHED      = 22  # SysUptime at flow start
OUT_BYTES           = 23  # Outgoing counter for bytes
OUT_PKTS            = 24  # Outgoing counter for packets
MIN_PKT_LNGTH       = 25  # Minimum IP packet length
MAX_PKT_LNGTH       = 26  # Maximum IP packet length
IPV6_SRC_ADDR       = 27  # IPv6 source address
IPV6_DST_ADDR       = 28  # IPv6 destination address
IPV6_SRC_MASK       = 29  # IPv6 source prefix length
IPV6_DST_MASK       = 30  # IPv6 destination prefix length
IPV6_FLOW_LABEL     = 31  # IPv6 flow label
ICMP_TYPE           = 32  # ICMP type * 256 + code
MUL_IGMP_TYPE       = 33  # IGMP type
SAMPLING_INTERVAL   = 34  # Sampling interval
SAMPLING_ALGORITHM  = 35  # Sampling algorithm
FLOW_ACTIVE_TIMEOUT = 36  # Active flow timeout in seconds
FLOW_INACTIVE_TIMEOUT = 37  # Inactive flow timeout in seconds
ENGINE_TYPE         = 38  # Flow-switching engine type
ENGINE_ID           = 39  # Slot number of the flow-switching engine
TOTAL_BYTES_EXP     = 40  # Total bytes exported
TOTAL_PKTS_EXP      = 41  # Total packets exported
TOTAL_FLOWS_EXP     = 42  # Total flows exported
IPV4_SRC_PREFIX     = 44  # IPv4 source prefix
IPV4_DST_PREFIX     = 45  # IPv4 destination prefix
MPLS_TOP_LABEL_TYPE = 46  # MPLS top label type
MPLS_TOP_LABEL_IP   = 47  # Forwarding equivalent class
FLOW_SAMPLER_ID     = 48  # Identifier for each sampler
FLOW_SAMPLER_MODE   = 49  # Sampler mode
FLOW_SAMPLER_INTERVAL = 50  # Packet interval at which to sample
MIN_TTL             = 52  # Min TTL observed
MAX_TTL             = 53  # Max TTL observed
IPV4_IDENT          = 54  # IP identification
DST_TOS             = 55  # TOS at destination
IN_SRC_MAC          = 56  # Source MAC address
OUT_DST_MAC         = 57  # Destination MAC address
SRC_VLAN            = 58  # Source VLAN ID
DST_VLAN            = 59  # Destination VLAN ID
IP_PROTOCOL_VERSION = 60  # IP version
DIRECTION           = 61  # Flow direction
IPV6_NEXT_HOP       = 62  # IPv6 next-hop address
BGP_IPV6_NEXT_HOP   = 63  # BGP IPv6 next-hop
IPV6_OPTION_HEADERS = 64  # IPv6 option headers
MPLS_LABEL_1        = 70  # MPLS label 1
MPLS_LABEL_2        = 71  # MPLS label 2
MPLS_LABEL_3        = 72  # MPLS label 3
MPLS_LABEL_4        = 73  # MPLS label 4
MPLS_LABEL_5        = 74  # MPLS label 5
MPLS_LABEL_6        = 75  # MPLS label 6
MPLS_LABEL_7        = 76  # MPLS label 7
MPLS_LABEL_8        = 77  # MPLS label 8
MPLS_LABEL_9        = 78  # MPLS label 9
MPLS_LABEL_10       = 79  # MPLS label 10
IN_DST_MAC          = 80  # Destination MAC for incoming
OUT_SRC_MAC         = 81  # Source MAC for outgoing
IF_NAME             = 82  # Interface name
IF_DESC             = 83  # Interface description
SAMPLER_NAME        = 84  # Sampler name
IN_PERMANENT_BYTES  = 85  # Permanent flow input bytes
IN_PERMANENT_PKTS   = 86  # Permanent flow input packets
FRAGMENT_OFFSET     = 88  # Fragment offset
FORWARDING_STATUS   = 89  # Forwarding status
MPLS_PAL_RD         = 90  # MPLS PAL route distinguisher
MPLS_PREFIX_LEN     = 91  # MPLS prefix length
SRC_TRAFFIC_INDEX   = 92  # BGP policy accounting src
DST_TRAFFIC_INDEX   = 93  # BGP policy accounting dst
APPLICATION_DESC    = 94  # Application description
APPLICATION_TAG     = 95  # Application tag
APPLICATION_NAME    = 96  # Application name
postipDiffServCodePoint = 98  # DSCP at egress
replication_factor  = 99  # Multicast replication factor

# ---------------------------------------------------------------------------
# Human-readable name map (for logging/debugging)
# ---------------------------------------------------------------------------

FIELD_NAMES: Dict[int, str] = {
    IN_BYTES: 'IN_BYTES',
    IN_PKTS: 'IN_PKTS',
    FLOWS: 'FLOWS',
    PROTOCOL: 'PROTOCOL',
    SRC_TOS: 'SRC_TOS',
    TCP_FLAGS: 'TCP_FLAGS',
    L4_SRC_PORT: 'L4_SRC_PORT',
    IPV4_SRC_ADDR: 'IPV4_SRC_ADDR',
    SRC_MASK: 'SRC_MASK',
    INPUT_SNMP: 'INPUT_SNMP',
    L4_DST_PORT: 'L4_DST_PORT',
    IPV4_DST_ADDR: 'IPV4_DST_ADDR',
    DST_MASK: 'DST_MASK',
    OUTPUT_SNMP: 'OUTPUT_SNMP',
    IPV4_NEXT_HOP: 'IPV4_NEXT_HOP',
    SRC_AS: 'SRC_AS',
    DST_AS: 'DST_AS',
    LAST_SWITCHED: 'LAST_SWITCHED',
    FIRST_SWITCHED: 'FIRST_SWITCHED',
    OUT_BYTES: 'OUT_BYTES',
    OUT_PKTS: 'OUT_PKTS',
    IPV4_SRC_PREFIX: 'IPV4_SRC_PREFIX',
    IPV4_DST_PREFIX: 'IPV4_DST_PREFIX',
    SRC_VLAN: 'SRC_VLAN',
    DST_VLAN: 'DST_VLAN',
    DIRECTION: 'DIRECTION',
}

# ---------------------------------------------------------------------------
# Field length defaults (bytes) for common types
# ---------------------------------------------------------------------------

DEFAULT_FIELD_LENGTHS: Dict[int, int] = {
    IN_BYTES:           4,
    IN_PKTS:            4,
    FLOWS:              4,
    PROTOCOL:           1,
    SRC_TOS:            1,
    TCP_FLAGS:          1,
    L4_SRC_PORT:        2,
    IPV4_SRC_ADDR:      4,
    SRC_MASK:           1,
    INPUT_SNMP:         2,
    L4_DST_PORT:        2,
    IPV4_DST_ADDR:      4,
    DST_MASK:           1,
    OUTPUT_SNMP:        2,
    IPV4_NEXT_HOP:      4,
    SRC_AS:             4,
    DST_AS:             4,
    LAST_SWITCHED:      4,
    FIRST_SWITCHED:     4,
    OUT_BYTES:          4,
    OUT_PKTS:           4,
    SRC_VLAN:           2,
    DST_VLAN:           2,
    IP_PROTOCOL_VERSION: 1,
    DIRECTION:          1,
    FRAGMENT_OFFSET:    2,
    FORWARDING_STATUS:  1,
}

# NetFlow v9 version number
NETFLOW_V9_VERSION = 9

# Special flowset IDs
FLOWSET_ID_TEMPLATE = 0   # Template FlowSet
FLOWSET_ID_OPTIONS  = 1   # Options Template FlowSet
# Data FlowSet IDs are >= 256
FLOWSET_ID_DATA_MIN = 256
