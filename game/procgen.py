"""Procedural generation of hunt areas.

Each style is a function that returns a grid of map symbols (the same
symbols as the map files). Then place_features() finds the two points
furthest apart (where you come in, and the far end) and scatters loot.

Every area comes from a seed, so the same contract always gives the
same areas.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

Grid = list[list[str]]  # grid[y][x]

# Movement is four-way (v0.41.0): an area is connected only through side-by-side cells.
STEPS = [(0, -1), (0, 1), (-1, 0), (1, 0)]
NEIGHBOURS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]   # for shaping caves
# Bump when generation changes: a hunt saved under another generation can't be rebuilt
# from its seed, so loading one sends the Hunter home (game/saves.py).
GENERATION = 5


@dataclass
class AreaPlan:
    """Everything a generated area needs, before it becomes a GameMap."""
    rows: list[str]
    entry: tuple[int, int]
    far_end: tuple[int, int]
    items: list[tuple[int, int, str, int]] = field(default_factory=list)


# ---- Styles ---------------------------------------------------------------
def caves(rng: random.Random, w: int, h: int) -> Grid:
    """Winding natural caverns in rough stone (cellular automaton), with the odd pool."""
    grid = _cellular(rng, w, h, wall="%", floor="c", fill=0.45)
    _ponds(rng, grid, "~", count=rng.randint(0, 2), floor="c", wall="%")   # (where hookjaw eels wait)
    return grid


def mountains(rng: random.Random, w: int, h: int) -> Grid:
    """High, broken ground: open slopes between outcrops of rock (v0.49.0)."""
    grid = _cellular(rng, w, h, wall="%", floor=",", fill=0.47)
    for y in range(1, h - 1):                       # loose scree on the slopes
        for x in range(1, w - 1):
            if grid[y][x] == "," and rng.random() < 0.12:
                grid[y][x] = "."
    return grid


def plains(rng: random.Random, w: int, h: int) -> Grid:
    """Wide open grassland, a few copses and ponds (v0.49.0)."""
    grid = _cellular(rng, w, h, wall="T", floor=",", fill=0.3)
    _ponds(rng, grid, "~", count=rng.randint(0, 2))
    return grid


def forest(rng: random.Random, w: int, h: int) -> Grid:
    """Clearings and paths through dense trees, with the odd pond."""
    grid = _cellular(rng, w, h, wall="T", floor=",", fill=0.42)
    _ponds(rng, grid, "~", count=rng.randint(1, 3))
    return grid


def ruins(rng: random.Random, w: int, h: int) -> Grid:
    """Broken-down built rooms, joined by tunnels through the rock."""
    grid = [["%"] * w for _ in range(h)]
    rooms: list[tuple[int, int, int, int]] = []
    for _ in range(200):
        if len(rooms) >= 12:
            break
        rw, rh = rng.randint(6, 13), rng.randint(5, 8)
        x0, y0 = rng.randint(1, w - rw - 2), rng.randint(1, h - rh - 2)
        x1, y1 = x0 + rw - 1, y0 + rh - 1
        if any(x0 <= bx1 + 2 and x1 >= bx0 - 2 and y0 <= by1 + 2 and y1 >= by0 - 2
               for bx0, by0, bx1, by1 in rooms):
            continue
        rooms.append((x0, y0, x1, y1))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                edge = x in (x0, x1) or y in (y0, y1)
                grid[y][x] = "#" if edge else "."
    # Join each room to the next (sorted left to right) with an L-shaped
    # tunnel, plus a couple of extra tunnels so there are loops.
    rooms.sort()
    links = list(zip(rooms, rooms[1:]))
    for _ in range(2):
        links.append(tuple(rng.sample(rooms, 2)))
    for a, b in links:
        ax, ay = (a[0] + a[2]) // 2, (a[1] + a[3]) // 2
        bx, by = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
        options = [
            [(x, ay) for x in _span(ax, bx)] + [(bx, y) for y in _span(ay, by)],
            [(ax, y) for y in _span(ay, by)] + [(x, by) for x in _span(ax, bx)],
        ]
        # Prefer the route that breaks through the fewest walls.
        path = min(options, key=lambda p: sum(grid[y][x] == "#" for x, y in p))
        walls = {(x, y) for x, y in path if grid[y][x] == "#"}
        for i, (x, y) in enumerate(path):
            if grid[y][x] == "%":
                grid[y][x] = "c"
            elif (x, y) in walls:
                # A clean crossing gets a doorway (sometimes); a tunnel that
                # runs along a wall just leaves a breach.
                beside = [path[j] for j in (i - 1, i + 1) if 0 <= j < len(path)]
                crossing = not any(p in walls for p in beside)
                grid[y][x] = "+" if crossing and rng.random() < 0.5 else "."
    # Some walls have crumbled.
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if grid[y][x] == "#" and rng.random() < 0.04:
                grid[y][x] = "."
    _keep_largest_region(grid, "%")
    return grid


def grassland(rng: random.Random, w: int, h: int) -> Grid:
    """Lush, open grassland (v0.70.0, user: Verdant): a few copses, and wide swathes of tall
    grass you can walk through but not see over."""
    grid = _cellular(rng, w, h, wall="T", floor=",", fill=0.3)
    for y in range(1, h - 1):                     # thin the copses out to the odd stand of trees
        for x in range(1, w - 1):
            if grid[y][x] == "T" and rng.random() < 0.7:
                grid[y][x] = ","
    _ponds(rng, grid, "~", count=rng.randint(0, 1))
    _patches(rng, grid, ",", "g", share=0.5)
    return grid


def marsh(rng: random.Random, w: int, h: int) -> Grid:
    """Bog and marsh (v0.70.0, user: Deeply Ill): mud winding between black pools, reed beds
    that hide what's in them, the odd tussock of grass."""
    grid = _cellular(rng, w, h, wall="~", floor="e", fill=0.36)
    _patches(rng, grid, "e", "r", share=0.5)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if grid[y][x] == "e" and rng.random() < 0.06:
                grid[y][x] = ","
    return grid


