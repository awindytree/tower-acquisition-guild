"""Throwing (roadmap step 2, v0.82.0): `h` (hurl) throws something at a cell you can see.

What can be thrown:
  * **supplies** with a `throw` property (data/items.json): a flash pot (everything within a cell of
    where it lands loses a turn), a smoke jar (a cloud that blocks sight for a while), a lure (creatures
    that haven't seen you, or have lost you, go to it for a while);
  * **the weapon in hand**, if it has a trait that lets it be thrown (Wrist-flick on a knife, Throwing
    balance on an axe: the talent key `throw_weapon` is its range). It's an attack: melee accuracy, less
    a point every 3 cells, and its own damage. A knife comes back to your hand; anything else lands where
    it struck, and you're bare-handed until you pick it up.
A throw flies like an arrow (ranged.flight: it stops at the first creature or anything solid) and takes
a turn. Numbers are drafts.
"""
from __future__ import annotations

from game import combat, ranged
from game.items import FloorItem, Item
from game.look import can_see

SUPPLY_RANGE = 5          # how far a pot, jar or lure goes
FLASH_RADIUS = 1          # a flash pot: everything this close to where it lands (rows count once)
SMOKE_RADIUS = 2          # a smoke jar's cloud, and how long it hangs
SMOKE_TURNS = 8
LURE_TURNS = 12           # a lure: how long it draws them, and from how far
LURE_REACH = 12
LOST_TURNS = 3            # a creature that hasn't seen you for this long has "lost" you


def weapon_range(player) -> int:
    from game import talents
    if player.equipped.get("weapon") is None:
        return 0
    return talents.total(player, "throw_weapon")


def throwables(player) -> list:
    """What the Hunter can throw now: [(label, item, range)], the weapon in hand first."""
    out = []
    w = player.equipped.get("weapon")
    if w is not None and weapon_range(player):
        out.append((f"{w.label} (in hand)", w, weapon_range(player)))
    seen = set()
    for it in player.inventory.items:
        if it.type.properties.get("throw") and it.type.id not in seen:
            seen.add(it.type.id)
            out.append((f"{it.type.label(player.inventory.count_of(it.type.id))}", it, SUPPLY_RANGE))
    return out


def why_not(engine, item, reach: int, tx: int, ty: int) -> str | None:
    p = engine.player
    if (tx, ty) == (p.x, p.y):
        return "Pick somewhere to throw it."
    if not can_see(engine, tx, ty):
        return "You can only throw at what you can see."
    if ranged.distance(p.x, p.y, tx, ty) > reach:
        return f"That's too far: you can throw it {reach}."
    if item is p.equipped.get("weapon") and abs(tx - p.x) + abs(ty - p.y) <= 1:
        return "It's right beside you: strike it instead."
    return None


def throw(engine, item, tx: int, ty: int) -> bool:
    """Throw it at (tx, ty). Returns True if a turn passed."""
    p, gm = engine.player, engine.game_map
    reach = weapon_range(p) if item is p.equipped.get("weapon") else SUPPLY_RANGE
    why = why_not(engine, item, reach, tx, ty)
    if why:
        engine.log(why)
        return False
    path, creature = ranged.flight(engine, tx, ty)
    landed = path[-1] if path else (p.x, p.y)
    from game import sound
    sound.play("bow")
    if item is p.equipped.get("weapon"):
        return _throw_weapon(engine, item, creature, landed)
    kind = item.type.properties["throw"]
    i = next(n for n, it in enumerate(p.inventory.items) if it.type.id == item.type.id)
    p.inventory.remove(i, 1)
    where = (creature.x, creature.y) if creature is not None else landed
    if kind == "flash":
        hit = [m for m in gm.monsters if max(abs(m.x - where[0]), abs(m.y - where[1])) <= FLASH_RADIUS
               and not m.type.ghost and not m.burrowed]
        for m in hit:
            m.staggered = max(m.staggered, 1)
        engine.log("The pot bursts in a white flash" + (f": {_reel(hit)}." if hit else "."))
    elif kind == "smoke":
        engine.log("The jar breaks, and smoke billows up.")
        make_smoke(gm, where)
    elif kind == "lure":
        gm.lure = [where[0], where[1], LURE_TURNS]
        engine.log("The lure lands with a soft thump. Its smell spreads.")
    return True


