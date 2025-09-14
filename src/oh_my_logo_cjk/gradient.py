from __future__ import annotations

from typing import Iterable, Tuple
import math


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return r, g, b


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_rgb(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return (
        int(round(_lerp(c1[0], c2[0], t))),
        int(round(_lerp(c1[1], c2[1], t))),
        int(round(_lerp(c1[2], c2[2], t))),
    )


# OKLab conversion helpers (approx, sufficient for interpolation)
# Source: https://bottosson.github.io/posts/oklab/

def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> int:
    if c <= 0.0031308:
        v = 12.92 * c
    else:
        v = 1.055 * (c ** (1.0 / 2.4)) - 0.055
    return int(round(max(0.0, min(1.0, v)) * 255.0))


def _rgb_to_oklab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    lr = _srgb_to_linear(r)
    lg = _srgb_to_linear(g)
    lb = _srgb_to_linear(b)

    l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb

    l_ = l ** (1.0 / 3.0)
    m_ = m ** (1.0 / 3.0)
    s_ = s ** (1.0 / 3.0)

    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return (L, a, b2)


def _oklab_to_rgb(L: float, a: float, b: float) -> Tuple[int, int, int]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b

    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3

    lr = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    lb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    r = _linear_to_srgb(lr)
    g = _linear_to_srgb(lg)
    b = _linear_to_srgb(lb)
    return (r, g, b)


def _lerp_oklab(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    L1, a1, b1 = _rgb_to_oklab(*c1)
    L2, a2, b2 = _rgb_to_oklab(*c2)
    L = _lerp(L1, L2, t)
    a = _lerp(a1, a2, t)
    b = _lerp(b1, b2, t)
    return _oklab_to_rgb(L, a, b)


def rgb_to_ansi_fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def reset_ansi() -> str:
    return "\x1b[0m"


def build_multi_stop_gradient(hex_colors: Iterable[str], color_space: str = "rgb"):
    stops = [_hex_to_rgb(c) for c in hex_colors]
    if not stops:
        stops = [(255, 255, 255)]

    def map_t(t: float) -> Tuple[int, int, int]:
        if t <= 0:
            return stops[0]
        if t >= 1:
            return stops[-1]
        seg_count = len(stops) - 1
        f = t * seg_count
        i = int(f)
        local_t = f - i
        if color_space.lower() == "oklab":
            return _lerp_oklab(stops[i], stops[i + 1], local_t)
        return _lerp_rgb(stops[i], stops[i + 1], local_t)

    return map_t


def position_to_t(x: int, y: int, width: int, height: int, direction: str) -> float:
    if width <= 1:
        width = 2
    if height <= 1:
        height = 2
    d = direction.lower()
    if d == "horizontal":
        return x / (width - 1)
    if d == "vertical":
        return y / (height - 1)
    return (x / (width - 1) + y / (height - 1)) * 0.5
