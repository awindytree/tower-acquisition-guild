"""Saving and loading.

There's one autosave and three manual slots, each a JSON file in saves/.
The autosave is written automatically (quitting, setting out, changing area,
coming home). Manual saves can only be made in a safe zone (a map with
;safe=yes, like Bytorsskug).

Every Hunter has an id. When a Hunter dies, every save holding that Hunter is
deleted: permadeath can't be undone by loading.

Hunt areas aren't stored whole. Each is rebuilt from its seed when loading,
then the changes are put back: items, creatures and what you've explored.
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from game.hunt import Contract, Hunt
from game.items import FloorItem, Item, Inventory
from game.monsters import Monster
from game import crafting, work
from game.player import Player
from game.version import VERSION
from game import procgen

if TYPE_CHECKING:
    from game.engine import Engine

SAVE_VERSION = 1
AUTOSAVE = "autosave"
SLOTS = ("slot1", "slot2", "slot3")
SLOT_NAMES = {AUTOSAVE: "Autosave", "slot1": "Slot 1", "slot2": "Slot 2", "slot3": "Slot 3"}
KEEP_MESSAGES = 200


class SaveError(Exception):
    """A save file that's missing, damaged, or from an incompatible version."""


class SaveSystem:
    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def path(self, slot: str) -> Path:
        return self.folder / f"{slot}.json"

    def exists(self, slot: str) -> bool:
        return self.path(slot).exists()

    def summary(self, slot: str) -> dict | None:
        """What's in a slot, for menus. None if empty; {'damaged': True} if unreadable."""
        if not self.exists(slot):
            return None
        try:
            return self.read(slot)["summary"]
        except SaveError:
            return {"damaged": True}

    def write(self, slot: str, engine: "Engine") -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        data = capture(engine)
        # Write to a temporary file first, so a crash mid-write can't ruin the old save.
        tmp = self.path(slot).with_suffix(".tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, self.path(slot))

    def read(self, slot: str) -> dict:
        try:
            data = json.loads(self.path(slot).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SaveError(f"{SLOT_NAMES.get(slot, slot)} is empty.") from None
        except (OSError, ValueError):
            raise SaveError(f"{SLOT_NAMES.get(slot, slot)} is damaged and can't be read.") from None
        if not isinstance(data, dict) or "summary" not in data:
            raise SaveError(f"{SLOT_NAMES.get(slot, slot)} is damaged and can't be read.")
        if data.get("version") != SAVE_VERSION:
            raise SaveError(f"{SLOT_NAMES.get(slot, slot)} is from a different version of the game.")
        return data

    def load(self, slot: str, engine: "Engine") -> None:
        restore(engine, self.read(slot))

    def delete_hunter(self, hunter_id: str) -> list[str]:
        """Delete every save holding this Hunter. Returns the slots cleared."""
        cleared = []
        for slot in (AUTOSAVE, *SLOTS):
            info = self.summary(slot)
            if info and info.get("hunter_id") == hunter_id:
                self.path(slot).unlink(missing_ok=True)
                cleared.append(slot)
        return cleared


# ---- Turning the game into data and back --------------------------------------
def _pack(mask: np.ndarray) -> str:
    return base64.b64encode(np.packbits(mask.ravel()).tobytes()).decode("ascii")


def _unpack(text: str, shape: tuple[int, int]) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(base64.b64decode(text), dtype=np.uint8))
    return bits[: shape[0] * shape[1]].reshape(shape).astype(bool)


def _items(game_map) -> list:
    return [[f.x, f.y, *f.item.to_entry()] for f in game_map.items]


def _set_items(game_map, items: list, catalogue) -> None:
    game_map.item_spawns = []
    game_map.items = [FloorItem(e[0], e[1], Item.from_entry(e[2:], catalogue)) for e in items
                      if e[2] in catalogue.types]


def contract_to_dict(c) -> dict:
    return {"region": c.region.id, "artifact": c.artifact_id, "danger": c.danger, "job": c.job,
            "story": c.story, "story_title": c.story_title, "guardian": c.guardian, "min_rank": c.min_rank,
            "depth": c.depth, "seed": c.seed, "free": c.free, "prize_folk": c.prize_folk, "guardians": c.guardians,
            "recover": c.recover}


def contract_from_dict(engine, d: dict):
    """A saved contract, or None if its place no longer exists (an older version's region)."""
    if d is None or d.get("region") not in engine.regions:
        return None
    from game.hunt import Contract
    return Contract(engine.regions[d["region"]], d["artifact"], d["danger"], d["depth"], d["seed"],
                    d.get("job", ""), d.get("story", ""), d.get("story_title", ""), d.get("guardian", ""),
                    d.get("min_rank", 0), d.get("free", False), d.get("prize_folk", ""), d.get("guardians", 1),
                    d.get("recover"))


def capture(engine: "Engine") -> dict:
    p = engine.player
    hunt = engine.hunt
    where = hunt.contract.region.name if hunt else engine.game_map.title
    data = {
        "version": SAVE_VERSION,
        "game_version": VERSION,   # which version of the game wrote this save
        "summary": {
            "hunter_id": p.hunter_id,
            "name": p.full_name,
            "level": p.stats.level,
            "day": engine.day,
            "date": engine.date.short,
            "where": where,
            "on_hunt": hunt is not None,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "player": {**p.to_dict(), "x": p.x, "y": p.y, "regen_progress": p.regen_progress,
                   "contract": contract_to_dict(p.contract) if p.contract else None},
        "world": {
            "day": engine.day,
            "turn": engine.turn,
            "messages": engine.messages[-KEEP_MESSAGES:],
            "city_return": list(engine.city_return),
            "city_items": _items(engine.city),
            "home": __import__("game.homes", fromlist=["x"]).to_save(engine),      # (v0.74.0)
            "sites": __import__("game.sites", fromlist=["x"]).to_save(engine),
            "stash": engine.stash.to_list(),   # the guild stash outlives Hunters
            "stocks": {vid: st.to_list() for vid, st in engine.stocks.items()},
            "flags": sorted(engine.world_flags),
            "words": sorted(engine.words),
            "brisering": ({"explored": _pack(engine._brisering.explored), "steps": getattr(engine, "bris_steps", 0),
                           "here": engine.in_brisering()}
                          if getattr(engine, "_brisering", None) is not None else None),
            "orders": crafting.orders_to_list(engine.orders),
            "library": list(engine.library),
            "archive": engine.archive,
            "hall": engine.hall,
            "lost": getattr(engine, "lost", []),          # lost Hunters' packs (v0.85.0)
            "road": getattr(engine, "road", {}),          # people met on the road (v0.90.0)
            "wilds": getattr(engine, "wilds", {}),        # foraging and camps (v0.91.0)
            "works": getattr(engine, "works", None),
            "trophies": getattr(engine, "trophies", None),   # the trophy wall (v0.61.0)
            "story": engine.story,
            "rivals": {"cast": engine.rivals, "next_id": engine.next_rival_id, "taken": engine.rival_taken},
            "mentor": engine.mentor,
            "work": {"board": work.jobs_to_list(engine.job_board), "requests": work.requests_to_list(engine.requests),
                     "posted": [engine.jobs_posted, engine.requests_posted], "next_id": engine.next_work_id},
        },
        "hunt": None,
    }
    if hunt:
        c = hunt.contract
        data["hunt"] = {
            **contract_to_dict(c), "gen": procgen.GENERATION,
            "current": hunt.current, "faints_used": hunt.faints_used, "faints_earned": hunt.faints_earned,
            "carried_at_start": hunt.carried_at_start,
            "writings": hunt.writings,
            "story_items": hunt.story_items,
            "bounties": hunt.bounties,
            "race": hunt.race,
            "areas": {
                str(i): {
                    "items": _items(area),
                    "monsters": [[m.type.id, m.x, m.y, m.hp, m.awake, m.turns_unseen, m.bounty, m.burrowed]
                                 + ([m.named, m.affixes] if m.named else []) for m in area.monsters],
                    "explored": _pack(area.explored),
                }
                for i, area in enumerate(hunt.areas) if area is not None
            },
        }
    return data


def restore(engine: "Engine", data: dict) -> None:
    cat = engine.catalogue
    try:
        pd = data["player"]
        player = Player.from_dict(pd, cat, pd["x"], pd["y"])
        player.regen_progress = pd.get("regen_progress", 0)

        world = data["world"]
        _set_items(engine.city, world["city_items"], cat)

        hunt = None
        hd = data.get("hunt")
        from game import procgen
        if hd and hd.get("gen", 1) != procgen.GENERATION:
            # Made by an older version: its areas can't be rebuilt from the seed. The Hunter walks home.
            hd = None
            player.x, player.y = tuple(world["city_return"])
            stale_hunt = True
        else:
            stale_hunt = False
        if hd:
            contract = contract_from_dict(engine, hd)
            hunt = Hunt(contract, engine.monster_types)
            hunt.faints_used = hd["faints_used"]
            # (v0.82.0) older saves: as many earned as new areas reached, and at least those used
            hunt.faints_earned = hd.get("faints_earned", max(hd["faints_used"], len(hd.get("areas", {})) - 1))
            hunt.carried_at_start = hd["carried_at_start"]
            hunt.writings = [w if w in cat.types else None for w in hd.get("writings", [None] * contract.depth)]
            hunt.story_items = [s for s in hd.get("story_items", []) if s[0] in cat.types]
            hunt.race = hd.get("race")
            hunt.bounties = hd.get("bounties", [])
            if hunt.race and hunt.race.get("at"):
                hunt.race["at"] = tuple(hunt.race["at"])
            for key, ad in hd["areas"].items():
                area = hunt.area(int(key), cat)     # rebuilt from the seed...
                _set_items(area, ad["items"], cat)  # ...then put back as it was
                area.monsters = []
                for mid, x, y, hp, awake, unseen, *rest in ad["monsters"]:
                    m = Monster.spawn(engine.monster_types[mid], x, y)
                    m.hp, m.awake, m.turns_unseen = hp, awake, unseen
                    m.bounty = rest[0] if rest else 0
                    m.burrowed = bool(rest[1]) if len(rest) > 1 else False
                    if len(rest) > 3 and rest[2]:            # a named creature (v0.83.0)
                        from game import named
                        named.apply(m, rest[2], rest[3], fresh=False)
                    area.monsters.append(m)
                area.explored = _unpack(ad["explored"], area.kinds.shape)
            hunt.current = hd["current"]
    except (KeyError, TypeError, ValueError) as err:
        raise SaveError(f"This save is damaged and can't be loaded ({err}).") from None

    engine.player = player
    engine.day = world["day"]
    engine.turn = world["turn"]
    engine.messages = list(world["messages"])
    engine.city_return = tuple(world["city_return"])
    from game.engine import STASH_SLOTS
    from game import works as _works       # (the stash room's extra slots: room for all of it, v0.60.0)
    engine.stash = Inventory.from_list(world.get("stash", []), cat,
                                       STASH_SLOTS + _works.effect_of(world.get("works"), "stash_slots"))
    from game.stock import Stock
    engine.world_flags = set(world.get("flags", []))
    engine.words = set(world["words"]) if "words" in world else set(engine.regions.keywords.start)
    engine.words &= set(engine.regions.keywords.all_ids())
    player.contract = contract_from_dict(engine, data["player"].get("contract"))
    player.jobs = [j for j in player.jobs if j.region in engine.regions]   # (jobs in the old gate regions are gone)
    engine.orders = crafting.orders_from_list(world.get("orders", []))
    engine.library = [w for w in world.get("library", []) if w in cat.types]
    from game import archive
    engine.archive = world.get("archive") or archive.empty()
    engine.archive["regions"] = {r: n for r, n in engine.archive.get("regions", {}).items() if r in engine.regions}
    engine.hall = list(world.get("hall", []))
    engine.lost = [r for r in world.get("lost", []) if r.get("place") in engine.regions]
    engine.road = dict(world.get("road", {}))
    engine.wilds = dict(world.get("wilds", {}))
    from game import works
    engine.works = world.get("works") or works.fresh()
    from game import trophies
    engine.trophies = world.get("trophies") or trophies.fresh()
    from game import story
    engine.story = {**story.empty(), **world.get("story", {})}
    engine.scene_queue = []
    rv = world.get("rivals", {})
    engine.rivals = rv.get("cast", [])
    engine.next_rival_id = rv.get("next_id", len(engine.rivals))
    engine.rival_taken = rv.get("taken", {"day": 0, "taken": {}})
    engine.mentor = world.get("mentor")
    from game import homes, sites
    homes.from_save(engine, world.get("home"))             # (v0.74.0)
    site_here = sites.from_save(engine, world.get("sites"))
    homes.furnish_all(engine)
    engine.passing = False
    engine.update_mentor()
    from game import rivals
    rivals.place_in_hall(engine)
    works.apply(engine)                         # the hall as the Guild's works left it (v0.60.0)
    if "work" in world:
        w = world["work"]
        engine.job_board = [j for j in work.jobs_from_list(w["board"]) if j.region in engine.regions]
        engine.requests = work.requests_from_list(w["requests"])
        engine.jobs_posted, engine.requests_posted = w["posted"]
        engine.next_work_id = w["next_id"]
    engine.reset_stocks()  # (vendors this save doesn't know yet start full)
    fresh = engine.stocks
    engine.stocks = dict(fresh)
    for vid, data in world.get("stocks", {}).items():
        st = Stock.from_list(data)
        if vid in fresh:            # (v0.78.0) lines added to the data since this save start full
            have = {l.item_id for l in st.lines if l.max > 0}
            st.lines += [l for l in fresh[vid].lines if l.max > 0 and l.item_id not in have]
        engine.stocks[vid] = st
    engine.hunt = hunt
    engine.screen = None
    engine.started = True
    bd = world.get("brisering")
    if bd:                         # the Brisering: what's been seen of it, and whether you're out there
        bris = engine.brisering
        bris.explored = _unpack(bd["explored"], bris.kinds.shape)
        engine.reveal_landmarks()
        engine.bris_steps = bd.get("steps", 0)
    elif getattr(engine, "_brisering", None) is not None:
        engine._brisering.explored[:] = False
        engine.reveal_landmarks()
    where = engine.brisering if (bd and bd.get("here") and not hunt) else None
    engine.change_map(hunt.areas[hunt.current] if hunt else where or engine.city, player.x, player.y)
    if site_here and not hunt and sites.known(site_here):   # in Ingenfjel, the stead or a Lost Ground (v0.74.0, v0.87.0)
        engine.site = site_here
        engine.change_map(sites.get(engine, site_here), player.x, player.y)
    if stale_hunt:
        engine.log("That hunt was saved by an older version of the game, and its areas can't be rebuilt. "
                   "You've made your way back to Bytorsskug; the contract is lost.")
    from game import lost_grounds
    lost_grounds.clear_work(engine)  # no work at a Lost Ground's words (v0.87.1)
    story.fire(engine, "load")     # the story catches up with a save from before it (v0.67.0)
