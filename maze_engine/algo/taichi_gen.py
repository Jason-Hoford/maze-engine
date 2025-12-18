import taichi as ti
import numpy as np
import random
from array import array
from typing import Iterator
from maze_engine.core.grid import Grid
from maze_engine.algo.base import Generator

@ti.data_oriented
class TaichiParallelGenerator:
    def __init__(self, grid: Grid, block_size=32, seed=None):
        self.grid = grid
        self.width = grid.width
        self.height = grid.height
        self.block_size = block_size
        self.seed = seed if seed is not None else random.randint(0, 10000)
        
        # Calculate blocks
        # Calculate blocks (Round up!)
        self.blocks_x = (self.width + self.block_size - 1) // self.block_size
        self.blocks_y = (self.height + self.block_size - 1) // self.block_size
        
        # Taichi Fields
        # We need to ensure we don't init multiple times if used repeatedly?
        # Assuming one generator instance per run or handled by user.
        try:
            ti.init(arch=ti.gpu, offline_cache=True)
        except:
            pass # Already initialized
            
        self.cells = ti.field(dtype=ti.uint8, shape=(self.width, self.height))
        
        # Stacks for each block
        # Shape: (bx, by, max_stack_depth)
        # Max depth for 32x32 is 1024.
        self.max_stack = self.block_size * self.block_size
        self.stacks = ti.field(dtype=ti.int32, shape=(self.blocks_x, self.blocks_y, self.max_stack))
        self.stack_heads = ti.field(dtype=ti.int32, shape=(self.blocks_x, self.blocks_y))
        
        # Seeds for each block to ensure determinism/variety
        self.seeds = ti.field(dtype=ti.int32, shape=(self.blocks_x, self.blocks_y))
        
        # Macro-Maze Field (for Fractal Strictness)
        # Stores connectivity bits for the blocks themselves.
        # 1=N, 2=E, 4=S, 8=W
        self.macro_grid = ti.field(dtype=ti.uint8, shape=(self.blocks_x, self.blocks_y))

    def setup(self):
        # Initialize seeds
        seeds_np = np.random.randint(0, 2**31, size=(self.blocks_x, self.blocks_y), dtype=np.int32)
        self.seeds.from_numpy(seeds_np)
        
        # Initialize cells (0 = Walls implicitly if we define 0 as empty? Wait.)
        # Grid definition: 0 means "Four Walls"? No.
        # Grid.py: self.cells = bytearray(width * height) -> initialized to 0.
        # 0 means NO WALLS?
        # Let's check Grid.py.
        # get_neighbors checks: if not (cell & mask).
        # So 1 means Wall.
        # Default 0 means No Walls?
        # Actually usually Maze init means "All Walls".
        # Let's check Grid.init.
        # It's bytearray(size). So 0.
        # If 0 means no walls, then simple DFS needs "All Walls" start.
        # Usually we want bits 1|2|4|8 = 15 (0x0F) set.
        # Initial Macro Generation (CPU)
        macro_map = self.generate_macro_maze_cpu()
        self.macro_grid.from_numpy(macro_map)
        
    def generate_macro_maze_cpu(self):
        """
        Generates a Perfect Maze on the BLOCK grid using Recursive Backtracker (Iterative).
        Returns a numpy array of shape (blocks_x, blocks_y) with direction bits (1,2,4,8).
        """
        w, h = self.blocks_x, self.blocks_y
        grid = np.zeros((w, h), dtype=np.uint8)
        visited = np.zeros((w, h), dtype=bool)
        
        # Stack for DFS: (x, y)
        start_x, start_y = random.randint(0, w-1), random.randint(0, h-1)
        stack = [(start_x, start_y)]
        visited[start_x, start_y] = True
        
        while stack:
            cx, cy = stack[-1]
            neighbors = []
            
            # Check 4 directions
            # N(0,-1), E(1,0), S(0,1), W(-1,0)
            dirs = [(0, -1, 1, 4), (1, 0, 2, 8), (0, 1, 4, 1), (-1, 0, 8, 2)]
            
            for dx, dy, d_bit, opp_bit in dirs:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h and not visited[nx, ny]:
                    neighbors.append((nx, ny, d_bit, opp_bit))
            
            if neighbors:
                nx, ny, d_bit, opp_bit = random.choice(neighbors)
                # Carve connection
                grid[cx, cy] |= d_bit
                grid[nx, ny] |= opp_bit
                visited[nx, ny] = True
                stack.append((nx, ny))
            else:
                stack.pop()
                
        return grid

    @ti.func
    def rand_int(self, bx, by, limit):
        # Simple LCG or similar for local randomness
        # We can use ti.random() but we need per-thread state?
        # ti.random(dtype) is supported.
        return int(ti.random() * limit)

    @ti.kernel
    def init_grid_kernel(self):
        # Set all cells to HAVE WALLS (0x0F = 15)
        # 1(N) | 2(E) | 4(S) | 8(W) = 15
        for i, j in self.cells:
            self.cells[i, j] = ti.cast(15, ti.u8)

    @ti.kernel
    def generate_blocks_kernel(self):
        # Parallelize over blocks
        for bx, by in self.seeds:
            # 1. Initialize Stack
            # Start at random point in block? Or (0,0)?
            # Let's start at local (0,0) of the block
            lx, ly = 0, 0
            
            # Global coords
            gx_start = bx * self.block_size
            gy_start = by * self.block_size
            
            start_x = gx_start + lx
            start_y = gy_start + ly
            
            # Mark Visited (0x10 = 16)
            # We must be careful not to overwrite walls (which are 0x0F)
            # Initial state is 15. Visited | 15 = 31.
            if start_x < self.width and start_y < self.height:
                self.cells[start_x, start_y] |= ti.cast(16, ti.u8)
            
            # Push to stack
            # Stack stores packed local coord? or just flat index?
            # 32x32 = 1024. 10 bits. 
            # Store local index: ly * 32 + lx
            stack_idx = 0
            self.stacks[bx, by, stack_idx] = ly * self.block_size + lx
            stack_idx += 1
            
            # DFS Loop
            # We can't do infinite loop in Taichi easily without care?
            # Taichi loops are unrolled or bounded? 
            # While loops are supported.
            
            # Limit iterations to prevent TDR (Timeout)?
            # A 32x32 block takes ~1000 steps. Safe.
            
            while stack_idx > 0:
                # Peek
                curr_packed = self.stacks[bx, by, stack_idx-1]
                cy = curr_packed // self.block_size
                cx = curr_packed % self.block_size
                
                gcx = gx_start + cx
                gcy = gy_start + cy
                
                # Find Unvisited Neighbors (within block)
                # Directions: N(0,-1), E(1,0), S(0,1), W(-1,0)
                # Bits: 1, 2, 4, 8
                
                # We need to randomly shuffle neighbors.
                # Hard to shuffle list.
                # Pick random offset and iterate 4 times modulo 4.
                start_dir = int(ti.random() * 4) # 0 to 3
                
                found = 0
                next_lx = -1
                next_ly = -1
                carve_bit = 0
                opp_bit = 0
                
                for k in range(4):
                    d = (start_dir + k) % 4
                    nx, ny = cx, cy
                    n_bit = 0
                    o_bit = 0
                    
                    if d == 0: # N
                        ny -= 1
                        n_bit = 1
                        o_bit = 4
                    elif d == 1: # E
                        nx += 1
                        n_bit = 2
                        o_bit = 8
                    elif d == 2: # S
                        ny += 1
                        n_bit = 4
                        o_bit = 1
                    elif d == 3: # W
                        nx -= 1
                        n_bit = 8
                        o_bit = 2
                        
                    # Bounds Check (Local)
                    if 0 <= nx < self.block_size and 0 <= ny < self.block_size:
                        # Check Visited (Global bit 0x10)
                        gnx = gx_start + nx
                        gny = gy_start + ny
                        
                        # Add Global Bounds Check (Fix for edge blocks)
                        if gnx < self.width and gny < self.height:
                            if not (self.cells[gnx, gny] & 16):
                                # Found unvisited!
                                found = 1
                                next_lx = nx
                                next_ly = ny
                                carve_bit = n_bit
                                opp_bit = o_bit
                                break
                
                if found:
                    # Carve Walls
                    # Remove wall bit from current
                    self.cells[gcx, gcy] &= ti.cast(~carve_bit, ti.u8)
                    
                    # Remove opp wall bit from neighbor
                    gnx = gx_start + next_lx
                    gny = gy_start + next_ly
                    self.cells[gnx, gny] &= ti.cast(~opp_bit, ti.u8)
                    
                    # Mark Neighbor Visited
                    self.cells[gnx, gny] |= ti.cast(16, ti.u8)
                    
                    # Push
                    self.stacks[bx, by, stack_idx] = next_ly * self.block_size + next_lx
                    stack_idx += 1
                else:
                    # Pop
                    stack_idx -= 1
                    
    @ti.kernel
    def stitch_blocks_kernel(self):
        # Open random walls between blocks.
        # Horizontal boundaries: (bx, by) connects to (bx+1, by)
        # Vertical boundaries: (bx, by) connects to (bx, by+1)
        
        # Horizontal Connections
        # For each block except last column
        for bx in range(self.blocks_x - 1):
            for by in range(self.blocks_y):
                # Boundary is between local x=31 (Global x = bx*32 + 31)
                # and local x=0 of next block (Global x = (bx+1)*32)
                
                # Pick a random y row in the block
                # Or multiple? Ideally just 1 or 2 to connect.
                # Let's open 1 random hole.
                
                # STRICT FRACTAL LOGIC (VISUALLY SEAMLESS):
                # Only open if Macro Maze says so.
                # Check current block's connectivity bit for EAST (2)
                if self.macro_grid[bx, by] & 2:
                    # High Permeability Merging:
                    # Iterate ALL cells along the boundary.
                    # Open ~50% of them. This matches internal maze density (~50% passability).
                    # This hides the grid line completely.
                    # It creates LOCAL loops (A<->B) but keeps GLOBAL Tree topology.
                    
                    x1 = bx * self.block_size + (self.block_size - 1)
                    x2 = x1 + 1
                    
                    if x1 < self.width and x2 < self.width:
                        for k in range(self.block_size):
                             if ti.random() < 0.45:
                                y = by * self.block_size + k
                                if y < self.height:
                                    # Mask 253 (0xFD) = ~2
                                    self.cells[x1, y] &= ti.cast(253, ti.u8) 
                                    # Mask 247 (0xF7) = ~8
                                    self.cells[x2, y] &= ti.cast(247, ti.u8)
                
        # Vertical Connections
        for bx in range(self.blocks_x):
            for by in range(self.blocks_y - 1):
                # Boundary between locally y=31 and next y=0
                
                # STRICT FRACTAL LOGIC (VISUALLY SEAMLESS):
                # Check current block's connectivity bit for SOUTH (4)
                if self.macro_grid[bx, by] & 4:
                     # High Permeability Merging (South)
                    y1 = by * self.block_size + (self.block_size - 1)
                    y2 = y1 + 1
                    
                    if y1 < self.height and y2 < self.height:
                         for k in range(self.block_size):
                            if ti.random() < 0.45:
                                x = bx * self.block_size + k
                                if x < self.width:
                                    # Mask 251 (0xFB) = ~4
                                    self.cells[x, y1] &= ti.cast(251, ti.u8) 
                                    # Carve North of y2 (Mask 254 = 0xFE = ~1)
                                    self.cells[x, y2] &= ti.cast(254, ti.u8)

    def run_all(self):
        self.setup()
        self.init_grid_kernel()
        self.generate_blocks_kernel()
        self.stitch_blocks_kernel()
        ti.sync()
        
        # Download data back to grid
        # self.cells is (width, height)
        # grid.cells is bytearray width*height
        
        # Optimized copy
        arr = self.cells.to_numpy()
        # arr is (width, height)
        # grid.cells expects flat buffer.
        # Need to check scanline order.
        # Grid index: y * width + x
        # So we need row-major.
        # numpy default is C-order (row-major) if we have (height, width)?
        # Our field is (width, height).
        # arr[x, y].
        # We need to transpose to (height, width) so that flat array follows y then x.
        
        arr_t = arr.T # Now (height, width)
        
        # tobytes behaves as row-major flat C array
        self.grid.cells = array('B', arr_t.tobytes())
        
        return "Done"

# Adapter for consistency
class TaichiGenAdapter(Generator):
    def run(self):
        gen = TaichiParallelGenerator(self.grid, seed=self.seed)
        gen.run_all()
        yield "Done"
