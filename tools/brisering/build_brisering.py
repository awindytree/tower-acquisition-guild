"""Build the Brisering travel map: data/maps/brisering.txt (stage 3 of the redesign;
design: claude/design-brisering-keywords.md).

    python tools/brisering/build_brisering.py [out_path]

Run from the project root. Re-running overwrites hand edits.

The Brisering (lore, user): the land within 99 km of Myligast, where the Chorus Winds
push the miasma back. Myligast is 9 km across, at the centre; Bytorsskug lies 9 km south
of Myligast's southernmost point. Each of the city's gates opens onto its own terrain
(user): north, the mountains (and Myligast); east, ruins; south, forests; west, forests
along the Towerway.

Scale (my call, placeholder): a cell is 0.5 km wide and 1 km tall (cells are twice as tall
as wide), so the 99 km radius is 198 cells across and 99 down: the map is 400 x 202.
Bytorsskug, a few kilometres across, is a small walled block with its four gates.

Symbols (game/tiles.py): X the miasma (the edge), M Myligast, B Bytorsskug, G a gate
(;gate= lines), , plains, f woods, ^ hills, A mountains, u ruins, R road, ~ water,
= / I bridges (road over water).
"""
from __future__ import annotations

import math
import random
import sys
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "maps" / "brisering.txt"
SEED = 211

KM_X, KM_Y = 2, 1                 # cells per km, across and down
RADIUS_KM = 99
W, H = 2 * RADIUS_KM * KM_X + 4, 2 * RADIUS_KM * KM_Y + 4      # 400 x 202
CX, CY = W // 2, H // 2           # Myligast's centre
MYL_R_KM = 4.5
CITY_KM = 4.5 + 9 + 1.5           # Myligast's radius + 9 km + half the city
CITY = (CX, CY + int(CITY_KM * KM_Y))       # the city's centre
CITY_HALF = (3, 1)                # the walled block: 7 x 3 cells

rng = random.Random(SEED)
np_rng = np.random.default_rng(SEED)


def km(x: float, y: float, ox: float = CX, oy: float = CY) -> float:
    return math.hypot((x - ox) / KM_X, (y - oy) / KM_Y)


