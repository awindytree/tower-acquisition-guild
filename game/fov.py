"""Field of view: which cells the player can see from where they stand.

Recursive shadowcasting: scan outward in eight wedges, and whenever
something opaque blocks the view, remember the shadow it casts and skip
whatever lies inside it. Walls you can see are visible; what's behind
them isn't.

Distances count rows double, because cells are twice as tall as they are
wide; that keeps the visible area round on screen, like the torchlight.
"""
from __future__ import annotations

import numpy as np

# The eight wedges: how a wedge's local (column, row) maps onto map offsets.
# Columns are xx, xy, yx, yy for each wedge.
_MULT = [
    [1, 0, 0, -1, -1, 0, 0, 1],
    [0, 1, -1, 0, 0, -1, 1, 0],
    [0, 1, 1, 0, 0, -1, -1, 0],
    [1, 0, 0, 1, -1, 0, 0, -1],
]


def compute(transparent: np.ndarray, x: int, y: int, radius: float, aspect: float = 2.0) -> np.ndarray:
    """transparent[x, y] says what you can see through. Returns visible[x, y]."""
    w, h = transparent.shape
    visible = np.zeros((w, h), dtype=bool)
    visible[x, y] = True
    reach = int(radius) + 1
    for o in range(8):
        _cast(transparent, visible, x, y, 1, 1.0, 0.0, radius, reach, aspect,
              _MULT[0][o], _MULT[1][o], _MULT[2][o], _MULT[3][o])
    return visible


def _cast(transparent, visible, cx, cy, row, start, end, radius, reach, aspect, xx, xy, yx, yy):
    if start < end:
        return
    w, h = transparent.shape
    r2 = radius * radius
    new_start = start
    for j in range(row, reach + 1):
        dx, dy = -j - 1, -j
        blocked = False
        while dx <= 0:
            dx += 1
            mx, my = cx + dx * xx + dy * xy, cy + dx * yx + dy * yy
            l_slope, r_slope = (dx - 0.5) / (dy + 0.5), (dx + 0.5) / (dy - 0.5)
            if start < r_slope:
                continue
            if end > l_slope:
                break
            inside = 0 <= mx < w and 0 <= my < h
            if inside:
                ox, oy = mx - cx, (my - cy) * aspect
                if ox * ox + oy * oy <= r2:
                    visible[mx, my] = True
            opaque = not inside or not transparent[mx, my]
            if blocked:
                if opaque:
                    new_start = r_slope
                    continue
                blocked = False
                start = new_start
            elif opaque and j < reach:
                blocked = True
                _cast(transparent, visible, cx, cy, j + 1, start, l_slope, radius, reach, aspect, xx, xy, yx, yy)
                new_start = r_slope
        if blocked:
            break
