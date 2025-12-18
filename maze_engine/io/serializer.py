import struct
import json
import zlib
import os
from typing import Optional, Dict, Any, Tuple
from array import array
from maze_engine.core.grid import Grid

class MazeSerializer:
    MAGIC = b"MAZE"
    VERSION = 1
    
    # Flags
    FLAG_COMPRESSED = 1
    FLAG_SEED_ONLY = 2
    
    @staticmethod
    def save(grid: Grid, filepath: str, meta: Dict[str, Any] = None, seed_only=False, compress=False):
        """
        Saves the maze to a binary file.
        Format:
        - MAGIC (4 bytes)
        - VERSION (1 byte)
        - FLAGS (1 byte)
        - WIDTH (4 bytes)
        - HEIGHT (4 bytes)
        - META_LEN (2 bytes)
        - META_JSON (META_LEN bytes)
        - DATA_LEN (4 bytes, 0 if seed_only)
        - DATA (compressed or raw)
        """
        if meta is None:
            meta = {}
            
        flags = 0
        if compress:
            flags |= MazeSerializer.FLAG_COMPRESSED
        if seed_only:
            flags |= MazeSerializer.FLAG_SEED_ONLY
            
        meta_bytes = json.dumps(meta).encode('utf-8')
        meta_len = len(meta_bytes)
        
        with open(filepath, "wb") as f:
            f.write(MazeSerializer.MAGIC)
            f.write(struct.pack("B", MazeSerializer.VERSION))
            f.write(struct.pack("B", flags))
            f.write(struct.pack("II", grid.width, grid.height))
            f.write(struct.pack("H", meta_len))
            f.write(meta_bytes)
            
            if seed_only:
                f.write(struct.pack("I", 0)) # No data length
            else:
                data = grid.cells.tobytes()
                if compress:
                    data = zlib.compress(data)
                
                f.write(struct.pack("I", len(data)))
                f.write(data)
                
    @staticmethod
    def load(filepath: str) -> Tuple[Grid, Dict[str, Any]]:
        with open(filepath, "rb") as f:
            magic = f.read(4)
            if magic != MazeSerializer.MAGIC:
                raise ValueError("Invalid file format")
                
            version = struct.unpack("B", f.read(1))[0]
            flags = struct.unpack("B", f.read(1))[0]
            width, height = struct.unpack("II", f.read(8))
            meta_len = struct.unpack("H", f.read(2))[0]
            meta_bytes = f.read(meta_len)
            meta = json.loads(meta_bytes.decode('utf-8'))
            
            grid = Grid(width, height)
            
            data_len = struct.unpack("I", f.read(4))[0]
            
            if flags & MazeSerializer.FLAG_SEED_ONLY:
                # User must re-run generation based on meta['seed'] and meta['algo']
                # This loader just returns the empty grid and metadata
                pass 
            elif data_len > 0:
                data = f.read(data_len)
                if flags & MazeSerializer.FLAG_COMPRESSED:
                    data = zlib.decompress(data)
                
                # Replace cells completely
                grid.cells = array('B', data)
                
            return grid, meta
