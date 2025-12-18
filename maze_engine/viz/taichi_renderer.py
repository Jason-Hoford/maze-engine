import taichi as ti
import pygame
import numpy as np
from maze_engine.core.grid import Grid
from maze_engine.viz.recorder import VideoRecorder
from maze_engine.viz.lod import LODSystem

@ti.data_oriented
class TaichiRenderer:
    def __init__(self, grid: Grid, generator=None, solver=None, width=1280, height=720, record=False):
        self.grid = grid
        self.generator = generator
        self.solver = solver
        
        # Fixed resolution for Taichi kernel (avoid dynamic resizing complexity)
        # We process input size, but enforce a max buffer if needed.
        self.screen_width = width
        self.screen_height = height
        
        # Initialize Taichi
        try:
            # Check if likely already initialized
            ti.init(arch=ti.gpu, offline_cache=True)
        except Exception as e:
            print(f"Warning: Ti init issue (maybe already running?): {e}")

        # Data Fields
        # Maze cells (w, h)
        self.field_cells = ti.field(dtype=ti.uint8, shape=(grid.width, grid.height))
        
        # Screen Buffer for Pixel Shader
        self.pixels = ti.Vector.field(3, dtype=ti.uint8, shape=(width, height))
        
        # Colors (hardcoded constants)
        self.c_bg = ti.Vector([10, 10, 10])
        self.c_wall = ti.Vector([100, 100, 100]) # Dimmer walls for aesthetics
        self.c_visited = ti.Vector([60, 100, 160])
        self.c_path = ti.Vector([255, 215, 0])
        self.c_aux = ti.Vector([200, 60, 60]) # Red for specialized states
        
        # Camera
        self.cell_size = 20.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom_speed = 1.1

        # Tools
        self.recorder = VideoRecorder(active=record)
        
        self.font = None
        self.running = True
        self.clock = None
        self.surface = None
        self.gen_finished = False
        
        # Recording Cooldown
        self.exit_cooldown = -1 # -1: Inactive, >0: Frames remaining

        # Initial Upload
        self.update_grid_data()

    def update_grid_data(self):
        # Convert bytearray to numpy (w, h)
        # Grid is (height, width) row-major technically in memory (y*w + x)
        # Reshape to (height, width) from buffer
        arr = np.frombuffer(self.grid.cells, dtype=np.uint8)
        arr = arr.reshape((self.grid.height, self.grid.width))
        # Transpose to (width, height) for x,y indexing
        self.field_cells.from_numpy(arr.T)

    @ti.kernel
    def render_kernel(self, zoom: float, off_x: float, off_y: float):
        for x, y in self.pixels:
            color = self.c_bg
            
            # Screen -> World
            # px = wx * zoom + off
            wx = (x - off_x) / zoom
            wy = (y - off_y) / zoom
            
            iw = int(ti.floor(wx))
            ih = int(ti.floor(wy))
            
            # Bounds Check
            if 0 <= iw < self.field_cells.shape[0] and 0 <= ih < self.field_cells.shape[1]:
                cell = self.field_cells[iw, ih]
                
                # 1. Visited Background
                if (cell & 0x10) != 0:
                    color = self.c_visited

                # 2. Solver Overlay
                if (cell & 0x40) != 0: # SOLVER_VISITED
                    color = ti.Vector([100, 150, 200]) # Lighter Blue

                # 3. Solver Aux (Red)
                if (cell & 0x80) != 0: # SOLVER_AUX
                    color = self.c_aux

                # 3. Path Overlay
                # PATH (0x20)
                if (cell & 0x20) != 0:
                    color = self.c_path
                
                # 4. Walls (Internal Borders)
                # u, v in [0, 1] relative to cell
                u = wx - iw
                v = wy - ih
                
                # Wall thickness scales with zoom? No, relative to cell is fine.
                # But at far zoom, wall < 1 pixel might flicker.
                # Constant visual thickness: 
                # wall_px = 2.0
                # wall_u = wall_px / zoom
                
                th = 0.1 # Fixed relative thickness (10% of cell)
                
                is_wall = False
                # Check walls (NORTH=1, EAST=2, SOUTH=4, WEST=8)
                if u < th and (cell & 8): is_wall = True # WEST
                if u > (1-th) and (cell & 2): is_wall = True # EAST
                if v < th and (cell & 1): is_wall = True # NORTH
                if v > (1-th) and (cell & 4): is_wall = True # SOUTH
                
                if is_wall:
                    color = self.c_wall
            
            self.pixels[x, y] = color

    def fit_to_screen(self):
        padding = 40
        available_w = self.screen_width - (padding * 2)
        available_h = self.screen_height - (padding * 2)
        zoom_x = available_w / self.grid.width
        zoom_y = available_h / self.grid.height
        self.cell_size = min(zoom_x, zoom_y)
        total_w = self.grid.width * self.cell_size
        total_h = self.grid.height * self.cell_size
        self.offset_x = (self.screen_width - total_w) / 2
        self.offset_y = (self.screen_height - total_h) / 2

    def init_window(self):
        pygame.init()
        pygame.display.set_caption(f"Maze Engine (GPU) - {self.grid.width}x{self.grid.height}")
        self.surface = pygame.display.set_mode((self.screen_width, self.screen_height)) # Not resizable for Ti
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Consolas", 16)
        self.fit_to_screen()

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                wx = (mx - self.offset_x) / self.cell_size
                wy = (my - self.offset_y) / self.cell_size
                
                if event.y > 0: self.cell_size *= self.zoom_speed
                else: self.cell_size /= self.zoom_speed
                
                self.cell_size = max(0.001, min(100.0, self.cell_size))
                
                self.offset_x = mx - wx * self.cell_size
                self.offset_y = my - wy * self.cell_size
                
            elif event.type == pygame.MOUSEMOTION:
                if pygame.mouse.get_pressed()[0] or pygame.mouse.get_pressed()[2]:
                    self.offset_x += event.rel[0]
                    self.offset_y += event.rel[1]

    def draw_hud(self):
        fps = int(self.clock.get_fps())
        text = f"GPU | FPS: {fps} | Zoom: {self.cell_size:.4f}"
        lbl = self.font.render(text, True, (255, 255, 255))
        self.surface.blit(lbl, (10, 10))

    def run_loop(self):
        gen_iter = self.generator.run() if self.generator else None
        
        # Solver iterator
        solver_iter = None
        if hasattr(self, 'solver_iter'):
            solver_iter = self.solver_iter
        
        while self.running:
            self.handle_input()
            
            # Step Logic
            updated = False
            
            # Generator Step
            if gen_iter and not self.gen_finished:
                try:
                    for _ in range(500): # Reduce steps to keep UI responsive
                        next(gen_iter)
                    updated = True
                except StopIteration:
                    self.gen_finished = True
                    updated = True

            # Solver Step
            if solver_iter:
                try:
                    for _ in range(200): # Solver is CPU heavy, keep budget low
                        next(solver_iter)
                    updated = True
                except StopIteration:
                    solver_iter = None
                    updated = True
                    # If recording, trigger exit cooldown (1.0s @ 60fps ~= 60 frames)
                    if self.recorder.active:
                        self.exit_cooldown = 60

            # Handle Exit Cooldown
            if self.exit_cooldown > 0:
                self.exit_cooldown -= 1
                if self.exit_cooldown == 0:
                    self.running = False

            # If grid changed, upload to GPU
            if updated or self.generator or self.solver: 
                 # Optimization: Always upload for now to be safe, or check dirty flag
                 # Uploading 400MB is heavy. 
                 # Let's trust the 'updated' flag.
                 # Actually, generators update continuously.
                 if updated:
                     self.update_grid_data()
            
            # Render
            self.render_kernel(self.cell_size, self.offset_x, self.offset_y)
            ti.sync()
            
            # Blit to Pygame
            arr = self.pixels.to_numpy()
            # Pygame uses (w, h, 3). Taichi (w, h, 3) fits.
            # But pygame coordinate system? 
            # Pygame surface (0,0) is top left.
            # Taichi field (0,0) is usually ... (0,0).
            # We used (x,y) indexing in kernel.
            pygame.surfarray.blit_array(self.surface, arr)
            
            self.draw_hud()
            
            # Capture Frame Logic
            if self.recorder.active:
                # Recorder expects surface to be correct. taichi blit ensures this.
                self.recorder.capture_frame(self.surface)

            pygame.display.flip()
            self.clock.tick(60)
            
        if self.recorder.active:
            self.recorder.stop()
        pygame.quit()
