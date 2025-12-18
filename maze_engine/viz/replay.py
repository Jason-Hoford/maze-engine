from typing import Iterator, Set, Tuple, List
from maze_engine.core.grid import Grid
from maze_engine.core.events import EventReader, EVT_VISIT, EVT_CARVE, EVT_PATH_ADD, EVT_PATH_REM, EVT_SOLVER_SCAN, EVT_SOLVER_SCAN_AUX

class EventAdapter:
    """
    Adapts an EventReader stream to look like a Generator/Solver for the Renderer.
    Applies changes to the Grid as it iterates.
    """
    def __init__(self, grid: Grid, reader: EventReader):
        self.grid = grid
        self.reader = reader
        
        # Mock Solver interface
        self.visited_count = 0
        self.path: List[Tuple[int, int]] = []
        
    def run(self) -> Iterator[str]:
        count = 0
        for type_code, data in self.reader.stream_events():
            count += 1
            
            if type_code == EVT_VISIT:
                x, y = data
                idx = self.grid.get_index(x, y)
                self.grid.cells[idx] |= Grid.VISITED
                
            elif type_code == EVT_CARVE:
                x, y, d = data
                self.grid.carve_path(x, y, d)
                
            elif type_code == EVT_SOLVER_SCAN:
                x, y = data
                idx = self.grid.get_index(x, y)
                self.grid.cells[idx] |= Grid.SOLVER_VISITED
                self.visited_count += 1
                
            elif type_code == EVT_SOLVER_SCAN_AUX:
                x, y = data
                idx = self.grid.get_index(x, y)
                self.grid.cells[idx] |= Grid.SOLVER_VISITED | Grid.SOLVER_AUX # Mark visited AND aux (Red)
                self.visited_count += 1
                
            elif type_code == EVT_PATH_ADD:
                x, y = data
                idx = self.grid.get_index(x, y)
                self.grid.cells[idx] |= Grid.PATH
                
            elif type_code == EVT_PATH_REM:
                x, y = data
                idx = self.grid.get_index(x, y)
                self.grid.cells[idx] &= ~Grid.PATH
                
            # Yield every N steps
            if count % 50 == 0:
                yield "Replay"
                
        yield "Done"
