"""The map: a grid of tile indices, loaded from a text file.

Hand-made text files suit the persistent places (the city, the overland).
Procedural dungeons will later fill the same kind of grid from code.

Map file format:
    ; lines starting with a semicolon are comments or settings
    ;light=lit          (or dark, the default; old maps may say day or torch)
    ;item=44,20 shard 12 (an item lying at x=44, y=20; the count is optional)
    ;gate=59,4 north     (a city gate at x=59, y=4, leading to the "north" region)
    ;title=The City      (name shown in the side panel)
    ;fog=on              (fog of war; off by default)
    ;safe=yes            (a safe zone: manual saving allowed)
    ;npc=101,30 supplier (a shopkeeper for the "supplier" shop in data/shops.json)
    ####
    #@.#
    ####
"""
from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np

from game.tiles import SYMBOL_TO_INDEX, TILE_TYPES, VOID, WALL_INDEX, TileType, graphic_dt

PLAYER_START = "@"

# (up, down, right, left) neighbours that are walls -> the line piece to draw.
JOINED_LINES = {
    (0, 0, 0, 0): "■",  # a lone pillar
    (1, 0, 0, 0): "║", (0, 1, 0, 0): "║", (1, 1, 0, 0): "║",
    (0, 0, 1, 0): "═", (0, 0, 0, 1): "═", (0, 0, 1, 1): "═",
    (0, 1, 1, 0): "╔", (0, 1, 0, 1): "╗", (1, 0, 1, 0): "╚", (1, 0, 0, 1): "╝",
    (1, 1, 1, 0): "╠", (1, 1, 0, 1): "╣", (0, 1, 1, 1): "╦", (1, 0, 1, 1): "╩",
    (1, 1, 1, 1): "╬",
}


