"""
BitTorrent Simulator - Simplified Main Entry Point

This script provides a simplified entry point for the BitTorrent simulator
without requiring complex package imports.
"""

import os
import time
import random

# Simple configuration class
class Config:
    def __init__(self):
        self.piece_size = 1024
        self.file_name = "sample_file.dat"
        self.max_connections = 5
        self.handshake_header = "P2PFILESHARINGPROJ"

# Simple BitField class
class BitField:
    def __init__(self, num_pieces):
        self.pieces = [False] * num_pieces
        self.num_pieces = num_pieces
    
    def has_piece(self, piece_index):
        if 0 <= piece_index < self.num_pieces:
            return self.pieces[piece_index]
        return False
    
    def set_piece(self, piece_index, has_piece=True):
        if 0 <= piece_index < self.num_pieces:
            self.pieces[piece_index] = has_piece
    
    def get_completed_count(self):
        return sum(1 for piece in self.pieces if piece)
    
    def is_complete(self):
        return all(self.pieces)
    
    def get_missing_pieces(self):
        return [i for i, has_piece in enumerate(self.pieces) if not has_piece]
    
    def get_owned_pieces(self):
        return [i for i, has_piece in enumerate(self.pieces) if has_piece]

# Simple Event class
class Event:
    def __init__(self, time, event_type, data=None):
        self.time = time
        self.event_type = event_type
        self.data = data or {}
    
    def __lt__(self, other):
        return self.time < other.time

# Simple EventQueue
class EventQueue:
    def __init__(self):
        self.events = []
    
    def push(self, event):
        self.events.append(event)
        self.events.sort()  # Sort by time
    
    def pop(self):
        if self.events:
            return self.events.pop(0)
        return None
    
    def is_empty(self):
        return len(self.events) == 0

# Simplified Tracker class
class Tracker:
    def __init__(self, config):
        self.config = config
        self.peers = {}  # peer_id -> info
        self.num_pieces = 10  # Default value
    
    def register_peer(self, peer_id, is_seed=False):
        self.peers[peer_id] = {
            'is_seed': is_seed,
            'pieces': list(range(self.num_pieces)) if is_seed else []
        }
        print(f"Registered peer {peer_id} as {'seed' if is_seed else 'leecher'}")
    
    def update_peer(self, peer_id, pieces):
        if peer_id in self.peers:
            self.peers[peer_id]['pieces'] = pieces
            if len(pieces) == self.num_pieces:
                self.peers[peer_id]['is_seed'] = True
                print(f"Peer {peer_id} has become a seed")
    
    def get_peers(self, requesting_peer_id, max_peers=3):
        other_peers = [pid for pid in self.peers if pid != requesting_peer_id]
        if not other_peers:
            return []
        
        # Prioritize seeds
        seeds = [pid for pid in other_peers if self.peers[pid]['is_seed']]
        non_seeds = [pid for pid in other_peers if not self.peers[pid]['is_seed']]
        
        result = []
        # Add seeds first
        result.extend(seeds[:max_peers])
        
        # Add non-seeds if we have space
        remaining = max_peers - len(result)
        if remaining > 0:
            result.extend(non_seeds[:remaining])
        
        return result

