"""Gear tiers (v0.75.0; design: claude/design-equipment.md, stage 1).

Every weapon and armour piece has its own tier, +0 and up with no ceiling (user). Today's pieces
are all +0. Each tier adds one point, alternating (draft numbers):
  * weapons: odd tiers +1 accuracy, even tiers +1 damage (bows: for shots);
  * armour: even tiers +1 armour, odd tiers +2 max HP.
Windcatchers have no tier and take no traits (user). Traits (rolled at +5, +10...) are kept on
the item from now on; the pools and their effects come in stage 3.

Armour goes by slot: head, chest, legs (no armour classes, user). A piece's slot is its `slot`
property; anything without one is chest armour, as everything was before.

Materials: five families in three tiers (data/gear.json); each weapon type and armour slot is
made from two of them. material_bill() is what going to a tier takes (used from stage 2).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "gear.json"

ARMOUR_SLOTS = ("head", "chest", "legs")
SLOTS = ("weapon",) + ARMOUR_SLOTS + ("windcatcher",)
SLOT_NAMES = {"weapon": "Weapon", "head": "Head", "chest": "Chest", "legs": "Legs", "windcatcher": "Windcatcher"}
EMPTY = {"weapon": "bare hands", "head": "nothing", "chest": "nothing", "legs": "nothing", "windcatcher": "none"}
HP_PER_TIER = 2          # armour: max HP on each odd tier


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def families() -> dict[str, list[str]]:
    return data()["families"]


def armour_slot(item_type) -> str:
    """Which armour slot a piece of armour goes in (chest unless it says otherwise)."""
    return item_type.properties.get("slot", "chest")


def has_tier(item) -> bool:
    """Weapons, armour and tackle (v0.96.0) have tiers; windcatchers, artifacts, bait and everything else don't."""
    t = item.type
    if t.kind == "tackle":
        return bool(t.properties.get("tackle_slot"))
    return t.kind in ("weapon", "armor") and not t.properties.get("windcatcher") and not t.rarity


def gear_type(item_type) -> str | None:
    """The weapon type or armour slot that decides an item's materials (data/gear.json)."""
    if item_type.kind == "armor":
        return armour_slot(item_type)
    if item_type.kind == "tackle":                        # rod, reel, line, hook, float (v0.96.0)
        return item_type.properties.get("tackle_slot")
    if item_type.kind != "weapon":
        return None
    props = item_type.properties
    if props.get("gear"):
        return props["gear"]
    for tid, t in data()["types"].items():
        if props.get("ammo") and t.get("ammo") == props["ammo"]:
            return tid
        if t.get("skill") and t.get("skill") == props.get("skill"):
            return tid
    return None


# ---- What a tier gives ------------------------------------------------------------------
def accuracy(item) -> int:
    return (item.tier + 1) // 2 if item is not None and item.type.kind == "weapon" else 0


def damage(item) -> int:
    return item.tier // 2 if item is not None and item.type.kind == "weapon" else 0


def armour(item) -> int:
    return item.tier // 2 if item is not None and item.type.kind == "armor" else 0


