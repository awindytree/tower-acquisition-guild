"""A Hunter's home (user, 2026-11-21, v0.74.0). See data/homes.json.

Three places: a house in Bytorsskug, a house in Ingenfjel, the Towerway stead. Bought from the
property dealer, one at a time; bare when bought; improved with a bed, a chest and trophy shelves
(more later: a workbench, a small forge). World state, like the guild stash: the next Hunter moves in.

engine.home: None, or {"id", "paid", "built": {improvement: tier}, "chest": Inventory,
"shelves": Inventory}. Moving keeps the chest's and shelves' contents (boxed up until the new place
has room: the inventories may hold more than their capacity, and take nothing more until under it).

Furniture: each home's house is found by its door (";home=x,y id" in a map). Its spots (bed, chest,
shelves) are worked out from the house's floor, deepest first and against a wall, never cutting the
room in two; `furnish` puts tiles there for what's been built, on every map that has a home door.
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from game.items import Inventory, Item


class Shelf(Inventory):
    """Trophy shelves: room is counted in trophies, not pack slots (a big trophy is still one)."""

    @property
    def used(self) -> int:
        return len(self.items)

    def can_add(self, item) -> bool:
        return len(self.items) < self.capacity

    def add(self, item) -> bool:
        if not self.can_add(item):
            return False
        self.items.append(item)
        return True

DATA = Path(__file__).resolve().parent.parent / "data" / "homes.json"
FURNITURE = {"bed": "n", "chest": "q", "shelves": "j", "forge": "F", "workbench": "d"}
_data: dict | None = None


def data() -> dict:
    global _data
    if _data is None:
        _data = json.loads(DATA.read_text(encoding="utf-8"))
    return _data


def fresh() -> None:
    return None


def owned(engine) -> str | None:
    h = getattr(engine, "home", None)
    return h["id"] if h else None


def tier(engine, key: str) -> int:
    h = getattr(engine, "home", None)
    return h["built"].get(key, 0) if h else 0


def slots(key: str, t: int) -> int:
    return data()["improvements"][key]["tiers"][t - 1].get("slots", 0) if t else 0


def most(hid: str, key: str) -> int:
    return data()["homes"][hid]["most"].get(key, 0)


# ---- Where homes are ---------------------------------------------------------------------------------------
def home_map(engine, hid: str):
    where = data()["homes"][hid]["where"]
    if where == "city":
        return engine.city
    from game import sites
    return sites.get(engine, where)


def door_of(gm, hid: str):
    return next((d for d, h in gm.home_doors.items() if h == hid), None)


def rooms(gm, door) -> list[tuple[int, int]]:
    """The house's floor, reached from its door (walkable cells, not through another door)."""
    seen, q, out = {door}, deque([door]), []
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n in seen or not gm.in_bounds(*n):
                continue
            seen.add(n)
            if gm.tile_at(*n).symbol in "wnqjFd":         # (floor, or furniture on it)
                out.append(n)
                q.append(n)
    return out


