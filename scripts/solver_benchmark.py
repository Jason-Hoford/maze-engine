import sys
import os
import time
import argparse
from typing import List, Tuple

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid
from maze_engine.algo.dfs import RecursiveBacktracker
from maze_engine.algo.taichi_gen import TaichiGenAdapter
from maze_engine.core.complexity import MazePostProcessor
from maze_engine.algo.solvers import (
    BFS, Dijkstra, AStar, WallFollower, 
    BiDirectionalAStar, Tremaux, RecursiveDFS, 
    DeadEndFiller, SwarmSolver
)

# ==========================================
# GLOBAL CONFIGURATION
# Add or remove solver names here to include/exclude them from the race.
# ==========================================
ENABLED_SOLVERS = [
    "bfs", 
    "dijkstra",
    "astar", 
    "biastar", 
    "tremaux",
    "dfs_solve", 
    "deadend", 
    "swarm",
    "left",     # Wall Follower (Left)
    "right"     # Wall Follower (Right)
]

def get_solver_class(name, grid):
    # Helper to return instance
    if name == "bfs": return BFS(grid)
    if name == "dijkstra": return Dijkstra(grid)
    if name == "astar": return AStar(grid)
    if name == "biastar": return BiDirectionalAStar(grid)
    if name == "tremaux": return Tremaux(grid)
    if name == "dfs_solve": return RecursiveDFS(grid)
    if name == "deadend": return DeadEndFiller(grid)
    if name == "swarm": return SwarmSolver(grid)
    if name == "left": return WallFollower(grid, rule="left")
    if name == "right": return WallFollower(grid, rule="right")
    return None

def run_benchmark():
    parser = argparse.ArgumentParser(description="Solver Benchmark")
    parser.add_argument("--width", type=int, default=500, help="Maze Width")
    parser.add_argument("--height", type=int, default=500, help="Maze Height")
    parser.add_argument("--braid", type=float, default=0.1, help="Braid Factor (0.0-1.0)")
    parser.add_argument("--seed", type=int, default=None, help="Random Seed")
    args = parser.parse_args()

    print(f"=== MAZE SOLVER BENCHMARK ===")
    print(f"Size: {args.width}x{args.height} | Braid: {args.braid}")
    print(f"Solvers: {', '.join(ENABLED_SOLVERS)}")
    print("-" * 50)

    # 1. Generate Maze
    print("Generating Maze (Recursive Backtracker)...")
    t0 = time.time()
    grid = Grid(args.width, args.height)
    # Auto-select GPU for large mazes
    if args.width * args.height > 7000 * 7000:
        print("Large maze detected. Using GPU Generator...")
        gen = TaichiGenAdapter(grid, seed=args.seed)
    else:
        gen = RecursiveBacktracker(grid, seed=args.seed)
        
    gen.run_all()
    
    if args.braid > 0:
        removed = MazePostProcessor.braid(grid, factor=args.braid, seed=args.seed)
        print(f"Braided: Removed {removed} dead ends.")
        
    gen_time = time.time() - t0
    print(f"Generation Complete in {gen_time:.4f}s.")
    print("-" * 50)

    # 2. Race Loop
    results = [] # (name, time, path_len, visited)
    
    start_pos = (0, 0)
    end_pos = (args.width-1, args.height-1)
    
    for name in ENABLED_SOLVERS:
        print(f"Running {name.upper()}...", end="", flush=True)
        
        # Fresh instance (reusing grid is fine as solvers rely on internal state usually, 
        # but advanced solvers write to grid bits. 
        # Ideally we should CLEAR solver bits between runs.
        # Let's do a quick bit clear?
        # Grid.SOLVER_VISITED | Grid.PATH | Grid.SOLVER_AUX
        # Clearing entire array is fast?
        # Actually safer to let them overwrite or just ingore bits.
        # Solvers DON'T read visited bits for validity (except Swarm/Tremaux maybe?).
        # Tremaux might read visited bits? No, it uses internal dict usually.
        # Wait, Tremaux reads 'visits' dict. 
        # Swarm reads 'self.grid.cells' for SOLVER_VISITED.
        # YES, SWARM READS GRID BITS. We MUST clear bits.
        
        # Clear Solver Bits
        # Mask: ~ (SOLVER_VISITED | PATH | SOLVER_AUX)
        # 0x40 | 0x20 | 0x80 = 0xE0
        # Inverse mask: 0x1F (00011111) -> Keeps Walls (0x0F) and Visited (0x10)
        
        # Efficient clear?
        # In python loop it's slow for large grids.
        # But for 500x500 (250k) it's ok.
        # For 5000x5000 it's slow.
        # Faster way: new array? But we lose walls.
        # Use simple comprehension or map?
        # grid.cells = array('B', [b & 0x1F for b in grid.cells]) is simplest fast way.
        
        import array
        grid.cells = array.array('B', [b & 0x1F for b in grid.cells])
        
        solver = get_solver_class(name, grid)
        
        t_start = time.time()
        
        step_count = 0
        try:
            # Run to completion
            for _ in solver.run(start_pos, end_pos):
                step_count += 1
                # if step_count > 5_000_000: # Safety break
                #      raise TimeoutError("Too many steps")
        except Exception as e:
            print(f" FAILED ({e})")
            results.append({
                "name": name,
                "time": 9999.0,
                "path": 0,
                "visited": 0,
                "status": "Failed"
            })
            continue

        t_end = time.time()
        duration = t_end - t_start
        
        path_len = len(solver.path)
        visited_count = solver.visited_count
        
        print(f" Done ({duration:.4f}s) | Path: {path_len}")
        
        results.append({
            "name": name,
            "time": duration,
            "path": path_len,
            "visited": visited_count,
            "status": "Success"
        })

    # 3. Leaderboard
    print("=" * 60)
    print(f"{'RANK':<5} | {'ALGORITHM':<20} | {'TIME (s)':<10} | {'PATH':<8} | {'VISITED':<8}")
    print("-" * 60)
    
    # Sort by Time
    results.sort(key=lambda x: x['time'])
    
    for i, res in enumerate(results):
        print(f"{i+1:<5} | {res['name'].upper():<20} | {res['time']:<10.4f} | {res['path']:<8} | {res['visited']:<8}")
    print("=" * 60)

if __name__ == "__main__":
    run_benchmark()
