"""Ranged combat: bows, arrows and Marksmanship.

A wielded weapon with a "range" property (a bow) can fire its "ammo" (arrows)
at a spot in view and within range. The arrow flies along a straight line and
strikes the first creature in its way. Hit chance uses the usual formula, with
ranged accuracy: Celerity + artifact accuracy + 2 per Marksmanship rank above 1,
minus 1 for every 3 cells of distance. Damage is the bow's dice (no
Physicality bonus), minus armour, at least 1.

Every shot at a creature is Marksmanship practice; a hit counts double. A shot
arrow survives half the time, landing where it struck or fell.
"""
from __future__ import annotations

import random

from game import gear
from game.look import can_see

SKILL = "marksmanship"

RANK_BONUS = 2            # accuracy per Marksmanship rank above 1
DISTANCE_PENALTY = 3      # -1 accuracy for every this many cells away
ARROW_SURVIVES = 0.5      # chance a shot arrow can be picked up again


def skill_of(weapon) -> str:
    """The skill a ranged weapon practises: Marksmanship for bows, Crossbows for crossbows (v0.78.0)."""
    return weapon.type.properties.get("skill", SKILL) if weapon is not None else SKILL


def bow(player):
    """The wielded ranged weapon (a bow or a crossbow), if any."""
    weapon = player.equipped.get("weapon")
    return weapon if weapon and "range" in weapon.type.properties else None


def distance(x0: int, y0: int, x1: int, y1: int, aspect: float = 2.0) -> float:
    """How far, counting rows double (cells are twice as tall as wide), as sight does."""
    return ((x1 - x0) ** 2 + (aspect * (y1 - y0)) ** 2) ** 0.5


def line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """The cells from (x0, y0) towards (x1, y1), not counting the start (Bresenham)."""
    cells = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    err, x, y = dx + dy, x0, y0
    while (x, y) != (x1, y1):
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
        cells.append((x, y))
    return cells


def flight(engine, tx: int, ty: int) -> tuple[list[tuple[int, int]], object | None]:
    """The path an arrow takes towards (tx, ty): it stops at the first creature (returned)
    or just before anything solid."""
    p, gm = engine.player, engine.game_map
    path = []
    for cell in line(p.x, p.y, tx, ty):
        if not gm.in_bounds(*cell) or not gm.transparent[cell]:
            break
        path.append(cell)
        creature = gm.monster_at(*cell)
        if creature and not creature.type.ghost and not creature.burrowed:   # (arrows pass through ash and over the buried)
            return path, creature
    return path, None


