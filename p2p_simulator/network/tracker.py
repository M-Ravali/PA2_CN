import random

class Tracker:
    """
    Represents a BitTorrent tracker that keeps track of peers and connects them.
    """
    def __init__(self, config):
        self.config = config
        self.peers = {}  # peer_id -> (host, port, is_seed)
        self.torrent_info = {
            'piece_size': config.piece_size,
            'num_pieces': 0,  # Will be set when we determine file size
            'file_name': config.file_name
        }
    
    def register_peer(self, peer_id, host, port, is_seed=False, has_pieces=None):
        """
        Register a peer with the tracker.
        """
        self.peers[peer_id] = {
            'host': host, 
            'port': port, 
            'is_seed': is_seed,
            'pieces': has_pieces or []
        }
        return True
    
    def update_peer_pieces(self, peer_id, pieces):
        """
        Update the list of pieces a peer has.
        """
        if peer_id in self.peers:
            self.peers[peer_id]['pieces'] = pieces
            # If peer has all pieces, mark as seed
            if len(pieces) == self.torrent_info['num_pieces']:
                self.peers[peer_id]['is_seed'] = True
            return True
        return False
    
    def get_peers(self, requesting_peer_id, max_peers=None):
        """
        Return a list of peers (excluding the requesting peer).
        """
        if max_peers is None:
            max_peers = len(self.peers) - 1  # All peers except requester
        
        # Create a list of peers other than the requester
        other_peers = [
            (pid, info) for pid, info in self.peers.items() 
            if pid != requesting_peer_id
        ]
        
        # Prioritize seeds but also add some non-seeds for better distribution
        seeds = [(pid, info) for pid, info in other_peers if info['is_seed']]
        non_seeds = [(pid, info) for pid, info in other_peers if not info['is_seed']]
        
        # Randomly select the peers (prioritizing seeds)
        selected_peers = []
        selected_peers.extend(seeds[:max(1, max_peers // 2)])  # At least one seed if available
        
        # If we need more peers, add some non-seeds
        remaining_slots = max_peers - len(selected_peers)
        if remaining_slots > 0 and non_seeds:
            # Randomly select non-seeds
            selected_peers.extend(random.sample(non_seeds, min(remaining_slots, len(non_seeds))))
        
        # If we still have slots and not enough seeds or non-seeds, add more of whatever is left
        remaining_slots = max_peers - len(selected_peers)
        if remaining_slots > 0:
            remaining_peers = seeds[len(selected_peers):] if len(seeds) > len(selected_peers) else non_seeds
            if remaining_peers:
                selected_peers.extend(random.sample(remaining_peers, min(remaining_slots, len(remaining_peers))))
        
        # Format the response
        return [
            {
                'peer_id': pid,
                'host': info['host'],
                'port': info['port'],
                'is_seed': info['is_seed']
            }
            for pid, info in selected_peers
        ]
    
    def set_torrent_info(self, num_pieces, file_size=None):
        """
        Set information about the torrent.
        """
        self.torrent_info['num_pieces'] = num_pieces
        if file_size:
            self.torrent_info['file_size'] = file_size
    
    def get_peer_count(self):
        """
        Return the number of peers and seeds.
        """
        seeds = sum(1 for info in self.peers.values() if info['is_seed'])
        return {
            'total_peers': len(self.peers),
            'seeds': seeds,
            'leechers': len(self.peers) - seeds
        }
    
    def deregister_peer(self, peer_id):
        """
        Remove a peer from the tracker.
        """
        if peer_id in self.peers:
            del self.peers[peer_id]
            return True
        return False