# Simplified Peer class
class Peer:
    def __init__(self, peer_id, config, tracker, is_seed=False):
        self.peer_id = peer_id
        self.config = config
        self.tracker = tracker
        self.is_seed = is_seed
        
        # Initialize bitfield
        self.num_pieces = tracker.num_pieces
        self.bitfield = BitField(self.num_pieces)
        
        # If seed, mark all pieces as available
        if is_seed:
            for i in range(self.num_pieces):
                self.bitfield.set_piece(i, True)
        
        # Connected peers
        self.connected_peers = {}  # peer_id -> peer info
        
        # Register with tracker
        self.tracker.register_peer(peer_id, is_seed)
    
    def connect_to_peer(self, other_peer_id):
        if other_peer_id not in self.connected_peers:
            print(f"Peer {self.peer_id} connecting to peer {other_peer_id}")
            self.connected_peers[other_peer_id] = {
                'pieces': [],
                'am_interested': False,
                'am_choking': True,
                'peer_interested': False,
                'peer_choking': True
            }
            return True
        return False
    
    def request_piece(self, from_peer_id, piece_index):
        if (from_peer_id in self.connected_peers and 
                not self.connected_peers[from_peer_id]['peer_choking']):
            print(f"Peer {self.peer_id} requesting piece {piece_index} from {from_peer_id}")
            return True
        return False
    
    def receive_piece(self, piece_index):
        if not self.bitfield.has_piece(piece_index):
            self.bitfield.set_piece(piece_index, True)
            print(f"Peer {self.peer_id} received piece {piece_index}")
            
            # Update tracker
            self.tracker.update_peer(self.peer_id, self.bitfield.get_owned_pieces())
            
            # Check if download is complete
            if self.bitfield.is_complete():
                self.is_seed = True
                print(f"Peer {self.peer_id} has completed the download and is now a seed")
            
            return True
        return False
    
    def unchoke_peer(self, peer_id):
        if peer_id in self.connected_peers:
            self.connected_peers[peer_id]['am_choking'] = False
            print(f"Peer {self.peer_id} unchoked peer {peer_id}")
            return True
        return False
    
    def choke_peer(self, peer_id):
        if peer_id in self.connected_peers:
            self.connected_peers[peer_id]['am_choking'] = True
            print(f"Peer {self.peer_id} choked peer {peer_id}")
            return True
        return False

