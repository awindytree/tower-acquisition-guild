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


def consign_payout(t: ItemType, player=None) -> int:
    """(working sale price - repair fee) / 2, rounded down; never below the broken price; then
    the artificer's +20% (ARTIFICER_PAY)."""
    from game import bargaining
    base = max(t.rarity.broken_price, (t.value - t.rarity.repair_fee) // 2)
    return bargaining.paid(player, int(base * ARTIFICER_PAY))


def repair(player, index: int, catalogue) -> tuple[bool, str]:
    item = player.inventory.items[index]
    t = item.type
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
    was_known = t.identified
    pay = consign_payout(t, player)
    player.inventory.remove(index, 1)
    player.earn(pay)
    from game import sound
    sound.play("pay")
    learn(player, t)
    if stock is not None and catalogue is not None:
        working = catalogue[t.repairs_to]
        stock.add(working.id, working.value)
    found = "" if was_known else f" It turns out to have been {_a(t.real_name)}."
    return True, f"You consign it to the workshop and are paid {pay} shards.{found}"


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
        return [f"Your {w.type.name} falls silent. Your artifacts go still."]
    if before > low >= w.charge:
        return [f"Your {w.type.name}'s hum is fading. It's running low on Jodebris."]
    return []


def refill(player) -> None:
    """Back in the Brisering: every windcatcher fills up again."""
    for item in player.inventory.items:
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
    if effect == "heal":
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
    player.artifact_uses[t.id] = player.artifact_uses.get(t.id, 0) + 1
    from game import attunement
    attunement.practise(engine)                    # (v0.57.0)
    left = uses_left(player, t)
    if left == 0:
        engine.log(f"The {t.name} falls still. It's spent for this hunt.")
    return True


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
    lasting = bool(parts)
    if p.get("use") == "heal":
        parts.append(f"Use: heal {p.get('heal', 0)}, {p.get('uses_per_hunt', 1)}/hunt")
    elif p.get("use") == "reveal":
        parts.append(f"Use: map the area, {p.get('uses_per_hunt', 1)}/hunt")
    text = ". ".join(parts) + "." if parts else ""
    if p.get("use"):
        text += " Its uses carry their own Jodebris" + (": no windcatcher needed for them." if not lasting
                                                       else "; its lasting effects need a windcatcher in the miasma.")
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
