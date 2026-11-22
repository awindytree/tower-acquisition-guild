"""The Guild's works (v0.60.0; design: claude/design-progression.md, stage 6a).

The user's design: TAG improves what it thinks needs improving, paid for by dues; the player has a
shred of agency by paying into any project they like (the Guild may be hiring a quartermaster while
you want more stash room: pay toward the stash). Rivals add a trickle, Animal Crossing style. The hall
itself changes; a plaque records who paid. World state: outlasts every Hunter.

data/guildworks.json: projects in the Guild's order of priority, each with tiers {cost, effect,
changes, people}. The Guild's focus is the first unfinished tier in that order; dues paid go to it.

State (engine.works, saved in world): {"done": {project: tiers done}, "progress": {project: shards
toward its next tier}, "givers": {project: {name: shards}} (toward the next tier),
"plaque": [[project, tier, [names...]]]}.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "guildworks.json"
DUES = "the Guild's dues"
RIVALS = "other Hunters"


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def projects() -> dict:
    return data()["projects"]


def fresh() -> dict:
    return {"done": {}, "progress": {}, "givers": {}, "plaque": []}


def state(engine) -> dict:
    if not getattr(engine, "works", None):
        engine.works = fresh()
    return engine.works


def tiers_done(engine, pid: str) -> int:
    return state(engine)["done"].get(pid, 0)


def finished(engine, pid: str) -> bool:
    return tiers_done(engine, pid) >= len(projects()[pid]["tiers"])


def next_tier(engine, pid: str) -> dict | None:
    t = tiers_done(engine, pid)
    tiers = projects()[pid]["tiers"]
    return tiers[t] if t < len(tiers) else None


def focus(engine) -> str | None:
    """The project the Guild is working on: the first unfinished one in its order."""
    return next((pid for pid in projects() if not finished(engine, pid)), None)


def effect_of(works_state: dict | None, key: str) -> int:
    """effect() for a saved works state (loading the stash before the engine has it)."""
    class _E:
        pass
    e = _E()
    e.works = works_state or fresh()
    return effect(e, key)


def effect(engine, key: str) -> int:
    """The sum of an effect over every finished tier (stash_slots, training, healing, mending, rest,
    notes, bestiary_kills, loaner)."""
    total = 0
    for pid, p in projects().items():
        for tier in p["tiers"][: tiers_done(engine, pid)]:
            v = tier.get("effect", {}).get(key)
            if v is not None:
                total = max(total, v) if key in ("stash_slots", "training", "healing", "mending", "rest") else total + v
    return total


def tier_name(pid: str, n: int) -> str:
    """'The stash room' or 'The stash room (II)'."""
    p = projects()[pid]
    numerals = ["I", "II", "III", "IV", "V"]
    return p["name"] + (f" ({numerals[n]})" if len(p["tiers"]) > 1 else "")


def give(engine, pid: str, amount: int, who: str) -> list[str]:
    """Shards toward a project's next tier. Finishing it builds it. Returns log lines."""
    s = state(engine)
    if amount <= 0 or finished(engine, pid):
        return []
    tier = next_tier(engine, pid)
    have = s["progress"].get(pid, 0)
    take = min(amount, tier["cost"] - have)
    s["progress"][pid] = have + take
    givers = s["givers"].setdefault(pid, {})
    givers[who] = givers.get(who, 0) + take
    out = []
    if s["progress"][pid] >= tier["cost"]:
        out += complete(engine, pid)
    left = amount - take
    if left > 0:                       # anything over goes on to whatever the Guild's working on next
        nxt = focus(engine)
        if nxt:
            out += give(engine, nxt, left, who)
    return out


def complete(engine, pid: str) -> list[str]:
    s = state(engine)
    n = tiers_done(engine, pid)
    s["done"][pid] = n + 1
    s["progress"][pid] = 0
    givers = s["givers"].pop(pid, {})
    names = [name for name, _ in sorted(givers.items(), key=lambda kv: -kv[1])]
    s["plaque"].append([pid, n, names])
    apply(engine)
    name = tier_name(pid, n)
    nxt = focus(engine)
    after = f" The Guild turns to {projects()[nxt]['name'].lower()} next." if nxt else ""
    return [f"The Guild's works: {name} is finished!{after}"]


def contribute(engine, pid: str, amount: int) -> tuple[bool, str]:
    """The Hunter pays into a project (at the clerk). Not earnings; owes no dues."""
    p = engine.player
    if finished(engine, pid):
        return False, "That's finished already."
    amount = min(amount, p.shards, next_tier(engine, pid)["cost"] - state(engine)["progress"].get(pid, 0))
    if amount <= 0:
        return False, "You have no shards to give."
    p.shards -= amount
    lines = give(engine, pid, amount, p.full_name)
    for line in lines:
        engine.log(line)
    return True, f"You give {amount} shards toward {projects()[pid]['name'].lower()}."


def dues_paid(engine, amount: int) -> None:
    """Dues paid to the Guild go to its focus."""
    pid = focus(engine)
    if pid and amount > 0:
        for line in give(engine, pid, amount, DUES):
            engine.log(line)


