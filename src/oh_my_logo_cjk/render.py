from __future__ import annotations

import shutil
import sys
from typing import List, Tuple, Dict, Any

from .gradient import build_multi_stop_gradient, position_to_t, rgb_to_ansi_fg, reset_ansi
from .palettes import PALETTES, DEFAULT_PALETTE_NAME


def _detect_color_enabled(force_color: bool | None) -> bool:
    if force_color is True:
        return True
    if force_color is False:
        return False
    return sys.stdout.isatty()


def _bbox_of_filled(px_grid: List[List[bool]]) -> Tuple[int, int, int, int] | None:
    min_x = None
    min_y = None
    max_x = None
    max_y = None
    for y, row in enumerate(px_grid):
        for x, on in enumerate(row):
            if on:
                if min_x is None or x < min_x:
                    min_x = x
                if max_x is None or x > max_x:
                    max_x = x
                if min_y is None or y < min_y:
                    min_y = y
                if max_y is None or y > max_y:
                    max_y = y
    if min_x is None:
        return None
    return min_x, min_y, max_x, max_y


def _collect_filled_axes(px_grid: List[List[bool]]) -> Tuple[List[int], List[int]]:
    h = len(px_grid)
    w = len(px_grid[0]) if h else 0
    filled_cols: List[int] = []
    filled_rows: List[int] = []
    for x in range(w):
        if any(px_grid[y][x] for y in range(h)):
            filled_cols.append(x)
    for y in range(h):
        if any(px_grid[y][x] for x in range(w)):
            filled_rows.append(y)
    return filled_cols, filled_rows


