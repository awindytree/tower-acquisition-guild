"""The Medicine skill: bandages and poultices used in the field (see game/injuries.py).

A bandage stops bleeding; a poultice stops poison. From MEND_MINOR_RANK, a
bandage also mends a minor injury outright. Each try uses the item and a
turn, and may fail; the chance rises with rank. Every try is practice.
"""
from __future__ import annotations

from game import injuries
from game.skills import add_practice, gain_for

SKILL = "medicine"
BASE_CHANCE = 50       # % at rank 1
PER_RANK = 10          # % per rank above 1
MAX_CHANCE = 95
MEND_MINOR_RANK = 2    # from this rank, a bandage mends a minor injury outright


def chance(player) -> int:
    return min(MAX_CHANCE, BASE_CHANCE + PER_RANK * (player.skill(SKILL).rank - 1))


def target(player, treats: str):
    """The injury this item would be used on: one bleeding/poisoning first, then (bandages,
    at rank) a minor injury. None if there's nothing it can help."""
    t = injuries.table()
    running = [i for i in player.injuries if i.dot_left > 0 and t[i.id].dot["kind"] == treats]
    if running:
        return running[0]
    if treats == "bleeding" and player.skill(SKILL).rank >= MEND_MINOR_RANK:
        minor = [i for i in player.injuries if t[i.id].severity == "minor"]
        if minor:
            return minor[0]
    return None


def use(engine, index: int) -> bool:
    """Use the bandage or poultice at inventory `index`. Returns whether a turn passed."""
    p = engine.player
    item = p.inventory.items[index]
    treats = item.type.properties["treats"]
    inj = target(p, treats)
    if inj is None:
        if treats == "bleeding":
            engine.log("You're not bleeding." + (" Nothing else a bandage can help with." if p.injuries else ""))
        else:
            engine.log("You're not poisoned.")
        return False
    it = injuries.table()[inj.id]
    p.inventory.remove(index, 1)
    success = engine.rng.randint(1, 100) <= chance(p)
    if not success:
        engine.log(f"You try to see to your {it.name} with the {item.type.name}, but make a poor job of it.")
    elif it.severity == "minor" and treats == "bleeding" and p.skill(SKILL).rank >= MEND_MINOR_RANK:
        injuries.remove(p, inj.id)
        engine.log(f"You bind up your {it.name}. It will trouble you no more.")
    else:
        inj.dot_left = 0
        engine.log(f"You see to your {it.name}: {'the bleeding stops' if treats == 'bleeding' else 'the poison is drawn out'}.")
    skill = engine.skills[SKILL]
    for message in add_practice(skill, p.skill(SKILL), gain_for(skill, p) * (2 if success else 1)):
        engine.log(message)
    return True
