"""
Simple BitTorrent Simulator - A direct, no-frills implementation
"""

import random
import time

class Peer:
    def __init__(self, peer_id, is_seed=False, num_pieces=10):
        self.peer_id = peer_id
        self.is_seed = is_seed
        self.num_pieces = num_pieces
        self.pieces = [is_seed] * num_pieces  # True if we have the piece
        self.connected_peers = []  # List of connected peer IDs
        self.unchoked_peers = []  # List of peers we've unchoked
        self.interested_in = []  # List of peers we're interested in
        
    def connect_to_peer(self, peer_id):
        if peer_id not in self.connected_peers:
            self.connected_peers.append(peer_id)
            print(f"Peer {self.peer_id} connected to {peer_id}")
            return True
        return False
    
    def has_piece(self, piece_index):
        return self.pieces[piece_index]
    
    def get_missing_pieces(self):
        return [i for i, has_piece in enumerate(self.pieces) if not has_piece]
    
    def get_progress(self):
        return sum(self.pieces), self.num_pieces
    
    def receive_piece(self, piece_index):
        if not self.pieces[piece_index]:
            self.pieces[piece_index] = True
            print(f"Peer {self.peer_id} received piece {piece_index}")
            if all(self.pieces):
                self.is_seed = True
                print(f"Peer {self.peer_id} is now a seed (has all pieces)")
            return True
        return False
    
    def has_all_pieces(self):
        return all(self.pieces)
    
    def unchoke_peer(self, peer_id):
        if peer_id not in self.unchoked_peers:
            self.unchoked_peers.append(peer_id)
            print(f"Peer {self.peer_id} unchoked {peer_id}")
            return True
        return False
    
    def express_interest(self, peer_id):
        if peer_id not in self.interested_in:
            self.interested_in.append(peer_id)
            print(f"Peer {self.peer_id} expressed interest in {peer_id}")
            return True
        return False

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
        """Connect leechers to seeds and other peers."""
        # For each leecher
        leechers = [p for p_id, p in self.peers.items() if not p.is_seed]
        seeds = [p for p_id, p in self.peers.items() if p.is_seed]
        
        for leecher in leechers:
            # Connect to all seeds
            for seed in seeds:
                leecher.connect_to_peer(seed.peer_id)
                seed.connect_to_peer(leecher.peer_id)
                
                # Express interest in the seed
                leecher.express_interest(seed.peer_id)
                
                # Seeds unchoke all peers
                seed.unchoke_peer(leecher.peer_id)
            
            # Connect to some other leechers
            other_leechers = [l for l in leechers if l.peer_id != leecher.peer_id]
            for other in random.sample(other_leechers, min(2, len(other_leechers))):
                leecher.connect_to_peer(other.peer_id)
                other.connect_to_peer(leecher.peer_id)
    
    def run_simulation(self, max_time=100):
        """Run the BitTorrent simulation."""
        print("\nSetting up connections...")
        self.setup_connections()
        
        print("\nStarting simulation...")
        print(f"Initial state: {sum(1 for p in self.peers.values() if p.is_seed)} seeds, {sum(1 for p in self.peers.values() if not p.is_seed)} leechers")
        
        # Run the simulation for max_time steps
        for t in range(1, max_time + 1):
            self.current_time = t
            
            # Each leecher tries to download pieces
            for peer_id, peer in self.peers.items():
                # Skip completed peers
                if peer.has_all_pieces():
                    continue
                
                # Try to get a piece from an unchoked peer we're interested in
                for target_id in peer.interested_in:
                    target_peer = self.peers[target_id]
                    
                    # Check if we're unchoked by this peer
                    if peer_id in target_peer.unchoked_peers:
                        # Find a piece we need that the target has
                        missing_pieces = peer.get_missing_pieces()
                        if missing_pieces:
                            random.shuffle(missing_pieces)  # Randomize for now (should be rarest-first)
                            
                            for piece_idx in missing_pieces:
                                if target_peer.has_piece(piece_idx):
                                    # Download the piece
                                    peer.receive_piece(piece_idx)
                                    
                                    # A peer that gets a piece becomes interesting to others
                                    for other_id in peer.connected_peers:
                                        other_peer = self.peers[other_id]
                                        if not other_peer.has_piece(piece_idx):
                                            other_peer.express_interest(peer_id)
                                    
                                    # We only download one piece per time step
                                    break
            
            # Every 10 time steps, print stats
            if t % 10 == 0 or t == 1:
                self.print_stats()
            
            # If all peers are seeds, end simulation
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
    """Run the BitTorrent simulation."""
    # Create and run the simulator
    sim = Simulator(num_seeds=1, num_leechers=5, num_pieces=10)
    sim.run_simulation(max_time=100)

if __name__ == "__main__":
    main()