def noise(scale: int, octaves: int = 3) -> np.ndarray:
    """Smooth value noise in [0, 1], shape (H, W)."""
    total = np.zeros((H, W))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        step = max(2, scale >> o)
        gh, gw = H // step + 2, W // step + 2
        grid = np_rng.random((gh, gw))
        ys, xs = np.mgrid[0:H, 0:W]
        fy, fx = ys / step, xs / step
        y0, x0 = fy.astype(int), fx.astype(int)
        ty, tx = fy - y0, fx - x0
        ty, tx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
        a, b = grid[y0, x0], grid[y0, x0 + 1]
        c, d = grid[y0 + 1, x0], grid[y0 + 1, x0 + 1]
        total += amp * ((a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty)
        norm += amp
        amp /= 2
    return total / norm


g = [["," for _ in range(W)] for _ in range(H)]
n1, n2, n3, n4 = noise(24), noise(10), noise(16), noise(8, 2)

# ---- Terrain by direction from Bytorsskug (user: each gate opens onto its own terrain) ----
for y in range(H):
    for x in range(W):
        dx, dy = (x - CITY[0]) / KM_X, (y - CITY[1]) / KM_Y
        ang = math.degrees(math.atan2(dx, -dy)) % 360       # 0 = north, 90 = east
        a, b, c = n1[y, x], n2[y, x], n3[y, x]
        # sectors blur into each other with the noise
        ang = (ang + (a - 0.5) * 50) % 360
        if ang >= 300 or ang < 60:          # north: the mountains
            if a > 0.62 and b > 0.45:
                g[y][x] = "A"
            elif a > 0.5:
                g[y][x] = "^"
            elif b > 0.7:
                g[y][x] = "f"
        elif ang < 140:                     # east: the ruins
            if c > 0.64:
                g[y][x] = "u"
            elif b > 0.68:
                g[y][x] = "f"
            elif a > 0.7:
                g[y][x] = "^"
        elif ang < 220:                     # south: the forests
            if a > 0.4 or b > 0.55:
                g[y][x] = "f"
        else:                               # west: forests along the Towerway
            if a > 0.5 and b > 0.35:
                g[y][x] = "f"
            elif c > 0.75:
                g[y][x] = "^"
        if n4[y, x] > 0.8:                  # a few lakes
            g[y][x] = "~"

# ---- The river: in from the west, past the city's south side, out to the south-east ----
river = []
x, y = 2, CITY[1] + 10
while x < W - 2 and y < H - 2:
    river.append((x, y))
    if x < CITY[0] - 10:
        if rng.random() < 0.3:          # meander, drifting towards the city's south side
            y += rng.choice([-1, 1, 1 if y < CITY[1] + 3 else -1])
        y = min(max(y, CITY[1] - 2), CITY[1] + 16)
        x += 1
    else:
        x += 1
        if rng.random() < 0.55:
            y += 1
for x, y in river:
    for dx in (0, 1):
        if 0 <= x + dx < W:
            g[y][x + dx] = "~"

# ---- Myligast, the miasma's edge ----
for y in range(H):
    for x in range(W):
        if km(x, y) > RADIUS_KM:
            g[y][x] = "X"
        elif km(x, y) <= MYL_R_KM:
            g[y][x] = "M"
        elif km(x, y) <= MYL_R_KM + 1.5 and g[y][x] in "A^":
            g[y][x] = ","                   # open ground at the tower's foot

# ---- Bytorsskug and its gates ----
cx, cy = CITY
hx, hy = CITY_HALF
for y in range(cy - hy - 2, cy + hy + 3):
    for x in range(cx - hx - 3, cx + hx + 4):
        g[y][x] = ","                       # cleared ground round the walls
for y in range(cy - hy, cy + hy + 1):
    for x in range(cx - hx, cx + hx + 1):
        g[y][x] = "B"
GATES = {"north": (cx + 2, cy - hy - 1), "south": (cx - 2, cy + hy + 1),
         "east": (cx + hx + 1, cy), "west": (cx - hx - 1, cy)}
OUTWARD = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
for gid, (x, y) in GATES.items():
    g[y][x] = "G"


# ---- Roads from the gates (they cross the river on bridges) ----
def lay(path):
    for x, y in path:
        if g[y][x] in "XMBGVQ":
            continue
        if g[y][x] == "~":
            g[y][x] = "I" if any(abs(px - x) == 0 for px, py in path if abs(py - y) == 1) else "="
        else:
            g[y][x] = "R"


def road(start, goal, wander=0.15):
    """A road that keeps to the four directions, drifting a little."""
    (x, y), path = start, []
    while (x, y) != goal:
        dx, dy = goal[0] - x, goal[1] - y
        if dx and (not dy or rng.random() < abs(dx) / (abs(dx) + 2 * abs(dy)) + rng.uniform(-wander, wander)):
            x += 1 if dx > 0 else -1
        elif dy:
            y += 1 if dy > 0 else -1
        path.append((x, y))
    return path


def edge_point(angle_deg, km_out):
    a = math.radians(angle_deg)
    return (int(CITY[0] + math.sin(a) * km_out * KM_X), int(CITY[1] - math.cos(a) * km_out * KM_Y))


ox, oy = OUTWARD["north"]
lay(road((GATES["north"][0], GATES["north"][1] - 1), (CX + 2, CY + int((MYL_R_KM + 1) * KM_Y))))   # to Myligast's foot
# ---- Villages (lore, user, 2026-11-19) ----
# Igerste: near the outer eastern edge of the Brisering. Ingenfjel: 15-20 km south-west of
# Bytorsskug, home to boga stables and the Overland's largest boga circuit.
LANDMARKS = {}
def village(name, cx_, cy_, w=3):
    for x in range(cx_ - w // 2 - 2, cx_ + w // 2 + 3):
        for y in range(cy_ - 2, cy_ + 3):
            if g[y][x] not in "XMBG":
                g[y][x] = ","
    for x in range(cx_ - w // 2, cx_ + w // 2 + 1):
        g[cy_][x] = "V"
        LANDMARKS[(x, cy_)] = name
IGERSTE = (CX + 90 * KM_X, CY + 6)
a = math.radians(225)
INGENFJEL = (int(CITY[0] + math.sin(a) * 17.5 * KM_X), int(CITY[1] - math.cos(a) * 17.5 * KM_Y))
# Ingenfjel: "no mountain" (user): no hills or mountains within 12 km of it
for y in range(INGENFJEL[1] - 12, INGENFJEL[1] + 13):
    for x in range(INGENFJEL[0] - 24, INGENFJEL[0] + 25):
        if ((x - INGENFJEL[0]) / 2) ** 2 + (y - INGENFJEL[1]) ** 2 <= 144 and g[y][x] in "^A":
            g[y][x] = "f"
village("Igerste", *IGERSTE)
village("Ingenfjel", *INGENFJEL)
# the boga circuit, just south-east of Ingenfjel (off the road): an oval track about 1.5 x 3 km
cx_, cy_ = INGENFJEL[0] + 3, INGENFJEL[1] + 4
for x in range(cx_ - 3, cx_ + 4):
    for y in range(cy_ - 2, cy_ + 3):
        if g[y][x] not in "XMBGV":
            g[y][x] = ","
for x, y in [(cx_ - 1, cy_ - 1), (cx_, cy_ - 1), (cx_ + 1, cy_ - 1), (cx_ - 1, cy_), (cx_ + 1, cy_), (cx_ - 1, cy_ + 1), (cx_, cy_ + 1), (cx_ + 1, cy_ + 1)]:
    g[y][x] = "Q"
    LANDMARKS[(x, y)] = "the Ingenfjel boga circuit"
g[cy_][cx_] = ","
lay(road((GATES["east"][0] + 1, GATES["east"][1]), (IGERSTE[0] - 2, IGERSTE[1])))   # the east road ends at Igerste
lay(road((GATES["west"][0] - 1, GATES["west"][1] + 1), (INGENFJEL[0], INGENFJEL[1] - 1), wander=0.1))  # out the Towerway, then south-west
lay(road((GATES["south"][0], GATES["south"][1] + 1), edge_point(185, 70)))
towerway = road((GATES["west"][0] - 1, GATES["west"][1]), (CX - (RADIUS_KM - 1) * KM_X, CITY[1] - 4), wander=0.05)
lay(towerway)   # the Towerway, west to the edge of the Brisering (its name: lore, user)
for x, y in [(GATES[k][0] + OUTWARD[k][0], GATES[k][1] + OUTWARD[k][1]) for k in GATES]:
    if g[y][x] not in "R=I":
        g[y][x] = "R"

# ---- Everything walkable must be reachable from the gates (four-way): fill the rest ----
WALK = set(",f^uRGI=Q")
seen = set()
q = deque(GATES.values())
seen |= set(GATES.values())
while q:
    x, y = q.popleft()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (x + dx, y + dy)
        if 0 <= n[0] < W and 0 <= n[1] < H and n not in seen and g[n[1]][n[0]] in WALK:
            seen.add(n)
            q.append(n)
for y in range(H):
    for x in range(W):
        if g[y][x] in WALK and (x, y) not in seen:
            g[y][x] = "A"          # a pocket no road or path reaches: high ground
lost = sum(1 for y in range(H) for x in range(W) if g[y][x] in WALK and (x, y) not in seen)
assert lost == 0

# The Towerway stead (v0.74.0): a Hunter's home for sale (data/homes.json), just off the Towerway
# about 3 km west of the west gate, on its north side. Added last, so nothing else moves.
STEAD = None
for x, y in towerway:
    if x <= GATES["west"][0] - 3 * KM_X and g[y - 1][x] in ",f^" and g[y - 2][x] in ",f^":
        STEAD = (x, y - 1)
        break
assert STEAD, "no room for the stead by the Towerway"
g[STEAD[1]][STEAD[0]] = "V"
LANDMARKS[STEAD] = "the Towerway stead"

# Arrive just outside each gate; the city-side "gate" in the city map leads here.
arrive = {gid: (x + OUTWARD[gid][0], y + OUTWARD[gid][1]) for gid, (x, y) in GATES.items()}
for gid, (x, y) in arrive.items():
    assert g[y][x] in WALK, (gid, g[y][x])

header = [
    "; The Brisering (tools/brisering/build_brisering.py). A cell is 0.5 km across and 1 km down.",
    ";title=The Brisering",
    ";light=day",
    ";safe=yes",
    ";fog=on",
    "; Bytorsskug's gates (data/gates.json). Walking onto one goes back into the city.",
    *[f";gate={x},{y} {gid}" for gid, (x, y) in GATES.items()],
    "; Named places (lore, user): villages and the boga circuit.",
    *[f";landmark={x},{y} {name}" for (x, y), name in sorted(LANDMARKS.items())],
    "; Where a Hunter arrives, coming out of each gate.",
    *[f";arrive={x},{y} {gid}" for gid, (x, y) in arrive.items()],
    "@ placeholder",
]
header.pop()   # (no player start on this map)
OUT.write_text("\n".join(header) + "\n" + "\n".join("".join(r) for r in g) + "\n", encoding="utf-8")
counts = {ch: sum(r.count(ch) for r in g) for ch in ",f^AuR~XMB"}
print(f"{W}x{H}: city at {CITY}, Myligast at {(CX, CY)}; gates {GATES}; cells {counts}")
