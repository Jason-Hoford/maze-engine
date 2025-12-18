import pygame
import math
from maze_engine.core.grid import Grid

class Renderer:
    COLOR_BG = (10, 10, 10)
    COLOR_WALL = (200, 200, 200)
    COLOR_VISITED = (60, 100, 160)# Blue tint
    COLOR_SOLUTION = (255, 215, 0)# Gold

    def __init__(self, grid: Grid, generator=None, solver=None, width=1280, height=720, record=False):
        self.grid = grid
        self.generator = generator
        self.solver = solver
        self.screen_width = width
        self.screen_height = height
        
        # Camera
        self.cell_size = 20.0  # Pixels per cell
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom_speed = 1.1

        # Tools
        from maze_engine.viz.recorder import VideoRecorder
        from maze_engine.viz.lod import LODSystem
        self.recorder = VideoRecorder(active=record)
        self.lod = LODSystem(grid)
        
        # Performance
        self.font = None
        self.running = True
        self.clock = None
        self.surface = None
        self.gen_finished = False

    def fit_to_screen(self):
        """Auto-adjust zoom and pan to fit the entire grid on screen with padding."""
        padding = 40
        available_w = self.screen_width - (padding * 2)
        available_h = self.screen_height - (padding * 2)
        
        zoom_x = available_w / self.grid.width
        zoom_y = available_h / self.grid.height
        
        # Taking minimum zoom to fit both dimensions
        self.cell_size = min(zoom_x, zoom_y)
        
        # Center
        total_maze_w = self.grid.width * self.cell_size
        total_maze_h = self.grid.height * self.cell_size
        
        self.offset_x = (self.screen_width - total_maze_w) / 2
        self.offset_y = (self.screen_height - total_maze_h) / 2

    def init_window(self):
        pygame.init()
        pygame.display.set_caption(f"Maze Justice - {self.grid.width}x{self.grid.height}")
        self.surface = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Consolas", 16)
        
        # Initial fit
        self.fit_to_screen()

    def world_to_screen(self, wx, wy):
        sx = wx * self.cell_size + self.offset_x
        sy = wy * self.cell_size + self.offset_y
        return sx, sy

    def screen_to_world(self, sx, sy):
        wx = (sx - self.offset_x) / self.cell_size
        wy = (sy - self.offset_y) / self.cell_size
        return int(wx), int(wy)

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.VIDEORESIZE:
                self.screen_width, self.screen_height = event.w, event.h
                
            elif event.type == pygame.MOUSEWHEEL:
                # Zoom towards mouse
                mx, my = pygame.mouse.get_pos()
                
                # World coord before zoom
                wx = (mx - self.offset_x) / self.cell_size
                wy = (my - self.offset_y) / self.cell_size
                
                old_zoom = self.cell_size
                if event.y > 0:
                    self.cell_size *= self.zoom_speed
                else:
                    self.cell_size /= self.zoom_speed
                
                # Clamp zoom
                self.cell_size = max(0.001, min(100.0, self.cell_size))
                
                # Adjust offset to keep mouse at same world coord
                self.offset_x = mx - wx * self.cell_size
                self.offset_y = my - wy * self.cell_size
                
            elif event.type == pygame.MOUSEMOTION:
                if pygame.mouse.get_pressed()[0] or pygame.mouse.get_pressed()[2]: # Left or Right drag
                    self.offset_x += event.rel[0]
                    self.offset_y += event.rel[1]

    def draw_grid(self):
        self.surface.fill(self.COLOR_BG)
        
        # Culling: Calculate visible cell range
        start_x = int((-self.offset_x) / self.cell_size)
        start_y = int((-self.offset_y) / self.cell_size)
        end_x = int((self.screen_width - self.offset_x) / self.cell_size) + 1
        end_y = int((self.screen_height - self.offset_y) / self.cell_size) + 1
        
        # Clamp to grid bounds
        start_x = max(0, start_x)
        start_y = max(0, start_y)
        end_x = min(self.grid.width, end_x)
        end_y = min(self.grid.height, end_y)
        
        draw_walls = self.cell_size > 4.0
        
        # 1. Draw Grid Base & Overlay (Pass 1 - Backgrounds)
        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                idx = y * self.grid.width + x
                cell = self.grid.cells[idx]
                
                px = int(x * self.cell_size + self.offset_x)
                py = int(y * self.cell_size + self.offset_y)
                size = int(self.cell_size) + 1 
                
                # Base Maze Visited
                if cell & Grid.VISITED:
                    color = self.COLOR_VISITED
                    pygame.draw.rect(self.surface, color, (px, py, size, size))
                    
                # Solver Visited (Overlay)
                if self.solver and (cell & Grid.SOLVER_VISITED):
                    pygame.draw.rect(self.surface, (100, 150, 200), (px, py, size, size))
        
        # 2. Draw Walls (Pass 2 - Foreground)
        if draw_walls:
            for y in range(start_y, end_y):
                for x in range(start_x, end_x):
                    idx = y * self.grid.width + x
                    cell = self.grid.cells[idx]
                    
                    px = int(x * self.cell_size + self.offset_x)
                    py = int(y * self.cell_size + self.offset_y)
                    size = int(self.cell_size) + 1 
                    
                    wall_color = self.COLOR_WALL
                    if cell & Grid.SOUTH:
                        pygame.draw.line(self.surface, wall_color, (px, py + size), (px + size, py + size), 1)
                    if cell & Grid.EAST:
                        pygame.draw.line(self.surface, wall_color, (px + size, py), (px + size, py + size), 1)
                    
                    if y == 0 and (cell & Grid.NORTH):
                        pygame.draw.line(self.surface, wall_color, (px, py), (px + size, py), 1)
                    if x == 0 and (cell & Grid.WEST):
                        pygame.draw.line(self.surface, wall_color, (px, py), (px, py + size), 1)
        
        # Draw Solver Path (Gold) - High priority
        if self.solver and self.solver.path:
            for (px, py) in self.solver.path:
                if start_x <= px < end_x and start_y <= py < end_y:
                    sx, sy = self.world_to_screen(px, py)
                    size = int(self.cell_size) + 1
                    pygame.draw.rect(self.surface, self.COLOR_SOLUTION, (sx, sy, size, size))

    def draw_hud(self):
        fps = int(self.clock.get_fps())
        cells = self.grid.width * self.grid.height
        rec_status = "REC" if self.recorder.active else ""
        status = "Done" if self.gen_finished else "Running"
        info = [
            f"FPS: {fps}",
            f"Size: {self.grid.width}x{self.grid.height} ({cells:,})",
            f"Zoom: {self.cell_size:.2f}",
            f"Status: {status}",
            rec_status
        ]
        
        for i, text in enumerate(info):
            lbl = self.font.render(text, True, (255, 255, 255))
            self.surface.blit(lbl, (10, 10 + i * 20))

    def run_loop(self):
        gen_iter = None
        if self.generator:
            gen_iter = self.generator.run()
        
        solver_iter = None
        if hasattr(self, 'solver_iter'):
            solver_iter = self.solver_iter

        while self.running:
            self.handle_input()
            
            # Step Generator
            if gen_iter and not self.gen_finished:
                try:
                    steps = 1000 
                    for _ in range(steps):
                        next(gen_iter)
                except StopIteration:
                    self.gen_finished = True
                    
            # Step Solver
            if solver_iter: 
                 try:
                    steps = 100 
                    for _ in range(steps):
                        next(solver_iter)
                 except StopIteration:
                    solver_iter = None

            self.draw_grid()
            self.draw_hud()
            pygame.display.flip()
            
            if self.recorder.active:
                self.recorder.capture_frame(self.surface)
                
            self.clock.tick(60)
        
        self.recorder.stop()
        pygame.quit()