def accuracy(player, dist: float) -> int:
    from game import artifacts
    sk_id = skill_of(bow(player))
    rank = player.skill(sk_id).rank
    from game import injuries
    from game import weaponskills
    from game import talents
    steady = ((sk_id == SKILL and rank >= weaponskills.PASSIVE_RANK)       # Steady hand (or the trait)
              or talents.total(player, "steady"))
    braced = (weaponskills.BRACED_ACCURACY if sk_id == "crossbows" and rank >= weaponskills.PASSIVE_RANK
              and not getattr(player, "stepped_last", False) else 0)     # Braced (Crossbows 3, v0.78.0)
    aimed = weaponskills.AIM_ACCURACY if player.readied == "Aimed shot" else 0
    from game import talents
    aimed += talents.total(player, "ranged_accuracy")          # (Eagle Eye)
    return (player.stats["celerity"] + artifacts.bonus(player, "accuracy") + injuries.total(player, "ranged")
            + RANK_BONUS * (rank - 1) - (0 if steady else int(dist // DISTANCE_PENALTY)) + aimed
            - (2 if player.dazed else 0) + gear.accuracy(bow(player)) + braced)     # (the bow's tier, v0.75.0)


def hit_chance(player, creature, dist: float) -> int:
    from game import combat, mastery
    return combat.hit_chance(accuracy(player, dist) + mastery.prey_bonus(player, creature)[0], creature.evasion)


def can_fire(engine) -> str | None:
    """Why the player can't shoot right now, or None if they can."""
    p = engine.player
    weapon = bow(p)
    if weapon is None:
        return "You need a bow or a crossbow in hand to shoot."
    ammo = weapon.type.properties.get("ammo", "arrow")
    if p.inventory.count_of(ammo) <= 0:
        return f"You have no {engine.catalogue[ammo].label(2)[2:]} left."
    return None


def in_range(engine, x: int, y: int) -> bool:
    weapon = bow(engine.player)
    p = engine.player
    return weapon is not None and distance(p.x, p.y, x, y) <= bow_range(p, weapon)


def bow_range(player, weapon) -> int:
    from game import talents, mastery            # (Long Draw; an Archer's calling)
    return weapon.type.properties["range"] + talents.total(player, "range") + mastery.calling_bonus(player, "range")


def fire(engine, tx: int, ty: int, rng: random.Random = random) -> bool:
    """Shoot at (tx, ty). Returns True if a turn passed."""
    from game import combat
    from game.items import FloorItem, Item
    from game.skills import add_practice
    p, gm = engine.player, engine.game_map
    why = can_fire(engine)
    if why:
        engine.log(why)
        return False
    if (tx, ty) == (p.x, p.y):
        engine.log("Pick something to shoot at.")
        return False
    if not can_see(engine, tx, ty):
        engine.log("You can't see there.")
        return False
    if not in_range(engine, tx, ty):
        engine.log("That's out of range.")
        return False
    weapon = bow(p)
    ammo_id = weapon.type.properties.get("ammo", "arrow")
    i = next(n for n, it in enumerate(p.inventory.items) if it.type.id == ammo_id)
    p.inventory.remove(i, 1)
    p.note_weapon_use()   # every shot counts towards the Hunter's calling
    sk_id = skill_of(weapon)
    from game import weaponskills
    path, creature = flight(engine, tx, ty)
    piercing = creature is not None and p.readied == "Piercing bolt" and weaponskills.spend(p)
    targets = [creature] if creature is not None else []
    if piercing:                      # Piercing bolt (Crossbows 5, v0.78.0): everything in its line, to range
        path, targets = flight_through(engine, tx, ty)
    landed = path[-1] if path else (p.x, p.y)
    from game import sound
    sound.play("bow")
    noun = "bolt" if ammo_id == "bolt" else "arrow"
    if not targets:
        engine.log(f"Your {noun} flies wide and clatters away." if path else f"Your {noun} strikes the rock at once.")
    skill = engine.skills.get(sk_id)
    aimed = bool(targets) and p.readied == "Aimed shot" and weaponskills.spend(p)
    what = "Your aimed shot" if aimed else ("Your piercing bolt" if piercing else f"Your {noun}")
    from game import talents
    braced = sk_id == "crossbows" and weaponskills.has_passive(p, "crossbows") and not getattr(p, "stepped_last", False)
    for creature in targets:
        unaware = not creature.awake
        creature.awake, creature.turns_unseen = True, 0
        dist = distance(p.x, p.y, creature.x, creature.y)
        chance = hit_chance(p, creature, dist)
        hit = rng.randint(1, 100) <= chance or (unaware and bool(talents.total(p, "sure_unnoticed")))   # Reliable
        if hit:
            dice = weapon.type.properties["damage"]
            from game import talents
            from game import mastery
            damage = max(1, sum(combat.roll(dice, rng) for _ in range(2 if aimed else 1))
                         + talents.total(p, "ranged_damage") + mastery.prey_bonus(p, creature)[1]
                         + gear.damage(weapon) - max(0, creature.armor - talents.total(p, "ranged_pierce"))
                         + (talents.total(p, "marked_shot_damage") if getattr(creature, "shot", False) else 0)
                         + (talents.total(p, "braced_damage") if braced else 0)                # Braced stock
                         + (talents.total(p, "tier3_ranged_damage") if creature.type.tier >= 3 else 0))   # Siege-made
            creature.shot = True                                           # (Hunter's mark, a trait)
            creature.take_damage(damage)
            sound.play("arrow_hit")
            if creature.is_dead:
                engine.log(f"{what} kills the {creature.name}.")
                engine.slay(creature)
            else:
                engine.log(f"{what} hits the {creature.name} for {damage}.")
                shot_traits(engine, creature, rng)
        else:
            engine.log(f"{what} misses the {creature.name}.")
        if skill:
            from game.skills import gain_for
            for message in add_practice(skill, p.skill(sk_id), gain_for(skill, p) * (2 if hit else 1)):
                engine.log(message)
    if weapon.type.properties.get("reload"):   # a crossbow: a turn to wind it before the next shot
        from game import talents
        p.cranked = not getattr(p, "cranked", False)
        p.unloaded = not (talents.total(p, "quick_reload") and p.cranked)    # Quick crank: every other shot
    from game import talents
    if path and rng.random() < ARROW_SURVIVES + talents.total(p, "arrow_survive") / 100:
        gm.items.append(FloorItem(*landed, Item(engine.catalogue[ammo_id])))
    free = talents.total(p, "free_shot")                    # Swift string (a trait): no turn, sometimes
    return not (free and rng.randint(1, 100) <= free)


def flight_through(engine, tx: int, ty: int) -> tuple[list, list]:
    """A piercing bolt: on along the line past (tx, ty) to the weapon's range, through every creature,
    stopping before anything solid. Returns the path and the creatures on it."""
    p, gm = engine.player, engine.game_map
    reach = bow_range(p, bow(p))
    far = (p.x + (tx - p.x) * 40, p.y + (ty - p.y) * 40)
    path, hit = [], []
    for cell in line(p.x, p.y, *far):
        if not gm.in_bounds(*cell) or not gm.transparent[cell] or distance(p.x, p.y, *cell) > reach:
            break
        path.append(cell)
        m = gm.monster_at(*cell)
        if m and not m.type.ghost and not m.burrowed:
            hit.append(m)
    return path, hit


def reload(engine) -> bool:
    """f with an unwound crossbow: a turn to wind it and fit a bolt."""
    engine.player.unloaded = False
    engine.log("You wind the crossbow and fit a bolt.")
    return True


def shot_traits(engine, creature, rng) -> None:
    """Bow traits that act when a shot lands (v0.77.0): bleeding, pinning."""
    from game import talents, weaponskills as ws
    p = engine.player
    bleed = talents.total(p, "ranged_bleed_chance")
    if bleed and rng.randint(1, 100) <= bleed and creature.bleeding < ws.REND_TURNS:
        creature.bleeding = ws.REND_TURNS
        engine.log(f"The {creature.name} is bleeding.")
    pin = talents.total(p, "ranged_stagger")
    if pin and rng.randint(1, 100) <= pin:
        creature.staggered = max(creature.staggered, 2)
        engine.log(f"The arrow pins the {creature.name}.")
