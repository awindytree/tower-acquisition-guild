"""Guild ranks: earned by hunts and level, sat for at the clerk for a fee (data/ranks.json).

Rank gates which gates' boards are open and how dangerous a contract a Hunter may take,
and brings privileges (cheaper training, better pay for requests, first pick of contracts
over rivals). A Hunter's rank is theirs (Hunter state): a new Hunter starts at the bottom.
Debt: Guild labour works dues off (time passes); still owing when the next dues fall due
costs a rank. Rivals are ranked too (by the same requirements, without the fee).
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def settings() -> dict:
    return json.loads((DATA / "ranks.json").read_text(encoding="utf-8"))


def table() -> list[dict]:
    return settings()["ranks"]


def name(index: int) -> str:
    return table()[max(0, min(index, len(table()) - 1))]["name"]


def of(player) -> dict:
    return table()[max(0, min(player.rank, len(table()) - 1))]


def privilege(player, key: str, default=0):
    return of(player).get(key, default)


def regions(index: int) -> list[str]:
    return table()[index]["regions"]


def max_danger(index: int) -> int:
    return table()[index]["max_danger"]


def lowest_rank_for_region(region_id: str) -> int:
    return next((i for i, r in enumerate(table()) if region_id in r["regions"]), len(table()) - 1)


def lowest_rank_for_danger(danger: int) -> int:
    return next((i for i, r in enumerate(table()) if r["max_danger"] >= danger), len(table()) - 1)


# ---- Rising -------------------------------------------------------------------------------------------
def next_rank(player) -> dict | None:
    return table()[player.rank + 1] if player.rank + 1 < len(table()) else None


def needs(player) -> list[str]:
    """What the Hunter still needs for the next rank (empty when they can sit for it)."""
    nxt = next_rank(player)
    if nxt is None:
        return []
    out = []
    if player.hunts_done < nxt["hunts"]:
        left = nxt["hunts"] - player.hunts_done
        out.append(f"{left} more completed hunt{'s' if left != 1 else ''}")
    if player.stats.level < nxt["level"]:
        out.append(f"level {nxt['level']}")
    return out


def ready(player) -> bool:
    return next_rank(player) is not None and not needs(player)


def sit(engine) -> str:
    """Sit for the next rank (at the clerk): the fee, then the new rank."""
    p = engine.player
    nxt = next_rank(p)
    if nxt is None:
        return "There's no higher rank in the Guild."
    if needs(p):
        return f"You're not ready to sit for {nxt['name']}: you need {' and '.join(needs(p))}."
    if p.shards < nxt["fee"]:
        return f"Sitting for {nxt['name']} costs {nxt['fee']} shards. You have {p.shards}."
    p.shards -= nxt["fee"]
    p.rank += 1
    extra = ""
    if max_danger(p.rank) > max_danger(p.rank - 1):
        extra = f" The Wayfinder will take you to danger {max_danger(p.rank)} now."
    kw = getattr(engine.regions, "keywords", None)
    if kw is not None:   # the Guild teaches a few words with each rank (data/keywords.json rank_words)
        from game import keywords
        new = keywords.learn(engine, kw.rank_words.get(p.rank, []), say=False)
        if new:
            extra += " The Guild teaches you " + " ".join(kw.word(w).shown for w in new) + "."
    return f"You sit for {nxt['name']} and pass. ({nxt['fee']} shards){extra}"


def describe_next(player) -> str:
    nxt = next_rank(player)
    if nxt is None:
        return f"You're a {of(player)['name']}: the highest rank there is."
    reqs = f"{nxt['hunts']} completed hunts and level {nxt['level']}"
    have = f"You have {player.hunts_done} and level {player.stats.level}."
    return f"{nxt['name']} takes {reqs}, and a fee of {nxt['fee']} shards. {have}"


def rank_for(hunts: int, level: int) -> int:
    """A rival's rank: the highest whose requirements they meet."""
    best = 0
    for i, r in enumerate(table()):
        if hunts >= r["hunts"] and level >= r["level"]:
            best = i
    return best


# ---- Gates and boards ------------------------------------------------------------------------------------
def region_closed(player, region_id: str) -> str | None:
    if region_id in regions(player.rank):
        return None
    return name(lowest_rank_for_region(region_id))


def contract_closed(player, contract) -> str | None:
    """Why the Hunter can't take this contract (the rank it's posted for), or None. A story
    contract is posted for the rank its writer gave it; others by their danger."""
    if getattr(contract, "story", ""):
        return name(contract.min_rank) if player.rank < contract.min_rank else None
    if contract.danger <= max_danger(player.rank):
        return None
    return name(lowest_rank_for_danger(contract.danger))


# ---- Debt ---------------------------------------------------------------------------------------------------
def labour_pulses(player) -> int:
    return math.ceil(player.dues_owed / settings()["labour_per_pulse"]) if player.dues_owed > 0 else 0


def labour(engine) -> str:
    """Work off the Guild dues: a Pulse at a time, paying down labour_per_pulse each."""
    p = engine.player
    pulses = labour_pulses(p)
    if not pulses:
        return "You don't owe the Guild anything."
    rate = settings()["labour_per_pulse"]
    paid = 0
    p.labouring = True
    try:
        for _ in range(pulses):
            engine.next_day()
            if engine.passing:
                return "Your years ran out at the work."
            pay = min(rate, p.dues_owed)
            p.dues_owed -= pay
            from game import works
            works.dues_paid(engine, pay)           # (labour pays dues too: the Guild's works)
            paid += pay
            if p.dues_owed <= 0:
                break
    finally:
        p.labouring = False
    cycles, rest = divmod(pulses, engine.calendar.per_cycle)
    took = (f"{cycles} Cycle{'s' if cycles != 1 else ''}" if cycles else "") + \
           (f"{' and ' if cycles and rest else ''}{rest} Pulse{'s' if rest != 1 else ''}" if rest else "")
    left = f" You still owe {p.dues_owed}." if p.dues_owed else " Your dues are paid; the boards are open to you."
    return f"You work for the Guild for {took}, hauling and mending and running errands, and pay off {paid} shards.{left}"
