"""Build data/maps/city.txt: Bytorsskug, laid out after the city plan.

The big shapes come from the plan (Bytorsskug.png): the wall and its towers,
the river's course, the plaza and the gates, read off by hand in image
pixels. Everything inside is generated on simple rules:

  * streets are always two cells wide: a ring road inside the wall, main
    streets from each gate to the plaza, and side streets that split the
    rest into blocks (some jog sideways partway along);
  * bridges are straight and two cells wide, where streets cross the river,
    with a short straight approach road where a bank isn't already street;
  * houses are rectangles or L-shapes with a wall, a wooden floor and a door
    onto a street, and never touch each other.

Re-running it overwrites hand edits to the map. Change SEED for a different
town on the same plan.

    python tools/city_plan/build_city.py data/maps/city.txt
"""
import random
import sys
from collections import deque

OUT = sys.argv[1] if len(sys.argv) > 1 else "data/maps/city.txt"
SEED = 11
W, H = 232, 116
IMAGE = 780  # the plan is 780 x 780 pixels
SX, SY = IMAGE / W, IMAGE / H

TOWERS = [(308, 137), (555, 165), (576, 251), (590, 312), (587, 342), (559, 553), (548, 581),
          (528, 608), (500, 618), (469, 621), (430, 613), (342, 578), (191, 431), (170, 404),
          (160, 376), (162, 310), (165, 281)]
GATES = [("north", (533, 162), (0, -1)), ("east", (584, 370), (1, 0)),
         ("south", (339, 576), (0, 1)), ("west", (161, 345), (-1, 0))]
RIVER_PATH = [(0, 245), (60, 262), (100, 282), (150, 285), (165, 300), (240, 320), (300, 345),
              (350, 365), (380, 378), (400, 405), (430, 430), (445, 460), (452, 492), (462, 522),
              (495, 527), (520, 545), (530, 575), (545, 600), (565, 628), (608, 650), (622, 700),
              (640, 750), (690, 790)]
PLAZA_PX = (388, 168, 480, 258)    # image pixels: x0, y0, x1, y1
WELL_PX = (433, 213)
SUBURB_PX = (25, 285, 155, 485)    # outside the west gate
BLOCK_W, BLOCK_H = 34, 15          # side streets stop splitting blocks below this size

# The Academy: the largest building in the city, at its northernmost point, fronting the plaza.
# The wall bulges north around it (the 2nd to 5th towers above). b = bookshelves, @ = the librarian.
ACADEMY = [
    "########################################",
    "#bbbbbbbbbb..#............#..bbbbbbbbbb#",
    "#............#.....@......#............#",
    "#bbbb.bbbbb..#............#..bbbbb.bbbb#",
    "#............#............#............#",
    "#bbbb.bbbbb..#............#..bbbbb.bbbb#",
    "#............+............+............#",
    "#bbbb.bbbbb..#............#..bbbbb.bbbb#",
    "#............#............#............#",
    "#bbbb.bbbbb..#............#..bbbbb.bbbb#",
    "#............#............#............#",
    "#bbbbbbbbbb..#............#..bbbbbbbbbb#",
    "#################+####+#################",
]

# The guild hall (redesigned v0.54.0, user: the clerk works from a small room behind a window).
# Front hall: the two boards in its front corners (P, J: placed below), where you start (@).
# Back middle: the clerk's office, closed off, with a service window (W) onto the hall; walking
# into the window talks to whoever's behind it (";window=x,y folk" in the map file).
# Back left: the training corner (the trainer; room for another teacher later).
# Back right: the stash room (the chest, C) and the retired Hunter who teaches (the mentor).
GUILD = [
    "#########+###L######",   # L: the plaque (v0.60.0): who paid for the Guild's works
    "#..................#",
    "#........@.........#",
    "#..................#",
    "#..................#",
    "####+####W####+#####",
    "#......#...#.......#",
    "#......#...#.......#",
    "#......#bbb#.......#",
    "#......#####.......#",
    "####################",
]

rng = random.Random(SEED)
cell = lambda p: (int(p[0] / SX), int(p[1] / SY))
PLAZA = (*cell(PLAZA_PX[:2]), *cell(PLAZA_PX[2:]))
WELL = cell(WELL_PX)
SUBURB = (*cell(SUBURB_PX[:2]), *cell(SUBURB_PX[2:]))
GX = (PLAZA[0] + PLAZA[2]) // 2 - len(GUILD[0]) // 2   # the guild hall, south of the plaza
GY = PLAZA[3] + 3
AX = (PLAZA[0] + PLAZA[2]) // 2 - len(ACADEMY[0]) // 2  # the Academy, its front on the plaza's north edge
AY = PLAZA[1] - len(ACADEMY)
poly = [(x / SX, y / SY) for x, y in TOWERS]


