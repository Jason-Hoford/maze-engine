import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid
from maze_engine.algo.solvers import BFS, AStar, WallFollower

class TestSolvers(unittest.TestCase):
    def create_simple_maze(self):
        # 5x5 maze, simple path
        grid = Grid(5, 5)
        # 0,0 -> 0,1 -> 0,2 -> 1,2 -> 2,2 -> 3,2 -> 4,2 -> 4,3 -> 4,4
        grid.carve_path(0, 0, Grid.SOUTH) # to 0,1
        grid.carve_path(0, 1, Grid.SOUTH) # to 0,2
        grid.carve_path(0, 2, Grid.EAST)  # to 1,2
        grid.carve_path(1, 2, Grid.EAST)  # to 2,2
        grid.carve_path(2, 2, Grid.EAST)  # to 3,2
        grid.carve_path(3, 2, Grid.EAST)  # to 4,2
        grid.carve_path(4, 2, Grid.SOUTH) # to 4,3
        grid.carve_path(4, 3, Grid.SOUTH) # to 4,4
        return grid

    def test_bfs_optimality(self):
        grid = self.create_simple_maze()
        bfs = BFS(grid)
        for _ in bfs.run((0,0), (4,4)): pass
        
        path_len = len(bfs.path)
        # Expected path: (0,0), (0,1), (0,2), (1,2), (2,2), (3,2), (4,2), (4,3), (4,4)
        # Count = 9
        self.assertEqual(path_len, 9)
        self.assertEqual(bfs.path[0], (0,0))
        self.assertEqual(bfs.path[-1], (4,4))

    def test_astar_correctness(self):
        grid = self.create_simple_maze()
        astar = AStar(grid)
        for _ in astar.run((0,0), (4,4)): pass
        
        self.assertEqual(len(astar.path), 9)
        self.assertEqual(astar.path[-1], (4,4))

    def test_wall_follower(self):
        grid = self.create_simple_maze()
        wf = WallFollower(grid, rule="left")
        for _ in wf.run((0,0), (4,4)): pass
        
        # Wall follower might take a longer path depending on walls, but in this simple line it should match or be close
        # Actually in a single corridor it matches.
        self.assertEqual(wf.path[-1], (4,4))

    def test_no_path(self):
        grid = Grid(5, 5) # All walls
        bfs = BFS(grid)
        for _ in bfs.run((0,0), (4,4)): pass
        
        self.assertEqual(len(bfs.path), 0)

if __name__ == '__main__':
    unittest.main()
