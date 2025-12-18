import struct
from typing import Iterator, Tuple

# Event Types
EVT_INIT = 0x01
EVT_VISIT = 0x02
EVT_CARVE = 0x03
EVT_PATH_ADD = 0x04
EVT_PATH_REM = 0x05
EVT_SOLVER_SCAN = 0x06
EVT_SOLVER_SCAN_AUX = 0x07

class EventWriter:
    def __init__(self, filename: str):
        self.filename = filename
        self.file = open(filename, "wb")
        
    def write_header(self, width: int, height: int):
        # Header: Magic "MAZELOG" + Width (4b) + Height (4b)
        self.file.write(b"MAZELOG")
        self.file.write(struct.pack(">II", width, height))
        
    def log_visit(self, x: int, y: int):
        # 1 byte type + 4 byte X + 4 byte Y = 9 bytes
        # Optimization: We could use 2 bytes for coords if < 65536. 
        # But for 20k x 20k we need 2 bytes (short) is enough (0-65535).
        # Let's use 'H' (unsigned short) for coordinate packing to save space.
        # Maze is max 20,000, so 'H' (65535) is perfect.
        data = struct.pack(">BHH", EVT_VISIT, x, y)
        self.file.write(data)

    def log_solver_scan(self, x: int, y: int):
        data = struct.pack(">BHH", EVT_SOLVER_SCAN, x, y)
        self.file.write(data)

    def log_solver_scan_aux(self, x: int, y: int):
        data = struct.pack(">BHH", EVT_SOLVER_SCAN_AUX, x, y)
        self.file.write(data)
        
    def log_carve(self, x: int, y: int, direction: int):
        # 1 byte type + 2b X + 2b Y + 1b Dir
        data = struct.pack(">BHHB", EVT_CARVE, x, y, direction)
        self.file.write(data)
        
    def log_path_add(self, x: int, y: int):
        data = struct.pack(">BHH", EVT_PATH_ADD, x, y)
        self.file.write(data)

    def log_path_rem(self, x: int, y: int):
        data = struct.pack(">BHH", EVT_PATH_REM, x, y)
        self.file.write(data)
        
    def close(self):
        if self.file:
            self.file.close()
            self.file = None

class EventReader:
    def __init__(self, filename: str):
        self.filename = filename
        self.file = open(filename, "rb")
        self.width = 0
        self.height = 0
        
    def read_header(self) -> Tuple[int, int]:
        magic = self.file.read(7)
        if magic != b"MAZELOG":
            raise ValueError("Invalid event log file")
        data = self.file.read(8)
        self.width, self.height = struct.unpack(">II", data)
        return self.width, self.height
        
    def stream_events(self) -> Iterator[Tuple[int, Tuple]]:
        # Read chunks or one by one. One by one is easier for Python generator.
        while True:
            type_byte = self.file.read(1)
            if not type_byte:
                break
                
            type_code = ord(type_byte)
            
            if type_code == EVT_VISIT:
                data = self.file.read(4) # 2 shorts
                x, y = struct.unpack(">HH", data)
                yield (type_code, (x, y))
                
            elif type_code == EVT_CARVE:
                data = self.file.read(5) # 2 shorts + 1 byte
                x, y, d = struct.unpack(">HHB", data)
                yield (type_code, (x, y, d))
                
            elif type_code == EVT_PATH_ADD:
                data = self.file.read(4)
                x, y = struct.unpack(">HH", data)
                yield (type_code, (x, y))
                
            elif type_code == EVT_PATH_REM:
                data = self.file.read(4)
                x, y = struct.unpack(">HH", data)
                yield (type_code, (x, y))

            elif type_code == EVT_SOLVER_SCAN:
                data = self.file.read(4)
                x, y = struct.unpack(">HH", data)
                yield (type_code, (x, y))

            elif type_code == EVT_SOLVER_SCAN_AUX:
                data = self.file.read(4)
                x, y = struct.unpack(">HH", data)
                yield (type_code, (x, y))
                
    def close(self):
        if self.file:
            self.file.close()
            self.file = None
