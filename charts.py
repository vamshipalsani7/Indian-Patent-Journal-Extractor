"""
Lightweight, dependency-free charts on a Tkinter Canvas (v6 Phase 7).

No matplotlib, no new dependency - keeps the eventual single .exe small. Each
chart is a CTkFrame wrapping a tk.Canvas that redraws on resize, truncates long
labels, and shows "No data" for empty input. The geometry maths is factored
into pure helpers (tested headless); the widget classes only draw.
"""

import math
import tkinter as tk

import customtkinter as ctk

_BG = "#1a1a1a"
_AXIS = "#3a3a3a"
_TEXT = "#cccccc"
_BAR = "#3b8ed0"
_BAR2 = "#e08a3b"


# --------------------------------------------------------------- pure helpers

def truncate(text, maxlen=22):
    text = str(text)
    return text if len(text) <= maxlen else text[:maxlen - 1] + "…"


def nice_max(value):
    """A 'nice' upper bound >= value (1/2/2.5/5/10 x 10^k)."""
    if value <= 0:
        return 1
    exp = math.floor(math.log10(value))
    base = 10 ** exp
    for m in (1, 2, 2.5, 5, 10):
        if value <= m * base:
            nb = m * base
            return int(nb) if nb >= 1 else nb
    return int(10 * base)


def bar_rects(values, width, height,
              pad_left=44, pad_bottom=26, pad_top=12, pad_right=12):
    """Vertical-bar rectangles (x0,y0,x1,y1) plus the axis max. Bars grow up
    from the baseline; tallest bar corresponds to the largest value."""
    n = len(values)
    if n == 0:
        return [], nice_max(0)
    top = nice_max(max(values))
    plot_w = max(width - pad_left - pad_right, 1)
    plot_h = max(height - pad_top - pad_bottom, 1)
    slot = plot_w / n
    bar_w = slot * 0.7
    base_y = pad_top + plot_h
    rects = []
    for i, v in enumerate(values):
        x0 = pad_left + i * slot + (slot - bar_w) / 2
        h = plot_h * (v / top) if top else 0
        rects.append((x0, base_y - h, x0 + bar_w, base_y))
    return rects, top


def line_points(values, width, height,
                pad_left=44, pad_bottom=26, pad_top=12, pad_right=12):
    """(x,y) points for a categorical line/trend chart, plus the axis max."""
    n = len(values)
    if n == 0:
        return [], nice_max(0)
    top = nice_max(max(values))
    plot_w = max(width - pad_left - pad_right, 1)
    plot_h = max(height - pad_top - pad_bottom, 1)
    base_y = pad_top + plot_h
    step = plot_w / max(n - 1, 1)
    return [
        (pad_left + i * step, base_y - (plot_h * (v / top) if top else 0))
        for i, v in enumerate(values)
    ], top


# ------------------------------------------------------------------- widgets

