import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.algo.dfs import RecursiveBacktracker

from maze_engine.core.grid import Grid

from maze_engine.core.complexity import MazePostProcessor

class TestComplexity(unittest.TestCase):
    def test_braiding(self):
        w, h = 20, 20
        grid = Grid(w, h)
        RecursiveBacktracker(grid, seed=42).run_all()
        
        # Initial stats
        stats1 = MazePostProcessor.calculate_stats(grid)
        self.assertGreater(stats1["dead_ends"], 0)
        
        # Braid 1.0 (Remove all dead ends)
        removed = MazePostProcessor.braid(grid, factor=1.0, seed=42)
        
        # Final stats
        stats2 = MazePostProcessor.calculate_stats(grid)
        self.assertEqual(stats2["dead_ends"], 0, "Factor 1.0 should remove all dead ends")
        self.assertGreater(removed, 0)
        
    def test_partial_braiding(self):
        w, h = 30, 30
        grid = Grid(w, h)
        RecursiveBacktracker(grid, seed=99).run_all()
        
        stats_orig = MazePostProcessor.calculate_stats(grid)
        initial_dead_ends = stats_orig["dead_ends"]
        
        # Braid 50%
        MazePostProcessor.braid(grid, factor=0.5, seed=99)
        
        stats_new = MazePostProcessor.calculate_stats(grid)
        # Should have fewer dead ends
        self.assertLess(stats_new["dead_ends"], initial_dead_ends)
        # But not zero (unlikely for DFS on 30x30 to have 0 dead ends naturally unless braided fully)
        self.assertGreater(stats_new["dead_ends"], 0)

if __name__ == '__main__':
    unittest.main()
