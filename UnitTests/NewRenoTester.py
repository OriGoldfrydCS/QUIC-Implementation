import unittest
from NewReno import NewReno
from Utils import MAX_PACKET_SIZE
import time


class TestNewReno(unittest.TestCase):
    """
    Unit tests for the NewReno congestion control algorithm.

    This class contains unit tests to verify the correct implementation of the NewReno algorithm.
    Each test case examines a specific functionality or condition within the algorithm.

    Attributes:
        newreno (NewReno): An instance of the NewReno class to be tested.
    """

    def setUp(self):
        """
        Set up the testing environment.

        This method is called before each test to initialize a fresh instance of the NewReno class.
        """
        self.newreno = NewReno()

    def test_initialization(self):
        """
        Test the initialization of the NewReno instance.

        Verifies that all attributes are correctly initialized with their expected default values.
        """
        self.assertEqual(self.newreno.congestion_window, 2 * MAX_PACKET_SIZE)
        self.assertEqual(self.newreno.ssthresh, float('inf'))
        self.assertEqual(self.newreno.acked_bytes, 0)
        self.assertEqual(self.newreno.estimated_rtt, 0.0001 * 1000)
        self.assertEqual(self.newreno.dev_rtt, 0.001 * 1000)
        self.assertFalse(self.newreno.loss_detected)

    def test_on_ack_slow_start(self):
        """
        Test the behavior of the on_ack method during the slow start phase.

        Verifies that the congestion window increases exponentially when the on_ack method is called,
        and that the appropriate value is logged.
        """
        self.newreno.on_ack(acked_bytes=MAX_PACKET_SIZE, rtt=0.02)
        self.assertEqual(self.newreno.congestion_window, 3 * MAX_PACKET_SIZE)
        self.assertIn(3, self.newreno.cwnd_log)

    def test_on_ack_congestion_avoidance(self):
        """
        Test the behavior of the on_ack method during the congestion avoidance phase.

        Verifies that the congestion window increases linearly when the on_ack method is called,
        after the slow start threshold has been reached.
        """
        self.newreno.ssthresh = 2 * MAX_PACKET_SIZE
        self.newreno.congestion_window = 2 * MAX_PACKET_SIZE
        self.newreno.on_ack(acked_bytes=MAX_PACKET_SIZE, rtt=0.02)
        self.assertGreater(self.newreno.congestion_window, 2 * MAX_PACKET_SIZE)

    def test_on_loss(self):
        """
        Test the behavior of the on_loss method.

        Verifies that the congestion window and slow start threshold are correctly adjusted when a packet loss is detected.
        """
        self.newreno.on_ack(acked_bytes=MAX_PACKET_SIZE, rtt=0.02)
        self.newreno.on_loss(time_sent=time.time() - 0.01)
        self.assertEqual(self.newreno.ssthresh, 2 * MAX_PACKET_SIZE)
        self.assertEqual(self.newreno.congestion_window, 2 * MAX_PACKET_SIZE)

    def test_update_rtt(self):
        """
        Test the update_rtt method.

        Verifies that the estimated RTT and RTT deviation are correctly updated using the Exponentially Weighted Moving Average (EWMA).
        """
        self.newreno.update_rtt(50)
        self.assertAlmostEqual(self.newreno.estimated_rtt, 6.3375)
        self.assertAlmostEqual(self.newreno.dev_rtt, 11.665625)

    def test_congestion_state_slow_start(self):
        """
        Test the get_congestion_state method during the slow start phase.

        Verifies that the method returns the correct state (0) when the congestion window is less than the slow start threshold.
        """
        state = self.newreno.get_congestion_state()
        self.assertEqual(state, 0)

    def test_congestion_state_congestion_avoidance(self):
        """
        Test the get_congestion_state method during the congestion avoidance phase.

        Verifies that the method returns the correct state (1) when the congestion window is equal to the slow start threshold.
        """
        self.newreno.congestion_window = self.newreno.ssthresh
        state = self.newreno.get_congestion_state()
        self.assertEqual(state, 1)

    def test_congestion_state_recovery(self):
        """
        Test the get_congestion_state method during the recovery phase.

        Verifies that the method returns the correct state (2) when the sender is in the recovery phase after a packet loss.
        """
        self.newreno.recovery_start_time = time.time()
        state = self.newreno.get_congestion_state()
        self.assertEqual(state, 2)

    def test_max_ssthresh_tracking(self):
        """
        Test the tracking of the maximum slow start threshold.

        Verifies that the max_ssthresh attribute is correctly updated when a loss occurs and the slow start threshold is adjusted.
        """
        self.newreno.on_loss(time_sent=time.time())
        self.assertEqual(self.newreno.max_ssthresh, 2 * MAX_PACKET_SIZE)

    def test_loss_detection(self):
        """
        Test the detection of packet loss.

        Verifies that the loss_detected attribute is set to True when a loss is detected by the on_loss method.
        """
        self.newreno.on_loss(time_sent=time.time())
        self.assertTrue(self.newreno.loss_detected)

if __name__ == '__main__':
    unittest.main()
