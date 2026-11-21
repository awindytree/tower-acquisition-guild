"""Corpses and trophies (v0.61.0; user, design-progression.md stage 6b).

A creature leaves its corpse where it dies (almost always: not one that bursts, like the lantern
tick, nor a ghost). It's up to the Hunter what to do with it:

- leave it;
- butcher it there (b) for materials, the creature's drops (monsters.json), as loose drops used to
  be: Harvesting makes them likelier and more;
- pick it up (g): in the pack it's a trophy, not a corpse, and takes slots by its size. Trophies
  don't spoil.

Back in Bytorsskug the trophymaster keeps the records, like a fishing contest: the heaviest of
each creature, and the first of each quirk (a curiosity). A record goes on the trophy wall and pays
shards, more for a bigger margin and a tougher creature; anything else he turns away. The butcher
breaks a trophy down for nothing, and surely: every material it has, at the most.

Records are world state (the wall outlives Hunters, and names who set each one). Trophies are
things in a pack, so they're lost with a Hunter like anything else they carry.
Everything in data/trophies.json is a placeholder.
"""
from __future__ import annotations

import json
import random
from functools import lru_cache

from game.engine import DATA

GLYPH = "%"


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads((DATA / "trophies.json").read_text(encoding="utf-8"))


def type_id(monster_id: str) -> str:
    return f"trophy_{monster_id}"


def leaves_corpse(mtype) -> bool:
    """A lantern tick bursts; an ashmantle is smoke. Everything else leaves a body."""
    return not (mtype.burst or mtype.ghost)


def profile(mtype) -> dict:
    """The creature's weight and size (a made-up one if trophies.json doesn't list it)."""
    c = data()["creatures"].get(mtype.id)
    if c:
        return c
    return {"kg": [max(0.5, mtype.hp * 2.5), 0.12], "slots": min(6, 1 + mtype.tier)}


def register(catalogue, monster_types: dict) -> None:
    """Add a trophy item type for every creature that leaves a corpse (once per catalogue)."""
    from game.items import ItemType
    for mid, t in monster_types.items():
        tid = type_id(mid)
        if not leaves_corpse(t) or tid in catalogue.types:
            continue
        dim = tuple(int(c * 0.75) for c in t.color)
        catalogue.types[tid] = ItemType(
            id=tid, real_name=f"{t.name} trophy", glyph=GLYPH, color=dim, kind="trophy",
            real_description=(f"The body of a {t.name}, hauled whole. The trophymaster in Bytorsskug pays for "
                              "a record; the butcher will break it down into materials. Or butcher it yourself (u)."),
            properties={"monster": mid, "slots": profile(t)["slots"]})


# ---- Weights and names ---------------------------------------------------------------------
def weight_text(kg: float) -> str:
    return f"{round(kg * 1000)} g" if kg < 1 else f"{kg:.1f} kg"


def quirk_name(qid: str) -> str:
    return data()["quirks"].get(qid, {}).get("name", qid)


def _creature(item) -> str:
    return item.type.real_name.removesuffix(" trophy")


def label(item) -> str:
    """In the pack: 'crawler trophy (70.2 kg)', 'pale wild dog trophy (24.8 kg)'."""
    q = item.trophy.get("quirk", "")
    return f"{quirk_name(q) + ' ' if q else ''}{item.type.real_name} ({weight_text(item.trophy['kg'])})"


def corpse_label(item) -> str:
    """On the ground: 'crawler corpse'."""
    q = item.trophy.get("quirk", "")
    return f"{quirk_name(q) + ' ' if q else ''}{_creature(item)} corpse"


def make(engine, mtype, rng=random):
    """A fresh corpse of this creature, its weight and any quirk rolled."""
    from game.items import Item
    d, prof = data(), profile(mtype)
    mean, spread = prof["kg"]
    f = min(d["weight"]["high"], max(d["weight"]["low"], rng.gauss(1.0, spread)))
    quirk = ""
    if rng.random() < d["quirk_chance"]:
        quirk = rng.choice(sorted(d["quirks"]))
        f *= {"runt": 0.75, "old": 1.08}.get(quirk, 1.0)
    kg = round(mean * f, 3 if mean * f < 1 else 1)
    return Item(engine.catalogue[type_id(mtype.id)], trophy={"kg": kg, "quirk": quirk})


