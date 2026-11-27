"""Tower Artifacts: identifying them, the Artificers' workshop, and what working ones do.

Broken artifacts are found on hunts. Until a Hunter identifies one, it shows
only its appearance and rarity (see ItemType.name). Identification is a
skill: your rank is the highest rarity tier you can identify.

At a workshop a Hunter can:
  repair  - pay the rarity's repair fee; get the working artifact back
  sell    - the Artificer buys it broken, for the rarity's nominal price
  consign - the Artificer repairs and sells it; the Hunter is paid at once
            (working value - repair fee) / 2
The Artificer quotes by rarity alone and doesn't identify anything until it's
repaired, so selling or consigning an unknown artifact is a gamble.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from game.items import Item, ItemType
from game.skills import add_practice, gain_for

IDENTIFICATION = "identification"


# ---- Identifying -----------------------------------------------------------------------
def study(player, item_type: ItemType, skills: dict) -> tuple[bool, list[str]]:
    """Try to identify a broken artifact. Returns (took time, messages)."""
    skill = skills[IDENTIFICATION]
    state = player.skill(IDENTIFICATION)
    tier, rarity = item_type.rarity.tier, item_type.rarity.name
    from game import talents
    tier = max(1, tier - talents.total(player, "identify"))     # (Good Eye: a rarity beyond your rank)
    if item_type.identified:
        return False, [f"You already know this is {_a(item_type.name)}. It needs an Artificer's repair."]
    if item_type.properties.get("locked"):        # story-locked (Chapter 1's Unique, v0.67.0)
        return False, [f"You turn the {item_type.name} over and over. Its marks mean nothing to you, and nothing "
                       "you know of Identification gets a grip on it. Not yet."]
    studied = player.studied.get(item_type.id, 0)
    if studied >= state.rank:
        return False, [f"You've studied the {item_type.name} as far as your skill allows. "
                       f"It's beyond rank {state.rank} Identification."]
    player.studied[item_type.id] = state.rank
    gain = gain_for(skill, player)
    if tier <= state.rank:
        player.known_artifacts.add(item_type.id)
        player.studied.pop(item_type.id, None)
        messages = [f"You study the artifact. It's {_a(item_type.name)}! ({rarity})"]
    elif tier == state.rank + 1:
        messages = [f"You study the {item_type.name}, but it's beyond you. ({rarity} needs rank {tier}.) "
                    "Still, you learn something from trying."]
    else:
        return True, [f"You study the {item_type.name}, but it's far beyond you. "
                      f"({rarity} needs rank {tier} Identification.)"]
    return True, messages + add_practice(skill, state, gain)


def learn(player, item_type: ItemType) -> None:
    """The Hunter now knows what this broken artifact is (e.g. after a repair)."""
    player.known_artifacts.add(item_type.id)
    player.studied.pop(item_type.id, None)


# ---- The workshop ------------------------------------------------------------------------
# Prices take the Hunter's Bargaining when given a player (v0.59.0, game/bargaining.py).
def repair_fee(t: ItemType, player=None) -> int:
    from game import bargaining
    return bargaining.pay(player, t.rarity.repair_fee)


ARTIFICER_PAY = 1.2   # balance pass 3 (user, v0.62.0): what the artificer pays Hunters, +20%


def broken_price(t: ItemType, player=None) -> int:
    from game import bargaining
    return bargaining.paid(player, int(t.rarity.broken_price * ARTIFICER_PAY))


def consign_share(t: ItemType, player=None) -> int:
    """Consigning (v0.64.0, user): the Hunter first pays their half of the repair fee (rounded up)."""
    from game import bargaining
    return bargaining.pay(player, -(-t.rarity.repair_fee // 2))


def consign_payout(t: ItemType, player=None) -> int:
    """...then is paid half the working sale price, with the artificer's +20% (ARTIFICER_PAY).
    Hunter and artificer split the prize and share the repair (the user's design, 2026-11-18);
    since v0.64.0 the Hunter's half of the fee is paid up front, so consigning needs shards in
    hand, and selling broken is the way out when they're short. (Before: one payment of
    (working price - repair fee) / 2, never below the broken price.)"""
    from game import bargaining
    return bargaining.paid(player, int(t.value / 2 * ARTIFICER_PAY))


LOCKED = ("The artificer turns it over for a long time, then hands it back. \"I can't tell you what this is. "
          "I don't think anyone in this city can.\"")


def locked(t: ItemType) -> bool:
    """A story artifact: kept, not repaired, sold or studied (v0.67.0, user: story-locked)."""
    return bool(t.properties.get("locked"))


def repair(player, index: int, catalogue) -> tuple[bool, str]:
    item = player.inventory.items[index]
    t = item.type
    if locked(t):
        return False, LOCKED
    fee = repair_fee(t, player)
    if player.shards < fee:
        return False, f"Repairing it costs {fee} shards. You don't have enough."
    was_known = t.identified
    player.shards -= fee
    from game import sound
    sound.play("pay")
    working = catalogue[t.repairs_to]
    player.inventory.items[index] = Item(working)
    learn(player, t)
    found = "" if was_known else f" It was {_a(t.real_name)}."
    return True, f"The artificer repairs it for {fee} shards.{found} You now have {_a(working.name)}."


def sell_broken(player, index: int) -> tuple[bool, str]:
    t = player.inventory.items[index].type
    if locked(t):
        return False, LOCKED
    price = broken_price(t, player)
    player.inventory.remove(index, 1)
    player.earn(price)
    from game import sound
    sound.play("pay")
    return True, f"The artificer buys the {t.name} as it is, for {price} shards."


WORKING_SELL_RATE = 0.5   # v0.52.0 (user): the artificer buys repaired artifacts too; my number


def working_price(t: ItemType, player=None) -> int:
    """What the artificer pays for a working artifact: half its sale price (like the supplier)."""
    from game import bargaining
    return bargaining.paid(player, max(1, int(t.value * WORKING_SELL_RATE * ARTIFICER_PAY)))


def sell_working(player, index: int, stock=None) -> tuple[bool, str]:
    """Sell a repaired artifact from the bag; it goes up for sale in the workshop at full price."""
    item = player.inventory.items[index]
    t = item.type
    if player.is_equipped(item):
        return False, f"Take off the {t.name} first."
    price = working_price(t, player)
    player.inventory.remove(index, 1)
    player.earn(price)
    from game import sound
    sound.play("pay")
    if stock is not None:
        stock.add(t.id, t.value)
    return True, f"The artificer buys the {t.name} for {price} shards."


def consign(player, index: int, stock=None, catalogue=None) -> tuple[bool, str]:
    """Paid at once. If the workshop's stock is given, the repaired artifact goes up for sale there."""
    t = player.inventory.items[index].type
    if locked(t):
        return False, LOCKED
    was_known = t.identified
    share = consign_share(t, player)
    if player.shards < share:
        return False, f"Consigning it means paying your half of the repair first: {share} shards. You don't have enough."
    pay = consign_payout(t, player)
    player.shards -= share
    player.inventory.remove(index, 1)
    player.earn(pay)
    from game import sound
    sound.play("pay")
    learn(player, t)
    if stock is not None and catalogue is not None:
        working = catalogue[t.repairs_to]
        stock.add(working.id, working.value)
    found = "" if was_known else f" It turns out to have been {_a(t.real_name)}."
    return True, (f"You pay your half of the repair ({share} shards) and consign it to the workshop; "
                  f"you're paid {pay} shards.{found}")


