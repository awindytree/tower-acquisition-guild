"""Bargaining (v0.59.0; design: claude/design-progression.md, stage 5): better prices with the supplier
and the artificer, 3% a rank above 1, both ways (you pay less, they pay more; the artificer's repair
fees too). Governed by Acumen; trained by the supplier. Practice: every trade. Placeholders.
"""
from __future__ import annotations

import math

SKILL = "bargaining"
STEP = 0.03


def rank(player) -> int:
    if player is None:
        return 1
    try:
        return player.skill(SKILL).rank
    except KeyError:
        return 1


def pay(player, price: int) -> int:
    """What you pay for something listed at `price`."""
    if price <= 0:
        return price
    return max(1, math.ceil(price * (1 - STEP * (rank(player) - 1)) - 1e-9))


def paid(player, price: int) -> int:
    """What you're paid for something worth `price` to them."""
    if price <= 0:
        return price
    return int(price * (1 + STEP * (rank(player) - 1)) + 1e-9)


def practise(engine) -> None:
    from game import skills
    if SKILL not in engine.skills:
        return
    sk = engine.skills[SKILL]
    for msg in skills.add_practice(sk, engine.player.skill(SKILL), skills.gain_for(sk, engine.player)):
        engine.log(msg)


def sheet_lines(engine, skill_id: str) -> list[str]:
    if skill_id != SKILL:
        return []
    r = rank(engine.player)
    return [f"The supplier and the artificer give you {round(STEP * 100 * (r - 1))}% better prices, both ways."]
