"""Named creatures (roadmap step 3, v0.83.0).

Now and then a creature out there is one the Guild knows by name: Hunters come back calling that one
dangerous glasswing "Knif the Swift", and the Guild's reports take up the name (user). Mechanically the
name comes from the Starsong given-name generator (user), and the creature has one or two affixes,
like traits for creatures. Its title is its first affix ("Idred the Venomous"); a second goes in front
("Armoured Idred the Venomous", user); a third would only show in the look description.

From danger 2 up, each area has a chance to hold one named creature (NAMED_CHANCE); a feature word can
raise it (Region.named, none yet); a bounty's marked creature is named BOUNTY_CHANCE of the time.
Named creatures give double XP, and their bodies go in their own section of the trophy wall.
Numbers are drafts.
"""
from __future__ import annotations

import random
from pathlib import Path

NAMED_CHANCE = {1: 0.0, 2: 0.05, 3: 0.10, 4: 0.15, 5: 0.20}    # per area, by danger
SECOND_AFFIX = {2: 0.15, 3: 0.25, 4: 0.40, 5: 0.50}
BOUNTY_CHANCE = 0.33
COLOR = (235, 120, 255)            # how a named creature is drawn
VENOM_TURNS = 6                    # Venomous: 1 HP every other turn this long

# id: (title, adjective, what it does)
AFFIXES = {
    "venomous": ("the Venomous", "Venomous", "its hits poison you"),
    "armoured": ("the Armoured", "Armoured", "+2 armour"),
    "swift": ("the Swift", "Swift", "it acts twice a turn"),
    "caller": ("the Caller", "Calling", "when it notices you, it calls everything near"),
    "hulking": ("the Hulking", "Hulking", "half again its health, and +1 damage"),
    "bloodthirsty": ("the Bloodthirsty", "Bloodthirsty", "it heals when it hits you"),
}

_maker = None


def maker():
    global _maker
    if _maker is None:
        from game.names import NameMaker
        _maker = NameMaker(Path(__file__).resolve().parent.parent / "data" / "names.json")
    return _maker


def display(name: str, affixes: list) -> str:
    """'Idred the Venomous'; 'Armoured Idred the Venomous'."""
    if not affixes:
        return name
    out = f"{name} {AFFIXES[affixes[0]][0]}"
    if len(affixes) > 1:
        out = f"{AFFIXES[affixes[1]][1]} {out}"
    return out


NAMES: set[str] = set()      # every named creature's full name met so far (for `fix`)


def fix(text: str) -> str:
    """Messages are written "the wild dog hits you"; a named creature is just "Knif the Swift"
    (v0.86.0: "The Knif the Swift" before). Drops the "the" or "a" in front of any named one's name."""
    if not NAMES or not text:
        return text
    import re
    for n in NAMES:
        if n in text:
            text = re.sub(r"\b(?:[Tt]he|[Aa]n?) " + re.escape(n), n, text)
    return text


def apply(m, name: str, affixes: list, fresh: bool = True) -> None:
    """Make a creature a named one (fresh: also give it its extra health)."""
    m.named, m.affixes = name, list(affixes)
    m.name = display(name, affixes)
    NAMES.add(m.name)
    m.color = COLOR
    if fresh and "hulking" in affixes:
        m.hp = m.type.hp * 3 // 2


def roll(m, rng: random.Random, danger: int) -> None:
    """Make this creature a named one, with one affix (two, sometimes)."""
    ids = sorted(AFFIXES)
    first = ids[rng.randint(0, len(ids) - 1)]
    affixes = [first]
    if rng.random() < SECOND_AFFIX.get(danger, 0):
        rest = [a for a in ids if a != first]
        affixes.append(rest[rng.randint(0, len(rest) - 1)])
    apply(m, maker().given_name(rng), affixes)


def maybe_name(monsters: list, rng: random.Random, danger: int, more: float = 1.0) -> None:
    """An area's creatures: perhaps one of them is named (from danger 2)."""
    chance = NAMED_CHANCE.get(danger, 0.2) * more
    candidates = [m for m in monsters if not m.type.ghost and m.type.behaviour != "still"]
    if candidates and chance and rng.random() < chance:
        roll(candidates[rng.randint(0, len(candidates) - 1)], rng, danger)


def has(m, affix: str) -> bool:
    return affix in getattr(m, "affixes", ())


def call(engine, m) -> None:
    """A Caller (or a creature that calls by nature) has noticed you: everything near wakes and comes."""
    if getattr(m, "called", False):
        return
    m.called = True
    near = [o for o in engine.game_map.monsters if o is not m and not o.awake
            and abs(o.x - m.x) + abs(o.y - m.y) <= 15]
    for o in near:
        o.awake, o.turns_unseen = True, 0
    engine.log(f"The {m.name} lets out a call" + (", and something answers." if near else "."))


def look_lines(m) -> list[str]:
    if not getattr(m, "named", ""):
        return []
    out = [f"The Guild knows this one by name: {m.name}."]
    out += [f"{AFFIXES[a][1]}: {AFFIXES[a][2]}." for a in m.affixes]
    return out
