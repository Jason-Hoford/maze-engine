import taichi as ti
import numpy as np
import random
from array import array
from maze_engine.core.grid import Grid
from maze_engine.algo.base import Generator

@ti.data_oriented
class TaichiOrganicGenerator:
    def __init__(self, grid: Grid, num_walkers=4096, seed=None):
        self.grid = grid
        self.width = grid.width
        self.height = grid.height
        self.num_walkers = num_walkers
        self.seed = seed if seed is not None else random.randint(0, 10000)
        
        try:
            ti.init(arch=ti.gpu, offline_cache=True)
        except:
            pass 
            
        # 0 = Wall (15), 16 = Visited
        self.cells = ti.field(dtype=ti.uint8, shape=(self.width, self.height))
        
        # Walkers: x, y, active (1=yes, 0=no)
        self.walkers = ti.Vector.field(3, dtype=ti.int32, shape=self.num_walkers)
        self.visited_count = ti.field(dtype=ti.int32, shape=())
        
        # Candidate list for Scanning Hunt (fallback)
        self.max_candidates = 1024 * 1024 # Buffer
        self.candidates = ti.Vector.field(2, dtype=ti.int32, shape=self.max_candidates)
        self.candidate_count = ti.field(dtype=ti.int32, shape=())
        
        # Field to store potential restart candidates (found during scanning)
        # To avoid atomic contention on a list, we just scan random points in python loop or kernel?
        # A simple "Hunt" kernel is efficient on GPU.

    def setup(self):
        self.visited_count[None] = 1
        
    @ti.kernel
    def init_grid(self):
        # Fill with Walls (15)
        for i, j in self.cells:
            self.cells[i, j] = ti.cast(15, ti.u8)

    @ti.kernel
    def init_walkers(self):
        # Start one walker in the middle
        cx, cy = self.width // 2, self.height // 2
        # Use atomic check
        old = ti.atomic_or(self.cells[cx, cy], ti.cast(16, ti.u8))
        if not (old & 16):
            ti.atomic_add(self.visited_count[None], 1)
        
        # Set first walker active
        self.walkers[0] = ti.Vector([cx, cy, 1])
        
        # Others inactive
        for i in range(1, self.num_walkers):
            self.walkers[i] = ti.Vector([0, 0, 0])

    @ti.kernel
    def walk_step(self, steps: int):
        # Each active walker takes 'steps' moves
        for i in range(self.num_walkers):
            if self.walkers[i][2] == 1: # Active
                cx = self.walkers[i][0]
                cy = self.walkers[i][1]
                
                for _ in range(steps):
                    # Check neighbors
                    # N, E, S, W
                    # Randomly permute? 
                    # Simplest GPU shuffle: pick random start dir
                    start_d = int(ti.random() * 4)
                    
                    found = 0
                    nx, ny = -1, -1
                    carve_bit = 0
                    opp_bit = 0
                    
                    for k in range(4):
                        d = (start_d + k) % 4
                        tx, ty = cx, cy
                        
                        dir_bit = 0
                        inv_bit = 0
                        
                        if d == 0: # N
                            ty -= 1
                            dir_bit = 1
                            inv_bit = 4
                        elif d == 1: # E
                            tx += 1
                            dir_bit = 2
                            inv_bit = 8
                        elif d == 2: # S
                            ty += 1
                            dir_bit = 4
                            inv_bit = 1
                        elif d == 3: # W
                            tx -= 1
                            dir_bit = 8
                            inv_bit = 2
                            
                        # Bounds
                        if 0 <= tx < self.width and 0 <= ty < self.height:
                            # Must be UNVISITED (not have bit 16)
                            if not (self.cells[tx, ty] & 16):
                                # Found!
                                nx, ny = tx, ty
                                carve_bit = dir_bit
                                opp_bit = inv_bit
                                found = 1
                                break
                    
                    if found:
                        # Carve
                        # Use explicit masks for safety
                        self.cells[cx, cy] &= ti.cast(~carve_bit, ti.u8)
                        self.cells[nx, ny] &= ti.cast(~opp_bit, ti.u8)
                        
                        # Mark Visited
                        # Use atomic_or to prevent double counting if multiple walkers hit same cell
                        old_val = ti.atomic_or(self.cells[nx, ny], ti.cast(16, ti.u8))
                        if not (old_val & 16):
                            ti.atomic_add(self.visited_count[None], 1)
                        
                        # Move
                        cx, cy = nx, ny
                        self.walkers[i][0] = cx
                        self.walkers[i][1] = cy
                    else:
                        # Stuck! Die.
                        self.walkers[i][2] = 0
                        break

    @ti.kernel
    def hunt_and_respawn(self, attempts: int):
        # Randomly probe the grid to revive dead walkers
        # Global random hunt
        for i in range(self.num_walkers):
            if self.walkers[i][2] == 0:
                # Try to revive
                # Probe 'attempts' times
                for _ in range(attempts):
                    # Random point
                    rx = int(ti.random() * self.width)
                    ry = int(ti.random() * self.height)
                    
                    # Must be Unvisited (0x10 is 0)
                    if not (self.cells[rx, ry] & 16):
                        # Must have a Visited Neighbor to branch from
                        valid_neighbor = 0
                        nx, ny = -1, -1
                        carve_bit = 0
                        opp_bit = 0
                        
                        # Check 4 neighbors
                        start_d = int(ti.random() * 4)
                        for k in range(4):
                            d = (start_d + k) % 4
                            tx, ty = rx, ry
                            db = 0
                            ob = 0
                            if d==0: ty-=1; db=1; ob=4
                            elif d==1: tx+=1; db=2; ob=8
                            elif d==2: ty+=1; db=4; ob=1
                            elif d==3: tx-=1; db=8; ob=2
                            
                            if 0 <= tx < self.width and 0 <= ty < self.height:
                                # Neighbor MUST be Visited
                                if self.cells[tx, ty] & 16:
                                    valid_neighbor = 1
                                    nx, ny = tx, ty
                                    carve_bit = db
                                    opp_bit = ob
                                    break
                        
                        if valid_neighbor:
                            # Respawn here!
                            # Carve connection to the visited neighbor
                            self.cells[rx, ry] &= ti.cast(~carve_bit, ti.u8)
                            self.cells[nx, ny] &= ti.cast(~opp_bit, ti.u8)
                            
                            # Mark self visited
                            old_v = ti.atomic_or(self.cells[rx, ry], ti.cast(16, ti.u8))
                            if not (old_v & 16):
                                ti.atomic_add(self.visited_count[None], 1)
                            
                            # Activate
                            self.walkers[i][0] = rx
                            self.walkers[i][1] = ry
                            self.walkers[i][2] = 1 # Alive
                            break # Go to next walker

    @ti.kernel
    def scan_for_candidates(self):
        # Scan ENTIRE grid to find valid spawn points (Unvisited next to Visited)
        # No stride. We need every last pixel.
        ti.loop_config(block_dim=256)
        for i, j in self.cells:
             # Must be Unvisited
             if not (self.cells[i, j] & 16):
                # Check if neighbor is Visited
                has_vis_neighbor = 0
                if i > 0 and (self.cells[i-1, j] & 16): has_vis_neighbor = 1
                elif i < self.width-1 and (self.cells[i+1, j] & 16): has_vis_neighbor = 1
                elif j > 0 and (self.cells[i, j-1] & 16): has_vis_neighbor = 1
                elif j < self.height-1 and (self.cells[i, j+1] & 16): has_vis_neighbor = 1
                
                if has_vis_neighbor:
                    # Append to candidates
                    idx = ti.atomic_add(self.candidate_count[None], 1)
                    if idx < self.max_candidates:
                        self.candidates[idx] = ti.Vector([i, j])

    @ti.kernel
    def respawn_from_candidates(self):
        # Respawn dead walkers using the candidate list
        count = self.candidate_count[None]
        if count > 0:
            for i in range(self.num_walkers):
                if self.walkers[i][2] == 0:
                    # Pick random candidate
                    r_idx = int(ti.random() * count)
                    if r_idx >= self.max_candidates: r_idx = self.max_candidates - 1
                    
                    cand = self.candidates[r_idx]
                    rx, ry = cand[0], cand[1]
                    
                    # Verify it is still valid (atomic race might have visited it)
                    if not (self.cells[rx, ry] & 16):
                         # Connect to neighbor
                        nx, ny = -1, -1
                        carve_bit = 0
                        opp_bit = 0
                        
                        start_d = int(ti.random() * 4)
                        for k in range(4):
                            d = (start_d + k) % 4
                            tx, ty = rx, ry
                            db=0; ob=0
                            if d==0: ty-=1; db=1; ob=4
                            elif d==1: tx+=1; db=2; ob=8
                            elif d==2: ty+=1; db=4; ob=1
                            elif d==3: tx-=1; db=8; ob=2
                            
                            if 0 <= tx < self.width and 0 <= ty < self.height:
                                if self.cells[tx, ty] & 16:
                                    nx, ny = tx, ty
                                    carve_bit = db
                                    opp_bit = ob
                                    break
                        
                        if nx != -1:
                            self.cells[rx, ry] &= ti.cast(~carve_bit, ti.u8)
                            self.cells[nx, ny] &= ti.cast(~opp_bit, ti.u8)
                            
                            old_c = ti.atomic_or(self.cells[rx, ry], ti.cast(16, ti.u8))
                            if not (old_c & 16):
                                ti.atomic_add(self.visited_count[None], 1)
                            
                            self.walkers[i][0] = rx
                            self.walkers[i][1] = ry
                            self.walkers[i][2] = 1 # Active

    @ti.kernel
    def auto_complete_step(self):
        # NUCLEAR OPTION: Cellular Automata Growth
        # For every Unvisited cell, if it touches a Visited cell, connect and mark visited.
        # This expands the frontier by 1 pixel every step globally.
        # It handles "dust", "holes", and "corners" efficiently.
        
        ti.loop_config(block_dim=256)
        for i, j in self.cells:
             if not (self.cells[i, j] & 16): # If Unvisited
                # Find Visited Neighbors
                # We need to pick ONE to connect to (Tree Property).
                
                # Check neighbors
                valid_neighbor = 0
                nx, ny = -1, -1
                carve_bit = 0
                opp_bit = 0
                
                # Shuffle order casually
                start_d = int(ti.random() * 4)
                for k in range(4):
                    d = (start_d + k) % 4
                    tx, ty = i, j
                    db=0; ob=0
                    if d==0: ty-=1; db=1; ob=4
                    elif d==1: tx+=1; db=2; ob=8
                    elif d==2: ty+=1; db=4; ob=1
                    elif d==3: tx-=1; db=8; ob=2
                    
                    if 0 <= tx < self.width and 0 <= ty < self.height:
                        if self.cells[tx, ty] & 16: # Found Visited Neighbor
                            valid_neighbor = 1
                            nx, ny = tx, ty
                            carve_bit = db
                            opp_bit = ob
                            break
                
                if valid_neighbor:
                    # Connect!
                    self.cells[i, j] &= ti.cast(~carve_bit, ti.u8)
                    self.cells[nx, ny] &= ti.cast(~opp_bit, ti.u8)
                    
                    # Atomic count check
                    old_a = ti.atomic_or(self.cells[i, j], ti.cast(16, ti.u8))
                    if not (old_a & 16):
                        ti.atomic_add(self.visited_count[None], 1)

    def run_all(self):
        self.setup()
        self.init_grid()
        self.init_walkers()
        
        total_cells = self.width * self.height
        
        iter_count = 0
        last_visited = 0
        stuck_frames = 0
        
        while self.visited_count[None] < total_cells:
            # Update status
            current_v = self.visited_count[None]
            fill_ratio = current_v / total_cells

            # Strategy Switch
            if fill_ratio > 0.90 or stuck_frames > 20:
                # Late Game / Stuck -> Auto Complete Mode
                self.auto_complete_step()
                # Run multiple steps per frame to speed up filling (e.g. 10 pixels expansion)
                for _ in range(9):
                     self.auto_complete_step()
                     
                ti.sync()
            else:
                # Early Game -> Walkers
                self.walk_step(50)
                ti.sync()
                # Light hunt to keep population up
                if iter_count % 10 == 0:
                     self.hunt_and_respawn(100)
                     ti.sync()
            
            # Check progress 
            new_v = self.visited_count[None]
            if new_v == last_visited:
                stuck_frames += 1
            else:
                stuck_frames = 0
            last_visited = new_v
            
            # STRICT TERMINATION
            if total_cells - new_v < 100: 
                 # Final sweep
                 for _ in range(100): self.auto_complete_step()
                 print("Generator Done (Complete).")
                 break
            
            if stuck_frames > 2000: 
                 print(f"Generator stuck at {fill_ratio*100:.4f}%. Force Stop.")
                 break
                
            iter_count += 1
            if iter_count % 100 == 0:
                print(f"Generated: {new_v}/{total_cells} ({new_v/total_cells*100:.1f}%)")

        print("Downloading to CPU...")
        arr = self.cells.to_numpy()
        arr_t = arr.T
        self.grid.cells = array('B', arr_t.tobytes())
        return "Done"

class TaichiOrganicAdapter(Generator):
    def run(self):
        gen = TaichiOrganicGenerator(self.grid, seed=self.seed)
        gen.run_all()
        yield "Done"
