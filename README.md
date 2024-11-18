# QUIC with NewReno Congestion Control

This project is a simulation of the **QUIC protocol** combined with the **NewReno congestion control algorithm**. It emulates a real-world network environment to showcase how data packets are sent, received, acknowledged, and managed under varying network conditions such as delays, packet loss, and congestion. 

## Overview

The QUIC protocol is a transport layer protocol designed to improve the performance of internet applications by reducing latency and increasing throughput. This project implements:
- A **QUIC sender** that transmits packets to a receiver.
- A **QUIC receiver** that acknowledges packets and simulates network conditions like packet loss and delay.
- The **NewReno algorithm**, which is widely used for congestion control, adjusting the sender’s behavior based on acknowledgment patterns and packet loss.

This implementation emphasizes how congestion control algorithms like NewReno can enhance the performance and reliability of QUIC.

---

## Features

### Protocol Simulation
- **Packet Transmission**: The QUIC sender sends data packets over a simulated network, and the receiver acknowledges them.
- **Congestion Control**: The NewReno algorithm dynamically adjusts the congestion window based on network feedback.

### Network Conditions
- **Packet Loss Simulation**: Randomly drop packets based on a configurable probability.
- **Variable Delays**: Simulate normal and extended delays to mimic real-world networks.
- **Persistent Congestion Detection**: Handle prolonged packet loss scenarios.

### Performance Analysis
- **RTT Tracking**: Measure and log the round-trip time (RTT) for every packet.
- **Congestion State Logging**: Record transitions between Slow Start, Congestion Avoidance, and Recovery phases.
- **Graphical Visualization**: Generate plots for RTT trends, congestion window size, and state transitions.

---

## File Descriptions

### Core Files
- **`NewReno.py`**:
  - Implements the NewReno congestion control algorithm.
  - Tracks congestion window size, RTT, and state transitions.
  - Handles packet loss and recovery phases.

- **`QuicSender.py`**:
  - Simulates the QUIC sender responsible for transmitting data packets.
  - Implements logic for sending, retransmitting packets, and adjusting behavior based on NewReno.

- **`QuicReceiver.py`**:
  - Simulates the QUIC receiver that acknowledges received packets.
  - Introduces artificial packet loss and delays to simulate network variability.

- **`Utils.py`**:
  - Contains constants such as the maximum packet size and initial congestion window size.

### Supporting Logs and Plots
- RTT over time
- Congestion window size dynamics
- Congestion control states (Slow Start, Congestion Avoidance, Recovery)

---

## Setup and Installation

### Requirements
- **Python 3.7+**
- **Libraries**: Install required libraries using:
  ```bash
  pip install matplotlib
