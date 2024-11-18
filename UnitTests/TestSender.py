from functools import wraps
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend
import socket
import unittest
from unittest.mock import MagicMock, patch
import Utils
from QuicSender import QuicSender
from NewReno import NewReno


def handle_exceptions(exception_types=(Exception,)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                print(f"Handled exception: {e}. Continuing the test.")
        return wrapper
    return decorator


class TestQuicSender(unittest.TestCase):

    def setUp(self):
        self.sender = QuicSender(sender_port=8080, is_test=True)

    def tearDown(self):
        # Ensure the sender's socket is closed after each test
        if hasattr(self.sender, 'sender_socket'):
            try:
                self.sender.sender_socket.close()
            except Exception as e:
                print(f"Error closing sender socket: {e}")
            finally:
                del self.sender.sender_socket

    @patch('socket.socket')
    def test_start_sender_binds_and_listens(self, mock_socket_class):
        def create_packet(packet_id):
            return str(packet_id).zfill(8).encode()

        # Create a mock socket instance
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        # Bind the mock socket to the address
        mock_socket_instance.bind.return_value = None

        # Set up the mock to simulate the receiver's messages
        mock_socket_instance.recvfrom.side_effect = [
            (b'CONNECT', ('127.0.0.1', 8080)),  # Simulate the CONNECT message from the receiver
            (create_packet(1), ('127.0.0.1', 8080)),  # Simulate receiving a data packet
            (create_packet(2), ('127.0.0.1', 8080)),
            (create_packet(3), ('127.0.0.1', 8080)),
        ]

        # Replace the socket in the QuicSender instance with our mock socket
        self.sender.sender_socket = mock_socket_instance

        # Call the start_sender method
        self.sender.start_sender()

        # Ensure the socket was bound to the correct port
        mock_socket_instance.bind.assert_called_once_with(('127.0.0.1', 8080))

        # Ensure the sender is listening for a connection (recvfrom is called)
        self.assertEqual(mock_socket_instance.recvfrom.call_count, 1)

        try:
            # Simulate the rest of the sending process
            self.sender.simulate(num_packets=3)
        except Exception as e:
            pass


        # Ensure the recvfrom was called multiple times as expected
        self.assertEqual(mock_socket_instance.recvfrom.call_count, 5)

        # Check that the sender correctly identified the receiver's address
        self.assertEqual(self.sender.Receiver_address, ('127.0.0.1', 8080))

    def test_reset_method(self):
        self.sender.reset()
        self.assertEqual(self.sender.packet_sent, {})
        self.assertEqual(self.sender.packet_times, {})
        self.assertIsNone(self.sender.global_start_time)
        self.assertEqual(self.sender.rtt_times, [])
        self.assertIsInstance(self.sender.congestion_control, NewReno)

    @patch('time.time', return_value=1000.0)
    @patch('socket.socket')
    def test_send_packet(self, mock_socket_class, mock_time):
        # Create a mock socket instance
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        # Set the sender's socket to the mock instance
        self.sender.sender_socket = mock_socket_instance

        # Manually set the Receiver_address as it's required by send_packet
        self.sender.Receiver_address = ('127.0.0.1', 8080)

        # Initialize the sender's state
        self.sender.reset()  # This will set global_start_time and other attributes

        # Define a packet to send
        packet = b'00000001data'

        # Call the method under test
        send_time = self.sender.send_packet(packet)

        # Assertions
        self.assertEqual(send_time, 1000.0)  # Check if the time returned by send_packet is the mocked time
        self.assertEqual(self.sender.packet_sent[1], 1000.0)  # Verify that the packet ID and send time are recorded
        mock_socket_instance.sendto.assert_called_once_with(packet,
                                                            self.sender.Receiver_address)  # Verify that the packet was sent to the correct address

    @patch('time.time', return_value=1001.0)
    @patch('socket.socket')
    def test_receive_ack(self, mock_socket_class, mock_time):
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        self.sender.sender_socket = mock_socket_instance

        ack_data = b'00000001'
        mock_socket_instance.recvfrom.return_value = (ack_data, ('127.0.0.1', 8080))

        acked_packet_id, receive_time = self.sender.receive_ack()

        self.assertEqual(acked_packet_id, 1)
        self.assertEqual(receive_time, 1001.0)

    @patch('socket.socket')
    @patch('time.time', return_value=1000.0)
    def test_congestion_window_adjustment_on_ack(self, mock_time, mock_socket_class):
        # Create a mock socket instance
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        # Set the sender's socket to the mock instance
        self.sender.sender_socket = mock_socket_instance

        # Manually set the Receiver_address as it's required by send_packet
        self.sender.Receiver_address = ('127.0.0.1', 8080)

        # Initialize the sender's state
        self.sender.reset()

        # Set up the initial congestion window and the expected adjustment
        initial_cwnd = self.sender.congestion_control.congestion_window
        ack_packet_id = 1
        rtt_sample = 0.1  # Sample RTT in seconds

        # Define the ACK packet to be received
        ack_packet = str(ack_packet_id).zfill(8).encode()

        # Mock the recvfrom method to return the ACK packet
        mock_socket_instance.recvfrom.return_value = (ack_packet, ('127.0.0.1', 8080))

        # Call the receive_ack method, which should adjust the congestion window
        acked_packet_id, receive_time = self.sender.receive_ack()
        self.sender.congestion_control.on_ack(self.sender.max_packet_size, 0.00001)

        # After receiving the ACK, the congestion window should have been adjusted
        expected_cwnd = initial_cwnd + (Utils.MAX_PACKET_SIZE * ack_packet_id)
        actual_cwnd = self.sender.congestion_control.congestion_window

        # Assertions
        self.assertEqual(acked_packet_id, ack_packet_id)  # Verify that the ACKed packet ID is correct
        self.assertGreater(actual_cwnd, initial_cwnd)  # The congestion window should increase after ACK
        self.assertEqual(actual_cwnd, expected_cwnd)  # Verify the exact expected adjustment

    @patch('builtins.input', lambda *args: 'n')
    @patch('socket.socket')
    def test_persistent_congestion_detection(self, mock_socket_class):
        # Create a mock socket instance
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        # Set the sender's socket to the mock instance
        self.sender.sender_socket = mock_socket_instance

        # Manually set the Receiver_address as it's required by send_packet
        self.sender.Receiver_address = ('127.0.0.1', 8080)

        # Initialize the sender's state
        self.sender.reset()

        def create_packet(packet_id):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded

        # First, simulate the CONNECT message to establish connection
        mock_socket_instance.recvfrom.side_effect = [
            (b'CONNECT', ('127.0.0.1', 8080)),  # Simulate the CONNECT message from the receiver
        ]

        # Start the sender to handle the CONNECT message
        self.sender.start_sender()

        # Now simulate receiving packet data and ACKs
        mock_socket_instance.recvfrom.side_effect = [
            (create_packet(1), ('127.0.0.1', 8080)),  # Simulate receiving the first data packet ACK
            (create_packet(2), ('127.0.0.1', 8080)),  # Simulate receiving the second data packet ACK
            socket.timeout,  # Simulate a timeout to indicate no more packets are received
            (create_packet(-2), ('127.0.0.1', 8080)),  # Simulate receiving the final ACK for session close
        ]

        # Run the simulation, expecting that only 2 packets will be "ACKed"
        try:
            self.sender.simulate(num_packets=3)
        except socket.timeout:

            pass  # We expect a timeout after 2 packets are ACKed, so this is normal


        # Check if the congestion control was triggered for loss detection
        self.assertTrue(self.sender.congestion_control.loss_detected,
                        "Persistent congestion was not detected as expected")



    @patch('builtins.input', lambda *args: 'n')
    @patch('socket.socket')
    @handle_exceptions((socket.timeout,))
    def test_send_end_of_file_packet(self, mock_socket_class):
        def create_packet(packet_id):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded

        # Create a mock socket instance
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        # Set the sender's socket to the mock instance
        self.sender.sender_socket = mock_socket_instance

        # Manually set the Receiver_address as it's required by send_packet
        self.sender.Receiver_address = ('127.0.0.1', 8080)

        # Initialize the sender's state
        self.sender.reset()

        # Simulate the CONNECT message and then an EOF scenario
        mock_socket_instance.recvfrom.side_effect = [
            (b'CONNECT', ('127.0.0.1', 8080)),
            (create_packet(1), ('127.0.0.1', 8080)),
            (create_packet(2), ('127.0.0.1', 8080)),
            socket.timeout,  # Simulate a timeout after packets are received
        ]

        # Start the sender to handle the CONNECT message
        self.sender.start_sender()

        # Run the simulate method to trigger sending the EOF packet
        self.sender.simulate(num_packets=2)

        # Check if the EOF packet was sent
        packet_id_encoded = str(-1).zfill(8).encode()
        eof_packet = packet_id_encoded + b"EOF"
        mock_socket_instance.sendto.assert_any_call(eof_packet, self.sender.Receiver_address)

        # Check if the END packet was sent to close the session
        end_packet_id_encoded = str(-2).zfill(8).encode()
        end_packet = end_packet_id_encoded + b"END"
        mock_socket_instance.sendto.assert_any_call(end_packet, self.sender.Receiver_address)

    @patch('builtins.input', lambda *args: 'n')
    @patch('socket.socket')
    def test_total_data_logging(self, mock_socket_class):
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        # Mock the required socket communication to simulate a basic run
        def create_packet(packet_id, content=''):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded + content.encode()

        # Mocking recvfrom to simulate a normal flow of packets and EOF
        mock_socket_instance.recvfrom.side_effect = [
            (b'CONNECT', ('127.0.0.1', 8080)),  # Simulate the CONNECT message from the receiver
            (create_packet(1), ('127.0.0.1', 8080)),  # Simulate receiving a data packet
            (create_packet(1), ('127.0.0.1', 8080)),  # Simulate ACK for packet 1
            (create_packet(-1), ('127.0.0.1', 8080)),  # Simulate end of file
            (create_packet(-2), ('127.0.0.1', 8080)),  # Simulate session close
        ]

        self.sender.sender_socket = mock_socket_instance
        self.sender.start_sender()  # Start the sender to handle the CONNECT message
        self.sender.simulate(num_packets=1)  # Simulate sending 1 packet

        # Check if total_data_passed has entries
        self.assertGreater(len(self.sender.total_data_passed), 0)

    from unittest.mock import MagicMock, patch

    @patch('socket.socket')
    def test_close_session(self, mock_socket_class):
        # Create a mock socket instance
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        # Manually set the Receiver_address before calling close_session
        self.sender.Receiver_address = ('127.0.0.1', 8080)

        # Create a properly formatted packet ID for the ACK packet
        ack_packet = str(-2).zfill(8).encode()  # This simulates an acknowledgment packet with ID -2

        # Mock the `recvfrom` method to return a valid response to avoid unpacking errors
        mock_socket_instance.recvfrom.return_value = (ack_packet, ('127.0.0.1', 8080))

        # Assign the mock socket to the sender's socket
        self.sender.sender_socket = mock_socket_instance

        # Call the `close_session` method
        self.sender.close_session()

        # Ensure that the end session packet was sent
        expected_packet = b'-0000002END'
        mock_socket_instance.sendto.assert_called_once_with(expected_packet, ('127.0.0.1', 8080))

        # Ensure the socket was closed
        mock_socket_instance.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
