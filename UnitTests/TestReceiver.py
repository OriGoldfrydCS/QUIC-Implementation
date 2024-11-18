import unittest
from unittest.mock import MagicMock, patch
import socket
from QuicReceiver import QuicReceiver


class TestQuicReceiver(unittest.TestCase):
    """
    Unit tests for the QuicReceiver class, which simulates packet reception and acknowledgment
    in a QUIC protocol implementation.
    """

    def setUp(self):
        """
        Set up the testing environment by initializing an instance of QuicReceiver.

        This method is called before each test to ensure a fresh instance is used.
        """
        self.receiver = QuicReceiver(sender_port=8080, sender_ip='127.0.0.1', loss_threshold=1, delay_threshold=0.0, delay_range=(0.001, 0.0001))

    def tearDown(self):
        """
        Tear down the testing environment by closing the receiver's socket.

        This method is called after each test to ensure resources are properly released.
        """
        if hasattr(self.receiver, 'receiver_socket'):
            try:
                self.receiver.receiver_socket.close()
            except Exception as e:
                print(f"Error closing receiver socket: {e}")
            finally:
                del self.receiver.receiver_socket

    @patch('socket.socket')
    def test_start_receiver_successful(self, mock_socket_class):
        """
        Test that the receiver successfully starts and sends a CONNECT message to the sender.

        Verifies that the receiver sends the correct initial packet and properly receives a response.
        """
        def create_packet(packet_id, content):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded + content.encode()

        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        mock_socket_instance.bind.return_value = None

        mock_socket_instance.recvfrom.side_effect = [
            (b'CONNECT', ('127.0.0.1', 8080)),
            (create_packet(0, 'S'), ('127.0.0.1', 8080))
        ]

        self.receiver.receiver_socket.close()
        self.receiver.receiver_socket = mock_socket_instance

        self.receiver.start_receiver()

        mock_socket_instance.sendto.assert_called_once_with(b'CONNECT', ('127.0.0.1', 8080))
        self.assertEqual(mock_socket_instance.recvfrom.call_count, 1)

        self.receiver.receiver_socket.close()
        del self.receiver.receiver_socket

    @patch('socket.socket')
    def test_receive_data_with_delay(self, mock_socket_class):
        """
        Test that the receiver correctly handles data reception with simulated delays.

        Verifies that the receiver processes incoming packets and correctly acknowledges them.
        """
        def create_packet(packet_id, content):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded + content.encode()

        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        mock_socket_instance.recvfrom.side_effect = [
            (create_packet(1, 'data'), ('127.0.0.1', 8080)),
            (create_packet(-1, ''), ('127.0.0.1', 8080)),
            (create_packet(-2, ''), ('127.0.0.1', 8080))
        ]
        self.receiver.receiver_socket.close()
        self.receiver.receiver_socket = mock_socket_instance
        self.receiver.receive_data()

        self.assertIn(1, self.receiver.received_packets)
        mock_socket_instance.sendto.assert_called()

    @patch('socket.socket')
    def test_packet_loss_simulation(self, mock_socket_class):
        """
        Test that the receiver correctly simulates packet loss based on the loss threshold.

        Verifies that when packet loss is simulated, the receiver does not acknowledge the lost packet.
        """
        def create_packet(packet_id, content):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded + content.encode()

        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        mock_socket_instance.recvfrom.side_effect = [
            (create_packet(1, 'data'), ('127.0.0.1', 8080)),
            (create_packet(-1, ''), ('127.0.0.1', 8080)),
            (create_packet(-2, ''), ('127.0.0.1', 8080))
        ]

        self.receiver.receiver_socket.close()
        self.receiver.receiver_socket = mock_socket_instance

        with patch('random.random', return_value=1.1):  # Simulate packet loss
            self.receiver.receive_data()

        self.assertNotIn(1, self.receiver.received_packets)

    @patch('socket.socket')
    def test_acknowledgement_sent(self, mock_socket_class):
        """
        Test that the receiver sends an acknowledgment for each received packet.

        Verifies that the correct acknowledgment is sent back to the sender for each packet.
        """
        def create_packet(packet_id, content):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded + content.encode()

        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        mock_socket_instance.recvfrom.side_effect = [
            (create_packet(1, 'data'), ('127.0.0.1', 8080)),
            (create_packet(-1, ''), ('127.0.0.1', 8080)),
            (create_packet(-2, ''), ('127.0.0.1', 8080))
        ]

        self.receiver.receiver_socket.close()
        self.receiver.receiver_socket = mock_socket_instance
        self.receiver.receive_data()

        ack_packet = self.receiver.make_ack_packet(1)
        mock_socket_instance.sendto.assert_any_call(ack_packet, ('127.0.0.1', 8080))

    @patch('socket.socket')
    def test_close_session(self, mock_socket_class):
        """
        Test that the receiver correctly handles session closure.

        Verifies that the receiver sends the final acknowledgment and closes the socket properly.
        """
        def create_packet(packet_id, content):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded + content.encode()

        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        mock_socket_instance.recvfrom.side_effect = [
            (create_packet(1, 'data'), ('127.0.0.1', 8080)),
            (create_packet(-1, ''), ('127.0.0.1', 8080)),
            (create_packet(-2, ''), ('127.0.0.1', 8080))
        ]

        self.receiver.receiver_socket.close()  # another time for mock_socket_instance
        self.receiver.receiver_socket = mock_socket_instance
        self.receiver.receive_data()
        self.receiver.close_session()

        ack_packet = self.receiver.make_ack_packet(-2)
        mock_socket_instance.sendto.assert_any_call(ack_packet, ('127.0.0.1', 8080))
        self.assertEqual(mock_socket_instance.close.call_count, 2)

    @patch('socket.socket')
    def test_handle_multiple_packets(self, mock_socket_class):
        """
        Test that the receiver correctly handles the reception of multiple packets.

        Verifies that all received packets are processed and acknowledged in sequence.
        """
        def create_packet(packet_id, content):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded + content.encode()

        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        mock_socket_instance.recvfrom.side_effect = [
            (create_packet(1, 'data'), ('127.0.0.1', 8080)),
            (create_packet(2, 'data'), ('127.0.0.1', 8080)),
            (create_packet(-1, ''), ('127.0.0.1', 8080)),
            (create_packet(-2, ''), ('127.0.0.1', 8080))
        ]

        self.receiver.receiver_socket.close()
        self.receiver.receiver_socket = mock_socket_instance
        self.receiver.receive_data()
        self.receiver.close_session()

        self.assertIn(1, self.receiver.received_packets)
        self.assertIn(2, self.receiver.received_packets)
        mock_socket_instance.sendto.assert_called()

    @patch('socket.socket')
    def test_handle_retransmission_request(self, mock_socket_class):
        """
        Test that the receiver correctly handles retransmission requests.

        Verifies that the receiver processes retransmitted packets and correctly acknowledges them.
        """
        def create_packet(packet_id, content):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded + content.encode()

        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        mock_socket_instance.recvfrom.side_effect = [
            (create_packet(-1, ''), ('127.0.0.1', 8080)),  # EOF
            (create_packet(0, ''), ('127.0.0.1', 8080)),  # send a file
            (create_packet(1, 'data'), ('127.0.0.1', 8080)),  # Retransmitted packet
            (create_packet(-1, ''), ('127.0.0.1', 8080)),
            (create_packet(-2, ''), ('127.0.0.1', 8080))  # End session
        ]

        self.receiver.receiver_socket.close()
        self.receiver.receiver_socket = mock_socket_instance
        self.receiver.receive_data()
        self.receiver.close_session()

        self.assertIn(1, self.receiver.received_packets)
        mock_socket_instance.sendto.assert_called()

    @patch('socket.socket')
    def test_no_packets_received(self, mock_socket_class):
        """
        Test the behavior when no packets are received within the timeout period.

        Verifies that the receiver correctly handles timeouts and does not process any packets.
        """
        mock_socket_instance = MagicMock()
        mock_socket_class.return_value = mock_socket_instance

        mock_socket_instance.recvfrom.side_effect = socket.timeout
        self.receiver.receiver_socket.close()
        self.receiver.receiver_socket = mock_socket_instance

        with self.assertRaises(socket.timeout):
            self.receiver.receive_data(timeout=1)

        self.assertEqual(len(self.receiver.received_packets), 0)

    def test_make_ack_packet(self):
        """
        Test the creation of acknowledgment packets.

        Verifies that the acknowledgment packet is correctly formatted with the given packet ID.
        """
        ack_packet = self.receiver.make_ack_packet(1)
        self.assertEqual(ack_packet, b'00000001')

    @patch('socket.socket')
    def test_simultaneous_packet_reception(self, mock_socket_class):
        """
        Test the receiver's handling of multiple packets arriving simultaneously.

        Verifies that the receiver processes all packets correctly and sends acknowledgments for each.
        """
        def create_packet(packet_id, content):
            packet_id_encoded = str(packet_id).zfill(8).encode()
            return packet_id_encoded + content.encode()

        mock_socket_instance = MagicMock()
        self.receiver.receiver_socket.close()
        mock_socket_class.return_value = mock_socket_instance

        mock_socket_instance.recvfrom.side_effect = [
            (create_packet(0, 'data1'), ('127.0.0.1', 8080)),
            (create_packet(1, 'data1'), ('127.0.0.1', 8080)),
            (create_packet(2, 'data2'), ('127.0.0.1', 8080)),
            (create_packet(3, 'data3'), ('127.0.0.1', 8080)),
            (create_packet(-1, ''), ('127.0.0.1', 8080)),
            (create_packet(-2, ''), ('127.0.0.1', 8080))
        ]

        self.receiver.receiver_socket = mock_socket_instance

        self.receiver.receive_data()

        self.assertIn(1, self.receiver.received_packets)
        self.assertIn(2, self.receiver.received_packets)
        self.assertIn(3, self.receiver.received_packets)
        self.assertEqual(mock_socket_instance.sendto.call_count, 5)  # One for each packet

if __name__ == '__main__':
    unittest.main()
