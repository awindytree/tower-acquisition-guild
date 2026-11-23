"""Recovery contracts (roadmap step 4, part 2; user, 2026-11-22).

"Go out and recover a lost Hunter's pack, and they're added to the Hall of Hunters." Three kinds of
lost Hunter (user: all three):
- one of your own fallen Hunters (`own`): their pack is what they carried when they fell, and lies
  in the area where they fell;
- a rival from the cast who died out there (`rival`);
- a Hunter invented for the contract (`invented`), so there's work even if nobody you know has died.

World state: `engine.lost`, a list of records (saved as `world.lost`):
    {id, kind, name, place, area (1-based: the area they fell in), day, items [item entries],
     shards, hall (index into engine.hall, or None), recovered (None or {by, day})}
Own and rival records stay posted on the contracts board until someone brings the pack home.
An invented one is posted for a Cycle (seeded from the Cycle) and joins `engine.lost` only when it's
recovered (so it can't be done twice).

The pack is the contract's prize (item `lost_pack`), at the far end of the area they fell in.
Bringing it home: the Guild puts what was in it in the guild stash (anything carried between Hunters
goes through a persistent place), pays a small fee (Guild pay: no dues), and remembers the Hunter
in the Hall of Hunters: a new entry for an invented one, a note on the entry for the others.
All numbers are the assistant's placeholders.
"""
from __future__ import annotations

import random
import zlib

PACK = "lost_pack"
MAX_POSTED = 2            # own and rival records on the board at once (oldest first)
INVENTED_CHANCE = 0.5     # a Cycle with an invented recovery posted
MAX_ITEMS = 20            # entries kept from a fallen Hunter's pack
FEE_BASE, FEE_PER_DANGER = 15, 10
DANGER_WEIGHTS = {1: 4, 2: 3, 3: 2, 4: 1.5, 5: 1}   # an invented Hunter's place (the bounty board's spread)
LEFT_OUT = ("key", "trophy")   # kinds that don't go into a lost pack (story items go to the stash anyway)


def empty() -> list:
    return []


def _danger(engine, place: str) -> int:
    return engine.regions[place].danger[0]


def _record(engine, kind: str, name: str, place: str, area: int, items: list, shards: int, hall) -> dict:
    n = sum(1 for r in engine.lost if r["kind"] == kind)
    rec = {"id": f"{kind}{n + 1}", "kind": kind, "name": name, "place": place, "area": max(1, area),
           "day": engine.day, "items": items, "shards": shards, "hall": hall, "recovered": None}
    engine.lost.append(rec)
    return rec


# ---- Who's lost -----------------------------------------------------------------------------------------
def on_death(engine, hunt) -> dict | None:
    """The Hunter has fallen out on a hunt (after story items went to the stash): their pack stays
    where they fell. Called before the Hunter is replaced."""
    if hunt is None or not hunt.contract.region.place or hunt.contract.region.id not in engine.regions:
        return None
    p = engine.player
    items = []
    for it in p.all_items():
        if it.type.kind in LEFT_OUT or it.type.properties.get("no_drop") or it.type.id in (PACK, "shard"):
            continue
        items.append(it.to_entry())
    return _record(engine, "own", p.full_name, hunt.contract.region.id, hunt.current + 1,
                   items[:MAX_ITEMS], p.shards, len(engine.hall) - 1 if engine.hall else None)


def contents(engine, place: str, rng: random.Random) -> tuple[list, int]:
    """What a Hunter you didn't play had on them: shards, a few supplies, perhaps a broken artifact."""
    from game.hunt import pick_artifact
    danger = _danger(engine, place)
    items = []
    for item_id, lo, hi in (("healing_draught", 0, 2), ("ration", 1, 3), ("torch", 0, 2), ("rope", 0, 1)):
        n = rng.randint(lo, hi)
        if n and item_id in engine.catalogue.types:
            items.append([item_id, n])
    if rng.random() < 0.4:
        items.append([pick_artifact(engine.regions[place], danger, engine.catalogue, rng), 1])
    return items, rng.randint(10, 30) * danger


def rival_lost(engine, r: dict, trip: dict) -> dict | None:
    """A rival died out there (rivals.come_home): their pack lies in the deepest area of the trip."""
    place = trip.get("region")
    if place not in engine.regions or not engine.regions[place].place:
        return None
    from game import rivals
    rng = random.Random(zlib.crc32(f"lost-rival/{r['id']}/{engine.day}".encode()))
    items, shards = contents(engine, place, rng)
    return _record(engine, "rival", rivals.full_name(r), place, trip.get("depth", 1), items, shards,
                   len(engine.hall) - 1)


