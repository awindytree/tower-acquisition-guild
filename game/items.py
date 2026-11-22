"""Items: the catalogue of item types, and the player's inventory.

Item types live in data/items.json, so adding a sword is editing a data
file, not code. An Item in the game is just "which type, how many".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from game.tiles import Color

ITEM_KINDS = ("weapon", "armor", "consumable", "material", "treasure", "key", "artifact", "misc", "writing",
              "trophy")   # trophy (v0.61.0): a creature's corpse, hauled whole (game/trophies.py)
ARTIFACT_GLYPH = "☼"

# What the current Hunter knows: the broken artifacts they've identified and the
# writings they've read. The Engine points these at the player's own sets
# (Player.known_artifacts, Player.read_writings) whenever the player changes,
# so names everywhere follow what *this* Hunter knows.
_known: tuple[set[str], ...] = (set(),)


def set_known(*known: set[str]) -> None:
    global _known
    _known = known


def _is_known(item_id: str) -> bool:
    return any(item_id in k for k in _known)


@dataclass(frozen=True)
class Rarity:
    id: str
    name: str
    tier: int            # 1 Common ... 6 Unique; also the Identification rank needed
    color: Color
    repair_fee: int
    broken_price: int


def load_rarities(path: str | Path) -> dict[str, Rarity]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {rid: Rarity(rid, d["name"], d["tier"], tuple(d["color"]), d["repair_fee"], d["broken_price"])
            for rid, d in raw.items() if not rid.startswith("_")}


@dataclass(frozen=True)
class ItemType:
    id: str
    real_name: str
    glyph: str
    color: Color
    kind: str
    real_description: str
    value: int = 0             # in shards (for a broken artifact: what it sells for once working)
    stackable: bool = False
    plural: str = ""           # defaults to name + "s" (or "es" after s, x, ch, sh)
    properties: dict = field(default_factory=dict)  # free-form: {"damage": "1d6"}, {"heal": 8}…
    rarity: Rarity | None = None       # Tower Artifacts only
    appearance: tuple[str, str] | None = None  # broken artifacts: (name, description) until identified
    repairs_to: str = ""               # broken artifacts: the working artifact's id
    working: bool = False              # a repaired artifact
    writing: dict | None = None        # writings (data/writings.json): {"difficulty", "title", "text"}

    @property
    def is_broken_artifact(self) -> bool:
        return bool(self.repairs_to)

    @property
    def identified(self) -> bool:
        """Does the current Hunter know what this is? Only broken artifacts (not yet identified)
        and writings (not yet read) can be unknown."""
        return not (self.is_broken_artifact or self.writing) or _is_known(self.id)

    @property
    def name(self) -> str:
        return self.real_name if self.identified else self.appearance[0]

    @property
    def description(self) -> str:
        return self.real_description if self.identified else self.appearance[1]

    def label(self, count: int = 1) -> str:
        if count == 1:
            return self.name
        if self.plural:
            return f"{count} {self.plural}"
        ending = "es" if self.name.endswith(("s", "x", "ch", "sh")) else "s"
        return f"{count} {self.name}{ending}"


class Catalogue:
    """Every item type, by id."""

    def __init__(self, types: dict[str, ItemType]) -> None:
        self.types = types
        self.rarities: dict[str, Rarity] = {}

    def __getitem__(self, item_id: str) -> ItemType:
        try:
            return self.types[item_id]
        except KeyError:
            raise KeyError(f"No item type {item_id!r} in items.json") from None

    def artifacts(self, broken: bool = True) -> list[ItemType]:
        return [t for t in self.types.values()
                if t.kind == "artifact" and (t.is_broken_artifact if broken else t.working)]

    @classmethod
    def load(cls, path: str | Path) -> "Catalogue":
        """Item types from items.json. Rarities and appearances (for Tower
        Artifacts) come from rarities.json and appearances.json beside it."""
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        rarities = load_rarities(path.with_name("rarities.json"))
        appearances = json.loads(path.with_name("appearances.json").read_text(encoding="utf-8"))
        types: dict[str, ItemType] = {}
        for item_id, d in raw.items():
            if item_id.startswith("_"):
                continue  # "_comment" and friends
            kind = d.get("kind", "misc")
            if kind not in ITEM_KINDS:
                raise ValueError(f"Item {item_id!r}: kind must be one of {ITEM_KINDS}, not {kind!r}")
            rarity = rarities[d["rarity"]] if "rarity" in d else None
            appearance = None
            if "appearance" in d:
                a = appearances[d["appearance"]]
                appearance = (a["name"], a["description"])
            types[item_id] = ItemType(
                id=item_id,
                real_name=d["name"],
                glyph=d.get("glyph", ARTIFACT_GLYPH if rarity else "?"),
                color=tuple(d.get("color", rarity.color if rarity else (220, 220, 220))),
                kind=kind,
                real_description=d.get("description", ""),
                value=d.get("value", 0),
                stackable=d.get("stackable", False),
                plural=d.get("plural", ""),
                properties=d.get("properties", {}),
                rarity=rarity,
                appearance=appearance,
                repairs_to=d.get("repairs_to", ""),
                working=d.get("working", False),
            )
        for t in types.values():
            if t.repairs_to and t.repairs_to not in types:
                raise ValueError(f"Item {t.id!r} repairs to {t.repairs_to!r}, which isn't in items.json")
            if t.repairs_to and t.appearance is None:
                raise ValueError(f"Broken artifact {t.id!r} needs an appearance")
        writings_path = path.with_name("writings.json")
        if writings_path.exists():
            types.update(load_writings(writings_path))
        cat = cls(types)
        cat.rarities = rarities
        return cat


def load_writings(path: Path) -> dict[str, ItemType]:
    """Writings (data/writings.json) as item types: until read, named for what they look like."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    types = {}
    for wid, d in raw["writings"].items():
        look = raw["looks"][d["look"]]
        script = raw["scripts"][str(d["difficulty"])]
        seen = f"{look['description']} {script}."
        types[wid] = ItemType(
            id=wid, real_name=f"{look['name']}: {d['title']}", glyph=look.get("glyph", "?"),
            color=tuple(look.get("color", (220, 210, 180))), kind="writing",
            real_description=f"{seen} You've read it. The Academy library would take it (talk to the librarian).",
            value=0, appearance=(look["name"], f"{seen} Read it (u), or take it to the Academy library."),
            properties={"regions": d.get("regions", []), "story": bool(d.get("story"))},
            writing={"difficulty": d["difficulty"], "title": d["title"], "text": d["text"],
                     "teaches": list(d.get("teaches", []))})
    return types


