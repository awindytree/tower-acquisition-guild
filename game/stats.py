"""Character statistics: attributes, health, level and experience.

The attribute list below is the one place attributes are defined. Rename,
add or remove them here; the side panel and the save format follow along.
The derived values (max HP and so on) are plain functions near the bottom,
so the game's maths is easy to find and tune.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Attribute:
    key: str     # used in data files: "physicality"
    abbr: str    # shown in the side panel: "PHY"
    name: str
    description: str


ATTRIBUTES: list[Attribute] = [
    # Roles rewritten in v0.57.0 (design-progression stage 3): Hunters cast no spells (Chorus magic exists in the world,
    # but needs Jodebris sensitivity; user, 2026-11-21), so Acumen and
    # Tenacity lost "spell power" and "mana". Each attribute also speeds practice in its skills.
    Attribute("physicality", "PHY", "Physicality", "Melee damage and how much you can carry. Speeds Axes, Hafted, Brawling, Harvesting."),
    Attribute("celerity",    "CEL", "Celerity",    "Accuracy and dodging. Speeds Blades, Marksmanship, Stealth."),
    Attribute("fortitude",   "FOR", "Fortitude",   "Hit points and healing. Speeds Survival."),
    Attribute("acumen",      "ACU", "Acumen",      "Understanding what you find. Speeds Identification, Scholarship, Medicine, Tracking, Bargaining."),
    Attribute("tenacity",    "TEN", "Tenacity",    "Shaking off being dazed. Speeds Attunement."),
]
ATTRIBUTE_KEYS = [a.key for a in ATTRIBUTES]


@dataclass
class Stats:
    attributes: dict[str, int] = field(default_factory=lambda: {k: 10 for k in ATTRIBUTE_KEYS})
    level: int = 1
    xp: int = 0
    hp: int = -1  # -1 means "start at full health"
    mods: dict = field(default_factory=dict)  # attribute changes from injuries (not saved: worked out from them)
    hp_mod: int = 0                           # max-HP change from injuries

    def __post_init__(self) -> None:
        unknown = set(self.attributes) - set(ATTRIBUTE_KEYS)
        if unknown:
            raise ValueError(f"Unknown attributes {sorted(unknown)}; expected {ATTRIBUTE_KEYS}")
        for key in ATTRIBUTE_KEYS:
            self.attributes.setdefault(key, 10)
        if self.hp < 0:
            self.hp = self.max_hp

    def __getitem__(self, key: str) -> int:
        """An attribute as it is now (after injuries; never below 1). The base is in .attributes."""
        return max(1, self.attributes[key] + self.mods.get(key, 0))

    # ---- Derived values -------------------------------------------------
    @property
    def max_hp(self) -> int:
        return max(1, max_hp(self["fortitude"], self.level) + self.hp_mod)

    @property
    def xp_to_next(self) -> int:
        return xp_for_level(self.level + 1)

    @property
    def is_dead(self) -> bool:
        return self.hp <= 0

    # ---- Changes --------------------------------------------------------
    def take_damage(self, amount: int) -> int:
        """Lose up to `amount` HP. Returns how much was actually lost."""
        lost = min(max(0, amount), self.hp)
        self.hp -= lost
        return lost

    def heal(self, amount: int) -> int:
        """Regain up to `amount` HP, capped at max. Returns how much was healed."""
        gained = min(max(0, amount), self.max_hp - self.hp)
        self.hp += gained
        return gained

    def gain_xp(self, amount: int) -> int:
        """Add experience. Returns how many levels were gained."""
        self.xp += amount
        levels = 0
        while self.xp >= self.xp_to_next:
            self.level += 1
            levels += 1
            self.hp = self.max_hp  # a full heal on level up
        return levels

    # ---- Saving ---------------------------------------------------------
    def to_dict(self) -> dict:
        return {"attributes": dict(self.attributes), "level": self.level, "xp": self.xp, "hp": self.hp}

    @classmethod
    def from_dict(cls, data: dict) -> "Stats":
        return cls(
            attributes=dict(data.get("attributes", {})),
            level=data.get("level", 1),
            xp=data.get("xp", 0),
            hp=data.get("hp", -1),
        )


# ---- The formulas. Tune these freely. ------------------------------------
def max_hp(fortitude: int, level: int) -> int:
    return 20 + fortitude + (level - 1) * (4 + fortitude // 4)


def xp_for_level(level: int) -> int:
    """Total experience needed to reach `level`."""
    return 0 if level <= 1 else 5 * (level - 1) * level * (level + 1)


def regen_turns(fortitude: int) -> int:
    """Turns to recover 1 HP naturally. Higher Fortitude heals faster."""
    return max(3, 10 - (fortitude - 10) // 2)


def carry_slots(physicality: int) -> int:
    """How many different things you can carry (stacks count as one)."""
    return min(26, 10 + physicality // 2)  # 26: one per letter, a to z
