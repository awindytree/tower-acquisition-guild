"""The minimap (v0.53.0, user): the whole current map, shrunk to fit a box.

Drawn with half blocks (▀): each console cell holds two square "pixels", the top one in
the glyph's colour and the bottom one in the background colour. A map cell is twice as
tall as it is wide, so at scale k one pixel covers k map columns and k/2 map rows, which
keeps the map's shape. Only explored ground shows on fog-of-war maps.

Used in two places: the side panel (toggled with n, in place of the messages) and the full
map window (v), over the map view.
"""
from __future__ import annotations

import math

import numpy as np

from game.tiles import TILE_TYPES, GROUND

UNSEEN = (10, 9, 8)
PLAYER = (255, 90, 230)       # the Hunter's colour (game/player.py)
WAY = (240, 160, 80)          # ways deeper and back, the trail home, gates
CREATURE = (220, 70, 60)
MARKED = (255, 214, 90)
PERSON = (232, 196, 100)

# Map-file symbols drawn as landmarks over the terrain, in their own colour, wherever explored.
WAY_SYMBOLS = set("<>HG")
LANDMARK_SYMBOLS = set("BVYQ")     # Bytorsskug, villages, the Wayfinder, the boga circuit


def _mix(a, b, t: float):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _palette() -> np.ndarray:
    """A minimap colour per tile kind: open ground lit, walls and rock dark, water and
    thickets in between."""
    out = np.zeros((len(TILE_TYPES), 3), dtype=np.float32)
    for i, t in enumerate(TILE_TYPES):
        fg = t.colors[0] if t.colors else (120, 110, 100)
        bg = t.bg if t.bg else GROUND
        if t.walkable:
            c = _mix(fg, bg, 0.15)
        elif t.transparent:              # water and the like
            c = tuple(int(v * 0.7) for v in _mix(fg, bg, 0.2))
        else:                            # walls, rock, solid trees
            c = tuple(int(v * 0.5) for v in _mix(fg, bg, 0.3))
        out[i] = c
    return out


PALETTE = _palette()


def scale_for(w: int, h: int, cols: int, rows: int) -> float:
    """Map columns per pixel so a w x h stretch of map fits cols x rows console cells (2 pixels a cell)."""
    return max(w / max(1, cols), 2 * h / max(1, 2 * rows), 1.0)


def window(engine, gm, cols: int, rows: int, scale: float) -> tuple[int, int, int, int]:
    """A stretch of map around the Hunter at a fixed scale (for big maps in the side panel)."""
    w = min(gm.width, int(cols * scale))
    h = min(gm.height, int(rows * scale))
    x0 = max(0, min(gm.width - w, engine.player.x - w // 2))
    y0 = max(0, min(gm.height - h, engine.player.y - h // 2))
    return x0, y0, w, h


def pixels(engine, gm, cols: int, rows: int, area=None) -> tuple[np.ndarray, float, int, int]:
    """The minimap as an RGB array (px_w, px_h, 3), with its scale and size in pixels. area
    (x0, y0, w, h) limits it to a stretch of the map; by default, the whole map."""
    ax, ay, aw, ah = area or (0, 0, gm.width, gm.height)
    k = scale_for(aw, ah, cols, rows)
    kx, ky = k, k / 2
    pw = min(cols, max(1, math.ceil(aw / kx)))
    ph = min(2 * rows, max(1, math.ceil(ah / ky)))
    seen_all = gm.explored if gm.fog else np.ones((gm.width, gm.height), dtype=bool)
    seen = seen_all[ax:ax + aw, ay:ay + ah]
    colours = PALETTE[gm.kinds[ax:ax + aw, ay:ay + ah]]          # (aw, ah, 3)
    img = np.empty((pw, ph, 3), dtype=np.float32)
    img[:] = UNSEEN
    xs = [int(round(i * kx)) for i in range(pw + 1)]
    ys = [int(round(j * ky)) for j in range(ph + 1)]
    for i in range(pw):
        x0, x1 = xs[i], max(xs[i] + 1, xs[i + 1])
        for j in range(ph):
            y0, y1 = ys[j], max(ys[j] + 1, ys[j + 1])
            m = seen[x0:x1, y0:y1]
            if m.any():
                img[i, j] = colours[x0:x1, y0:y1][m].mean(axis=0)

    def put(x, y, colour):
        i, j = int((x - ax) / kx), int((y - ay) / ky)
        if not (ax <= x < ax + aw and ay <= y < ay + ah):
            return
        if 0 <= i < pw and 0 <= j < ph:
            img[i, j] = colour

    # Landmarks and ways, where seen.
    from game.tiles import TILE_TYPES as TT
    special = np.isin(gm.kinds, [i for i, t in enumerate(TT) if t.symbol in WAY_SYMBOLS | LANDMARK_SYMBOLS])
    for x, y in zip(*np.nonzero(special & seen_all)):
        t = TT[gm.kinds[x, y]]
        put(x, y, WAY if t.symbol in WAY_SYMBOLS else (t.colors[0] if t.colors else WAY))
    # Creatures in view (a marked bounty in gold), people, then you on top.
    visible = getattr(engine, "visible", None)
    for mo in gm.monsters:
        if not gm.fog or (visible is not None and visible[mo.x, mo.y]):
            if getattr(mo, "burrowed", False):
                continue
            put(mo.x, mo.y, MARKED if getattr(mo, "bounty", 0) else CREATURE)
    from game import fieldskills            # creatures Tracking tells you of, unseen (v0.56.0)
    for mo in fieldskills.minimap_creatures(engine, gm):
        put(mo.x, mo.y, MARKED if getattr(mo, "bounty", 0) else CREATURE)
    for n in gm.npcs:
        if not gm.fog or seen_all[n.x, n.y]:
            put(n.x, n.y, n.color)
    if engine.game_map is gm:
        put(engine.player.x, engine.player.y, PLAYER)
    return img.astype(np.uint8), k, pw, ph


def draw(console, engine, x: int, y: int, cols: int, rows: int, bg=(0, 0, 0), gm=None,
         max_scale: float | None = None) -> tuple[int, int]:
    """Draw the minimap of gm (default: the current map) in the box at (x, y), centred.
    With max_scale, a map too big to show at that scale shows the stretch around the Hunter.
    Returns the (cols, rows) it used."""
    gm = gm or engine.game_map
    area = None
    if max_scale and scale_for(gm.width, gm.height, cols, rows) > max_scale:
        area = window(engine, gm, cols, rows, max_scale)
    img, k, pw, ph = pixels(engine, gm, cols, rows, area)
    used_rows = (ph + 1) // 2
    ox = x + (cols - pw) // 2
    oy = y + (rows - used_rows) // 2
    for i in range(pw):
        for r in range(used_rows):
            top = tuple(int(v) for v in img[i, 2 * r])
            bottom = tuple(int(v) for v in img[i, 2 * r + 1]) if 2 * r + 1 < ph else bg
            console.print(ox + i, oy + r, "▀", fg=top, bg=bottom)
    return pw, used_rows
