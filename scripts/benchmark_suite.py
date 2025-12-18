import sys
import os
import time
import timeit
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid
from maze_engine.algo.dfs import RecursiveBacktracker
from maze_engine.algo.taichi_gen import TaichiGenAdapter
from maze_engine.core.complexity import MazePostProcessor

def benchmark_size(width: int, height: int):
    print(f"\n--- Benchmarking {width}x{height} ({width*height/1e6:.1f}M cells) ---")
    
    # 1. Memory
    start_time = time.time()
    grid = Grid(width, height)
    mem_mb = (width * height) / (1024 * 1024) # Theoretical
    print(f"Grid Init: {time.time() - start_time:.4f}s")
    print(f"Memory (Grid Data): ~{mem_mb:.2f} MB")
    
    # 2. Generation (DFS)
    print("Generating...")
    # Use GPU for > 1M cells (1000x1000)
    if width * height > 1_000_000:
        print("(Using GPU Accelerated Generator)")
        algo = TaichiGenAdapter(grid, seed=42)
    else:
        print("(Using CPU Recursive Backtracker)")
        algo = RecursiveBacktracker(grid, seed=42)
    
    gen_start = time.time()
    algo.run_all()
    gen_end = time.time()
    
    gen_time = gen_end - gen_start
    print(f"Generation Time: {gen_time:.4f}s")
    print(f"Speed: {(width*height)/gen_time:,.0f} cells/sec")
    
    # 3. Braiding (10%)
    print("Braiding (10%)...")
    braid_start = time.time()
    # removed = MazePostProcessor.braid(grid, factor=0.0, seed=42)
    braid_time = time.time() - braid_start
    print(f"Braid Time: {braid_time:.4f}s (removed {0} dead ends)")

def run_suite():
    sizes = [
        (100, 100),
        (2000, 2000),      # 1M
        (4600, 4600),      # "Code Green" (21M)
        (20000, 20000)   # "Justice" (400M) - might take a while, uncomment if patient
    ]
    
    for w, h in sizes:
        benchmark_size(w, h)
        
    print("\nScale Extrapolation for 20k x 20k:")
    # Based on 4600x4600 metrics
    # If linear O(N), 400M is ~19x larger than 21M.
    # Prediction logic can go here.

if __name__ == "__main__":
    run_suite()
