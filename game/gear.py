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
    """Weapons and armour have tiers; windcatchers, artifacts and everything else don't."""
    t = item.type
    return t.kind in ("weapon", "armor") and not t.properties.get("windcatcher") and not t.rarity


def gear_type(item_type) -> str | None:
    """The weapon type or armour slot that decides an item's materials (data/gear.json)."""
    if item_type.kind == "armor":
        return armour_slot(item_type)
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
    if item.type.kind == "weapon":
        parts = [(accuracy(item), "accuracy"), (damage(item), "damage")]
    else:
        parts = [(armour(item), "armour"), (max_hp(item), "max HP")]
    return ", ".join(f"+{n} {what}" for n, what in parts if n)


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
