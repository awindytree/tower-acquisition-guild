"""The player: an Entity with a profile (name, stats, inventory, shards).

A new character comes from data/player.json. to_dict()/from_dict() turn
the whole profile into plain data and back, which is what a save file
will store.
"""
from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from game import artifacts, injuries
from game.combat import attribute_bonus
from game.entity import Entity
from game.items import Catalogue, Inventory, Item
from game.names import NameMaker, full_name
from game.work import jobs_from_list as work_jobs_from_list, jobs_to_list as work_jobs_to_list
from game.skills import SkillState
from game import gear
from game.stats import ATTRIBUTES, Stats, carry_slots, regen_turns

def weaponskills_guard(player) -> int:
    """Guard (Staves 3, v0.78.0): +2 evasion with a staff in hand."""
    from game import weaponskills
    return weaponskills.GUARD_EVASION if weaponskills.has_passive(player, "staves") else 0


# Which kinds of item go in which equipment slot (armour: its own slot, game/gear.py, v0.75.0).
SLOT_FOR_KIND = {"weapon": "weapon"}
UNARMED = "1d3"

PLAYER_GLYPH = "@"   # people are @ (user, v0.52.1; ☺ from v0.42.0)
PLAYER_COLOR = (255, 90, 230)   # v0.52.0 (user: more ostentatious): a vivid magenta, unlike any creature or person


def roll_attributes(rng: random.Random, base: int = 8, points: int = 10, max: int = 14) -> dict:
    """Every attribute at base, then points handed out one by one at random (none above max)."""
    values = {a.key: base for a in ATTRIBUTES}
    for _ in range(points):
        open_ = [k for k, v in values.items() if v < max]
        if not open_:
            break
        values[rng.choice(open_)] += 1
    return values


def roll_kit(rng: random.Random, kit: dict) -> dict:
    """A random starting kit: inventory, equipped and shards for player.json's from_dict."""
    weapon_set = rng.choice(kit["weapons"])
    armor = rng.choice(kit.get("armor", [None]))
    inventory, equipped = [], []
    for i, entry in enumerate(weapon_set):
        inventory.append(entry)
        if i == 0:
            equipped.append(entry if isinstance(entry, str) else entry[0])
    if armor:
        inventory.append(armor)
        equipped.append(armor)
    for item_id, (low, high) in kit.get("supplies", {}).items():
        n = rng.randint(low, high)
        if n:
            inventory.append([item_id, n])
    low, high = kit.get("shards", [15, 15])
    return {"inventory": inventory, "equipped": equipped, "shards": rng.randint(low, high)}


JODEBRIS_SENSITIVE_CHANCE = 0.001   # (v0.64.1, user)


