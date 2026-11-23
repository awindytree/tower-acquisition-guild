"""Travel-to: pick a known place and walk there, one turn a step, stopping like
auto-explore does when something needs the Hunter's attention.

In the city: the guild hall, the stash, the people who keep shops or teach,
and the gates (walking onto a gate opens its contract board). On a hunt: the
passages found so far in this area (walking onto one takes it), and the hunt's
artifact once it's been seen. It stops when a new creature comes into view,
when the Hunter is hurt, when anything is said in the log, or on arrival.
"""
from __future__ import annotations

from collections import deque

from game.explore import STEPS, creatures_in_view, worth_stopping_for

MAX_STEPS = 2000
PASSAGES = {">": "the way deeper", "<": "the way back", "H": "the trail home"}


def destinations(engine) -> list[tuple[str, tuple[int, int], bool]]:
    """(label, spot, beside) for every place one can travel to from here.
    beside: stop next to it (a person, the stash) rather than on it."""
    gm, p = engine.game_map, engine.player
    out = []
    from game import sites, homes
    mine = homes.owned(engine)
    home_door = homes.door_of(gm, mine) if mine else None
    if sites.here(engine):                                 # Ingenfjel or the stead (v0.74.0)
        if home_door:
            out.append(("your home", home_door, False))
        for (x, y) in gm.gates:
            from game import lost_grounds
            out.append(("the way back out of the miasma" if lost_grounds.here(engine) else "back out to the Brisering",
                        (x, y), False))
        return out
    if engine.hunt is None and gm is not engine.city:     # the Brisering: back to the gates
        for (x, y), gate_id in sorted(gm.gates.items(), key=lambda g: g[1]):
            out.append((f"Bytorsskug: the {engine.gate_info.get(gate_id, {}).get('name', gate_id)}", (x, y), False))
        named = {}
        for (x, y), name in sorted(gm.landmarks.items()):   # places you've seen (stop beside them)
            if gm.explored[x, y] and name not in named:
                named[name] = (x, y)
        out += [(name, spot, True) for name, spot in named.items()]
    elif engine.hunt is None:
        out.append(("the guild hall", engine.city_start, False))
        if home_door:
            out.append(("your home", home_door, False))
        for x in range(gm.width):
            for y in range(gm.height):
                if gm.tile_at(x, y).symbol == "C":
                    out.append(("the guild stash", (x, y), True))
        windows = {folk: cell for cell, folk in gm.windows.items()}
        for n in gm.npcs:
            if n.wander == 0:      # (someone behind a service window: go to the window)
                out.append((n.name, windows.get(n.folk_id, (n.x, n.y)), True))
        for x in range(gm.width):           # the Wayfinder and the Guild's boards (stop beside them)
            for y in range(gm.height):
                sym = gm.tile_at(x, y).symbol
                if sym in "PJ":
                    out.append(("the contracts board" if sym == "P" else "the bounty board", (x, y), True))
        art = [(x, y) for x in range(gm.width) for y in range(gm.height) if gm.tile_at(x, y).symbol == "Y"]
        if art:
            out.append(("the Wayfinder", max(art, key=lambda c: (c[1], -abs(c[0] - sum(a[0] for a in art) / len(art)))), True))
        from game import monuments
        for (x, y) in sorted(getattr(gm, "monuments", {})):           # statues (v0.68.0; stop beside them)
            m = monuments.at(gm, x, y)
            if m:
                out.append((m["name"], (x, y), True))
        for (x, y), gate_id in sorted(gm.gates.items(), key=lambda g: g[1]):
            out.append((f"the {engine.gate_info.get(gate_id, {}).get('name', gate_id)}", (x, y), False))
    else:
        seen = {}
        for x in range(gm.width):
            for y in range(gm.height):
                symbol = gm.tile_at(x, y).symbol
                if symbol in PASSAGES and gm.explored[x, y] and symbol not in seen:
                    seen[symbol] = (x, y)
        for symbol in (">", "<", "H"):
            if symbol in seen:
                out.append((PASSAGES[symbol], seen[symbol], False))
        target = engine.hunt.contract.artifact_id
        for f in gm.items:
            if target and f.item.type.id == target and gm.explored[f.x, f.y]:
                out.append((f"the {f.item.type.name}", (f.x, f.y), False))
    return [d for d in out if d[1] != (p.x, p.y)]


def next_step(engine, spot: tuple[int, int], beside: bool) -> tuple[int, int] | None:
    gm, p = engine.game_map, engine.player
    start = (p.x, p.y)
    goals = ({(spot[0] + dx, spot[1] + dy) for dx, dy in STEPS} if beside else {spot})
    if start in goals:
        return None
    prev = {start: None}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        if cell in goals:
            while prev[cell] != start:
                cell = prev[cell]
            return cell[0] - start[0], cell[1] - start[1]
        x, y = cell
        for dx, dy in STEPS:
            n = (x + dx, y + dy)
            if n in prev or not gm.in_bounds(*n) or not gm.is_walkable(*n):
                continue
            if gm.fog and not gm.explored[n] and not engine.in_brisering():
                continue          # (on the Brisering you know the way home, seen or not: v0.89.0)
            if n != spot and (gm.tile_at(*n).symbol in "H<>" or n in gm.gates):
                continue  # never through another passage or gate on the way
            if gm.npc_at(*n) or _seen_creature(engine, n):
                continue  # (creatures out of sight don't change the plan: that would give them away)
            prev[n] = cell
            queue.append(n)
    return None


def travel(engine, label: str, spot: tuple[int, int], beside: bool) -> None:
    """Walk there all at once (tests and tools)."""
    for _ in travel_steps(engine, label, spot, beside):
        pass


def travel_steps(engine, label: str, spot: tuple[int, int], beside: bool):
    """Travel as a generator: one step each time it's advanced (watched step by step, v0.65.0)."""
    from game.actions import MoveAction
    gm, p = engine.game_map, engine.player
    known = set(map(id, creatures_in_view(engine)))
    for steps in range(MAX_STEPS):
        step = next_step(engine, spot, beside)
        if step is None:
            arrived = (p.x, p.y) == spot or (beside and abs(p.x - spot[0]) + abs(p.y - spot[1]) == 1)
            if steps == 0:
                engine.log("You're already there." if arrived else f"You don't know a way to {label} from here.")
            elif not arrived:
                engine.log(f"The way to {label} is blocked.")
            return
        ahead = (p.x + step[0], p.y + step[1])
        if gm.monster_at(*ahead):
            engine.log(f"Something is in your way: {gm.monster_at(*ahead).name}.")
            return  # never walk into a fight
        hp = p.stats.hp
        if not MoveAction(*step).perform(engine):
            return
        after_step = engine.logged
        engine.turn += 1
        engine.end_turn()
        if engine.game_map is not gm or engine.screen is not None or p.stats.is_dead:
            return  # arrived through a passage or onto a gate, or something opened
        new = [m for m in worth_stopping_for(engine) if id(m) not in known]
        if new:
            engine.log(f"You see {'an' if new[0].name[0] in 'aeiou' else 'a'} {new[0].name}.")
            return
        if p.stats.hp < hp or engine.logged > after_step:
            return
        yield


def _seen_creature(engine, cell) -> bool:
    m = engine.game_map.monster_at(*cell)
    return m is not None and (engine.visible is None or bool(engine.visible[cell]))
