import tkinter as tk
from tkinter import filedialog, messagebox
import json
from typing import Literal

NUMBER = "0123456789"

try:
    from main import CELL_TYPES
except ImportError:
    print("Unable to load data: CELL_TYPES does not exist. Make sure to have this file on the same folder as main.py.")
    CELL_TYPES = ["W"]
    
cell_type_count = max(len(CELL_TYPES), 1)

converter = {
    "N": "W",
    "W": "Bk",
    "C": "L",
    "F": "G",
    "E": "T",
    "A": "Gd",
    "I": "C",
    "M": "R",
    "H": "Gl",
    "G": "Bl",
}
inverted_converter = {v: k for k, v in converter.items()}

side = 2

def resizeImage(img: tk.PhotoImage, newWidth: int, newHeight: int) -> tk.PhotoImage:
    """Resize a Tk PhotoImage the same way the original application
    does.  We need this so that textures can be drawn at arbitrary
    board sizes without distortion.
    """
    oldWidth = img.width()
    oldHeight = img.height()
    newPhotoImage = tk.PhotoImage(width=newWidth, height=newHeight)
    for x in range(newWidth):
        for y in range(newHeight):
            xOld = int(x * oldWidth / newWidth)
            yOld = int(y * oldHeight / newHeight)
            rgb = '#%02x%02x%02x' % img.get(xOld, yOld)
            newPhotoImage.put(rgb, (x, y))
    return newPhotoImage


