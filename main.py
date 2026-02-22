from collections.abc import Sequence
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import math
from fractions import Fraction
from abc import ABC, abstractmethod
import os
from turtle import width
from typing import Literal
from itertools import combinations, permutations

# --- 0. Constants or at least Loose Constants ---

NUMBER: str = "0123456789"
very_negative = Fraction(-2147483647, 1)
threshold = Fraction(-65535, 1)

# --- 1. Cell Template & Implementations ---

class Cell(ABC):
    """
    Template class for all cells.
    """
    def __init__(self, texture_path="default.png"):
        self.texture_path = texture_path
        self.image = None  # Placeholder for the tk image object
        
    @property
    @abstractmethod
    def document(self) -> str:
        """String describing what the cell does."""
        pass

    @abstractmethod
    def result(self, coverage: Fraction) -> Fraction:
        """
        Takes the coverage (0 to 1) and returns a score.
        """
        pass

class BasicCell(Cell):
    @property
    def document(self):
        return "A basic cell. Gives points based on how much the area covering this cell."

    def result(self, coverage: Fraction) -> Fraction:
        return coverage
    
class WallCell(Cell):
    @property
    def document(self):
        return "The shape may not include this cell."

    def result(self, coverage: Fraction) -> Fraction:
        return very_negative if coverage > 0 else Fraction(0)
    
class CaptureCell(Cell):
    @property
    def document(self):
        return "A cell that must be included (even a part of it) to make the answer valid."

    def result(self, coverage: Fraction) -> Fraction:
        return coverage if coverage > 0 else very_negative
    
class StrictCaptureCell(Cell):
    @property
    def document(self):
        return "A cell that must be totally included to make the answer valid."

    def result(self, coverage: Fraction) -> Fraction:
        return coverage if coverage >= 1 else very_negative
    
class ExclusiveCaptureCell(Cell):
    @property
    def document(self):
        return "A cell that must be partially but not fully included to make the answer valid."

    def result(self, coverage: Fraction) -> Fraction:
        return coverage if 0 < coverage < 1 else very_negative
    
class MetalCell(Cell):
    @property
    def document(self):
        return "A cell that must be in whole to be valid."

    def result(self, coverage: Fraction) -> Fraction:
        return coverage if not (0 < coverage < 1) else very_negative
    
class GlassCell(Cell):
    @property
    def document(self):
        return "A cell that must not be totally included to be valid."

    def result(self, coverage: Fraction) -> Fraction:
        return coverage if coverage < 1 else very_negative
    
class MineCell(Cell):
    @property
    def document(self):
        return "Deduct an immediate -1 if the shape ever so slightly touches this. Does not score any points."

    def result(self, coverage: Fraction) -> Fraction:
        return Fraction(-1) if coverage > 0 else Fraction(0)
    
class HoleCell(Cell):
    @property
    def document(self):
        return "A cell that does nothing, even scoring."

    def result(self, coverage: Fraction) -> Fraction:
        return Fraction(0)
    
class GemCell(Cell):
    @property
    def document(self):
        return "A cell that gives an extra 1 point if touched."

    def result(self, coverage: Fraction) -> Fraction:
        return coverage + 1 if coverage > 0 else Fraction(0)
    
class NegativeCell(Cell):
    @property
    def document(self):
        return "Loses points as more area are covered."

    def result(self, coverage: Fraction) -> Fraction:
        return - coverage
    
class BonusCell(Cell):
    @property
    def document(self):
        return "Gives 1 point regardless but it has to be touched."

    def result(self, coverage: Fraction) -> Fraction:
        return Fraction(0) if coverage == 0 else Fraction(1)

class DoubleCell(Cell):
    @property
    def document(self):
        return "A cell that gives double the points that a normal cell would."

    def result(self, coverage: Fraction) -> Fraction:
        return coverage * 2