# Simplified Simulator class
class Simulator:
    def __init__(self, config, num_seeds=1, num_leechers=5):
        self.config = config
        self.current_time = 0
        
        # Create event queue
        self.event_queue = EventQueue()
        
        # Create tracker
        self.tracker = Tracker(config)
        
        # Create peers
        self.peers = {}
        
        # Create seeds
        for i in range(num_seeds):
            peer_id = f"SEED-{i+1}"
            peer = Peer(peer_id, config, self.tracker, is_seed=True)
            self.peers[peer_id] = peer
        
        # Create leechers
        for i in range(num_leechers):
            peer_id = f"PEER-{i+1}"
            peer = Peer(peer_id, config, self.tracker, is_seed=False)
            self.peers[peer_id] = peer
        
        # Initialize the connections
        self.initialize_connections()
        
        # Schedule initial events
        self.schedule_initial_events()
    
    def initialize_connections(self):
        # Each leecher connects to a few other peers
        for peer_id, peer in self.peers.items():
            if not peer.is_seed:
                # Get peers from tracker
                other_peers = self.tracker.get_peers(peer_id, max_peers=2)
                
                # Connect to these peers
                for other_id in other_peers:
                    peer.connect_to_peer(other_id)
                    
                    # Also schedule piece requests if the other peer is a seed
                    if self.peers[other_id].is_seed:
                        # Randomly request a few pieces
                        for _ in range(3):
                            piece_index = random.randint(0, peer.num_pieces - 1)
                            # Schedule a piece request
                            self.schedule_event(
                                self.current_time + random.uniform(1, 5),
                                "REQUEST_PIECE",
                                {
                                    'requester': peer_id,
                                    'provider': other_id,
                                    'piece_index': piece_index
                                }
                            )
    
    def schedule_initial_events(self):
        # Schedule some unchoke events
        for peer_id, peer in self.peers.items():
            if peer.is_seed:
                # Seeds unchoke all connected peers
                for other_id in peer.connected_peers:
                    self.schedule_event(
                        self.current_time + random.uniform(0.5, 2),
                        "UNCHOKE_PEER",
                        {
                            'from_peer': peer_id,
                            'to_peer': other_id
                        }
                    )
        
        # Schedule a stats print event
        self.schedule_event(10, "PRINT_STATS", {})
    
    def schedule_event(self, time, event_type, data):
        event = Event(time, event_type, data)
        self.event_queue.push(event)
    
    def run(self, max_time=30):
        print(f"Starting simulation with {len(self.peers)} peers")
        print(f"- {sum(1 for p in self.peers.values() if p.is_seed)} seeds")
        print(f"- {sum(1 for p in self.peers.values() if not p.is_seed)} leechers")
        
        while not self.event_queue.is_empty() and self.current_time < max_time:
            event = self.event_queue.pop()
            self.current_time = event.time
            
            self.process_event(event)
            
            # Check if all peers are complete
            if all(peer.is_seed for peer in self.peers.values()):
                print(f"Simulation complete at time {self.current_time:.2f}: All peers are seeds")
                break
        
        print(f"Simulation ended at time {self.current_time:.2f}")
        self.print_stats()
    
    def process_event(self, event):
        event_type = event.event_type
        data = event.data
        
        if event_type == "REQUEST_PIECE":
            self.handle_request_piece(data)
        
        elif event_type == "DELIVER_PIECE":
            self.handle_deliver_piece(data)
        
        elif event_type == "UNCHOKE_PEER":
            self.handle_unchoke_peer(data)
        
        elif event_type == "CHOKE_PEER":
            self.handle_choke_peer(data)
        
        elif event_type == "PRINT_STATS":
            self.print_stats()
            # Schedule next stats print
            self.schedule_event(self.current_time + 10, "PRINT_STATS", {})
    
    def handle_request_piece(self, data):
        requester_id = data['requester']
        provider_id = data['provider']
        piece_index = data['piece_index']
        
        if (requester_id in self.peers and provider_id in self.peers):
            requester = self.peers[requester_id]
            provider = self.peers[provider_id]
            
            # Check if the requester has requested this piece from provider
            if requester.request_piece(provider_id, piece_index):
                # If the provider has the piece, deliver it
                if provider.bitfield.has_piece(piece_index):
                    # Schedule piece delivery with a small delay
                    self.schedule_event(
                        self.current_time + random.uniform(0.2, 1.0),
                        "DELIVER_PIECE",
                        {
                            'from_peer': provider_id,
                            'to_peer': requester_id,
                            'piece_index': piece_index
                        }
                    )
    
    def handle_deliver_piece(self, data):
        from_peer_id = data['from_peer']
        to_peer_id = data['to_peer']
        piece_index = data['piece_index']
        
        if to_peer_id in self.peers:
            to_peer = self.peers[to_peer_id]
            # Deliver the piece
            if to_peer.receive_piece(piece_index):
                # Schedule more piece requests if not complete
                if not to_peer.is_seed:
                    missing_pieces = to_peer.bitfield.get_missing_pieces()
                    if missing_pieces:
                        # Request another piece
                        new_piece = random.choice(missing_pieces)
                        self.schedule_event(
                            self.current_time + random.uniform(0.5, 2.0),
                            "REQUEST_PIECE",
                            {
                                'requester': to_peer_id,
                                'provider': from_peer_id,
                                'piece_index': new_piece
                            }
                        )
    
    def handle_unchoke_peer(self, data):
        from_peer_id = data['from_peer']
        to_peer_id = data['to_peer']
        
        if from_peer_id in self.peers:
            peer = self.peers[from_peer_id]
            peer.unchoke_peer(to_peer_id)
    
    def handle_choke_peer(self, data):
        from_peer_id = data['from_peer']
        to_peer_id = data['to_peer']
        
        if from_peer_id in self.peers:
            peer = self.peers[from_peer_id]
            peer.choke_peer(to_peer_id)
    
    def print_stats(self):
        print(f"\nSimulation Stats at time {self.current_time:.2f}:")
        seeds = sum(1 for peer in self.peers.values() if peer.is_seed)
        leechers = len(self.peers) - seeds
        print(f"- Seeds: {seeds}")
        print(f"- Leechers: {leechers}")
        
        if leechers > 0:
            print("\nLeecher Progress:")
            for peer_id, peer in self.peers.items():
                if not peer.is_seed:
                    pieces = peer.bitfield.get_completed_count()
                    total = peer.num_pieces
                    percentage = (pieces / total) * 100
                    print(f"- Peer {peer_id}: {pieces}/{total} pieces ({percentage:.1f}%)")

def main():
    """Run a simplified BitTorrent simulation."""
    # Create configuration
    config = Config()
    
    # Create and run simulator
    print("Initializing BitTorrent simulator...")
    sim = Simulator(config, num_seeds=1, num_leechers=5)
    
    print("\nRunning simulation...")
    sim.run(max_time=100)
    
    print("\nSimulation complete!")

if __name__ == "__main__":
    main()