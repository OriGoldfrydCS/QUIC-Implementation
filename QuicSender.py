import math
import socket
import random
import matplotlib
import matplotlib.pyplot as plt
import os
from NewReno import *
import string


class QuicSender:
    """
    QUIC sender that simulates packet sending and receiving with congestion control.

    Attributes:
        sender_port (int): The sender's port for establishing the connection.
        congestion_control (NewReno): Instance of the NewReno congestion control algorithm.
        max_packet_size (int): Maximum packet size for transmission.
        packet_sent (dict): Dictionary mapping packet IDs to their send times.
        packet_times (dict): Dictionary mapping packet IDs to their Round-Trip Times (RTTs).
        global_start_time (float): Timestamp when the first packet was sent.
        rtt_times (list): List of relative times for RTT logging.
        total_data_passed (list): List of total data passed in each simulation round.
        results_dir (str): Directory where simulation results will be saved.
    """

    def __init__(self, sender_port, is_test=False):
        """
        Initializes the QUIC sender with a specified port.
        The NewReno congestion control algorithm is initialized in that method.

        Parameters:
            sender_port (int): The port number on which the sender will communicate.
        """
        self.sender_port = sender_port
        self.max_packet_size = MAX_PACKET_SIZE
        self.total_data_passed = []
        self.is_test = is_test

        # Create a central directory for all rounds of simulation.
        if not is_test:
            self.results_dir = "simulation_results"
            if not os.path.exists(self.results_dir):
                os.makedirs(self.results_dir)

    def start_sender(self):
        """
        Initializes the sender's socket, binds it to the specified port, and waits for the receiver to connect.

        This method sets up the sender to listen for incoming connection requests from the receiver.
        Once a connection is established, it prepares to send data.
        """
        self.sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sender_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print("Sender listening on port", self.sender_port)
        self.sender_socket.bind(('127.0.0.1', self.sender_port))

        # The sender continuously listens for incoming data from the receiver.
        while True:

            # The sender's socket is waiting to receive data. It captures the data received as well as the receiver's
            # address (IP and port), that returned as a tuple.
            data, self.Receiver_address = self.sender_socket.recvfrom(MAX_BUFFER_SIZE)
            if data:
                print("Receiver connected, beginning to send file...")
                return

    def reset(self):
        """
        Resets the state of the QUIC sender for a new simulation round.

        This method initializes the congestion control algorithm, clears previous packet logs,
        and prepares the sender for a new round of packet transmission.

        Key actions in this method:
        - Initializes a new instance of the NewReno congestion control algorithm.
        - Clears logs of sent packets and their respective round-trip times (RTTs).
        - Resets global time tracking to ensure accurate time measurement in a new round.
        - Prepares lists for storing RTT times to be used for analysis.
        """
        self.congestion_control = NewReno()  # Initialize a new instance of the NewReno congestion control algorithm.
        self.packet_sent = {}  # Clear the dictionary that stores the send times of packets.
        self.packet_times = {}  # Clear the dictionary that stores RTT (Round-Trip Time) measurements for each packet.
        self.global_start_time = None  # Reset the global start time (will be initialized when the 1st packet is sent).
        self.rtt_times = []  # Clear the list of RTT times, which logs the time intervals for RTT measurements.

    def send_packet(self, packet):
        """
        Sends a packet to the receiver with a unique ID and records its send time.

        Parameters:
            packet (bytes): The packet data to send. The first 8 bytes of the packet are used to extract the packet ID.

        Returns:
            float: The send time of the packet, which is recorded when the packet is sent.
        """

        # Record the exact time when the packet is being sent.
        # This timestamp will be used to calculate RTT when the acknowledgment is received.
        send_time = time.time()

        if self.global_start_time is None:
            self.global_start_time = send_time  # Set global start time on first send.
        self.sender_socket.sendto(packet, self.Receiver_address)  # Send the packet to the receiver.

        # Extract the packet ID from the first 8 bytes of the packet (for the next step).
        packet_id = int(packet[:8].decode().strip())

        # Record the send time of the packet, associating the packet ID with the send time.
        # This dictionary will be used later to calculate the RTT when an acknowledgment is received.
        self.packet_sent[packet_id] = send_time

        return send_time

    def receive_ack(self):
        """
        Receives an ACK packet from the receiver.

        Returns:
            tuple: The ID of the acknowledged packet and the receiving time.
        """

        ack_data, _ = self.sender_socket.recvfrom(self.max_packet_size)  # Waits to receive an ACK from the receiver.
        acked_packet_id = int(ack_data.decode().strip())  # Extract the ACK'ed packet ID from the received data.
        receive_time = time.time()  # Record the time when the ACK was received.
        return acked_packet_id, receive_time  # Return the packet ID and receive time.

    def simulate(self, num_packets):
        """
        Simulates the process of sending and receiving packets with congestion control.

        Parameters:
            num_packets (int): The total number of packets to send in the simulation.
        """
        self.sender_socket.settimeout(0.75)  # Set a timeout on the socket if no ACK is received within 0.75 seconds.
        send_again = True  # A flag to determine whether to continue with another simulation round.
        round_index = 0  # Track the index of the simulation round.

        # The main loop
        while send_again:
            self.reset()  # Reset the state for a new round, clearing packet logs and initializing congestion control.
            self.start_sending_initial_packet()  # Send an initial packet to signify the start of the transmission.

            packets_data = self.create_all_content(num_packets)  # Prepare content for packets to be sent.
            packet_id = 1  # Start with the first packet
            loss_timestamps = []  # List to track the timestamps of packet loss events.
            acked_packets = set()  # Set to track all the acknowledged packet IDs.
            sent_packets = 0  # Counter for the number of packets sent.

            # Secondary loop
            while packet_id <= num_packets:

                # Send packets in batches according to the current congestion window size.
                packets_in_window, packet_id, sent_packets = self.send_packets_in_window(packet_id, packets_data,
                                                                                         sent_packets, num_packets)
                # Flag to detect persistent congestion.
                persistent_congestion = False

                try:
                    # Attempt to receive ACKs for the packets sent in the current window.
                    for _ in range(packets_in_window):
                        acked_packet_id, ack_time = self.receive_ack()  # Receive the ACK and its reception time.

                        # Calculate the RTT by subtracting the packet's send time from its ACK time.
                        rtt = ack_time - self.packet_sent[acked_packet_id]

                        # Store the RTT (converted to milliseconds) for the acknowledged packet.
                        self.packet_times[acked_packet_id] = rtt * 1000

                        # Log the relative time from the start of the simulation for this packet.
                        self.rtt_times.append(ack_time - self.global_start_time)

                        # Notify NewReno that a packet has been acknowledged.
                        self.congestion_control.on_ack(self.max_packet_size, rtt)

                        # Add the acknowledged packet ID to the set of acknowledged packets.
                        acked_packets.add(acked_packet_id)

                # If timeout occurs (no ACK received within 0.75 seconds), we assume that the packet lost.
                except socket.timeout:
                    current_time = time.time()  # Record the current time of the loss event.
                    loss_timestamps.append(current_time)

                    # Check for persistent congestion by calculating RTT thresholds.
                    rtt_threshold = self.congestion_control.estimated_rtt + (4 * self.congestion_control.dev_rtt) * 2
                    congestion_period = rtt_threshold

                    # If two loss events happen check the next condition
                    if len(loss_timestamps) >= 2:

                        # If the loss occur: (a) within a short period; and
                        # (b) no packets in the window are acknowledged - mark this as persistent congestion.
                        if loss_timestamps[-1] - loss_timestamps[-2] < congestion_period and \
                                all(pkt not in acked_packets for pkt in
                                    range(packet_id - packets_in_window, packet_id)):
                            persistent_congestion = True
                            loss_timestamps = []  # Reset loss timestamps after detection.

                    # Notify NewReno of the packet loss, with information about congestion.
                    self.congestion_control.on_loss(current_time, is_persistent_congestion=persistent_congestion)

            # Calculate the total data successfully sent (based on acknowledged packets).
            actual_sent_packets = len(acked_packets)
            total_data = actual_sent_packets * self.max_packet_size
            self.total_data_passed.append(total_data)

            # Print the dictionaries and values after the simulation round (for debug)
            # print("Packet Sent Dictionary: ", self.packet_sent)
            # print("Packet Times Dictionary (RTTs): ", self.packet_times)
            # print("Global Start Time: ", self.global_start_time)
            # print("RTT Times List: ", self.rtt_times)

            # Send an end-of-file (EOF) packet to indicate that all packets have been sent.
            packet_id_encoded = str(-1).zfill(8).encode()  # EOF packet ID is encoded as -1.
            end_packet = packet_id_encoded + "EOF".encode()  # Add EOF message to the packet
            self.sender_socket.sendto(end_packet, self.Receiver_address) # Send the EOF packet to the receiver.

            print("Transfer complete")

            if not self.is_test:
                print("Saving outputs...")

                # Create a subdirectory for this round.
                round_dir = os.path.join(self.results_dir, f"round_{round_index}")
                if not os.path.exists(round_dir):
                    os.makedirs(round_dir)

                # Call plot_results with the round directory.
                self.plot_results(round_dir)

            user_choice = input("Do you want to send again? [Y/n] ")
            send_again = (user_choice != "n")
            if send_again:
                print("Sending the data again...")
                self.clear_socket_buffer()
                time.sleep(0.5)
            round_index += 1

        # After all rounds are complete, close the session.
        self.close_session()

    def close_session(self):
        """
        Closes the sender session by sending a final acknowledgment and closing the socket.

        This method sends an end-of-session packet to the receiver and waits for the acknowledgment before closing the socket.
        """

        # Prepare the end packet by encoding a special packet ID (-2) and adding "END".
        # i.e., -2000000 END.
        packet_id_encoded = str(-2).zfill(8).encode()
        end_packet = packet_id_encoded + "END".encode()
        self.sender_socket.sendto(end_packet, self.Receiver_address)     # Send the end packet to the receiver.
        self.receive_ack()  # Get the acknowledgment from the receiver - ending session.
        print("Sender end.")
        self.sender_socket.close()

    def plot_results(self, round_dir):
        """
        Plots and saves various graphs based on the simulation data.

        Parameters:
            round_dir (str): Directory where the plots will be saved.
        """

        # Prepare the necessary data for plotting.
        packet_numbers, rtt_log, estimated_rtt_log, state_log, min_length, min_rtt, dev_rtt = self.prepare_data()

        # Package the retrieved data into a tuple for easier passing between the plotting methods.
        data = (packet_numbers, rtt_log, estimated_rtt_log, state_log, min_length, min_rtt, dev_rtt)

        # Plot the RTT (Round-Trip Time) over the packet numbers.
        self.plot_rtt_over_packet_number(round_dir, data)

        # Plot RTT with congestion control states.
        self.plot_rtt_with_congestion_states(round_dir, data)

        # Plot the size of the congestion window over time.
        self.plot_congestion_window_size(round_dir, data)

        # Plot the congestion control state over time (e.g., Slow Start, Congestion Avoidance) to visualize
        # how the algorithm transitions between different states during the simulation.
        self.plot_congestion_state(round_dir, data)

    def clear_socket_buffer(self):
        """
        Clears the socket buffer by reading all available data.

        This method is used to ensure that no old or irrelevant data remains in the socket buffer between simulation rounds.
        """
        while True:
            try:
                self.sender_socket.recv(self.max_packet_size)
            except Exception as e:
                break

    def start_sending_initial_packet(self):
        """
        Sends the initial packet to indicate the start of transmission.

        This method sends a special packet with ID 0 to signify the beginning of data transfer.
        """
        packet_id_encoded = str(0).zfill(8).encode()  # Firstly, the ID for the initial packet is set to '00000000'.
        start_packet = packet_id_encoded + "S".encode()  # Create the initial packet by appending the letter 'S'
        # (for Start) to the encoded packet ID, i.e. '00000000S'.
        self.sender_socket.sendto(start_packet, self.Receiver_address)  # Send the initial packet to the receiver

    def send_packets_in_window(self, packet_id, packets_data, sent_packets, num_packets):
        """
        Sends packets within the current congestion window.

        Parameters:
            packet_id (int): The ID of the packet to send.
            packets_data (list): List of all packet contents to be sent.
            sent_packets (int): The number of packets already sent.
            num_packets (int): The total number of packets to send.

        Returns:
            tuple: Number of packets sent in the current window, the next packet ID, and the total sent packets.
        """

        # Calculate how many packets can be sent within the current congestion window.
        # The congestion window size is divided by the maximum packet size to determine the number of packets.
        packets_in_window = self.congestion_control.congestion_window // self.max_packet_size

        # Loop over the number of packets allowed by the congestion window size.
        for _ in range(packets_in_window):

            # Check if the packet ID exceeds the total number of packets to be sent.
            # If it does, stop sending further packets (end of transmission).
            if packet_id > num_packets:
                break

            # Remove the first piece of data (content) from the packets_data list to send.
            content = packets_data.pop(0)

            # Encode the packet ID as an 8-character, zero-padded string, and convert it to bytes.
            packet_id_encoded = str(packet_id).zfill(8).encode()

            # Construct the final packet by appending the content data to the encoded packet ID.
            # The packet format will look like: packet_id + content
            packet = packet_id_encoded + content.encode()

            # Send the constructed packet using the send_packet method.
            self.send_packet(packet)

            # Increment the count of sent packets  and the packet ID for the next packet to be sent.
            sent_packets += 1
            packet_id += 1

        # Return the number of packets sent in this window, the next packet ID to be sent, and the total sent packets.
        return packets_in_window, packet_id, sent_packets

    def prepare_data(self):
        """
        Prepares the data needed for plotting the results of the simulation.

        Returns:
            tuple: Various logs and measurements required for plotting.
        """

        # Extract the RTT for each packet. The RTT is stored in 'self.packet_times'.
        # The list comprehension ensures that only packet IDs which exist in the 'packet_times' dictionary are included.
        # The RTT values are taken for all packets up to the maximum packet ID.
        rtt_log = [self.packet_times[i] for i in range(max(self.packet_times.keys()) + 1) if i in self.packet_times]

        # Determine the minimum length of the logs. This ensures that all logs have the same length for
        # consistent plotting. We take the minimum of the lengths of several logs:
        # RTT log, congestion window log, state log, and estimated RTT log.
        min_length = min(len(rtt_log),
                         len(self.congestion_control.cwnd_log),
                         len(self.congestion_control.state_log),
                         len(self.congestion_control.estimated_rtt_log))

        # Create a list of packet numbers for plotting (from 1 to min_length).
        packet_numbers = list(range(1, min_length + 1))

        # Cut the RTT log, the estimated RTT log and the state log (which tracks the congestion control states)
        # to match the minimum length, ensuring that the logs are aligned.
        rtt_log = rtt_log[:min_length]
        estimated_rtt_log = self.congestion_control.estimated_rtt_log[:min_length]
        state_log = self.congestion_control.state_log[:min_length]

        # Compute the minimum RTT observed over time.
        # If there are no RTT logs, return 0 as the default value.
        min_rtt = self.get_min_over_time(rtt_log) if rtt_log else 0

        # Cut the RTT variance log (which tracks the deviation of RTT) to match the minimum length.
        dev_rtt = self.congestion_control.rtt_var_log[:min_length]

        # Return the prepared data as a tuple: packet numbers, RTT log, estimated RTT log, state log,
        # the minimum length of the logs, the minimum RTT, and the RTT deviation log.
        return packet_numbers, rtt_log, estimated_rtt_log, state_log, min_length, min_rtt, dev_rtt

    def get_min_over_time(self, rtt_log):
        """
        Computes the minimum RTT observed over time.

        Parameters:
            rtt_log (list): List of RTTs logged during the simulation.

        Returns:
            list: The minimum RTT observed at each point in time.
        """
        out = []     # Initialize an empty list 'out' to store the minimum RTT observed at each point.
        min_rtt = math.inf      # Initialize 'min_rtt' with the maximum possible value (infinity).

        # Iterate through each RTT value in the 'rtt_log' list.
        for rtt in rtt_log:

            # If the current RTT is smaller than the current 'min_rtt', update 'min_rtt' to this RTT.
            if rtt < min_rtt:
                min_rtt = rtt

            # Append the current minimum RTT (min_rtt) to the 'out' list.
            # This will build a list where each element represents the smallest RTT observed up to that point in time.
            out.append(min_rtt)
        return out

    def plot_rtt_over_packet_number(self, round_dir, data: tuple, show_plot=True):
        """
        Plots the RTT over the number of packets sent and saves the figure.

        Parameters:
            round_dir (str): Directory where the plot will be saved.
            data (tuple): Data required for plotting.
            show_plot (bool): Whether to display the plot interactively.
        """
        packet_numbers, rtt_log, estimated_rtt_log, _, _, min_rtt, dev_rtt = data  # consider only these values
        plt.figure(figsize=(10, 5))
        plt.plot(packet_numbers, rtt_log, label='RTT', marker='o', linestyle='-', alpha=0.5)
        plt.plot(packet_numbers, estimated_rtt_log, label='Estimated RTT', linestyle='--', color='black')
        plt.plot(packet_numbers, min_rtt, label='Min RTT', linestyle='-', color='darkred')
        plt.plot(packet_numbers, dev_rtt, label='RTT Variance', linestyle='--', color='magenta')
        plt.xlabel('Packet Number')
        plt.ylabel('RTT (Milliseconds)')
        plt.title('RTT Over Packet Number')
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(round_dir, 'rtt_over_packet_number.png'))

        # Check if the matplotlib backend allows interactive plotting. If so, display the plot.
        if matplotlib.get_backend() not in ['agg', 'FigureCanvasAgg']:
            plt.show()

        plt.close()

    def plot_rtt_with_congestion_states(self, round_dir, data, show_plot=True):
        """
        Plots RTT with congestion control states and saves the figure.

        Parameters:
            round_dir (str): Directory where the plot will be saved.
            data (tuple): Data required for plotting.
            show_plot (bool): Whether to display the plot interactively.
        """
        packet_numbers, rtt_log, estimated_rtt_log, state_log, min_length, min_rtt, dev_rtt = data
        colors = ['blue', 'orange', 'green']

        plt.figure(figsize=(10, 5))
        for i in range(min_length):
            plt.scatter(packet_numbers[i], rtt_log[i], color=colors[state_log[i]], alpha=0.5)
        plt.plot(packet_numbers, estimated_rtt_log, label='Estimated RTT', linestyle='--', color='black')
        plt.plot(packet_numbers, dev_rtt, label='RTT Variance', linestyle='--', color='magenta')
        plt.xlabel('Packet Number')
        plt.ylabel('RTT (Milliseconds)')
        plt.title('RTT Over Packet Number with Congestion States')
        handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color, markersize=10) for color in
                   colors]
        handles.append(plt.Line2D([0], [0], color='black', linestyle='--'))
        handles.append(plt.Line2D([0], [0], color='magenta', linestyle='--'))
        plt.legend(handles,
                   ['Slow Start', 'Congestion Avoidance', 'Recovery', 'Estimated RTT', 'RTT Variance'])
        plt.grid(True)
        plt.savefig(os.path.join(round_dir, 'rtt_with_congestion_states.png'))

        if matplotlib.get_backend() not in ['agg', 'FigureCanvasAgg']:
            plt.show()

        plt.close()

    def plot_congestion_window_size(self, round_dir, data, show_plot=True):
        """
        Plots congestion window size over time and saves the figure.

        Parameters:
            round_dir (str): Directory where the plot will be saved.
            data (tuple): Data required for plotting.
            show_plot (bool): Whether to display the plot interactively.
        """
        packet_numbers, _, _, _, min_length, _, _ = data

        plt.figure(figsize=(10, 5))
        plt.plot(packet_numbers, self.congestion_control.cwnd_log[:min_length], label='Congestion Window Size',
                 marker='o', linestyle='-', color='blue')
        plt.xlabel('Packet Number')
        plt.ylabel('Congestion Window Size')
        plt.title('Congestion Window Over Time')
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(round_dir, 'congestion_window_size.png'))

        if matplotlib.get_backend() not in ['agg', 'FigureCanvasAgg']:
            plt.show()

        plt.close()

    def plot_congestion_state(self, round_dir, data, show_plot=True):
        """
        Plots the congestion control state over time and saves the figure.

        Parameters:
            round_dir (str): Directory where the plot will be saved.
            data (tuple): Data required for plotting.
            show_plot (bool): Whether to display the plot interactively.
        """
        packet_numbers, _, _, state_log, min_length, _, _ = data

        plt.figure(figsize=(10, 5))
        plt.plot(packet_numbers, state_log[:min_length], label='Congestion State', marker='o', linestyle='-',
                 color='green')
        plt.xlabel('Packet Number')
        plt.ylabel('Congestion State')
        plt.title('Congestion State Over Time')
        plt.yticks([0, 1, 2], ['Slow Start', 'Congestion Avoidance', 'Recovery'])
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(round_dir, 'congestion_state.png'))
        if matplotlib.get_backend() not in ['agg', 'FigureCanvasAgg']:
            plt.show()

        plt.close()

    def create_all_content(self, num_packets):
        """
        Creates dummy packet content for simulation.

        Parameters:
            num_packets (int): Number of packets to create.

        Returns:
            list: List of packet contents.
        """
        data = []  # An empty list to store the generated data for each packet.
        for i in range(num_packets):
            # Generate a random string of characters for each packet.
            # The length of the string is (max_packet_size - 8), since the first 8 bytes are for the packet ID.
            curr_data = ''.join(
                random.choices(string.ascii_letters + string.digits, k=self.max_packet_size - 8))

            # Append the generated content to the data list. Each entry corresponds to one packet's data content.
            data.append(curr_data)
        return data


if __name__ == '__main__':
    sender = QuicSender(sender_port=8080)
    sender.start_sender()
    sender.simulate(num_packets=100)