class _Chart(ctk.CTkFrame):

    def __init__(self, master, title="", height=200, **kw):
        super().__init__(master, **kw)
        self.title_text = title
        self.data = []
        if title:
            ctk.CTkLabel(self, text=title, font=("Arial", 12, "bold")).pack(
                anchor="w", padx=8, pady=(6, 0))
        self.canvas = tk.Canvas(self, height=height, highlightthickness=0, bg=_BG)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.canvas.bind("<Configure>", lambda e: self._redraw())

    def set_data(self, data):
        self.data = list(data or [])
        self._redraw()

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w <= 1 or h <= 1:
            return
        if not self.data:
            c.create_text(w // 2, h // 2, text="No data", fill="#888")
            return
        self._draw(c, w, h)

    def _draw(self, canvas, w, h):
        raise NotImplementedError


class BarChart(_Chart):
    """data = [(label, value), ...]"""

    def _draw(self, canvas, w, h):
        labels = [truncate(lbl, 10) for lbl, _ in self.data]
        values = [v for _, v in self.data]
        rects, top = bar_rects(values, w, h)
        canvas.create_text(6, 12, text=str(top), fill=_TEXT, anchor="w", font=("Arial", 8))
        for (x0, y0, x1, y1), value, label in zip(rects, values, labels):
            canvas.create_rectangle(x0, y0, x1, y1, fill=_BAR, width=0)
            canvas.create_text((x0 + x1) / 2, y0 - 6, text=str(value),
                               fill=_TEXT, font=("Arial", 8))
            canvas.create_text((x0 + x1) / 2, y1 + 10, text=label,
                               fill=_TEXT, font=("Arial", 8))


class HBarChart(_Chart):
    """Horizontal bars - best for long labels (applicants, categories).
    data = [(label, value), ...]"""

    def _draw(self, canvas, w, h):
        n = len(self.data)
        top = nice_max(max(v for _, v in self.data))
        label_w = min(max(int(w * 0.42), 90), 240)
        plot_x0 = label_w + 6
        plot_w = max(w - plot_x0 - 44, 1)
        row_h = max((h - 12) / n, 6)
        for i, (label, value) in enumerate(self.data):
            y = 8 + i * row_h
            canvas.create_text(6, y + row_h / 2, text=truncate(label, 34),
                               fill=_TEXT, anchor="w", font=("Arial", 9))
            bw = plot_w * (value / top) if top else 0
            canvas.create_rectangle(plot_x0, y + 3, plot_x0 + bw, y + row_h - 3,
                                    fill=_BAR, width=0)
            canvas.create_text(plot_x0 + bw + 4, y + row_h / 2, text=str(value),
                               fill=_TEXT, anchor="w", font=("Arial", 9))


class LineChart(_Chart):
    """Simple categorical trend. data = [(label, value), ...]"""

    def _draw(self, canvas, w, h):
        labels = [truncate(lbl, 10) for lbl, _ in self.data]
        values = [v for _, v in self.data]
        points, top = line_points(values, w, h)
        canvas.create_text(6, 12, text=str(top), fill=_TEXT, anchor="w", font=("Arial", 8))
        if len(points) >= 2:
            flat = [coord for xy in points for coord in xy]
            canvas.create_line(*flat, fill=_BAR, width=2, smooth=False)
        for (x, y), value, label in zip(points, values, labels):
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=_BAR, width=0)
            canvas.create_text(x, y - 10, text=str(value), fill=_TEXT, font=("Arial", 8))
            canvas.create_text(x, h - 10, text=label, fill=_TEXT, font=("Arial", 8))


class GroupedBarChart(_Chart):
    """Two series per category (e.g. Published vs Granted).
    data = [(label, value1, value2), ...]; names = (name1, name2)."""

    def __init__(self, master, title="", names=("A", "B"), **kw):
        self.names = names
        super().__init__(master, title=title, **kw)

    def _draw(self, canvas, w, h):
        labels = [truncate(lbl, 10) for lbl, _, _ in self.data]
        top = nice_max(max(max(a, b) for _, a, b in self.data))
        pad_left, pad_bottom, pad_top, pad_right = 44, 26, 24, 12
        plot_w = max(w - pad_left - pad_right, 1)
        plot_h = max(h - pad_top - pad_bottom, 1)
        base_y = pad_top + plot_h
        slot = plot_w / len(self.data)
        bw = slot * 0.3
        # legend
        canvas.create_rectangle(pad_left, 6, pad_left + 10, 14, fill=_BAR, width=0)
        canvas.create_text(pad_left + 14, 10, text=self.names[0], anchor="w",
                           fill=_TEXT, font=("Arial", 8))
        canvas.create_rectangle(pad_left + 70, 6, pad_left + 80, 14, fill=_BAR2, width=0)
        canvas.create_text(pad_left + 84, 10, text=self.names[1], anchor="w",
                           fill=_TEXT, font=("Arial", 8))
        for i, (label, a, b) in enumerate(self.data):
            cx = pad_left + i * slot + slot / 2
            ha = plot_h * (a / top) if top else 0
            hb = plot_h * (b / top) if top else 0
            canvas.create_rectangle(cx - bw, base_y - ha, cx, base_y, fill=_BAR, width=0)
            canvas.create_rectangle(cx, base_y - hb, cx + bw, base_y, fill=_BAR2, width=0)
            canvas.create_text(cx, base_y + 10, text=labels[i], fill=_TEXT, font=("Arial", 8))
