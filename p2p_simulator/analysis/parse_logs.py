"""
BitTorrent Log Parser
Parse simulation logs and generate statistics
"""

import re
import os
import csv
from collections import defaultdict

# Create output directory
output_dir = "log_analysis"
os.makedirs(output_dir, exist_ok=True)

class LogParser:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.stats = {
            'piece_transfers': [],  # List of (time, from_peer, to_peer, piece_index)
            'peer_progress': defaultdict(list),  # peer_id -> [(time, pieces_completed, total)]
            'choke_events': [],  # List of (time, from_peer, to_peer, is_choke)
            'interest_events': []  # List of (time, from_peer, to_peer, is_interested)
        }
        
        # Regular expressions for pattern matching
        self.piece_transfer_pattern = r"Peer (\S+) received piece (\d+) from (\S+)"
        self.progress_pattern = r"- Peer (\S+): (\d+)/(\d+) pieces \(([0-9.]+)%\)"
        self.choke_pattern = r"Peer (\S+) (choked|unchoked) (\S+)"
        self.interest_pattern = r"Peer (\S+) expressed (interest|lack of interest) in (\S+)"
        self.time_pattern = r"Time: (\d+)"
        
        self.current_time = 0
    
    def parse(self):
        """Parse the log file and collect statistics."""
        try:
            with open(self.log_file_path, 'r') as f:
                for line in f:
                    # Check for time markers
                    time_match = re.search(self.time_pattern, line)
                    if time_match:
                        self.current_time = int(time_match.group(1))
                    
                    # Check for piece transfers
                    piece_match = re.search(self.piece_transfer_pattern, line)
                    if piece_match:
                        to_peer = piece_match.group(1)
                        piece_idx = int(piece_match.group(2))
                        from_peer = piece_match.group(3)
                        self.stats['piece_transfers'].append((self.current_time, from_peer, to_peer, piece_idx))
                    
                    # Check for peer progress updates
                    progress_match = re.search(self.progress_pattern, line)
                    if progress_match:
                        peer_id = progress_match.group(1)
                        pieces_completed = int(progress_match.group(2))
                        total_pieces = int(progress_match.group(3))
                        self.stats['peer_progress'][peer_id].append((self.current_time, pieces_completed, total_pieces))
                    
                    # Check for choking events
                    choke_match = re.search(self.choke_pattern, line)
                    if choke_match:
                        from_peer = choke_match.group(1)
                        is_choke = choke_match.group(2) == "choked"
                        to_peer = choke_match.group(3)
                        self.stats['choke_events'].append((self.current_time, from_peer, to_peer, is_choke))
                    
                    # Check for interest events
                    interest_match = re.search(self.interest_pattern, line)
                    if interest_match:
                        from_peer = interest_match.group(1)
                        is_interested = interest_match.group(2) == "interest"
                        to_peer = interest_match.group(3)
                        self.stats['interest_events'].append((self.current_time, from_peer, to_peer, is_interested))
            
            print(f"Successfully parsed log file: {self.log_file_path}")
            return True
        
        except Exception as e:
            print(f"Error parsing log file: {e}")
            return False
    
    def generate_reports(self):
        """Generate CSV reports from the parsed data."""
        # 1. Piece transfers report
        with open(f"{output_dir}/piece_transfers.csv", 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time', 'From Peer', 'To Peer', 'Piece Index'])
            for data in self.stats['piece_transfers']:
                writer.writerow(data)
        
        # 2. Peer progress report
        with open(f"{output_dir}/peer_progress.csv", 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Peer ID', 'Time', 'Pieces Completed', 'Total Pieces', 'Completion %'])
            for peer_id, progress_list in self.stats['peer_progress'].items():
                for time, completed, total in progress_list:
                    percentage = (completed / total) * 100 if total > 0 else 0
                    writer.writerow([peer_id, time, completed, total, f"{percentage:.1f}%"])
        
        # 3. Choking events report
        with open(f"{output_dir}/choke_events.csv", 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time', 'From Peer', 'To Peer', 'Event Type'])
            for time, from_peer, to_peer, is_choke in self.stats['choke_events']:
                event_type = "Choke" if is_choke else "Unchoke"
                writer.writerow([time, from_peer, to_peer, event_type])
        
        # 4. Interest events report
        with open(f"{output_dir}/interest_events.csv", 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Time', 'From Peer', 'To Peer', 'Event Type'])
            for time, from_peer, to_peer, is_interested in self.stats['interest_events']:
                event_type = "Interested" if is_interested else "Not Interested"
                writer.writerow([time, from_peer, to_peer, event_type])
        
        print(f"\nGenerated reports in the '{output_dir}' directory:")
        print(f"  - piece_transfers.csv")
        print(f"  - peer_progress.csv")
        print(f"  - choke_events.csv")
        print(f"  - interest_events.csv")

def main():
    """Main function to parse log file and generate reports."""
    # Use the paste.txt file that contains the simulation output
    log_file_path = "C:/Users/siraj/OneDrive/Documents/GitHub/PA2_CN/paste.txt"
    
    if not os.path.exists(log_file_path):
        print(f"Error: Log file '{log_file_path}' not found.")
        print("Please save your simulation output to 'paste.txt' in the current directory.")
        return
    
    parser = LogParser(log_file_path)
    if parser.parse():
        parser.generate_reports()
        print("\nLog analysis complete. You can use these CSV files.")

if __name__ == "__main__":
    main()