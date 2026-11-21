"""Lasting injuries: picked up from big hits, healed by time (minor ones) or the healer.

An injury belongs to the Hunter (lost with them). Its effects are worked out
here and fed to the player: attribute changes go into Stats (so a lower
Fortitude lowers max HP too), the rest are read by accuracy, evasion,
damage and the bow. Bleeding and poison tick each turn outside the city.
The table is data/injuries.json; every number is a placeholder.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "injuries.json"


@dataclass(frozen=True)
class InjuryType:
    id: str
    name: str
    severity: str           # "minor" (mends with time) or "serious" (needs the healer)
    description: str
    min_tier: int
    mends: int | None       # Pulses to mend on its own; None = never
    fee: int                # what the healer charges
    creature_only: bool = False
    attributes: dict = field(default_factory=dict)
    max_hp: int = 0
    accuracy: int = 0
    ranged: int = 0
    evasion: int = 0
    damage: int = 0
    sight: int = 0           # change to how far you can see, in cells (v0.43.0; none use it yet)
    dot: dict | None = None  # {"kind", "damage", "every", "turns"}

    def effect_text(self) -> str:
        from game.stats import ATTRIBUTES
        names = {a.key: a.name for a in ATTRIBUTES}
        parts = [f"{names.get(k, k)} {v:+d}" for k, v in self.attributes.items()]
        for key, label in (("max_hp", "max HP"), ("accuracy", "accuracy"), ("ranged", "with bows"),
                           ("evasion", "evasion"), ("damage", "damage"),
                           ("sight", "sight")):
            if getattr(self, key):
                parts.append(f"{label} {getattr(self, key):+d}")
        if self.dot:
            d = self.dot
            parts.append(f"{d['kind']}: {d['damage']} HP every {d['every']} turns for {d['turns']} turns")
        return ", ".join(parts)


@dataclass
class Injury:
    """One injury on a Hunter."""
    id: str
    since: int          # the day it happened
    dot_left: int = 0   # turns of bleeding/poison left
    dot_count: int = 0  # turns towards the next tick


class Table:
    def __init__(self, path: str | Path = DEFAULT_PATH) -> None:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.big_hit = raw.get("big_hit", 0.2)
        self.big_hit_cap = raw.get("big_hit_cap")   # never needs more than this much damage (or None)
        self.chance = raw.get("chance", 0.3)
        self.per_tier = raw.get("per_tier", 0.1)
        self.small_hit = raw.get("small_hit", 0.0)   # any lesser hit: this chance
        self.types: dict[str, InjuryType] = {}
        for iid, d in raw["injuries"].items():
            if d["severity"] not in ("minor", "serious"):
                raise ValueError(f"Injury {iid!r}: severity must be minor or serious")
            self.types[iid] = InjuryType(
                id=iid, name=d["name"], severity=d["severity"], description=d.get("description", ""),
                min_tier=d.get("min_tier", 1), mends=d.get("mends"), fee=d.get("fee", 0),
                creature_only=d.get("creature_only", False), attributes=dict(d.get("attributes", {})),
                max_hp=d.get("max_hp", 0), accuracy=d.get("accuracy", 0), ranged=d.get("ranged", 0),
                evasion=d.get("evasion", 0), damage=d.get("damage", 0), sight=d.get("sight", 0),
                dot=d.get("dot"))

    def __getitem__(self, iid: str) -> InjuryType:
        return self.types[iid]


_table: Table | None = None


def table() -> Table:
    global _table
    if _table is None:
        _table = Table()
    return _table


def load(path: str | Path) -> Table:
    global _table
    _table = Table(path)
    return _table


# ---- Effects --------------------------------------------------------------------------------------
def total(player, key: str) -> int:
    """The sum of one effect (accuracy, ranged, evasion, damage, max_hp) over the Hunter's injuries."""
    t = table()
    return sum(getattr(t[i.id], key) for i in player.injuries)


def _resist(player) -> float:
    """Iron Will: hard blows less likely to injure."""
    from game import talents
    return 1 - talents.total(player, "injury_chance") / 100


