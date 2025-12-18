import random
from maze_engine.core.grid import Grid

class MazePostProcessor:
    @staticmethod
    def braid(grid: Grid, factor: float = 1.0, seed: int = None):
        """
        Removes dead ends to create loops.
        factor: 0.0 = Remove NO dead ends (Perfect Maze)
                1.0 = Remove ALL dead ends (No dead ends)
        """
        rng = random.Random(seed)
        
        # Identify dead ends (cells with only 1 exit)
        # Scan entire grid
        dead_ends = []
        
        # Grid.ALL_WALLS = 15. If a cell has 3 walls, it's a dead end.
        # Actually checking neighbors is safer.
        # Check wall bits:
        # A cell has N, E, S, W bits.
        # If (cell & Grid.ALL_WALLS) has 3 bits set, it's a dead end.
        # Wait, our walls are 1=N, 2=E, 4=S, 8=W.
        # Popcount of (v & 15) == 3 -> Dead End.
        
        # Helper for popcount
        def popcount_walls(val):
            c = 0
            if val & Grid.NORTH: c += 1
            if val & Grid.EAST: c += 1
            if val & Grid.SOUTH: c += 1
            if val & Grid.WEST: c += 1
            return c

        for y in range(grid.height):
            for x in range(grid.width):
                idx = grid.get_index(x, y)
                if popcount_walls(grid.cells[idx]) == 3:
                    dead_ends.append((x, y))
                    
        rng.shuffle(dead_ends)
        
        # Number to remove
        target_remove = int(len(dead_ends) * factor)
        removed_count = 0
        
        for x, y in dead_ends:
            if removed_count >= target_remove:
                break
                
            # Re-check if it's still a dead end (neighbor updates might have changed it)
            idx = grid.get_index(x, y)
            if popcount_walls(grid.cells[idx]) != 3:
                continue 
            
            # Carve to a neighbor that is NOT the existing exit.
            # Best is to carve to another dead end to merge them, or any neighbor.
            # Simple approach: Carve to random valid wall neighbor.
            
            # Find closed neighbors
            closed_neighbors = []
            if grid.has_wall(x, y, Grid.NORTH) and y > 0: closed_neighbors.append(Grid.NORTH)
            if grid.has_wall(x, y, Grid.SOUTH) and y < grid.height - 1: closed_neighbors.append(Grid.SOUTH)
            if grid.has_wall(x, y, Grid.EAST) and x < grid.width - 1: closed_neighbors.append(Grid.EAST)
            if grid.has_wall(x, y, Grid.WEST) and x > 0: closed_neighbors.append(Grid.WEST)
            
            if closed_neighbors:
                direction = rng.choice(closed_neighbors)
                grid.carve_path(x, y, direction)
                removed_count += 1
                
        return removed_count

    @staticmethod
    def calculate_stats(grid: Grid):
        dead_ends = 0
        intersections = 0 # 0, 1 walls
        corridors = 0 # 2 walls
        
        def popcount_walls(val):
            c = 0
            if val & Grid.NORTH: c += 1
            if val & Grid.EAST: c += 1
            if val & Grid.SOUTH: c += 1
            if val & Grid.WEST: c += 1
            return c

        for i in range(grid.width * grid.height):
            walls = popcount_walls(grid.cells[i])
            if walls == 3: dead_ends += 1
            elif walls == 2: corridors += 1
            elif walls <= 1: intersections += 1
            
        total = grid.width * grid.height
        return {
            "dead_ends": dead_ends,
            "corridors": corridors,
            "intersections": intersections,
            "dead_end_percent": (dead_ends / total) * 100 if total > 0 else 0
        }
