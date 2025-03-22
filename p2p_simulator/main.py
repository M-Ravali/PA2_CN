"""
Final BitTorrent Simulator with LRF and Tit-for-Tat algorithms
- Saves output to paste.txt for analysis
"""

import random
import time
from collections import defaultdict
import sys
import os

# Set up logging to file
log_file = "paste.txt"

# Clear the log file if it exists
with open(log_file, 'w') as f:
    f.write("BitTorrent Simulator Log\n")
    f.write("======================\n\n")

# Create a custom print function that writes to both console and file
original_print = print
def tee_print(*args, **kwargs):
    # Print to console
    original_print(*args, **kwargs)
    
    # Print to file
    with open(log_file, 'a') as f:
        kwargs['file'] = f
        original_print(*args, **kwargs)

# Replace the built-in print function with our custom function
print = tee_print

class Peer:
    def __init__(self, peer_id, is_seed=False, num_pieces=10):
        self.peer_id = peer_id
        self.is_seed = is_seed
        self.num_pieces = num_pieces
        self.pieces = [is_seed] * num_pieces  # True if we have the piece
        self.connected_peers = {}  # peer_id -> PeerInfo
        self.upload_rates = {}  # peer_id -> upload rate
        self.download_rates = {}  # peer_id -> download rate
        self.piece_rarity = defaultdict(int)  # piece_index -> count
        self.last_optimistic_unchoke_time = 0
        
    def connect_to_peer(self, peer_id, peer_pieces):
        """Connect to another peer and store their bitfield."""
        if peer_id not in self.connected_peers:
            self.connected_peers[peer_id] = {
                'pieces': peer_pieces.copy(),
                'am_interested': False,
                'am_choking': True,  # We start by choking them
                'peer_interested': False,
                'peer_choking': True  # They start by choking us
            }
            # Update piece rarity based on new peer's pieces
            for i, has_piece in enumerate(peer_pieces):
                if has_piece:
                    self.piece_rarity[i] += 1
            
            print(f"Peer {self.peer_id} connected to {peer_id}")
            return True
        return False
    
    def has_piece(self, piece_index):
        """Check if this peer has a specific piece."""
        return self.pieces[piece_index]
    
    def get_missing_pieces(self):
        """Get indices of pieces we don't have."""
        return [i for i, has_piece in enumerate(self.pieces) if not has_piece]
    
    def get_progress(self):
        """Get completion progress as (pieces_completed, total_pieces)."""
        return sum(self.pieces), self.num_pieces
    
    def receive_piece(self, piece_index, from_peer_id):
        """Receive a piece from another peer."""
        if not self.pieces[piece_index]:
            self.pieces[piece_index] = True
            
            # Update download rate statistics
            if from_peer_id not in self.download_rates:
                self.download_rates[from_peer_id] = 0
            self.download_rates[from_peer_id] += 1
            
            print(f"Peer {self.peer_id} received piece {piece_index} from {from_peer_id}")
            
            # Check if we're complete
            if all(self.pieces):
                self.is_seed = True
                print(f"Peer {self.peer_id} is now a seed (has all pieces)")
            
            return True
        return False
    
    def select_piece_to_request(self, peer_id):
        """Select a piece to request using Local Rarest First algorithm."""
        if peer_id not in self.connected_peers:
            return None
            
        peer_info = self.connected_peers[peer_id]
        
        # Get pieces that the peer has and we don't
        candidate_pieces = [
            i for i, (peer_has, i_have) in enumerate(zip(peer_info['pieces'], self.pieces))
            if peer_has and not i_have
        ]
        
        if not candidate_pieces:
            return None
            
        # Sort by rarity (fewest occurrences first)
        candidate_pieces.sort(key=lambda p: self.piece_rarity[p])
        
        # Special case: if we have no pieces, pick a random one
        if sum(self.pieces) == 0:
            return random.choice(candidate_pieces)
            
        # Endgame mode: if we have most pieces, request all missing pieces
        if sum(self.pieces) >= 0.9 * self.num_pieces:
            return candidate_pieces[0]  # Just take the rarest
            
        # Normal mode: use rarest-first
        return candidate_pieces[0]
    
    def unchoke_peer(self, peer_id):
        """Unchoke a peer, allowing them to request pieces."""
        if peer_id in self.connected_peers:
            if self.connected_peers[peer_id]['am_choking']:
                self.connected_peers[peer_id]['am_choking'] = False
                print(f"Peer {self.peer_id} unchoked {peer_id}")
            return True
        return False
    
    def choke_peer(self, peer_id):
        """Choke a peer, preventing them from requesting pieces."""
        if peer_id in self.connected_peers:
            if not self.connected_peers[peer_id]['am_choking']:
                self.connected_peers[peer_id]['am_choking'] = True
                print(f"Peer {self.peer_id} choked {peer_id}")
            return True
        return False
    
    def express_interest(self, peer_id):
        """Express interest in a peer who has pieces we need."""
        if peer_id in self.connected_peers and not self.connected_peers[peer_id]['am_interested']:
            self.connected_peers[peer_id]['am_interested'] = True
            print(f"Peer {self.peer_id} expressed interest in {peer_id}")
            return True
        return False
    
    def set_peer_interested(self, peer_id, interested=True):
        """Set whether another peer is interested in us."""
        if peer_id in self.connected_peers:
            self.connected_peers[peer_id]['peer_interested'] = interested
            if interested:
                print(f"Peer {peer_id} expressed interest in {self.peer_id}")
            else:
                print(f"Peer {peer_id} expressed lack of interest in {self.peer_id}")
            return True
        return False
    
    def set_peer_choking(self, peer_id, choking=True):
        """Set whether another peer is choking us."""
        if peer_id in self.connected_peers:
            self.connected_peers[peer_id]['peer_choking'] = choking
            if choking:
                print(f"Peer {peer_id} choked {self.peer_id}")
            else:
                print(f"Peer {peer_id} unchoked {self.peer_id}")
            return True
        return False
    
    def select_peers_to_unchoke(self, time, max_unchoked=4):
        """Select peers to unchoke using tit-for-tat and optimistic unchoking."""
        # Get interested peers
        interested_peers = [
            pid for pid, info in self.connected_peers.items()
            if info['peer_interested']
        ]
        
        if not interested_peers:
            return []
        
        # For tit-for-tat, sort by download rate
        peers_by_rate = sorted(
            [(pid, self.download_rates.get(pid, 0)) for pid in interested_peers],
            key=lambda x: x[1],
            reverse=True
        )
        
        # Take top peers for normal slots
        peers_to_unchoke = [pid for pid, _ in peers_by_rate[:max_unchoked-1]]
        
        # Optimistic unchoking (every 30 seconds)
        if (time - self.last_optimistic_unchoke_time) >= 30:
            self.last_optimistic_unchoke_time = time
            
            # Find peers not already unchoked
            candidates = [pid for pid in interested_peers if pid not in peers_to_unchoke]
            
            if candidates:
                optimistic_peer = random.choice(candidates)
                peers_to_unchoke.append(optimistic_peer)
                print(f"Peer {self.peer_id} optimistically unchoked {optimistic_peer}")
        
        return peers_to_unchoke

