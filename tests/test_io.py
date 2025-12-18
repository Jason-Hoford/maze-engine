import unittest
import sys
import os
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid
from maze_engine.io.serializer import MazeSerializer

class TestIO(unittest.TestCase):
    def setUp(self):
        os.makedirs("test_out", exist_ok=True)
        
    def tearDown(self):
        shutil.rmtree("test_out", ignore_errors=True)
        
    def test_round_trip_raw(self):
        grid = Grid(10, 10)
        grid.carve_path(0, 0, Grid.SOUTH)
        grid.set_visited(5, 5, True)
        
        path = "test_out/raw.maze"
        MazeSerializer.save(grid, path)
        
        grid2, meta = MazeSerializer.load(path)
        self.assertEqual(grid.cells.tobytes(), grid2.cells.tobytes())
        self.assertEqual(grid.width, grid2.width)

    def test_round_trip_compressed(self):
        grid = Grid(100, 100) # larger for compression
        path = "test_out/comp.maze"
        MazeSerializer.save(grid, path, compress=True)
        
        grid2, meta = MazeSerializer.load(path)
        self.assertEqual(grid.cells.tobytes(), grid2.cells.tobytes())
        
    def test_seed_only(self):
        grid = Grid(10, 10)
        path = "test_out/seed.maze"
        meta = {"seed": 12345, "algo": "dfs"}
        MazeSerializer.save(grid, path, meta=meta, seed_only=True)
        
        grid2, meta2 = MazeSerializer.load(path)
        # Grid2 should be empty (all walls)
        self.assertEqual(grid2.cells[0], Grid.ALL_WALLS)
        self.assertEqual(meta2["seed"], 12345)
        
        # Verify file size is tiny
        size = os.path.getsize(path)
        self.assertLess(size, 200) # Header + Meta only

if __name__ == '__main__':
    unittest.main()