# ---- Jodebris and windcatchers ------------------------------------------------------------------
# Artifacts run on Jodebris, the Chorus Winds. In the Brisering (Bytorsskug)
# they work freely. Out in the miasma (on a hunt) they need an equipped
# windcatcher with Jodebris left. A windcatcher drains as turns pass on a hunt,
# and refills when you're back in the Brisering.
# v0.52.0 (user): artifacts with a limited number of uses (heal, reveal...) hold just enough
# Jodebris of their own to do their work, so they work anywhere with no windcatcher, and using
# them doesn't draw on one. Lasting effects (light, armour, accuracy...) still need a windcatcher
# with Jodebris beyond the Brisering.
DRAIN_PER_TURN = 1
LOW_FRACTION = 0.25  # warn when a windcatcher falls this low


def charge_words(w) -> str:
    """How full a windcatcher is, in words: the numbers are never shown (user, v0.41.1)."""
    if not w.capacity or w.jodebris <= 0:
        return "empty"
    share = w.jodebris / w.capacity
    if share >= 1:
        return "full"
    if share >= 0.75:
        return "nearly full"
    if share >= 0.5:
        return "more than half full"
    if share > LOW_FRACTION:           # at a quarter it warns, and reads "running low"
        return "less than half full"
    return "running low"


