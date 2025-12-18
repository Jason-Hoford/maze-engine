from abc import ABC, abstractmethod
from typing import Iterator, Tuple
from maze_engine.core.grid import Grid

class Generator(ABC):
    def __init__(self, grid: Grid, seed: int = None):
        self.grid = grid
        self.seed = seed
        self.step_count = 0
        
    @abstractmethod
    def run(self) -> Iterator[str]:
        """
        Yields status strings or progress updates.
        The actual grid modifications happen in-place on self.grid.
        """
        pass

    def run_all(self):
        """Helper to run the generator to completion."""
        for _ in self.run():
            pass