class EditorApp(tk.Tk):
    """Simple board editor for Boundary puzzles.

    The editor runs in a single Tk window.  A canvas occupies most of the
    area; the upper‑left portion of that canvas is used for the tile
    palette, and the remainder is the editable board.
    """

    def __init__(self):
        super().__init__()
        self.title("Boundary Board Editor")

        self.cols = 8
        self.rows = 8
        self.vertices_req = 5
        self.goal = ""
        self.info = {
            "title": "Unnamed Board",
            "creator": "Anon.",
            "found": "?",
            "verified": "?",
            "description": "-",
        }
        self.grid_data = [["W" for _ in range(self.cols)] for _ in range(self.rows)]

        self.history: list[list[list[str]]] = []
        self.history_index = -1

        self.tile_codes = CELL_TYPES
        self.current_tile = self.tile_codes[0]
        self.images_cache: dict[str, tk.PhotoImage] = {}
        self.palette_images_cache: dict[str, tk.PhotoImage] = {}
        self.image_cache_size = 0
        self.palette_image_cache_size = 0
        self.l: Literal["palette", "board"] = "board"
        self.r: Literal["palette", "board"] = "board"
        self.lr: Literal["l", "r"] = "l"
        self.anything_changed: bool = False

        self.setup_ui()
        self.push_history()

        self.grid_tl = (0, 0)

        self.bind("<Configure>", lambda e: self.draw_board())

    def setup_ui(self) -> None:
        toolbar = tk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)
        self.board_tile_height = 0
        self.cell_padding = 2

        tk.Button(toolbar, text="New", command=self.new_board).pack(side=tk.LEFT, padx=2)

        tk.Label(toolbar, text="Cols:").pack(side=tk.LEFT)
        self.entry_cols = tk.Entry(toolbar, width=3)
        self.entry_cols.pack(side=tk.LEFT)
        self.entry_cols.insert(0, str(self.cols))
        self.entry_cols.bind("<FocusOut>", lambda _: self.resize_board())

        tk.Label(toolbar, text="Rows:").pack(side=tk.LEFT)
        self.entry_rows = tk.Entry(toolbar, width=3)
        self.entry_rows.pack(side=tk.LEFT)
        self.entry_rows.insert(0, str(self.rows))
        self.entry_rows.bind("<FocusOut>", lambda _: self.resize_board())
        
        tk.Label(toolbar, text="Vert:").pack(side=tk.LEFT)
        self.entry_goal = tk.Entry(toolbar, width=3)
        self.entry_goal.pack(side=tk.LEFT)
        self.entry_goal.insert(0, str(self.vertices_req))

        meta = tk.Frame(self)
        meta.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)
        tk.Label(meta, text="Title:").pack(side=tk.LEFT)
        self.entry_title = tk.Entry(meta, width=20)
        self.entry_title.pack(side=tk.LEFT, padx=4)
        tk.Label(meta, text="Creator:").pack(side=tk.LEFT)
        self.entry_creator = tk.Entry(meta, width=15)
        self.entry_creator.pack(side=tk.LEFT, padx=4)
        tk.Label(meta, text="Goal:").pack(side=tk.LEFT)
        self.entry_maxv = tk.Entry(meta, width=3)
        self.entry_maxv.pack(side=tk.LEFT, padx=4)

        self.canvas = tk.Canvas(self, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_size = (self.canvas.winfo_width(), self.canvas.winfo_height())

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release)

        bottom = tk.Frame(self)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)
        tk.Button(bottom, text="Undo", command=self.undo).pack(side=tk.LEFT, padx=2)
        tk.Button(bottom, text="Redo", command=self.redo).pack(side=tk.LEFT, padx=2)
        tk.Button(bottom, text="Export String", command=self.export_string).pack(side=tk.LEFT, padx=2)
        tk.Button(bottom, text="Export JSON", command=self.export_json).pack(side=tk.LEFT, padx=2)

        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-y>", lambda e: self.redo())

    def resize_board(self) -> None:
        try:
            nc = int(self.entry_cols.get())
            nr = int(self.entry_rows.get())
        except ValueError:
            messagebox.showerror("Invalid size", "Rows and columns must be integers.")
            return
        self.cols = max(1, nc)
        self.rows = max(1, nr)
        self.grid_data = [["W" for _ in range(self.cols)] for __ in range(self.rows)]
        self.push_history(clear_future=True)
        self.draw_board()

    def new_board(self) -> None:
        if not all((self.grid_data[m][n] == self.grid_data[0][0] for n in range(len(self.grid_data[m]))) for m in range(len(self.grid_data))):
            option = messagebox.askyesno("New Board", "Do you want to start a new board? Unsaved changes will be lost.")
            if not option:
                return
        self.info = {k: "" for k in self.info}
        self.goal = ""
        self.vertices_req = 5
        self.entry_title.delete(0, tk.END)
        self.entry_creator.delete(0, tk.END)
        self.entry_goal.delete(0, tk.END)
        self.entry_maxv.delete(0, tk.END)
        self.grid_data = [["W" for _ in range(self.cols)] for __ in range(self.rows)]
        self.history.clear()
        self.history_index = -1
        self.resize_board()

    def push_history(self, clear_future: bool = False) -> None:
        snapshot = [row.copy() for row in self.grid_data]
        if clear_future:
            self.history = self.history[: self.history_index + 1]
        self.history.append(snapshot)
        self.history_index = len(self.history) - 1

    def undo(self) -> None:
        if self.history_index > 0:
            self.history_index -= 1
            self.grid_data = [row.copy() for row in self.history[self.history_index]]
            self.draw_board()

    def redo(self) -> None:
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.grid_data = [row.copy() for row in self.history[self.history_index]]
            self.draw_board()

    def board_to_string(self) -> str:
        flat = [self.grid_data[r][c] for r in range(self.rows) for c in range(self.cols)]
        out = ""
        i = 0
        while i < len(flat):
            ch = flat[i]
            cnt = 1
            while i + cnt < len(flat) and flat[i + cnt] == ch:
                cnt += 1
            out += inverted_converter.get(ch, ch)
            if cnt > 1:
                out += str(cnt)
            i += cnt
        header = f"{self.vertices_req};{self.cols}X{self.rows}"
        return header + out

    def export_string(self) -> None:
        s = self.board_to_string()
        win = tk.Toplevel(self)
        win.title("Board String")
        txt = tk.Text(win, width=80, height=4)
        txt.pack(padx=10, pady=10)
        txt.insert(tk.END, s)
        txt.configure(state="disabled")

    def export_json(self) -> None:
        self.info["title"] = self.entry_title.get()
        self.info["creator"] = self.entry_creator.get()
        self.goal = self.entry_goal.get()
        try:
            self.vertices_req = int(self.entry_maxv.get())
        except ValueError:
            self.vertices_req = 5

        data = {
            "cols": self.cols,
            "rows": self.rows,
            "max_vertices": self.vertices_req,
            "goal": self.goal,
            "grid": self.grid_data,
            "info": {
                "title": self.info.get("title", ""),
                "creator": self.info.get("creator", ""),
                "found": self.info.get("found", ""),
                "verified": self.info.get("verified", ""),
                "description": self.info.get("description", ""),
            },
        }
        fpath = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON files", "*.json")]
        )
        if not fpath:
            return
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        messagebox.showinfo("Exported", f"JSON saved to {fpath}")

    def on_canvas_click(self, event: tk.Event) -> None:
        x, y = event.x, event.y
        self.anything_changed = False
        if y < self.palette_tile_height:
            self.l = "palette"
        else:
            self.l = "board"
        self.lr = "l"

    def on_canvas_drag(self, event: tk.Event) -> None:
        state = int(event.state)
        shift = (state & 0x0001) != 0
        if shift and self.l == "board":
            if self.lr == "l":
                self.paint_at(event)
            else:
                self.change_cell(event, "W")
            self.anything_changed = True

    def on_canvas_release(self, event: tk.Event) -> None:
        state = int(event.state)
        ctrl = (state & 0x0004) != 0
        if self.l == "board":
            if ctrl:
                self.bucket_fill(event)
            else:
                self.paint_at(event)
            self.anything_changed = True
        else:
            if event.y <= self.palette_tile_height:
                idx = event.x // self.palette_tile_height
                if 0 <= idx < len(self.tile_codes):
                    self.current_tile = self.tile_codes[idx]
                    self.draw_board()
        if self.anything_changed:
            self.push_history()
            self.anything_changed = False

    def on_right_click(self, event: tk.Event) -> None:
        x, y = event.x, event.y
        self.anything_changed = False
        if y < self.palette_tile_height:
            self.r = "palette"
            return
        self.r = "board"
        self.lr = "r"

    def on_right_release(self, event: tk.Event) -> None:
        if self.r == "board":
            self.change_cell(event, "W")
            self.push_history()

    def paint_at(self, event: tk.Event) -> None:
        state = int(event.state)
        ctrl = (state & 0x0004) != 0
        if ctrl:
            self.bucket_fill(event)
        else:
            self.change_cell(event, self.current_tile)

    def change_cell(self, event: tk.Event, tile: str) -> None:
        x, y = event.x, event.y
        if y < self.board_tile_height:
            return
        c = x // self.board_tile_height
        r = (y - self.palette_tile_height) // self.board_tile_height
        if 0 <= r < self.rows and 0 <= c < self.cols:
            if self.grid_data[r][c] != tile:
                self.grid_data[r][c] = tile
                self.draw_board()

    def bucket_fill(self, event: tk.Event) -> None:
        x, y = event.x, event.y
        if y < self.board_tile_height:
            return
        c = x // self.board_tile_height
        r = (y - self.palette_tile_height) // self.board_tile_height
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return
        target = self.grid_data[r][c]
        new = self.current_tile
        if target == new:
            return
        stack = [(r, c)]
        while stack:
            rr, cc = stack.pop()
            if 0 <= rr < self.rows and 0 <= cc < self.cols and self.grid_data[rr][cc] == target:
                self.grid_data[rr][cc] = new
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    stack.append((rr + dr, cc + dc))
        self.draw_board()

    def draw_tile(self, x: int, y: int, code: str, size: int, is_palette: bool = False) -> None:
        path = f"textures/{code}.png"
        try:
            if not is_palette:
                if size != self.image_cache_size:
                    self.images_cache.clear()
                    self.image_cache_size = size
                if path not in self.images_cache:
                    img = resizeImage(tk.PhotoImage(file=path), size, size)
                    self.images_cache[path] = img
                else:
                    img = self.images_cache[path]
                self.canvas.create_image(x, y, anchor="nw", image=img)
            else:
                if size != self.palette_image_cache_size:
                    self.palette_images_cache.clear()
                    self.palette_image_cache_size = size
                if path not in self.palette_images_cache:
                    img = resizeImage(tk.PhotoImage(file=path), size, size)
                    self.palette_images_cache[path] = img
                else:
                    img = self.palette_images_cache[path]
                self.canvas.create_image(x, y, anchor="nw", image=img)
        except Exception:
            self.canvas.create_rectangle(x, y, x + size, y + size, fill="gray")
            self.canvas.create_text(x + size / 2, y + size / 2, text=code)

    def draw_board(self) -> None:
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if self.cols == 0 or self.rows == 0:
            return
        self.palette_tile_height = w//len(self.tile_codes)
        self.board_tile_height = min((h - self.palette_tile_height) // self.rows, w // self.cols)

        for idx, code in enumerate(self.tile_codes):
            x = idx * self.palette_tile_height
            self.draw_tile(x, 0, code, self.palette_tile_height, is_palette=True)
        if self.current_tile in self.tile_codes:
            idx = self.tile_codes.index(self.current_tile)
            x = idx * self.palette_tile_height
            self.canvas.create_rectangle(
                x, 0, x + self.palette_tile_height, self.palette_tile_height, outline="red", width=side
            )

        for r in range(self.rows):
            for c in range(self.cols):
                x = c * self.board_tile_height
                y = self.palette_tile_height + r * self.board_tile_height
                self.draw_tile(x, y, self.grid_data[r][c], self.board_tile_height)

        for r in range(self.rows + 1):
            y = self.palette_tile_height + r * self.board_tile_height
            self.canvas.create_line(0, y, self.cols * self.board_tile_height, y, fill="black")
        for c in range(self.cols + 1):
            x = c * self.board_tile_height
            self.canvas.create_line(x, self.palette_tile_height, x, self.palette_tile_height + self.rows * self.board_tile_height, fill="black")

        self.canvas.create_line(
            0,
            self.palette_tile_height,
            max(w, self.cols * self.board_tile_height),
            self.palette_tile_height,
            fill="black",
        )


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
