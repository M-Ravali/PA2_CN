class BitField:
    """
    Represents the pieces a peer has or doesn't have.
    """
    def __init__(self, num_pieces):
        self.pieces = [False] * num_pieces
        self.num_pieces = num_pieces
    
    def has_piece(self, piece_index):
        """Check if a peer has a specific piece."""
        if 0 <= piece_index < self.num_pieces:
            return self.pieces[piece_index]
        return False
    
    def set_piece(self, piece_index, has_piece=True):
        """Set a specific piece as owned (or not owned)."""
        if 0 <= piece_index < self.num_pieces:
            self.pieces[piece_index] = has_piece
    
    def get_completed_count(self):
        """Returns the number of pieces owned."""
        return sum(1 for piece in self.pieces if piece)
    
    def is_complete(self):
        """Check if all pieces are owned."""
        return all(self.pieces)
    
    def get_missing_pieces(self):
        """Returns a list of indices for missing pieces."""
        return [i for i, has_piece in enumerate(self.pieces) if not has_piece]
    
    def get_owned_pieces(self):
        """Returns a list of indices for owned pieces."""
        return [i for i, has_piece in enumerate(self.pieces) if has_piece]
    
    def to_bytes(self):
        """Convert the bitfield to a byte representation."""
        result = bytearray()
        for i in range(0, self.num_pieces, 8):
            byte = 0
            for j in range(8):
                if i + j < self.num_pieces and self.pieces[i + j]:
                    byte |= (1 << (7 - j))
            result.append(byte)
        return bytes(result)
    
    @classmethod
    def from_bytes(cls, data, num_pieces):
        """Create a BitField from a byte representation."""
        bitfield = cls(num_pieces)
        for i in range(num_pieces):
            byte_index = i // 8
            bit_index = 7 - (i % 8)
            if byte_index < len(data):
                bitfield.pieces[i] = bool((data[byte_index] >> bit_index) & 1)
        return bitfield
    
    def __str__(self):
        return ''.join('1' if piece else '0' for piece in self.pieces)