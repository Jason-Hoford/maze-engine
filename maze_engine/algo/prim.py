import random
from typing import Iterator, List, Tuple, Set
from maze_engine.core.grid import Grid
from maze_engine.algo.base import Generator

class PrimsAlgorithm(Generator):
    def run(self) -> Iterator[str]:
        rng = random.Random(self.seed)
        
        # Start at (0,0) or center? Let's do (0,0) for consistency
        start_x, start_y = 0, 0
        self.grid.set_visited(start_x, start_y)
        
        # Frontier: List of (x, y, from_x, from_y, dir_bit)
        # Actually Prim' usually tracks "Cells in frontier".
        # When we pick a cell from frontier, we carve to ONE of its visited neighbors.
        # So Frontier = List of (x, y)
        frontier: List[Tuple[int, int]] = []
        
        def add_neighbors(cx, cy):
            for nx, ny, dir_bit in self.grid.get_neighbors(cx, cy):
                if not self.grid.is_visited(nx, ny):
                    # Check if already in frontier?
                    # For strict Prim's we should update weights, but for maze generation
                    # we usually just add to a set to avoid duplicates.
                    # Ideally we want valid unvisited neighbors.
                    pass # logic below for efficiency

        # Efficient Frontier:
        # Instead of searching neighbors every time, let's keep a list of "Potential Walls to Carve"
        # Or just "Frontier Cells".
        # Let's stick to "Set of Frontier Cells" to allow O(1) lookup, converted to list for random choice?
        # A list with duplicates is actually fine (weighted Prim's), but let's do standard simplified Prim's.
        
        frontier_set: Set[Tuple[int, int]] = set()
        
        # Initial neighbors
        for nx, ny, _ in self.grid.get_neighbors(start_x, start_y):
            frontier_set.add((nx, ny))
            
        frontier_list = list(frontier_set) # For random choice
        
        while frontier_list:
            # Pick random cell from frontier
            idx = rng.randrange(len(frontier_list))
            # Swap remove for O(1)
            cx, cy = frontier_list[idx]
            frontier_list[idx] = frontier_list[-1]
            frontier_list.pop()
            
            if (cx, cy) in frontier_set:
                frontier_set.remove((cx, cy))
            else:
                continue # Should not happen if logic is correct
            
            # This cell might have been visited already (if added multiple times? no, we use set)
            # Actually, logic check: A cell is added to frontier when a neighbor is visited.
            # If we pick it, we carve to ONE visited neighbor.
            
            if self.grid.is_visited(cx, cy):
                continue
                
            # Find visited neighbors to carve TO
            possible_neighbors = []
            for nx, ny, dir_bit in self.grid.get_neighbors(cx, cy):
                if self.grid.is_visited(nx, ny):
                    # We want the direction FROM nx,ny TO cx,cy ? 
                    # No, we are at cx,cy (unvisited). Carve TO nx,ny (visited).
                    # grid.carve_path takes (x1, y1, dir).
                    # If we carve from cx,cy to nx,ny:
                    # We need the direction bit for cx,cy -> nx,ny.
                    possible_neighbors.append((nx, ny, dir_bit))
            
            if possible_neighbors:
                # Carve to one random visited neighbor
                nx, ny, dir_bit = rng.choice(possible_neighbors)
                self.grid.carve_path(cx, cy, dir_bit)
                self.grid.set_visited(cx, cy)
                self.step_count += 1
                
                # Add unvisited neighbors of THIS new cell to frontier
                for nx2, ny2, _ in self.grid.get_neighbors(cx, cy):
                    if not self.grid.is_visited(nx2, ny2):
                        if (nx2, ny2) not in frontier_set:
                            frontier_set.add((nx2, ny2))
                            frontier_list.append((nx2, ny2))
                            
            if self.step_count % 100 == 0:
                yield f"Frontier: {len(frontier_list)}"
                
        yield "Done"