def wrap_and_render(
    px_grid: List[List[bool]],
    meta: Dict[str, Any],
    palette_name: str | None,
    direction: str,
    reverse_gradient: bool,
    pixel_width_mode: str,
    style: str,
    force_color: bool | None,
    color_space: str | None = None,
) -> str:
    if not px_grid:
        return ""

    palette_name = palette_name or DEFAULT_PALETTE_NAME
    colors = PALETTES.get(palette_name)
    if not colors:
        raise KeyError(f"Palette '{palette_name}' not found. Available: {', '.join(PALETTES.keys())}")

    if reverse_gradient:
        colors = list(reversed(colors))

    color_map = build_multi_stop_gradient(colors, (color_space or "rgb"))

    char_fill = "█"
    char_empty = " "
    cell_cols = 1
    # Normalize style value and support common synonyms
    s_raw = style or "block"
    s_lower = s_raw.lower()
    if s_lower in ("none", "off", "no", "plain"):
        s = "none"
    elif s_lower in ("simpleblock", "simple", "sb"):
        s = "simpleblock"
    elif s_lower in ("shade", "sh"):
        s = "shade"
    elif s_lower in ("block", "bk"):
        s = "block"
    else:
        s = s_lower
    mode = (pixel_width_mode or "h").lower()
    if s == "simpleblock":
        # Force hf semantics
        mode = "hf"
    if mode == "hf":
        char_fill = "██"
        char_empty = "  "
        cell_cols = 2
    elif mode.startswith("f"):
        char_fill = "██"
        char_empty = "　"
        cell_cols = 2

    max_cols = shutil.get_terminal_size((80, 24)).columns
    usable_cols = max(1, max_cols // cell_cols)

    height = len(px_grid)
    width = len(px_grid[0]) if height > 0 else 0

    # For shade style, append one extra empty row BEFORE style processing so that
    # the extra rendering line will see an empty row above and fill fully with '░'.
    if s == "shade" and height > 0 and width > 0:
        px_grid = px_grid + [[False for _ in range(width)]]
        height += 1

    bbox = _bbox_of_filled(px_grid)
    if bbox is None:
        return ""
    min_x, min_y, max_x, max_y = bbox

    # Build axis lists for smooth banding aligned with visible content
    filled_cols, filled_rows = _collect_filled_axes(px_grid)
    if not filled_cols:
        filled_cols = list(range(min_x, max_x + 1))
    if not filled_rows:
        filled_rows = list(range(min_y, max_y + 1))

    color_enabled = _detect_color_enabled(force_color)
    chunks: List[str] = []

    # Precompute x->t and y->t maps over filled axes for stability
    x_to_t: Dict[int, float] = {}
    y_to_t: Dict[int, float] = {}
    d = direction.lower()
    if d == "horizontal":
        total = max(1, len(filled_cols) - 1)
        for idx, x in enumerate(filled_cols):
            x_to_t[x] = idx / total
    elif d == "vertical":
        total = max(1, len(filled_rows) - 1)
        for idx, y in enumerate(filled_rows):
            y_to_t[y] = idx / total
    else:
        total_x = max(1, len(filled_cols) - 1)
        for idx, x in enumerate(filled_cols):
            x_to_t[x] = idx / total_x
        total_y = max(1, len(filled_rows) - 1)
        for idy, y in enumerate(filled_rows):
            y_to_t[y] = idy / total_y

    # Add one extra line if any style is active to complete visual effects
    extra_lines = 0 if s == "none" else 1

    for x0 in range(0, width, usable_cols):
        x1 = min(width, x0 + usable_cols)
        for y in range(height + extra_lines):
            line_parts: List[str] = []
            for x in range(x0, x1):
                # Detect current cell state (extra last line is always empty)
                current_on = (y < height) and px_grid[y][x]

                # Compute gradient t for the whole art; clamp for out-of-range rows
                if d == "horizontal":
                    t = x_to_t.get(x)
                    if t is None:
                        t = (x - min_x) / max(1, (max_x - min_x))
                elif d == "vertical":
                    t = y_to_t.get(y)
                    if t is None:
                        t = (y - min_y) / max(1, (max_y - min_y))
                else:
                    tx = x_to_t.get(x)
                    if tx is None:
                        tx = (x - min_x) / max(1, (max_x - min_x))
                    ty = y_to_t.get(y)
                    if ty is None:
                        ty = (y - min_y) / max(1, (max_y - min_y))
                    t = 0.5 * (tx + ty)
                if t < 0:
                    t = 0.0
                elif t > 1:
                    t = 1.0

                if current_on:
                    if color_enabled:
                        r, g, b = color_map(t)
                        if s == "simpleblock":
                            line_parts.append(rgb_to_ansi_fg(r, g, b) + "_|" + reset_ansi())
                        else:
                            line_parts.append(rgb_to_ansi_fg(r, g, b) + char_fill + reset_ansi())
                    else:
                        if s == "simpleblock":
                            line_parts.append("_|")
                        else:
                            line_parts.append(char_fill)
                else:
                    # style for empty cells
                    if s == "simpleblock":
                        # ignore other style rules
                        line_parts.append(char_empty)
                    elif s == "shade":
                        above_empty_or_first = (y == 0) or (not px_grid[y - 1][x])
                        if above_empty_or_first:
                            glyph = "░" * cell_cols
                            if color_enabled:
                                r, g, b = color_map(t)
                                line_parts.append(rgb_to_ansi_fg(r, g, b) + glyph + reset_ansi())
                            else:
                                line_parts.append(glyph)
                        else:
                            line_parts.append(char_empty)
                    elif s == "none":
                        # no extra styling at all
                        line_parts.append(char_empty)
                    else:
                        # block or default
                        tl = 1 if (y > 0 and x > 0 and px_grid[y - 1][x - 1]) else 0
                        tcell = 1 if (y > 0 and px_grid[y - 1][x]) else 0
                        lcell = 1 if (x > 0 and y < height and px_grid[y][x - 1]) else 0
                        key = (tl, tcell, lcell, 0)
                        mapping = {
                            (1, 1, 1, 0): "╔",
                            (1, 1, 0, 0): "═",
                            (1, 0, 1, 0): "║",
                            (1, 0, 0, 0): "╝",
                            (0, 0, 0, 0): " ",
                            (0, 1, 1, 0): "╔",
                            (0, 0, 1, 0): "╗",
                            (0, 1, 0, 0): "╚",
                        }
                        base = mapping.get(key, " ")

                        # width handling
                        if mode == "hf":
                            expand_hf = {
                                "╔": "╔═",
                                "═": "══",
                                "║": "║ ",
                                "╝": "╝ ",
                                " ": "  ",
                                "╗": "╗ ",
                                "╚": "╚═",
                            }
                            out_ch = expand_hf.get(base, "  ")
                        elif cell_cols == 2:
                            out_ch = base * 2
                        else:
                            out_ch = base

                        if color_enabled and base.strip() != "":
                            r, g, b = color_map(t)
                            line_parts.append(rgb_to_ansi_fg(r, g, b) + out_ch + reset_ansi())
                        else:
                            # keep empty coloring for blank
                            line_parts.append(out_ch if base.strip() != "" else char_empty)
            chunks.append("".join(line_parts))
        if x1 < width:
            chunks.append("")

    return "\n".join(chunks)
