"""Names for Hunters, built from syllable patterns (data/names.json).

A full name is Given Middle Surname. Given names are generated here. The
middle name is occupational (for a Hunter, from their weapon) and every
Hunter's surname is Hunters, after the Guild.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SURNAME = "Hunters"


class NameMaker:
    def __init__(self, path: str | Path) -> None:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        self.classes = d["classes"]
        self.syllables = d["syllables"]
        self.three = d.get("three_syllable_chance", 0.15)
        self.min_len, self.max_len = d.get("length", [3, 8])
        self.allowed = set(d["allowed_clusters"])
        self.vowels = set(self.classes["V"])

    def given_name(self, rng: random.Random) -> str:
        for _ in range(1000):
            count = 3 if rng.random() < self.three else 2
            sounds = [rng.choice(self.classes[c]) for _ in range(count) for c in rng.choice(self.syllables)]
            if self.ok(sounds):
                name = "".join(sounds)
                return name[0].upper() + name[1:]
        raise RuntimeError("names.json rules are too strict: no name found")

    def ok(self, sounds: list[str]) -> bool:
        name = "".join(sounds)
        if not self.min_len <= len(name) <= self.max_len or not any(s in self.vowels for s in sounds):
            return False
        run = 0
        for a, b in zip(sounds, sounds[1:]):
            av, bv = a in self.vowels, b in self.vowels
            if av and bv:
                return False                      # no two vowels side by side
            if not av and not bv:
                if a + b not in self.allowed:     # covers hl/tl too: they only follow vowels
                    return False
                run += 1
                if run >= 3:                      # four consonants in a row
                    return False
            else:
                run = 0
        return True


def wielded_calling(player) -> str:
    """The calling of the weapon in hand ("Brawler" bare-handed)."""
    weapon = player.equipped.get("weapon")
    if weapon is None:
        return "Brawler"
    return weapon.type.properties.get("calling", "Fighter")


def calling(player) -> str:
    """The occupational middle name: from the kind of weapon the Hunter has used most (user),
    counted by attacks and shots. Before their first fight, from the weapon in hand; a tie
    goes to the weapon in hand if it's one of them. (v0.94.0 made a Hunter who earned most of their
    shards from fishing an Angler; v0.94.1 took it out, user: it would flip a Hunter's calling almost
    at once, with no way to choose. `Player.income` still counts the shards by how they were made.)"""
    use = getattr(player, "weapon_use", None)
    if not use:
        return wielded_calling(player)
    top = max(use.values())
    leaders = [c for c, n in use.items() if n == top]
    here = wielded_calling(player)
    return here if here in leaders else sorted(leaders)[0]


def full_name(player) -> str:
    return f"{player.name} {calling(player)} {SURNAME}"
