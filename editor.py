import tkinter as tk
from tkinter import filedialog, messagebox
import json
from fractions import Fraction

NUMBER = "0123456789"

# mapping used by main.py; kept here for consistency
CELL_TYPES = {
    "W": None,  # basic (wall is just another tile)
    "Bk": None,
    "L": None,
    "G": None,
    "T": None,
    "Gd": None,
    "C": None,
    "R": None,
    "Gl": None,
    "Bl": None,
    "Pk": None,
    "Pr": None,
    "Br": None,
    "Y": None,
    "O": None,
    "Lv": None,
    "M": None,
    "Pf": None,
}
# conversion table that str_to_board uses when _type == "basic".  For
# our exporter we can simply use the inverted map to produce the older
# single‑letter codes if desired.
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

        # logical board state
        self.cols = 8
        self.rows = 8
        self.max_vertices = 5
        self.goal = ""
        self.info = {
            "title": "",
            "creator": "",
            "found": "",
            "verified": "",
            "description": "",
        }
        self.grid_data = [["W" for _ in range(self.cols)] for __ in range(self.rows)]

        # history stack for undo/redo
        self.history: list[list[list[str]]] = []
        self.history_index = -1

        # palette
        self.tile_codes = list(CELL_TYPES.keys())
        self.current_tile = self.tile_codes[0]
        self.images_cache: dict[str, tk.PhotoImage] = {}
        self.image_cache_size = 0

        self.setup_ui()
        self.push_history()

        # redraw whenever the window size changes
        self.bind("<Configure>", lambda e: self.draw_board())

    # ------------------------------------------------------------------
    # UI initialization
    # ------------------------------------------------------------------

    def setup_ui(self) -> None:
        toolbar = tk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)
        self.cell_size = 0  # will be set in draw_board
        self.cell_padding = 2

        tk.Label(toolbar, text="Cols:").pack(side=tk.LEFT)
        self.entry_cols = tk.Entry(toolbar, width=3)
        self.entry_cols.pack(side=tk.LEFT)
        self.entry_cols.insert(0, str(self.cols))
        self.entry_cols.bind("<Return>", lambda e: self.resize_board())

        tk.Label(toolbar, text="Rows:").pack(side=tk.LEFT)
        self.entry_rows = tk.Entry(toolbar, width=3)
        self.entry_rows.pack(side=tk.LEFT)
        self.entry_rows.insert(0, str(self.rows))
        self.entry_rows.bind("<Return>", lambda e: self.resize_board())

        tk.Button(toolbar, text="Resize", command=self.resize_board).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="New", command=self.new_board).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Undo", command=self.undo).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Redo", command=self.redo).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Export String", command=self.export_string).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="Export JSON", command=self.export_json).pack(side=tk.LEFT, padx=2)

        # Metadata toolbar
        meta = tk.Frame(self)
        meta.pack(side=tk.TOP, fill=tk.X, padx=2, pady=2)
        tk.Label(meta, text="Title:").pack(side=tk.LEFT)
        self.entry_title = tk.Entry(meta, width=20)
        self.entry_title.pack(side=tk.LEFT, padx=4)
        tk.Label(meta, text="Creator:").pack(side=tk.LEFT)
        self.entry_creator = tk.Entry(meta, width=15)
        self.entry_creator.pack(side=tk.LEFT, padx=4)
        tk.Label(meta, text="Goal:").pack(side=tk.LEFT)
        self.entry_goal = tk.Entry(meta, width=8)
        self.entry_goal.pack(side=tk.LEFT, padx=4)
        tk.Label(meta, text="Max vert:").pack(side=tk.LEFT)
        self.entry_maxv = tk.Entry(meta, width=3)
        self.entry_maxv.pack(side=tk.LEFT, padx=4)

        # canvas
        self.canvas = tk.Canvas(self, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # keyboard shortcuts
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-y>", lambda e: self.redo())

    # ------------------------------------------------------------------
    # Board operations
    # ------------------------------------------------------------------

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
        self.resize_board()
        self.info = {k: "" for k in self.info}
        self.goal = ""
        self.max_vertices = 0
        self.entry_title.delete(0, tk.END)
        self.entry_creator.delete(0, tk.END)
        self.entry_goal.delete(0, tk.END)
        self.entry_maxv.delete(0, tk.END)

    # ------------------------------------------------------------------
    # History (undo/redo)
    # ------------------------------------------------------------------

    def push_history(self, clear_future: bool = False) -> None:
        # store a deep copy of the grid
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

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def board_to_string(self) -> str:
        flat = [self.grid_data[r][c] for r in range(self.rows) for c in range(self.cols)]
        out = ""
        i = 0
        while i < len(flat):
            ch = flat[i]
            cnt = 1
            while i + cnt < len(flat) and flat[i + cnt] == ch:
                cnt += 1
            out += ch
            if cnt > 1:
                out += str(cnt)
            i += cnt
        header = f"{self.max_vertices};{self.cols}X{self.rows}"
        return header + out

    def export_string(self) -> None:
        s = self.board_to_string()
        # show in dialog so user can copy
        win = tk.Toplevel(self)
        win.title("Board String")
        txt = tk.Text(win, width=80, height=4)
        txt.pack(padx=10, pady=10)
        txt.insert(tk.END, s)
        txt.configure(state="disabled")

    def export_json(self) -> None:
        # refresh metadata from entry widgets
        self.info["title"] = self.entry_title.get()
        self.info["creator"] = self.entry_creator.get()
        self.goal = self.entry_goal.get()
        try:
            self.max_vertices = int(self.entry_maxv.get())
        except ValueError:
            self.max_vertices = 0

        data = {
            "cols": self.cols,
            "rows": self.rows,
            "max_vertices": self.max_vertices,
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

    # ------------------------------------------------------------------
    # Event handling and painting
    # ------------------------------------------------------------------

    def on_canvas_click(self, event: tk.Event) -> None:
        x, y = event.x, event.y
        if self.cell_size == 0:
            return
        # palette occupies first row
        if y < self.cell_size:
            idx = x // self.cell_size
            if 0 <= idx < len(self.tile_codes):
                self.current_tile = self.tile_codes[idx]
                self.draw_board()
            return

        self.paint_at(event)

    def on_canvas_drag(self, event: tk.Event) -> None:
        # only draw on drag when shift is held
        state = int(event.state)
        shift = (state & 0x0001) != 0
        if shift:
            self.paint_at(event)

    def on_canvas_release(self, event: tk.Event) -> None:
        # after drag completes, push history
        self.push_history()

    def on_right_click(self, event: tk.Event) -> None:
        # always place wall
        self.change_cell(event, "W")
        self.push_history()

    def paint_at(self, event: tk.Event) -> None:
        state = int(event.state)
        ctrl = (state & 0x0004) != 0
        shift = (state & 0x0001) != 0
        if ctrl:
            self.bucket_fill(event)
            self.push_history()
        else:
            if shift:
                self.change_cell(event, "W")
            else:
                self.change_cell(event, self.current_tile)
            self.push_history()

    def change_cell(self, event: tk.Event, tile: str) -> None:
        x, y = event.x, event.y
        if y < self.cell_size:
            return
        c = x // self.cell_size
        r = (y - self.cell_size) // self.cell_size
        if 0 <= r < self.rows and 0 <= c < self.cols:
            if self.grid_data[r][c] != tile:
                self.grid_data[r][c] = tile
                self.draw_board()

    def bucket_fill(self, event: tk.Event) -> None:
        x, y = event.x, event.y
        if y < self.cell_size:
            return
        c = x // self.cell_size
        r = (y - self.cell_size) // self.cell_size
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

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def draw_tile(self, x: int, y: int, code: str, size: int) -> None:
        path = f"textures/{code}.png"
        try:
            if size != self.image_cache_size:
                self.images_cache.clear()
                self.image_cache_size = size
            if path not in self.images_cache:
                img = resizeImage(tk.PhotoImage(file=path), size, size)
                self.images_cache[path] = img
            else:
                img = self.images_cache[path]
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
        self.cell_size = min(w // self.cols, h // (self.rows + 1))
        palette_height = self.cell_size

        # draw palette row
        for idx, code in enumerate(self.tile_codes):
            x = idx * self.cell_size
            y = 0
            self.draw_tile(x, y, code, self.cell_size)
            if code == self.current_tile:
                self.canvas.create_rectangle(
                    x, y, x + self.cell_size, y + self.cell_size, outline="red", width=2
                )

        # draw board cells
        for r in range(self.rows):
            for c in range(self.cols):
                x = c * self.cell_size
                y = palette_height + r * self.cell_size
                self.draw_tile(x, y, self.grid_data[r][c], self.cell_size)

        # grid lines (board)
        for r in range(self.rows + 1):
            y = palette_height + r * self.cell_size
            self.canvas.create_line(0, y, self.cols * self.cell_size, y, fill="black")
        for c in range(self.cols + 1):
            x = c * self.cell_size
            self.canvas.create_line(x, palette_height, x, palette_height + self.rows * self.cell_size, fill="black")

        # palette border
        self.canvas.create_line(
            0,
            palette_height,
            max(w, self.cols * self.cell_size),
            palette_height,
            fill="black",
        )


if __name__ == "__main__":
    app = EditorApp()
    app.mainloop()
