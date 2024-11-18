import time
from Utils import *


class NewReno:
    """
    Implements the NewReno congestion control algorithm.

    This class manages congestion control using the NewReno algorithm,
    which adjusts the congestion window based on packet acknowledgments
    and losses to optimize data transmission.

    Attributes:
        congestion_window (int): Current size of the congestion window, representing the amount of data
                                 that can be sent without receiving an acknowledgment.
        ssthresh (float): Slow start threshold, which determines the transition point from Slow Start
                          to Congestion Avoidance.
        recovery_start_time (float or None): Timestamp when recovery mode started, used to track
                                             the duration of recovery after packet loss.
        acked_bytes (int): Total number of acknowledged bytes, representing the amount of data
                           successfully received by the peer.
        estimated_rtt (float): Estimated round-trip time (RTT) in milliseconds, updated with each acknowledgment.
        dev_rtt (float): Deviation of the RTT, representing the variability of the RTT measurements.
        loss_detected (bool): Indicates if packet loss has been detected, which affects congestion control decisions.
        cwnd_log (list): Log of congestion window sizes over time, used for analysis and plotting.
        estimated_rtt_log (list): Log of estimated RTT values over time, used for tracking RTT trends.
        state_log (list): Log of congestion control states over time, used to track the algorithm's state transitions.
        max_ssthresh (int): Maximum observed value of the slow start threshold, useful for analyzing the behavior
                            of the algorithm during congestion events.
    """

    def __init__(self):
        # Initial congestion window set to two times the maximum packet size.
        self.congestion_window = 2 * MAX_PACKET_SIZE

        # The slow start threshold, which determines the transition from Slow Start to Congestion Avoidance.
        # Initially, this is set to infinity, meaning there is no threshold at the start.
        self.ssthresh = float('inf')

        # Recovery start time, used to track the period of recovery after a packet loss event.
        # Initially set to None because no packet loss has been detected yet.
        self.recovery_start_time = None

        # Track the total number of acknowledged bytes (successfully received by the peer).
        # This counter starts at 0.
        self.acked_bytes = 0

        # Estimated Round-Trip Time (RTT), used to measure network latency.
        # This value is initialized with a very small default value (0.1) in milliseconds.
        self.estimated_rtt = 0.0001 * 1000

        # RTT deviation measures the variability of RTT samples.
        # This is initialized with a small default value in (0.1) milliseconds.
        self.dev_rtt = 0.001 * 1000

        # Flag to indicate if packet loss has been detected. Initially set to False.
        self.loss_detected = False

        # Logs for tracking congestion window sizes over time.
        self.cwnd_log = []

        # List to log the estimated RTT (smoothed rtt) values over time. It starts with the initial estimated RTT value.
        self.estimated_rtt_log = [self.estimated_rtt]

        # List to log the congestion control states over time.
        # The state can be Slow Start (0), Congestion Avoidance (1), or Recovery (2).
        self.state_log = [0]

        # Track the maximum value of the slow start threshold (ssthresh).
        # We use it for analyzing how the algorithm behaves during congestion.
        self.max_ssthresh = 0

        # Log for RTT variance (deviation) over time.
        self.rtt_var_log = []

    def on_ack(self, acked_bytes: int, rtt: float):
        """
        Handles ACK reception, updating RTT estimates and adjusting the congestion window.

        Parameters:
        - acked_bytes: Number of bytes acknowledged in the received ACK.
        - rtt: Round-trip time sample in seconds.
        """
        self.acked_bytes += acked_bytes    # Add the number of acknowledged bytes to the total acked_bytes count.
        self.update_rtt(rtt * 1000)   # Update the RTT estimates using the new RTT sample (convert RTT to milliseconds).

        # Check if recovery mode has ended.
        # If the recovery start time plus the RTT has passed, exit recovery mode.
        if self.recovery_start_time and time.time() > self.recovery_start_time + rtt:
            self.recovery_start_time = None

        # Congestion control logic.
        # (A) Slow Start phase: Increase the congestion window exponentially.
        if self.congestion_window < self.ssthresh:
            self.congestion_window += MAX_PACKET_SIZE

        # (B) Congestion Avoidance phase: Increase the congestion window linearly.
        else:
            self.congestion_window += (MAX_PACKET_SIZE * acked_bytes) // self.congestion_window
            self.loss_detected = False

        # Log the current congestion window size (in units of MAX_PACKET_SIZE), estimated RTT, and state.
        self.cwnd_log.append(self.congestion_window / MAX_PACKET_SIZE)
        self.estimated_rtt_log.append(self.estimated_rtt)
        self.state_log.append(self.get_congestion_state())

    def on_loss(self, time_sent, is_persistent_congestion=False):
        """
        Handles packet loss, adjusting the congestion window and slow start threshold (ssthresh).

        Parameters:
        - time_sent: Timestamp of when the lost packet was sent.
        - is_persistent_congestion: Boolean indicating if the loss is due to persistent congestion.
        """
        self.loss_detected = True    # Flag that a loss has been detected.

        # If recovery is still ongoing for the lost packet, do not re-enter recovery mode.
        if self.recovery_start_time and self.recovery_start_time >= time_sent:
            self.state_log.append(self.get_congestion_state())
            return

        # Enter recovery mode by recording the current time and updating the slow start threshold.
        self.recovery_start_time = time.time()
        self.ssthresh = max(self.congestion_window // 2, 2 * MAX_PACKET_SIZE)  # Set the slow start threshold (ssthresh)
                                                                               # to half of the current cwnd or two
                                                                               # times the max packet size.
        self.max_ssthresh = self.ssthresh

        # Handle persistent congestion case: reset the congestion window.
        if is_persistent_congestion:
            # Reset congestion window for persistent congestion.
            print("Persistent congestion detected")
            self.congestion_window = 2 * MAX_PACKET_SIZE
            self.recovery_start_time = None
            self.loss_detected = False
        else:
            # For regular packet loss (single loss event), halve the congestion window.
            self.congestion_window = max(2 * MAX_PACKET_SIZE, self.congestion_window // 2)

        # Log the current congestion state (recovery).
        self.state_log.append(self.get_congestion_state())

    def update_rtt(self, rtt_sample):
        """
        Updates the estimated RTT and RTT deviation using Exponentially Weighted Moving Average (EWMA).

        Parameters:
        - rtt_sample: The latest RTT measurement in milliseconds.
        """
        alpha = 0.125   # Alpha is the smoothing factor for RTT estimation (typically 1/8 = 0.125).
        beta = 0.25     # Beta is the smoothing factor for RTT deviation (typically 1/4 = 0.25).

        # Update the estimated RTT using the EWMA formula.
        self.estimated_rtt = (1 - alpha) * self.estimated_rtt + alpha * rtt_sample

        # Update the RTT variance using the absolute difference between the sample and estimated RTT.
        self.dev_rtt = (1 - beta) * self.dev_rtt + beta * abs(rtt_sample - self.estimated_rtt)

        # Log the RTT variance (deviation) over time.
        self.rtt_var_log.append(self.dev_rtt)

    def get_congestion_state(self):
        """
        Determines and returns the current congestion state:
        - 0: Slow Start
        - 1: Congestion Avoidance
        - 2: Recovery
        """

        # If in recovery mode, return state 2.
        if self.recovery_start_time:
            return 2  # Recovery

        # If the congestion window is still smaller than the slow start threshold and no loss has been detected,
        # the state is Slow Start (state 0).
        elif self.congestion_window < self.ssthresh and not self.loss_detected:
            return 0  # Slow Start

        # Otherwise, the state is Congestion Avoidance (state 1).
        else:
            return 1  # Congestion Avoidance
