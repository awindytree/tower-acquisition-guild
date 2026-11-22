"""Build the small walkable places entered from the Brisering (v0.74.0): a piece of Ingenfjel,
and the Towerway stead. Run from the project root: python tools/sites/build_sites.py

Each is a fog-free, safe, day-lit map. A gate (G, ";gate=x,y out") leads back out to the
Brisering. ";home=x,y ID" marks the door of a house that can be a Hunter's home (data/homes.json);
its furniture appears as it's bought. ";landmark=x,y Name" names things you can't go into.
Layouts are the assistant's (placeholders); the places are the user's.
"""
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "maps"


def blank(w, h, ch=","):
    return [[ch] * w for _ in range(h)]


def house(g, x0, y0, w, h, door):
    """A house: walls h, floor w, a door + on the given side ('n','s','e','w'). Returns the door."""
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            edge = x in (x0, x0 + w - 1) or y in (y0, y0 + h - 1)
            g[y][x] = "h" if edge else "w"
    dx = {"n": (x0 + w // 2, y0), "s": (x0 + w // 2, y0 + h - 1),
          "w": (x0, y0 + h // 2), "e": (x0 + w - 1, y0 + h // 2)}[door]
    g[dx[1]][dx[0]] = "+"
    return dx


def path(g, a, b, ch="-"):
    """An L-shaped dirt path from a to b (four-way)."""
    (x0, y0), (x1, y1) = a, b
    for x in range(min(x0, x1), max(x0, x1) + 1):
        if g[y0][x] in ",T":
            g[y0][x] = ch
    for y in range(min(y0, y1), max(y0, y1) + 1):
        if g[y][x1] in ",T":
            g[y][x1] = ch


def trees(g, rng, share, keep):
    h, w = len(g), len(g[0])
    for y in range(h):
        for x in range(w):
            edge = x in (0, w - 1) or y in (0, h - 1)
            if g[y][x] == "," and (x, y) not in keep and (edge or rng.random() < share):
                g[y][x] = "T"


def write(name, title, g, lines):
    h, w = len(g), len(g[0])
    for y in range(h):                 # a closed edge of trees all round (the gate is inside it)
        for x in range(w):
            if (x in (0, w - 1) or y in (0, h - 1)) and g[y][x] != "G":
                g[y][x] = "T"
    text = "\n".join([f"; {title} (tools/sites/build_sites.py).", f";title={title}", ";light=day", ";safe=yes",
                      *lines]) + "\n" + "\n".join("".join(r) for r in g) + "\n"
    (OUT / f"{name}.txt").write_text(text, encoding="utf-8")


def reachable(g, start):
    walk = set(",.-+wGQ:")
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if 0 <= n[1] < len(g) and 0 <= n[0] < len(g[0]) and n not in seen and g[n[1]][n[0]] in walk:
                seen.add(n)
                todo.append(n)
    return seen


# ---- Ingenfjel: a piece of the village, the stables and the circuit seen from outside ----------------
def ingenfjel():
    rng = random.Random(17)
    W, H = 76, 30
    g = blank(W, H)
    gate = (1, 14)
    road_y = 14
    for x in range(1, 40):
        g[road_y][x] = "-"
    g[gate[1]][gate[0]] = "G"
    doors = {}
    doors["v1"] = house(g, 8, 6, 7, 5, "s")
    doors["v2"] = house(g, 18, 5, 6, 6, "s")
    doors["home"] = house(g, 27, 6, 8, 6, "s")          # the house that can be yours
    doors["v3"] = house(g, 10, 17, 7, 5, "n")
    doors["v4"] = house(g, 21, 18, 6, 5, "n")
    for d in doors.values():
        path(g, d, (d[0], road_y))
    # the stables: a long building you can't go into yet (boga: 2.x)
    stables = [(x, y) for y in range(17, 23) for x in range(31, 47)]
    for x, y in stables:              # walls round a floor of stalls (no door: not yet)
        edge = x in (31, 46) or y in (17, 22)
        g[y][x] = "h" if edge or (x % 3 == 0 and y in (18, 21)) else "w"
    path(g, (39, road_y), (39, 16))
    # the circuit: an oval track east of the village, grass inside
    cx, cy, rx, ry = 61, 14, 12, 10
    track = []
    for y in range(H):
        for x in range(W):
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if 0.72 <= d <= 1.0:
                g[y][x] = "Q"
                track.append((x, y))
    path(g, (40, road_y), (cx - rx, road_y))
    keep = set(doors.values()) | {gate} | set(track) | set(stables)
    trees(g, rng, 0.04, keep | {(x, road_y) for x in range(W)})
    for (x, y) in list(track):        # keep the track whole
        g[y][x] = "Q"
    seen = reachable(g, (gate[0] + 1, gate[1]))
    assert all(d in seen for d in doors.values()), "a door can't be reached"
    lines = ["; The way back out to the Brisering.", f";gate={gate[0]},{gate[1]} out",
             "; A house that can be a Hunter's home (data/homes.json).", f";home={doors['home'][0]},{doors['home'][1]} ingenfjel",
             "; Named things you can't go into yet.",
             *[f";landmark={x},{y} the Ingenfjel stables" for x, y in stables if g[y][x] == "h"]]
    write("ingenfjel", "Ingenfjel", g, lines)
    return g


# ---- The Towerway stead: a one-room stead by the road ------------------------------------------------
def stead():
    rng = random.Random(23)
    W, H = 46, 18
    g = blank(W, H)
    road_y = 4
    for x in range(1, W - 1):
        g[road_y][x] = "-"
    gate = (W - 2, road_y)            # (east, back toward the city)
    g[gate[1]][gate[0]] = "G"
    door = house(g, 18, 8, 6, 5, "n")   # 4 x 3 inside
    path(g, door, (door[0], road_y))
    keep = {door, gate} | {(x, road_y) for x in range(W)} | {(door[0], y) for y in range(road_y, door[1])}
    trees(g, rng, 0.07, keep)
    seen = reachable(g, (gate[0] - 1, gate[1]))
    assert door in seen
    lines = ["; The way back out to the Brisering (the Towerway).", f";gate={gate[0]},{gate[1]} out",
             "; The stead: a Hunter's home if bought (data/homes.json).", f";home={door[0]},{door[1]} stead"]
    write("stead", "The Towerway stead", g, lines)
    return g


if __name__ == "__main__":
    a, b = ingenfjel(), stead()
    print("ingenfjel", len(a[0]), "x", len(a), "| stead", len(b[0]), "x", len(b))
