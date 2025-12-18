import os
import pygame
import cv2
import numpy as np
from datetime import datetime

class VideoRecorder:
    def __init__(self, active=False, output_file=None, fps=30):
        self.active = active
        self.output_file = output_file
        self.fps = fps
        self.writer = None
        self.frame_size = None
        self.frame_count = 0
        
        if self.active and not self.output_file:
            # Generate filename if not provided
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"maze_solve_{ts}.mp4"
            
            # Check for recordings dir
            if os.path.exists("recordings"):
                self.output_file = os.path.join("recordings", fname)
            else:
                self.output_file = fname

    def capture_frame(self, surface: pygame.Surface):
        if not self.active:
            return
            
        # Get dimensions
        width, height = surface.get_size()
        
        # Initialize writer on first frame
        if self.writer is None:
            self.frame_size = (width, height)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.writer = cv2.VideoWriter(self.output_file, fourcc, self.fps, self.frame_size)
            print(f"Recording started: {self.output_file}")
            
        view = pygame.surfarray.array3d(surface)
        # view is (width, height, 3) RGB
        # We need (height, width, 3) BGR
        
        # Transpose to (height, width, 3)
        frame = np.transpose(view, (1, 0, 2))
        
        # Convert RGB to BGR
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        self.writer.write(frame)
        self.frame_count += 1

    def stop(self):
        if self.writer:
            self.writer.release()
            print(f"Video saved: {self.output_file} ({self.frame_count} frames)")
            self.writer = None
