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
        help="Pixel width mode: h=half width, f=full width",
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
                force_color,
                color_space,
            )
            lines.append(out)
            lines.append("")
        sys.stdout.write("\n".join(lines) + "\n")
    else:
        sys.stdout.write(output + "\n")
