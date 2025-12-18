import random
from typing import Iterator, List
from maze_engine.core.grid import Grid
from maze_engine.algo.base import Generator

class RecursiveBacktracker(Generator):
    def run(self) -> Iterator[str]:
        rng = random.Random(self.seed)
        
        # Start at (0,0)
        start_x, start_y = 0, 0
        self.grid.set_visited(start_x, start_y)
        
        # Stack of (x, y)
        stack: List[Tuple[int, int]] = [(start_x, start_y)]
        
        while stack:
            cx, cy = stack[-1]
            
            # Find unvisited neighbors
            neighbors = []
            # We iterate all potential neighbors (N, S, E, W)
            for nx, ny, dir_bit in self.grid.get_neighbors(cx, cy):
                if not self.grid.is_visited(nx, ny):
                    neighbors.append((nx, ny, dir_bit))
            
            if neighbors:
                # Choose random neighbor
                nx, ny, dir_bit = rng.choice(neighbors)
                
                # Carve
                self.grid.carve_path(cx, cy, dir_bit)
                self.grid.set_visited(nx, ny)
                
                stack.append((nx, ny))
                self.step_count += 1
                
                # Yield every N steps to keep UI responsive without spamming
                if self.step_count % 100 == 0:
                    yield f"Carving... Stack: {len(stack)}"
            else:
                # Backtrack
                stack.pop()
                if self.step_count % 100 == 0:
                    yield f"Backtracking... Stack: {len(stack)}"
                    
        yield "Done"