def spots(gm, hid: str) -> dict:
    """{improvement: cell}, worked out once per map and home and kept."""
    cache = gm.__dict__.setdefault("home_spots", {})
    if hid in cache:
        return cache[hid]
    door = door_of(gm, hid)
    floor = rooms(gm, door)
    inside = next((c for c in floor if abs(c[0] - door[0]) + abs(c[1] - door[1]) == 1), None)
    dist = {c: abs(c[0] - door[0]) + abs(c[1] - door[1]) for c in floor}
    fl = set(floor)
    def against_wall(c):
        return any((c[0] + dx, c[1] + dy) not in fl and (c[0] + dx, c[1] + dy) != door
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    def connected(blocked):
        rest = [c for c in floor if c not in blocked]
        if inside is None or inside in blocked:
            return False
        seen, q = {inside}, deque([inside])
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if n in fl and n not in blocked and n not in seen:
                    seen.add(n)
                    q.append(n)
        return all(c in seen for c in rest)
    chosen, blocked = {}, set()
    for key in ("bed", "shelves", "chest", "forge", "workbench"):
        if not most(hid, key):
            continue                          # (forge and workbench: only where the home takes one)
        for c in sorted(floor, key=lambda c: (-dist[c], c[1], c[0])):
            if c in blocked or c == inside or not against_wall(c):
                continue
            if any(abs(c[0] - b[0]) + abs(c[1] - b[1]) == 1 for b in blocked) and len(floor) > 9:
                continue                      # (room permitting, furniture doesn't touch)
            if connected(blocked | {c}):
                chosen[key] = c
                blocked.add(c)
                break
    cache[hid] = chosen
    gm.__dict__.setdefault("home_spots_all", set()).update(chosen.values())
    return chosen


def furnish(engine, gm) -> None:
    """Put the owned home's furniture on this map (and clear it from homes that aren't yours)."""
    mine = owned(engine)
    for door, hid in getattr(gm, "home_doors", {}).items():
        for key, (x, y) in spots(gm, hid).items():
            want = FURNITURE[key] if hid == mine and tier(engine, key) else "w"
            if gm.tile_at(x, y).symbol != want:
                gm.set_tile(x, y, want)


def furnish_all(engine) -> None:
    furnish(engine, engine.city)
    for gm in getattr(engine, "sites", {}).values():
        furnish(engine, gm)


# ---- Buying and improving ------------------------------------------------------------------------------------
def can_buy(engine, hid: str) -> str | None:
    h = data()["homes"][hid]
    if owned(engine) == hid:
        return "It's already yours."
    back = refund(engine)
    if engine.player.shards + back < h["price"]:
        return f"It costs {h['price']} shards" + (f" ({back} back for your old place)" if back else "") + "."
    return None


def refund(engine) -> int:
    hm = getattr(engine, "home", None)
    return int(hm["paid"] * data()["sell_back"]) if hm else 0


def buy(engine, hid: str) -> tuple[bool, str]:
    why = can_buy(engine, hid)
    if why:
        return False, why
    h = data()["homes"][hid]
    p = engine.player
    old = getattr(engine, "home", None)
    back = refund(engine)
    p.shards += back - h["price"]
    chest, shelves = (old["chest"].items, old["shelves"].items) if old else ([], [])
    engine.home = {"id": hid, "paid": h["price"], "built": {},
                   "chest": Inventory(0), "shelves": Shelf(0)}
    engine.home["chest"].items = list(chest)          # (boxed up until there's a chest with room)
    engine.home["shelves"].items = list(shelves)
    furnish_all(engine)
    from game import sound
    sound.play("pay")
    moved = (f" You sell {data()['homes'][old['id']]['name']} back for {back} shards"
             + (", and your things come with you" if chest or shelves else "") + ".") if old else ""
    return True, f"{h['name'][0].upper() + h['name'][1:]} is yours.{moved}"


def improve(engine, key: str) -> tuple[bool, str]:
    hid = owned(engine)
    if hid is None:
        return False, "You have no home to improve."
    imp = data()["improvements"][key]
    t = tier(engine, key)
    if t >= most(hid, key):
        return False, f"There's no room for more of that at {data()['homes'][hid]['short']}."
    cost = imp["tiers"][t]["cost"]
    p = engine.player
    if p.shards < cost:
        return False, f"That costs {cost} shards."
    p.shards -= cost
    engine.home["built"][key] = t + 1
    if key in ("chest", "shelves"):
        engine.home[key].capacity = slots(key, t + 1)
    furnish_all(engine)
    from game import sound
    sound.play("pay")
    word = imp["name"].lower()
    return True, (f"Your {word} is ready." if t == 0 else f"Your {word} is bigger now.")


# ---- Using it --------------------------------------------------------------------------------------------------
def rest_rate(engine) -> float:
    """How fast your own bed pays off the rest you owe (user, v0.88.0: the stead, then Ingenfjel, then
    Bytorsskug, all faster than the Guild's bunks)."""
    mine = owned(engine)
    return float(data()["homes"][mine].get("rest_rate", 1.5)) if mine else 1.0


def rest(engine) -> None:
    """The bed: sleep off everything owed (at least a Pulse). Full HP, and every minor injury mended."""
    from game import injuries, rest as _rest
    p = engine.player
    before = len(p.injuries)
    p.injuries = [i for i in p.injuries if injuries.table()[i.id].mends is None]
    mended = before - len(p.injuries)
    injuries.apply_to_stats(p)
    _rest.sleep(engine, rest_rate(engine), "in your own bed")
    if mended:
        engine.log(f"{mended} minor injur{'y has' if mended == 1 else 'ies have'} mended.")
    if p.injuries:
        engine.log("What's left needs the healer.")


def open_chest(engine) -> None:
    from game.screens import StashScreen
    engine.screen = StashScreen(store=lambda e: e.home["chest"], title="Your chest", name="Chest")


def open_shelves(engine) -> None:
    from game.screens import StashScreen
    engine.screen = StashScreen(store=lambda e: e.home["shelves"], title="Your trophy shelves", name="Shelves",
                                only=lambda it: it.trophy is not None, only_why="Only trophies go on the shelves.")


def use(engine, x: int, y: int) -> bool:
    """Walking into a piece of your furniture. True if it was one."""
    sym = engine.game_map.tile_at(x, y).symbol
    if sym not in FURNITURE.values() or owned(engine) is None:
        return False
    {"n": rest, "q": open_chest, "j": open_shelves, "F": smithing, "d": workbench}[sym](engine)
    return True


def smithing_key(engine) -> str | None:
    """The improvement that raises gear at the owned home, if it's built (v0.76.0)."""
    hid = owned(engine)
    key = data()["homes"][hid].get("smithing") if hid else None
    return key if key and tier(engine, key) else None


def smithing(engine) -> None:
    """The forge or workbench: raise gear to +3 with materials only (user, v0.76.0)."""
    from game.screens import UpgradeScreen
    key = smithing_key(engine)
    if key is None:
        return
    engine.screen = UpgradeScreen(at="home", title=f"Your {data()['improvements'][key]['name'].lower()}")


def artificy_key(engine) -> str | None:
    """The improvement that repairs Common artifacts at the owned home, if it's built (v0.79.0)."""
    hid = owned(engine)
    key = data()["homes"][hid].get("artificy") if hid else None
    return key if key and tier(engine, key) else None


def workbench(engine) -> None:
    """The workbench: artifacts, and (where there's no forge) gear too: then it asks which."""
    from game.screens import ArtificyScreen, ChoiceScreen
    art, smith = artificy_key(engine) == "workbench", smithing_key(engine) == "workbench"
    if art and smith:
        engine.screen = ChoiceScreen("Your workbench", [("Repair an artifact", lambda e: setattr(e, "screen", ArtificyScreen())),
                                                        ("Raise a weapon or armour piece", smithing)])
    elif art:
        engine.screen = ArtificyScreen()
    elif smith:
        smithing(engine)


COMMON = 1     # the rarity tier you can repair at home (user: Common artifacts)


def repairable(engine) -> list:
    """(store, item) for every broken artifact in the pack and the home chest."""
    out = [(engine.player.inventory, it) for it in engine.player.inventory.items if it.type.is_broken_artifact]
    if getattr(engine, "home", None):
        out += [(engine.home["chest"], it) for it in engine.home["chest"].items if it.type.is_broken_artifact]
    return out


def repair_blocked(item) -> str | None:
    from game import artifacts
    t = item.type
    if artifacts.locked(t):
        return "You can't make anything of this one."
    if t.rarity.tier > COMMON:
        return f"{t.rarity.name}: past Common, that's the Artificer's work."
    if not t.identified:
        return "You'd need to know what it is first: study it (u)."
    return None


def repair_at_home(engine, store, item) -> tuple[bool, str]:
    """Repair a Common artifact yourself on the workbench (user, v0.79.0): no fee, a Pulse's work."""
    why = repair_blocked(item)
    if why:
        return False, why
    from game import artifacts
    working = engine.catalogue[item.type.repairs_to]
    i = next(n for n, it in enumerate(store.items) if it is item)
    store.items[i] = Item(working)
    artifacts.learn(engine.player, item.type)
    engine.next_day()
    from game import sound
    sound.play("pay")
    return True, f"A Pulse at the bench, and the {item.type.name} works again: {artifacts._a(working.name)}."


# ---- Saving ----------------------------------------------------------------------------------------------------
def to_save(engine) -> dict | None:
    h = getattr(engine, "home", None)
    if not h:
        return None
    return {"id": h["id"], "paid": h["paid"], "built": dict(h["built"]),
            "chest": h["chest"].to_list(), "shelves": h["shelves"].to_list()}


def from_save(engine, d: dict | None) -> None:
    if not d:
        engine.home = None
        return
    chest, shelves = Inventory(slots("chest", d["built"].get("chest", 0))), Shelf(slots("shelves", d["built"].get("shelves", 0)))
    chest.items = Inventory.from_list(d.get("chest", []), engine.catalogue, 999).items
    shelves.items = Inventory.from_list(d.get("shelves", []), engine.catalogue, 999).items
    engine.home = {"id": d["id"], "paid": d["paid"], "built": dict(d.get("built", {})), "chest": chest, "shelves": shelves}
