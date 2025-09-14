from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from colorama import just_fix_windows_console, init as colorama_init

from . import __version__
from .fonts_loader import FontRegistry, rasterize_text_to_grid
from .palettes import PALETTES, DEFAULT_PALETTE_NAME
from .render import wrap_and_render

app = typer.Typer(add_completion=True, no_args_is_help=True)


def _init_console() -> None:
    try:
        just_fix_windows_console()
        # Do not convert/strip ANSI; we emit 24-bit codes ourselves
        colorama_init(convert=False, strip=False, autoreset=False)
    except Exception:
        pass


def main() -> None:
    _init_console()
    argv = sys.argv[1:]
    # Fast-path root options to avoid Typer routing quirks
    if any(arg in ("-v", "--version") for arg in argv):
        print(f"oh-my-logo-cjk {__version__}")
        sys.exit(0)
    if argv and argv[0] not in ("-h", "--help"):
        if argv[0] != "run":
            sys.argv.insert(1, "run")
    app()


@app.callback()
def _version_callback(
    version: Optional[bool] = typer.Option(
        None, "-v", "--version", help="Show version number", is_eager=True
    )
):
    # Kept for help display; main() already prints version directly
    if version:
        typer.echo(f"oh-my-logo-cjk {__version__}")
        raise typer.Exit()


@app.command(context_settings={"ignore_unknown_options": False})
def run(
    text: Optional[str] = typer.Argument(None, help="Text to render in quotes e.g. \"你好世界\""),
    font: Optional[str] = typer.Argument(None, help="Font name from fonts.json, e.g. 7px"),
    palette: Optional[str] = typer.Argument(None, help="Palette name, e.g. grad-blue"),
    pixel_width: str = typer.Option(
        "h",
        "-pw",
        "--pixel-width",
        help="每个像素输出的字符模式是全角还是半角，如果参数为h（half），则为半角的'█'和空格；如果参数为f（full），则用全角的\"█\"和全角空格\"　\"，如果参数为hf（half-full），则为两个半角的'█'或半角空格作为视觉上的全角字符来绘制",
        show_default=True,
    ),
    direction: str = typer.Option(
        "vertical",
        "-d",
        "--direction",
        help="Gradient direction: vertical, horizontal, diagonal",
        show_default=True,
    ),
    letter_spacing: int = typer.Option(
        1, "--letter-spacing", help="Spaces between characters in filled mode (0+)", min=0
    ),
    style: str = typer.Option(
        "block",
        "-s",
        "--style",
        help=(
            "额外样式选择：none：无额外样式；simpleBlock：如果使用此选项，将-pw的规则强制应用为hf（half-full），然后将其中原本的两个半角的'█'替换为\"_|\"；"
            "shade：阴影样式（实现方式：依次遍历空格留空格子，如果空格子正上方一格有填充，那么保持留空，否则填充\"░\"。如果正上方一格无格子，也就是第一行，则填充\"░\"）；"
            "block：伪3d格子样式（实现方式：依次遍历空格子，检查该格子左上角方向的三个相邻格子，这里为说明方便，将该包含该空格子的左上角三个格子共四个格子是否填充描述为：[1，1，1，0]（最左上、该空格上方格子、该格子左边格子、该空格子），"
            "实心为1、空格留白为0，制表符阴影的填充规则为：[1，1，1，0]-\"╔\", [1，1，0，0]-\"═\", [1，0，1，0]-\"║\", [1，0，0，0]-\"╝\", [0，0，0，0]-\" \"， [0，1，1，0]-\"╝\", [0，0，1，0]-\"╗\", [0，1，0，0]-\"╚\"）；"
            "默认样式为block"
        ),
        show_default=True,
    ),
    reverse_gradient: bool = typer.Option(
        False, "--reverse-gradient", help="Reverse gradient colors"
    ),
    list_palettes: bool = typer.Option(
        False, "-l", "--list-palettes", help="Show all available color palettes", is_eager=True
    ),
    gallery: bool = typer.Option(
        False, "--gallery", help="Render text in all available palettes"
    ),
    force_color: Optional[bool] = typer.Option(
        None,
        "--color/--no-color",
        help="Force enable/disable color output",
        show_default=False,
    ),
    color_space: str = typer.Option(
        "rgb", "--color-space", help="Color space for interpolation: rgb or oklab"
    ),
    debug_gradient: bool = typer.Option(
        False, "--debug-gradient", help="Print gradient bbox and axes stats"
    ),
):
    """oh-my-logo-cjk <text> [font] [palette] [options]"""
    repo_root = Path.cwd()
    registry = FontRegistry.from_repo_root(repo_root)
    registry.load_from_json()

    if list_palettes:
        names = sorted(PALETTES.keys())
        typer.echo("Available palettes:")
        for name in names:
            colors = ", ".join(PALETTES[name])
            typer.echo(f"- {name}: {colors}")
        raise typer.Exit()

    if text is None:
        typer.echo("Error: missing <text>. Usage: oh-my-logo-cjk \"你好世界\" [font] [palette] [options]", err=True)
        raise typer.Exit(code=2)

    try:
        spec = registry.get(font)
    except Exception as e:
        typer.echo(f"Font error: {e}", err=True)
        raise typer.Exit(code=2)

    selected_palette = palette or DEFAULT_PALETTE_NAME

    try:
        grid, meta = rasterize_text_to_grid(text, spec, registry.fonts_dir, max(0, int(letter_spacing)))
    except Exception as e:
        typer.echo(f"Render error: {e}", err=True)
        raise typer.Exit(code=1)

    output = wrap_and_render(
        grid,
        meta,
        selected_palette,
        direction,
        reverse_gradient,
        pixel_width,
        style,
        force_color,
        color_space,
    )

    if debug_gradient:
        from .render import _bbox_of_filled, _collect_filled_axes  # type: ignore

        bbox = _bbox_of_filled(grid)
        if bbox:
            min_x, min_y, max_x, max_y = bbox
            cols, rows = _collect_filled_axes(grid)
            sys.stderr.write(f"[debug] bbox=({min_x},{min_y})-({max_x},{max_y}), filled_cols={len(cols)}, filled_rows={len(rows)}\n")

    if gallery:
        lines = []
        for name in sorted(PALETTES.keys()):
            lines.append(f"=== {name} ===")
            out = wrap_and_render(
                grid,
                meta,
                name,
                direction,
                reverse_gradient,
                pixel_width,
                style,
                force_color,
                color_space,
            )
            lines.append(out)
            lines.append("")
        sys.stdout.write("\n".join(lines) + "\n")
    else:
        sys.stdout.write(output + "\n")
