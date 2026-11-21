"""The camera: which part of the map is on screen.

It keeps the player centred, but stops at the map's edges so you never see
past them. A map smaller than the screen in some direction is centred in it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Viewport:
    map_x: int     # first map column shown
    map_y: int     # first map row shown
    screen_x: int  # where that column appears on screen
    screen_y: int
    width: int     # how many cells are shown
    height: int

    def to_screen(self, x: int, y: int) -> tuple[int, int] | None:
        """Screen position of a map cell, or None if it's off screen."""
        sx, sy = x - self.map_x, y - self.map_y
        if 0 <= sx < self.width and 0 <= sy < self.height:
            return self.screen_x + sx, self.screen_y + sy
        return None


def _axis(focus: int, map_len: int, view_len: int) -> tuple[int, int, int]:
    """(first map cell, screen offset, cells shown) along one direction."""
    if map_len <= view_len:
        return 0, (view_len - map_len) // 2, map_len
    first = min(max(focus - view_len // 2, 0), map_len - view_len)
    return first, 0, view_len


def follow(focus_x: int, focus_y: int, map_w: int, map_h: int, view_w: int, view_h: int) -> Viewport:
    mx, sx, w = _axis(focus_x, map_w, view_w)
    my, sy, h = _axis(focus_y, map_h, view_h)
    return Viewport(mx, my, sx, sy, w, h)