def max_hp(item) -> int:
    return HP_PER_TIER * ((item.tier + 1) // 2) if item is not None and item.type.kind == "armor" else 0


def worn_armour(player) -> list:
    return [player.equipped[s] for s in ARMOUR_SLOTS if player.equipped.get(s) is not None]


def armour_total(player) -> int:
    """Armour from the pieces worn: each piece's own, plus its tier's."""
    return sum(i.type.properties.get("armor", 0) + armour(i) for i in worn_armour(player))


def hp_total(player) -> int:
    return sum(max_hp(i) for i in worn_armour(player))


def tier_text(item) -> str:
    """What the tier adds, for the item windows: "+2 accuracy, +1 damage"."""
    if not has_tier(item) or item.tier == 0:
        return ""
    if item.type.kind == "tackle":
        from game import fishing
        return fishing.tier_text(item)
    if item.type.kind == "weapon":
        parts = [(accuracy(item), "accuracy"), (damage(item), "damage")]
    else:
        parts = [(armour(item), "armour"), (max_hp(item), "max HP")]
    return ", ".join(f"+{n} {what}" for n, what in parts if n)


def step_gain(item_type, tier: int) -> str:
    """What reaching this tier adds: "+1 accuracy", "+1 damage", "+2 max HP" or "+1 armour"."""
    if item_type.kind == "tackle":
        from game import fishing
        return fishing.step_gain(item_type, tier)
    if item_type.kind == "weapon":
        return "+1 accuracy" if tier % 2 else "+1 damage"
    return f"+{HP_PER_TIER} max HP" if tier % 2 else "+1 armour"


# ---- Materials ----------------------------------------------------------------------------
def material_bill(item_type, tier: int) -> dict[str, int]:
    """The materials going TO this tier takes (draft): {item id: count}.
    First family, common: 2 + T/2. Second family, common: 1 + T/4.
    First family, uncommon: from +7, 1 + (T-7)/3. First family, rare: from +14, 1 + (T-14)/4."""
    gt = gear_type(item_type)
    if gt is None:
        return {}
    first, second = (families()[f] for f in data()["types"][gt]["families"])
    bill = {first[0]: 2 + tier // 2}
    bill[second[0]] = bill.get(second[0], 0) + 1 + tier // 4
    if tier >= 7:
        bill[first[1]] = 1 + (tier - 7) // 3
    if tier >= 14:
        bill[first[2]] = 1 + (tier - 14) // 4
    return bill


# ---- Upgrading (stage 2, v0.76.0) ------------------------------------------------------------------
HOME_MAX = 3             # what you can do yourself at home (user)


def chance(tier: int) -> int:
    """% chance that going TO this tier works (draft): 100 to +3; 95 falling 5 a tier to 65 at +10;
    62 falling 3 a tier to 35 at +20; then 33 falling 2 a tier, never below 10."""
    if tier <= 3:
        return 100
    if tier <= 10:
        return 95 - 5 * (tier - 4)
    if tier <= 20:
        return 62 - 3 * (tier - 11)
    return max(10, 33 - 2 * (tier - 21))


def destroy_chance(tier: int) -> int:
    """% of failed attempts TO this tier that destroy the piece (draft): none to +20; 5 at +21,
    5 more a tier after, at most 75."""
    return 0 if tier <= 20 else min(75, 5 * (tier - 20))


def shard_cost(tier: int) -> int:
    """The smith's fee for going TO this tier: FEE × T^1.5, rounded to 5. Only paid if it works."""
    return int(round(FEE * tier ** 1.5 / 5)) * 5


FEE = 15        # (balance pass 4, user: was 25)


def value(item) -> int:
    """What a piece is worth: its type's value plus the materials put into its tiers (shards aren't
    counted: an upgrade is an investment, not a trade)."""
    if getattr(item, "catch", None) is not None:      # a fish: by weight (v0.94.0)
        from game import fishing
        return fishing.value(item)
    base = item.type.value
    if not has_tier(item) or not item.tier:
        return base
    return base + sum(n * _material_value(mid) for t in range(1, item.tier + 1)
                      for mid, n in material_bill(item.type, t).items())


_VALUES: dict = {}


def set_catalogue(catalogue) -> None:
    """Material values for value() (set when the Engine starts)."""
    _VALUES.clear()
    for fam in families().values():
        for mid in fam:
            if mid in catalogue.types:
                _VALUES[mid] = catalogue[mid].value


def _material_value(mid: str) -> int:
    return _VALUES.get(mid, 0)


PAID = {"smith": "smith", "tackleman": "tackleman"}   # where raising a piece costs a fee (v0.96.0: tackle too)


def stores(engine, at: str) -> list:
    """Where materials are taken from: the pack, and at home the home chest too."""
    out = [engine.player.inventory]
    home = getattr(engine, "home", None)
    if at == "home" and home is not None:
        out.append(home["chest"])
    return out


def have(engine, item_id: str, at: str) -> int:
    return sum(inv.count_of(item_id) for inv in stores(engine, at))


def blocked(engine, item, at: str) -> str | None:
    """Why this piece can't go up a tier here and now, or None."""
    if not has_tier(item):
        return "That can't be raised."
    to = item.tier + 1
    if at == "home" and to > HOME_MAX:
        return f"Past +{HOME_MAX} is the smith's work."
    short = [f"{n - have(engine, mid, at)} more {engine.catalogue[mid].label(2)[2:]}"
             for mid, n in material_bill(item.type, to).items() if have(engine, mid, at) < n]
    if short:
        return "You need " + ", ".join(short) + "."
    if at in PAID and engine.player.shards < shard_cost(to):
        return f"The {PAID[at]}'s fee is {shard_cost(to)} shards."
    return None


def _take(engine, item_id: str, n: int, at: str) -> None:
    for inv in stores(engine, at):
        while n > 0 and inv.count_of(item_id):
            i = next(k for k, it in enumerate(inv.items) if it.type.id == item_id)
            got = min(n, inv.items[i].count)
            inv.remove(i, got)
            n -= got


def _discard(engine, item) -> None:
    p = engine.player
    for slot, it in list(p.equipped.items()):
        if it is item:
            del p.equipped[slot]
            p.gear_changed()
            return
    p.inventory.items = [it for it in p.inventory.items if it is not item]


def upgrade(engine, item, at: str, rng=None) -> tuple[str, str]:
    """Try to raise a piece one tier (at "smith" or "home"). Returns (outcome, message): outcome
    "blocked", "up", "failed" (materials lost, no fee taken) or "destroyed" (the piece is gone)."""
    why = blocked(engine, item, at)
    if why:
        return "blocked", why
    rng = rng or engine.rng
    to = item.tier + 1
    for mid, n in material_bill(item.type, to).items():
        _take(engine, mid, n, at)
    from game import sound
    if rng.randint(1, 100) <= chance(to):
        if at in PAID:
            engine.player.shards -= shard_cost(to)
        item.tier = to
        extra = ""
        if to % TRAIT_EVERY == 0:                       # a trait at +5, +10... (user)
            tid = roll_trait(item, rng)
            if tid:
                extra = f" It takes on a trait: {trait_line(item, tid)}."
        engine.player.gear_changed()
        sound.play("pay")
        return "up", f"The {item.type.name} is +{to} now: {step_gain(item.type, to)}.{extra}"
    if destroy_chance(to) and rng.randint(1, 100) <= destroy_chance(to):
        _discard(engine, item)
        return "destroyed", (f"The {item.type.name} gives way under the hammer and is ruined. "
                             "The materials are gone with it.")
    return "failed", (f"It doesn't take: the {item.type.name} stays +{item.tier}. The materials are spent"
                      + (f"; the {PAID[at]} keeps no fee." if at in PAID else "."))


# ---- Traits (stage 3, v0.77.0) ----------------------------------------------------------------------
# Rolled when a piece reaches +5, +10, +15... (user): one from its type's pool (data/traits.json), never
# twice on one piece. Effects use the talent keys (talents.total adds every worn piece's traits) plus
# these gear keys, read where they apply:
#   melee: parry (%), bleed_chance (%), stagger_chance (%), bounty_damage, heal_on_hit, damage_vs:<creature>,
#     armoured_rolls (dice rolls vs armour 2+), crit_bleed, rend_double, ghost_strike, riposte_accuracy,
#     pierce; bows: ranged_pierce, arrow_survive (%), free_shot (%), marked_shot_damage, ranged_stagger (%),
#     ranged_bleed_chance (%), steady; worn: light, daze_immune, no_injury:<injury>, thorns_back,
#     quick_butcher, no_heavy, ash_immune.
#   Moving (v0.86.0, game/legs.py and game/explore.py): vault, wading, mud_boots, runner, pathfinder.
#   v0.78.0: melee first_double, first_accuracy, sneak_accuracy, full_hp_damage, reach_damage, close_damage,
#     bleeding_damage, execute (%), double_strike (%), bleed_extra, hold_on_hit, pin_chance (%), crit_stagger,
#     sweep_stagger, frenzy_extra, impale_stagger, set_rolls, counter (%), reach; worn still_evasion,
#     still_armour; crossbows quick_reload, braced_damage, tier3_ranged_damage, sure_unnoticed.
#   v0.81.0: melee poison_chance, slow_chance, frighten_chance, fumble_chance (%: on_hit_states), measured,
#     momentum, notched, kill_accuracy, beast_accuracy, charge_damage, charge_beast_damage, paired_damage,
#     cleave_extra, crit_quake, reach_pull, skewer, snare_pull, throw_far, free_blows, free_reach, free_kick,
#     reach_past, pulping, make_flee (%), bleed_kill_heal; defence rhythm, brace_armour, ringing, fearsome (%);
#     bows sneak_shot_damage, close_shot_damage, volley, twin_shot (%), shot_knockback; worn listen,
#     lit_accuracy, poison_resist.
#   v0.82.0: throw_weapon (the weapon in hand can be thrown that far: game/throwing.py).
# A key ending in /5 counts once for every 5 tiers of the piece ("max_hp/5": 2 = +2 max HP per 5 tiers).
TRAITS_DATA = Path(__file__).resolve().parent.parent / "data" / "traits.json"
TRAIT_EVERY = 5
WORN = ("weapon",) + ARMOUR_SLOTS


@lru_cache(maxsize=1)
def trait_pools() -> dict:
    return json.loads(TRAITS_DATA.read_text(encoding="utf-8"))["pools"]


def pool_of(item) -> dict:
    return trait_pools().get(gear_type(item.type) or "", {})


def trait(item, tid: str) -> dict:
    return pool_of(item).get(tid, {"name": tid, "text": "", "effects": {}})


def trait_line(item, tid: str) -> str:
    t = trait(item, tid)
    return f"{t['name']} ({t['text']})" if t.get("text") else t["name"]


def trait_total(player, key: str) -> int:
    """A key summed over the traits of everything worn and wielded."""
    eq = getattr(player, "equipped", None)
    if not eq:
        return 0
    total = 0
    for slot in WORN:
        item = eq.get(slot)
        if item is None or not item.traits:
            continue
        pool = pool_of(item)
        for tid in item.traits:
            eff = pool.get(tid, {}).get("effects", {})
            total += eff.get(key, 0) + eff.get(key + "/5", 0) * (item.tier // TRAIT_EVERY)
    return total


def trait_attrs(player) -> dict:
    """Attribute changes from traits ("attr:<attribute>")."""
    out: dict = {}
    for slot in WORN:
        item = (getattr(player, "equipped", None) or {}).get(slot)
        if item is None:
            continue
        for tid in item.traits:
            for k, v in pool_of(item).get(tid, {}).get("effects", {}).items():
                if k.startswith("attr:"):
                    out[k[5:]] = out.get(k[5:], 0) + v
    return out


def roll_trait(item, rng) -> str | None:
    """A new trait for a piece that's reached a fifth tier: from the ready ones in its pool, not one it
    has. None if there are none left."""
    choices = sorted(tid for tid, t in pool_of(item).items() if t.get("ready") and tid not in item.traits)
    if not choices:
        return None
    tid = choices[rng.randint(0, len(choices) - 1)]
    item.traits.append(tid)
    return tid
