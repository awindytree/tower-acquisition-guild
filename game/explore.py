"""Auto-explore: walk towards the nearest unexplored ground, one step a turn,
until something needs the Hunter's attention.

Each step is a real turn (creatures act, torches burn, Jodebris drains, and a
new Pulse only comes with an area change, which auto-explore never makes: it
keeps off passages, the trail home and gates). It stops when:
  - a creature comes into view (and won't start with one in view),
  - a passage comes into view for the first time (the way deeper, usually),
  - the Hunter is hurt,
  - it reaches something lying on the ground (shards it collects without stopping),
  - anything else is said in the log (a torch going out, a fading windcatcher...),
  - there's nothing left it can reach.
Only areas with fog of war can be explored (hunts); the city is known ground.
"""
from __future__ import annotations

from collections import deque

NO_ENTRY = "H<>G"   # passages, the trail home and gates: never stepped on by auto-explore
MAX_STEPS = 1000
STEPS = [(0, -1), (-1, 0), (1, 0), (0, 1)]   # four-way movement (v0.41.0)


def creatures_in_view(engine) -> list:
    return [m for m in engine.game_map.monsters if engine.visible is not None and engine.visible[m.x, m.y]]


def next_step(engine) -> tuple[tuple[int, int] | None, str]:
    """The first step towards the nearest place worth going: ground next to the
    unexplored, or something lying there (not already passed over). Returns
    (step, why) where why is "explore" or "item", or (None, "") when done."""
    gm, p = engine.game_map, engine.player
    w, h = gm.width, gm.height
    ignored = engine.explore_seen_items
    items = {(f.x, f.y) for f in gm.items if gm.explored[f.x, f.y] and (f.x, f.y) not in ignored}
    start = (p.x, p.y)
    prev = {start: None}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        x, y = cell
        if cell != start:
            why = ""
            if cell in items:
                why = "item"
            elif any(0 <= x + dx < w and 0 <= y + dy < h and not gm.explored[x + dx, y + dy] for dx, dy in STEPS):
                why = "explore"
            if why:
                while prev[cell] != start:
                    cell = prev[cell]
                return (cell[0] - start[0], cell[1] - start[1]), why
        for dx, dy in STEPS:
            n = (x + dx, y + dy)
            if (n in prev or not (0 <= n[0] < w and 0 <= n[1] < h) or not gm.explored[n]
                    or not gm.is_walkable(*n) or gm.tile_at(*n).symbol in NO_ENTRY or n in gm.gates
                    or gm.npc_at(*n) or _seen_creature(engine, n)):
                continue
            prev[n] = cell
            queue.append(n)
    return None, ""


def explore(engine) -> None:
    """Auto-explore until something comes up. Turns are taken here, step by step."""
    from game.actions import MoveAction, PickUpAction
    gm, p = engine.game_map, engine.player
    if not gm.fog:
        engine.log("There's nothing to explore here.")
        return
    seen = creatures_in_view(engine)
    if seen:
        engine.log(f"Not with {_a(seen[0].name)} in view.")
        return
    known_ways = _way_spots(engine)  # passages already found before this run
    for steps in range(MAX_STEPS):
        step, why = next_step(engine)
        if step is None:
            ways = _known_ways(engine)
            engine.log("Nothing left to explore here." + (f" Known ways on: {', '.join(ways)}." if ways else "")
                       if steps == 0 else "Explored as far as you can go.")
            return
        if gm.monster_at(p.x + step[0], p.y + step[1]):
            engine.log(f"Something is in your way: {gm.monster_at(p.x + step[0], p.y + step[1]).name}.")
            return  # never walk into a fight
        hp = p.stats.hp
        if not MoveAction(*step).perform(engine):
            return
        if any(f.item.type.id == "shard" for f in gm.items_at(p.x, p.y)):
            PickUpAction().perform(engine)  # shards go straight in the purse
        count_after_step = engine.logged
        engine.turn += 1
        engine.end_turn()
        if engine.game_map is not gm or engine.screen is not None or p.stats.is_dead:
            return
        if (p.x, p.y) in {(f.x, f.y) for f in gm.items}:  # (shards were picked up above)
            engine.explore_seen_items.add((p.x, p.y))
            if why == "item":
                return
        found = _way_spots(engine) - known_ways
        if found:
            x, y = sorted(found)[0]
            engine.log(f"You've found the {gm.tile_at(x, y).name}.")
            return
        new = creatures_in_view(engine)
        if new:
            engine.log(f"You see {_a(new[0].name)}.")
            return
        if p.stats.hp < hp:
            return
        if engine.logged > count_after_step:  # something happened that's worth a look
            return


def _way_spots(engine) -> set[tuple[int, int]]:
    """Explored passages (way deeper, way back, trail home)."""
    import numpy as np
    from game.tiles import SYMBOL_TO_INDEX
    gm = engine.game_map
    spots = set()
    for symbol in "H<>":
        xs, ys = np.nonzero((gm.kinds == SYMBOL_TO_INDEX[symbol]) & gm.explored)
        spots |= set(zip(xs.tolist(), ys.tolist()))
    return spots


def _known_ways(engine) -> list[str]:
    names = []
    for x, y in sorted(_way_spots(engine)):
        name = engine.game_map.tile_at(x, y).name
        if name not in names:
            names.append(name)
    return names


def _a(name: str) -> str:
    return ("an " if name[0].lower() in "aeiou" else "a ") + name


def _seen_creature(engine, cell) -> bool:
    m = engine.game_map.monster_at(*cell)
    return m is not None and (engine.visible is None or bool(engine.visible[cell]))