@dataclass
class Player(Entity):
    stats: Stats = field(default_factory=Stats)
    gender: str = ""
    inventory: Inventory = field(default_factory=lambda: Inventory(10))
    shards: int = 0  # money: coins today, once true pieces of Windcatcher glass
    equipped: dict = field(default_factory=dict)  # slot -> Item, out of the bag (user, v0.69.0; was: in it)
    faints_allowed: int = 1  # knockouts survived per hunt; the next one is death
    regen_progress: int = 0  # turns towards the next point of natural healing
    hunter_id: str = field(default_factory=lambda: uuid.uuid4().hex)  # which saves are this Hunter's
    skills: dict = field(default_factory=dict)            # skill id -> SkillState
    known_artifacts: set = field(default_factory=set)     # broken artifact ids this Hunter has identified
    read_writings: set = field(default_factory=set)       # writings this Hunter has read (game/library.py)
    notes: dict = field(default_factory=dict)             # unreported field notes for the Guild archive (game/archive.py)
    studied: dict = field(default_factory=dict)           # artifact id -> Identification rank last tried at
    artifact_uses: dict = field(default_factory=dict)     # working artifact id -> uses this hunt
    artifact_slots: list = field(default_factory=lambda: [None] * 3)  # equipped artifacts (out of the bag)
    flags: set = field(default_factory=set)   # conversation flags that belong to this Hunter
    earned: int = 0      # shards earned since the last dues were assessed (pickups, sales, consignments)
    earned_free: int = 0 # ...and Guild pay since then, which owes no dues (bounties, jobs, notes; v0.52.0)
    dues_owed: int = 0   # Guild dues not yet paid
    jobs: list = field(default_factory=list)  # odd jobs taken (game/work.py)
    contract: object = None    # the Guild contract taken (game/postings.py; a hunt.Contract)
    in_miasma: bool = False  # out on a hunt, beyond the Chorus Winds (set by the Engine; not saved)
    torch_turns: int = 0     # turns left on the lit torch (0 = none lit)
    dazed: int = 0           # turns left dazed (a mirebellow's bellow): accuracy and evasion -2
    readied: str | None = None   # an active technique readied with z (game/weaponskills.py)
    talents: list = field(default_factory=list)        # talent ids, in the order taken (game/talents.py)
    talent_offers: list = field(default_factory=list)  # [[id, id, id], ...]: choices still to make
    second_wind_used: bool = False   # (the Second Wind talent: once a hunt)
    vengeance: bool = False          # (Vengeful: a creature hit you; your next blow gets more accuracy)
    unloaded: bool = False           # a crossbow shot and not yet wound again (v0.78.0)
    frenzy: int = 0                  # Frenzy (Claws 5): blows left that take no time
    stepped_now: bool = False        # this action was a step (Braced: did you step the turn before?)
    stepped_last: bool = False
    prey: dict = field(default_factory=dict)   # creature id -> kills by this Hunter (game/mastery.py)
    tech_rest: int = 0           # turns before one can be readied again
    torch_light: int = 0     # how much light it gives
    meal_turns: int = 0      # turns left of healing from something eaten
    meal_heal: int = 0       # HP it gives each of those turns
    injuries: list = field(default_factory=list)  # lasting injuries (game/injuries.py)
    join_age: int = 0          # age (in Pulses) when they joined the Guild (game/aging.py)
    born: int | None = None    # the day (absolute Pulse) they were born; set when they join
    age_mods: dict = field(default_factory=dict)  # attribute changes from age (worked out, not saved)
    judgments_seen: int = 0    # whole Judgments of age last marked (for "has seen ...")
    hunts_done: int = 0        # hunts completed (for the Hall of Hunters)
    weapon_use: dict = field(default_factory=dict)  # calling -> attacks made with such a weapon (game/names.py)
    quests: dict = field(default_factory=dict)      # this Hunter's own quests ("scope": "hunter"; game/story.py)
    rank: int = 0              # Guild rank (index into data/ranks.json; game/ranks.py)
    labouring: bool = False    # working off dues right now (not saved)

    def skill(self, skill_id: str) -> SkillState:
        """This Hunter's progress in a skill (rank 1, no practice, if new to it)."""
        return self.skills.setdefault(skill_id, SkillState())

    def regenerate(self) -> None:
        """Called once per turn: slowly recover HP."""
        if self.stats.hp >= self.stats.max_hp or self.stats.is_dead or injuries.bleeding(self):
            self.regen_progress = 0
            return
        self.regen_progress += 1
        from game import talents
        if self.regen_progress >= max(1, regen_turns(self.stats["fortitude"]) - talents.total(self, "heal_rate")):
            self.regen_progress = 0
            self.stats.heal(1)

    # ---- Equipment ------------------------------------------------------
    def slot_for(self, item: Item) -> str | None:
        if item.type.properties.get("windcatcher"):
            return "windcatcher"
        if item.type.kind == "armor":
            return gear.armour_slot(item.type)
        return SLOT_FOR_KIND.get(item.type.kind)

    def gear_changed(self) -> None:
        """Call after the equipment changes: armour tiers give max HP (v0.75.0)."""
        self.stats.gear_hp = gear.hp_total(self)
        injuries.apply_to_stats(self)              # (traits: attributes, max HP; v0.77.0)
        self.stats.hp = min(self.stats.hp, self.stats.max_hp)

    def earn(self, amount: int) -> None:
        """Shards earned (found, or from selling and consigning): the Guild takes its share as dues."""
        self.shards += amount
        self.earned += amount

    def guild_pay(self, amount: int) -> None:
        """Paid by the Guild (bounties, scouting, field notes): no dues are taken from it."""
        self.shards += amount
        self.earned_free += amount

    # ---- Artifact slots: separate from the bag ------------------------------------
    @staticmethod
    def goes_in_artifact_slot(item: Item) -> bool:
        return item.type.working and not item.type.properties.get("windcatcher")

    def equip_artifact(self, index: int, slot: int | None = None) -> tuple[bool, str]:
        """Move a working artifact from the bag into an artifact slot: the first free one, or the
        given one (v0.69.0, from the equipment window), swapping out what's there into the bag."""
        item = self.inventory.items[index]
        from game import attunement
        attunement.sync_slots(self)                  # a fourth slot at Attunement 5 (v0.57.0)
        if slot is None:
            if None not in self.artifact_slots:
                return False, (f"Your {len(self.artifact_slots)} artifact slots are full. "
                               "Take one off first.")
            slot = self.artifact_slots.index(None)
        old = self.artifact_slots[slot]
        self.artifact_slots[slot] = self.inventory.remove(index)
        if old is not None:
            self.inventory.add(old)                  # (the new one's place in the bag is free)
            return True, f"You swap the {old.type.name} for the {item.type.name}."
        return True, f"You equip the {item.type.name}."

    def unequip_artifact(self, slot: int) -> tuple[bool, str]:
        """Move an artifact from its slot back into the bag."""
        item = self.artifact_slots[slot]
        if item is None:
            return False, "That slot is empty."
        if not self.inventory.add(item):
            return False, f"You have no room in your pack for the {item.type.name}."
        self.artifact_slots[slot] = None
        return True, f"You take off the {item.type.name}."

    @property
    def equipped_artifacts(self) -> list[Item]:
        return [i for i in self.artifact_slots if i is not None]

    @property
    def windcatcher(self) -> Item | None:
        """The equipped windcatcher, if any."""
        return self.equipped.get("windcatcher")

    def is_equipped(self, item: Item) -> bool:
        return any(item is e for e in self.equipped.values())

    def all_items(self) -> list[Item]:
        """Everything the Hunter has: the bag, the equipment slots and the artifact slots."""
        return list(self.inventory.items) + list(self.equipped.values()) + self.equipped_artifacts

    def equip(self, item: Item) -> Item | None:
        """Wield, wear or hang an item (from the bag, or given). Since v0.69.0 (user) equipment has its
        own slots, out of the bag: the item leaves the bag, and what it replaces goes into the bag.
        Returns what it replaced. Raises ValueError if it can't be equipped or the old one won't fit."""
        slot = self.slot_for(item)
        if slot is None:
            raise ValueError(f"{item.type.name} can't be equipped")
        old = self.equipped.get(slot)
        idx = next((i for i, x in enumerate(self.inventory.items) if x is item), None)
        if idx is not None:
            self.inventory.items.pop(idx)
        if old is not None and not self.inventory.add(old):
            if idx is not None:
                self.inventory.items.insert(idx, item)
            raise ValueError(f"No room in your pack for the {old.type.name}")
        self.equipped[slot] = item
        self.gear_changed()
        return old

    def unequip_slot(self, slot: str) -> tuple[bool, str]:
        """Take off what's in an equipment slot and put it in the bag."""
        item = self.equipped.get(slot)
        if item is None:
            return False, "Nothing's there."
        if not self.inventory.add(item):
            return False, f"You have no room in your pack for the {item.type.name}."
        del self.equipped[slot]
        self.gear_changed()
        off = {"weapon": "put away", "windcatcher": "unhook"}.get(slot, "take off")
        return True, f"You {off} the {item.type.name}."

    def unequip(self, item: Item) -> tuple[bool, str]:
        slot = next((s for s, e in self.equipped.items() if e is item), None)
        return self.unequip_slot(slot) if slot else (False, "That isn't equipped.")

    # ---- Combat (see game/combat.py) --------------------------------------
    @property
    def accuracy(self) -> int:
        from game import weaponskills
        from game import talents, mastery
        weapon = self.equipped.get("weapon")
        tier = gear.accuracy(weapon) if weapon and not weapon.type.properties.get("bash_every") else 0
        return (self.stats["celerity"] + artifacts.bonus(self, "accuracy") + injuries.total(self, "accuracy")
                + weaponskills.accuracy_bonus(self) + talents.total(self, "accuracy") + tier
                + mastery.calling_bonus(self, "accuracy") - (2 if self.dazed else 0))

    @property
    def evasion(self) -> int:
        from game import talents, mastery
        return (self.stats["celerity"] + artifacts.bonus(self, "evasion") + injuries.total(self, "evasion")
                + talents.total(self, "evasion") + mastery.calling_bonus(self, "evasion") - (2 if self.dazed else 0)
                + weaponskills_guard(self)
                + (0 if self.stepped_now else talents.total(self, "still_evasion")))       # Line-holder

    @property
    def light_bonus(self) -> int:
        """Extra light in dark places: the strongest of a lit torch and powered artifacts."""
        from game import talents                   # (+ the light traits on gear, v0.77.0)
        return (max(artifacts.light_bonus(self), self.torch_light if self.torch_turns > 0 else 0)
                + talents.total(self, "light"))

    def tick_supplies(self) -> list[str]:
        """Once per turn: torches burn down, meals mend. Returns messages."""
        messages = []
        if self.meal_turns > 0:
            self.meal_turns -= 1
            if not self.stats.is_dead:
                self.stats.heal(self.meal_heal)
        if self.torch_turns > 0:
            self.torch_turns -= 1
            if self.torch_turns == 0:
                self.torch_light = 0
                messages.append("Your torch gutters out.")
            elif self.torch_turns == 25:
                messages.append("Your torch is burning low.")
        return messages

    @property
    def damage_dice(self) -> str:
        weapon = self.equipped.get("weapon")
        if weapon is None:
            return UNARMED
        props = weapon.type.properties
        return props.get("melee", props.get("damage", UNARMED))  # a bow in close combat is only a bash

    def note_weapon_use(self) -> None:
        """An attack (or a shot) with the weapon in hand: the most used kind gives the Hunter's calling."""
        from game.names import wielded_calling
        c = wielded_calling(self)
        self.weapon_use[c] = self.weapon_use.get(c, 0) + 1

    @property
    def damage_bonus(self) -> int:
        weapon = self.equipped.get("weapon")
        bash = weapon.type.properties.get("bash_every") if weapon else None
        if bash:   # a bow in close combat: a bash, helped by Physicality (instead of the usual bonus)
            return self.stats["physicality"] // bash + injuries.total(self, "damage")
        from game import weaponskills
        from game import talents
        low = talents.total(self, "low_hp_damage") if self.stats.hp * 3 < self.stats.max_hp else 0   # Last Stand
        from game import mastery
        return (attribute_bonus(self.stats["physicality"]) + injuries.total(self, "damage")
                + weaponskills.damage_bonus(self) + talents.total(self, "damage") + low + gear.damage(weapon)
                + mastery.calling_bonus(self, "damage"))

    @property
    def crit(self) -> int:
        """% chance a landed blow does double damage (Keen Edge, Executioner)."""
        from game import talents
        return talents.total(self, "crit")

    @property
    def faint_limit(self) -> int:
        """Faints survived each hunt (Hard to Kill adds one)."""
        from game import talents
        return self.faints_allowed + talents.total(self, "faints")

    @property
    def pierce(self) -> int:
        """Armour your blows ignore (Crush, Hafted rank 3)."""
        from game import weaponskills, mastery
        from game import talents                   # (+ Sundering and Splitting, traits)
        return ((1 if weaponskills.has_passive(self, "hafted") else 0) + mastery.calling_bonus(self, "pierce")
                + talents.total(self, "pierce"))

    @property
    def armor(self) -> int:
        from game import talents
        return (gear.armour_total(self) + artifacts.bonus(self, "armor") + talents.total(self, "armor")
                + (0 if self.stepped_now else talents.total(self, "still_armour")))        # Braced (legs)

    @property
    def is_dead(self) -> bool:
        return self.stats.is_dead

    def take_damage(self, amount: int) -> None:
        self.stats.take_damage(amount)

    def refresh_capacity(self) -> None:
        """Call after Physicality changes."""
        from game import talents
        self.inventory.capacity = carry_slots(self.stats["physicality"]) + talents.total(self, "carry")

    # ---- Creating and saving --------------------------------------------
    @classmethod
    def new(cls, path: str | Path, catalogue: Catalogue, x: int = 0, y: int = 0,
            rng: random.Random | None = None) -> "Player":
        """A fresh Hunter from the starting profile in data/player.json:
        random given name, gender and attributes unless the profile fixes them."""
        rng = rng or random.Random()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not data.get("name"):
            data["name"] = NameMaker(Path(path).with_name("names.json")).given_name(rng)
        if "gender" not in data and data.get("genders"):
            data["gender"] = rng.choice(data["genders"])
        from game import aging
        if "join_age" not in data:
            data["join_age"] = aging.roll_age(rng)
        if "random_attributes" in data:
            ra = dict(data["random_attributes"])
            ra["points"] = ra.get("points", 10) + aging.extra_points(data["join_age"])  # an older recruit's past
            data["attributes"] = roll_attributes(rng, **ra)
        if "random_kit" in data:
            data.update(roll_kit(rng, data["random_kit"]))
        player = cls.from_dict(data, catalogue, x, y)
        # About 19 in 1.3 million people can hear or feel Jodebris (user, lore); a new Hunter is one of
        # them 0.1% of the time (user, v0.64.1: far likelier than in life, so it can happen in play).
        # Hunter flag "jodebris_sensitive". It does nothing yet: what it means, mechanically and in the
        # story, is to be decided (user). Rolled only for random Hunters (not fixed test profiles).
        if "random_attributes" in data and rng.random() < JODEBRIS_SENSITIVE_CHANCE:
            player.flags.add("jodebris_sensitive")
        return player

    @property
    def full_name(self) -> str:
        """Given name, calling (from the weapon) and Hunters: "Ylfa Fencer Hunters"."""
        return full_name(self)

    def to_dict(self) -> dict:
        return {
            "hunter_id": self.hunter_id,
            "name": self.name,
            "gender": self.gender,
            "shards": self.shards,
            **self.stats.to_dict(),
            "inventory": self.inventory.to_list(),
            "equipment": {slot: item.to_entry() for slot, item in self.equipped.items()},   # (v0.69.0)
            "faints_allowed": self.faints_allowed,
            "skills": {sid: [st.rank, st.practice] for sid, st in self.skills.items()},
            "known_artifacts": sorted(self.known_artifacts),
            "read_writings": sorted(self.read_writings),
            "notes": self.notes,
            "studied": dict(self.studied),
            "artifact_uses": dict(self.artifact_uses),
            "artifact_slots": [i.type.id if i else None for i in self.artifact_slots],
            "flags": sorted(self.flags),
            "dues": [self.earned, self.dues_owed, self.earned_free],
            "jobs": work_jobs_to_list(self.jobs),
            "torch": [self.torch_turns, self.torch_light],
            "meal": [self.meal_turns, self.meal_heal],
            "injuries": injuries.to_list(self.injuries),
            "age": [self.join_age, self.born, self.judgments_seen],
            "hunts_done": self.hunts_done,
            "weapon_use": dict(self.weapon_use),
            "technique": [self.readied, self.tech_rest],
            "talents": list(self.talents),
            "prey": dict(self.prey),
            "talent_offers": [list(o) for o in self.talent_offers],
            "quests": self.quests,
            "rank": self.rank,
        }

    @classmethod
    def from_dict(cls, data: dict, catalogue: Catalogue, x: int = 0, y: int = 0) -> "Player":
        stats = Stats.from_dict(data)
        inventory = Inventory.from_list(data.get("inventory", []), catalogue,
                                        carry_slots(stats["physicality"]))
        player = cls(x=x, y=y, char=PLAYER_GLYPH, color=PLAYER_COLOR, name=data.get("name", "Nameless"),
                     stats=stats, inventory=inventory, shards=data.get("shards", 0),
                     faints_allowed=data.get("faints_allowed", 1), gender=data.get("gender", ""))
        for sid, entry in data.get("skills", {}).items():
            rank, practice = (entry, 0) if isinstance(entry, int) else entry
            player.skills[sid] = SkillState(rank, practice)
        player.known_artifacts = set(data.get("known_artifacts", []))
        player.read_writings = set(data.get("read_writings", []))
        player.notes = data.get("notes", {})
        player.studied = dict(data.get("studied", {}))
        player.artifact_uses = dict(data.get("artifact_uses", {}))
        slots = data.get("artifact_slots", [])
        count = data.get("artifact_slot_count", max(3, len(slots)))
        player.artifact_slots = [Item(catalogue[i]) if i else None for i in slots] + [None] * (count - len(slots))
        player.flags = set(data.get("flags", []))
        dues = list(data.get("dues", [0, 0])) + [0]
        player.earned, player.dues_owed, player.earned_free = dues[0], dues[1], dues[2]
        player.jobs = work_jobs_from_list(data.get("jobs", []))
        player.torch_turns, player.torch_light = data.get("torch", [0, 0])
        player.meal_turns, player.meal_heal = data.get("meal", [0, 0])
        player.injuries = injuries.from_list(data.get("injuries", []))
        if "age" in data:
            player.join_age, player.born, player.judgments_seen = data["age"]
        else:
            player.join_age = data.get("join_age", 0)
        player.hunts_done = data.get("hunts_done", 0)
        player.weapon_use = dict(data.get("weapon_use", {}))
        player.readied, player.tech_rest = data.get("technique", [None, 0])
        from game import talents as _t
        renamed = {"jodebris_sense": "windcatcher_efficient"}    # (v0.64.1, user: few can sense Jodebris)
        player.talents = [renamed.get(t, t) for t in data.get("talents", []) if renamed.get(t, t) in _t.pool()]
        player.talent_offers = [[renamed.get(t, t) for t in o] for o in data.get("talent_offers", [])]
        player.prey = dict(data.get("prey", {}))
        player.quests = data.get("quests", {})
        player.rank = data.get("rank", 0)
        if player.injuries:
            hp = stats.hp
            injuries.apply_to_stats(player)
            stats.hp = min(hp, stats.max_hp)
        if "hunter_id" in data:
            player.hunter_id = data["hunter_id"]
        if "equipment" in data:                    # v0.69.0: equipment out of the bag
            for slot, entry in data["equipment"].items():
                item = Item.from_entry(entry, catalogue)
                if slot == "armor":                # v0.75.0: armour by slot; what was "armour" is chest
                    slot = player.slot_for(item)
                player.equipped[slot] = item
        for item_id in data.get("equipped", []):   # older saves and player.json: equipped things are in the bag
            item = next((i for i in inventory.items if i.type.id == item_id and not player.is_equipped(i)), None)
            if item is None:
                raise ValueError(f"Equipped {item_id!r} isn't in the inventory")
            player.equip(item)                      # (moves it out of the bag)
        hp = stats.hp
        player.gear_changed()                       # (armour tiers' max HP; v0.75.0)
        stats.hp = min(hp, stats.max_hp)
        return player
