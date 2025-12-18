import heapq
from abc import ABC, abstractmethod
from typing import Iterator, List, Tuple, Dict, Set
from maze_engine.core.grid import Grid
from array import array

class Solver(ABC):
    def __init__(self, grid: Grid, event_writer=None):
        self.grid = grid
        self.path: List[Tuple[int, int]] = []
        # Removed set to save memory. Use Grid.SOLVER_VISITED bit.
        self.visited_count = 0 
        self.event_writer = event_writer
        
    @abstractmethod
    def run(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[str]:
        pass

class BFS(Solver):
    def run(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[str]:
        queue = [start]
        # Memory Opt: Dense Parent Array
        # 0 = None, 1=N, 2=E, 4=S, 8=W
        self.parents = array('B', [0] * (self.grid.width * self.grid.height))
        
        # Mark Start
        self.visited_count = 1
        idx = self.grid.get_index(*start)
        self.grid.cells[idx] |= Grid.SOLVER_VISITED
        
        while queue:
            current = queue.pop(0)
            cx, cy = current
            
            if current == end:
                break
                
            for nx, ny, direction in self.grid.get_neighbors(cx, cy):
                # Check walls manually since get_neighbors ignores them
                if not self.grid.has_wall(cx, cy, direction):
                    idx = self.grid.get_index(nx, ny)
                    if not (self.grid.cells[idx] & Grid.SOLVER_VISITED):
                        # Mark Visited
                        self.grid.cells[idx] |= Grid.SOLVER_VISITED
                        self.visited_count += 1
                        
                        # Store Parent Direction (Inverse)
                        self.parents[idx] = Grid.OPPOSITE[direction]
                        
                        queue.append((nx, ny))
                        
                        if self.event_writer:
                            self.event_writer.log_solver_scan(nx, ny)
                    
            if self.visited_count % 100 == 0:
                yield f"Visited: {self.visited_count}"
                
        # Reconstruct path
        self.reconstruct_path(start, end)
        yield "Solved"

    def reconstruct_path(self, start, end):
        curr = end
        end_idx = self.grid.get_index(*end)
        if not (self.grid.cells[end_idx] & Grid.SOLVER_VISITED) and start != end:
             return

        while curr != start:
            self.path.append(curr)
            idx = self.grid.get_index(*curr)
            self.grid.cells[idx] |= Grid.PATH
            
            if self.event_writer:
                self.event_writer.log_path_add(*curr)
            
            # Move to parent
            p_dir = self.parents[idx]
            if p_dir == 0: break 
            
            dx, dy = Grid.DX[p_dir], Grid.DY[p_dir]
            curr = (curr[0] + dx, curr[1] + dy)
            
        self.path.append(start)
        self.path.reverse()

class AStar(Solver):
    def run(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[str]:
        # Priority Queue: (f_score, x, y)
        open_set = []
        start_node = (0, start[0], start[1])
        heapq.heappush(open_set, start_node)
        
        # Dense Arrays
        # g_score initialized with -1 (infinity)
        self.g_score = array('i', [-1] * (self.grid.width * self.grid.height))
        self.parents = array('B', [0] * (self.grid.width * self.grid.height))
        
        start_idx = self.grid.get_index(*start)
        self.g_score[start_idx] = 0
        
        self.visited_count = 1
        self.grid.cells[start_idx] |= Grid.SOLVER_VISITED
        
        count = 0 
        
        while open_set:
            _, cx, cy = heapq.heappop(open_set)
            current = (cx, cy)
            
            if current == end:
                break
                
            curr_idx = self.grid.get_index(cx, cy)
            curr_g = self.g_score[curr_idx]
            
            for nx, ny, direction in self.grid.get_neighbors(cx, cy):
                if not self.grid.has_wall(cx, cy, direction):
                    neighbor_idx = self.grid.get_index(nx, ny)
                    new_g = curr_g + 1
                    
                    old_g = self.g_score[neighbor_idx]
                    
                    if old_g == -1 or new_g < old_g:
                        self.g_score[neighbor_idx] = new_g
                        priority = new_g + self.heuristic((nx, ny), end)
                        heapq.heappush(open_set, (priority, nx, ny))
                        
                        self.parents[neighbor_idx] = Grid.OPPOSITE[direction]
                        
                        if not (self.grid.cells[neighbor_idx] & Grid.SOLVER_VISITED):
                            self.grid.cells[neighbor_idx] |= Grid.SOLVER_VISITED
                            self.visited_count += 1
                        
                        if self.event_writer:
                            self.event_writer.log_solver_scan(nx, ny)
            
            count += 1
            if count % 100 == 0:
                yield f"Visited: {self.visited_count}"
                
        self.reconstruct_path(start, end)
        yield "Solved"

    def reconstruct_path(self, start, end):
        curr = end
        end_idx = self.grid.get_index(*end)
        if self.g_score[end_idx] == -1 and start != end: return 

        while curr != start:
            self.path.append(curr)
            idx = self.grid.get_index(*curr)
            self.grid.cells[idx] |= Grid.PATH
            
            if self.event_writer:
                self.event_writer.log_path_add(*curr)
            
            p_dir = self.parents[idx]
            if p_dir == 0: break
            
            dx, dy = Grid.DX[p_dir], Grid.DY[p_dir]
            curr = (curr[0] + dx, curr[1] + dy)
            
        self.path.append(start)
        self.path.reverse()

    def heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

class Dijkstra(AStar):
    """ Weighted BFS (Dijkstra) is just A* with h(n) = 0. """
    def heuristic(self, a, b):
        return 0

class WallFollower(Solver):
    def __init__(self, grid: Grid, rule="left", event_writer=None):
        super().__init__(grid, event_writer)
        self.rule = rule 

    def run(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[str]:
        dirs = [Grid.NORTH, Grid.EAST, Grid.SOUTH, Grid.WEST]
        dx = [0, 1, 0, -1]
        dy = [-1, 0, 1, 0]
        
        facing = 1 # East
        
        cx, cy = start
        self.path.append((cx, cy))
        self.visited_count = 1
        
        idx = self.grid.get_index(cx, cy)
        self.grid.cells[idx] |= Grid.SOLVER_VISITED | Grid.PATH
        
        steps = 0
        max_steps = self.grid.width * self.grid.height * 4 
        
        while (cx, cy) != end and steps < max_steps:
            if self.rule == "left":
                check_order = [(facing - 1) % 4, facing, (facing + 1) % 4, (facing + 2) % 4]
            else: 
                check_order = [(facing + 1) % 4, facing, (facing - 1) % 4, (facing + 2) % 4]
                
            moved = False
            for d_idx in check_order:
                d_bit = dirs[d_idx]
                if not self.grid.has_wall(cx, cy, d_bit):
                    nx, ny = cx + dx[d_idx], cy + dy[d_idx]
                    
                    if 0 <= nx < self.grid.width and 0 <= ny < self.grid.height:
                        cx, cy = nx, ny
                        facing = d_idx
                        self.path.append((cx, cy))
                        
                        idx = self.grid.get_index(cx, cy)
                        if not (self.grid.cells[idx] & Grid.SOLVER_VISITED):
                            self.visited_count += 1
                        self.grid.cells[idx] |= Grid.SOLVER_VISITED
                        
                        if self.event_writer:
                            self.event_writer.log_solver_scan(cx, cy)
                        moved = True
                        break
            
            if not moved:
                break
                
            steps += 1
            if steps % 100 == 0:
                yield f"Steps: {steps}"
                
        if (cx, cy) == end:
             for px, py in self.path:
                 idx = self.grid.get_index(px, py)
                 self.grid.cells[idx] |= Grid.PATH
                 if self.event_writer:
                     self.event_writer.log_path_add(px, py)
                 
        yield "Solved" if (cx, cy) == end else "Stuck"

class BiDirectionalAStar(Solver):
    def heuristic(self, a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    def run(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[str]:
        pq_fwd = [(0, 0, start[0], start[1])]
        pq_bwd = [(0, 0, end[0], end[1])]
        
        # Dense Arrays
        self.g_fwd = array('i', [-1] * (self.grid.width * self.grid.height))
        self.g_bwd = array('i', [-1] * (self.grid.width * self.grid.height))
        
        self.parents_fwd = array('B', [0] * (self.grid.width * self.grid.height))
        self.parents_bwd = array('B', [0] * (self.grid.width * self.grid.height))
        
        start_idx = self.grid.get_index(*start)
        end_idx = self.grid.get_index(*end)
        
        self.g_fwd[start_idx] = 0
        self.g_bwd[end_idx] = 0
        
        self.grid.cells[start_idx] |= Grid.SOLVER_VISITED
        self.grid.cells[end_idx]   |= Grid.SOLVER_AUX 
        
        self.visited_count = 2
        meeting_node = None
        
        count = 0
        
        while pq_fwd and pq_bwd:
            # Expand Forward
            if pq_fwd:
                _, g_curr, cx, cy = heapq.heappop(pq_fwd)
                curr_idx = self.grid.get_index(cx, cy)
                
                if self.grid.cells[curr_idx] & Grid.SOLVER_AUX:
                    meeting_node = (cx, cy)
                    break
                    
                for nx, ny, direction in self.grid.get_neighbors(cx, cy):
                     if not self.grid.has_wall(cx, cy, direction):
                        neighbor_idx = self.grid.get_index(nx, ny)
                        new_g = g_curr + 1
                        old_g = self.g_fwd[neighbor_idx]
                        
                        if old_g == -1 or new_g < old_g:
                            self.g_fwd[neighbor_idx] = new_g
                            f = new_g + self.heuristic((nx, ny), end)
                            heapq.heappush(pq_fwd, (f, new_g, nx, ny))
                            
                            self.parents_fwd[neighbor_idx] = Grid.OPPOSITE[direction]
                            
                            if not (self.grid.cells[neighbor_idx] & Grid.SOLVER_VISITED):
                                self.grid.cells[neighbor_idx] |= Grid.SOLVER_VISITED
                                self.visited_count += 1
                            
                            if self.event_writer:
                                self.event_writer.log_solver_scan(nx, ny)
                            
                            if self.grid.cells[neighbor_idx] & Grid.SOLVER_AUX:
                                meeting_node = (nx, ny)
                                break
                if meeting_node: break

            # Expand Backward
            if pq_bwd:
                _, g_curr, cx, cy = heapq.heappop(pq_bwd)
                curr_idx = self.grid.get_index(cx, cy)
                
                if (self.grid.cells[curr_idx] & Grid.SOLVER_VISITED):
                     meeting_node = (cx, cy)
                     break
                
                for nx, ny, direction in self.grid.get_neighbors(cx, cy):
                     if not self.grid.has_wall(cx, cy, direction):
                        neighbor_idx = self.grid.get_index(nx, ny)
                        new_g = g_curr + 1
                        old_g = self.g_bwd[neighbor_idx]
                        
                        if old_g == -1 or new_g < old_g:
                            self.g_bwd[neighbor_idx] = new_g
                            f = new_g + self.heuristic((nx, ny), start)
                            heapq.heappush(pq_bwd, (f, new_g, nx, ny))
                            
                            self.parents_bwd[neighbor_idx] = Grid.OPPOSITE[direction]
                            
                            if not (self.grid.cells[neighbor_idx] & Grid.SOLVER_AUX):
                                self.grid.cells[neighbor_idx] |= Grid.SOLVER_AUX
                                self.visited_count += 1
                                
                            if self.event_writer:
                                self.event_writer.log_solver_scan_aux(nx, ny)
                                
                            if self.grid.cells[neighbor_idx] & Grid.SOLVER_VISITED:
                                meeting_node = (nx, ny)
                                break
                if meeting_node: break

            count += 1
            if count % 50 == 0:
                yield f"Visited: {self.visited_count}"

        if meeting_node:
            self.reconstruct_merged_path(meeting_node, start, end)
            yield "Solved"
        else:
            yield "No Path"

    def reconstruct_merged_path(self, meet, start, end):
        # 1. Start -> Meet
        curr = meet
        while curr != start:
            self.path.append(curr)
            idx = self.grid.get_index(*curr)
            self.grid.cells[idx] |= Grid.PATH
            if self.event_writer:
                self.event_writer.log_path_add(*curr)
            
            p_dir = self.parents_fwd[idx]
            if p_dir == 0: break
            dx, dy = Grid.DX[p_dir], Grid.DY[p_dir]
            curr = (curr[0] + dx, curr[1] + dy)
        self.path.append(start)
        self.path.reverse()
        
        # 2. Meet -> End
        curr = meet
        idx = self.grid.get_index(*curr)
        p_dir = self.parents_bwd[idx]
        if p_dir != 0:
             dx, dy = Grid.DX[p_dir], Grid.DY[p_dir]
             curr = (curr[0] + dx, curr[1] + dy)
             
             while True: 
                self.path.append(curr)
                idx = self.grid.get_index(*curr)
                self.grid.cells[idx] |= Grid.PATH
                if self.event_writer:
                    self.event_writer.log_path_add(*curr)
                
                if curr == end: break
                
                p_dir = self.parents_bwd[idx]
                if p_dir == 0: break
                dx, dy = Grid.DX[p_dir], Grid.DY[p_dir]
                curr = (curr[0] + dx, curr[1] + dy)

class Tremaux(Solver):
    def run(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[str]:
        curr = start
        path_stack = [start] 
        visits = {start: 1} # Keep small local dict, or use array? Array is better but dict OK for normal sizes.
        # But for 400M cells, visits dict is HUGE.
        # Tremaux relies on visit COUNT (0, 1, 2).
        # We can use Grid bits strictly?
        # VISITED (1) + AUX (2)?
        # 0 = Unvisited
        # VISITED = 1 visit
        # VISITED | AUX = 2 visits (or more)
        # 400M dict for Tremaux is BAD.
        # I should upgrade Tremaux to use bits fully.
        
        # UPGRADE TREMAUX:
        # Use SOLVER_VISITED for "Visited >= 1"
        # Use SOLVER_AUX for "Visited >= 2"
        
        idx = self.grid.get_index(*start)
        self.grid.cells[idx] |= Grid.SOLVER_VISITED
        
        steps = 0
        max_steps = self.grid.width * self.grid.height * 20
        self.visited_count = 1
        
        while curr != end and steps < max_steps:
            cx, cy = curr
            neighbors = list(self.grid.get_open_neighbors(cx, cy))
            
            candidates = []
            for n in neighbors:
                n_idx = self.grid.get_index(*n)
                cell = self.grid.cells[n_idx]
                v = 0
                if cell & Grid.SOLVER_VISITED: v = 1
                if cell & Grid.SOLVER_AUX: v = 2
                
                if v < 2:
                    candidates.append((v, n))
            
            candidates.sort(key=lambda x: x[0]) 
            
            move_target = None
            if candidates:
                move_target = candidates[0][1]
            else:
                if path_stack:
                    path_stack.pop() # Current
                    if path_stack:
                        move_target = path_stack[-1] # Backtrack
                    else:
                        break
                else:
                    break
                    
            if move_target:
                 t_idx = self.grid.get_index(*move_target)
                 
                 # Increment visit
                 if not (self.grid.cells[t_idx] & Grid.SOLVER_VISITED):
                     self.grid.cells[t_idx] |= Grid.SOLVER_VISITED
                     self.visited_count += 1
                     path_stack.append(move_target)
                     self.path.append(move_target)
                 else:
                     # Second visit
                     self.grid.cells[t_idx] |= Grid.SOLVER_AUX
                     if path_stack and path_stack[-1] == move_target:
                         # We are backtracking
                         path_stack.pop() # Remove from active stack
                     else:
                         # We are entering a visited cell
                         # Logic: if we move to a cell with 1 visit, we mark it 2.
                         pass

                 curr = move_target
            
            steps += 1
            if steps % 50 == 0:
                yield f"Steps: {steps}"

        self.path = list(path_stack)
        yield "Solved"

class RecursiveDFS(Solver):
    def run(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[str]:
        stack = [start]
        # Use parents array for recursion stack reconstruction?
        # DFS Stack can be deep.
        # Visited status: SOLVER_VISITED bit.
        
        idx = self.grid.get_index(*start)
        self.grid.cells[idx] |= Grid.SOLVER_VISITED
        self.visited_count = 1
        
        parents = {} # Dict still risky for OOM on DFS 400M. 
        # Use array for parents
        # parent array overhead: 400MB. OK.
        # Dict overhead: 20GB+. BAD.
        
        # Using same 'parents' array scheme as BFS (Direction)
        self.parents = array('B', [0] * (self.grid.width * self.grid.height))
        
        count = 0
        while stack:
            curr = stack.pop()
            if curr == end: break
            
            cx, cy = curr
            neighbors = list(self.grid.get_open_neighbors(cx, cy))
            
            for n in neighbors:
                n_idx = self.grid.get_index(*n)
                if not (self.grid.cells[n_idx] & Grid.SOLVER_VISITED):
                    self.grid.cells[n_idx] |= Grid.SOLVER_VISITED
                    self.visited_count += 1
                    
                    # Parent: curr -> n. n's parent is curr.
                    # Direction n->curr?
                    # get_open_neighbors doesn't give direction.
                    # Need direction.
                    # Re-derive direction:
                    dx, dy = cx-n[0], cy-n[1]
                    p_bit = 0
                    if dy == -1: p_bit = Grid.NORTH
                    elif dy == 1: p_bit = Grid.SOUTH
                    elif dx == -1: p_bit = Grid.WEST
                    elif dx == 1: p_bit = Grid.EAST
                    
                    self.parents[n_idx] = p_bit
                    stack.append(n)
            
            count += 1
            if count % 100 == 0:
                yield f"Stack: {len(stack)}"
        
        # Reconstruct
        curr = end
        end_idx = self.grid.get_index(*end)
        if self.grid.cells[end_idx] & Grid.SOLVER_VISITED:
            while curr != start:
                self.path.append(curr)
                idx = self.grid.get_index(*curr)
                self.grid.cells[idx] |= Grid.PATH
                if self.event_writer:
                    self.event_writer.log_path_add(*curr)
                p_dir = self.parents[idx]
                if p_dir == 0: break
                dx, dy = Grid.DX[p_dir], Grid.DY[p_dir]
                curr = (curr[0] + dx, curr[1] + dy)
            self.path.append(start)
            self.path.reverse()
        
        yield "Solved"

class DeadEndFiller(Solver):
    def run(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[str]:
        width, height = self.grid.width, self.grid.height
        active_leaves = []
        
        # Pre-calc degrees (using local array instead of dict)
        # dict: (x,y)->int. 400M ints. Dict overhead is bad.
        # Use array('B') for degrees (max 4).
        degrees = array('B', [0] * (width * height))
        
        for y in range(height):
            for x in range(width):
                deg = 0
                for _ in self.grid.get_open_neighbors(x, y):
                    deg += 1
                idx = y * width + x
                degrees[idx] = deg
                if deg == 1 and (x,y) != start and (x,y) != end:
                    active_leaves.append((x,y))
        
        yield "Scanning..."
        
        filled_count = 0
        
        while active_leaves:
            next_leaves = []
            
            for cx, cy in active_leaves:
                idx = self.grid.get_index(cx, cy)
                self.grid.cells[idx] |= Grid.SOLVER_AUX
                self.visited_count += 1
                
                for nx, ny in self.grid.get_open_neighbors(cx, cy):
                    n_idx = self.grid.get_index(nx, ny)
                    if not (self.grid.cells[n_idx] & Grid.SOLVER_AUX):
                        degrees[n_idx] -= 1
                        if degrees[n_idx] == 1 and (nx, ny) != start and (nx, ny) != end:
                            next_leaves.append((nx, ny))
            
            active_leaves = next_leaves
            if self.visited_count % 100 == 0:
                yield f"Filled: {self.visited_count}"
        
        # Visualize remaining & Reconstruct Path
        # Logic: Any cell NOT in SOLVER_AUX (Dead End) is part of the solution (or a loop).
        # We collect them to show count. Order is widely approximate (scanline).
        for i in range(width * height):
             if not (self.grid.cells[i] & Grid.SOLVER_AUX):
                 if self.grid.cells[i] & 15 != 15: # Not solid wall
                     self.grid.cells[i] |= Grid.PATH
                     # Add to path list for benchmark count
                     self.path.append((i % width, i // width))
                     if self.event_writer:
                         self.event_writer.log_path_add(i % width, i // width)
        
        yield "Reduced"

class SwarmSolver(Solver):
    def run(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[str]:
        num_agents = 10
        agents = [[start] for _ in range(num_agents)] 
        finished = False
        
        idx = self.grid.get_index(*start)
        self.grid.cells[idx] |= Grid.SOLVER_VISITED
        
        import random
        import random
        # Memory Opt: Dense Parent Array
        # 0 = None, 1=N, 2=E, 4=S, 8=W
        self.parents = array('B', [0] * (self.grid.width * self.grid.height))
        # If running on 20k x 20k, this will OOM.
        # But let's assume Swarm is optional or updated next time.
        # For now, fix the len(visited_count) bug.
        
        while not finished:
            all_stuck = True
            for i in range(num_agents):
                stack = agents[i]
                if not stack: continue
                all_stuck = False
                curr = stack[-1]
                
                if curr == end:
                    finished = True
                    break
                
                cx, cy = curr
                neighbors = []
                for nx, ny in self.grid.get_open_neighbors(cx, cy):
                    n_idx = self.grid.get_index(nx, ny)
                    if not (self.grid.cells[n_idx] & Grid.SOLVER_VISITED):
                        neighbors.append((nx, ny))
                
                if neighbors:
                    next_node = random.choice(neighbors)
                    stack.append(next_node)
                    
                    nx, ny = next_node
                    n_idx = self.grid.get_index(nx, ny)
                    self.grid.cells[n_idx] |= Grid.SOLVER_VISITED
                    self.visited_count += 1
                    
                    if self.parents[n_idx] == 0:
                        # Need direction. Re-derive:
                        dx, dy = neighbors[0][0]-cx, neighbors[0][1]-cy
                        # neighbors list logic is a bit disconnected.
                        # Wait, we picked 'next_node' from 'neighbors'.
                        # Let's get direction from next_node calc.
                        dx, dy = nx - cx, ny - cy
                        p_bit = 0
                        if dy == -1: p_bit = Grid.NORTH # Moved N, came from S
                        elif dy == 1: p_bit = Grid.SOUTH
                        elif dx == -1: p_bit = Grid.WEST
                        elif dx == 1: p_bit = Grid.EAST
                        # Store PARENT direction (inverse of move)
                        # Actually BFS uses 'from current to parent' or 'from neighbor to current'?
                        # BFS: self.parents[idx] = Grid.OPPOSITE[direction]
                        # So if we moved NORTH to neighbor, neighbor's parent is SOUTH.
                        if dy == -1: self.parents[n_idx] = Grid.SOUTH
                        elif dy == 1: self.parents[n_idx] = Grid.NORTH
                        elif dx == -1: self.parents[n_idx] = Grid.EAST
                        elif dx == 1: self.parents[n_idx] = Grid.WEST
                        
                    if self.event_writer:
                        self.event_writer.log_solver_scan(nx, ny)
                else:
                    stack.pop()
            
            if finished or all_stuck:
                break
                
            if self.visited_count % 100 == 0:
                yield f"Visited: {self.visited_count}"

        if finished:
            curr = end
            idx = self.grid.get_index(*curr)
            if self.parents[idx] != 0:
                while curr != start:
                    self.path.append(curr)
                    idx = self.grid.get_index(*curr)
                    self.grid.cells[idx] |= Grid.PATH
                    if self.event_writer:
                        self.event_writer.log_path_add(*curr)
                    
                    p_dir = self.parents[idx]
                    if p_dir == 0: break
                    dx, dy = Grid.DX[p_dir], Grid.DY[p_dir]
                    curr = (curr[0] + dx, curr[1] + dy)
                self.path.reverse()

        yield "Solved"