def _reel(ms) -> str:
    if len(ms) == 1:
        return f"the {ms[0].name} reels"
    words = {2: "two", 3: "three", 4: "four", 5: "five"}
    return f"{words.get(len(ms), len(ms))} creatures reel"


def _throw_weapon(engine, w, creature, landed) -> bool:
    p, gm = engine.player, engine.game_map
    from game import gear, weaponskills
    returns = gear.gear_type(w.type) == "knife"            # Wrist-flick: it comes back to your hand
    if creature is not None:
        dist = ranged.distance(p.x, p.y, creature.x, creature.y)
        creature.awake, creature.touched = True, True
        chance = combat.hit_chance(p.accuracy - int(dist // 3), creature.evasion)
        if engine.rng.randint(1, 100) <= chance:
            dmg = max(1, combat.roll(w.type.properties.get("damage", "1d4"), engine.rng) + p.damage_bonus
                      - max(0, creature.armor - p.pierce))
            creature.take_damage(dmg)
            weaponskills.practise(engine, True)
            if creature.is_dead:
                engine.log(f"Your thrown {w.type.name} kills the {creature.name}.")
                engine.slay(creature)
            else:
                engine.log(f"Your thrown {w.type.name} hits the {creature.name} for {dmg}.")
        else:
            weaponskills.practise(engine, False)
            engine.log(f"Your thrown {w.type.name} misses the {creature.name}.")
    else:
        engine.log(f"Your {w.type.name} flies and clatters down.")
    if returns:
        engine.log(f"The {w.type.name} comes back to your hand.")
        return True
    del p.equipped["weapon"]                               # (an axe stays where it fell)
    p.gear_changed()
    spot = (creature.x, creature.y) if creature is not None and creature in gm.monsters else landed
    gm.items.append(FloorItem(*spot, w))
    return True


# ---- Smoke and lures, as turns pass -------------------------------------------------------------
def make_smoke(gm, where) -> None:
    cx, cy = where
    for x in range(cx - SMOKE_RADIUS * 2, cx + SMOKE_RADIUS * 2 + 1):
        for y in range(cy - SMOKE_RADIUS, cy + SMOKE_RADIUS + 1):
            if not gm.in_bounds(x, y) or ((x - cx) / 2) ** 2 + (y - cy) ** 2 > SMOKE_RADIUS ** 2 + 0.5:
                continue
            if not gm.is_walkable(x, y):
                continue
            gm.smoke[(x, y)] = SMOKE_TURNS
            gm.transparent[x, y] = False


def tick(engine) -> None:
    """Smoke thins; a lure's smell fades (from Engine._end_turn_once)."""
    gm = engine.game_map
    smoke = getattr(gm, "smoke", None)
    if smoke:
        from game.tiles import TILE_TYPES
        for cell in list(smoke):
            smoke[cell] -= 1
            if smoke[cell] <= 0:
                del smoke[cell]
                gm.transparent[cell] = TILE_TYPES[gm.kinds[cell]].transparent
    lure = getattr(gm, "lure", None)
    if lure:
        lure[2] -= 1
        if lure[2] <= 0:
            gm.lure = None


def lured(engine, m) -> tuple | None:
    """Where a lure draws this creature, if it does: one that hasn't seen you or has lost you, near it."""
    lure = getattr(engine.game_map, "lure", None)
    if not lure or m.type.ghost or m.burrowed or m.type.behaviour == "still":
        return None
    if m.awake and getattr(m, "turns_unseen", 0) < LOST_TURNS:
        return None
    lx, ly = lure[0], lure[1]
    if abs(m.x - lx) + abs(m.y - ly) > LURE_REACH:
        return None
    return lx, ly
