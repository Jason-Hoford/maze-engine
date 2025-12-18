import sys
import os

# Ensure the maze_engine package is in the python path
# This allows 'pytest' to be run from the root directory or inside tests/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
