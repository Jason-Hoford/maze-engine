from array import array
import math

class LODSystem:
    def __init__(self, grid):
        self.original_grid = grid
        self.mipmaps = {} # Level -> Compressed Grid Array
        # Level 0 = Original
        # Level 1 = 2x2 blocks
        # Level 2 = 4x4 blocks -> 16 cells per pixel
        # Level 3 = 8x8 blocks -> 64 cells per pixel
        
    def generate_level(self, level: int):
        if level in self.mipmaps:
            return self.mipmaps[level]
            
        block_size = 1 << level
        width = math.ceil(self.original_grid.width / block_size)
        height = math.ceil(self.original_grid.height / block_size)
        
        # For LOD visualization, we care about "density".
        # If a block is mostly walls, it's a wall.
        # If it's mostly open, it's open.
        # We store density: 0=Open, 1=Mixed, 2=Solid Wall
        
        # This is a heavy computation for 20k, so we only compute ON DEMAND or for specific chunks.
        # For this implementation, we will use a simplified "Sampling" approach.
        # Just check the center pixel of the block.
        # (Naive but fast O(1))
        
        # Actually, let's just use the Grid accessor.
        # The renderer will ask "What is the value at scaled coord X,Y?"
        pass

    def get_lod_color(self, x: int, y: int, level: int):
        """
        Returns a simplified color/state for a large block at (x,y) in LOD coordinates.
        """
        # Sampling approach (fastest for real-time zooming)
        # Map LOD coord to World Coord
        step = 1 << level
        wx = x * step
        wy = y * step
        
        # Bounds check
        if wx >= self.original_grid.width or wy >= self.original_grid.height:
            return 0 # Out of bounds
            
        # Sample the top-left (or center)
        # This creates aliasing but allows 60fps on 20k grids without pre-computing 400MB of mipmaps.
        idx = self.original_grid.get_index(wx, wy)
        val = self.original_grid.cells[idx]
        
        # Return rudimentary state
        return val # Just return the raw flags of the sample
