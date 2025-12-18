import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid
from maze_engine.algo.dfs import RecursiveBacktracker

class TestGenerators(unittest.TestCase):
    def test_dfs_coverage(self):
        w, h = 20, 20
        grid = Grid(w, h)
        algo = RecursiveBacktracker(grid, seed=42)
        algo.run_all()
            
        # 1. Total Coverage Check
        visited_count = 0
        for i in range(w * h):
            if (grid.cells[i] & Grid.VISITED):
                visited_count += 1
        
        self.assertEqual(visited_count, w * h, "DFS should visit every cell")

    def test_prim_coverage(self):
        w, h = 20, 20
        grid = Grid(w, h)
        from maze_engine.algo.prim import PrimsAlgorithm
        algo = PrimsAlgorithm(grid, seed=42)
        algo.run_all()
        
        visited_count = 0
        for i in range(w * h):
            if (grid.cells[i] & Grid.VISITED):
                visited_count += 1
        
        self.assertEqual(visited_count, w * h, "Prim's should visit every cell")

    def test_determinism(self):
        w, h = 10, 10
        grid1 = Grid(w, h)
        RecursiveBacktracker(grid1, seed=12345).run_all() # need helper or loop
        
        grid2 = Grid(w, h)
        rec = RecursiveBacktracker(grid2, seed=12345)
        for _ in rec.run(): pass
        
        self.assertEqual(grid1.cells.tobytes(), grid2.cells.tobytes())

if __name__ == '__main__':
    unittest.main()
