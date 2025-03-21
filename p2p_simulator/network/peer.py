import random
import time
from enum import Enum
from collections import defaultdict

from .message import MessageType, Message, HandshakeMessage
from .bitfield import BitField
from ..utils.logger import P2PLog
from ..utils.file_handler import FileHandler

class PeerState(Enum):
    CHOKED = 1
    UNCHOKED = 2
    INTERESTED = 3
    NOT_INTERESTED = 4

class Peer:
    """
    Represents a BitTorrent peer with all necessary functionality.
    """
    def __init__(self, peer_id, host, port, config, tracker=None, is_seed=False):
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.config = config
        self.tracker = tracker
        self.is_seed = is_seed
        
        self.log = P2PLog(peer_id)
        
        # File handling
        self.file_handler = None
        self.num_pieces = 0
        self.piece_size = config.piece_size
        
        # BitField tracking which pieces we have
        self.bitfield = None
        
        # Connections to other peers
        self.connected_peers = {}  # peer_id -> connection info
        
        # Peer state
        self.peer_states = {}  # peer_id -> {"am_choking": bool, "am_interested": bool, "peer_choking": bool, "peer_interested": bool}
        
        # Piece statistics for rarest-first algorithm
        self.piece_counts = defaultdict(int)  # piece_index -> count of peers who have it
        
        # Peer statistics for tit-for-tat
        self.peer_download_rates = {}  # peer_id -> download rate
        self.last_unchoke_time = 0
        self.last_optimistic_unchoke_time = 0
        self.unchoked_peers = set()
        self.max_unchoked_peers = 4  # Standard in BitTorrent
        
        # Download statistics
        self.download_progress = {}  # piece_index -> percentage complete
        self.requested_pieces = set()  # Currently requested pieces
        self.downloading_pieces = {}  # piece_index -> {offset: data}
        
        self.initialize_file()
        
        if self.tracker:
            self.register_with_tracker()
    
    def initialize_file(self):
        """Initialize file handling and bitfield."""
        if self.is_seed:
            # For seeds, set all pieces as available
            file_handler = FileHandler(self.config.file_name, self.config.piece_size)
            self.file_handler = file_handler
            
            # Calculate num_pieces based on file size
            file_size = file_handler.file_size
            self.num_pieces = (file_size + self.piece_size - 1) // self.piece_size
            
            # Initialize bitfield with all pieces
            self.bitfield = BitField(self.num_pieces)
            for i in range(self.num_pieces):
                self.bitfield.set_piece(i, True)
        else:
            # For leechers, initialize empty bitfield
            # We'll get num_pieces from tracker or first seed connection
            # For now, assume a placeholder
            self.num_pieces = 1  # Will be updated later
            self.bitfield = BitField(self.num_pieces)
            
            # Initialize empty file
            self.file_handler = FileHandler(f"{self.peer_id}_{self.config.file_name}", self.config.piece_size)
    
    def register_with_tracker(self):
        """Register this peer with the tracker."""
        pieces = self.bitfield.get_owned_pieces() if self.bitfield else []
        result = self.tracker.register_peer(
            self.peer_id, 
            self.host, 
            self.port, 
            self.is_seed,
            pieces
        )
        
        if result:
            self.log.info(f"Registered with tracker as {'seed' if self.is_seed else 'leecher'}")
            
            # Get torrent info and update our state
            torrent_info = getattr(self.tracker, 'torrent_info', None)
            if torrent_info and 'num_pieces' in torrent_info:
                self.num_pieces = torrent_info['num_pieces']
                
                # Update bitfield if needed
                if self.bitfield.num_pieces != self.num_pieces:
                    new_bitfield = BitField(self.num_pieces)
                    # Copy existing pieces if applicable
                    for i in range(min(self.bitfield.num_pieces, self.num_pieces)):
                        if self.bitfield.has_piece(i):
                            new_bitfield.set_piece(i, True)
                    self.bitfield = new_bitfield
        else:
            self.log.error("Failed to register with tracker")
    
    def connect_to_peer(self, peer_id, host, port):
        """Establish a connection to another peer."""
        if peer_id in self.connected_peers:
            return True
        
        self.log.info(f"Connecting to peer {peer_id} at {host}:{port}")
        
        # In a simulator, we just track the connection without actual socket operations
        self.connected_peers[peer_id] = {
            'host': host,
            'port': port,
            'bitfield': None,  # Will be updated when we receive peer's bitfield
            'last_seen': time.time()
        }
        
        # Initialize peer state
        self.peer_states[peer_id] = {
            'am_choking': True,       # We start by choking them
            'am_interested': False,   # We start not interested
            'peer_choking': True,     # They start by choking us
            'peer_interested': False  # They start not interested
        }
        
        # Send handshake
        self.send_handshake(peer_id)
        
        # Send bitfield
        self.send_bitfield(peer_id)
        
        return True
    
    def disconnect_peer(self, peer_id):
        """Disconnect from a peer."""
        if peer_id in self.connected_peers:
            self.log.info(f"Disconnecting from peer {peer_id}")
            del self.connected_peers[peer_id]
            
            if peer_id in self.peer_states:
                del self.peer_states[peer_id]
            
            if peer_id in self.peer_download_rates:
                del self.peer_download_rates[peer_id]
            
            if peer_id in self.unchoked_peers:
                self.unchoked_peers.remove(peer_id)
    
    def send_handshake(self, peer_id):
        """Send a handshake message to a peer."""
        handshake = HandshakeMessage(self.config.handshake_header, self.peer_id)
        self.log.debug(f"Sending handshake to peer {peer_id}")
        self.send_message(peer_id, handshake)
    
    def send_bitfield(self, peer_id):
        """Send our bitfield to a peer."""
        from .message import BitfieldMessage
        bitfield_message = BitfieldMessage(self.bitfield.to_bytes())
        self.log.debug(f"Sending bitfield to peer {peer_id}")
        self.send_message(peer_id, bitfield_message)
    
    def send_message(self, peer_id, message):
        """Send a message to a peer (simulated)."""
        if peer_id not in self.connected_peers:
            self.log.error(f"Cannot send message to {peer_id}, not connected")
            return False
        
        # In the simulator, we need to generate events rather than actually sending
        # The event will be handled by the simulator to deliver to the target peer
        
        # Log the message send
        self.log.debug(f"Sent {message.msg_type.name} message to peer {peer_id}")
        return True
    
    def process_event(self, event):
        """Process an event received from the simulator."""
        event_type, data = event
        
        # Event handlers for different event types
        handlers = {
            "HANDSHAKE_RECEIVED": self.handle_handshake,
            "BITFIELD_RECEIVED": self.handle_bitfield,
            "INTERESTED_RECEIVED": self.handle_interested,
            "NOT_INTERESTED_RECEIVED": self.handle_not_interested,
            "CHOKE_RECEIVED": self.handle_choke,
            "UNCHOKE_RECEIVED": self.handle_unchoke,
            "REQUEST_RECEIVED": self.handle_request,
            "PIECE_RECEIVED": self.handle_piece,
            "HAVE_RECEIVED": self.handle_have,
            "CONNECT_PEER": self.handle_connect_peer,
            "DISCONNECT_PEER": self.handle_disconnect_peer,
            "RUN_UNCHOKING_ALGORITHM": self.run_unchoking_algorithm,
            "REQUEST_PIECE": self.request_pieces,
            "TRACKER_ANNOUNCE": self.announce_to_tracker,
        }
        
        if event_type in handlers:
            handlers[event_type](data)
        else:
            self.log.error(f"Unknown event type: {event_type}")
    
    def handle_handshake(self, data):
        """Handle a received handshake message."""
        peer_id = data.get('peer_id')
        if peer_id:
            self.log.info(f"Received handshake from peer {peer_id}")
            
            # If we don't have a connection to this peer yet, create one
            if peer_id not in self.connected_peers:
                host = data.get('host', 'unknown')
                port = data.get('port', -1)
                self.connected_peers[peer_id] = {
                    'host': host,
                    'port': port,
                    'bitfield': None,
                    'last_seen': time.time()
                }
                
                # Initialize peer state
                self.peer_states[peer_id] = {
                    'am_choking': True,
                    'am_interested': False,
                    'peer_choking': True,
                    'peer_interested': False
                }
                
                # Send handshake back
                self.send_handshake(peer_id)
                
                # Send our bitfield
                self.send_bitfield(peer_id)
    
    def handle_bitfield(self, data):
        """Handle a received bitfield message."""
        peer_id = data.get('peer_id')
        bitfield_bytes = data.get('bitfield')
        
        if peer_id and bitfield_bytes and peer_id in self.connected_peers:
            # Update the peer's bitfield in our records
            peer_bitfield = BitField.from_bytes(bitfield_bytes, self.num_pieces)
            self.connected_peers[peer_id]['bitfield'] = peer_bitfield
            
            # Update piece rarity counts
            for piece_idx in range(self.num_pieces):
                if peer_bitfield.has_piece(piece_idx):
                    self.piece_counts[piece_idx] += 1
            
            # Check if we're interested in any pieces from this peer
            if not self.bitfield.is_complete():
                interested = False
                for piece_idx in range(self.num_pieces):
                    if not self.bitfield.has_piece(piece_idx) and peer_bitfield.has_piece(piece_idx):
                        interested = True
                        break
                
                if interested:
                    # Send interested message
                    self.send_interested(peer_id)
    
    def handle_interested(self, data):
        """Handle a received interested message."""
        peer_id = data.get('peer_id')
        if peer_id and peer_id in self.peer_states:
            self.log.info(f"Peer {peer_id} is interested in our pieces")
            self.peer_states[peer_id]['peer_interested'] = True
            
            # Consider unchoking if we have pieces they need
            # This would be handled by periodic unchoking algorithm
    
    def handle_not_interested(self, data):
        """Handle a received not interested message."""
        peer_id = data.get('peer_id')
        if peer_id and peer_id in self.peer_states:
            self.log.info(f"Peer {peer_id} is not interested in our pieces")
            self.peer_states[peer_id]['peer_interested'] = False
    
    def handle_choke(self, data):
        """Handle a received choke message."""
        peer_id = data.get('peer_id')
        if peer_id and peer_id in self.peer_states:
            self.log.info(f"Peer {peer_id} has choked us")
            self.peer_states[peer_id]['peer_choking'] = True
            
            # Cancel any pending requests to this peer
            self.cancel_requests_to_peer(peer_id)
    
    def handle_unchoke(self, data):
        """Handle a received unchoke message."""
        peer_id = data.get('peer_id')
        if peer_id and peer_id in self.peer_states:
            self.log.info(f"Peer {peer_id} has unchoked us")
            self.peer_states[peer_id]['peer_choking'] = False
            
            # Schedule requests for pieces if we're interested
            if self.peer_states[peer_id]['am_interested']:
                # Generate a REQUEST_PIECE event to request pieces from this peer
                pass
    
    def handle_request(self, data):
        """Handle a received request message."""
        peer_id = data.get('peer_id')
        piece_index = data.get('piece_index')
        offset = data.get('offset', 0)
        length = data.get('length', self.piece_size)
        
        if (peer_id and peer_id in self.peer_states and 
                not self.peer_states[peer_id]['am_choking'] and
                piece_index is not None):
            
            # Check if we have the requested piece
            if self.bitfield.has_piece(piece_index):
                # Read the piece data
                piece_data = self.file_handler.read_piece(piece_index)
                
                # If offset and length are specified, extract the requested portion
                if offset > 0 or length < len(piece_data):
                    piece_data = piece_data[offset:offset+length]
                
                # Send the piece
                self.send_piece(peer_id, piece_index, offset, piece_data)
            else:
                self.log.error(f"Peer {peer_id} requested piece {piece_index}, but we don't have it")
    
    def handle_piece(self, data):
        """Handle a received piece message."""
        peer_id = data.get('peer_id')
        piece_index = data.get('piece_index')
        offset = data.get('offset', 0)
        piece_data = data.get('data')
        
        if peer_id and piece_index is not None and piece_data:
            self.log.info(f"Received piece {piece_index} from peer {peer_id}")
            
            # Store the piece data
            self.receiving_piece(peer_id, piece_index, offset, piece_data)
            
            # Update download statistics for tit-for-tat
            self.update_download_rate(peer_id, len(piece_data))
            
            # Check if we've completed the piece
            if self.is_piece_complete(piece_index):
                # Mark as complete in our bitfield
                self.bitfield.set_piece(piece_index, True)
                
                # Write the complete piece to disk
                self.write_complete_piece(piece_index)
                
                # Remove from requested and downloading sets
                if piece_index in self.requested_pieces:
                    self.requested_pieces.remove(piece_index)
                if piece_index in self.downloading_pieces:
                    del self.downloading_pieces[piece_index]
                
                # Send HAVE messages to all peers
                self.broadcast_have(piece_index)
                
                # Update tracker
                self.announce_to_tracker({})
                
                # Check if download is complete
                if self.bitfield.is_complete():
                    self.log.info("Download complete! This peer is now a seed.")
                    self.is_seed = True
    
    def handle_have(self, data):
        """Handle a received have message."""
        peer_id = data.get('peer_id')
        piece_index = data.get('piece_index')
        
        if peer_id and piece_index is not None and peer_id in self.connected_peers:
            # Update peer's bitfield
            if self.connected_peers[peer_id]['bitfield']:
                self.connected_peers[peer_id]['bitfield'].set_piece(piece_index, True)
            else:
                # If we don't have their bitfield yet, create one
                peer_bitfield = BitField(self.num_pieces)
                peer_bitfield.set_piece(piece_index, True)
                self.connected_peers[peer_id]['bitfield'] = peer_bitfield
            
            # Update piece rarity
            self.piece_counts[piece_index] += 1
            
            # Check if we need this piece
            if not self.bitfield.has_piece(piece_index):
                # If we weren't interested before, send interested now
                if not self.peer_states[peer_id]['am_interested']:
                    self.send_interested(peer_id)
    
    def handle_connect_peer(self, data):
        """Handle a connect peer event."""
        peer_id = data.get('target_peer_id')
        host = data.get('host')
        port = data.get('port')
        
        if peer_id and host and port:
            self.connect_to_peer(peer_id, host, port)
    
    def handle_disconnect_peer(self, data):
        """Handle a disconnect peer event."""
        peer_id = data.get('peer_id')
        if peer_id:
            self.disconnect_peer(peer_id)
    
    def send_interested(self, peer_id):
        """Send an interested message to a peer."""
        from .message import InterestedMessage
        
        if peer_id in self.peer_states:
            self.log.debug(f"Sending INTERESTED to peer {peer_id}")
            self.peer_states[peer_id]['am_interested'] = True
            interested_msg = InterestedMessage()
            self.send_message(peer_id, interested_msg)
    
    def send_not_interested(self, peer_id):
        """Send a not interested message to a peer."""
        from .message import NotInterestedMessage
        
        if peer_id in self.peer_states:
            self.log.debug(f"Sending NOT_INTERESTED to peer {peer_id}")
            self.peer_states[peer_id]['am_interested'] = False
            not_interested_msg = NotInterestedMessage()
            self.send_message(peer_id, not_interested_msg)
    
    def send_choke(self, peer_id):
        """Send a choke message to a peer."""
        from .message import ChokeMessage
        
        if peer_id in self.peer_states:
            self.log.debug(f"Sending CHOKE to peer {peer_id}")
            self.peer_states[peer_id]['am_choking'] = True
            choke_msg = ChokeMessage()
            self.send_message(peer_id, choke_msg)
    
    def send_unchoke(self, peer_id):
        """Send an unchoke message to a peer."""
        from .message import UnchokeMessage
        
        if peer_id in self.peer_states:
            self.log.debug(f"Sending UNCHOKE to peer {peer_id}")
            self.peer_states[peer_id]['am_choking'] = False
            self.unchoked_peers.add(peer_id)
            unchoke_msg = UnchokeMessage()
            self.send_message(peer_id, unchoke_msg)
    
    def send_request(self, peer_id, piece_index, offset=0, length=None):
        """Send a request for a piece to a peer."""
        from .message import RequestMessage
        
        if length is None:
            length = self.piece_size
        
        if (peer_id in self.peer_states and 
                not self.peer_states[peer_id]['peer_choking'] and
                self.peer_states[peer_id]['am_interested']):
            
            self.log.debug(f"Sending REQUEST to peer {peer_id} for piece {piece_index}")
            request_msg = RequestMessage(piece_index, offset, length)
            self.send_message(peer_id, request_msg)
            
            # Mark as requested
            self.requested_pieces.add(piece_index)
    
    def send_piece(self, peer_id, piece_index, offset, data):
        """Send a piece to a peer."""
        from .message import PieceMessage
        
        if peer_id in self.peer_states:
            self.log.debug(f"Sending PIECE {piece_index} to peer {peer_id}")
            piece_msg = PieceMessage(piece_index, offset, data)
            self.send_message(peer_id, piece_msg)
    
    def broadcast_have(self, piece_index):
        """Send a HAVE message to all connected peers."""
        from .message import HaveMessage
        
        self.log.debug(f"Broadcasting HAVE message for piece {piece_index}")
        have_msg = HaveMessage(piece_index)
        
        for peer_id in list(self.connected_peers.keys()):
            self.send_message(peer_id, have_msg)
    
    def run_unchoking_algorithm(self, data=None):
        """Run the unchoking algorithm (tit-for-tat)."""
        current_time = time.time()
        
        # Regular unchoking (every 10 seconds)
        if current_time - self.last_unchoke_time >= 10:
            self.last_unchoke_time = current_time
            
            # Choose peers based on their download rate (tit-for-tat)
            interested_peers = [
                peer_id for peer_id, state in self.peer_states.items()
                if state['peer_interested'] and peer_id in self.connected_peers
            ]
            
            if interested_peers:
                # Sort peers by download rate (highest first)
                sorted_peers = sorted(
                    interested_peers,
                    key=lambda pid: self.peer_download_rates.get(pid, 0),
                    reverse=True
                )
                
                # Unchoke the top peers
                new_unchoked = set(sorted_peers[:self.max_unchoked_peers-1])  # Leave one slot for optimistic unchoking
                
                # Optimistic unchoking (every 30 seconds)
                if current_time - self.last_optimistic_unchoke_time >= 30:
                    self.last_optimistic_unchoke_time = current_time
                    
                    # Choose a random peer that's not already unchoked
                    choked_interested_peers = [
                        peer_id for peer_id in interested_peers
                        if peer_id not in new_unchoked
                    ]
                    
                    if choked_interested_peers:
                        optimistic_peer = random.choice(choked_interested_peers)
                        new_unchoked.add(optimistic_peer)
                        self.log.info(f"Optimistically unchoking peer {optimistic_peer}")
                
                # Choke peers that should be choked, unchoke the rest
                for peer_id in interested_peers:
                    if peer_id in new_unchoked and peer_id not in self.unchoked_peers:
                        self.send_unchoke(peer_id)
                    elif peer_id not in new_unchoked and peer_id in self.unchoked_peers:
                        self.send_choke(peer_id)
                
                # Update the set of unchoked peers
                self.unchoked_peers = new_unchoked
    
    def request_pieces(self, data=None):
        """Request pieces from unchoked peers using rarest-first strategy."""
        # Skip if we're a seed
        if self.is_seed:
            return
        
        # Find pieces we need
        needed_pieces = self.bitfield.get_missing_pieces()
        
        if not needed_pieces:
            # No pieces needed, we're complete
            return
        
        # Check which peers we can request from
        available_peers = [
            peer_id for peer_id, state in self.peer_states.items()
            if not state['peer_choking'] and state['am_interested']
        ]
        
        if not available_peers:
            # No unchoked peers to request from
            return
        
        # Calculate rarity of each needed piece
        piece_rarity = {}
        for piece_idx in needed_pieces:
            # Skip pieces we've already requested
            if piece_idx in self.requested_pieces:
                continue
            
            # Count how many peers have this piece
            piece_rarity[piece_idx] = self.piece_counts.get(piece_idx, 0)
        
        if not piece_rarity:
            # No unrequested pieces available
            return
        
        # Sort pieces by rarity (rarest first)
        rarest_pieces = sorted(piece_rarity.items(), key=lambda x: x[1])
        
        # Request the rarest pieces from available peers
        for piece_idx, _ in rarest_pieces:
            # Find peers who have this piece
            peers_with_piece = [
                peer_id for peer_id in available_peers
                if (peer_id in self.connected_peers and 
                    self.connected_peers[peer_id]['bitfield'] and
                    self.connected_peers[peer_id]['bitfield'].has_piece(piece_idx))
            ]
            
            if peers_with_piece:
                # Choose a random peer with this piece
                target_peer = random.choice(peers_with_piece)
                
                # Send request
                self.send_request(target_peer, piece_idx)
                
                # Exit after requesting one piece (we'll request more in next cycle)
                break
    
    def receiving_piece(self, peer_id, piece_index, offset, data):
        """Process a received piece fragment."""
        # Initialize piece data structure if needed
        if piece_index not in self.downloading_pieces:
            self.downloading_pieces[piece_index] = {}
        
        # Store the fragment
        self.downloading_pieces[piece_index][offset] = data
    
    def is_piece_complete(self, piece_index):
        """Check if all fragments of a piece have been received."""
        if piece_index not in self.downloading_pieces:
            return False
        
        # For simplicity, we're assuming a piece is complete if we have any data for it
        # In a real implementation, we would check that all fragments are received
        return len(self.downloading_pieces[piece_index]) > 0
    
    def write_complete_piece(self, piece_index):
        """Write a complete piece to disk."""
        if piece_index in self.downloading_pieces:
            # In a real implementation, we would combine all fragments
            # For simplicity, we'll just use the first fragment
            offset, data = next(iter(self.downloading_pieces[piece_index].items()))
            
            # Write to disk
            self.file_handler.write_piece(piece_index, data)
            
            self.log.info(f"Piece {piece_index} written to disk")
    
    def update_download_rate(self, peer_id, bytes_received):
        """Update download rate statistics for a peer."""
        # Simple implementation: just keep a running average
        current_rate = self.peer_download_rates.get(peer_id, 0)
        # Weight new data more heavily (75% new, 25% old)
        new_rate = 0.25 * current_rate + 0.75 * bytes_received
        self.peer_download_rates[peer_id] = new_rate
    
    def cancel_requests_to_peer(self, peer_id):
        """Cancel any pending requests to a peer that has choked us."""
        # In a real implementation, we would track which pieces were requested from which peers
        # For simplicity, we'll just log that requests are canceled
        self.log.info(f"Canceling pending requests to peer {peer_id}")
    
    def announce_to_tracker(self, data=None):
        """Send an announcement to the tracker."""
        if self.tracker:
            pieces = self.bitfield.get_owned_pieces()
            self.tracker.update_peer_pieces(self.peer_id, pieces)
            
            if self.bitfield.is_complete() and not self.is_seed:
                self.is_seed = True
                self.log.info("Announced to tracker as a seed")
            
            # Get updated peer list from tracker
            new_peers = self.tracker.get_peers(self.peer_id, max_peers=5)
            
            # Connect to any new peers
            for peer_info in new_peers:
                peer_id = peer_info['peer_id']
                if peer_id not in self.connected_peers:
                    self.connect_to_peer(
                        peer_id,
                        peer_info['host'],
                        peer_info['port']
                    )