# Registry to map string names in JSON to Classes
CELL_TYPES: dict[str, type[Cell]] = {
    "W": BasicCell,
    "Bk":WallCell,
    "L": CaptureCell,
    "G": StrictCaptureCell,
    "T": ExclusiveCaptureCell,
    "Gd":MetalCell,
    "C": GlassCell,
    "R": MineCell,
    "Gl":HoleCell,
    "Bl":GemCell,
}
color_map: dict[Cell, str] = {}

def resizeImage(img: tk.PhotoImage, newWidth: int, newHeight: int) -> tk.PhotoImage:
    oldWidth = img.width()
    oldHeight = img.height()
    newPhotoImage = tk.PhotoImage(width=newWidth, height=newHeight)
    for x in range(newWidth):
        for y in range(newHeight):
            xOld = int(x*oldWidth/newWidth)
            yOld = int(y*oldHeight/newHeight)
            rgb = '#%02x%02x%02x' % img.get(xOld, yOld)
            newPhotoImage.put(rgb, (x, y))
    return newPhotoImage

converter: dict[str, str] = {
    "N": "W",
    "W": "Bk",
    "C": "L",
    "F": "G",
    "E": "T",
    "A": "Gd",
    "I": "C",
    "M": "R",
    "H": "Gl",
    "G": "Bl"
}
inverted_converter: dict[str, str] = {v: k for k, v in converter.items()}

def str_to_board(board_str: str, _type: Literal["basic"] = "basic") -> dict:
    """Converts a string representation of the board into a 2D list."""
    vertices_index: int = board_str.find(";")
    if vertices_index == -1: raise ValueError("Invalid board string format: Vertices limit is either corrupted or missing.")
    vertices_limit: int = int(board_str[:vertices_index])
    separator_index: int = board_str.find("X")
    if separator_index == -1:
        raise ValueError("Invalid board string format: Board size is either corrupted or missing.")
    for i in range(separator_index+2, len(board_str)):
        if board_str[i] not in NUMBER:
            board_index = i
            break
    else:
        raise ValueError("Invalid board string format: Board data is either corrupted or missing.")
    cols: int = int(board_str[vertices_index+1:separator_index])
    rows: int = int(board_str[separator_index+1:board_index])
    board_data_str: str = board_str[board_index:]

    placeholder: list[str] = list()
    last_char: str = ""
    int_chars: str = ""
    for char in board_data_str:
        if char not in NUMBER:
            if int_chars:
                for i in range(int(int_chars)-1):
                    placeholder.append(last_char)
                int_chars = ""
            placeholder.append(char)
            last_char = char
        else:
            int_chars += char

    placeholder = [converter.get(ch, ch) for ch in placeholder] if _type == "basic" else placeholder
    
    board_data: list[list[str]] = list()
    for r in range(rows):
        row_data: list[str] = list()
        for c in range(cols):
            idx = r * cols + c
            if idx < len(placeholder):
                row_data.append(placeholder[idx])
            else:
                row_data.append("0") # Default to "0" if data is missing
        board_data.append(row_data)
    return {
        "cols": cols,
        "rows": rows,
        "max_vertices": vertices_limit,
        "goal": Fraction(0, 1), # Not provided
        "grid": board_data,
        "info": {
            "creator": "-",
            "found": "-",
            "verified": "-"
        }
    }

def more_numbers_to_fraction(num_str: str) -> Fraction:
    """Converts a string with more than 3 numbers into a fraction."""
    if ' ' in num_str:
        whole_part, frac_part = num_str.split()
        whole_part = int(whole_part)
        numerator, denominator = map(int, frac_part.split('/'))
        return Fraction(whole_part * denominator + numerator, denominator)
    elif '/' in num_str:
        numerator, denominator = map(int, num_str.split('/'))
        return Fraction(numerator, denominator)
    else:
        return Fraction(int(num_str), 1)

def get_unique_structures(elements: Sequence[tuple[Fraction, Fraction]]) -> list[Sequence[tuple[Fraction, Fraction]]]:
    n = len(elements)
    if n <= 2:
        return [tuple(elements)]
    
    first = elements[0]
    others = elements[1:]
    
    unique_list: list[Sequence[tuple[Fraction, Fraction]]] = []
    for p in permutations(others):
        if p[0] < p[-1]:
            unique_list.append((first,) + p)
            
    return unique_list

