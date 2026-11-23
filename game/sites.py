"""Small places you walk into from the Brisering (v0.74.0): a piece of Ingenfjel and the Towerway
stead (tools/sites/build_sites.py). Persistent like the city: what you leave there stays.

Bump the place's landmark on the Brisering to go in; walk onto its gate (";gate=x,y out") to come
back out where you went in. `engine.sites` holds the loaded maps; `engine.site` is the one you're
in (None elsewhere); `engine.site_return` the Brisering cell you went in from.
"""
from __future__ import annotations

from pathlib import Path

from game.game_map import GameMap

DATA = Path(__file__).resolve().parent.parent / "data" / "maps"
SITES = {   # id: (map file, the Brisering landmark that leads in)
    "ingenfjel": ("ingenfjel.txt", "Ingenfjel"),
    "stead": ("stead.txt", "the Towerway stead"),
}


def for_landmark(name: str) -> str | None:
    return next((sid for sid, (_, mark) in SITES.items() if mark == name), None)


def get(engine, sid: str) -> GameMap:
    sites = engine.__dict__.setdefault("sites", {})
    if sid not in sites:
        from game import lost_grounds
        path = (lost_grounds.grounds()[sid[len(lost_grounds.PREFIX):]]["map_path"]
                if sid.startswith(lost_grounds.PREFIX) else DATA / SITES[sid][0])   # (a Lost Ground, v0.87.0)
        gm, _ = GameMap.from_file(path)
        gm.place_items(engine.catalogue)
        saved = engine.__dict__.get("site_items", {}).get(sid)
        if saved is not None:                 # (what was left there, from a save)
            from game import saves
            saves._set_items(gm, saved, engine.catalogue)
        sites[sid] = gm
        from game import homes
        homes.furnish(engine, gm)
    return sites[sid]


def here(engine) -> str | None:
    sid = engine.__dict__.get("site")
    if sid and engine.__dict__.get("sites", {}).get(sid) is engine.game_map:
        return sid
    return None


def arrival(gm: GameMap) -> tuple[int, int]:
    """The walkable cell just inside the way out."""
    gx, gy = next(iter(gm.gates))
    for dx, dy in ((-1, 0), (1, 0), (0, 1), (0, -1)):
        x, y = gx + dx, gy + dy
        if gm.in_bounds(x, y) and gm.is_walkable(x, y) and (x, y) not in gm.gates:
            return x, y
    return gx, gy


def enter(engine, sid: str, from_xy: tuple[int, int]) -> None:
    gm = get(engine, sid)
    engine.site, engine.site_return = sid, tuple(from_xy)
    engine.change_map(gm, *arrival(gm))
    from game import homes
    mine = homes.owned(engine)
    note = " Your home is here." if mine and homes.data()["homes"][mine]["where"] == sid else ""
    name = gm.title[0].lower() + gm.title[1:] if gm.title.startswith("The ") else gm.title
    engine.log(f"You come to {name}.{note}")
    engine.autosave()


def leave(engine) -> None:
    sid = here(engine)
    from game import lost_grounds
    if sid and sid.startswith(lost_grounds.PREFIX):     # a Lost Ground: home through the Wayfinder (v0.87.0)
        lost_grounds.leave(engine)
        return
    bris = engine.brisering
    x, y = engine.__dict__.get("site_return") or next(iter(bris.arrivals.values()))
    engine.site = None
    engine.change_map(bris, x, y)
    engine.log(f"You head back out onto the Brisering.")
    engine.autosave()


def to_save(engine) -> dict:
    from game import saves
    items = dict(engine.__dict__.get("site_items", {}))
    for sid, gm in engine.__dict__.get("sites", {}).items():
        items[sid] = saves._items(gm)
    ret = engine.__dict__.get("site_return")
    return {"here": here(engine), "return": list(ret) if ret else None, "items": items}


def known(sid: str | None) -> bool:
    """A site id this game can put you back in (a site, or a Lost Ground that still exists)."""
    if not sid:
        return False
    from game import lost_grounds
    if sid.startswith(lost_grounds.PREFIX):
        return sid[len(lost_grounds.PREFIX):] in lost_grounds.grounds()
    return sid in SITES


def from_save(engine, data: dict | None) -> None:
    data = data or {}
    engine.sites = {}
    engine.site_items = data.get("items", {})
    engine.site = None
    engine.site_return = tuple(data["return"]) if data.get("return") else None
    return data.get("here")
