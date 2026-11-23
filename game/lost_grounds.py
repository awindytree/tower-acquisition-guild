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
- Choosing a Lost Ground's words at the Wayfinder takes you there instead of a hunt (a contract or
  bounty you hold for that exact place still wins). Rank limits on danger words apply as usual.
- It's **persistent** (like Ingenfjel and the stead, game/sites.py): the same place every time, and
  what you take or leave stays taken or left, for every Hunter after you.
- It lies **in the miasma**: windcatchers drain, artifacts need one, torches burn. No creatures unless
  a later version adds them; no faints are needed.
- Going and coming back each take a Pulse. The way back (`;gate=x,y out`) returns you to the Wayfinder.
- The Guild's boards never post work at a Lost Ground's words.
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


def leave(engine) -> None:
    """The way back: home through the Wayfinder."""
    gid = here(engine)
    engine.site = None
    engine.next_day()
    engine.change_map(engine.city, *engine.city_return)
    name = in_sentence(grounds()[gid]["name"]) if gid in grounds() else "that place"
    engine.log(f"You leave {name} behind, and the Wayfinder sets you down in the plaza.")
    engine.autosave()
