"""
Advanced BitTorrent Simulator with Local Rarest First and Tit-for-Tat algorithms
"""

import random
import time
from collections import defaultdict

class Peer:
    def __init__(self, peer_id, is_seed=False, num_pieces=10):
        self.peer_id = peer_id
        self.is_seed = is_seed
        self.num_pieces = num_pieces
        self.pieces = [is_seed] * num_pieces  # True if we have the piece
        self.connected_peers = {}  # peer_id -> PeerInfo
        self.upload_rates = {}  # peer_id -> upload rate
        self.download_rates = {}  # peer_id -> download rate
        self.max_unchoked_peers = 4  # Standard in BitTorrent
        self.piece_rarity = defaultdict(int)  # piece_index -> count
        self.last_optimistic_unchoke_time = 0
        self.optimistic_unchoke_interval = 30  # seconds
        
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
    
    def upload_piece(self, piece_index, to_peer_id):
        """Upload a piece to another peer."""
        if self.has_piece(piece_index):
            # Update upload rate statistics
            if to_peer_id not in self.upload_rates:
                self.upload_rates[to_peer_id] = 0
            self.upload_rates[to_peer_id] += 1
            
            return True
        return False
    
    def update_peer_pieces(self, peer_id, piece_index, has_piece=True):
        """Update our knowledge of another peer's pieces."""
        if peer_id in self.connected_peers:
            peer_info = self.connected_peers[peer_id]
            
            # Update piece rarity if the peer now has a piece they didn't have before
            if has_piece and not peer_info['pieces'][piece_index]:
                self.piece_rarity[piece_index] += 1
            elif not has_piece and peer_info['pieces'][piece_index]:
                self.piece_rarity[piece_index] -= 1
                
            peer_info['pieces'][piece_index] = has_piece
            
            # Check if we should be interested in this peer
            if not self.is_seed and not self.connected_peers[peer_id]['am_interested']:
                for i, has_p in enumerate(peer_info['pieces']):
                    if has_p and not self.pieces[i]:
                        self.express_interest(peer_id)
                        break
    
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
        # (Random piece for first download is standard in BitTorrent)
        if sum(self.pieces) == 0:
            return random.choice(candidate_pieces)
            
        # Endgame mode: if we have most pieces, request all missing pieces
        if sum(self.pieces) >= 0.9 * self.num_pieces:
            return candidate_pieces[0]  # Just take the rarest
            
        # Normal mode: use rarest-first
        return candidate_pieces[0]
    
    def run_choking_algorithm(self, current_time):
        """Run the choking algorithm (Tit-for-Tat with optimistic unchoking)."""
        # Skip if we're not a seed and have no pieces
        if not self.is_seed and sum(self.pieces) == 0:
            return []
            
        # Get peers who are interested in us
        interested_peers = [
            pid for pid, info in self.connected_peers.items()
            if info['peer_interested']
        ]
        
        if not interested_peers:
            return []
            
        # Choose peers to unchoke based on their upload rates to us (tit-for-tat)
        candidate_peers = [
            (pid, self.download_rates.get(pid, 0))
            for pid in interested_peers
        ]
        
        # Sort by upload rate (highest first)
        candidate_peers.sort(key=lambda x: x[1], reverse=True)
        
        # Select top peers to unchoke
        peers_to_unchoke = [pid for pid, _ in candidate_peers[:self.max_unchoked_peers-1]]
        
        # Optimistic unchoking (every 30 seconds, unchoke a random peer)
        if current_time - self.last_optimistic_unchoke_time >= self.optimistic_unchoke_interval:
            self.last_optimistic_unchoke_time = current_time
            
            # Choose a random peer that's not already going to be unchoked
            choked_interested_peers = [
                pid for pid in interested_peers
                if pid not in peers_to_unchoke
            ]
            
            if choked_interested_peers:
                optimistic_peer = random.choice(choked_interested_peers)
                peers_to_unchoke.append(optimistic_peer)
                print(f"Peer {self.peer_id} optimistically unchoked {optimistic_peer}")
        
        return peers_to_unchoke
    
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
    
    def express_not_interested(self, peer_id):
        """Express lack of interest in a peer."""
        if peer_id in self.connected_peers and self.connected_peers[peer_id]['am_interested']:
            self.connected_peers[peer_id]['am_interested'] = False
            print(f"Peer {self.peer_id} expressed lack of interest in {peer_id}")
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
        """Connect peers to each other and initialize piece knowledge."""
        print("\nSetting up connections...")
        
        # Each peer connects to every other peer (fully connected network for simplicity)
        peer_ids = list(self.peers.keys())
        for i, peer_id1 in enumerate(peer_ids):
            for peer_id2 in peer_ids[i+1:]:
                peer1 = self.peers[peer_id1]
                peer2 = self.peers[peer_id2]
                
                # Connect peers to each other and share their piece information
                peer1.connect_to_peer(peer_id2, peer2.pieces)
                peer2.connect_to_peer(peer_id1, peer1.pieces)
                
                # If one peer is a seed, the other expresses interest
                if peer1.is_seed and not peer2.is_seed:
                    peer2.express_interest(peer_id1)
                    peer1.set_peer_interested(peer_id2, True)
                
                if peer2.is_seed and not peer1.is_seed:
                    peer1.express_interest(peer_id2)
                    peer2.set_peer_interested(peer_id1, True)
    
    def run_simulation(self, max_time=100):
        """Run the BitTorrent simulation with LRF and Tit-for-Tat."""
        # Setup connections
        self.setup_connections()
        
        print("\nStarting simulation...")
        print(f"Initial state: {sum(1 for p in self.peers.values() if p.is_seed)} seeds, {sum(1 for p in self.peers.values() if not p.is_seed)} leechers")
        
        # Run the simulation for max_time steps
        for t in range(1, max_time + 1):
            self.current_time = t
            
            # 1. Run choking algorithm for all peers
            for peer_id, peer in self.peers.items():
                # Get list of peers to unchoke
                peers_to_unchoke = peer.run_choking_algorithm(t)
                
                # Update choking status for all connected peers
                for other_id in peer.connected_peers:
                    if other_id in peers_to_unchoke:
                        peer.unchoke_peer(other_id)
                        self.peers[other_id].set_peer_choking(peer_id, False)
                    else:
                        peer.choke_peer(other_id)
                        self.peers[other_id].set_peer_choking(peer_id, True)
            
            # 2. Each peer requests pieces using LRF algorithm
            for peer_id, peer in self.peers.items():
                # Skip completed peers
                if peer.is_seed:
                    continue
                
                # For each peer that has unchoked us, try to request a piece
                for other_id, info in peer.connected_peers.items():
                    if not info['peer_choking'] and info['am_interested']:
                        # Select a piece using Local Rarest First algorithm
                        piece_to_request = peer.select_piece_to_request(other_id)
                        
                        if piece_to_request is not None:
                            # Request the piece
                            other_peer = self.peers[other_id]
                            
                            # If successful upload/download
                            if (other_peer.upload_piece(piece_to_request, peer_id) and 
                                peer.receive_piece(piece_to_request, other_id)):
                                
                                # Update all peers' knowledge of this peer's pieces
                                for pid in peer.connected_peers:
                                    if pid != other_id:  # Already updated during receive_piece
                                        self.peers[pid].update_peer_pieces(peer_id, piece_to_request, True)
                                
                                # If peer now has all pieces, check if we're still interested in others
                                if peer.is_seed:
                                    for pid in peer.connected_peers:
                                        peer.express_not_interested(pid)
                                
                                # Break - only download one piece per peer per time unit
                                break
            
            # 3. Update interest status based on new pieces
            for peer_id, peer in self.peers.items():
                # Skip seeds
                if peer.is_seed:
                    continue
                
                # For each connected peer, check if we're still interested
                for other_id, info in peer.connected_peers.items():
                    other_peer = self.peers[other_id]
                    
                    # Check if they have any pieces we need
                    has_interesting_pieces = False
                    for i, has_piece in enumerate(other_peer.pieces):
                        if has_piece and not peer.pieces[i]:
                            has_interesting_pieces = True
                            break
                    
                    # Update interest status
                    if has_interesting_pieces and not info['am_interested']:
                        peer.express_interest(other_id)
                    elif not has_interesting_pieces and info['am_interested']:
                        peer.express_not_interested(other_id)
            
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
    """Run the BitTorrent simulation with advanced algorithms."""
    # Create and run the simulator
    sim = Simulator(num_seeds=1, num_leechers=5, num_pieces=10)
    sim.run_simulation(max_time=100)

if __name__ == "__main__":
    main()