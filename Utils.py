"""
Constants for the QUIC protocol
"""
# Maximum packet size in bytes, including headers.
MAX_PACKET_SIZE = 1500

# Maximum buffer size for packet data, excluding headers.
MAX_BUFFER_SIZE = MAX_PACKET_SIZE - 8

# Initial congestion window size, set to three times the maximum packet size.
# This is the starting size of the congestion window for the NewReno algorithm.
INITIAL_CONGESTION_WINDOW = 2 * MAX_PACKET_SIZE