def powered(player) -> bool:
    if not player.in_miasma:
        return True
    w = player.windcatcher
    return w is not None and w.jodebris > 0


def drain(player, amount: int) -> list[str]:
    """Take Jodebris from the equipped windcatcher (on a hunt). Returns warnings."""
    w = player.windcatcher
    if not player.in_miasma or w is None or w.jodebris <= 0:
        return []
    before = w.jodebris
    from game import attunement             # Attunement slows the drain (v0.57.0); fractions carry over
    owed = amount * attunement.drain_factor(player) + getattr(player, "jb_carry", 0.0)
    whole = int(owed)
    player.jb_carry = owed - whole
    w.charge = max(0, before - whole)
    low = int(w.capacity * LOW_FRACTION)
    if w.charge == 0:
        player.gear_changed()                   # (their bonuses go with them: v0.101.0)
        return [f"Your {w.type.name} falls silent. Your artifacts go still."]
    if before > low >= w.charge:
        return [f"Your {w.type.name}'s hum is fading. It's running low on Jodebris."]
    return []


def refill(player) -> None:
    """Back in the Brisering: every windcatcher fills up again."""
    for item in player.all_items():     # (the equipped one is out of the bag since v0.69.0)
        if item.type.properties.get("windcatcher"):
            item.charge = None


# ---- Working artifacts ---------------------------------------------------------------------
def carried(player) -> list[ItemType]:
    """Artifacts whose effects are on right now: those in artifact slots, if powered.
    (Artifacts in the bag do nothing; equip them first.)"""
    if not powered(player):
        return []
    return [i.type for i in player.equipped_artifacts]


def light_bonus(player) -> int:
    """Extra sight and torchlight in dark places. Only the strongest light counts."""
    return max((t.properties.get("light", 0) for t in carried(player)), default=0)


def bonus_total(player, key: str) -> int:
    """A talent key from working artifacts carried: their "bonus" {key: n} (v0.101.0), read through
    talents.total, so an artifact can do anything a talent or a trait does."""
    if not hasattr(player, "artifact_slots"):
        return 0
    return sum(t.properties.get("bonus", {}).get(key, 0) for t in carried(player))


def bonus(player, stat: str) -> int:
    """Armour, accuracy or evasion from working artifacts carried (these add up)."""
    return sum(t.properties.get(stat, 0) for t in carried(player))


def uses_per_hunt(player, t: ItemType) -> int:
    base = t.properties.get("uses_per_hunt", 0)
    if not base:
        return 0
    from game import attunement
    return base + attunement.extra_uses(player)      # one more at Attunement 3 (v0.57.0)


def uses_left(player, t: ItemType) -> int:
    return uses_per_hunt(player, t) - player.artifact_uses.get(t.id, 0)