# --- 2. Geometric Logic (Pure Python) ---

def inside(p: tuple[Fraction, Fraction], edge: str, val: Fraction) -> bool:
    """Check if point p is inside the clip edge."""
    if edge == 'left':   return p[0] >= val
    if edge == 'right':  return p[0] <= val
    if edge == 'bottom': return p[1] >= val
    if edge == 'top':    return p[1] <= val
    else: raise ValueError("Invalid edge type")

def compute_intersection(p1: tuple[Fraction, Fraction], p2: tuple[Fraction, Fraction], edge: str, val: Fraction) -> tuple[Fraction, Fraction]:
    """Compute intersection of line segment p1-p2 with the clip edge."""
    x1, y1 = p1
    x2, y2 = p2
    
    if edge in ['left', 'right']:
        slope = (y2 - y1) / (x2 - x1)
        return (val, y1 + slope * (val - x1))
    else:
        inv_slope = (x2 - x1) / (y2 - y1)
        return (x1 + inv_slope * (val - y1), val)

def clip(poly: Sequence[tuple[Fraction, Fraction]], edge: str, val: Fraction) -> list[tuple[Fraction, Fraction]]:
    new_poly = []
    if not poly:
        return new_poly

    for i in range(len(poly)):
        p1 = poly[i - 1] # Previous vertex
        p2 = poly[i]     # Current vertex
        
        p1_in = inside(p1, edge, val)
        p2_in = inside(p2, edge, val)
        
        if p1_in and p2_in:
            new_poly.append(p2)
        elif p1_in and not p2_in:
            new_poly.append(compute_intersection(p1, p2, edge, val))
        elif not p1_in and p2_in:
            new_poly.append(compute_intersection(p1, p2, edge, val))
            new_poly.append(p2)
        
    return new_poly

def calculate_cell_coverage(min_x: Fraction, min_y: Fraction, polygon: Sequence[tuple[Fraction, Fraction]]) -> Fraction:
    max_x = min_x + 1
    max_y = min_y + 1

    # 1. Clip against all 4 sides of the square
    # We pipeline the output of one clip as the input to the next
    out_poly = clip(polygon, 'left', min_x)
    out_poly = clip(out_poly, 'right', max_x)
    out_poly = clip(out_poly, 'bottom', min_y)
    out_poly = clip(out_poly, 'top', max_y)

    # 2. Calculate area of the resulting clipped polygon using Shoelace Formula
    if len(out_poly) < 3:
        return Fraction(0, 1)

    area = Fraction(0, 1)
    for i in range(len(out_poly)):
        x1, y1 = out_poly[i]
        x2, y2 = out_poly[(i + 1) % len(out_poly)] # Wrap around to 0
        area += x1 * y2 - x2 * y1
        
    return abs(area) / 2

def get_orientation(p: tuple[Fraction, Fraction], q: tuple[Fraction, Fraction], r: tuple[Fraction, Fraction]):
    """Returns 0 if collinear, 1 if clockwise, 2 if counter-clockwise"""
    val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    if val == 0: return 0
    return 1 if val > 0 else 2

def on_segment(p: tuple[Fraction, Fraction], q: tuple[Fraction, Fraction], r: tuple[Fraction, Fraction]):
    """Checks if point q lies on segment pr"""
    return (q[0] <= max(p[0], r[0]) and q[0] >= min(p[0], r[0]) and
            q[1] <= max(p[1], r[1]) and q[1] >= min(p[1], r[1]))

def intersect(p1: tuple[Fraction, Fraction], q1: tuple[Fraction, Fraction], p2: tuple[Fraction, Fraction], q2: tuple[Fraction, Fraction]) -> bool:
    o1 = get_orientation(p1, q1, p2)
    o2 = get_orientation(p1, q1, q2)
    o3 = get_orientation(p2, q2, p1)
    o4 = get_orientation(p2, q2, q1)

    # General case: segments cross
    if o1 != o2 and o3 != o4:
        return True

    # Special cases: segments are collinear and one point is on the other segment
    if o1 == 0 and on_segment(p1, p2, q1): return True
    if o2 == 0 and on_segment(p1, q2, q1): return True
    if o3 == 0 and on_segment(p2, p1, q2): return True
    if o4 == 0 and on_segment(p2, q1, q2): return True
    return False

