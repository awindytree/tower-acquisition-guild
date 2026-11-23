"""Lost Grounds (roadmap step 5; user, 2026-11-22): TAG's own version of .hack's Lost Grounds.

Hand-built, fixed places out in the miasma, reached through the Wayfinder by particular words, there
for lore and story. This module is the plumbing; **the places themselves are the user's** to write.

**Data:** every `data/lost_grounds/*.json` (not `_*`, not `examples/`), one ground each:
    {"name": shown on arrival and in the log,
     "words": [danger, land, feature] (keyword ids from data/keywords.json; story words are fine),
     "map": a map file beside it (the usual map format; `;gate=x,y out` is the way back),
     "arrive": [lines for the card the first time anyone comes here] (optional),
     "again": [lines for later visits] (optional),
     "monuments": {id: {name, look, title, text}} (optional; placed with `;monument=x,y id`),
     "ambience": a key in data/sounds.json "ambience" (optional; else the land word's terrain)}
`data/lost_grounds/_README.md` is the writer's guide; `examples/` holds an example the tests load.

**How it behaves** (assistant's calls, for the user to change):
- Choosing a Lost Ground's words at the Wayfinder always takes you there: **a Lost Ground is never a
  hunt** (user, v0.87.1). Rank limits on danger words apply as usual.
- It's **persistent** (like Ingenfjel and the stead, game/sites.py): the same place every time, and
  what you take or leave stays taken or left, for every Hunter after you.
- It lies **in the miasma**: windcatchers drain, artifacts need one, torches burn. No creatures unless
  a later version adds them; no faints are needed.
- Going and coming out each take a Pulse. The way back (`;gate=x,y out`) brings you out at the edge of
  the Brisering, on the land word's side, to walk home (v0.89.0: the Wayfinder is one way).
- The Guild's boards never post work at a Lost Ground's words. Work a save already held there (from
  before the ground existed) is dropped on load (`clear_work`).
- **World state:** `engine.story["grounds"]` {id: first day anyone came}. Story: event `lost_ground`
  (ground=ID, first=True/False) on arrival; condition `visited:ID`.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "lost_grounds"
PREFIX = "lost:"          # their ids among engine.sites
_cache: dict | None = None
_root: Path = ROOT


def load(root: Path | str | None = None, keywords=None) -> dict:
    """Read every ground in `root` (default data/lost_grounds). Checked: words, map, the way back."""
    global _cache, _root
    _root = Path(root) if root else ROOT
    out = {}
    for f in sorted(_root.glob("*.json")) if _root.exists() else []:
        if f.name.startswith("_"):
            continue
        g = json.loads(f.read_text(encoding="utf-8"))
        gid = f.stem
        if len(g.get("words", [])) != 3:
            raise ValueError(f"Lost Ground {gid}: 'words' needs three keyword ids [danger, land, feature]")
        if keywords is not None:
            for slot, w in zip(("danger", "land", "feature"), g["words"]):
                if w not in keywords.words[slot]:
                    raise ValueError(f"Lost Ground {gid}: '{w}' isn't a {slot} word in data/keywords.json")
        mp = _root / g.get("map", f"{gid}.txt")
        if not mp.exists():
            raise ValueError(f"Lost Ground {gid}: no map file {mp.name}")
        if ";gate=" not in mp.read_text(encoding="utf-8"):
            raise ValueError(f"Lost Ground {gid}: its map needs a way back (;gate=x,y out)")
        g["id"], g["map_path"], g["place"] = gid, mp, "/".join(g["words"])
        out[gid] = g
        if g.get("monuments"):
            from game import monuments
            monuments.table().update(g["monuments"])
    _cache = out
    return out


def check_story(story_data) -> None:
    """A story key hunt can't send a Hunter to a Lost Ground's words: a Lost Ground is never a hunt."""
    places = {g["place"]: gid for gid, g in grounds().items()}
    for cid, c in getattr(story_data, "contracts", {}).items():
        words = "/".join(c.get("words", []))
        if words in places:
            raise ValueError(f"Story contract {cid}: its words are the Lost Ground {places[words]}'s. "
                             "A Lost Ground is never a hunt: pick other words.")


def grounds() -> dict:
    return _cache if _cache is not None else load()


def at_place(place_id: str) -> str | None:
    """The Lost Ground at these words, if there is one."""
    return next((gid for gid, g in grounds().items() if g["place"] == place_id), None)


def sid(gid: str) -> str:
    return PREFIX + gid


def here(engine) -> str | None:
    """The Lost Ground you're in, if any."""
    from game import sites
    s = sites.here(engine)
    return s[len(PREFIX):] if s and s.startswith(PREFIX) else None


def in_sentence(name: str) -> str:
    """'The Example Hollow' -> 'the Example Hollow' (inside a sentence)."""
    return "the " + name[4:] if name.startswith("The ") else name


def visited(engine, gid: str) -> bool:
    return gid in engine.story.get("grounds", {})


def enter(engine, gid: str) -> None:
    """Through the Wayfinder to a Lost Ground (from Engine.set_out)."""
    from game import sites, story
    from game.screens import TitleCardScreen, TEXT, DIM
    g = grounds()[gid]
    gm = sites.get(engine, sid(gid))
    first = not visited(engine, gid)
    engine.story.setdefault("grounds", {}).setdefault(gid, engine.day)
    engine.site = sid(gid)                      # (city_return: where you stood at the Wayfinder)
    engine.next_day()
    engine.change_map(gm, *sites.arrival(gm))
    engine.log(f"You step into the Wayfinder, and it carries you somewhere else entirely: {in_sentence(g['name'])}.")
    lines = g.get("arrive" if first else "again") or g.get("arrive") or []
    engine.screen = TitleCardScreen(g["name"], [(t, TEXT) for t in lines]
                                    + [("", TEXT), (f"{engine.date.short}", DIM)])
    story.fire(engine, "lost_ground", ground=gid, first=first)
    engine.autosave()


def clear_work(engine) -> list[str]:
    """Drop work at any Lost Ground's words (a save from before the ground was added): the Hunter's
    contract, their bounties, errands on the notice board. Returns what went, for the log."""
    places = {g["place"] for g in grounds().values()}
    gone = []
    p = engine.player
    if p.contract is not None and p.contract.region.id in places:
        gone.append(p.contract.title(engine.catalogue))
        p.contract = None
    for j in [j for j in p.jobs if j.region in places]:
        p.jobs.remove(j)
        gone.append(j.label(engine))
    engine.requests = [r for r in engine.requests if not (r.kind == "errand" and r.place in places)]
    engine.job_board = [j for j in engine.job_board if j.region not in places]
    for what in gone:
        engine.log(f"The Guild has withdrawn your work there: {what}. Those words lead somewhere else now.")
    return gone


def leave(engine) -> None:
    """The way back: out to the edge of the Brisering, and home on foot (user, v0.89.0: the Wayfinder
    is one way, Lost Grounds too)."""
    gid = here(engine)
    engine.site = None
    engine.next_day()
    g = grounds().get(gid)
    name = in_sentence(g["name"]) if g else "that place"
    from game import journey
    region = engine.regions[g["place"]] if g and g["place"] in engine.regions else None
    where = journey.come_out(engine, region, f"ground:{gid}")
    engine.log(f"You leave {name} behind, and come out at {where}.")
    engine.autosave()