def use(engine, item) -> bool:
    """Use a working artifact (an Item in the bag or an artifact slot). True if it took a turn."""
    player = engine.player
    t = item.type
    if t.properties.get("windcatcher"):
        w = item
        engine.log(f"Equip the {t.name} (e) to carry Jodebris into the miasma. "
                   f"It's {charge_words(w)}.")
        return False
    effect = t.properties.get("use")
    if not any(item is i for i in player.equipped_artifacts):
        engine.log(f"Equip the {t.name} (e) in an artifact slot to use it.")
        return False
    if effect is None:
        engine.log(f"The {t.name} works simply by being equipped.")
        return False
    if uses_left(player, t) <= 0:
        engine.log(f"The {t.name} is spent. It will recover before your next hunt.")
        return False
    cost = t.properties.get("hp_cost", 0)          # a use that takes blood (v0.101.0)
    if cost and player.stats.hp <= cost:
        engine.log(f"The {t.name} wants {cost} of your blood, and you haven't got it to give.")
        return False
    if effect in USES:
        if not USES[effect](engine, t):
            return False
    elif effect == "heal":
        if player.stats.hp >= player.stats.max_hp:
            engine.log("You're not hurt.")
            return False
        gained = player.stats.heal(t.properties.get("heal", 0))
        engine.log(f"The {t.name} closes your wounds. (+{gained} HP)")
    elif effect == "reveal":
        gm = engine.game_map
        if not gm.fog:
            engine.log(f"The {t.name} turns, but you already know this place.")
            return False
        floor = gm.walkable
        near = floor.copy()  # every floor, and the walls next to it
        near[1:, :] |= floor[:-1, :]; near[:-1, :] |= floor[1:, :]
        near[:, 1:] |= floor[:, :-1]; near[:, :-1] |= floor[:, 1:]
        gm.explored |= near
        engine.log(f"The {t.name} turns, and the shape of this place comes to you.")
    else:
        engine.log(f"Nothing happens. (Unknown effect {effect!r}.)")
        return False
    if cost:
        player.stats.hp -= cost
        engine.log(f"It takes its price: {cost} HP.")
    player.artifact_uses[t.id] = player.artifact_uses.get(t.id, 0) + 1
    from game import attunement
    attunement.practise(engine)                    # (v0.57.0)
    left = uses_left(player, t)
    if left == 0:
        engine.log(f"The {t.name} falls still. It's spent for this hunt.")
    return True


# ---- More uses (v0.101.0: the user's "we really need more artifacts"; every effect a draft) -----------
# Each returns True if it happened (a use spent, a turn taken), False if it couldn't (nothing spent).
def _monsters(engine, radius=None, seen=True):
    p, gm = engine.player, engine.game_map
    out = []
    for m in gm.monsters:
        if getattr(m, "burrowed", False) or m.hp <= 0:
            continue
        if seen and not engine.visible[m.x, m.y]:
            continue
        if radius is not None and (m.x - p.x) ** 2 + ((m.y - p.y) * 2) ** 2 > radius ** 2:
            continue
        out.append(m)
    return out


def _on_hunt(engine, t) -> bool:
    if engine.hunt is None:
        engine.log(f"The {t.name} does nothing here: it's made for the miasma.")
        return False
    return True