def inside(x, y):
    n, c = len(poly), False
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def line4(a, b):
    """Cells from a to b with no diagonal steps."""
    (x0, y0), (x1, y1) = a, b
    out, x, y = [(x0, y0)], x0, y0
    while (x, y) != (x1, y1):
        opts = []
        if x != x1:
            opts.append((x + (1 if x1 > x else -1), y))
        if y != y1:
            opts.append((x, y + (1 if y1 > y else -1)))
        x, y = min(opts, key=lambda c: abs((x1 - x0) * (y0 - c[1]) - (x0 - c[0]) * (y1 - y0)))
        out.append((x, y))
    return out


ok = lambda x, y: 0 <= x < W and 0 <= y < H
g = [["T" if rng.random() < 0.04 else "," for _ in range(W)] for _ in range(H)]
IN = [[inside(x + .5, y + .5) for x in range(W)] for y in range(H)]

# ---- River --------------------------------------------------------------------
river = set()
pts = [cell(p) for p in RIVER_PATH]
for a, b in zip(pts, pts[1:]):
    for x, y in line4(a, b):
        for dx in (-1, 0, 1):
            for dy in (0, 1):
                if ok(x + dx, y + dy):
                    river.add((x + dx, y + dy))
for x, y in river:
    g[y][x] = "~"

# ---- Wall and towers -----------------------------------------------------------
towers = [cell(p) for p in TOWERS]
wall = []
for i in range(len(towers)):
    wall += line4(towers[i], towers[(i + 1) % len(towers)])
wall_cells = {c for c in wall if c not in river}
for tx, ty in towers:
    for dx in (-1, 0, 1):
        for dy in (0, 1):
            if (tx + dx, ty + dy) not in river:
                wall_cells.add((tx + dx, ty + dy))
for x, y in wall_cells:
    g[y][x] = "#"
for y in range(H):
    for x in range(W):
        if (x, y) in wall_cells:
            IN[y][x] = False

# ---- Streets (inside the walls), two cells wide ---------------------------------
street = set()          # cells that are street (or bridge, if over the river)
segments = []           # each painted stretch, so river crossings can become bridges


def paint(cells_):
    seg = []
    for x, y in cells_:
        if ok(x, y) and IN[y][x]:
            street.add((x, y))
            seg.append((x, y))
    segments.append(seg)


def thick(path):
    """Two cells wide: widen sideways for up-down stretches, downwards for across."""
    out = []
    for i, (x, y) in enumerate(path):
        nx, ny = path[min(i + 1, len(path) - 1)]
        px_, py_ = path[max(i - 1, 0)]
        vertical = nx == x and px_ == x
        out += [(x, y), (x + 1, y) if vertical else (x, y + 1)]
        if not vertical and (nx == x or px_ == x):   # corners: fill the elbow
            out += [(x + 1, y), (x + 1, y + 1)]
    return out


# Ring road just inside the wall.
ring = [(x, y) for y in range(H) for x in range(W) if IN[y][x] and
        any((x + dx, y + dy) in wall_cells for dx in (-2, -1, 0, 1, 2) for dy in (-1, 0, 1))]
paint(ring)

