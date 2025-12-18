import unittest
import sys
import os

# Add project root to path so we can import maze_engine
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid

class TestGrid(unittest.TestCase):
    def test_initialization(self):
        w, h = 10, 10
        grid = Grid(w, h)
        self.assertEqual(len(grid.cells), w * h, f"Grid initialization size mismatch. Expected {w*h}, got {len(grid.cells)}")
        # All cells should have all walls (value 15)
        for val in grid.cells:
            self.assertEqual(val & Grid.ALL_WALLS, Grid.ALL_WALLS)

    def test_coordinates(self):
        grid = Grid(5, 5)
        idx = grid.get_index(2, 2)
        self.assertEqual(idx, 12) # 2 * 5 + 2
        
        with self.assertRaises(IndexError):
            grid.get_index(-1, 0)
        with self.assertRaises(IndexError):
            grid.get_index(0, 5)

    def test_carve_path(self):
        grid = Grid(2, 2)
        # 0,0  1,0
        # 0,1  1,1
        
        # Carve from (0,0) EAST to (1,0)
        # (0,0) should lose EAST wall
        # (1,0) should lose WEST wall
        grid.carve_path(0, 0, Grid.EAST)
        
        idx0 = grid.get_index(0, 0)
        idx1 = grid.get_index(1, 0)
        
        self.assertFalse(grid.cells[idx0] & Grid.EAST)
        self.assertFalse(grid.cells[idx1] & Grid.WEST)
        
        # Others remain
        self.assertTrue(grid.cells[idx0] & Grid.NORTH)
        self.assertTrue(grid.cells[idx1] & Grid.EAST) # (1,0) still has its own East wall

    def test_visited_flags(self):
        grid = Grid(3, 3)
        self.assertFalse(grid.is_visited(1, 1))
        grid.set_visited(1, 1)
        self.assertTrue(grid.is_visited(1, 1))

    def test_neighbors(self):
        grid = Grid(3, 3)
        # Center cell (1,1) should have 4 neighbors
        neighbors = list(grid.get_neighbors(1, 1))
        self.assertEqual(len(neighbors), 4)
        
        # Corner cell (0,0) should have 2 neighbors (East, South)
        corner_neighbors = list(grid.get_neighbors(0, 0))
        self.assertEqual(len(corner_neighbors), 2)
        self.assertIn((1, 0, Grid.EAST), corner_neighbors)
        self.assertIn((0, 1, Grid.SOUTH), corner_neighbors)

    def test_memory_sanity(self):
        # 4600 * 4600 = ~21 million cells
        # Should be ~20MB
        w, h = 4600, 4600
        grid = Grid(w, h)
        size_bytes = grid.cells.buffer_info()[1] * grid.cells.itemsize
        mb = size_bytes / (1024 * 1024)
        print(f"\nGrid {w}x{h} size: {mb:.2f} MB")
        self.assertLess(mb, 25.0) # Should be ~20.1 MB

if __name__ == '__main__':
    unittest.main()