def invented(engine, day: int) -> dict | None:
    """This Cycle's invented recovery, if there is one and it isn't done (not added to engine.lost)."""
    cycle = day // engine.calendar.per_cycle
    rid = f"invented-c{cycle}"
    if any(r["id"] == rid for r in engine.lost):
        return None
    rng = random.Random(zlib.crc32(f"lost-invented/{cycle}".encode()))
    if rng.random() >= INVENTED_CHANCE:
        return None
    from game import keywords, named, rivals
    danger = rng.choices(list(DANGER_WEIGHTS), list(DANGER_WEIGHTS.values()))[0]
    region = keywords.random_place(engine, danger, rng)
    from game.hunt import depth_of
    area = rng.randint(1, depth_of(region, danger))
    given = named.maker().given_name(rng)
    calling = rng.choice(rivals.settings()["callings"])
    items, shards = contents(engine, region.id, rng)
    return {"id": rid, "kind": "invented", "name": f"{given} {calling} Hunters", "place": region.id, "area": area,
            "day": day - rng.randint(9, 81), "items": items, "shards": shards, "hall": None, "recovered": None,
            "level": max(1, danger * 2 - rng.randint(0, 2)), "hunts": rng.randint(2, 6 + 6 * danger),
            "age_seed": rng.getrandbits(32)}


# ---- The board ------------------------------------------------------------------------------------------
def contract_for(engine, rec: dict):
    from game.hunt import Contract
    region = engine.regions[rec["place"]]
    return Contract(region, PACK, _danger(engine, rec["place"]), rec["area"],
                    zlib.crc32(f"lost/{rec['id']}".encode()), recover=dict(rec))


def postings(engine) -> list:
    """Recovery contracts on the Guild's board today: the oldest lost packs, then an invented one."""
    out = [contract_for(engine, r) for r in engine.lost
           if r["recovered"] is None and r["kind"] != "invented" and r["place"] in engine.regions][:MAX_POSTED]
    inv = invented(engine, engine.day)
    if inv is not None:
        out.append(contract_for(engine, inv))
    return out


def owner(name: str) -> str:
    """'Xonil Fencer Hunters' -> "Xonil Fencer Hunters'" (every Hunter's surname ends in s)."""
    return name + ("'" if name.endswith("s") else "'s")


def whose(rec: dict) -> str:
    return {"own": "one of your own Hunters", "rival": "a Hunter of the hall",
            "invented": "a Hunter you never met"}.get(rec["kind"], "a Hunter")


def title(rec: dict) -> str:
    return f"Bring home {rec['name']}"


def describe(engine, c) -> str:
    rec = c.recover
    area = f"area {rec['area']}" if c.depth > 1 else "the only area"
    return (f"{rec['name']}, {whose(rec)}, went out to {c.region.name} and never came back. Their pack should "
            f"still lie in {area}. Bring it home: the Guild keeps what was in it in the stash for whoever "
            f"comes after, and puts their name in the Hall of Hunters.")


def fee(c) -> int:
    return FEE_BASE + FEE_PER_DANGER * c.danger


# ---- Home with it ---------------------------------------------------------------------------------------
def complete(engine, c) -> list[str]:
    """The pack is home (finish_hunt, on success). Returns lines for the card."""
    from game.items import Item
    p = engine.player
    rec = c.recover
    for i, it in enumerate(list(p.inventory.items)):     # the pack goes to the Guild
        if it.type.id == PACK:
            p.inventory.remove(i, 1)
            break
    stashed, kept, lost = [], [], []
    for entry in rec.get("items", []):
        try:
            item = Item.from_entry(entry, engine.catalogue)
        except KeyError:
            continue
        if engine.stash.add(item):
            stashed.append(item)
        elif p.inventory.add(item):
            kept.append(item)
        else:
            lost.append(item)
    shards = rec.get("shards", 0)
    pay = fee(c)
    p.guild_pay(pay + shards)
    # The Hall of Hunters
    note = {"by": p.full_name, "day": engine.day}
    real = next((r for r in engine.lost if r["id"] == rec["id"]), None)
    if real is not None:
        real["recovered"] = note
        if real.get("hall") is not None and real["hall"] < len(engine.hall):
            engine.hall[real["hall"]]["recovered"] = note
    else:                                                   # an invented Hunter: remembered from now on
        from game import aging, ranks
        rng = random.Random(rec.get("age_seed", 0))
        rec = dict(rec, recovered=note, hall=len(engine.hall))
        rec.pop("age_seed", None)
        engine.lost.append(rec)
        names = [r["name"] for r in ranks.table()]
        engine.hall.append({"name": rec["name"], "rank": names[min(len(names) - 1, c.danger // 2)] if names else "",
                            "age": aging.roll_age(rng), "level": rec.get("level", 1), "hunts": rec.get("hunts", 0),
                            "joined": rec["day"] - rng.randint(200, 2000), "ended": rec["day"],
                            "cause": f"lost in {c.region.name}", "recovered": note})
    lines = [f"You bring {owner(rec['name'])} pack home.",
             f"The Guild pays {pay} shards for the recovery" + (f", and the {shards} shards in it are yours." if shards else ".")]
    if stashed:
        lines.append("The rest goes into the guild stash: " + ", ".join(i.label for i in stashed) + ".")
    if kept:
        lines.append("The stash is full, so you keep " + ", ".join(i.label for i in kept) + ".")
    if lost:
        lines.append("There's no room for " + ", ".join(i.label for i in lost) + ": the Guild lets it go.")
    lines.append(f"{rec['name']} is remembered in the Hall of Hunters.")
    engine.log(f"You bring {owner(rec['name'])} pack home. The Guild pays {pay + shards} shards.")
    return lines


def hall_line(entry: dict, engine) -> str:
    r = entry.get("recovered")
    if not r:
        return ""
    return f" Their pack was brought home by {r['by']} on {engine.calendar.date(r['day']).short}."
