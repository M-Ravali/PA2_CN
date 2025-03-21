import time
import random
from .event import Event
from .event_queue import EventQueue

class Simulator:
    """
    Main BitTorrent simulator. Manages the global timeline, event queue,
    and coordinates the behavior of peers and the tracker.
    """
    def __init__(self, event_queue, peers, tracker=None, config=None):
        self.event_queue = event_queue
        self.peers = peers
        self.tracker = tracker
        self.config = config
        self.current_time = 0
        self.is_running = False
    
    def initialize(self):
        """
        Initialize the simulator with initial events.
        """
        # Register all peers with the tracker
        if self.tracker:
            for peer_id, peer in self.peers.items():
                pieces = peer.bitfield.get_owned_pieces() if hasattr(peer, 'bitfield') else []
                self.tracker.register_peer(
                    peer_id, 
                    peer.host, 
                    peer.port, 
                    peer.is_seed,
                    pieces
                )
            
            # Set torrent info in tracker
            seed_peer = next((p for p in self.peers.values() if p.is_seed), None)
            if seed_peer and hasattr(seed_peer, 'num_pieces'):
                self.tracker.set_torrent_info(seed_peer.num_pieces)
        
        # Schedule initial peer connections
        self.schedule_initial_connections()
        
        # Schedule periodic events
        self.schedule_periodic_events()
    
    def schedule_initial_connections(self):
        """
        Schedule initial connections between peers.
        """
        # For each leecher, connect to a few peers
        for peer_id, peer in self.peers.items():
            if not peer.is_seed:
                # Get list of other peers from tracker
                if self.tracker:
                    other_peers = self.tracker.get_peers(peer_id, max_peers=4)
                    connection_delay = 1.0  # Stagger connections
                    
                    for i, peer_info in enumerate(other_peers):
                        other_id = peer_info['peer_id']
                        host = peer_info['host']
                        port = peer_info['port']
                        
                        # Schedule a connection event
                        self.schedule_event(
                            self.current_time + connection_delay + (i * 0.5),
                            "CONNECT_PEER",
                            {
                                'peer_id': peer_id,
                                'target_peer_id': other_id,
                                'host': host,
                                'port': port
                            }
                        )
    
    def schedule_periodic_events(self):
        """
        Schedule periodic events for all peers.
        """
        # Schedule unchoking algorithm runs (every 10 seconds)
        for peer_id in self.peers.keys():
            self.schedule_recurring_event(
                self.current_time + 10.0,
                10.0,  # Every 10 seconds
                "RUN_UNCHOKING_ALGORITHM",
                {'peer_id': peer_id}
            )
            
            # Schedule piece requests (every 2 seconds)
            self.schedule_recurring_event(
                self.current_time + 2.0,
                2.0,  # Every 2 seconds
                "REQUEST_PIECE",
                {'peer_id': peer_id}
            )
            
            # Schedule tracker announcements (every 30 seconds)
            self.schedule_recurring_event(
                self.current_time + 30.0,
                30.0,  # Every 30 seconds
                "TRACKER_ANNOUNCE",
                {'peer_id': peer_id}
            )
    
    def schedule_recurring_event(self, time, interval, event_type, data=None):
        """
        Schedule a recurring event that will be re-scheduled after execution.
        """
        event_data = data.copy() if data else {}
        event_data['recurring'] = True
        event_data['interval'] = interval
        
        self.schedule_event(time, event_type, event_data)
    
    def run(self, end_time=1000.0, max_events=None):
        """
        Run the simulation until the specified end time or event count.
        """
        self.is_running = True
        event_count = 0
        
        print(f"Starting simulation with {len(self.peers)} peers...")
        
        while self.is_running and not self.event_queue.is_empty():
            event = self.event_queue.pop()
            
            if event.time > end_time:
                print(f"Reached end time: {end_time}")
                break
            
            if max_events and event_count >= max_events:
                print(f"Processed maximum number of events: {max_events}")
                break
            
            self.current_time = event.time
            self.dispatch_event(event)
            
            event_count += 1
            
            # Print progress every 1000 events
            if event_count % 1000 == 0:
                print(f"Processed {event_count} events, current simulation time: {self.current_time:.2f}")
                self.print_stats()
        
        print(f"Simulation ended after {event_count} events at time {self.current_time:.2f}")
        self.print_stats()
        
        return self.collect_results()
    
    def dispatch_event(self, event):
        """
        Dispatch an event to the appropriate peer.
        """
        event_type = event.event_type
        data = event.data or {}
        
        # Handle recurring events by rescheduling them
        if data.get('recurring'):
            interval = data.get('interval', 10.0)
            next_time = self.current_time + interval
            self.schedule_event(next_time, event_type, data)
        
        # Identify which peer should receive the event
        if 'peer_id' in data:
            peer_id = data['peer_id']
            if peer_id in self.peers:
                # Create a copy of the event data without the peer_id
                event_data = {k: v for k, v in data.items() if k != 'peer_id'}
                
                # Add current simulation time
                event_data['current_time'] = self.current_time
                
                # Dispatch to the peer
                self.peers[peer_id].process_event((event_type, event_data))
            else:
                print(f"Warning: Event for unknown peer {peer_id}: {event_type}")
        else:
            # Handle global events
            self.handle_global_event(event_type, data)
    
    def handle_global_event(self, event_type, data):
        """
        Handle events that aren't directed at a specific peer.
        """
        if event_type == "SIMULATION_END":
            self.is_running = False
            print("Simulation end event received")
        
        elif event_type == "PRINT_STATS":
            self.print_stats()
        
        else:
            print(f"Warning: Unhandled global event {event_type}")
    
    def schedule_event(self, time, event_type, data=None):
        """
        Schedule a new event in the event queue.
        """
        if not isinstance(time, (int, float)) or time < self.current_time:
            time = self.current_time
        
        ev = Event(time, event_type, data)
        self.event_queue.push(ev)
    
    def schedule_message(self, from_peer_id, to_peer_id, message, delay=0.1):
        """
        Schedule a message event from one peer to another.
        """
        # Ensure we have a valid delay (network latency)
        if delay <= 0:
            delay = 0.1
        
        # Create combined message data
        msg_data = {
            'from_peer_id': from_peer_id,
            'peer_id': to_peer_id,  # The recipient
            'message': message,
            **message.payload
        }
        
        # Schedule the event
        event_type = f"{message.msg_type.name}_RECEIVED"
        self.schedule_event(self.current_time + delay, event_type, msg_data)
    
    def print_stats(self):
        """
        Print statistics about the current state of the simulation.
        """
        total_peers = len(self.peers)
        seeds = sum(1 for p in self.peers.values() if p.is_seed)
        leechers = total_peers - seeds
        
        print(f"\nSimulation Statistics at time {self.current_time:.2f}:")
        print(f"  Total Peers: {total_peers}")
        print(f"  Seeds: {seeds}")
        print(f"  Leechers: {leechers}")
        
        if leechers > 0:
            # Print download progress for leechers
            print("\nLeecher Progress:")
            for peer_id, peer in self.peers.items():
                if not peer.is_seed and hasattr(peer, 'bitfield'):
                    pieces = peer.bitfield.get_completed_count()
                    total = peer.bitfield.num_pieces
                    percentage = (pieces / total) * 100 if total > 0 else 0
                    print(f"  Peer {peer_id}: {pieces}/{total} pieces ({percentage:.1f}%)")
        
        print()  # Empty line for readability
    
    def collect_results(self):
        """
        Collect and return results from the simulation.
        """
        results = {
            'simulation_time': self.current_time,
            'peer_stats': {}
        }
        
        for peer_id, peer in self.peers.items():
            if hasattr(peer, 'bitfield'):
                results['peer_stats'][peer_id] = {
                    'is_seed': peer.is_seed,
                    'pieces_completed': peer.bitfield.get_completed_count(),
                    'total_pieces': peer.bitfield.num_pieces
                }
        
        return results