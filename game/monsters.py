"""Creatures: their types (data/monsters.json), and the ones alive in an area.

Which creatures turn up depends on the area's style (its habitat), and
how many and how tough on the hunt's danger and how deep you are.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from game import combat
from game.entity import Entity
from game.tiles import Color

BEHAVIOURS = ("hunt", "still")


@dataclass(frozen=True)
class MonsterType:
    id: str
    name: str
    glyph: str
    color: Color
    habitats: tuple[str, ...]
    tier: int
    hp: int
    accuracy: int
    evasion: int
    damage: str
    armor: int
    xp: int
    sight: float
    behaviour: str = "hunt"
    description: str = ""
    drops: tuple = ()   # ((item id, chance, least, most), ...): materials left where it dies
    injures: tuple = ()  # extra lasting injuries its big hits can cause (data/injuries.json)
    # v0.49.0 (the user's creatures; data/monsters.json _comment):
    when: tuple = ()     # ((style, "day"/"night"/"any"), ...): where and when it lives
    speed: str = "normal"
    flies: bool = False
    swims: bool = False
    spawn_weight: float = 1.0
    opens: str = ""      # "daze" or "leap"
    burst: str = ""      # dice: hurts everything beside it when it dies
    ghost: bool = False  # can't hit or be hit; keeps its distance
    trail: str = ""      # dice: the ash it leaves hurts the Hunter who walks on it
    thorns: int = 0
    flees: float = 0.0
    burrows: bool = False
    beast: bool = False        # an animal (v0.81.0: Herder's, Boar-spear)
    calls: bool = False        # raises the alarm when it notices you (v0.83.0: corridor-breakers)
    flanks: bool = False       # goes round another way when the way to you is blocked (v0.83.0)

    def lives(self, style: str, light: str) -> bool:
        """Does it turn up in this kind of place, at this time? (night = torchlight only)"""
        times = dict(self.when)
        if style not in times:
            return False
        return times[style] in ("any", "night" if light == "torch" else "day")


def load_monster_types(path: str | Path) -> dict[str, MonsterType]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    types = {}
    for mid, d in raw.items():
        if mid.startswith("_"):
            continue
        behaviour = d.get("behaviour", "hunt")
        if behaviour not in BEHAVIOURS:
            raise ValueError(f"Monster {mid!r}: behaviour must be one of {BEHAVIOURS}")
        combat.roll(d["damage"])  # fail early on badly written dice
        hab = d["habitats"]
        when = tuple(hab.items()) if isinstance(hab, dict) else tuple((h, "any") for h in hab)
        for _, t in when:
            if t not in ("day", "night", "any"):
                raise ValueError(f"Monster {mid!r}: a habitat's time must be day, night or any")
        for key in ("burst", "trail"):
            if d.get(key):
                combat.roll(d[key])
        types[mid] = MonsterType(
            id=mid, name=d["name"], glyph=d["glyph"], color=tuple(d["color"]),
            habitats=tuple(h for h, _ in when), tier=d["tier"], hp=d["hp"],
            accuracy=d["accuracy"], evasion=d["evasion"], damage=d["damage"],
            armor=d.get("armor", 0), xp=d.get("xp", 1), sight=d.get("sight", 8),
            behaviour=behaviour, description=d.get("description", ""),
            drops=tuple(tuple(x) for x in d.get("drops", ())),
            injures=tuple(d.get("injures", ())),
            when=when, speed=d.get("speed", "normal"), flies=d.get("flies", False), swims=d.get("swims", False),
            spawn_weight=d.get("spawn_weight", 1.0), opens=d.get("opens", ""), burst=d.get("burst", ""),
            ghost=d.get("ghost", False), trail=d.get("trail", ""), thorns=d.get("thorns", 0),
            flees=d.get("flees", 0.0), burrows=d.get("burrows", False), beast=d.get("beast", False),
            calls=d.get("calls", False), flanks=d.get("flanks", False),
        )
    return types


@dataclass
class Monster(Entity):
    type: MonsterType = None
    hp: int = 0
    awake: bool = False        # has it noticed you?
    turns_unseen: int = 0      # how long since it last saw you
    bounty: int = 0            # a bounty's marked creature: the job id (game/work.py)
    ticks: int = 0             # turns lived (slow creatures act every other one)
    opened: bool = False       # has it made its opening move (daze, leap)?
    burrowed: bool = False     # under the ground (burrowing creatures)
    phase: int = 0             # turns left in this phase (up or under)
    staggered: int = 0         # turns it loses (Stagger, Throw: game/weaponskills.py)
    bleeding: int = 0          # turns it bleeds (Rend)
    touched: bool = False      # have you struck at it yet (Quick hands)
    held: int = 0              # turns it can't move (Snare, v0.78.0); it can still fight
    set_done: bool = False     # a polearm's Set has struck it (once)
    # traits (v0.81.0)
    poisoned: int = 0          # turns of poison left (1 damage every other turn)
    slowed: int = 0            # turns slowed (it acts every other turn)
    fleeing: int = 0           # turns it runs from you (frightened)
    fumble: bool = False       # its next attack misses (Disarming, Hooked)
    charged: bool = False      # it just closed in on you (Bracing, Boar-spear, Ringing)
    blows: int = 0             # your blows at it so far (Quick hands)
    named: str = ""            # a named creature's given name (game/named.py, v0.83.0)
    affixes: list = field(default_factory=list)
    called: bool = False       # it has raised the alarm

    @classmethod
    def spawn(cls, mtype: MonsterType, x: int, y: int) -> "Monster":
        return cls(x=x, y=y, char=mtype.glyph, color=mtype.color, name=mtype.name,
                   type=mtype, hp=mtype.hp)

    # The combat interface (see game/combat.py).
    @property
    def speed(self) -> str:
        return "quick" if "swift" in self.affixes else self.type.speed

    @property
    def accuracy(self) -> int:
        return self.type.accuracy

    @property
    def evasion(self) -> int:
        return self.type.evasion

    @property
    def damage_dice(self) -> str:
        return self.type.damage

    @property
    def damage_bonus(self) -> int:
        return 1 if "hulking" in self.affixes else 0

    @property
    def armor(self) -> int:
        return self.type.armor + (2 if "armoured" in self.affixes else 0)

    @property
    def pierce(self) -> int:
        return 0

    @property
    def is_dead(self) -> bool:
        return self.hp <= 0

    def take_damage(self, amount: int) -> None:
        self.hp -= amount


# ---- Spawning --------------------------------------------------------------
def tier_cap(danger: int, area_index: int) -> int:
    """The toughest tier allowed: rises with danger and with depth."""
    return min(4, (2 + danger + area_index // 2) // 2)


def spawn_count(danger: int, area_index: int) -> int:
    # (balance pass 3, user: one more creature per area at danger 3 (v0.62.1), and at 4 and 5 (v0.62.2))
    return min(10, 2 + danger + area_index // 2 + (1 if danger >= 3 else 0))


def choose_spawns(types: dict[str, MonsterType], habitat: str, danger: int, area_index: int,
                  spots: list[tuple[int, int]], rng: random.Random,
                  more: float = 1.0, favour: str = "", light: str = "day",
                  water: list[tuple[int, int]] | None = None, only: str = "") -> list[Monster]:
    """Pick creatures for an area and place them on the given spots. `more` scales how
    many; `favour` is a creature that turns up far more often, wherever it lives, if
    the danger allows its tier (keyword places, game/keywords.py)."""
    cap = tier_cap(danger, area_index)
    pool = [t for t in types.values() if (t.lives(habitat, light) or t.id == favour) and t.tier <= cap
            and (not t.swims or water)]          # (swimmers only where there's water)
    if only and only in types:                   # a place with one creature only (Ashfall, v0.70.0): any tier, anywhere
        pool = [types[only]]
    if not pool:
        return []
    # Higher tiers are rarer: weight 4 for tier 1, 3 for tier 2, and so on.
    weights = [(5 - t.tier) * (6 if t.id == favour else 1) * t.spawn_weight for t in pool]
    spots = spots[:]
    rng.shuffle(spots)
    count = max(1, round(spawn_count(danger, area_index) * more))
    chosen = rng.choices(pool, weights, k=min(count, len(spots)))
    out, wet = [], list(water or [])
    rng.shuffle(wet)
    dry = [t for t in pool if not t.swims]
    for t in chosen:
        if t.swims and not wet and dry:      # no water left for it: something else instead
            t = rng.choices(dry, [(5 - d.tier) * d.spawn_weight for d in dry])[0]
        if t.swims:
            if wet:
                out.append(Monster.spawn(t, *wet.pop()))   # waiting in the water
        else:
            m = Monster.spawn(t, *spots.pop())
            if t.burrows:
                m.burrowed, m.phase = True, 0
            out.append(m)
    return out