@dataclass
class Item:
    type: ItemType
    count: int = 1
    charge: int | None = None  # windcatchers: Jodebris stored (None = full)
    trophy: dict | None = None  # trophies (v0.61.0): {"kg": weight, "quirk": quirk id or ""}
    tier: int = 0               # weapons and armour (v0.75.0, game/gear.py): +0 and up, no ceiling
    traits: list = field(default_factory=list)   # trait ids, rolled at +5, +10... (stage 3)

    @property
    def slots(self) -> int:
        """Pack slots it takes: one, or more for a big trophy (v0.61.0)."""
        return max(1, self.type.properties.get("slots", 1))

    @property
    def floor_label(self) -> str:
        """What it's called lying on the ground: a trophy is still a corpse there (user, v0.61.0)."""
        if self.trophy is not None:
            from game import trophies
            return trophies.corpse_label(self)
        return self.label

    @property
    def capacity(self) -> int:
        return self.type.properties.get("capacity", 0)

    @property
    def jodebris(self) -> int:
        return self.capacity if self.charge is None else self.charge

    @property
    def label(self) -> str:
        if self.trophy is not None:
            from game import trophies
            return trophies.label(self)
        text = self.type.label(self.count)
        return f"{text} +{self.tier}" if self.tier else text

    # ---- Saving ---------------------------------------------------------
    def to_entry(self) -> list:
        """[id, count], then the charge (or None), the trophy data (or None) and the gear
        {"tier", "traits"} (v0.75.0), as far as there are any."""
        e = [self.type.id, self.count]
        gear = {}
        if self.tier:
            gear["tier"] = self.tier
        if self.traits:
            gear["traits"] = list(self.traits)
        if self.charge is not None or self.trophy is not None or gear:
            e.append(self.charge)
        if self.trophy is not None or gear:
            e.append(self.trophy)
        if gear:
            e.append(gear)
        return e

    @classmethod
    def from_entry(cls, entry, catalogue: "Catalogue") -> "Item":
        entry = [entry, 1] if isinstance(entry, str) else list(entry)
        gear = entry[4] if len(entry) > 4 and entry[4] else {}
        return cls(catalogue[entry[0]], entry[1], entry[2] if len(entry) > 2 else None,
                   dict(entry[3]) if len(entry) > 3 and entry[3] is not None else None,
                   gear.get("tier", 0), list(gear.get("traits", [])))


