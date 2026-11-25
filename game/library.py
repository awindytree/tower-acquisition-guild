"""Writings, Scholarship and the Academy library.

Writings (data/writings.json) turn up on hunts. A Hunter can read one (u)
if their Scholarship rank is up to its difficulty; one rank short, they
can't, but learn from trying. Either way, the Academy librarian takes them
for a nominal payment (more if you've read it), and shelves them: from then
on every Hunter can read it in the library, and it never turns up again.
The library is world state; what a Hunter has read is theirs.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from game.skills import add_practice, gain_for

SKILL = "scholarship"
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "writings.json"


def settings(engine) -> dict:
    if getattr(engine, "_writing_settings", None) is None:
        raw = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
        engine._writing_settings = {k: v for k, v in raw.items() if k not in ("writings", "looks")}
    return engine._writing_settings


def writings(catalogue) -> list:
    return [t for t in catalogue.types.values() if t.writing]


# ---- Reading ----------------------------------------------------------------------------------
def read(engine, item_type) -> tuple[bool, list[str], bool]:
    """Try to read a writing. Returns (took time, messages, show the text)."""
    p = engine.player
    if item_type.id in p.read_writings:
        return False, [], True
    skill = engine.skills[SKILL]
    state = p.skill(SKILL)
    need = item_type.writing["difficulty"]
    if p.studied.get(item_type.id, 0) >= state.rank:
        return False, [f"You've puzzled over the {item_type.name} as far as you can. "
                       f"It needs rank {need} Scholarship."], False
    p.studied[item_type.id] = state.rank
    gain = gain_for(skill, p)
    if need < state.rank:            # v0.52.0 (user: too much from one easy note): easy reading teaches little
        gain = 1
    if need <= state.rank:
        p.read_writings.add(item_type.id)
        p.studied.pop(item_type.id, None)
        teach(engine, item_type)
        return True, [f"You read the {item_type.appearance[0]}: \"{item_type.writing['title']}\"."]\
            + add_practice(skill, state, gain), True
    if need == state.rank + 1:
        return True, [f"You puzzle over the {item_type.name}, but can't make it out. (It needs rank {need} "
                      "Scholarship.) Still, you learn something from trying."] + add_practice(skill, state, gain), False
    return True, [f"You puzzle over the {item_type.name}, but it's far beyond you. "
                  f"(It needs rank {need} Scholarship.)"], False


def teach(engine, item_type) -> list[str]:
    """A writing that names one of the Wayfinder's words teaches it to a Hunter who can read it
    (user, 2026-11-19: only if Scholarship is up to it; most writings are only lore)."""
    words = item_type.writing.get("teaches", []) if item_type.writing else []
    if not words or engine.player.skill(SKILL).rank < item_type.writing["difficulty"]:
        return []
    from game import keywords
    return keywords.learn(engine, words)


# ---- Finding them on hunts --------------------------------------------------------------------
def owned(engine) -> set[str]:
    """Writings someone has: the library's, the Hunter's, the stash's, anything lying in the city
    or in the hunt under way."""
    have = set(engine.library)
    have |= {i.type.id for i in engine.player.inventory.items if i.type.writing}
    have |= {i.type.id for i in engine.stash.items if i.type.writing}
    have |= {f.item.type.id for f in engine.city.items if f.item.type.writing}
    if engine.hunt:
        have |= {w for w in engine.hunt.writings if w}
    return have


def plan_hunt(engine, contract) -> list:
    """Which writing (if any) lies in each area of a new hunt."""
    s = settings(engine)
    rng = random.Random(contract.seed ^ 0x5C401A)
    taken = owned(engine)
    r = contract.region
    where = {r.id, *r.all_styles(), *r.place}     # a writing's "regions" can name a place, a land style or a word
    pool = sorted(t.id for t in writings(engine.catalogue) if t.id not in taken and not t.properties.get("story")
                  and (not t.properties.get("regions") or where & set(t.properties["regions"])))
    chance = min(0.9, s["find_chance"] * getattr(r, "writings", 1.0))   # (the Letters feature: more)
    plan = []
    for _ in range(contract.depth):
        if pool and rng.random() < chance:
            plan.append(pool.pop(rng.randrange(len(pool))))
        else:
            plan.append(None)
    return plan


# ---- The librarian -----------------------------------------------------------------------------
def payment(engine, item_type) -> int:
    s = settings(engine)
    pay = s["pay_per_difficulty"] * item_type.writing["difficulty"]
    return pay * s.get("read_bonus", 2) if item_type.id in engine.player.read_writings else pay


def hand_in(engine) -> str:
    """Hand every writing in the bag to the librarian: paid, and shelved."""
    p = engine.player
    found = [i for i in p.inventory.items if i.type.writing]
    if not found:
        return "You have no writings to hand in."
    total, copies = 0, []
    for item in found:
        if item.type.id in engine.library:      # a copy she has: she takes it, but doesn't pay (v0.100.10, user)
            copies.append(item.type.name)
        else:
            total += payment(engine, item.type)
            engine.library.append(item.type.id)
        p.inventory.items.remove(item)
    if total:
        p.earn(total)
    n = len(found) - len(copies)
    out = []
    if n:
        out.append(f"You hand over {n} writing{'s' if n != 1 else ''} for the library, and are paid {total} shards. "
                   "Any Hunter can read them there now.")
    if len(copies) == 1:
        out.append(f"The library already has a copy of the {copies[0]}: she takes it off your hands, "
                   "but pays nothing for it.")
    elif copies:
        out.append(f"The library already has copies of {len(copies)} of them: she takes those off your hands, "
                   "but pays nothing for them.")
    return " ".join(out)
