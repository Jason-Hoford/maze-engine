import unittest
import sys
import os
import taichi as ti

# Ensure import works even if conftest isn't loaded (e.g. running file directly)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid
from maze_engine.viz.taichi_renderer import TaichiRenderer

class TestGPU(unittest.TestCase):
    def test_gpu_render_kernel(self):
        """Verifies that Taichi can initialize and run a kernel on the GPU."""
        try:
            # Try initializing Taichi (simulated or real GPU)
            # Use cpu if gpu unavailable to prevent hard crash, but we want to test gpu ideally.
            # We specifically want to check if the 'TaichiRenderer' class works.
            ti.init(arch=ti.gpu, offline_cache=True)
        except Exception as e:
            self.skipTest(f"Taichi Initialization Failed (No GPU?): {e}")

        try:
            grid = Grid(100, 100)
            # Initialize renderer (headless if supported, but TaichiRenderer might need window)
            # TaichiRenderer checks for window. Using show_window=False if possible?
            # The class assumes visual usage. We'll try to init it.
            # Note: This might open a window for a split second.
            renderer = TaichiRenderer(grid, width=800, height=600)
            
            # Run the kernel
            renderer.render_kernel(1.0, 0.0, 0.0)
            ti.sync()
            
            # Verify output shape
            arr = renderer.pixels.to_numpy()
            self.assertEqual(arr.shape, (800, 600, 3), "Output buffer has wrong shape")
            
        except Exception as e:
            # Clear failure message
            self.fail(f"GPU Render Pipeline Crashed. Possible causes: outdated drivers, no VRAM. Error: {e}")

if __name__ == '__main__':
    unittest.main()
