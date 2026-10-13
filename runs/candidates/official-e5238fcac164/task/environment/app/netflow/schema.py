"""
NetFlow v9 field type constants (RFC 3954 Section 8).

Only the field types used by the settlement service are listed here;
the full RFC defines many more. All values are integers matching the
field type IDs encoded in NetFlow v9 template flowsets.
"""

# Flowset IDs
TEMPLATE_FLOWSET_ID = 0      # Template flowset identifier
OPTIONS_FLOWSET_ID = 1       # Options template flowset identifier
DATA_FLOWSET_ID_MIN = 256    # Data flowsets use IDs >= 256

# Packet header sizes (bytes)
PACKET_HEADER_SIZE = 20      # Version + Count + Uptime + UnixSecs + Seq + SrcId
FLOWSET_HEADER_SIZE = 4      # FlowsetID + Length
TEMPLATE_RECORD_HEADER_SIZE = 4  # TemplateID + FieldCount
TEMPLATE_FIELD_SIZE = 4     # FieldType + FieldLength

# -----------------------------------------------------------------------
# Commonly used NetFlow v9 field type IDs
# -----------------------------------------------------------------------

IN_BYTES = 1                # Byte count for the flow
IN_PKTS = 2                 # Packet count for the flow
FLOWS = 3                   # Number of flows represented
PROTOCOL = 4                # IP protocol (TCP=6, UDP=17, etc.)
SRC_TOS = 5                 # IP Type of Service byte (contains DSCP in high 6 bits)
TCP_FLAGS = 6               # TCP flags (OR of all TCP flags in flow)
L4_SRC_PORT = 7             # Layer 4 source port
IPV4_SRC_ADDR = 8           # IPv4 source address (4 bytes)
SRC_MASK = 9                # Source address prefix mask
INPUT_SNMP = 10             # Input SNMP interface index
L4_DST_PORT = 11            # Layer 4 destination port
IPV4_DST_ADDR = 12          # IPv4 destination address (4 bytes)
DST_MASK = 13               # Destination address prefix mask
OUTPUT_SNMP = 14            # Output SNMP interface index
IPV4_NEXT_HOP = 15          # IPv4 address of next-hop router
SRC_AS = 16                 # Source BGP autonomous system number
DST_AS = 17                 # Destination BGP autonomous system number
BGP_IPV4_NEXT_HOP = 18      # BGP next-hop address
MUL_DST_PKTS = 19           # IP multicast destination packet count
MUL_DST_BYTES = 20          # IP multicast destination byte count
LAST_SWITCHED = 21          # sysUptime at which the last packet was switched
FIRST_SWITCHED = 22         # sysUptime at which the first packet was switched
OUT_BYTES = 23              # Outgoing byte count
OUT_PKTS = 24               # Outgoing packet count
MIN_PKT_LNGTH = 25          # Minimum IP packet length on incoming packets
MAX_PKT_LNGTH = 26          # Maximum IP packet length on incoming packets
IPV6_SRC_ADDR = 27          # IPv6 source address (16 bytes)
IPV6_DST_ADDR = 28          # IPv6 destination address (16 bytes)
IPV6_SRC_MASK = 29          # IPv6 source prefix length
IPV6_DST_MASK = 30          # IPv6 destination prefix length
IPV6_FLOW_LABEL = 31        # IPv6 flow label
ICMP_TYPE = 32              # ICMP type * 256 + ICMP code
MUL_IGMP_TYPE = 33          # IGMP type
SAMPLING_INTERVAL = 34      # Sampling interval if sampled NetFlow
SAMPLING_ALGORITHM = 35     # Sampling algorithm
FLOW_ACTIVE_TIMEOUT = 36    # Active flow timeout in seconds
FLOW_INACTIVE_TIMEOUT = 37  # Inactive flow timeout in seconds
ENGINE_TYPE = 38             # Aggregation engine type
ENGINE_ID = 39               # Aggregation engine ID
TOTAL_BYTES_EXP = 40        # Total bytes exported
TOTAL_PKTS_EXP = 41         # Total packets exported
TOTAL_FLOWS_EXP = 42        # Total flows exported
IPV4_SRC_PREFIX = 44        # IPv4 source address prefix (with mask applied)
IPV4_DST_PREFIX = 45        # IPv4 destination address prefix
MPLS_TOP_LABEL_TYPE = 46    # MPLS top label type
MPLS_TOP_LABEL_IP_ADDR = 47 # MPLS top label IP address
FLOW_SAMPLER_ID = 48        # Flow sampler identifier
FLOW_SAMPLER_MODE = 49      # Flow sampler mode
FLOW_SAMPLER_RANDOM_INTERVAL = 50  # Flow sampler random interval
DST_TOS = 55                # IP ToS of the destination
SRC_MAC = 56                # Source MAC address
DST_MAC = 57                # Destination MAC address
SRC_VLAN = 58               # Virtual LAN identifier of source
DST_VLAN = 59               # Virtual LAN identifier of destination
IP_PROTOCOL_VERSION = 60    # IP protocol version (4 or 6)
DIRECTION = 61              # Flow direction (0=ingress, 1=egress)
IPV6_NEXT_HOP = 62          # IPv6 next-hop address
BGP_IPV6_NEXT_HOP = 63      # BGP IPv6 next-hop address
IPV6_OPTION_HEADERS = 64    # IPv6 option headers bitmap
MPLS_LABEL_1 = 70           # MPLS label 1
MPLS_LABEL_2 = 71           # MPLS label 2
MPLS_LABEL_3 = 72           # MPLS label 3
MPLS_LABEL_4 = 73           # MPLS label 4
MPLS_LABEL_5 = 74           # MPLS label 5
MPLS_LABEL_6 = 75           # MPLS label 6
MPLS_LABEL_7 = 76           # MPLS label 7
MPLS_LABEL_8 = 77           # MPLS label 8
MPLS_LABEL_9 = 78           # MPLS label 9
MPLS_LABEL_10 = 79          # MPLS label 10
IN_DST_MAC = 80             # Incoming destination MAC address
OUT_SRC_MAC = 81            # Outgoing source MAC address
IF_NAME = 82                # Short name of input/output interface
IF_DESC = 83                # Description of interface
SAMPLER_NAME = 84           # Name of the flow sampler
IN_PERMANENT_BYTES = 85     # Running byte counter for permanent flows
IN_PERMANENT_PKTS = 86      # Running packet counter for permanent flows
FRAGMENT_OFFSET = 88        # Fragment offset
FORWARDING_STATUS = 89      # Forwarding status
MPLS_PAL_RD = 90            # MPLS PAL Route Distinguisher
MPLS_PREFIX_LEN = 91        # Number of consecutive bits in the MPLS prefix
SRC_TRAFFIC_INDEX = 92      # BGP Policy Accounting source traffic index
DST_TRAFFIC_INDEX = 93      # BGP Policy Accounting destination traffic index
APPLICATION_DESCRIPTION = 94  # Application description string
APPLICATION_TAG = 95        # 8-bit classification engine ID + n-bit tag
APPLICATION_NAME = 96       # Application name string
POST_IP_DIFF_SERV_CODE_POINT = 98  # Post-NAT DSCP value
REPLICATION_FACTOR = 99     # Multicast replication factor

# DSCP-related aliases for clarity in the settlement pipeline
DSCP_FIELD = SRC_TOS        # Settlement pipeline reads DSCP from ToS byte