def _patches(rng: random.Random, grid: Grid, under: str, over: str, share: float) -> None:
    """Blobs of `over` on cells of `under` (smoothed noise), about `share` of them."""
    h, w = len(grid), len(grid[0])
    cells = [[rng.random() < share for _ in range(w)] for _ in range(h)]
    for _ in range(3):
        cells = [[sum(cells[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) >= 5
                  if 0 < x < w - 1 and 0 < y < h - 1 else False for x in range(w)] for y in range(h)]
    for y in range(h):
        for x in range(w):
            if cells[y][x] and grid[y][x] == under:
                grid[y][x] = over


STYLES = {"caves": caves, "forest": forest, "ruins": ruins, "mountains": mountains, "plains": plains,
          "grassland": grassland, "marsh": marsh}


# ---- Putting it together ---------------------------------------------------
def generate(style: str, seed: int, w: int, h: int) -> AreaPlan:
    """A connected area with an entry point and a far end, furthest apart."""
    rng = random.Random(seed)
    for _ in range(20):
        grid = STYLES[style](rng, w, h)
        open_cells = [(x, y) for y in range(h) for x in range(w) if _walkable(grid[y][x])]
        if len(open_cells) >= w * h * 0.25:
            break
    entry = _furthest(grid, rng.choice(open_cells))[0]
    far_end, _ = _furthest(grid, entry)
    return AreaPlan(["".join(r) for r in grid], entry, far_end)


def scatter_loot(plan: AreaPlan, rng: random.Random, danger: int) -> None:
    """Shards and a few supplies, mostly away from the entry."""
    dist = _distances(plan.rows, plan.entry)
    spots = [p for p, d in dist.items() if d > 8 and p != plan.far_end
             and plan.rows[p[1]][p[0]] in WALKABLE_FLOORS]
    rng.shuffle(spots)
    # Loose shards are small change (user, 2026-11-19): the odd pile, the difference between
    # affording something and not. Income comes from artifacts, contracts, requests and jobs.
    for _ in range(rng.randint(0, 2)):
        if spots:
            x, y = spots.pop()
            plan.items.append((x, y, "shard", rng.randint(1, 3) + danger // 2))
    supplies = ["healing_draught", "ration", "torch", "healing_draught"]
    for _ in range(rng.randint(0, 2)):
        if spots:
            x, y = spots.pop()
            plan.items.append((x, y, rng.choice(supplies), 1))


def scatter_extra(plan: AreaPlan, rng: random.Random, items) -> None:
    """Extra things lying about an area, for a place's words (v0.70.0): ((item id, least, most), ...),
    each a separate find, anywhere but the entry and the far end."""
    spots = sorted(p for p in _distances(plan.rows, plan.entry)
                   if p not in (plan.entry, plan.far_end) and plan.rows[p[1]][p[0]] in WALKABLE_FLOORS)
    taken = {(x, y) for x, y, _, _ in plan.items}
    spots = [p for p in spots if p not in taken]
    rng.shuffle(spots)
    for item_id, least, most in items:
        for _ in range(rng.randint(int(least), int(most))):
            if spots:
                x, y = spots.pop()
                plan.items.append((x, y, item_id, 1))


# ---- Helpers ----------------------------------------------------------------
WALKABLE_FLOORS = set("c.,ger")       # (g tall grass, e mud, r reeds: v0.70.0)
WALKABLE = set("c.,+><Hger")


def _walkable(ch: str) -> bool:
    return ch in WALKABLE


def _span(a: int, b: int) -> range:
    return range(a, b + 1) if a <= b else range(a, b - 1, -1)


def _cellular(rng: random.Random, w: int, h: int, wall: str, floor: str, fill: float) -> Grid:
    cells = [[rng.random() < fill for _ in range(w)] for _ in range(h)]
    for step in range(5):
        nxt = [[True] * w for _ in range(h)]
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                n = sum(cells[y + dy][x + dx] for dx, dy in NEIGHBOURS)
                # Walls clump together; early on, empty patches get a pillar
                # so the open spaces don't grow too big.
                nxt[y][x] = n >= 5 or (cells[y][x] and n >= 4) or (step < 2 and n == 0)
        cells = nxt
    grid = [[wall if c else floor for c in row] for row in cells]
    _keep_largest_region(grid, wall)
    return grid


def _ponds(rng: random.Random, grid: Grid, water: str, count: int, floor: str = ",", wall: str = "T") -> None:
    """Small ponds, only where they can't cut the area in two."""
    h, w = len(grid), len(grid[0])
    for _ in range(count):
        cx, cy = rng.randint(4, w - 5), rng.randint(3, h - 4)
        rx, ry = rng.randint(2, 4), rng.randint(1, 3)
        before = sum(row.count(floor) for row in grid)
        saved = [row[:] for row in grid]
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                if grid[y][x] == floor and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                    grid[y][x] = water
        lost = before - sum(row.count(floor) for row in grid)
        _keep_largest_region(grid, wall)
        if before - sum(row.count(floor) for row in grid) > lost:  # it split the map: undo
            grid[:] = saved


def dead_end_pool(grid: Grid, keep_clear: set, rng: random.Random) -> tuple[int, int] | None:
    """Turn one dead-end floor cell (open on one side only) into water, away from the cells
    given; a dead end can't cut an area in two. Returns the cell, or None."""
    h, w = len(grid), len(grid[0])
    cells = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1)
             if grid[y][x] in WALKABLE_FLOORS and (x, y) not in keep_clear
             and sum(_walkable(grid[y + dy][x + dx]) for dx, dy in STEPS) == 1]
    if not cells:
        return None
    x, y = rng.choice(sorted(cells))
    grid[y][x] = "~"
    return x, y


OPENED = {"%": "c", "T": ",", "#": ".", "~": ","}   # what a blocking cell becomes when opened up


def _open_pinches(grid: Grid) -> None:
    """Where open ground meets only at a corner (two open cells diagonal to each
    other, with both cells between them blocked), open one of those cells, so the
    way through needs no diagonal step. Prefers opening rock or trees to water."""
    h, w = len(grid), len(grid[0])
    for _ in range(4):
        changed = False
        for y in range(1, h - 2):
            for x in range(1, w - 2):
                a, b = grid[y][x], grid[y][x + 1]
                c, d = grid[y + 1][x], grid[y + 1][x + 1]
                if _walkable(a) and _walkable(d) and not _walkable(b) and not _walkable(c):
                    pick = [(x + 1, y), (x, y + 1)]
                elif _walkable(b) and _walkable(c) and not _walkable(a) and not _walkable(d):
                    pick = [(x, y), (x + 1, y + 1)]
                else:
                    continue
                pick.sort(key=lambda q: grid[q[1]][q[0]] == "~")      # water last
                ox, oy = pick[0]
                if not (0 < ox < w - 1 and 0 < oy < h - 1):
                    ox, oy = pick[1]
                grid[oy][ox] = OPENED.get(grid[oy][ox], ".")
                changed = True
        if not changed:
            return


def _keep_largest_region(grid: Grid, wall: str) -> None:
    """Fill in every pocket of open ground except the biggest one (after joining
    pockets that touched only at a corner)."""
    _open_pinches(grid)
    h, w = len(grid), len(grid[0])
    seen: set[tuple[int, int]] = set()
    regions: list[set[tuple[int, int]]] = []
    for y in range(h):
        for x in range(w):
            if (x, y) not in seen and _walkable(grid[y][x]):
                region = set(_distances(["".join(r) for r in grid], (x, y)))
                seen |= region
                regions.append(region)
    if not regions:
        return
    biggest = max(regions, key=len)
    for region in regions:
        if region is not biggest:
            for x, y in region:
                grid[y][x] = wall


def _distances(rows, start: tuple[int, int]) -> dict[tuple[int, int], int]:
    """Steps from start to every reachable cell (moving in 4 directions)."""
    h, w = len(rows), len(rows[0])
    dist = {start: 0}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in STEPS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in dist and _walkable(rows[ny][nx]):
                dist[(nx, ny)] = dist[(x, y)] + 1
                queue.append((nx, ny))
    return dist


def _furthest(grid, start: tuple[int, int]) -> tuple[tuple[int, int], int]:
    rows = ["".join(r) for r in grid] if isinstance(grid[0], list) else grid
    dist = _distances(rows, start)
    far = max(dist, key=dist.get)
    return far, dist[far]