def leave_corpse(engine, monster, rng=random) -> None:
    """A creature has died: its body falls where it died (or, in water, on the nearest bank)."""
    from game.items import FloorItem
    if not leaves_corpse(monster.type) or type_id(monster.type.id) not in engine.catalogue.types:
        return
    gm = engine.game_map
    x, y = monster.x, monster.y
    if not gm.tile_at(x, y).walkable:          # an eel in the water, a glasswing over it
        p = engine.player
        cells = [(x + dx, y + dy) for dx in range(-3, 4) for dy in range(-3, 4)
                 if gm.in_bounds(x + dx, y + dy) and gm.tile_at(x + dx, y + dy).walkable]
        if not cells:
            return
        x, y = min(cells, key=lambda c: (abs(c[0] - x) + abs(c[1] - y), abs(c[0] - p.x) + abs(c[1] - p.y)))
    gm.items.append(FloorItem(x, y, make(engine, monster.type, rng)))
    p = engine.player
    from game import story
    if "seen_corpse" not in p.flags:
        p.flags.add("seen_corpse")
        if getattr(engine, "story", None) and story.holds(engine, "quest", "first_jobs"):
            return                              # the first jobs explain it in a popup
        engine.log(f"The {monster.name} leaves its corpse. Pick it up (g) to haul it home as a trophy, "
                   "or butcher it here (b) for materials.")


# ---- Butchering ----------------------------------------------------------------------------
def materials(engine, mtype, rng=random, sure: bool = False) -> list[tuple[str, int]]:
    """What a body gives up. In the field each material is a chance (Harvesting makes it likelier,
    and more of it); the butcher gets every one, at the most (sure)."""
    from game import fieldskills
    out = []
    if sure:
        return [(item_id, high) for item_id, chance, low, high in mtype.drops]
    bonus, extra = fieldskills.drop_chance_bonus(engine), fieldskills.extra_count(engine)
    for item_id, chance, low, high in mtype.drops:
        if rng.random() < chance + bonus:
            out.append((item_id, rng.randint(low, high) + extra))
    return out


def _hand_over(engine, got) -> list[str]:
    from game.items import FloorItem, Item
    p, names = engine.player, []
    for item_id, n in got:
        item = Item(engine.catalogue[item_id], n)
        if not p.inventory.add(item):
            engine.game_map.items.append(FloorItem(p.x, p.y, item))
        names.append(item.label)
    return names


def _say_got(names) -> str:
    from game.actions import article
    return ", ".join(article(n) for n in names[:-1]) + (" and " if len(names) > 1 else "") + article(names[-1])


def butcher(engine, item, rng=random) -> str:
    """Butcher a body in the field (one on the ground, or a trophy from the pack, already taken
    out of it). The materials go in the pack, or at your feet if there's no room."""
    from game import fieldskills
    mtype = engine.monster_types[item.type.properties["monster"]]
    got = materials(engine, mtype, rng)
    fieldskills.practise(engine, "harvesting")
    from game import sound
    sound.play("butcher")
    if not got:
        return f"You butcher the {_creature(item)}, but there's nothing on it worth keeping."
    return f"You butcher the {_creature(item)}: {_say_got(_hand_over(engine, got))}."


def butcher_at_shop(engine, index: int) -> str:
    """The butcher breaks a trophy down for you, for nothing: every material, at the most."""
    item = engine.player.inventory.remove(index)
    mtype = engine.monster_types[item.type.properties["monster"]]
    got = materials(engine, mtype, sure=True)
    from game import sound
    sound.play("butcher")
    if not got:
        return f"The butcher turns the {_creature(item)} over. \"Nothing on this worth the knife.\" He keeps it anyway."
    return f"The butcher breaks down the {_creature(item)}: {_say_got(_hand_over(engine, got))}."


def corpses_here(engine) -> list:
    p = engine.player
    return [f for f in engine.game_map.items_at(p.x, p.y) if f.item.trophy is not None]


def butcher_here(engine) -> bool:
    """b: butcher the corpse you're standing on. Takes a turn."""
    here = corpses_here(engine)
    if not here:
        engine.log("There's no corpse here to butcher.")
        return False
    f = here[-1]
    engine.game_map.items.remove(f)
    engine.log(butcher(engine, f.item, engine.rng))
    return True


# ---- The trophymaster and the wall (world state) -------------------------------------------
def fresh() -> dict:
    return {"records": {}, "curios": {}}


def state(engine) -> dict:
    if not getattr(engine, "trophies", None):
        engine.trophies = fresh()
    return engine.trophies


def _line(kind: str, rng, **values) -> str:
    if "holder" in values:              # "Hunters'" rather than "Hunters's"
        h = values["holder"]
        values["holder_s"] = h + ("'" if h.endswith("s") else "'s")
    return rng.choice(data()["lines"][kind]).format(**values).strip()