class GameMap:
    def __init__(self, kinds: np.ndarray, name: str = "", light: str = "dark") -> None:
        # kinds[x, y] is an index into TILE_TYPES. Indexed [x, y] to match tcod.
        self.kinds = kinds
        self.name = name
        from game import sky
        self.light = sky.norm(light)  # "dark": dark beyond the player's light; "lit": all lit
        # Items to place when the map loads, from ";item=" lines: (x, y, item id, count).
        self.item_spawns: list[tuple[int, int, str, int]] = []
        self.items: list = []  # FloorItems lying on the map
        self.monsters: list = []  # creatures alive here
        self.npcs: list = []      # people: shopkeepers and the like
        self.npc_spawns: list[tuple[int, int, str]] = []  # from ";npc=" lines: (x, y, role)
        self.title = name.replace("_", " ").title()  # shown in the side panel
        self.gates: dict[tuple[int, int], str] = {}  # city gates: position -> region id
        self.arrivals: dict[str, tuple[int, int]] = {}  # gate id -> where you come out (the Brisering)
        self.trails: dict[tuple[int, int], int] = {}
        self.style = ""        # a hunt area's terrain (v0.70.0; "" elsewhere)
        self.home_doors: dict[tuple[int, int], str] = {}   # door -> home id (data/homes.json, v0.74.0)
        self.monuments: dict[tuple[int, int], str] = {}  # statues and the like: cell -> id (data/monuments.json)
        self.landmarks: dict[tuple[int, int], str] = {}  # named places (the Brisering): cell -> name
        self.windows: dict[tuple[int, int], str] = {}    # service windows: cell -> folk id behind it
        self.tracks: dict[tuple[int, int], int] = {}     # creature tracks: cell -> turn left (Tracking)
        self.smoke: dict[tuple[int, int], int] = {}      # a smoke jar's cloud: cell -> turns left (v0.82.0)
        self.lure = None                                 # a thrown lure: [x, y, turns left] (v0.82.0)
        self.hall: tuple[int, int] | None = None         # the guild hall's corner (the city)    # hot ash (an ashmantle's trail): cell -> turns left
        # Fog of war (hunt areas only): you see what's in your line of sight,
        # and remember what you've seen.
        self.fog = False
        self.safe = False  # can you make a manual save here?
        self.explored = np.zeros(kinds.shape, dtype=bool)
        self.transparent = np.array([t.transparent for t in TILE_TYPES])[kinds]
        self.walkable = np.array([t.walkable for t in TILE_TYPES])[kinds]
        # A fixed random number per cell, so a map always looks the same.
        rng = np.random.default_rng(zlib.crc32(name.encode()))
        self.variants = rng.integers(0, 1 << 30, size=kinds.shape, dtype=np.int64)
        self.graphics = np.zeros(kinds.shape, dtype=graphic_dt)
        self.build_graphics()

    @property
    def width(self) -> int:
        return self.kinds.shape[0]

    @property
    def height(self) -> int:
        return self.kinds.shape[1]

    # ---- Loading ----------------------------------------------------------
    @classmethod
    def from_text(cls, text: str, name: str = "") -> tuple["GameMap", tuple[int, int]]:
        """Build a map from rows of symbols. '@' marks where the player starts
        and is treated as floor. Returns (map, (start_x, start_y))."""
        settings: dict[str, str] = {}
        spawns: list[tuple[int, int, str, int]] = []
        gates: dict[tuple[int, int], str] = {}
        arrivals: dict[str, tuple[int, int]] = {}
        landmarks: dict[tuple[int, int], str] = {}
        windows: dict[tuple[int, int], str] = {}
        monuments: dict[tuple[int, int], str] = {}
        home_doors: dict[tuple[int, int], str] = {}
        hall = None
        npcs: list[tuple[int, int, str]] = []
        rows: list[str] = []
        for line in text.splitlines():
            if line.startswith(";"):
                key, _, value = line[1:].partition("=")
                key, value = key.strip(), value.strip()
                if key == "item":  # ;item=x,y item_id [count]
                    pos, item_id, *count = value.split()
                    x, y = (int(n) for n in pos.split(","))
                    spawns.append((x, y, item_id, int(count[0]) if count else 1))
                elif key == "npc":  # ;npc=x,y role (a shop id, for now)
                    pos, role = value.split()
                    x, y = (int(n) for n in pos.split(","))
                    npcs.append((x, y, role))
                elif key == "gate":  # ;gate=x,y gate_id (data/gates.json)
                    pos, region = value.split()
                    gates[tuple(int(n) for n in pos.split(","))] = region
                elif key == "hall":      # ;hall=x,y: the guild hall's corner (v0.60.0)
                    hall = tuple(int(n) for n in value.split(","))
                elif key == "window":    # ;window=x,y folk_id: a service window (v0.54.0)
                    pos, folk = value.split()
                    windows[tuple(int(n) for n in pos.split(","))] = folk
                elif key == "home":      # ;home=x,y id: the door of a house that can be a Hunter's home (v0.74.0)
                    pos, hid = value.split()
                    home_doors[tuple(int(n) for n in pos.split(","))] = hid
                elif key == "monument":  # ;monument=x,y id: a statue and its story (data/monuments.json, v0.68.0)
                    pos, mid = value.split()
                    monuments[tuple(int(n) for n in pos.split(","))] = mid
                elif key == "landmark":  # ;landmark=x,y Name of the place
                    pos, _, lname = value.partition(" ")
                    landmarks[tuple(int(n) for n in pos.split(","))] = lname
                elif key == "arrive":  # ;arrive=x,y gate_id: where you come out of that gate (the Brisering)
                    pos, gid = value.split()
                    arrivals[gid] = tuple(int(n) for n in pos.split(","))
                elif value:
                    settings[key] = value
            elif line.strip():
                rows.append(line.rstrip())
        game_map, start = cls.from_rows(rows, name, settings.get("light", "dark"))
        game_map.item_spawns = spawns
        game_map.gates = gates
        game_map.arrivals = arrivals
        game_map.landmarks = landmarks
        game_map.windows = windows
        game_map.monuments = monuments
        game_map.home_doors = home_doors
        game_map.hall = hall
        game_map.npc_spawns = npcs
        if "title" in settings:
            game_map.title = settings["title"]
        game_map.fog = settings.get("fog", "off") == "on"
        game_map.safe = settings.get("safe", "no") == "yes"
        return game_map, start

    @classmethod
    def from_rows(cls, rows: list[str], name: str = "", light: str = "dark") -> tuple["GameMap", tuple[int, int]]:
        """Build a map from rows of map symbols (used for files and generated maps)."""
        width = max(len(r) for r in rows)
        kinds = np.full((width, len(rows)), WALL_INDEX, dtype=np.int8)
        start = (1, 1)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == PLAYER_START:
                    start = (x, y)
                    ch = "."
                if ch not in SYMBOL_TO_INDEX:
                    raise ValueError(f"Unknown map symbol {ch!r} at {x},{y} in {name or 'map'}")
                kinds[x, y] = SYMBOL_TO_INDEX[ch]
        from game import sky
        light = sky.norm(light)
        if light not in (sky.LIT, sky.DARK):
            raise ValueError(f"light must be 'lit' or 'dark', not {light!r}, in {name or 'map'}")
        return cls(kinds, name, light), start

    @classmethod
    def from_file(cls, path: str | Path) -> tuple["GameMap", tuple[int, int]]:
        path = Path(path)
        return cls.from_text(path.read_text(encoding="utf-8"), name=path.stem)

    # ---- Queries ----------------------------------------------------------
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_at(self, x: int, y: int) -> TileType:
        """Off-map cells count as wall, so nothing can walk off the edge."""
        if not self.in_bounds(x, y):
            return TILE_TYPES[WALL_INDEX]
        return TILE_TYPES[self.kinds[x, y]]

    def is_walkable(self, x: int, y: int) -> bool:
        return self.tile_at(x, y).walkable

    def monster_at(self, x: int, y: int):
        return next((m for m in self.monsters if m.x == x and m.y == y), None)

    def npc_at(self, x: int, y: int):
        return next((n for n in self.npcs if n.x == x and n.y == y), None)

    def items_at(self, x: int, y: int) -> list:
        return [f for f in self.items if f.x == x and f.y == y]

    def place_items(self, catalogue) -> None:
        """Turn the map file's ;item= lines into items lying on the floor."""
        from game.items import FloorItem, Item
        for x, y, item_id, count in self.item_spawns:
            if not self.is_walkable(x, y):
                raise ValueError(f"{self.name}: item {item_id!r} at {x},{y} is inside a wall")
            self.items.append(FloorItem(x, y, Item(catalogue[item_id], count)))
        self.item_spawns = []  # placed; don't place them twice

    # ---- Drawing ----------------------------------------------------------
    def set_tile(self, x: int, y: int, symbol: str) -> None:
        """Change one cell (the Guild's works, v0.60.0), keeping its looks and the caches right."""
        kind = SYMBOL_TO_INDEX[symbol]
        self.kinds[x, y] = kind
        tile = TILE_TYPES[kind]
        self.transparent[x, y] = tile.transparent
        self.walkable[x, y] = tile.walkable
        v = int(self.variants[x, y])
        glyph = tile.glyphs[v % len(tile.glyphs)]
        color = dict(tile.glyph_colors).get(glyph) or tile.colors[(v // 97) % len(tile.colors)]
        self.graphics[x, y] = (ord(glyph), color, tile.bg)

    def build_graphics(self) -> None:
        """Work out what every cell looks like. Runs once when the map loads
        (call it again if the terrain changes), not every frame."""
        # Which cells are next to open space (in any of the 8 directions)?
        open_ = np.array([[TILE_TYPES[k].transparent for k in col] for col in self.kinds])
        padded = np.pad(open_, 1)
        near_open = np.zeros_like(open_)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                near_open |= padded[1 + dx : 1 + dx + self.width, 1 + dy : 1 + dy + self.height]

        for x in range(self.width):
            for y in range(self.height):
                tile = TILE_TYPES[self.kinds[x, y]]
                v = int(self.variants[x, y])
                if tile.hide_when_buried and not near_open[x, y]:
                    self.graphics[x, y] = (ord(" "), VOID, VOID)
                    continue
                glyph = tile.glyphs[v % len(tile.glyphs)]
                color = dict(tile.glyph_colors).get(glyph) or tile.colors[(v // 97) % len(tile.colors)]
                self.graphics[x, y] = (ord(glyph), color, tile.bg)

        # Joined walls: pick the line piece that connects to each visible
        # neighbour of the same type above, below, right and left.
        kinds = self.kinds
        shown = self.graphics["ch"] != ord(" ")
        for x in range(self.width):
            for y in range(self.height):
                kind = kinds[x, y]
                if not (TILE_TYPES[kind].joined and shown[x, y]):
                    continue

                def joins(nx: int, ny: int) -> int:
                    return int(self.in_bounds(nx, ny) and kinds[nx, ny] == kind and shown[nx, ny])

                key = (joins(x, y - 1), joins(x, y + 1), joins(x + 1, y), joins(x - 1, y))
                self.graphics["ch"][x, y] = ord(JOINED_LINES[key])
