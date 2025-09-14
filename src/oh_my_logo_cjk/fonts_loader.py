from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Any

from PIL import Image, ImageDraw, ImageFont


@dataclass
class FontSpec:
    name: str
    path: str
    font_size: int
    grid_width: int
    grid_height: int
    offset_x: int = 0
    offset_y: int = 0


class FontRegistry:
    def __init__(self, fonts_dir: Path) -> None:
        self.fonts_dir = fonts_dir
        self._fonts: Dict[str, FontSpec] = {}

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "FontRegistry":
        return cls(repo_root / "fonts")

    def _parse_grid(self, raw_grid) -> Tuple[int, int]:
        if isinstance(raw_grid, int):
            return int(raw_grid), int(raw_grid)
        if isinstance(raw_grid, list) and len(raw_grid) == 2:
            return int(raw_grid[0]), int(raw_grid[1])
        raise ValueError(f"Unsupported grid_size format: {raw_grid}")

    def _parse_offset(self, raw_offset) -> Tuple[int, int]:
        if raw_offset is None:
            return 0, 0
        if isinstance(raw_offset, list) and len(raw_offset) == 2:
            return int(raw_offset[0]), int(raw_offset[1])
        raise ValueError(f"Unsupported offset format: {raw_offset}")

    def load_from_json(self) -> None:
        import json

        config_path = self.fonts_dir / "fonts.json"
        if not config_path.exists():
            raise FileNotFoundError(f"fonts config not found: {config_path}")
        data = json.loads(config_path.read_text(encoding="utf-8"))
        fonts = data.get("fonts", [])
        for item in fonts:
            name = str(item["name"]).strip()
            path = str(item["path"]).strip()
            raw_grid = item.get("grid_size")
            if raw_grid is None:
                raise ValueError(f"Missing grid_size for font '{name}'")
            grid_w, grid_h = self._parse_grid(raw_grid)
            font_size = int(item.get("font_size", grid_h))
            off_x, off_y = self._parse_offset(item.get("offset"))
            spec = FontSpec(
                name=name,
                path=path,
                font_size=font_size,
                grid_width=grid_w,
                grid_height=grid_h,
                offset_x=off_x,
                offset_y=off_y,
            )
            self._fonts[spec.name] = spec

    def list_names(self) -> List[str]:
        return list(self._fonts.keys())

    def _fallback_by_grid_or_size(self, token: str) -> FontSpec | None:
        import re

        m = re.search(r"(\d+)", token)
        if not m:
            return None
        g = int(m.group(1))
        for spec in self._fonts.values():
            if spec.grid_width == g or spec.grid_height == g or spec.font_size == g:
                return spec
        return None

    def get(self, name: str | None) -> FontSpec:
        if name is None:
            if not self._fonts:
                raise RuntimeError("No fonts available in fonts.json")
            return next(iter(self._fonts.values()))
        if name in self._fonts:
            return self._fonts[name]
        spec = self._fallback_by_grid_or_size(name)
        if spec is not None:
            return spec
        raise KeyError(f"Font '{name}' not found. Available: {', '.join(self._fonts.keys())}")

    def resolve_font_path(self, spec: FontSpec) -> Path:
        p = self.fonts_dir / spec.path
        if not p.exists():
            raise FileNotFoundError(f"Font file not found: {p}")
        return p


def _render_char_to_grid(
    ch: str,
    font: ImageFont.FreeTypeFont,
    grid_w: int,
    grid_h: int,
    extra_off_x: int,
    extra_off_y: int,
) -> List[List[bool]]:
    # Whitespace produces an empty cell (do not draw tofu)
    if ch.isspace():
        return [[False for _ in range(grid_w)] for _ in range(grid_h)]

    img = Image.new("L", (grid_w, grid_h), color=0)
    draw = ImageDraw.Draw(img)

    try:
        base_off_x, base_off_y = font.getoffset(ch)
    except Exception:
        base_off_x, base_off_y = (0, 0)

    eff_off_x = base_off_x + extra_off_x
    eff_off_y = base_off_y + extra_off_y

    draw.text((0 - eff_off_x, 0 - eff_off_y), ch, fill=255, font=font)

    pixels = img.load()
    result: List[List[bool]] = []
    on_count = 0
    for y in range(grid_h):
        row: List[bool] = []
        for x in range(grid_w):
            on = pixels[x, y] > 127
            on_count += 1 if on else 0
            row.append(on)
        result.append(row)

    # Missing glyph => tofu frame; not triggered for whitespace
    if on_count == 0:
        result = [[False for _ in range(grid_w)] for _ in range(grid_h)]
        for i in range(grid_w):
            result[0][i] = True
            result[grid_h - 1][i] = True
        for j in range(grid_h):
            result[j][0] = True
            result[j][grid_w - 1] = True
    return result


def rasterize_text_to_grid(text: str, spec: FontSpec, fonts_dir: Path, letter_spacing: int) -> Tuple[List[List[bool]], Dict[str, Any]]:
    font_path = fonts_dir / spec.path
    font = ImageFont.truetype(str(font_path), size=spec.font_size)

    per_char_grids: List[List[List[bool]]] = []
    for ch in text:
        g = _render_char_to_grid(
            ch,
            font,
            spec.grid_width,
            spec.grid_height,
            spec.offset_x,
            spec.offset_y,
        )
        per_char_grids.append(g)

    height = spec.grid_height
    stride = spec.grid_width + max(0, int(letter_spacing))
    total_width = len(per_char_grids) * spec.grid_width
    if len(per_char_grids) > 1 and letter_spacing > 0:
        total_width += letter_spacing * (len(per_char_grids) - 1)

    canvas: List[List[bool]] = [[False for _ in range(total_width)] for _ in range(height)]

    char_offsets: List[int] = []
    x_cursor = 0
    for idx, g in enumerate(per_char_grids):
        char_offsets.append(x_cursor)
        for y in range(height):
            row = g[y]
            for x in range(spec.grid_width):
                if row[x]:
                    canvas[y][x_cursor + x] = True
        x_cursor += spec.grid_width
        if idx != len(per_char_grids) - 1 and letter_spacing > 0:
            x_cursor += letter_spacing

    meta: Dict[str, Any] = {
        "char_width": spec.grid_width,
        "char_height": spec.grid_height,
        "char_count": len(per_char_grids),
        "letter_spacing": max(0, int(letter_spacing)),
        "char_offsets": char_offsets,
        "stride": stride,
    }
    return canvas, meta
