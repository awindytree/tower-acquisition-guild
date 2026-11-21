"""Hunter ages: rolled for each new Hunter, counted in Turns and Judgments.

A Turn is about 16 Earth years and a Judgment about 2; people speak of age in
Turns and Judgments ("my son has seen four Judgments"). A Hunter's birth day
(an absolute Pulse) is fixed when they join; their age follows the calendar.
Past a peak the body declines; the mind grows with the years; very old
Hunters can die of old age. Settings are in data/aging.json.
"""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

from game.calendar import Calendar

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def settings() -> dict:
    return json.loads((DATA / "aging.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def calendar() -> Calendar:
    return Calendar(DATA / "calendar.json")


def judgments_per_turn() -> int:
    c = calendar()
    return c.judgments * len(c.duels)


def to_judgments(turns_judgments) -> int:
    t, j = turns_judgments
    return t * judgments_per_turn() + j


def split(age: int) -> tuple[int, int]:
    """An age in Pulses as (Turns, Judgments)."""
    c = calendar()
    turns, rest = divmod(max(0, age), c.per_turn)
    return turns, min(rest // c.per_judgment, judgments_per_turn() - 1)


def total_judgments(age: int) -> int:
    t, j = split(age)
    return t * judgments_per_turn() + j


def describe(age: int) -> str:
    """'1 Turn, 3 Judgments', '2 Turns', '1 Turn, 1 Judgment'."""
    t, j = split(age)
    parts = []
    if t:
        parts.append(f"{t} Turn{'s' if t != 1 else ''}")
    if j or not t:
        parts.append(f"{j} Judgment{'s' if j != 1 else ''}")
    return ", ".join(parts)


def roll_age(rng: random.Random) -> int:
    """A new Hunter's age, in Pulses."""
    s, c = settings(), calendar()
    lo, hi = (to_judgments(a) for a in s["start_age"])
    js = rng.randint(lo, hi)
    turns, j = divmod(js, judgments_per_turn())
    return turns * c.per_turn + j * c.per_judgment + rng.randrange(c.per_judgment)


def extra_points(age: int) -> int:
    """More attribute points for an older recruit (their life before the Guild)."""
    s = settings()
    youngest = to_judgments(s["start_age"][0])
    return max(0, total_judgments(age) - youngest) // s["extra_point_every"]


def mods(age: int, seed: str = "") -> dict[str, int]:
    """Attribute changes from age: the body past its peak, the mind with the years."""
    s = settings()
    js = total_judgments(age)
    out: dict[str, int] = {}
    lost = max(0, js - to_judgments(s["peak"])) // s["decline_every"]
    body = list(s["body"])
    start = sum(map(ord, seed)) % len(body) if seed else 0   # which goes first differs by Hunter
    for i in range(lost):
        a = body[(start + i) % len(body)]
        out[a] = out.get(a, 0) - 1
    mind_from = to_judgments(s["mind_from"])
    if js >= mind_from:
        gained = min(s["mind_max"], 1 + (js - mind_from) // s["mind_every"])
        for i in range(gained):
            a = s["mind"][i % len(s["mind"])]
            out[a] = out.get(a, 0) + 1
    return out


def age_of(player, day: int) -> int:
    return day - player.born if player.born is not None else player.join_age


# ---- As days pass ---------------------------------------------------------------------------------
def refresh(engine, log: bool = True) -> None:
    """Bring the Hunter's age effects up to date (each new Pulse); log what changed, mark
    new Judgments, and roll for death of old age. Quietly, with log=False (loading, joining)."""
    from game import injuries
    from game.stats import ATTRIBUTES
    p = engine.player
    if p.born is None:
        return
    age = age_of(p, engine.day)
    new = mods(age, p.hunter_id)
    if new != p.age_mods:
        old = p.age_mods
        p.age_mods = new
        injuries.apply_to_stats(p)
        if log:
            names = {a.key: a.name for a in ATTRIBUTES}
            for k in sorted(set(old) | set(new)):
                d = new.get(k, 0) - old.get(k, 0)
                if d:
                    engine.log(f"The years tell: {names.get(k, k)} {d:+d}.")
    js = total_judgments(age)
    if log and js > p.judgments_seen:
        engine.log(f"{p.name} has seen {describe(age)}.")
        s = settings()
        past = js - to_judgments(s["old_age_from"])
        if past >= 0 and engine.rng.random() < s["old_age_chance"] * (past + 1):
            p.judgments_seen = js
            engine.die_of_old_age()
            return
    p.judgments_seen = max(p.judgments_seen, js)


def rest_pulses(player) -> int:
    s = settings()
    from game import fieldskills
    return int((s["rest_pulses"] + s["rest_per_injury"] * len(player.injuries)) * fieldskills.rest_factor(player))


# ---- Retirement and the Hall of Hunters -------------------------------------------------------------
MENTOR_DISCOUNT = 0.75  # the share of the trainer's price a retired Hunter charges, up to their own rank
                        # (user, v0.67.0: 25% off; was half price)


def record(engine, player, cause: str) -> dict:
    """An entry for the Hall of Hunters (world state): who, how old, how far, and how it ended."""
    from game import ranks
    entry = {"name": player.full_name, "rank": ranks.of(player)["name"],
             "age": age_of(player, engine.day), "level": player.stats.level,
             "hunts": player.hunts_done, "joined": player.born + player.join_age if player.born is not None else 0,
             "ended": engine.day, "cause": cause}
    engine.hall.append(entry)
    return entry


def mentor_from(player) -> dict:
    """What a retiring Hunter can teach: their skills above rank 1."""
    return {"name": player.full_name, "given": player.name,
            "skills": {sid: st.rank for sid, st in player.skills.items() if st.rank > 1}}
