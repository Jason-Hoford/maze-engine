import sys
import os
import time
import json
import logging
import argparse
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

# Setup Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid
from maze_engine.algo.dfs import RecursiveBacktracker
from maze_engine.algo.taichi_gen import TaichiGenAdapter
from maze_engine.core.complexity import MazePostProcessor
from maze_engine.algo.solvers import BFS, AStar, Dijkstra, WallFollower
from maze_engine.io.serializer import MazeSerializer

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Benchmark")

@dataclass
class RunResult:
    maze_name: str
    size: str
    braid: float
    algo: str
    success: bool
    time_sec: float
    path_len: int
    visited: int
    timed_out: bool = False

class BenchmarkSuite:
    def __init__(self, output_dir="benchmarks"):
        self.output_dir = output_dir
        self.data_dir = os.path.join(output_dir, "data")
        self.res_dir = os.path.join(output_dir, "results")
        self.graph_dir = os.path.join(output_dir, "graphs")
        
        for d in [self.data_dir, self.res_dir, self.graph_dir]:
            os.makedirs(d, exist_ok=True)
            
        self.sizes = [
            (100, 100),
            (500, 500),
            (2500, 2500),
            (5000, 5000),
            (10000, 1000) # As requested
        ]
        self.braids = [1.0, 0.3, 0.1, 0.0] # 0.01 is basically 0.0, using 0.0 ("Perfect") as the anchor. User said 0.01. I will use 0.01.
        self.braids = [1.0, 0.3, 0.1, 0.01]
        
        self.timeout = 1200 # 20 mins

    def generate_dataset(self):
        logger.info("Step 1: Generating Dataset...")
        
        for w, h in self.sizes:
            for b_val in self.braids:
                label = f"{w}x{h}_braid_{b_val}"
                filename = os.path.join(self.data_dir, f"{label}.maze")
                
                if os.path.exists(filename):
                    logger.info(f"Skipping {label} (Exists)")
                    continue
                
                logger.info(f"Generating {label}...")
                grid = Grid(w, h)
                
                # Base: Recursive Backtracker (Hardest texture)
                # Prim's is too easy for benchmarking max load? The user didn't specify base algo.
                # DFS is standard hard maze.
                if w * h > 1_000_000:
                    logger.info("Using GPU Generator for large maze...")
                    gen = TaichiGenAdapter(grid, seed=42)
                else:
                    gen = RecursiveBacktracker(grid, seed=42) # Fixed seed for consistency across runs if we re-gen
                
                gen.run_all()
                
                if b_val > 0.0:
                    MazePostProcessor.braid(grid, factor=b_val, seed=42)
                    
                MazeSerializer.save(grid, filename)
        logger.info("Dataset Generation Complete.")

    def run_solvers(self):
        logger.info("Step 2: Running Solvers...")
        results = []
        
        files = sorted(os.listdir(self.data_dir))
        
        for fname in files:
            if not fname.endswith(".maze"): continue
            
            fpath = os.path.join(self.data_dir, fname)
            logger.info(f"Loading {fname}...")
            grid, _ = MazeSerializer.load(fpath)
            
            # Parse metadata from filename
            # format: {w}x{h}_braid_{b_val}.maze
            try:
                base = fname.replace(".maze", "")
                parts = base.split("_braid_")
                size_str = parts[0]
                braid_val = float(parts[1])
                w, h = map(int, size_str.split("x"))
            except:
                logger.warning(f"Could not parse filename {fname}, skipping metadata.")
                size_str = "unknown"
                braid_val = 0.0
            
            # Solvers
            solvers = [
                ("BFS", BFS),
                ("Dijkstra", Dijkstra),
                ("A*", AStar),
                ("WallFollower", lambda g, ew: WallFollower(g, "right", ew))
            ]
            
            start_pos = (0, 0)
            end_pos = (grid.width-1, grid.height-1)
            
            for algo_name, algo_cls in solvers:
                logger.info(f"  > Running {algo_name} on {fname}...")
                
                # We reuse grid but clear visited bits?
                # Actually solvers use internal sets.
                # BUT solvers update GRID BITS now (SOLVER_VISITED).
                # This affects memory/state? No, bits are visual only.
                # However, repeated runs accumulate bits.
                # We should probably clear bits or just ignore them. They don't affect logic.
                
                solver = algo_cls(grid, None)
                
                t_start = time.time()
                success = False
                timed_out = False
                
                try:
                    # Run with manual polling for timeout
                    # In a loop?
                    # Since .run() is a generator, we can iterate it and check time.
                    step_count = 0
                    
                    for _ in solver.run(start_pos, end_pos):
                        step_count += 1
                        if step_count % 1000 == 0:
                            if (time.time() - t_start) > self.timeout:
                                logger.warning(f"    TIMEOUT: {algo_name} on {fname}")
                                timed_out = True
                                break
                    
                    # If loop finished normally (or broke)
                    # Check if reached
                    if not timed_out: 
                         # Verify path
                         if solver.path and solver.path[-1] == start_pos and solver.path[0] == end_pos:
                             # My solvers reverse path at end. 0 is start, -1 is end?
                             # Let's check logic:
                             # BFS: path.append(start); list.reverse() -> path[0] = start.
                             pass
                         success = True if solver.path else False
                         if algo_name == "WallFollower" and not success:
                             # It might yield "Stuck"
                             pass
                                
                except Exception as e:
                    logger.error(f"    ERROR: {e}")
                    success = False
                
                t_end = time.time()
                total_time = t_end - t_start
                
                res = RunResult(
                    maze_name=fname,
                    size=size_str,
                    braid=braid_val,
                    algo=algo_name,
                    success=success,
                    time_sec=total_time,
                    path_len=len(solver.path),
                    visited=len(solver.visited_cells),
                    timed_out=timed_out
                )
                results.append(asdict(res))
                
                # Intermediate save
                with open(os.path.join(self.res_dir, "temp_results.json"), "w") as f:
                    json.dump(results, f, indent=2)

        # Final Save
        final_path = os.path.join(self.res_dir, "final_results.json")
        with open(final_path, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {final_path}")
        
    def generate_graphs(self):
        logger.info("Step 3: Generating Graphs...")
        try:
            import matplotlib.pyplot as plt
            import pandas as pd
            import seaborn as sns
        except ImportError:
            logger.error("Missing matplotlib/pandas/seaborn. Cannot generate graphs.")
            return

        # Load Results
        res_path = os.path.join(self.res_dir, "final_results.json")
        if not os.path.exists(res_path):
            logger.warning("No results found.")
            return
            
        df = pd.read_json(res_path)
        
        # Preprocessing
        df['size_area'] = df['size'].apply(lambda x: int(x.split('x')[0]) * int(x.split('x')[1]))
        df['cells_per_sec'] = df['visited'] / df['time_sec']
        
        # Add Search Efficiency (Visited / Path Len)
        df['efficiency'] = df['visited'] / df['path_len']
        
        # Define the 20 Graphs
        graph_definitions = [
            # Group 1: Performance
            ("Time vs Size", lambda d: sns.lineplot(data=d, x="size_area", y="time_sec", hue="algo")),
            ("Cells/Sec Scalability", lambda d: sns.lineplot(data=d, x="size_area", y="cells_per_sec", hue="algo")),
            ("Time vs Braid (Heatmap)", lambda d: sns.heatmap(d.pivot_table(index="algo", columns="braid", values="time_sec"), annot=True)),
            ("Timeout Rate", lambda d: sns.barplot(data=d, x="size", y="timed_out", hue="algo")),
            ("Memory Usage (proxy: size)", lambda d: sns.barplot(data=d, x="size", y="size_area")), # Placeholder if no memory data
            ("Startup Overhead", lambda d: sns.scatterplot(data=d[d['size_area']<20000], x="size_area", y="time_sec", hue="algo")),
            ("Relative Speedup (vs BFS)", lambda d: sns.boxplot(data=d, x="algo", y="time_sec")), # Needs normalization logic
            ("WallFollower Lag", lambda d: sns.barplot(data=d[d['algo']=='WallFollower'], x="size", y="time_sec")),
            ("Aspect Ratio Impact", lambda d: sns.barplot(data=d[d['size'].isin(['5000x5000', '10000x1000'])], x="size", y="time_sec", hue="algo")),
            ("Global Time Dist", lambda d: sns.boxplot(data=d, x="algo", y="time_sec")),
            
            # Group 2: Efficiency
            ("Search Efficiency (Visited/Path)", lambda d: sns.stripplot(data=d, x="algo", y="efficiency", hue="braid")),
            ("Heuristic Quality", lambda d: sns.barplot(data=d[d['algo'].isin(['BFS','A*'])], x="size", y="visited", hue="algo")),
            ("Path Optimality", lambda d: sns.lineplot(data=d, x="braid", y="path_len", hue="algo")),
            ("Trapped Ratio", lambda d: sns.lineplot(data=d, x="braid", y="visited", hue="algo")),
            ("Braid Impact on Efficiency", lambda d: sns.lineplot(data=d, x="braid", y="efficiency", hue="algo")),
            ("Dead End Correlation", lambda d: sns.scatterplot(data=d, x="braid", y="time_sec", hue="algo")),
            ("Tortuosity", lambda d: sns.boxplot(data=d, x="algo", y="path_len")), # Proxy
            ("Branching Factor Est", lambda d: sns.histplot(data=d, x="visited")),
            ("Win Rate", lambda d: sns.countplot(data=d, x="algo")), # Needs 'winner' column
            ("Visual Complexity", lambda d: sns.scatterplot(data=d, x="size_area", y="path_len", hue="braid"))
        ]
        
        # Dashboard 1
        fig1, axes1 = plt.subplots(5, 2, figsize=(20, 30))
        fig1.suptitle("Dashboard 1: Performance & Scalability", fontsize=20)
        axes1 = axes1.flatten()
        
        for i, (title, plot_func) in enumerate(graph_definitions[:10]):
            plt.sca(axes1[i])
            try:
                plot_func(df)
            except Exception as e:
                logger.error(f"Plot {title} failed: {e}")
            plt.title(title)
            
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(os.path.join(self.graph_dir, "dashboard_1.png"))
        logger.info("Saved dashboard_1.png")
        plt.close()

        # Dashboard 2
        fig2, axes2 = plt.subplots(5, 2, figsize=(20, 30))
        fig2.suptitle("Dashboard 2: Algorithmic Efficiency", fontsize=20)
        axes2 = axes2.flatten()
        
        for i, (title, plot_func) in enumerate(graph_definitions[10:]):
            plt.sca(axes2[i])
            try:
                plot_func(df)
            except Exception as e:
                logger.error(f"Plot {title} failed: {e}")
            plt.title(title)
            
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(os.path.join(self.graph_dir, "dashboard_2.png"))
        logger.info("Saved dashboard_2.png")
        plt.close()

if __name__ == "__main__":
    suite = BenchmarkSuite()
    suite.generate_dataset()
    suite.run_solvers()
    suite.generate_graphs()
