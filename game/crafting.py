"""Materials and commissioned gear.

Creatures leave their corpses where they die; butchered, a corpse gives materials
(MonsterType.drops; game/trophies.py, v0.61.0). A smith makes
gear to order from them (data/recipes.json): the materials and a fee up front,
then the piece is ready after some Pulses; collect it by talking to the smith.

Orders are world state (the smith keeps them). If the Hunter who placed an
order dies, the smith sends the finished piece to the guild stash, so it
passes to the next Hunter like everything else there.
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_ORDERS = 2


@dataclass(frozen=True)
class Recipe:
    item: str
    materials: tuple[tuple[str, int], ...]
    fee: int
    pulses: int


def load_recipes(path, catalogue) -> dict[str, list[Recipe]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for crafter, recipes in raw.items():
        if crafter.startswith("_"):
            continue
        out[crafter] = []
        for r in recipes:
            catalogue[r["item"]]
            for m in r["materials"]:
                catalogue[m]
            out[crafter].append(Recipe(r["item"], tuple(r["materials"].items()), r["fee"], r["pulses"]))
    return out


@dataclass
class Order:
    id: int
    hunter_id: str
    crafter: str
    item: str
    ready: int        # the day it's ready


def drop_materials(engine, monster, rng=random) -> None:
    """Leave a creature's materials where it fell, loose (as kills did before v0.61.0). Kills now
    leave a corpse instead (game/trophies.py); this is still handy for tests and tools."""
    from game.items import FloorItem, Item
    from game import fieldskills, trophies
    got = trophies.materials(engine, monster.type, rng)
    for item_id, n in got:
        engine.game_map.items.append(FloorItem(monster.x, monster.y, Item(engine.catalogue[item_id], n)))
    if got:
        fieldskills.practise(engine, "harvesting")


def missing(engine, recipe: Recipe) -> list[tuple[str, int, int]]:
    """(item id, have, need) for each material the Hunter is short of."""
    inv = engine.player.inventory
    return [(m, inv.count_of(m), n) for m, n in recipe.materials if inv.count_of(m) < n]


def my_orders(engine, crafter: str | None = None) -> list[Order]:
    hid = engine.player.hunter_id
    return [o for o in engine.orders if o.hunter_id == hid and (crafter is None or o.crafter == crafter)]


def commission(engine, crafter: str, recipe: Recipe) -> tuple[bool, str]:
    p = engine.player
    name = engine.catalogue[recipe.item].name
    if len(my_orders(engine)) >= MAX_ORDERS:
        return False, f"You can have {MAX_ORDERS} orders in at once. Collect one first."
    short = missing(engine, recipe)
    if short:
        what = ", ".join(f"{need - have} more {engine.catalogue[m].label(2)[2:] if need - have > 1 else engine.catalogue[m].name}"
                         for m, have, need in short)
        return False, f"For the {name} you need {what}."
    if p.shards < recipe.fee:
        return False, f"The {name} costs {recipe.fee} shards on top of the materials."
    for m, n in recipe.materials:
        left = n
        for i in reversed(range(len(p.inventory.items))):
            it = p.inventory.items[i]
            if left and it.type.id == m:
                took = min(left, it.count)
                p.inventory.remove(i, took)
                left -= took
    p.shards -= recipe.fee
    engine.next_work_id += 1
    order = Order(engine.next_work_id, p.hunter_id, crafter, recipe.item, engine.day + recipe.pulses)
    engine.orders.append(order)
    return True, f"Ordered: a {name}, ready in {recipe.pulses} Pulses."


def ready_orders(engine, crafter: str | None = None) -> list[Order]:
    return [o for o in my_orders(engine, crafter) if o.ready <= engine.day]


def collect(engine, crafter: str | None = None) -> str:
    """Hand over the Hunter's finished orders (to the floor if the pack is full)."""
    from game.items import FloorItem, Item
    p = engine.player
    got = []
    for o in ready_orders(engine, crafter):
        item = Item(engine.catalogue[o.item])
        if not p.inventory.add(item):
            engine.game_map.items.append(FloorItem(p.x, p.y, item))
        engine.orders.remove(o)
        got.append(item.type.name)
    if not got:
        return "Nothing of yours is ready yet."
    return f"You collect your {' and '.join(got)}."


def deliver_orphans(engine) -> None:
    """Finished orders whose Hunter has died go to the guild stash."""
    from game.items import Item
    hid = engine.player.hunter_id
    for o in [o for o in engine.orders if o.hunter_id != hid and o.ready <= engine.day]:
        engine.orders.remove(o)
        engine.stash.add(Item(engine.catalogue[o.item]))
        engine.log(f"The smith has sent a finished {engine.catalogue[o.item].name} to the guild stash: "
                   "its owner never came back for it.")


def orders_to_list(orders) -> list:
    return [asdict(o) for o in orders]


def orders_from_list(data) -> list[Order]:
    return [Order(**d) for d in data]
