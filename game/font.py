"""Letters the CP437 font lacks (þ, Þ...).

tools/make_tileset.py draws them from GNU Unifont into the rows after CP437 in
data/font_8x16.png (16 columns: CP437 in rows 0-15, then EXTRA in order). main.py loads
the whole sheet with charmap(), so they're part of the tileset from the start.
"""
from __future__ import annotations

EXTRA = "þÞ"  # keep in step with tools/make_tileset.py


def charmap(cp437) -> list[int]:
    """CP437 (as tcod gives it), then the extra letters."""
    return list(cp437) + [ord(c) for c in EXTRA]


def rows() -> int:
    return 16 + (len(EXTRA) + 15) // 16
