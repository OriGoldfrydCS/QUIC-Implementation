import socket
import random
import time
import threading
from Utils import *


class QuicReceiver:
    """
    QUIC receiver that simulates packet reception and acknowledgment with varying delays.

    Attributes:
        sender_port (int): The port on which the sender listens.
        sender_ip (str): The IP address of the sender.
        receiver_socket (socket.socket): The UDP socket for communication with the sender.
        received_packets (set): Set of received packet IDs for tracking which packets have been received.
        lock (threading.Lock): Lock for synchronizing access to shared resources like the received_packets set.
        loss_threshold (float): Probability threshold for simulating packet loss.
        delay_threshold (float): Probability threshold for simulating significant delays in packet acknowledgment.
        delay_range (tuple): Range (min, max) for the normal delay simulation in seconds.
    """

    def __init__(self, sender_port: int, sender_ip: str, loss_threshold: float = 0.00, delay_threshold: float = 0.99, delay_range: tuple = (0.01, 0.001), longer_delay =(0.5, 0.15)):
        """
        Initializes the QUIC receiver with a specified port and thresholds for loss and delay.

        Parameters:
            sender_port (int): The port on which the sender will listen.
            sender_ip (str): The IP address of the sender.
            loss_threshold (float): The threshold for simulating packet loss (0 to 1).
            delay_threshold (float): The threshold for simulating significant delays (0 to 1).
            delay_range (tuple): The range (min, max) for simulating normal delays in seconds.
        """
        self.sender_ip = sender_ip
        self.sender_port = sender_port
        self.loss_threshold = loss_threshold  # Probability threshold for packet loss simulation.
        self.delay_threshold = delay_threshold  # Probability for significant delays in packet acknowledgment.
        self.longer_delay = longer_delay  # Range for longer delay simulation.
        self.delay_range = delay_range  # Range for normal packet delays in seconds.
        self.receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create a UDP socket.
        self.receiver_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Set socket options.
        self.received_packets = set()  # Set to store IDs of received packets.
        self.lock = threading.Lock()  # Lock for thread safety (ensure that only one thread can access a shared resource
                                      # (such as variables, data structures, or files) at a time. ).
        print("Start Receiver")

    def start_receiver(self):
        """
        Establishes an initial connection with the sender by sending a CONNECT message.

        This method sends a CONNECT message to the sender and waits for the first packet.
        If the connection fails, it raises an exception and terminates the program.
        """
        try:
            # Display connection information.
            print(f"Trying to connect to IP address: {self.sender_ip} on port {self.sender_port}")

            # Send an initial connection message to the sender.
            self.receiver_socket.sendto(b'CONNECT', (self.sender_ip, self.sender_port)) # Send a connection message.

            # Wait for the sender to send back a response (could be the first packet or acknowledgment of connection).
            data, self.sender_address = self.receiver_socket.recvfrom(MAX_BUFFER_SIZE + 8)
        except Exception as e:
            print("Connection failed, please check the sender's connection.")
            exit(1)

    def receive_data(self, timeout=5):
        """
        Starts the receiver to listen for incoming packets and process them with possible delays and loss.

        Parameters:
            timeout (int): The timeout period (in seconds) for receiving data. Default is 5 seconds.

        This method listens for packets from the sender, processes them with possible delays or loss,
        and sends acknowledgments for received packets. If a packet indicates the end of a transfer,
        the receiver waits for further instructions or closes the session.
        """
        print("Waiting to receive data...")
        self.receiver_socket.settimeout(timeout)  # Set the socket to timeout if no data received within a period.
        fin = False  # A flag to signal the end of the file transfer
        while not fin:
            try:
                # Wait to receive packet data from the sender.
                data, self.sender_address = self.receiver_socket.recvfrom(MAX_BUFFER_SIZE + 8)
                packet_id, data = data[:8], data[8:]  # Split the packet into ID and content.
                packet_id = int(packet_id.decode().strip())  # Decode the packet ID.

                # Check for the end-of-file signal (packet_id == -1).
                if packet_id == -1:
                    print("File transfer complete")
                    self.receiver_socket.settimeout(None)  # Disable socket timeout.
                    print("Waiting for sender response...")

                    data, self.sender_address = self.receiver_socket.recvfrom(MAX_BUFFER_SIZE + 8) # Receive data from the sender.
                    packet_id, data = data[:8], data[8:]  # Extract the packet ID and data.
                    packet_id = int(packet_id.decode().strip())  # Decode the packet ID.

                    # If the packet_id is -2, it indicates the session should close.
                    if packet_id == -2:
                        self.close_session()  # Close the receiver session.
                        return

                    # If not the end of the session, continue and set the timeout again.
                    else:
                        self.receiver_socket.settimeout(timeout)  # Reset the timeout.
                        print("The sender will send the file again.")
                        continue

                print(f"Received packet {packet_id}")

                # Introduce artificial delay to simulate network latency.
                draw = random.random() # Generate a random number for decision-making.

                if draw < self.loss_threshold:  # Simulate packet delays.

                    # Simulate packet delays: if the random draw is greater than the delay threshold, use normal delay.
                    if draw > self.delay_threshold:
                        delay = random.uniform(*self.delay_range)  # Use Normal delay range (by unpacking the tuple).
                    else:
                        delay = random.uniform(*self.longer_delay) # Simulate a longer delay for certain packets.

                # Simulate lost packet: no ACK sent.
                else:
                    continue
                time.sleep(delay)  # Simulate the delay by sleeping the thread.

                # Use thread-safe mechanisms to add the packet ID to the set of received packets.
                with self.lock:
                    self.received_packets.add(packet_id)

                # Send acknowledgment back to the sender in a separate thread for faster response.
                ack_thread = threading.Thread(target=self.send_ack, args=(packet_id, self.sender_address))  # Create a thread for sending the acknowledgment.
                ack_thread.start()  # Start the acknowledgment thread.

            # Raise a timeout exception if no data is received in the specified period.
            except socket.timeout:
                raise socket.timeout("Socket timed out")

    def send_ack(self, packet_id, sender_address):
        """
        Sends an acknowledgment for the received packet.

        Parameters:
            packet_id (int): The ID of the packet being acknowledged.
            sender_address (tuple): The address of the sender.
        """
        ack_packet = self.make_ack_packet(packet_id)  # Create the acknowledgment packet.
        self.receiver_socket.sendto(ack_packet, sender_address)  # Send the acknowledgment packet.

    def make_ack_packet(self, packet_id):
        """
        Creates an acknowledgment packet with the packet ID.

        Parameters:
            packet_id (int): The ID of the packet.

        Returns:
            bytes: The encoded acknowledgment packet.
        """

        # Format the packet ID into a string with padding of zeroes, encode as bytes.
        ack_packet_id_encoded = str(packet_id).zfill(8).encode()
        return ack_packet_id_encoded  # Return the acknowledgment packet.

    def close_session(self):
        """
        Closes the receiver session by sending a final acknowledgment and closing the socket.

        This method is called when the sender indicates the end of the session. It sends a final
        acknowledgment packet and then closes the socket.
        """
        print("Sender sent exit message.")
        self.send_ack(-2, self.sender_address)  # Send the final acknowledgment.
        print("Receiver end.")
        self.receiver_socket.close()  # Close the receiver socket.
        return

# Example usage.
if __name__ == '__main__':
    receiver = QuicReceiver(8080, sender_ip='127.0.0.1', loss_threshold=1, delay_threshold=0.0, delay_range=(0.001, 0.0001), longer_delay =(0.5, 0.15)) # Create a QUIC receiver.
    receiver.start_receiver()  # Start the receiver to establish a connection.
    receiver.receive_data()  # Start the receiver to receive data.