# Gates, roads out to the edge of the map, and main streets in to the plaza.
gate_lines, gate_cells = [], []
plaza_mid = ((PLAZA[0] + PLAZA[2]) // 2, (PLAZA[1] + PLAZA[3]) // 2)
for region, p, (ox, oy) in GATES:
    cx, cy = cell(p)
    gx, gy = min(wall_cells, key=lambda c: (c[0] - cx) ** 2 + ((c[1] - cy) * 2) ** 2)
    g[gy][gx] = "G"
    gate_lines.append(f";gate={gx},{gy} {region}")
    gate_cells.append((gx, gy))
    x, y = gx + ox, gy + oy
    while ok(x, y):                       # road out
        if g[y][x] != "~":
            g[y][x] = "-"
        x, y = x + ox, y + oy
    # cut straight in through the wall, so the gate opens onto the town without a diagonal step
    x, y = gx - ox, gy - oy
    while (x, y) in wall_cells:
        wall_cells.discard((x, y))
        IN[y][x] = True
        g[y][x] = ":"
        x, y = x - ox, y - oy
    start_in = (x, y)
    paint([(c, d) for c, d in line4((gx - ox, gy - oy), start_in)])
    # in towards the plaza, by way of a wobbly midpoint
    mid = ((start_in[0] + plaza_mid[0]) // 2 + rng.randint(-4, 4),
           (start_in[1] + plaza_mid[1]) // 2 + rng.randint(-2, 2))
    path = line4(start_in, mid)[:-1] + line4(mid, plaza_mid)
    paint(thick(path))

# Side streets: split the town into blocks, binary-space-partition style.
xs = [x for y in range(H) for x in range(W) if IN[y][x]]
ys = [y for y in range(H) for x in range(W) if IN[y][x]]


def split(x0, y0, x1, y1, depth=0):
    w, h = x1 - x0 + 1, y1 - y0 + 1
    if w <= BLOCK_W and h <= BLOCK_H:
        return
    if w > 2 * h:                         # cells are tall: compare like with like
        s = rng.randint(x0 + w * 35 // 100, x0 + w * 65 // 100)
        jog_at = rng.randint(y0 + h // 4, y1 - h // 4) if rng.random() < 0.6 else None
        d = rng.choice([-3, -2, 2, 3]) if jog_at else 0
        path = [(s, y) for y in range(y0, (jog_at or y1 + 1))]
        if jog_at:
            path += [(x, jog_at) for x in (range(s, s + d + 1) if d > 0 else range(s, s + d - 1, -1))]
            path += [(s + d, y) for y in range(jog_at, y1 + 1)]
        paint(thick(path))
        split(x0, y0, s - 1 + min(d, 0), y1, depth + 1)
        split(s + 2 + max(d, 0), y0, x1, y1, depth + 1)
    else:
        s = rng.randint(y0 + h * 35 // 100, y0 + h * 65 // 100)
        jog_at = rng.randint(x0 + w // 4, x1 - w // 4) if rng.random() < 0.6 else None
        d = rng.choice([-1, 1]) if jog_at else 0
        path = [(x, s) for x in range(x0, (jog_at or x1 + 1))]
        if jog_at:
            path += [(jog_at, s + d)]
            path += [(x, s + d) for x in range(jog_at, x1 + 1)]
        paint(thick(path))
        split(x0, y0, x1, s - 1 + min(d, 0), depth + 1)
        split(x0, s + 2 + max(d, 0), x1, y1, depth + 1)


split(min(xs), min(ys), max(xs), max(ys))

# The plaza.
plaza = {(x, y) for x in range(PLAZA[0], PLAZA[2] + 1) for y in range(PLAZA[1], PLAZA[3] + 1) if IN[y][x]}
street |= plaza

# The guild hall, with a street all round it.
hall = set()
for y in range(GY - 2, GY + len(GUILD) + 2):
    for x in range(GX - 2, GX + len(GUILD[0]) + 2):
        inner = GX <= x < GX + len(GUILD[0]) and GY <= y < GY + len(GUILD)
        if inner:
            hall.add((x, y))
        elif IN[y][x] and (x, y) not in river:
            street.add((x, y))
street -= hall

# ---- Bridges: two-wide, where streets cross the river ---------------------------
crossings = []
for seg in segments:
    wet = [c for c in seg if c in river]
    if wet:
        # one stretch of river per crossing
        groups, cur = [], []
        for c in seg:
            if c in river:
                cur.append(c)
            elif cur:
                groups.append(cur); cur = []
        if cur:
            groups.append(cur)
        crossings += [grp for grp in groups if len(grp) <= 10]
for x, y in street:
    g[y][x] = ":"
for x, y in river:
    g[y][x] = "~"          # river wins until we choose the bridges


def components():
    walk = set(",:-.w+=IG@m")
    seen, comps = {}, []
    for y in range(H):
        for x in range(W):
            if g[y][x] in walk and (x, y) not in seen:
                comp, q = [], deque([(x, y)])
                seen[(x, y)] = len(comps)
                while q:
                    c = q.popleft()
                    comp.append(c)
                    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):   # no diagonal steps
                        n = (c[0] + dx, c[1] + dy)
                        if ok(*n) and g[n[1]][n[0]] in walk and n not in seen:
                            seen[n] = len(comps)
                            q.append(n)
                comps.append(comp)
    return seen, comps


bridged = set()
def bridge_plan(grp):
    """A straight bridge, two cells wide, across the river where this street meets it:
    the deck runs straight from bank to bank, and if a bank isn't already street, a
    short straight approach road (also two wide) runs on until it meets one. Tries
    up-down and across, and both ways of pairing the lanes; the shortest wins.
    Returns (deck, approach, runs_up_down), or None if there's no good bridge here."""
    cx, cy = grp[len(grp) // 2]
    best = None
    for vertical in (True, False):
        sx, sy = (0, 1) if vertical else (1, 0)
        for off in (0, -1):
            lanes = [(cx + off, cy), (cx + off + 1, cy)] if vertical else [(cx, cy + off), (cx, cy + off + 1)]
            if not all(c in river for c in lanes):
                continue
            lo = hi = 0
            for lx, ly in lanes:                       # how far the water runs each way along each lane
                a = 0
                while (lx - sx * (a + 1), ly - sy * (a + 1)) in river:
                    a += 1
                b_ = 0
                while (lx + sx * (b_ + 1), ly + sy * (b_ + 1)) in river:
                    b_ += 1
                lo, hi = min(lo, -a), max(hi, b_)
            if hi - lo + 1 > 12:
                continue
            deck = [(lx + sx * t, ly + sy * t) for lx, ly in lanes for t in range(lo, hi + 1)]
            if any(not ok(*c) or not IN[c[1]][c[0]] or c in wall_cells or c in hall for c in deck):
                continue
            road, good = [], True
            for t, step in ((lo - 1, -1), (hi + 1, 1)):
                for _ in range(8):
                    row = [(lx + sx * t, ly + sy * t) for lx, ly in lanes]
                    if any(not ok(*c) or not IN[c[1]][c[0]] or c in river or c in wall_cells or c in hall
                           for c in row):
                        good = False
                        break
                    if any(c in street for c in row):  # met a street: pave the mouth two wide and stop
                        road += [c for c in row if c not in street]
                        break
                    road += row
                    t += step
                else:
                    good = False
                if not good:
                    break
            if not good:
                continue
            cost = len(deck) + 2 * len(road)
            if best is None or cost < best[0]:
                best = (cost, deck, road, vertical)
    return best and best[1:]


bridges = []
seen, _ = components()
crossings.sort(key=len)
for grp in crossings:
    plan = bridge_plan(grp)
    if not plan:
        continue
    deck, road, vertical = plan
    if any(c in bridged for c in deck):
        continue
    ends = set()
    for x, y in deck + road:
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            if (x + dx, y + dy) in seen:
                ends.add(seen[(x + dx, y + dy)])
    joins = len(ends) > 1
    spaced = all(abs(deck[0][0] - bx) + 2 * abs(deck[0][1] - by) > 24 for bx, by in bridges)
    if joins or (spaced and len(bridges) < 6):
        for x, y in road:
            g[y][x] = ":"
            street.add((x, y))
        for x, y in deck:
            g[y][x] = "I" if vertical else "="
        bridged.update(deck)
        bridges.append(deck[0])
        seen, _ = components()

# ---- Guild hall ------------------------------------------------------------------
for dy, row in enumerate(GUILD):
    for dx, ch in enumerate(row):
        g[GY + dy][GX + dx] = ch
start = (GX + GUILD[2].index("@"), GY + 2)
STASH = (GX + 18, GY + 9)  # the guild stash: a chest in the back corner of the stash room
CLERK_WINDOW = (GX + GUILD[5].index("W"), GY + 5)
CLERK = (CLERK_WINDOW[0], CLERK_WINDOW[1] + 1)   # just behind the window
g[STASH[1]][STASH[0]] = "C"

# ---- Houses: rectangles and L-shapes, a door on a street, never touching ----------
free = lambda x, y: ok(x, y) and g[y][x] in ",T"
taken = set()  # house cells plus the gap ring around them
built = []     # (cells, interior, door) for every house


def try_house(cells_, door_side_cells):
    cells_ = set(cells_)
    if not all(free(x, y) and (x, y) not in taken and (IN[y][x] or outside_ok(x, y)) for x, y in cells_):
        return False
    edge = {(x, y) for x, y in cells_
            if any((x + dx, y + dy) not in cells_ for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
    interior = cells_ - edge
    if not interior:
        return False
    # a door: an edge cell, not a corner, with street outside and floor inside
    doors = []
    for x, y in edge:
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            out, inn = (x + dx, y + dy), (x - dx, y - dy)
            along = [(x + dy, y + dx), (x - dy, y - dx)]
            if (ok(*out) and g[out[1]][out[0]] in ":-" and inn in interior
                    and all(a in edge for a in along)):
                doors.append((x, y))
    if not doors:
        return False
    for x, y in edge:
        g[y][x] = "h"
    for x, y in interior:
        g[y][x] = "w"
    dx_, dy_ = rng.choice(doors)
    g[dy_][dx_] = "+"
    built.append((cells_, interior, (dx_, dy_)))
    for x, y in cells_:
        for ddx in (-1, 0, 1):
            for ddy in (-1, 0, 1):
                taken.add((x + ddx, y + ddy))
    return True


def outside_ok(x, y):
    sx0, sy0, sx1, sy1 = SUBURB
    return sx0 <= x <= sx1 and sy0 <= y <= sy1


def house_shape(ax, ay, facing, w, h, wing):
    """A footprint w x h with one side along the street next to (ax, ay),
    extending away from it; wing adds an L-shaped extension at the back."""
    fx, fy = facing                          # direction from the house to the street
    if fy:                                   # street above or below
        x0 = ax - rng.randint(0, max(0, w - 3))
        y0 = ay if fy < 0 else ay - h + 1
    else:                                    # street to the left or right
        y0 = ay - rng.randint(0, max(0, h - 2))
        x0 = ax if fx < 0 else ax - w + 1
    rect = {(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h)}
    if wing:
        ww, wh = wing
        if fy:
            wx = x0 if rng.random() < 0.5 else x0 + w - ww
            wy = y0 + h if fy < 0 else y0 - wh
        else:
            wy = y0 if rng.random() < 0.5 else y0 + h - wh
            wx = x0 + w if fx < 0 else x0 - ww
        rect |= {(x, y) for x in range(wx, wx + ww) for y in range(wy, wy + wh)}
    return rect


def sizes(facing):
    """Sizes to try at a spot, biggest first, with a little shuffling."""
    if facing[1]:   # along a street running across: wider than deep
        opts = [(w, h) for w in range(10, 4, -1) for h in (5, 4, 3)]
    else:           # along a street running up and down: narrower, deeper
        opts = [(w, h) for w in (7, 6, 5, 4) for h in (6, 5, 4, 3)]
    opts.sort(key=lambda wh: -(wh[0] * wh[1]) + rng.uniform(-6, 6))
    return opts


# Spots right next to a street, worked through in order along the streets.
spots = [(x, y, (dx, dy)) for y in range(H) for x in range(W) if free(x, y) and (IN[y][x] or outside_ok(x, y))
         for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
         if ok(x + dx, y + dy) and g[y + dy][x + dx] in ":-"]
houses = 0
for x, y, facing in spots:
    if (x, y) in taken or not free(x, y):
        continue
    for w, h in sizes(facing):
        wing = None
        if rng.random() < 0.3:   # sometimes an L
            wing = (rng.randint(3, max(3, w // 2)), rng.randint(2, 3)) if facing[1] else \
                   (rng.randint(2, 3), rng.randint(3, max(3, h // 2 + 1)))
        if try_house(house_shape(x, y, facing, w, h, wing), None) or \
           (wing and try_house(house_shape(x, y, facing, w, h, None), None)):
            houses += 1
            break

# Leftover ground inside the walls: yards, with the odd tree.
for y in range(H):
    for x in range(W):
        if IN[y][x] and g[y][x] == "T":
            g[y][x] = ","
        if IN[y][x] and g[y][x] == "," and rng.random() < 0.03:
            g[y][x] = "T"

# ---- The supplier's shop: the house whose door is nearest the plaza ----
def plaza_dist(house):
    (dx_, dy_) = house[2]
    px = min(max(dx_, PLAZA[0]), PLAZA[2])
    py = min(max(dy_, PLAZA[1]), PLAZA[3])
    return abs(dx_ - px) + 2 * abs(dy_ - py)


shop = min((h for h in built if len(h[1]) >= 6 and IN[h[2][1]][h[2][0]]), key=plaza_dist)
for x, y in shop[1]:
    g[y][x] = "m"
door = shop[2]
keeper = max(shop[1], key=lambda c: abs(c[0] - door[0]) + 2 * abs(c[1] - door[1]))
npc_lines = [f";npc={keeper[0]},{keeper[1]} supplier"]

# ---- The artificer's workshop: the next-nearest roomy house to the plaza ----
workshop = min((h for h in built if h is not shop and len(h[1]) >= 8 and IN[h[2][1]][h[2][0]]), key=plaza_dist)
for x, y in workshop[1]:
    g[y][x] = "k"
door = workshop[2]
artificer = max(workshop[1], key=lambda c: abs(c[0] - door[0]) + 2 * abs(c[1] - door[1]))
npc_lines.append(f";npc={artificer[0]},{artificer[1]} artificer")

g[WELL[1]][WELL[0]] = "O"
g[start[1]][start[0]] = "@"

# ---- Checks -------------------------------------------------------------------------
# ---- The Academy, added last so the rest of the town stays as it was ----------------
# The wall bulges north round it (towers at the corners), with a two-wide street inside.
bx0, bx1, by0 = AX - 4, AX + len(ACADEMY[0]) + 3, AY - 3
old_wall = {(x, y) for x, y in wall_cells if bx0 < x < bx1 and y <= PLAZA[1]}
for x, y in old_wall:                         # the stretch of wall the Academy replaces
    g[y][x] = ","
bottom = {x: max(y for xx, y in wall_cells if xx == x and y <= PLAZA[1]) for x in (bx0, bx1)}
bulge_wall = ([(bx0, y) for y in range(by0, bottom[bx0] + 1)] + [(bx1, y) for y in range(by0, bottom[bx1] + 1)]
              + [(x, by0) for x in range(bx0, bx1 + 1)])
for x, y in bulge_wall:
    g[y][x] = "#"
for x in range(bx0 + 1, bx1):                 # the street inside: along the top, then down both sides
    for y in range(by0 + 1, AY + len(ACADEMY) + 1):
        if g[y][x] in ",T" or (x, y) in old_wall:
            near_wall = y <= by0 + 2 or x <= bx0 + 2 or x >= bx1 - 2
            g[y][x] = ":" if near_wall or y >= AY + len(ACADEMY) - 1 else ","
for dy, row in enumerate(ACADEMY):
    for dx, ch in enumerate(row):
        g[AY + dy][AX + dx] = "." if ch == "@" else ch
LIBRARIAN = (AX + ACADEMY[2].index("@"), AY + 2)

seen, comps = components()
home = seen[start]
for gx, gy in gate_cells:
    assert seen[(gx, gy)] == home, f"gate at {gx},{gy} can't be reached"
doors = [(x, y) for y in range(H) for x in range(W) if g[y][x] == "+"]
cut_off = [d for d in doors if seen.get(d) != home]
assert not cut_off, f"doors that can't be reached: {cut_off[:5]}"

# ---- The smithy: the next roomy house to the plaza after the workshop ----
smithy = min((h for h in built if h is not shop and h is not workshop and len(h[1]) >= 8 and IN[h[2][1]][h[2][0]]),
             key=plaza_dist)
for x, y in smithy[1]:
    g[y][x] = "k"
door = smithy[2]
smith = max(smithy[1], key=lambda c: abs(c[0] - door[0]) + 2 * abs(c[1] - door[1]))
npc_lines.append(f";npc={smith[0]},{smith[1]} smith")

# ---- The healer: the next roomy house to the plaza after the smithy (its floor stays as it is) ----
healing = min((h for h in built if h is not shop and h is not workshop and h is not smithy and len(h[1]) >= 8
               and IN[h[2][1]][h[2][0]]), key=plaza_dist)
door = healing[2]
healer = max(healing[1], key=lambda c: abs(c[0] - door[0]) + 2 * abs(c[1] - door[1]))
npc_lines.append(f";npc={healer[0]},{healer[1]} healer")
npc_lines.append(f";npc={LIBRARIAN[0]},{LIBRARIAN[1]} librarian")

# ---- The butcher and the trophymaster (v0.61.0): the next two roomy houses to the plaza ----
# The butcher's floor stays as it is. The trophymaster's house gets a wooden floor and, on the
# wall farthest from its door, the trophy wall (D): the records, mounted.
used = [shop, workshop, smithy, healing]
butchery = min((h for h in built if all(h is not u for u in used) and len(h[1]) >= 8
                and IN[h[2][1]][h[2][0]]), key=plaza_dist)
used.append(butchery)
door = butchery[2]
butcher = max(butchery[1], key=lambda c: abs(c[0] - door[0]) + 2 * abs(c[1] - door[1]))
npc_lines.append(f";npc={butcher[0]},{butcher[1]} butcher")
lodge = min((h for h in built if all(h is not u for u in used) and len(h[1]) >= 12
             and IN[h[2][1]][h[2][0]]), key=plaza_dist)
for x, y in lodge[1]:
    g[y][x] = "w"
door = lodge[2]
dist = lambda c: abs(c[0] - door[0]) + 2 * abs(c[1] - door[1])
far = max(lodge[1], key=dist)
# the trophy wall: the far cell and the cells beside it along the same wall
along = [(far[0] + dx, far[1] + dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
wall_side = [c for c in along if c in lodge[1] and dist(c) == dist(far) - (1 if c[1] == far[1] else 2)
             and any((c[0] + ex, c[1] + ey) not in lodge[1] for ex, ey in ((-1, 0), (1, 0), (0, -1), (0, 1)))]
TROPHY_WALL = [far] + wall_side[:2]
for x, y in TROPHY_WALL:
    g[y][x] = "D"
TROPHYMASTER = min((c for c in lodge[1] if c not in TROPHY_WALL),
                   key=lambda c: (abs(c[0] - far[0]) + abs(c[1] - far[1]), c))
npc_lines.append(f";npc={TROPHYMASTER[0]},{TROPHYMASTER[1]} trophymaster")
seen, _ = components()
assert all(seen.get(c) == seen[start] for c in lodge[1] if c not in TROPHY_WALL), "the trophy wall cuts the lodge off"

# ---- The notice board (requests from the city): an open plaza cell near the well ----
BOARD = min((c for c in plaza if g[c[1]][c[0]] == ":" and c != WELL and abs(c[0] - WELL[0]) + abs(c[1] - WELL[1]) >= 3
             and all(g[c[1] + dy][c[0] + dx] == ":" for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0))),
            key=lambda c: abs(c[0] - (WELL[0] - 3)) + abs(c[1] - (WELL[1] - 2)))
g[BOARD[1]][BOARD[0]] = "N"

# ---- The Wayfinder (v0.44.0): big enough to walk into; hunts leave from it ----
# A 5 x 3 block on open plaza cells with open ground all round, as near the middle of the
# plaza as fits (placeholder shape). Walking into it opens the keyword window.
ART_W, ART_H = 5, 3
plaza_mid = ((PLAZA[0] + PLAZA[2]) // 2, (PLAZA[1] + PLAZA[3]) // 2)
def art_fits(x0, y0):
    return all(g[y][x] == ":" and (x, y) != BOARD and (x, y) != WELL
               for x in range(x0 - 1, x0 + ART_W + 1) for y in range(y0 - 1, y0 + ART_H + 1))
ART = min(((x, y) for x, y in plaza if art_fits(x, y)),
          key=lambda c: abs(c[0] + ART_W // 2 - (plaza_mid[0] + 8)) + 2 * abs(c[1] + 1 - plaza_mid[1]))
for x in range(ART[0], ART[0] + ART_W):
    for y in range(ART[1], ART[1] + ART_H):
        g[y][x] = "Y"

# ---- The Guild's two boards (v0.44.0), in the guild hall's front corners ----
g[GY + 1][GX + 1] = "P"                     # contracts
g[GY + 1][GX + len(GUILD[0]) - 2] = "J"      # bounties and scouting (odd jobs, for now)

# ---- Townsfolk (data/townsfolk.json): the guild clerk, and a few people about the plaza ----
npc_lines.append(f";npc={CLERK[0]},{CLERK[1]} clerk")
window_lines = [f";window={CLERK_WINDOW[0]},{CLERK_WINDOW[1]} clerk"]
TRAINER, MENTOR = (GX + 3, GY + 7), (GX + 14, GY + 7)
npc_lines.append(f";npc={TRAINER[0]},{TRAINER[1]} trainer")
npc_lines.append(f";npc={MENTOR[0]},{MENTOR[1]} mentor")   # the latest retired Hunter, if any (game/aging.py)
# Spare corners for people still to come: (GX+5, GY+9) in the training corner, (GX+16, GY+7) in the stash room.
RIVALS = [(GX + 3, GY + 1), (GX + 6, GY + 3), (GX + 14, GY + 1), (GX + 16, GY + 3), (GX + 2, GY + 4), (GX + 17, GY + 4)]
for rx, ry in RIVALS:                                   # other Hunters, when they're home (game/rivals.py)
    npc_lines.append(f";npc={rx},{ry} rival")
taken = {start, CLERK, TRAINER, MENTOR, BOARD, *RIVALS}
for who, (ox, oy) in (("porter", (-6, -3)), ("washer", (2, 1)), ("carter", (7, 4))):
    # the nearest open plaza cell to the well plus this offset
    want = (WELL[0] + ox, WELL[1] + oy)
    spot = min((c for c in plaza if g[c[1]][c[0]] == ":" and c not in taken),
               key=lambda c: abs(c[0] - want[0]) + abs(c[1] - want[1]))
    taken.add(spot)
    npc_lines.append(f";npc={spot[0]},{spot[1]} {who}")

# ---- Whisper Poet's statue (v0.68.0, user's lore): in the plaza, near the Wayfinder ----
# Placed after everything else, on an open plaza cell with open ground all round that no one
# stands on, as near the Wayfinder's west end as fits, so nothing else in the city moves.
art_cells = {(x, y) for x in range(ART[0], ART[0] + ART_W) for y in range(ART[1], ART[1] + ART_H)}
near_art = {(x + dx, y + dy) for x, y in art_cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
STATUE = min((c for c in plaza if c not in taken and c not in near_art and c != WELL and c != BOARD
              and all(g[c[1] + dy][c[0] + dx] == ":" and (c[0] + dx, c[1] + dy) not in taken
                      for dx in (-1, 0, 1) for dy in (-1, 0, 1))),
             key=lambda c: abs(c[0] - (ART[0] - 4)) + 2 * abs(c[1] - (ART[1] + 1)))
g[STATUE[1]][STATUE[0]] = "S"
monument_lines = [f";monument={STATUE[0]},{STATUE[1]} whisper_poet"]

# ---- A Hunter's home (v0.74.0, data/homes.json): the property dealer, and the house for sale ----
# Added last, so nothing else moves. The dealer: the next roomy house to the plaza after the trophy
# lodge. The house: the nearest roomy house to the guild hall's front (3 x 3 inside at least), free.
used += [lodge]
dealing = min((h for h in built if all(h is not u for u in used) and len(h[1]) >= 8
               and IN[h[2][1]][h[2][0]]), key=plaza_dist)
used.append(dealing)
door = dealing[2]
DEALER = max(dealing[1], key=lambda c: abs(c[0] - door[0]) + 2 * abs(c[1] - door[1]))
npc_lines.append(f";npc={DEALER[0]},{DEALER[1]} dealer")
hall_front = (GX + len(GUILD[0]) // 2, GY - 1)
def wide(h):
    xs, ys = {x for x, _ in h[1]}, {y for _, y in h[1]}
    return len(h[1]) >= 9 and max(xs) - min(xs) >= 2 and max(ys) - min(ys) >= 2
HOME = min((h for h in built if all(h is not u for u in used) and wide(h) and IN[h[2][1]][h[2][0]]),
           key=lambda h: abs(h[2][0] - hall_front[0]) + 2 * abs(h[2][1] - hall_front[1]))
home_lines = [f";home={HOME[2][0]},{HOME[2][1]} bytorsskug"]

# ---- The Watermen and Anglers' Guild's tackleman (v0.94.0, user): in the free house nearest the river ----
# Added last, so nothing else moves: the roomy house whose door is closest to the water.
used.append(HOME)
river = [(x, y) for y in range(H) for x in range(W) if g[y][x] == "~"]
def to_river(h):
    dx, dy = h[2]
    return min(abs(dx - x) + 2 * abs(dy - y) for x, y in river)
tackle_shop = min((h for h in built if all(h is not u for u in used) and len(h[1]) >= 8 and IN[h[2][1]][h[2][0]]),
                  key=lambda h: (to_river(h), h[2]))
door = tackle_shop[2]
TACKLEMAN = max(tackle_shop[1], key=lambda c: abs(c[0] - door[0]) + 2 * abs(c[1] - door[1]))
npc_lines.append(f";npc={TACKLEMAN[0]},{TACKLEMAN[1]} tackleman")

items = []   # (v0.54.0, user: the example items that littered the guild hall are gone)
header = [
    "; Bytorsskug. Laid out after the city plan (tools/city_plan/), then free to edit by hand.",
    ";title=Bytorsskug",
    ";light=lit",
    ";safe=yes",
    "; The four city gates (data/gates.json). They lead out into the Brisering (not built yet).",
    *gate_lines,
    "; Townsfolk (data/townsfolk.json): the supplier, the artificer, the smith, the healer, the librarian (in the Academy), the guild clerk and trainer, a retired Hunter (if there is one), people in the plaza.",
    *npc_lines,
    f";hall={GX},{GY}",   # the guild hall's corner: the Guild's works build relative to it (v0.60.0)
    "; Service windows: walking into one talks to the person behind it.",
    *window_lines,
    "; Monuments (data/monuments.json): walking into one reads it.",
    *monument_lines,
    "; The house that can be a Hunter's home (data/homes.json).",
    *home_lines,
    *[f";item={x},{y} {item} {n}" for (x, y), item, n in items],
]
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(header) + "\n" + "\n".join("".join(r) for r in g) + "\n")
print(f"{W}x{H}: {houses} houses, {len(bridges)} bridges, {len(doors)} doors (all reachable), gates {gate_lines}")