def assess(engine, index: int, rng=random) -> tuple[bool, str]:
    """Hand the trophy at this pack index to the trophymaster. A record (the heaviest of its kind,
    or the first of its quirk) goes up on the wall and pays; anything else stays in the pack."""
    p = engine.player
    item = p.inventory.items[index]
    mid, kg, quirk = item.type.properties["monster"], item.trophy["kg"], item.trophy.get("quirk", "")
    mtype = engine.monster_types[mid]
    st, d = state(engine), data()
    base = d["pay"]["base"][min(mtype.tier, len(d["pay"]["base"]) - 1)]
    rec = st["records"].get(mid)
    creature = mtype.name
    said, pay = [], 0
    heavier = rec is None or kg > rec["kg"]
    curio = bool(quirk) and quirk not in st["curios"].get(mid, {})
    if heavier:
        if rec is None:
            pay += base
            said.append(_line("first", rng, creature=creature, weight=weight_text(kg)))
        else:
            share = (kg - rec["kg"]) / rec["kg"]
            pay += round(base * min(d["pay"]["most"], 1 + d["pay"]["per_margin"] * share))
            extra = _line("big" if item.slots >= 4 else "small", rng)
            said.append(_line("record", rng, creature=creature, weight=weight_text(kg), extra=extra,
                              holder=rec["who"], old=weight_text(rec["kg"]), margin=weight_text(kg - rec["kg"])))
        st["records"][mid] = {"kg": kg, "who": p.full_name, "day": engine.day, "quirk": quirk}
    if curio:
        pay += round(base * d["pay"]["curio"])
        said.append(_line("curio", rng, creature=creature, quirk=quirk_name(quirk)))
        st["curios"].setdefault(mid, {})[quirk] = p.full_name
    if not pay:
        return False, _line("reject", rng, creature=creature, weight=weight_text(kg),
                            holder=rec["who"], old=weight_text(rec["kg"]))
    p.inventory.remove(index)
    p.earn(pay)
    from game import sound
    sound.play("record")
    return True, " ".join(said) + f" He pays you {pay} shards."


def wall_lines(engine) -> list[str]:
    """The trophy wall: each record, heaviest first by creature tier, then the curiosities."""
    st = state(engine)
    if not st["records"]:
        return ["Hooks and bare boards. Nobody has brought the trophymaster a record yet."]
    out = ["The records:"]
    order = sorted(st["records"], key=lambda m: (-engine.monster_types[m].tier, engine.monster_types[m].name)
                   if m in engine.monster_types else (0, m))
    for mid in order:
        r = st["records"][mid]
        name = engine.monster_types[mid].name if mid in engine.monster_types else mid
        out.append(f"{name[0].upper() + name[1:]}: {weight_text(r['kg'])}, {r['who']}")
    curios = [(mid, q, who) for mid, qs in st["curios"].items() for q, who in qs.items()]
    if curios:
        out += ["", "Curiosities:"]
        for mid, q, who in sorted(curios):
            name = engine.monster_types[mid].name if mid in engine.monster_types else mid
            out.append(f"A {quirk_name(q)} {name}: {who}")
    return out


def pack_trophies(engine) -> list[int]:
    return [i for i, it in enumerate(engine.player.inventory.items) if it.trophy is not None]



# ---- Other Hunters bring trophies too (v0.64.0, user) -----------------------------------------------
RIVAL_CHANCE = 0.35        # a successful rival hauls a body home this often (placeholder)


def rival_trophy(engine, who: str, trip: dict, rng=random) -> str:
    """A rival home from a hunt may bring the trophymaster a body: a creature of the place they went
    (one that lives there and is no tougher than its deepest area allows). If it makes a record it
    goes on the wall with their name. Returns what to say about it ("" if nothing came of it)."""
    from game import monsters
    if rng.random() >= RIVAL_CHANCE or trip.get("region") not in engine.regions:
        return ""
    place = engine.regions[trip["region"]]
    cap = monsters.tier_cap(trip.get("danger", 1), max(0, trip.get("depth", 2) - 1))
    kinds = sorted((m for m in engine.monster_types.values()
                    if leaves_corpse(m) and m.tier <= cap and m.lives(place.style, place.light)
                    and type_id(m.id) in engine.catalogue.types), key=lambda m: m.id)
    if not kinds:
        return ""
    mtype = rng.choice(kinds)
    item = make(engine, mtype, rng)
    kg, quirk = item.trophy["kg"], item.trophy["quirk"]
    st = state(engine)
    rec = st["records"].get(mtype.id)
    said = []
    if rec is None or kg > rec["kg"]:
        st["records"][mtype.id] = {"kg": kg, "who": who, "day": engine.day, "quirk": quirk}
        said.append(f"set the trophy wall's record for a {mtype.name} ({weight_text(kg)})")
    if quirk and quirk not in st["curios"].get(mtype.id, {}):
        st["curios"].setdefault(mtype.id, {})[quirk] = who
        said.append(f"brought the trophymaster the first {quirk_name(quirk)} {mtype.name}")
    return " and ".join(said) + "." if said else ""
