"""Combat rules: dice, hitting, and damage.

One attack:
  1. Hit roll. Chance to hit = 65% + 5% per point of the attacker's accuracy
     above the defender's evasion (or minus, below), kept between 5% and 95%.
     For the player, accuracy and evasion are both Celerity.
  2. Damage = the weapon's dice + a bonus (Physicality for the player),
     minus the defender's armour, but always at least 1.

All the numbers live in the constants and small functions here, so the
feel of combat can be tuned in one place.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass

BASE_HIT = 65      # % chance to hit an equal opponent
HIT_PER_POINT = 5  # % per point of accuracy over evasion
MIN_HIT, MAX_HIT = 5, 95

_DICE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$")


def roll(dice: str, rng: random.Random = random) -> int:
    """Roll dice written like '1d6', '2d4+1' or '1d8-1'."""
    match = _DICE.match(dice)
    if not match:
        raise ValueError(f"Can't read dice {dice!r}; write them like 1d6 or 2d4+1")
    count, sides, bonus = match.groups()
    total = sum(rng.randint(1, int(sides)) for _ in range(int(count)))
    return total + int(bonus.replace(" ", "")) if bonus else total


def average(dice: str) -> float:
    count, sides, bonus = _DICE.match(dice).groups()
    return int(count) * (int(sides) + 1) / 2 + (int(bonus.replace(" ", "")) if bonus else 0)


def hit_chance(accuracy: int, evasion: int) -> int:
    return max(MIN_HIT, min(MAX_HIT, BASE_HIT + HIT_PER_POINT * (accuracy - evasion)))


def attribute_bonus(value: int) -> int:
    """+1 for every 2 points above 10, -1 for every 2 below."""
    return (value - 10) // 2


@dataclass
class AttackResult:
    hit: bool
    damage: int = 0
    killed: bool = False
    crit: bool = False


def resolve(attacker, defender, rng: random.Random = random, accuracy: int = 0, rolls: int = 1,
            damage: int = 0) -> AttackResult:
    """attacker needs .accuracy, .damage_dice, .damage_bonus (and may have .pierce: armour ignored);
    defender needs .evasion, .armor, .take_damage(n) and .is_dead. accuracy: extra for this blow;
    rolls: how many times the damage dice are rolled (a Lunge: 2)."""
    if rng.randint(1, 100) > hit_chance(attacker.accuracy + accuracy, defender.evasion):
        return AttackResult(hit=False)
    armour = max(0, defender.armor - getattr(attacker, "pierce", 0))
    damage = max(1, sum(roll(attacker.damage_dice, rng) for _ in range(rolls)) + attacker.damage_bonus + damage - armour)
    crit = getattr(attacker, "crit", 0) > 0 and rng.randint(1, 100) <= getattr(attacker, "crit", 0)
    if crit:                                     # (Keen Edge, Executioner: double damage)
        damage *= 2
    defender.take_damage(damage)
    return AttackResult(hit=True, damage=damage, killed=defender.is_dead, crit=crit)
