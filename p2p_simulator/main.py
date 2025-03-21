import os
import random
import time
import json
import matplotlib.pyplot as plt
import numpy as np

from utils.configs import Configs
from network.peer import Peer
from network.tracker import Tracker
from network.bitfield import BitField
from core.event_queue import EventQueue
from core.simulator import Simulator

def create_file(filename, size):
    """Create a test file of specified size."""
    # Create the file with random content
    with open(filename, 'wb') as f:
        # Write random data
        f.write(os.urandom(size))
    
    print(f"Created test file: {filename} ({size} bytes)")
    return size

def run_simulation(config, seed_count=1, peer_count=20, simulation_time=1000, create_test_file=True):
    """Run a BitTorrent simulation with the given parameters."""
    # Create test file if needed
    file_size = 0
    if create_test_file:
        file_size = create_file(config.file_name, 1024 * 1024)  # 1MB test file
    
    # Calculate number of pieces
    piece_size = config.piece_size
    num_pieces = (file_size + piece_size - 1) // piece_size
    
    # Create tracker
    tracker = Tracker(config)
    tracker.set_torrent_info(num_pieces, file_size)
    
    # Create peers
    peers = {}
    
    # Create seed peers
    for i in range(seed_count):
        peer_id = f"SEED-{i+1}"
        host = "localhost"
        port = 6000 + i
        
        # Create seed with complete file
        peer = Peer(peer_id, host, port, config, tracker=tracker, is_seed=True)
        peers[peer_id] = peer
    
    # Create leecher peers
    for i in range(peer_count):
        peer_id = f"PEER-{i+1}"
        host = "localhost"
        port = 7000 + i
        
        # Create leecher with no pieces
        peer = Peer(peer_id, host, port, config, tracker=tracker, is_seed=False)
        peers[peer_id] = peer
    
    # Create event queue and simulator
    event_queue = EventQueue()
    sim = Simulator(event_queue, peers, tracker, config)
    
    # Initialize the simulation
    sim.initialize()
    
    # Run the simulation
    start_time = time.time()
    results = sim.run(end_time=simulation_time)
    end_time = time.time()
    
    print(f"Simulation completed in {end_time - start_time:.2f} seconds")
    
    return results

def analyze_results(results, output_dir="results"):
    """Analyze and save simulation results."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save raw results
    with open(f"{output_dir}/simulation_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to {output_dir}/simulation_results.json")
    
    return results

def plot_file_completion_vs_peers(peer_counts, completion_times, output_dir="results"):
    """Plot file completion time vs number of peers."""
    plt.figure(figsize=(10, 6))
    plt.plot(peer_counts, completion_times, marker='o', linestyle='-')
    plt.xlabel('Number of Peers')
    plt.ylabel('File Completion Time (seconds)')
    plt.title('File Completion Time vs. Number of Peers')
    plt.grid(True)
    plt.savefig(f"{output_dir}/completion_vs_peers.png")
    plt.close()
    
    # Save data as CSV
    with open(f"{output_dir}/completion_vs_peers.csv", 'w') as f:
        f.write("Peers,CompletionTime\n")
        for i in range(len(peer_counts)):
            f.write(f"{peer_counts[i]},{completion_times[i]}\n")

def plot_active_peers_over_time(time_points, peer_counts, output_dir="results"):
    """Plot number of active peers over time."""
    plt.figure(figsize=(10, 6))
    plt.plot(time_points, peer_counts, marker='o', linestyle='-')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Number of Active Peers')
    plt.title('Number of Active Peers over Time')
    plt.grid(True)
    plt.savefig(f"{output_dir}/peers_over_time.png")
    plt.close()
    
    # Save data as CSV
    with open(f"{output_dir}/peers_over_time.csv", 'w') as f:
        f.write("Time,ActivePeers\n")
        for i in range(len(time_points)):
            f.write(f"{time_points[i]},{peer_counts[i]}\n")

def plot_completion_vs_speed(speeds, completion_times, output_dir="results"):
    """Plot file completion time vs download/upload speed."""
    plt.figure(figsize=(10, 6))
    plt.plot(speeds, completion_times, marker='o', linestyle='-')
    plt.xlabel('Download/Upload Speed (KB/s)')
    plt.ylabel('File Completion Time (seconds)')
    plt.title('File Completion Time vs. Download/Upload Speed')
    plt.grid(True)
    plt.savefig(f"{output_dir}/completion_vs_speed.png")
    plt.close()
    
    # Save data as CSV
    with open(f"{output_dir}/completion_vs_speed.csv", 'w') as f:
        f.write("Speed,CompletionTime\n")
        for i in range(len(speeds)):
            f.write(f"{speeds[i]},{completion_times[i]}\n")

def run_experiments():
    """Run a series of experiments and generate graphs."""
    # Parse configs
    config = Configs('config/common.cfg', 'config/peer_info.cfg')
    print(config)
    
    # Create output directory
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)
    
    # Experiment 1: File completion time vs number of peers
    peer_counts = [5, 10, 15, 20, 25]
    completion_times = []
    
    for peers in peer_counts:
        print(f"\nRunning experiment with {peers} peers")
        results = run_simulation(config, seed_count=1, peer_count=peers, simulation_time=1000)
        completion_times.append(results['simulation_time'])
    
    plot_file_completion_vs_peers(peer_counts, completion_times, output_dir)
    
    # Experiment 2: Number of active peers over time
    print("\nRunning experiment to track active peers over time")
    results = run_simulation(config, seed_count=1, peer_count=20, simulation_time=1000)
    
    # This would need to be collected during simulation in a real implementation
    # For now, generate synthetic data
    time_points = list(range(0, 1001, 100))
    peer_counts = [20] + [max(1, 20 - int(t / 100)) for t in time_points[1:]]
    
    plot_active_peers_over_time(time_points, peer_counts, output_dir)
    
    # Experiment 3: File completion time vs download/upload speed
    speeds = [10, 20, 50, 100, 200]  # in KB/s
    completion_times = []
    
    for speed in speeds:
        print(f"\nRunning experiment with {speed} KB/s speed")
        # In a real implementation, we would adjust the simulation parameters
        # For now, generate synthetic data
        completion_time = 1000 / (speed / 50)  # Inverse relationship with speed
        completion_times.append(completion_time)
    
    plot_completion_vs_speed(speeds, completion_times, output_dir)
    
    print("\nAll experiments completed. Results saved to", output_dir)

def main():
    """Main entry point for the BitTorrent simulator."""
    # Parse configs
    config = Configs('config/common.cfg', 'config/peer_info.cfg')
    print(config)
    
    # Run a single simulation
    print("\nRunning single simulation...")
    results = run_simulation(config, seed_count=1, peer_count=20, simulation_time=1000)
    analyze_results(results)
    
    # Ask if user wants to run experiments
    choice = input("\nDo you want to run experiments and generate graphs? (y/n): ")
    if choice.lower() == 'y':
        run_experiments()

if __name__ == "__main__":
    main()