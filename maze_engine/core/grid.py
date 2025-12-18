from array import array
from typing import Iterator, Tuple

class Grid:
    # Bitmask Constants
    NORTH = 0b00000001
    EAST  = 0b00000010
    SOUTH = 0b00000100
    WEST  = 0b00001000
    
    # Flags
    VISITED = 0b00010000
    PATH    = 0b00100000
    SOLVER_VISITED = 0b01000000
    SOLVER_AUX     = 0b10000000 # Used for Bi-dir End, Trémaux Marked-2, Dead-End Fill
    
    # All walls present by default (N|E|S|W) = 15
    ALL_WALLS = NORTH | EAST | SOUTH | WEST
    
    # Direction Helpers
    DX = {NORTH: 0, SOUTH: 0, EAST: 1, WEST: -1}
    DY = {NORTH: -1, SOUTH: 1, EAST: 0, WEST: 0}
    OPPOSITE = {NORTH: SOUTH, SOUTH: NORTH, EAST: WEST, WEST: EAST}

    __slots__ = ('width', 'height', 'cells', 'event_writer')

    def __init__(self, width: int, height: int, event_writer=None):
        self.width = width
        self.height = height
        self.event_writer = event_writer
        # Initialize with all walls present (value 15)
        # using 'B' (unsigned char) -> 1 byte per cell
        self.cells = array('B', [self.ALL_WALLS] * (width * height))

        if self.event_writer:
             self.event_writer.write_header(width, height)

    def get_index(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return y * self.width + x
        raise IndexError(f"Coordinate ({x}, {y}) out of bounds")

    def carve_path(self, x1: int, y1: int, dir_bit: int):
        """
        Removes the wall between current cell (x,y) and the neighbor in 'dir_bit'.
        Also removes the OPPOSITE wall from the neighbor.
        """
        idx1 = y1 * self.width + x1
        
        # Determine neighbor coordinates
        x2, y2 = x1, y1
        opposite = 0
        
        if dir_bit == self.NORTH:
            y2 -= 1
            opposite = self.SOUTH
        elif dir_bit == self.SOUTH:
            y2 += 1
            opposite = self.NORTH
        elif dir_bit == self.EAST:
            x2 += 1
            opposite = self.WEST
        elif dir_bit == self.WEST:
            x2 -= 1
            opposite = self.EAST
            
        if not (0 <= x2 < self.width and 0 <= y2 < self.height):
             return # Cannot carve into void

        # Log event before modification or after? Doesn't matter much.
        if self.event_writer:
            self.event_writer.log_carve(x1, y1, dir_bit)

        idx2 = y2 * self.width + x2
        
        # Remove wall from cell 1
        self.cells[idx1] &= ~dir_bit
        # Remove opposite wall from cell 2
        self.cells[idx2] &= ~opposite
        
    def add_wall(self, x: int, y: int, dir_bit: int):
        idx = y * self.width + x
        self.cells[idx] |= dir_bit
        
        # Handle neighbor (strict consistency)
        nx, ny = x, y
        opposite = 0
        if dir_bit == self.NORTH: ny -= 1; opposite = self.SOUTH
        elif dir_bit == self.SOUTH: ny += 1; opposite = self.NORTH
        elif dir_bit == self.EAST: nx += 1; opposite = self.WEST
        elif dir_bit == self.WEST: nx -= 1; opposite = self.EAST
        
        if 0 <= nx < self.width and 0 <= ny < self.height:
            self.cells[ny * self.width + nx] |= opposite

    def has_wall(self, x: int, y: int, dir_bit: int) -> bool:
        return (self.cells[y * self.width + x] & dir_bit) != 0

    def set_visited(self, x: int, y: int, visited: bool = True):
        idx = y * self.width + x
        if visited:
            self.cells[idx] |= self.VISITED
            if self.event_writer:
                self.event_writer.log_visit(x, y)
        else:
            self.cells[idx] &= ~self.VISITED

    def is_visited(self, x: int, y: int) -> bool:
        return (self.cells[y * self.width + x] & self.VISITED) != 0

    def get_neighbors(self, x: int, y: int) -> Iterator[Tuple[int, int, int]]:
        """
        Yields (nx, ny, direction_to_neighbor) for all valid grid neighbors.
        Does NOT check walls (that's for pathfinding).
        """
        # North
        if y > 0:
            yield (x, y - 1, self.NORTH)
        # South
        if y < self.height - 1:
            yield (x, y + 1, self.SOUTH)
        # East
        if x < self.width - 1:
            yield (x + 1, y, self.EAST)
        # West
        if x > 0:
            yield (x - 1, y, self.WEST)
            
    def get_open_neighbors(self, x: int, y: int) -> Iterator[Tuple[int, int]]:
        """
        Yields (nx, ny) for neighbors that are NOT blocked by a wall.
        """
        idx = y * self.width + x
        val = self.cells[idx]
        
        if not (val & self.NORTH) and y > 0:
            yield (x, y - 1)
        if not (val & self.SOUTH) and y < self.height - 1:
            yield (x, y + 1)
        if not (val & self.EAST) and x < self.width - 1:
            yield (x + 1, y)
        if not (val & self.WEST) and x > 0:
            yield (x - 1, y)