@dataclass
class FloorItem:
    """An item lying on the map."""
    x: int
    y: int
    item: Item


@dataclass
class Inventory:
    capacity: int  # number of slots; a stack takes one slot
    items: list[Item] = field(default_factory=list)

    @property
    def pouch(self) -> int:
        """Kinds of material a materials pouch here carries without taking slots (v0.80.0)."""
        return max((i.type.properties.get("pouch", 0) for i in self.items), default=0)

    @property
    def used(self) -> int:
        """Slots taken: one a thing (a stack counts once), more for a big trophy (v0.61.0). Materials
        in a pouch (up to its kinds) take none (v0.80.0)."""
        mats = sum(1 for i in self.items if i.type.kind == "material")
        return sum(i.slots for i in self.items if i.type.kind != "material") + max(0, mats - self.pouch)

    def cost(self, item) -> int:
        """Slots adding this (a new stack) would take."""
        if item.type.kind == "material" and sum(1 for i in self.items if i.type.kind == "material") < self.pouch:
            return 0
        return item.slots

    @property
    def is_full(self) -> bool:
        return self.used >= self.capacity

    def can_add(self, item: Item) -> bool:
        return self._stack_for(item) is not None or self.used + self.cost(item) <= self.capacity

    def add(self, item: Item) -> bool:
        """Put an item in. Stackable items join an existing stack.
        Returns False (and changes nothing) if there's no room."""
        stack = self._stack_for(item)
        if stack:
            stack.count += item.count
            return True
        if self.used + self.cost(item) > self.capacity:
            return False
        self.items.append(item)
        return True

    def remove(self, index: int, count: int | None = None) -> Item:
        """Take an item (or part of a stack) out. Returns what was removed."""
        item = self.items[index]
        if count is None or count >= item.count:
            return self.items.pop(index)
        item.count -= count
        return Item(item.type, count, item.charge, item.trophy, item.tier, list(item.traits))

    def count_of(self, item_id: str) -> int:
        return sum(i.count for i in self.items if i.type.id == item_id)

    def _stack_for(self, item: Item) -> Item | None:
        if not item.type.stackable:
            return None
        return next((i for i in self.items if i.type.id == item.type.id and i.tier == item.tier), None)

    # ---- Saving ---------------------------------------------------------
    def to_list(self) -> list:
        return [i.to_entry() for i in self.items]

    @classmethod
    def from_list(cls, data: list, catalogue: Catalogue, capacity: int) -> "Inventory":
        inv = cls(capacity)
        for entry in data:
            inv.add(Item.from_entry(entry, catalogue))
        return inv
