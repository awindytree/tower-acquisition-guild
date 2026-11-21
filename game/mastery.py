"""Calling bonuses and knowing your prey (v0.59.0; design: claude/design-progression.md, stage 5).
Both the Hunter's own. Placeholders.

- Calling bonuses: when the weapon skill of your calling (the middle name, from the weapon you use
  most) reaches rank 3, a small passive, whatever is in your hand: Fencer +1 evasion, Hewer +1
  damage, Breaker 1 more armour ignored, Archer +2 bow range, Brawler +1 accuracy.
- Knowing your prey: your own kill counts per creature. 10 kills: +1 accuracy against it;
  25: +1 damage too.
"""
from __future__ import annotations

CALLING_RANK = 3
CALLINGS = {   # calling -> (skill, what it gives, the bonus key, how much)
    "Fencer": ("blades", "+1 evasion", "evasion", 1),
    "Hewer": ("axes", "+1 damage", "damage", 1),
    "Breaker": ("hafted", "1 more armour ignored", "pierce", 1),
    "Archer": ("marksmanship", "+2 bow range", "range", 2),
    "Brawler": ("brawling", "+1 accuracy", "accuracy", 1),
}
PREY_ACCURACY, PREY_DAMAGE = 10, 25


def calling_bonus(player, key: str) -> int:
    """The calling's bonus of this kind, if the calling's skill is at rank 3 or more."""
    from game import names
    c = CALLINGS.get(names.calling(player))
    if not c or c[2] != key:
        return 0
    skill, _, _, amount = c
    try:
        return amount if player.skill(skill).rank >= CALLING_RANK else 0
    except KeyError:
        return 0


def calling_line(player) -> str:
    from game import names
    calling = names.calling(player)
    c = CALLINGS.get(calling)
    if not c:
        return f"{calling}: no calling bonus."
    skill, what, _, _ = c
    have = player.skill(skill).rank >= CALLING_RANK
    return (f"{calling}: {what}." if have else
            f"{calling}: {what} once your {skill.capitalize()} reaches rank {CALLING_RANK}.")


def note_kill(player, monster_type_id: str) -> None:
    player.prey[monster_type_id] = player.prey.get(monster_type_id, 0) + 1


def prey_bonus(player, monster) -> tuple[int, int]:
    """(accuracy, damage) against a creature of this kind."""
    n = getattr(player, "prey", {}).get(monster.type.id, 0)
    return (1 if n >= PREY_ACCURACY else 0), (1 if n >= PREY_DAMAGE else 0)


def prey_lines(engine) -> list[tuple[str, int, str]]:
    """(creature name, kills, what you know) for every creature you've killed, most first."""
    p = engine.player
    out = []
    for mid, n in sorted(p.prey.items(), key=lambda kv: -kv[1]):
        mt = engine.monster_types.get(mid)
        if not mt:
            continue
        if n >= PREY_DAMAGE:
            what = "+1 accuracy, +1 damage"
        elif n >= PREY_ACCURACY:
            what = f"+1 accuracy; +1 damage at {PREY_DAMAGE}"
        else:
            what = f"+1 accuracy at {PREY_ACCURACY}"
        out.append((mt.name, n, what))
    return out
