import argparse
import sys
import os
import logging

# Ensure project root is in path so we can import 'maze_engine' package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

def main():
    parser = argparse.ArgumentParser(description="Maze Engine: High-performance maze generator")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Generate Command
    gen_parser = subparsers.add_parser("generate", help="Generate a new maze")
    gen_parser.add_argument("--width", type=int, default=100, help="Maze Width")
    gen_parser.add_argument("--height", type=int, default=100, help="Maze Height")
    gen_parser.add_argument("--visual", action="store_true", help="Show visualization")
    gen_parser.add_argument("--headless", action="store_true", help="Run in headless mode (default)")
    gen_parser.add_argument("--gpu", action="store_true", help="Use Taichi GPU Renderer")
    gen_parser.add_argument("--out", type=str, help="Output file path (optional)")
    gen_parser.add_argument("--seed", type=int, default=None, help="Random Seed")
    gen_parser.add_argument("--algo", type=str, default="dfs", choices=["dfs", "prim", "fractal", "organic"], help="Generation Algorithm")
    gen_parser.add_argument("--braid", type=float, default=0.0, help="Braid Factor (0.0 - 1.0)")
    gen_parser.add_argument("--record-events", type=str, help="Save generation events to binary file")
    gen_parser.add_argument("--record", action="store_true", help="Record generation video")

    # Solve Command
    solve_parser = subparsers.add_parser("solve", help="Solve an existing maze")
    solve_parser.add_argument("input_file", help="Path to maze file")
    solve_parser.add_argument("--visual", action="store_true", help="Show visualization")
    solve_parser.add_argument("--headless", action="store_true", help="Run in headless mode (default)")
    solve_parser.add_argument("--gpu", action="store_true", help="Use Taichi GPU Renderer")
    solve_parser.add_argument("--record", action="store_true", help="Record video (auto-fits maze)")
    solve_parser.add_argument("--record-events", type=str, help="Save solver events to binary file")
    solve_parser.add_argument("--algo", type=str, default="bfs", choices=["bfs", "dijkstra", "astar", "biastar", "left", "right", "tremaux", "dfs_solve", "deadend", "swarm"], help="Solver algorithm")
    
    # Replay Command
    replay_parser = subparsers.add_parser("replay", help="Replay an event log")
    replay_parser.add_argument("event_file", help="Path to event log file")
    replay_parser.add_argument("--maze", type=str, help="Optional base maze file to load walls from")
    replay_parser.add_argument("--gpu", action="store_true", help="Use Taichi GPU Renderer")
    replay_parser.add_argument("--record", action="store_true", help="Record video")
    
    # Benchmark Command
    bench_parser = subparsers.add_parser("benchmark", help="Run performance suite")
    bench_parser.add_argument("--size", type=int, default=4600, help="Benchmark size")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    logger = logging.getLogger("maze_engine")
    
    if args.command is None:
        parser.print_help()
        return

    logger.info(f"Running command: {args.command}")
    
    if args.command == "generate":
        # ... (generation logic omitted for brevity, keeping existing)
        # Assuming we don't need to change generate's record logic yet, or should we?
        # User asked for Solving Mazes option specifically.
        logger.info(f"Generating {args.width}x{args.height} maze with {args.algo.upper()}...")
        
        # Create Event Writer if requested
        from maze_engine.core.events import EventWriter
        evt_writer = None
        if args.record_events:
            evt_writer = EventWriter(args.record_events)
            logger.info(f"Recording events to {args.record_events}...")
        
        # Create Grid
        from maze_engine.core.grid import Grid
        grid = Grid(args.width, args.height, event_writer=evt_writer)
        
        # Initialize Algorithm
        generator = None
        if args.algo == "dfs":
            from maze_engine.algo.dfs import RecursiveBacktracker
            generator = RecursiveBacktracker(grid, seed=args.seed)
        elif args.algo == "prim":
            from maze_engine.algo.prim import PrimsAlgorithm
            generator = PrimsAlgorithm(grid, seed=args.seed)
        elif args.algo == "fractal":
            from maze_engine.algo.taichi_gen import TaichiGenAdapter
            print("Using Fractal DFS (Hierarchical GPU Generator)...")
            generator = TaichiGenAdapter(grid, seed=args.seed)
        elif args.algo == "organic":
            from maze_engine.algo.taichi_organic import TaichiOrganicAdapter
            print("Using Organic Walker (Parallel Hunt & Kill)...")
            generator = TaichiOrganicAdapter(grid, seed=args.seed)
            
        # Run Generator
        if args.visual or args.record:
            logger.info("Visual mode enabled - Opening window...")
            if args.gpu:
                from maze_engine.viz.taichi_renderer import TaichiRenderer
                renderer = TaichiRenderer(grid, generator=generator, record=args.record)
            else:
                from maze_engine.viz.renderer import Renderer
                renderer = Renderer(grid, generator=generator, record=args.record)
            
            # Auto-Name Recording
            if args.record:
                import datetime
                if not os.path.exists("recordings"):
                    os.makedirs("recordings")
                
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = f"gen_{args.algo}_{args.width}x{args.height}_{ts}.mp4"
                
                renderer.recorder.output_file = os.path.join("recordings", fname)
                logger.info(f"Recording video to {renderer.recorder.output_file}")

            renderer.init_window()
            renderer.run_loop()
        else:
            logger.info("Headless generation...")
            if generator:
                generator.run_all()
            print("Done.")

        # Post-Processing (Braid)
        if args.braid > 0.0:
            logger.info(f"Braiding maze (factor={args.braid})...")
            from maze_engine.core.complexity import MazePostProcessor
            removed = MazePostProcessor.braid(grid, factor=args.braid, seed=args.seed)
            logger.info(f"Removed {removed} dead ends.")
            
            # Recalculate stats
            stats = MazePostProcessor.calculate_stats(grid)
            logger.info(f"Stats: {stats}")
                
        # Save output if requested
        if args.out:
            logger.info(f"Saving maze to {args.out}...")
            from maze_engine.io.serializer import MazeSerializer
            meta = {"algo": args.algo, "seed": args.seed}
            MazeSerializer.save(grid, args.out, meta=meta)
            MazeSerializer.save(grid, args.out, meta=meta)
            logger.info("Save complete.")

        if evt_writer:
            evt_writer.close()
    
    elif args.command == "solve":
        logger.info(f"Loading {args.input_file}...")
        from maze_engine.io.serializer import MazeSerializer
        grid, meta = MazeSerializer.load(args.input_file)
        logger.info(f"Loaded {grid.width}x{grid.height} maze. Meta: {meta}")
        
        # Instantiate Solver
        from maze_engine.algo.solvers import BFS, AStar, WallFollower, Dijkstra, BiDirectionalAStar, Tremaux, RecursiveDFS, DeadEndFiller, SwarmSolver
        from maze_engine.core.events import EventWriter

        evt_writer = None
        if args.record_events:
            evt_writer = EventWriter(args.record_events)
            evt_writer.write_header(grid.width, grid.height) # Write header manually since grid is already loaded
            logger.info(f"Recording events to {args.record_events}...")
            
        solver = None
        if args.algo == "bfs":
            solver = BFS(grid, event_writer=evt_writer)
        elif args.algo == "dijkstra":
            solver = Dijkstra(grid, event_writer=evt_writer)
        elif args.algo == "astar":
            solver = AStar(grid, event_writer=evt_writer)
        elif args.algo == "left":
            solver = WallFollower(grid, rule="left", event_writer=evt_writer)
        elif args.algo == "right":
            solver = WallFollower(grid, rule="right", event_writer=evt_writer)
        elif args.algo == "biastar":
            solver = BiDirectionalAStar(grid, event_writer=evt_writer)
        elif args.algo == "tremaux":
            solver = Tremaux(grid, event_writer=evt_writer)
        elif args.algo == "dfs_solve":
            solver = RecursiveDFS(grid, event_writer=evt_writer)
        elif args.algo == "deadend":
            solver = DeadEndFiller(grid, event_writer=evt_writer)
        elif args.algo == "swarm":
            solver = SwarmSolver(grid, event_writer=evt_writer)
            
        start = (0, 0)
        end = (grid.width - 1, grid.height - 1)
        
        logger.info(f"Solving with {args.algo.upper()} from {start} to {end}...")

        # Visual OR Record means we need renderer
        if args.visual or args.record:
            if args.gpu:
                from maze_engine.viz.taichi_renderer import TaichiRenderer
                renderer = TaichiRenderer(grid, solver=solver, record=args.record)
            else:
                from maze_engine.viz.renderer import Renderer
                renderer = Renderer(grid, solver=solver, record=args.record)
            
            # Pass iterator
            # Note: TaichiRenderer must support solver_iter
            if hasattr(renderer, 'solver_iter'): 
                 # Wait, python objects dynamic on assignment? Yes.
                 pass
                 
            renderer.solver_iter = solver.run(start, end)
            
            # Auto-Name Recording
            if args.record:
                import datetime
                if not os.path.exists("recordings"):
                    os.makedirs("recordings")
                
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                # Remove path from input file name for cleaner string
                base_name = os.path.basename(args.input_file).replace(".maze", "")
                fname = f"solve_{base_name}_{args.algo}_{ts}.mp4"
                
                renderer.recorder.output_file = os.path.join("recordings", fname)
                logger.info(f"Recording video to {renderer.recorder.output_file}")

            renderer.init_window()
            renderer.run_loop()
            
            # After loop finishes, show path len
            if solver.path:
                logger.info(f"Solution length: {len(solver.path)}")
            else:
                logger.info("No solution found (or visualization closed early).")
        else:
            # Headless Solve
            count = 0
            for _ in solver.run(start, end):
                count += 1
                if count % 1000 == 0:
                    print(f"\rVisited: {solver.visited_count}", end="")
            print(f"\nDone. Path Length: {len(solver.path)}")
            
        if evt_writer:
            print(f"\nSaved events to {args.record_events}")
            evt_writer.close()

    elif args.command == "replay":
        logger.info(f"Replaying {args.event_file}...")
        from maze_engine.core.events import EventReader
        from maze_engine.core.grid import Grid
        from maze_engine.viz.replay import EventAdapter
        from maze_engine.viz.renderer import Renderer
        
        reader = EventReader(args.event_file)
        w, h = reader.read_header()
        logger.info(f"Log Header: {w}x{h}")
        
        if args.maze:
            from maze_engine.io.serializer import MazeSerializer
            logger.info(f"Loading base maze from {args.maze}...")
            # Load grid (ignoring meta for now)
            grid, _ = MazeSerializer.load(args.maze)
            # Ensure grid dims match event file
            if grid.width != w or grid.height != h:
                 logger.warning(f"Maze file dims ({grid.width}x{grid.height}) do not match event file ({w}x{h}). Visuals may be wrong.")
        else:
            grid = Grid(w, h)
            
        adapter = EventAdapter(grid, reader)
        
        if args.gpu:
            from maze_engine.viz.taichi_renderer import TaichiRenderer
            renderer = TaichiRenderer(grid, generator=adapter, record=args.record)
        else:
            renderer = Renderer(grid, generator=adapter, record=args.record)

        if args.record:
            import datetime
            if not os.path.exists("recordings"):
                os.makedirs("recordings")
            
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.basename(args.event_file).replace(".events", "")
            fname = f"replay_{base_name}_{ts}.mp4"
            
            renderer.recorder.output_file = os.path.join("recordings", fname)
            logger.info(f"Recording replay to {renderer.recorder.output_file}")
            
        renderer.init_window()
        renderer.run_loop()
        
        reader.close()

    elif args.command == "benchmark":
        logger.info(f"Running Solver Benchmark Suite (Size: {args.size}x{args.size})...")
        
        # 1. Generate Maze
        from maze_engine.core.grid import Grid
        from maze_engine.algo.dfs import RecursiveBacktracker
        import time
        
        logger.info("Generating base maze (DFS)...")
        t0 = time.time()
        grid = Grid(args.size, args.size)
        gen = RecursiveBacktracker(grid, seed=123)
        gen.run_all()
        logger.info(f"Generation complete in {time.time()-t0:.4f}s")
        
        # 2. Benchmark Solvers
        from maze_engine.algo.solvers import BFS, AStar, WallFollower, Dijkstra
        
        solvers = [
            ("BFS", BFS),
            ("Dijkstra", Dijkstra),
            ("A*", AStar),
            ("WallFollower (Right)", lambda g, ew: WallFollower(g, "right", ew))
        ]
        
        print(f"\n{'ALGORITHM':<20} | {'TIME (s)':<10} | {'PATH LEN':<10} | {'VISITED':<10}")
        print("-" * 60)
        
        start_pos = (0, 0)
        end_pos = (grid.width-1, grid.height-1)
        
        for name, cls in solvers:
            # We need a clean grid for 'visited' tracking? 
            # The solvers use their own 'visited_cells' set, but they might modify grid bits.
            # Grid bits are purely for visual, solvers rely on internal sets generally?
            # Waait, my solvers updated grid bits in previous step.
            # But that shouldn't affect logic of other solvers unless they check those bits.
            # They check `grid.has_wall` (bits 0-3). They don't check VISITED/PATH for validity, only set them.
            # So reusing grid is safe.
            
            # Re-init solver
            s = cls(grid, None) 
            
            t_start = time.time()
            # Run solver to completion
            # Solver.run yields iterator. Consume it.
            # For A*/BFS/Dijkstra, .run() does the whole search? No, it yields.
            # We need to exhaust the iterator.
            count = 0
            for _ in s.run(start_pos, end_pos):
                count += 1
                
            t_end = time.time()
            duration = t_end - t_start
            
            path_len = len(s.path)
            visited_count = len(s.visited_cells)
            
            print(f"{name:<20} | {duration:<10.4f} | {path_len:<10} | {visited_count:<10}")

if __name__ == "__main__":
    main()