def validate_polygon(polygon: Sequence[tuple[Fraction, Fraction]]) -> bool:
    n = len(polygon)
    if n < 3:
        return False
    
    # 1. Check for redundant (collinear) vertices
    for i in range(n):
        prev_p = polygon[i - 1]
        curr_p = polygon[i]
        next_p = polygon[(i + 1) % n]
        if get_orientation(prev_p, curr_p, next_p) == 0:
            return False # Vertex is on a straight line
        
    # 2. Check for self-crossing (edge intersections)
    edges = [(polygon[i], polygon[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            # Skip adjacent edges as they naturally share a vertex
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            
            if intersect(edges[i][0], edges[i][1], edges[j][0], edges[j][1]):
                return False
            
    return True

# --- 3. The Game Engine & GUI ---

class LoadPopup(tk.Toplevel):
    def __init__(self):
        super().__init__()
        self.title("Load Board")
        self.geometry("400x150")
        self.result: None | dict = None

        tk.Label(self, text="Enter board data:").pack(padx=10, pady=10)
        self.entry = tk.Text(self, height=1, width=50)
        self.entry.pack(padx=10, pady=5)
        self.entry.focus_set()

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Load a file instead", command=self.on_file_load).pack(side=tk.LEFT, padx=5)

    def on_ok(self):
        self.result = str_to_board(self.entry.get("1.0", tk.END).strip())
        self.destroy()

    def on_file_load(self):
        filename: str = filedialog.askopenfilename(filetypes=[("JSON Board", "*.json")])
        if filename:
            try:
                with open(filename, 'r') as f:
                    self.result = json.load(f)
                    self.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load board: {e}")

class PolygonGame(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Boundary")
        self.state('zoomed')

        # Game State
        self.board_data: dict | None = None
        self.current_vertices: list[tuple[Fraction, Fraction]] = []
        self.auto_calc = tk.BooleanVar(value=True)
        self.cell_instances: list[list[Cell]] = []
        self.images_cache: dict = {}
        self.image_cache_size: int = 0
        self.last_vertex: tuple[Fraction, Fraction] | None = None
        self.goal: Fraction = Fraction(0, 1)
        self.banned_vertices: set[tuple[Fraction, Fraction]] = set()

        self.setup_ui()
        self.create_dummy_board()
        self.clear_vertices()

    def setup_ui(self) -> None:
        # --- Toolbar ---
        toolbar = tk.Frame(self, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        btn_load = tk.Button(toolbar, text="Load Board", command=self.load_board)
        btn_load.pack(side=tk.LEFT, padx=5, pady=5)

        btn_info = tk.Button(toolbar, text="Map Info", command=self.show_info)
        btn_info.pack(side=tk.LEFT, padx=5, pady=5)
        
        btn_clear = tk.Button(toolbar, text="Clear Vertices", command=self.clear_vertices)
        btn_clear.pack(side=tk.LEFT, padx=5, pady=5)

        btn_calc = tk.Button(toolbar, text="Calculate Score", command=self.calculate_score)
        btn_calc.pack(side=tk.LEFT, padx=5, pady=5)

        chk_auto = tk.Checkbutton(toolbar, text="Auto-Calculate", variable=self.auto_calc)
        chk_auto.pack(side=tk.LEFT, padx=20, pady=5)

        btn_solve = tk.Button(toolbar, text="Find Solutions (?)", command=self.find_solution)
        btn_solve.pack(side=tk.RIGHT, padx=5, pady=5)

        # --- Main Area ---
        self.canvas_frame = tk.Frame(self, bg="#333")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<ButtonRelease-3>", self.undo_vertex) # Right click to undo

        # --- Status Bar ---
        self.status_frame = tk.Frame(self, bd=1, relief=tk.SUNKEN)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_score = tk.Label(self.status_frame, text="Score: 0", font=("Arial", 12, "bold"))
        self.lbl_score.pack(side=tk.LEFT, padx=10)
        
        self.lbl_goal = tk.Label(self.status_frame, text="Goal: --")
        self.lbl_goal.pack(side=tk.LEFT, padx=10)
        
        self.lbl_vertices = tk.Label(self.status_frame, text="Vertices: 0/0")
        self.lbl_vertices.pack(side=tk.RIGHT, padx=10)

        self.lbl_desc = tk.Label(self.status_frame, text="Click to add vertices. Drag to move. Right-click to undo.")
        self.lbl_desc.pack(side=tk.RIGHT, padx=20)

    def create_dummy_board(self) -> None:
        """Creates an in-memory default board if no file is loaded."""
        data: dict = {
            "cols": 5,
            "rows": 5,
            "max_vertices": 3,
            "goal": "4 1/2",
            "grid": [
                ["Bk","Bk","W", "Bk","W" ],
                ["Bk","W", "W", "Bk","Bk"],
                ["W", "W", "W", "W", "W" ],
                ["Bk","Bk","W", "Bk","Bk"],
                ["W", "Bk","W", "Bk","Bk"]
            ],
            "info": {
                "creator": "The_upgrater",
                "found": "-",
                "verified": "-"
            }
        }
        self.parse_board(data)

    def load_board(self) -> None:
        load_popup = LoadPopup()
        self.wait_window(load_popup)
        if load_popup.result:
            self.parse_board(load_popup.result)
            self.calculate_score()
            return

    def parse_board(self, data: dict) -> None:
        self.board_data = data
        self.cols: int = data['cols']
        self.rows: int = data['rows']
        self.max_v: int = data['max_vertices']
        
        # Create Cell Objects
        self.cell_instances = []
        for r in range(self.rows):
            row_list = []
            for c in range(self.cols):
                type_name = data['grid'][r][c]
                # Default to Normal if type not found
                cell_cls: type[Cell] = CELL_TYPES.get(type_name, BasicCell)
                cell_obj: Cell = cell_cls(texture_path=f"textures/{type_name}.png")
                row_list.append(cell_obj)
            self.cell_instances.append(row_list)
            
        self.current_vertices = []
        self.lbl_goal.config(text=f"Reach {data['goal']}")
        self.goal = more_numbers_to_fraction(data['goal']) if isinstance(data['goal'], str) else Fraction(0, 1)
        info: dict = self.board_data.get('info', {})
        self.lbl_desc.config(text=info.get('description', "Click to add vertices. Drag to move. Right-click to undo."))
        self.draw_board()
        self.update_status()

    def show_info(self):
        if not self.board_data: return
        info: dict = self.board_data.get('info', {})
        msg = f"Level name: {info.get('title', 'Unnamed Level')}\n\n"
        msg += f"Creator: {info.get('creator', 'Anon')}\n"
        msg += f"Solution found By: {info.get('found', 'Unknown')}\n"
        msg += f"Verified By: {info.get('verified', '-')}"
        messagebox.showinfo("Map Info", msg)

    def draw_board(self):
        self.canvas.delete("all")
        if not self.board_data: return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        # Calculate cell size
        self.cell_size = min(w // (self.cols + 1), h // (self.rows + 1))
        self.offset_x = (w - self.cell_size * self.cols) // 2
        self.offset_y = (h - self.cell_size * self.rows) // 2

        # Draw Cells
        for r in range(self.rows):
            for c in range(self.cols):
                x1 = self.offset_x + c * self.cell_size
                y1 = self.offset_y + r * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                
                cell = self.cell_instances[r][c]
                
                # Attempt to load texture, fallback to color
                try:
                    if self.cell_size != self.image_cache_size:
                        self.images_cache.clear()  # Clear cache if cell size changes
                        self.image_cache_size = self.cell_size
                    if cell.texture_path not in self.images_cache:
                        img = resizeImage(tk.PhotoImage(file=cell.texture_path), self.cell_size, self.cell_size)
                        self.images_cache[cell.texture_path] = img
                    else:
                        img = self.images_cache[cell.texture_path]
                    self.canvas.create_image(x1, y1, anchor="nw", image=img)
                except Exception as e:
                    print(f"Failed to load texture for cell at ({c}, {r}): {e}")
                    self.canvas.create_rectangle(x1, y1, x2, y2, fill=color_map.get(cell, "white"), outline="gray")
        
        # Draw grid lines
        for r in range(self.rows + 1):
            y = self.offset_y + r * self.cell_size
            self.canvas.create_line(self.offset_x, y, self.offset_x + self.cols * self.cell_size, y, fill="black", width=3)
        for c in range(self.cols + 1):
            x = self.offset_x + c * self.cell_size
            self.canvas.create_line(x, self.offset_y, x, self.offset_y + self.rows * self.cell_size, fill="black", width=3)
        self.draw_polygon()
        self.canvas.update() # Ensure we have the latest dimensions

    def draw_polygon(self):
        self.canvas.delete("poly_layer")
        if not self.current_vertices: return

        screen_points: list[tuple[float, float]] = []
        for c, r in self.current_vertices:
            px = float(self.offset_x + c * self.cell_size)
            py = float(self.offset_y + r * self.cell_size)
            screen_points.append((px, py))

        # Draw edges
        if len(screen_points) > 1:
            self.canvas.create_line(screen_points, fill="red", width=3, tags="poly_layer")
            # Close the loop visually if we have enough points
            if len(screen_points) >= 3:
                self.canvas.create_line(screen_points[-1], screen_points[0], fill="red", width=3, tags="poly_layer")
        
        if len(screen_points) >= 3:
            self.canvas.create_polygon(screen_points, fill="#FF0000", stipple="gray25", tags="poly_layer")

        for px, py in screen_points:
            self.canvas.create_oval(px-5, py-5, px+5, py+5, fill="yellow", tags="poly_layer")
        
        if self.last_vertex:
            lx = float(self.offset_x + self.last_vertex[0] * self.cell_size)
            ly = float(self.offset_y + self.last_vertex[1] * self.cell_size)
            self.canvas.create_oval(lx-7, ly-7, lx+7, ly+7, fill="cyan", tags="poly_layer")

    def on_canvas_click(self, event: tk.Event) -> None:
        if not self.board_data: return
        
        # Snap to nearest intersection
        col: int = round((event.x - self.offset_x) / self.cell_size)
        row: int = round((event.y - self.offset_y) / self.cell_size)
        vertex: tuple[Fraction, Fraction] = (Fraction(col), Fraction(row))

        # Bounds check
        if 0 <= col <= self.cols and 0 <= row <= self.rows:
            if vertex in self.current_vertices:
                self.last_vertex = vertex
            elif len(self.current_vertices) < self.max_v and (col, row) not in self.current_vertices:
                self.current_vertices.append(vertex)
                self.last_vertex = vertex
                self.draw_polygon()
                self.update_status()
                self.calculate_score()
        self.draw_board()

    def on_canvas_drag(self, event: tk.Event) -> None:
        if not self.board_data or not self.last_vertex: return
        
        col: int = round((event.x - self.offset_x) / self.cell_size)
        row: int = round((event.y - self.offset_y) / self.cell_size)

        if 0 <= col <= self.cols and 0 <= row <= self.rows:
            new_vertex = (Fraction(col), Fraction(row))
            if new_vertex != self.last_vertex and new_vertex not in self.current_vertices:
                index = self.current_vertices.index(self.last_vertex)
                self.current_vertices[index] = new_vertex
                self.last_vertex = new_vertex
                self.update_status()
                if self.auto_calc.get() and len(self.current_vertices) >= 3:
                    self.calculate_score()
        self.draw_board()

    def on_canvas_release(self, event: tk.Event) -> None:
        self.last_vertex = None
        self.draw_board() 

    def undo_vertex(self, event: tk.Event) -> None:
        col: int = round((event.x - self.offset_x) / self.cell_size)
        row: int = round((event.y - self.offset_y) / self.cell_size)
        
        if (coord := (Fraction(col), Fraction(row))) in self.current_vertices:
            self.current_vertices.remove(coord)
            self.draw_polygon()
            self.update_status()
            if self.auto_calc.get():
                self.calculate_score()
            else:
                self.lbl_score.config(text="No polygon", fg="black")

    def clear_vertices(self) -> None:
        self.current_vertices = []
        self.draw_board()
        self.update_status()
        self.lbl_score.config(text="No polygon", fg="black")

    def update_status(self) -> None:
        self.lbl_vertices.config(text=f"Vertices: {len(self.current_vertices)}/{self.max_v}", fg="black" if len(self.current_vertices) < self.max_v else "green")

    def calculate_score(self) -> None:
        global threshold, very_negative
        very_negative = Fraction(-(self.cols * self.rows)**2, 1)
        threshold = Fraction(-(self.cols * self.rows), 1)

        if len(self.current_vertices) < self.max_v:
            self.lbl_score.config(text="Not enough vertices", fg="red")
            self.lbl_vertices.config(fg="red")
            return
        
        total_score = Fraction(0, 1)

        for r in range(self.rows):
            for c in range(self.cols):
                total_score += self.cell_instances[r][c].result(calculate_cell_coverage(Fraction(c), Fraction(r), self.current_vertices))
        final_val = float(total_score)
        
        if final_val < threshold:
            self.lbl_score.config(text="Invalid polygon", fg="red")
        elif not validate_polygon(self.current_vertices):
            self.lbl_score.config(text="Disallowed polygon", fg="red")
        else:
            fg = "green" if total_score >= self.goal else "black"
            if total_score.denominator == 1:
                self.lbl_score.config(text=f"Score: {total_score.numerator} ({str(total_score) + ' or ' if total_score.numerator == 0 else ''}{final_val})", fg=fg)
            elif 0 <= total_score.numerator < total_score.denominator:
                self.lbl_score.config(text=f"Score: {total_score} ({final_val})", fg=fg)
            elif total_score.numerator < 0:
                self.lbl_score.config(text=f"Score: {total_score} ({final_val})", fg=fg)
            else:
                self.lbl_score.config(text=f"Score: {int(total_score)} {total_score.numerator % total_score.denominator}/{total_score.denominator} ({str(total_score) + ' or ' if int(total_score) == 0 else ''}{final_val})", fg=fg)
    
    def find_solution(self):
        possible_points: list[tuple[Fraction, Fraction]] = [(Fraction(c), Fraction(r)) for r in range(self.rows + 1) for c in range(self.cols + 1)]

        possible_combinations = combinations(possible_points, self.max_v)
        num_of_combinations = math.comb(len(possible_points), self.max_v)
        bests: list[list[tuple[Fraction, Fraction]]] = []
        best_score: Fraction = threshold
        i = 0
        for combo in possible_combinations:
            for perm in get_unique_structures(combo):
                if validate_polygon(perm):
                    score = Fraction(0, 1)
                    for r in range(self.rows):
                        for c in range(self.cols):
                            score += self.cell_instances[r][c].result(calculate_cell_coverage(Fraction(c), Fraction(r), perm))
                    if score > best_score:
                        best_score = score
                        bests = [list(perm)]
                        print(f"New best score: {best_score} with vertices {[(x.numerator, y.numerator) for x, y in perm]}")
                    elif score == best_score:
                        bests.append(list(perm))
                        print(f"Found another solution with score {best_score}: {[(x.numerator, y.numerator) for x, y in perm]}")
            i += 1
            if i % 1000 == 0:
                print(f"{i}/{num_of_combinations}", end="\r")
        print(f"Best score found: {best_score} with {len(bests)} solution(s).")

if __name__ == "__main__":
    app = PolygonGame()
    app.mainloop()