def _blink(engine, t) -> bool:
    """Step through the Jodebris to a spot you can see, as far from the creatures as it allows."""
    if not _on_hunt(engine, t):
        return False
    p, gm = engine.player, engine.game_map
    near = [m for m in _monsters(engine) if not m.type.ghost]
    if not near:
        engine.log(f"The {t.name} tugs at you, then lets go: there's nothing here to get away from.")
        return False
    reach = t.properties.get("reach", 6)
    taken = {(m.x, m.y) for m in gm.monsters} | {(n.x, n.y) for n in gm.npcs}
    best, score = None, -1.0
    for x in range(p.x - reach, p.x + reach + 1):
        for y in range(p.y - reach // 2 - 1, p.y + reach // 2 + 2):
            if not gm.in_bounds(x, y) or not engine.visible[x, y] or not gm.is_walkable(x, y) or (x, y) in taken:
                continue
            if (x - p.x) ** 2 + ((y - p.y) * 2) ** 2 > reach ** 2 or gm.tile_at(x, y).symbol in "<>HG":
                continue
            d = min((m.x - x) ** 2 + ((m.y - y) * 2) ** 2 for m in near)
            if d > score:
                best, score = (x, y), d
    if best is None or best == (p.x, p.y):
        engine.log(f"The {t.name} finds nowhere better to put you.")
        return False
    p.x, p.y = best
    engine.log(f"The {t.name} folds the air, and you're elsewhere.")
    return True


def _flash(engine, t) -> bool:
    if not _on_hunt(engine, t):
        return False
    hit = _monsters(engine, t.properties.get("radius", 6))
    if not hit:
        engine.log(f"The {t.name} flares, white, at nothing.")
        return True
    turns = t.properties.get("turns", 2)
    for m in hit:
        m.staggered = max(m.staggered, turns)
        m.awake = True
    engine.log(f"The {t.name} flares white. {_count(hit)} reel{'s' if len(hit) == 1 else ''}, blinded.")
    return True


def _ward(engine, t) -> bool:
    p = engine.player
    p.ward, p.ward_turns = t.properties.get("ward", 3), t.properties.get("turns", 20)
    engine.log(f"The {t.name} hums, and the air around you stiffens. (Armour +{p.ward} for {p.ward_turns} turns)")
    return True


def _cure(engine, t) -> bool:
    p = engine.player
    running = [i for i in getattr(p, "injuries", []) if getattr(i, "dot_left", 0) > 0]
    venom = getattr(p, "venom", 0) > 0
    if not running and not venom:
        engine.log("You're not bleeding or poisoned.")
        return False
    for i in running:
        i.dot_left = 0
    p.venom = 0
    engine.log(f"The {t.name} goes cold in your hand, and the bleeding and the poison stop.")
    return True


DIRS = ((0, "east"), (45, "north-east"), (90, "north"), (135, "north-west"), (180, "west"), (225, "south-west"),
        (270, "south"), (315, "south-east"), (360, "east"))


def _dir(dx, dy) -> str:
    import math
    a = math.degrees(math.atan2(-dy * 2, dx)) % 360
    return min(DIRS, key=lambda d: abs(d[0] - a))[1]


def _sense(engine, t) -> bool:
    if not _on_hunt(engine, t):
        return False
    p = engine.player
    all_ = [m for m in _monsters(engine, seen=False) if not m.type.ghost]
    if not all_:
        engine.log(f"The {t.name} listens. Nothing else lives in this area.")
        return True
    ways = {}
    for m in all_:
        ways.setdefault(_dir(m.x - p.x, m.y - p.y), []).append(m)
    parts = [f"{len(v)} to the {k}" for k, v in sorted(ways.items(), key=lambda kv: -len(kv[1]))]
    awake = sum(1 for m in all_ if m.awake)
    engine.log(f"The {t.name} listens: {len(all_)} creature{'s' if len(all_) != 1 else ''} in this area, "
               + ", ".join(parts) + (f". {awake} of them hunting you." if awake else ". None of them knows you're here."))
    return True


def _seek(engine, t) -> bool:
    if not _on_hunt(engine, t):
        return False
    p, gm, c = engine.player, engine.game_map, engine.hunt.contract
    want = c.artifact_id
    if want and any(it.type.id == want for it in p.all_items()):
        engine.log(f"The {t.name} points at your own pack.")
        return True
    here = [f for f in gm.items if f.item.type.id == want] if want else []
    if here:
        f = here[0]
        steps = abs(f.x - p.x) + abs(f.y - p.y)
        engine.log(f"The {t.name} swings and settles: what you came for lies {_dir(f.x - p.x, f.y - p.y)}, "
                   f"about {steps} steps away.")
    elif want:
        engine.log(f"The {t.name} points down: what you came for lies deeper than this.")
    else:
        engine.log(f"The {t.name} spins and finds nothing it's been asked to find.")
    return True


def _home(engine, t) -> bool:
    if not _on_hunt(engine, t):
        return False
    engine.screen = None
    engine.log(f"The {t.name} pulls you back along the way you came, to the trail home.")
    engine.travel(0, arrive_at="entry")
    engine.reach_trail_home()
    return True


def _calm(engine, t) -> bool:
    if not _on_hunt(engine, t):
        return False
    hit = [m for m in _monsters(engine, t.properties.get("radius", 8)) if m.awake and not m.bounty]
    if not hit:
        engine.log(f"The {t.name} sings low. Nothing near is hunting you.")
        return True
    for m in hit:
        m.awake = False
    engine.log(f"The {t.name} sings low, and {_count(hit)} forget{'s' if len(hit) == 1 else ''} you're here.")
    return True


def _smoke(engine, t) -> bool:
    if not _on_hunt(engine, t):
        return False
    from game import throwing
    throwing.make_smoke(engine.game_map, (engine.player.x, engine.player.y))
    engine.log(f"The {t.name} breathes out a grey cloud all around you.")
    return True


def _burst(engine, t) -> bool:
    if not _on_hunt(engine, t):
        return False
    import random as _r
    p = engine.player
    hit = [m for m in engine.game_map.monsters if abs(m.x - p.x) + abs(m.y - p.y) == 1
           and not m.type.ghost and not getattr(m, "burrowed", False)]
    if not hit:
        engine.log(f"The {t.name} wants something beside you to strike.")
        return False
    lo, hi = t.properties.get("damage", [4, 8])
    for m in hit:
        n = engine.rng.randint(lo, hi) if hasattr(engine.rng, "randint") else _r.randint(lo, hi)
        m.hp -= n
        m.awake = True
        engine.log(f"The {t.name} bursts against the {m.type.name}: {n} damage.")
        if m.hp <= 0:
            engine.slay(m)
    return True


def _recharge(engine, t) -> bool:
    w = engine.player.windcatcher
    if w is None:
        engine.log(f"The {t.name} has nothing to pour itself into: equip a windcatcher.")
        return False
    if w.jodebris >= w.capacity:
        engine.log(f"Your {w.type.name} is already full.")
        return False
    add = int(w.capacity * t.properties.get("share", 0.25))
    w.charge = min(w.capacity, w.jodebris + add)
    engine.player.gear_changed()
    engine.log(f"The {t.name} empties itself into your {w.type.name}. It's {charge_words(w)}.")
    return True


def _unrest(engine, t) -> bool:
    """Off a hunt: rest owed taken off at once (it counts its uses between hunts)."""
    if engine.hunt is not None:
        engine.log(f"The {t.name} won't settle out here.")
        return False
    from game import rest
    p = engine.player
    if not rest.owed(p):
        engine.log("You owe no rest.")
        return False
    n = t.properties.get("pulses", 9)
    p.rest_owed = max(0.0, rest.owed(p) - n)
    engine.log(f"You hold the {t.name} and breathe with it, and it's as if you'd slept {rest.text(n, engine.calendar.per_cycle)}. "
               f"{rest.owed_line(engine)}.")
    return True


def _count(ms) -> str:
    if len(ms) == 1:
        return f"The {ms[0].type.name}"
    return f"{len(ms)} creatures"


USES = {"blink": _blink, "flash": _flash, "ward": _ward, "cure": _cure, "sense": _sense, "seek": _seek,
        "home": _home, "calm": _calm, "smoke": _smoke, "burst": _burst, "recharge": _recharge, "unrest": _unrest}

USE_TEXT = {
    "heal": lambda p: f"heal {p.get('heal', 0)}",
    "reveal": lambda p: "map the area",
    "blink": lambda p: f"step away from what's hunting you (up to {p.get('reach', 6)} cells)",
    "flash": lambda p: f"blind what's near for {p.get('turns', 2)} turns",
    "ward": lambda p: f"armour +{p.get('ward', 3)} for {p.get('turns', 20)} turns",
    "cure": lambda p: "stop bleeding and poison",
    "sense": lambda p: "count the area's creatures and where they are",
    "seek": lambda p: "point to what you came for",
    "home": lambda p: "back to the trail home, as a rope does",
    "calm": lambda p: "make what's hunting you nearby forget you",
    "smoke": lambda p: "a cloud of smoke around you",
    "burst": lambda p: f"{p.get('damage', [4, 8])[0]}-{p.get('damage', [4, 8])[1]} damage to everything beside you",
    "recharge": lambda p: f"refill your windcatcher by {round(p.get('share', 0.25) * 100)}%",
    "unrest": lambda p: f"{p.get('pulses', 9)} Pulses of rest owed gone (off a hunt)",
}

BONUS_TEXT = {
    "crit": "{:d}% chance of a telling blow", "sight": "Sight {:+d}", "carry": "Carrying room {:+d}",
    "max_hp": "Max HP {:+d}", "heal_rate": "Heal {:+d} turns sooner", "injury_chance": "{:d}% fewer injuries",
    "daze_resist": "Dazed {:+d} turns less", "wound": "Bleeding and poison {:d}% shorter",
    "notice": "Creatures {:d}% less likely to notice you", "sneak_damage": "Unseen blows {:+d} damage",
    "material_chance": "{:d}% more materials", "material_extra": "{:+d} more of each material",
    "shards_found": "{:d}% more shards found", "xp": "{:d}% more experience", "practice_all": "Skills learned {:d}% faster",
    "draught": "Draughts heal {:+d} more", "ration": "Rations heal {:+d}% more", "track": "Tracks last {:+d} turns longer",
    "ranged_damage": "Shots {:+d} damage", "range": "Range {:+d}", "damage": "Melee damage {:+d}",
    "faints": "{:+d} faint allowed", "drain": "Jodebris drains {:d}% slower", "extra_uses": "Artifacts {:+d} use a hunt",
    "identify": "Identify {:+d} rarity higher", "bounty_pay": "Bounties pay {:d}% more", "request_pay": "Requests pay {:d}% more",
    "low_hp_damage": "Below half HP, {:+d} damage", "solo_accuracy": "Against one creature alone, accuracy {:+d}",
    "second_wind": "Once a hunt, at 0 HP, stand back up", "brisering_steps": "Brisering travel {:d}% quicker",
    "rest_rate": "Rest off a hunt {:d}% quicker", "bargain": "Prices {:d}% better, buying and selling",
    "road_quiet": "{:d}% fewer meetings on the Brisering", "forage": "{:+d} more from each foraging spot",
    "accuracy": "Accuracy {:+d}", "evasion": "Evasion {:+d}", "armor": "Armour {:+d}", "heal_on_kill": "Heal {:+d} on a kill",
    "attr:physicality": "Physicality {:+d}", "attr:celerity": "Celerity {:+d}", "attr:fortitude": "Fortitude {:+d}",
    "attr:acumen": "Acumen {:+d}", "attr:tenacity": "Tenacity {:+d}",
}


def bonus_words(key: str, n: int) -> str:
    """"Max HP +5", "Creatures 20% less likely to notice you"; a trade-off reads as one ("Sight -2")."""
    if key == "notice" and n < 0:
        return f"Creatures {-n}% more likely to notice you"
    if key == "drain" and n < 0:
        return f"Jodebris drains {-n}% faster"
    if key == "injury_chance" and n < 0:
        return f"{-n}% more injuries"
    fmt = BONUS_TEXT.get(key, key.replace("_", " ") + " {:+d}")
    return fmt.format(n) if "{" in fmt else fmt


def effect_text(t: ItemType) -> str:
    """A short summary of what a working artifact does."""
    p = t.properties
    if p.get("windcatcher"):
        return ("Stores Jodebris to power artifacts in the miasma. "
                "Equip it (e) to carry it on a hunt.")
    parts = []
    if "light" in p:
        parts.append(f"Light +{p['light']} in dark places")
    for stat, label in (("armor", "Armour"), ("accuracy", "Accuracy"), ("evasion", "Evasion")):
        if stat in p:
            parts.append(f"{label} +{p[stat]}")
    for key, n in p.get("bonus", {}).items():    # (v0.101.0)
        parts.append(bonus_words(key, n))
    if p.get("effect"):                          # anything else it does, in words (v0.98.0: fishing artifacts)
        parts.append(p["effect"])
    lasting = bool(parts)
    if p.get("use") in USE_TEXT:
        each = (" between hunts" if p.get("uses_per_hunt", 1) > 1 else ", once between hunts") if p["use"] == "unrest" else "/hunt"
        n = "" if p["use"] == "unrest" and p.get("uses_per_hunt", 1) == 1 else f", {p.get('uses_per_hunt', 1)}"
        parts.append(f"Use: {USE_TEXT[p['use']](p)}{n}{each}" + (f", costing {p['hp_cost']} HP" if p.get("hp_cost") else ""))
    text = ". ".join(parts) + "." if parts else ""
    if p.get("use") == "unrest" and not lasting:
        pass                                     # (off a hunt: no Jodebris to speak of)
    elif p.get("use"):
        text += (" Its uses carry their own Jodebris: no windcatcher needed for them." if not lasting
                 else " Its uses need no windcatcher; the rest needs one in the miasma.")
    elif lasting:
        text += " Needs a windcatcher in the miasma."
    return text


def _a(name: str) -> str:
    return ("an " if name[0].lower() in "aeiou" else "a ") + name


# ---- Workshops (data/workshops.json) ---------------------------------------------------------

@dataclass(frozen=True)
class Workshop:
    id: str
    name: str
    keeper: str
    greeting: str
    trains: tuple[str, ...]
    sells: tuple = ()   # stock entries (see game/stock.py)


def load_workshops(path) -> dict[str, Workshop]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {wid: Workshop(wid, d["name"], d.get("keeper", "the artificer"), d.get("greeting", ""),
                          tuple(d.get("trains", ())), tuple(d.get("sells", ())))
            for wid, d in raw.items() if not wid.startswith("_")}