def apply_to_stats(player) -> None:
    """Feed attribute and max-HP changes into the Hunter's Stats. Call after injuries change."""
    t = table()
    mods: dict[str, int] = dict(getattr(player, "age_mods", {}))   # age first (game/aging.py)
    for i in player.injuries:
        for k, v in t[i.id].attributes.items():
            mods[k] = mods.get(k, 0) + v
    from game import talents                     # attribute and HP talents (v0.58.0)
    for tid in getattr(player, "talents", []):
        for k, v in talents.pool().get(tid, {}).get("effects", {}).items():
            if k.startswith("attr:"):
                mods[k[5:]] = mods.get(k[5:], 0) + v
    player.stats.mods = mods
    player.stats.hp_mod = total(player, "max_hp") + talents.total(player, "max_hp")
    player.stats.hp = min(player.stats.hp, player.stats.max_hp)
    player.refresh_capacity()


def bleeding(player) -> list[str]:
    """The kinds of damage over time running now ("bleeding", "poisoned")."""
    t = table()
    return sorted({t[i.id].dot["kind"] for i in player.injuries if i.dot_left > 0})


# ---- Getting hurt ---------------------------------------------------------------------------------
def roll_injury(player, monster_type, damage: int, day: int, rng: random.Random) -> InjuryType | None:
    """Maybe injure the Hunter after a hit. Only big hits can."""
    t = table()
    threshold = t.big_hit * player.stats.max_hp
    if t.big_hit_cap:
        threshold = min(threshold, t.big_hit_cap)
    if damage < threshold:
        # lesser hits can injure too, more rarely (user, 2026-11-19: injuries across the board)
        if damage <= 0 or rng.random() >= t.small_hit:
            return None
    elif rng.random() >= (t.chance + t.per_tier * (monster_type.tier - 1)) * _resist(player):
        return None
    have = {i.id for i in player.injuries}
    pool = [it for it in t.types.values()
            if it.id not in have and ((not it.creature_only and it.min_tier <= monster_type.tier)
                                      or it.id in monster_type.injures)]
    if not pool:
        return None
    it = rng.choice(sorted(pool, key=lambda x: x.id))
    add(player, it.id, day)
    return it


def add(player, iid: str, day: int) -> None:
    it = table()[iid]
    from game import fieldskills
    player.injuries.append(Injury(iid, day, fieldskills.wound_turns(player, it.dot["turns"]) if it.dot else 0))
    apply_to_stats(player)


def remove(player, iid: str) -> None:
    player.injuries = [i for i in player.injuries if i.id != iid]
    apply_to_stats(player)


# ---- Each turn, each day ---------------------------------------------------------------------------
def tick(player, in_city: bool) -> tuple[int, list[str]]:
    """Once per turn: bleeding and poison. Returns (HP lost, messages). Nothing ticks in the city."""
    if in_city:
        return 0, []
    t = table()
    lost, messages = 0, []
    for i in player.injuries:
        if i.dot_left <= 0:
            continue
        dot = t[i.id].dot
        i.dot_left -= 1
        i.dot_count += 1
        if i.dot_count >= dot["every"]:
            i.dot_count = 0
            lost += player.stats.take_damage(dot["damage"])
        if i.dot_left == 0:
            messages.append(f"Your {t[i.id].name} has stopped {'bleeding' if dot['kind'] == 'bleeding' else 'burning'}.")
    return lost, messages


def mend(player, day: int) -> list[str]:
    """As days pass: minor injuries heal on their own."""
    t = table()
    from game import works                  # (the infirmary: minor injuries mend sooner)
    quicker = 1 - works.active("mending") / 100
    healed = [i for i in player.injuries if t[i.id].mends is not None and day - i.since >= t[i.id].mends * quicker]
    for i in healed:
        remove(player, i.id)
    return [f"Your {t[i.id].name} {'have' if t[i.id].name.endswith('s') else 'has'} mended." for i in healed]


def fee(it) -> int:
    """The healer's fee for an injury (less with the Guild's infirmary, v0.60.0)."""
    from game import works
    return max(1, round(it.fee * (1 - works.active("healing") / 100))) if it.fee else 0


def treat(player, iid: str) -> tuple[bool, str]:
    """The healer treats one injury, for a fee."""
    it = table()[iid]
    cost = fee(it)
    if player.shards < cost:
        return False, f"Treating your {it.name} costs {cost} shards; you have {player.shards}."
    player.shards -= cost
    remove(player, iid)
    return True, f"The healer sees to your {it.name}. ({cost} shards)"


# ---- Saving ------------------------------------------------------------------------------------------
def to_list(injuries) -> list:
    return [[i.id, i.since, i.dot_left, i.dot_count] for i in injuries]


def from_list(data) -> list[Injury]:
    return [Injury(*d) for d in data if d[0] in table().types]
