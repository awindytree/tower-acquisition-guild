"""Moving traits (v0.86.0): the last traits from the equipment design (`claude/design-equipment.md`).

- **Mud and reeds** now drag at you: a step onto either takes another turn (on hunts). **Mud-boots**
  (legs, `mud_boots`) cancel that.
- **Wading** (legs, `wading`): on a hunt, step into shallow water, water with walkable ground beside it
  (the edge of a pond or a marsh channel), at a normal step's cost. Creatures can't follow you in.
- **Runner's** (legs, `runner`): a creature you step away from (beside you before the step, not after)
  can't strike you that turn (`Engine.disengaged`; a quick creature otherwise catches up and strikes).
- **Pole-vault** (staff, `vault`): once an area, `j` then a direction leaps two cells: over a creature,
  water, a gap; not over a wall, a tree or anything else that blocks sight. A turn.
- **Pathfinder's** (legs, `pathfinder`) lives in game/explore.py.
"""
from __future__ import annotations

MUD = "er"            # mud, reeds
WATER = "~"
NO_LANDING = "<>HG"   # passages and gates: walk onto those


def _trait(engine, key: str) -> int:
    from game import talents
    return talents.total(engine.player, key)


def shallow(gm, x: int, y: int) -> bool:
    """Water with walkable ground beside it (four ways)."""
    if not gm.in_bounds(x, y) or gm.tile_at(x, y).symbol != WATER:
        return False
    return any(gm.in_bounds(x + dx, y + dy) and gm.is_walkable(x + dx, y + dy)
               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def can_wade(engine, x: int, y: int) -> bool:
    return engine.hunt is not None and bool(_trait(engine, "wading")) and shallow(engine.game_map, x, y)


def beside(engine) -> list:
    p = engine.player
    return [m for m in engine.game_map.monsters if abs(m.x - p.x) + abs(m.y - p.y) == 1]


def after_step(engine, tile, before: list, wade: bool) -> None:
    """After the Hunter's step onto `tile`: mud, Runner's, the first wade."""
    p = engine.player
    if engine.hunt is None:
        return
    if tile.symbol in MUD and not _trait(engine, "mud_boots"):
        engine.mud_step = True
        if "mud" not in p.flags:
            p.flags.add("mud")
            engine.log("The mud drags at your feet: every step here takes two turns.")
    if before and _trait(engine, "runner"):
        engine.disengaged = {id(m) for m in before if abs(m.x - p.x) + abs(m.y - p.y) > 1}
    if wade and "wade" not in p.flags:
        p.flags.add("wade")
        engine.log("You wade into the shallows. Nothing on legs follows you in.")


# ---- Pole-vault -----------------------------------------------------------------------------------------
def can_vault(engine) -> str:
    """Why not (empty: you can)."""
    p = engine.player
    if not _trait(engine, "vault"):
        return "You have nothing to vault with."
    if getattr(p, "vault_used", False):
        return "You've vaulted once in this area already."
    return ""


def vault_landing(engine, dx: int, dy: int) -> tuple[tuple[int, int] | None, str]:
    p, gm = engine.player, engine.game_map
    mx, my, lx, ly = p.x + dx, p.y + dy, p.x + 2 * dx, p.y + 2 * dy
    if not gm.in_bounds(lx, ly):
        return None, "There's nowhere to land."
    if not gm.tile_at(mx, my).transparent:
        return None, f"The {gm.tile_at(mx, my).name} is in the way."
    t = gm.tile_at(lx, ly)
    if not t.walkable or t.symbol in NO_LANDING:
        return None, f"You can't land on the {t.name}."
    if gm.monster_at(lx, ly) or gm.npc_at(lx, ly):
        return None, "Someone's standing where you'd land."
    return (lx, ly), ""


def vault(engine, dx: int, dy: int) -> bool:
    """Leap two cells. True if it happened (a turn)."""
    why = can_vault(engine)
    spot, why2 = vault_landing(engine, dx, dy) if not why else (None, why)
    if spot is None:
        engine.log(why or why2)
        return False
    p, gm = engine.player, engine.game_map
    over = gm.monster_at(p.x + dx, p.y + dy)
    before = beside(engine)
    fx, fy = p.x, p.y
    p.x, p.y = spot
    p.vault_used = True
    p.stepped_now = True
    engine.log(f"You plant the staff and vault over the {over.name}." if over else "You plant the staff and vault.")
    if before and _trait(engine, "runner"):
        engine.disengaged = {id(m) for m in before if abs(m.x - p.x) + abs(m.y - p.y) > 1}
    from game import sound
    sound.step(gm.tile_at(*spot).symbol, walking=False)
    engine.on_step(fx, fy)
    return True