def rival_trickle(engine, rng) -> None:
    """A rival home from a successful hunt adds a little to the Guild's focus (their share of dues)."""
    pid = focus(engine)
    if not pid:
        return
    low, high = data().get("rival_trickle", [2, 6])
    for line in give(engine, pid, rng.randint(low, high), RIVALS):
        engine.log(line)


# ---- The hall --------------------------------------------------------------------------------------
# The finished works' effects, for code that only has a Hunter to hand (training, the healer, mending,
# the archive, the rest after a hunt). Set by apply(), which every engine calls on a new game and a load.
ACTIVE: dict[str, int] = {}
KEYS = ("stash_slots", "training", "healing", "mending", "rest", "notes", "bestiary_kills", "loaner")


def active(key: str) -> int:
    return ACTIVE.get(key, 0)


def apply(engine) -> None:
    """Make the hall match the finished works: tiles and people, and their effects. Safe to call again."""
    ACTIVE.clear()
    ACTIVE.update({k: effect(engine, k) for k in KEYS})
    from game.engine import STASH_SLOTS
    if getattr(engine, "stash", None) is not None:
        engine.stash.capacity = STASH_SLOTS + ACTIVE["stash_slots"]
    city = engine.city
    if city is None or city.hall is None:
        return
    hx, hy = city.hall
    # Put the hall back as built first (a new game, or loading another save, in the same session).
    original = city.__dict__.setdefault("works_original", {})
    people = set()
    for p in projects().values():
        for tier in p["tiers"]:
            for dx, dy, _ in tier.get("changes", []):
                cell = (hx + dx, hy + dy)
                if cell not in original:
                    original[cell] = city.tile_at(*cell).symbol
                city.set_tile(*cell, original[cell])
            people |= {folk for _, _, folk in tier.get("people", [])}
    city.npcs = [n for n in city.npcs if n.folk_id not in people]
    for pid, p in projects().items():
        for tier in p["tiers"][: tiers_done(engine, pid)]:
            for dx, dy, sym in tier.get("changes", []):
                city.set_tile(hx + dx, hy + dy, sym)
            for dx, dy, folk_id in tier.get("people", []):
                place_person(engine, folk_id, hx + dx, hy + dy)
    from game import story                  # the story's people in the hall (v0.67.0)
    city.npcs = [n for n in city.npcs if not ((engine.townsfolk.get(n.folk_id) and
                 (engine.townsfolk[n.folk_id].extra or {}).get("hall_spot")))]
    story.place_folk(engine)


def place_person(engine, folk_id: str, x: int, y: int) -> None:
    from game.entity import NPC
    city = engine.city
    if folk_id not in engine.townsfolk or any(n.folk_id == folk_id for n in city.npcs):
        return
    folk = engine.townsfolk[folk_id]
    city.npcs.append(NPC(x, y, folk.glyph, folk.color, folk.full_name, folk_id=folk_id, home=(x, y), wander=0))


LESSON_FEE = 60


def word_lesson(engine) -> str:
    """The Wayfinder study's scholar teaches a word the Guild doesn't know yet, for a fee (once a Cycle)."""
    import random
    from game import keywords
    p = engine.player
    last = state(engine).get("lesson_day", -999)
    if engine.day - last < 9:
        return "\"Come back in a Cycle. Words don't come that fast.\""
    if p.shards < LESSON_FEE:
        return f"\"{LESSON_FEE} shards, and I'll give you a word.\" You don't have that."
    kw = engine.regions.keywords
    unknown = [w for w in kw.all_ids(ordinary=True) if w not in engine.words and keywords.allowed(engine, kw.word(w))]
    if not unknown:
        return "\"You know every word I could teach you. Come back after your next rank.\""
    word = random.Random(f"lesson/{engine.day}").choice(sorted(unknown))
    p.shards -= LESSON_FEE
    state(engine)["lesson_day"] = engine.day
    keywords.learn(engine, [word], say=False)
    return f"You pay {LESSON_FEE} shards. The scholar teaches you a word for the Wayfinder: {kw.word(word).shown}."


def lend(engine) -> None:
    """The armoury: a new Hunter gets an arming sword (a longbow, if they started with a bow) and a
    studded jerkin, in place of anything worse they were given."""
    from game.items import Item
    p = engine.player
    cat = engine.catalogue
    weapon = p.equipped.get("weapon")
    better_weapon = "longbow" if weapon and weapon.type.properties.get("ammo") else "arming_sword"
    for item_id, slot in ((better_weapon, "weapon"), ("studded_jerkin", "chest")):
        if item_id not in cat.types:
            continue
        old = p.equipped.get(slot)
        new = cat[item_id]
        if old is not None and old.type.value >= new.value:
            continue
        p.equipped[slot] = Item(new)     # (in place of the old one, as before)
    p.gear_changed()
    engine.log("The Guild's armoury lends you better gear to start with.")


def plaque_lines(engine) -> list[str]:
    s = state(engine)
    if not s["plaque"]:
        return ["A brass plaque, polished and empty: it will name those who pay for the Guild's works."]
    out = ["The Guild's works, and who paid for them:"]
    for pid, n, names in s["plaque"]:
        hunters = [x for x in names if x not in (DUES, RIVALS)]
        others = [x for x in names if x in (DUES, RIVALS)]
        who = ", ".join(hunters + others) if names else "the Guild"
        out.append(f"{tier_name(pid, n)}: {who}.")
    return out