class Simulator:
    def __init__(self, num_seeds=1, num_leechers=5, num_pieces=10):
        self.peers = {}
        self.current_time = 0
        self.num_pieces = num_pieces
        
        # Create seeds
        for i in range(num_seeds):
            peer_id = f"SEED-{i+1}"
            peer = Peer(peer_id, is_seed=True, num_pieces=num_pieces)
            self.peers[peer_id] = peer
        
        # Create leechers
        for i in range(num_leechers):
            peer_id = f"PEER-{i+1}"
            peer = Peer(peer_id, is_seed=False, num_pieces=num_pieces)
            self.peers[peer_id] = peer
    
    def setup_connections(self):
        """Connect peers to each other."""
        print("\nSetting up connections...")
        
        # Each peer connects to every other peer
        peer_ids = list(self.peers.keys())
        for i, peer_id1 in enumerate(peer_ids):
            for peer_id2 in peer_ids[i+1:]:
                peer1 = self.peers[peer_id1]
                peer2 = self.peers[peer_id2]
                
                # Connect peers to each other
                peer1.connect_to_peer(peer_id2, peer2.pieces)
                peer2.connect_to_peer(peer_id1, peer1.pieces)
                
                # If one is a seed, the other expresses interest
                if peer1.is_seed and not peer2.is_seed:
                    peer2.express_interest(peer_id1)
                    peer1.set_peer_interested(peer_id2, True)
                
                if peer2.is_seed and not peer1.is_seed:
                    peer1.express_interest(peer_id2)
                    peer2.set_peer_interested(peer_id1, True)
    
    def run_simulation(self, max_time=100):
        """Run the BitTorrent simulation."""
        self.setup_connections()
        
        print("\nStarting simulation...")
        print(f"Initial state: {sum(1 for p in self.peers.values() if p.is_seed)} seeds, {sum(1 for p in self.peers.values() if not p.is_seed)} leechers")
        
        # Run simulation for max_time steps
        for t in range(1, max_time + 1):
            self.current_time = t
            
            # Step 1: Each peer runs the unchoking algorithm
            for peer_id, peer in self.peers.items():
                # Skip peers with no pieces (they can't upload)
                if not peer.is_seed and sum(peer.pieces) == 0:
                    continue
                
                # Select peers to unchoke
                peers_to_unchoke = peer.select_peers_to_unchoke(t)
                
                # Update choking status
                for other_id in peer.connected_peers:
                    if other_id in peers_to_unchoke:
                        peer.unchoke_peer(other_id)
                        self.peers[other_id].set_peer_choking(peer_id, False)
                    else:
                        peer.choke_peer(other_id)
                        self.peers[other_id].set_peer_choking(peer_id, True)
            
            # Step 2: Each leecher requests pieces
            for peer_id, peer in self.peers.items():
                if peer.is_seed:
                    continue  # Seeds don't need to request pieces
                
                # For each peer that has unchoked us, try to request a piece
                for other_id, info in peer.connected_peers.items():
                    if not info['peer_choking'] and info['am_interested']:
                        # Select a piece using Local Rarest First
                        piece_idx = peer.select_piece_to_request(other_id)
                        
                        if piece_idx is not None:
                            # If the other peer has the piece, receive it
                            other_peer = self.peers[other_id]
                            if other_peer.has_piece(piece_idx):
                                if peer.receive_piece(piece_idx, other_id):
                                    # Update other peers' knowledge of this peer's pieces
                                    for pid in peer.connected_peers:
                                        if pid != other_id:
                                            self.peers[pid].connected_peers[peer_id]['pieces'][piece_idx] = True
                                            self.peers[pid].piece_rarity[piece_idx] += 1
                                    break  # Only download one piece per time step
            
            # Step 3: Update interest based on new pieces
            for peer_id, peer in self.peers.items():
                if peer.is_seed:
                    continue  # Seeds don't need to be interested
                
                # For each connected peer, check if we're still interested
                for other_id, info in peer.connected_peers.items():
                    other_peer = self.peers[other_id]
                    
                    # Check if they have any pieces we need
                    missing_pieces = peer.get_missing_pieces()
                    has_interesting_pieces = any(other_peer.has_piece(i) for i in missing_pieces)
                    
                    # Update interest status
                    if has_interesting_pieces and not info['am_interested']:
                        peer.express_interest(other_id)
                    elif not has_interesting_pieces and info['am_interested']:
                        info['am_interested'] = False  # Express lack of interest
            
            # Print stats periodically
            if t % 10 == 0 or t == 1:
                self.print_stats()
            
            # If all leechers have become seeds, end simulation
            if all(peer.is_seed for peer in self.peers.values()):
                print(f"\nAll peers have completed the download at time {t}")
                break
        
        # Final stats
        print("\nFinal simulation state:")
        self.print_stats()
    
    def print_stats(self):
        """Print the current state of the simulation."""
        print(f"\nTime: {self.current_time}")
        print(f"Seeds: {sum(1 for p in self.peers.values() if p.is_seed)}")
        print(f"Leechers: {sum(1 for p in self.peers.values() if not p.is_seed)}")
        
        # Print progress for each leecher
        leechers = [(p_id, p) for p_id, p in self.peers.items() if not p.is_seed]
        if leechers:
            print("\nLeecher progress:")
            for peer_id, peer in leechers:
                pieces, total = peer.get_progress()
                percentage = (pieces / total) * 100
                print(f"- {peer_id}: {pieces}/{total} pieces ({percentage:.1f}%)")

def main():
    # Create and run simulator
    print("BitTorrent Simulator - Logging to paste.txt")
    sim = Simulator(num_seeds=1, num_leechers=5, num_pieces=10)
    sim.run_simulation(max_time=100)
    
    print("\nSimulation complete!")
    print(f"Output has been saved to {log_file}")

if __name__ == "__main__":
    main()