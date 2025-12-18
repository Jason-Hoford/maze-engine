import sys
import os
import pygame
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid
from maze_engine.viz.renderer import Renderer

import sys
import os
import pygame
import math
import time
import taichi as ti

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from maze_engine.core.grid import Grid
from maze_engine.viz.taichi_renderer import TaichiRenderer
from maze_engine.algo.prim import PrimsAlgorithm

def run_comparison():
    # Target sizes
    SMALL_SIZE = 4600
    LARGE_SIZE = 20000
    
    print(f"Initializing {LARGE_SIZE}x{LARGE_SIZE} grid (approx 400M cells)...")
    try:
        # 1. Generate Real Maze Data
        t0 = time.time()
        grid = Grid(LARGE_SIZE, LARGE_SIZE)
        
        # Use simple Prims or DFS? DFS is recursive (stack). Prim is random.
        # 20k Prim might be slow due to frontier management.
        # Let's use recursive backtracker (iterative) which is heavily optimized.
        # Note: 400M cells might take ~60s.
        from maze_engine.algo.taichi_gen import TaichiGenAdapter
        print("Generating Maze Structure (GPU Accelerated)...")
        # Optimization: We don't need PERFECTION. We need texture.
        # We could generate a smaller maze and tile it?
        # User wants "load specific mazes".
        # Let's generate it fully.
        gen = TaichiGenAdapter(grid, seed=42)
        gen.run_all()
        print(f"Generation Complete ({time.time()-t0:.2f}s).")
        
    except MemoryError:
        print("Not enough RAM for 20k maze! Falling back to 10k.")
        LARGE_SIZE = 10000
        grid = Grid(LARGE_SIZE, LARGE_SIZE)
        gen = RecursiveBacktracker(grid, seed=42)
        gen.run_all()

    # 2. Setup Renderer
    # We use TaichiRenderer for GPU power
    renderer = TaichiRenderer(grid, width=1280, height=720, record=True)
    
    # Force specific filename
    renderer.recorder.output_file = os.path.join("recordings", "scale_comparison.mp4")
    
    renderer.init_window()
    
    # 3. Zoom Logic
    start_zoom = 20.0 # Seeing pixels
    end_zoom = 720.0 / LARGE_SIZE # Seeing whole grid (vertical fit)
    
    renderer.cell_size = start_zoom
    
    # Center start
    renderer.offset_x = (renderer.screen_width - (LARGE_SIZE * start_zoom)) / 2
    renderer.offset_y = (renderer.screen_height - (LARGE_SIZE * start_zoom)) / 2
    
    font = pygame.font.SysFont("Arial", 28, bold=True)
    
    running = True
    frame = 0
    
    # Wait at start
    wait_frames = 60
    
    print("Starting Render Loop...")
    
    while running:
        # Input (Allow exit)
        renderer.handle_input()
        if not renderer.running:
            running = False
            
        # Update Zoom (Cinematic Flyout)
        if wait_frames > 0:
            wait_frames -= 1
        else:
            if renderer.cell_size > end_zoom:
                # Exponential Zoom Out
                renderer.cell_size *= 0.98
                
                # Keep Centered?
                # Total world width
                total_w = LARGE_SIZE * renderer.cell_size
                total_h = LARGE_SIZE * renderer.cell_size
                
                # Center
                renderer.offset_x = (renderer.screen_width - total_w) / 2
                renderer.offset_y = (renderer.screen_height - total_h) / 2
            else:
                # Finished Zooming
                # Wait 2 seconds then exit
                if frame > 2000: # Sentinel
                     pass # Just wait
                else:
                     frame = 2000 # Trigger end sequence
                     
        # Render Maze (GPU)
        renderer.render_kernel(renderer.cell_size, renderer.offset_x, renderer.offset_y)
        ti.sync()
        
        # Blit
        arr = renderer.pixels.to_numpy()
        pygame.surfarray.blit_array(renderer.surface, arr)
        
        # Draw Overlays (Comparison Boxes)
        # Transform World (0,0) to Screen
        # top_left_x = renderer.offset_x
        # top_left_y = renderer.offset_y
        
        # We want to show "Scale of 4600".
        # Let's draw it in center? Or Top Left?
        # User implies comparing "Code Green" (Small) to "Justice" (Large).
        # Let's draw a Green Box of size 4600x4600 in the middle of the maze.
        
        small_w_scr = SMALL_SIZE * renderer.cell_size
        small_h_scr = SMALL_SIZE * renderer.cell_size
        
        center_x = renderer.screen_width / 2
        center_y = renderer.screen_height / 2
        
        # Box Rect
        box_x = center_x - (small_w_scr / 2)
        box_y = center_y - (small_h_scr / 2)
        
        # Draw only if it fits/is visible
        pygame.draw.rect(renderer.surface, (0, 255, 0), (box_x, box_y, small_w_scr, small_h_scr), 4) # Thickness 4
        
        # Text
        # Only show text if box is reasonably large
        if small_w_scr > 50:
            label = font.render(f"Code Green Scale ({SMALL_SIZE}x{SMALL_SIZE})", True, (0, 255, 0))
            renderer.surface.blit(label, (box_x + 10, box_y + 10))
            
        # Draw Large Label
        title = font.render(f"Project Justice Scale ({LARGE_SIZE}x{LARGE_SIZE})", True, (100, 100, 255))
        renderer.surface.blit(title, (20, 20))

        # Capture
        if renderer.recorder.active:
            renderer.recorder.capture_frame(renderer.surface)

        pygame.display.flip()
        renderer.clock.tick(60)
        
        # End Condition
        if frame >= 2000:
            frame += 1
            if frame > 2120: # Wait 2 seconds (120 frames)
                running = False
                
    if renderer.recorder.active:
        renderer.recorder.stop()
    pygame.quit()
    print("Comparison recording saved.")

if __name__ == "__main__":
    run_comparison()
