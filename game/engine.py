"""The Engine holds the game state and runs one turn at a time."""
from __future__ import annotations

import json
import random
import textwrap

import numpy as np

from game import fieldskills, weaponskills
from game import camera, fov
from game.actions import Action
from game.hunt import Contract, Hunt, Region, make_contracts
from pathlib import Path

from game.items import Catalogue, Inventory, set_known
from game.skills import load_skills
from game.calendar import Calendar
from game.player import Player
from game.game_map import GameMap
from game.tiles import SYMBOL_TO_INDEX, VOID
from game.version import VERSION

MAX_LOG = 500   # message history kept (m shows it); the side panel shows the newest
SIDEBAR_WIDTH = 24  # the info panel on the right, in cells
TEXT = (233, 223, 204)
DIM = (150, 138, 122)
PANEL_BG = (16, 14, 12)
RULE = (58, 52, 46)
HP_GOOD = (190, 70, 60)
KEEPER_COLOR = (240, 200, 120)  # shopkeepers and other townsfolk
VERSION_COLOR = (100, 92, 82)
HP_LOW = (240, 120, 40)
SHARD = (150, 220, 210)  # pale sea-glass
JODEBRIS = (120, 190, 235)      # the Chorus Winds, stored in a windcatcher
JODEBRIS_LOW = (90, 110, 160)
TORCH = (240, 150, 70)
DATE = (215, 190, 150)
INJURY = (220, 150, 110)

# Torchlight: full brightness near the player, fading to DARKEST at LIGHT_RADIUS.
LIGHT_RADIUS = 12.0
DARKEST = 0.5
# How far you can see in fog-of-war areas (in columns; rows count double).
FOV_RADIUS = {"dark": LIGHT_RADIUS, "lit": 30.0}
# Remembered (seen before, not in view now) cells: dim and cool.
MEMORY_TINT = np.array([0.42, 0.45, 0.55])
# Creatures.
STEPS = [(0, -1), (0, 1), (-1, 0), (1, 0)]   # four-way movement: no diagonal steps (v0.41.0)
DAZE_TURNS = 8          # a mirebellow's bellow (v0.49.0): accuracy and evasion -2 for this long
TRAIL_TURNS = 40        # how long an ashmantle's ash stays hot
BURROW_TURNS = 6        # a gravel wyrm stays under at most this long...
SURFACE_TURNS = 3       # ...and up this long before it burrows again


def t_opens(m) -> str:
    return m.type.opens

WANDER_CHANCE = 0.25    # chance an unaware creature shuffles about each turn
MONSTER_PATIENCE = 12   # turns a creature keeps hunting you after losing sight
MONSTER_TRACKING = 40   # how many steps away a creature can follow you
# Cells are twice as tall as they are wide, so a step up or down covers more
# screen than a step sideways. This keeps the light round on screen.
CELL_ASPECT = 2.0
ACCENT_PANEL = (230, 160, 80)
RANK_COLOR = (232, 196, 100)      # the rank beside the level (v0.73.0)
WORK_DONE = (140, 205, 120)       # a bounty done, a contract's prize in hand
MIN_LOG_ROWS = 4                  # the panel keeps at least this many rows for messages (v0.73.0)
TRACK_GLYPH, TRACK_COLOR = "\"", (200, 140, 80)   # a creature's tracks (Tracking)
MARKED_FG, MARKED_BG = (255, 214, 90), (120, 26, 26)   # a bounty's marked creature
STASH_SLOTS = 60   # the guild stash (a stack takes one slot)
DATA = Path(__file__).resolve().parent.parent / "data"



class Wound:
    """What brings a Hunter down when it's bleeding or poison, not a creature."""
    def __init__(self, kinds) -> None:
        poison = "poisoned" in kinds and "bleeding" not in kinds
        self.name = "poison" if poison else "blood loss"
        self.knocks = "The poison overcomes you." if poison else "You pass out from blood loss."
        self.struck = "The poison overcame you." if poison else "You lost too much blood."
        self.kills = "The poison kills you." if poison else "You bleed to death."
        self.epitaph = "{name} died of poison" if poison else "{name} bled to death"


def talents_total(player, key: str) -> int:
    from game import talents
    return talents.total(player, key)

def recovery_owner(c) -> str:
    from game import recovery
    return recovery.owner(c.recover["name"])


class Engine:
    def __init__(self, game_map: GameMap, player: Player, catalogue: Catalogue,
                 regions: dict[str, Region] | None = None,
                 monster_types: dict | None = None, new_hunter=None, saves=None,
                 shops: dict | None = None, workshops: dict | None = None,
                 skills: dict | None = None, calendar: Calendar | None = None,
                 townsfolk: dict | None = None) -> None:
        self.game_map = game_map
        self.player = player
        self.catalogue = catalogue
        from game.keywords import PlaceBook, load_places
        # The places the Wayfinder's keywords lead to (game/keywords.py; v0.44.0).
        self.regions = regions if isinstance(regions, PlaceBook) else load_places(DATA / "keywords.json")
        self.words: set = set(self.regions.keywords.start)   # keywords known (world state)
        self.gate_info = {k: v for k, v in json.loads((DATA / "gates.json").read_text(encoding="utf-8")).items()
                          if not k.startswith("_")}
        self.monster_types = monster_types or {}
        if catalogue is not None and self.monster_types:
            from game import trophies
            trophies.register(catalogue, self.monster_types)   # a trophy for every body (v0.61.0)
        if catalogue is not None:
            from game import fishing as _fishing
            _fishing.bind(catalogue)                     # a fish item for every kind of fish (v0.94.0)
        self.fishing = None                              # a line in the water (game/fishing.py)
        self.fishing_last = None                         # (x, y, bait) of the last cast
        self.angling = {}                                # world state: worm digging (v0.94.0)
        if catalogue is not None:
            from game import gear as _gear
            _gear.set_catalogue(catalogue)               # (material values for gear worth, v0.76.0)
        self.trophies = {"records": {}, "curios": {}}   # the trophy wall (world state, v0.61.0)
        self.lost = []          # lost Hunters' packs, for recovery contracts (world state, v0.85.0)
        from game import lost_grounds          # hand-built places at particular words (v0.87.0)
        lost_grounds.load(keywords=getattr(regions, "keywords", None))
        self.new_hunter = new_hunter     # makes a fresh Player, after a death
        self.rng = random.Random()
        self.turn = 0
        self.day = 1                     # moves on after every hunt
        from game import sky
        sky.watch(self)                  # the Duel decides which places under the open sky are lit (v0.93.0)
        self.messages: list[str] = []
        self.logged = 0                      # messages logged so far (a running count)
        self.screen = None               # a screen open over the map, like the inventory
        self.city = game_map             # the persistent city, kept while you're away
        self.hunt: Hunt | None = None    # the hunt in progress, if any
        self.city_return = (player.x, player.y)  # where you'll be back in the city
        self.city_start = (player.x, player.y)   # the guild hall, where Hunters start (for travel-to)
        self.visible = None              # what the player can see (fog-of-war maps)
        self.saves = saves               # the SaveSystem, if saving is on
        self.shops = shops or {}
        if townsfolk is None and shops is not None:
            from game.dialogue import load_townsfolk
            townsfolk = load_townsfolk(DATA / "townsfolk.json")
        self.townsfolk = townsfolk or {}
        if workshops is None and shops is not None:
            from game.artifacts import load_workshops
            workshops = load_workshops(DATA / "workshops.json")
        self.workshops = workshops or {}
        self.shops_given = shops is not None
        self.skills = skills if skills is not None else load_skills(DATA / "skills.json")
        self.calendar = calendar if calendar is not None else Calendar(DATA / "calendar.json")
        self.guild = json.loads((DATA / "guild.json").read_text(encoding="utf-8"))
        self.work = json.loads((DATA / "work.json").read_text(encoding="utf-8"))
        from game.crafting import load_recipes
        self.recipes = load_recipes(DATA / "recipes.json", catalogue)
        self.orders: list = []   # commissions with crafters (world state)
        from game import archive
        self.library: list = []          # writings shelved in the Academy library (world state; game/library.py)
        self.hall: list = []             # the Hall of Hunters: every Hunter who retired or died (world state)
        self.mentor: dict | None = None  # the latest retired Hunter, teaching in the guild hall (world state)
        self.mentor_spot = None          # where the mentor stands (from the city map)
        self.passing = False             # a Hunter has just died of old age (stops time until the card)
        self.heavy_step = False          # the last action was a step (Gravity, v0.70.0)
        self.mud_step = False            # ...onto mud or reeds (v0.86.0)
        self.disengaged = set()          # creatures you stepped away from with Runner's (v0.86.0)
        from game import story
        import os
        # quests, scenes, story talk and key hunts (data/story/*.json); TAG_NO_STORY=1 runs without
        # the story (the balance bot, and tests of other things)
        self.story_data = story.StoryData(None if os.environ.get("TAG_NO_STORY") else story.DATA)
        from game import lost_grounds
        lost_grounds.check_story(self.story_data)     # no key hunt at a Lost Ground's words (v0.87.1)
        self.story = story.empty()           # story progress (world state; game/story.py)
        self.scene_queue: list = []          # scenes waiting for the screen to be free
        self.story_event: dict = {}          # the event being handled (for event: conditions)
        self.rivals: list = []               # rival Hunters (world state; game/rivals.py)
        self.next_rival_id = 0
        self.rival_taken: dict = {"day": 0, "taken": {}}   # contracts rivals took off today's boards
        self.rival_spots: list = []          # where rivals at home stand in the guild hall
        self.archive = archive.empty()   # the Guild archive: bestiary and scouting (world state; game/archive.py)
        self.reset_work()
        self.reset_stocks()
        self.started = False             # becomes True once a game is begun or loaded
        self.stash = Inventory(STASH_SLOTS)  # the guild stash: belongs to the hall, passes to the next Hunter
        self.home = None                     # a Hunter's home (v0.74.0, game/homes.py): world state too
        self.sites, self.site, self.site_return, self.site_items = {}, None, None, {}   # (game/sites.py)
        self.stocks: dict = {}               # vendor id -> Stock (shops and workshops); world state
        self.world_flags: set = set()        # conversation flags that belong to the city (outlive Hunters)
        self.explore_seen_items: set = set() # spots auto-explore has already walked to (this area)
        game_map.place_items(catalogue)
        self.place_npcs(game_map)
        self.city_items_at_start = [(f.x, f.y, f.item.type.id, f.item.count) for f in game_map.items]
        self.update_fov()

    @property
    def player(self) -> Player:
        return self._player

    @player.setter
    def player(self, player: Player) -> None:
        # Item names follow what this Hunter has identified.
        self._player = player
        set_known(player.known_artifacts, player.read_writings)
        from game import aging
        if player.born is None:          # a new Hunter: born join_age Pulses before today
            player.born = getattr(self, "day", 1) - player.join_age
            player.judgments_seen = aging.total_judgments(player.join_age)
        if hasattr(self, "day"):
            aging.refresh(self, log=False)

    def reset_stocks(self) -> None:
        """Every shop and workshop fully stocked, as at the start of a new game."""
        from game.stock import Stock
        self.stocks = {sid: Stock.from_data(shop.stock, self.catalogue, self.day) for sid, shop in self.shops.items()}
        self.stocks.update({wid: Stock.from_data(w.sells, self.catalogue, self.day)
                            for wid, w in self.workshops.items()})

    def stock(self, vendor_id: str):
        """A vendor's stock, restocked for the Pulses that have passed."""
        if vendor_id not in self.stocks:  # a vendor added to the data after this save was made
            from game.stock import Stock
            entries = self.shops[vendor_id].stock if vendor_id in self.shops else self.workshops[vendor_id].sells
            self.stocks[vendor_id] = Stock.from_data(entries, self.catalogue, self.day)
        stock = self.stocks[vendor_id]
        stock.catch_up(self.day)
        return stock

    @property
    def date(self):
        """Today on the calendar (game/calendar.py)."""
        return self.calendar.date(self.day)

    def next_day(self, pulses: int = 1) -> None:
        """Time passes: a Pulse for each move between areas, a Cycle for a
        completed hunt. Contracts change; Duels and holidays are announced."""
        for _ in range(pulses):
            self.day += 1
            note = self.calendar.turning_point(self.day)
            if note:
                self.log(note)
            d = self.date
            if not d.intercalary and d.reckon == 1 and d.cycle == 1 and d.pulse_number == 1:
                self.assess_dues()   # the first Pulse of each Judgment
            from game import crafting, injuries, work
            work.refresh(self)
            from game import contests             # the WAG's fishing contests (v0.100.0)
            contests.refresh(self)
            crafting.deliver_orphans(self)
            for message in injuries.mend(self.player, self.day):
                self.log(message)
            from game import rest
            rest.passed(self, 1, getattr(self, "rest_rate", rest.NATURAL))    # the rest owed (v0.88.0)
            if not self.in_brisering():           # (v0.92.0) the caravans keep moving while you're elsewhere
                from game import caravans
                caravans.tick(self, caravans.data()["per_pulse"], walking=False)
            from game import aging, story
            aging.refresh(self)
            if self.passing:
                break
            story.fire(self, "pulse")
            from game import rivals
            rivals.day(self)

    def reset_work(self) -> None:
        """A fresh job board and requests (a new game)."""
        from game import work
        self.next_work_id = 0
        self.job_board, self.requests = [], []
        self.jobs_posted = self.requests_posted = -10 ** 6
        if self.townsfolk:
            work.refresh(self)

    def on_kill(self, monster) -> None:
        if monster.type.person:               # someone on the road (game/road.py, v0.90.0)
            from game import road
            road.on_kill(self, monster)
            return
        from game import mastery
        mastery.note_kill(self.player, monster.type.id)     # knowing your prey (v0.59.0)
        # (kills practised Tracking until v0.64.0; user: it rose much too fast. Entering areas does.)
        if monster.type.burst:            # it bursts (lantern tick): everything beside it is burned
            from game import combat
            dmg = combat.roll(monster.type.burst)
            self.log(f"The {monster.name} bursts in a gout of flame!")
            from game import sound
            sound.play("burst")
            for other in list(self.game_map.monsters):
                if max(abs(other.x - monster.x), abs(other.y - monster.y)) <= 1 and not other.type.ghost:
                    other.take_damage(dmg)
                    if other.hp <= 0:
                        self.game_map.monsters.remove(other)
            p = self.player
            if max(abs(p.x - monster.x), abs(p.y - monster.y)) <= 1:
                p.stats.hp -= dmg
                self.log(f"The flames catch you for {dmg}.")
                if p.stats.hp <= 0:
                    self.player_down(monster)
        from game import work
        work.on_kill(self, monster)
        from game import trophies, talents as _tal
        if _tal.total(self.player, "pulping") and monster.type.drops:   # Pulping (a trait, v0.81.0)
            from game.items import FloorItem, Item
            for _ in range(2):
                for item_id, n in trophies.materials(self, monster.type, self.rng):
                    self.game_map.items.append(FloorItem(monster.x, monster.y, Item(self.catalogue[item_id], n)))
        else:
            trophies.leave_corpse(self, monster, self.rng)   # its body, not loose materials (user, v0.61.0)
        from game import archive, story
        archive.note_kill(self, monster)
        story.fire(self, "kill", monster=monster.type.id,
                   region=self.hunt.contract.region.id if self.hunt else "")

    def assess_dues(self) -> None:
        """The first Pulse of a Judgment: the Guild's share of what this Hunter earned is owed."""
        p = self.player
        if p.dues_owed > 0 and p.rank > 0 and not p.labouring:   # still owing from the last: a rank lost
            from game import ranks
            p.rank -= 1
            self.log(f"You still owe the Guild from the last dues. You're demoted to {ranks.name(p.rank)}.")
        share = self.dues_share
        due = int(p.earned * share)
        p.earned = p.earned_free = 0
        if due <= 0:
            self.log("A new Judgment. You earned nothing since the last, so the Guild asks no dues.")
            return
        p.dues_owed += due
        self.log(f"A new Judgment: the Guild's dues are {due} shards ({round(share * 100)}% of what you earned). "
                 "Pay the clerk at the guild hall; the contract boards are closed to you until you do.")

    @property
    def dues_share(self) -> float:
        """The Guild's share of earnings (Guild Darling takes points off, v0.58.0)."""
        from game import talents
        return max(0.0, self.guild.get("dues_share", 0.2) - talents.total(self.player, "dues") / 100)

    @property
    def dues_so_far(self) -> int:
        """What the next dues would be, if they fell due now."""
        return int(self.player.earned * self.dues_share)

    def pay_dues(self) -> str:
        """Pay what you can of what you owe (from a conversation with the clerk)."""
        p = self.player
        paid = min(p.shards, p.dues_owed)
        p.shards -= paid
        if paid:
            from game import sound
            sound.play("pay")
        p.dues_owed -= paid
        from game import works
        works.dues_paid(self, paid)                # dues fund the Guild's works (v0.60.0)
        if p.dues_owed:
            return f"You pay {paid} shards. You still owe the Guild {p.dues_owed}."
        return f"You pay {paid} shards. Your dues are paid; the contract boards are open to you."

    @property
    def light_radius(self) -> float:
        """How far torchlight (and sight, in dark places) reaches."""
        return LIGHT_RADIUS + self.player.light_bonus

    @property
    def vision_range(self) -> float:
        """How far you can see, in cells (rows count double): light in dark places,
        full sight in lit places, less any injury that hurts sight. Field of view uses it,
        and the look and aim cursors can't go beyond it."""
        gm = self.game_map
        base = self.light_radius if gm.light == "dark" else FOV_RADIUS.get(gm.light, FOV_RADIUS["lit"])
        from game import injuries
        from game import talents
        if self.hunt is not None and gm is not self.city:      # a place where light reaches less far (v0.67.0)
            base *= getattr(self.hunt.contract.region, "sight", 1.0)
        return max(2.0, base + injuries.total(self.player, "sight") + talents.total(self.player, "sight"))

    def in_vision(self, x: int, y: int) -> bool:
        """Is (x, y) within your vision range? (Range only: walls still block what you see.)"""
        p = self.player
        return (x - p.x) ** 2 + ((y - p.y) * CELL_ASPECT) ** 2 <= self.vision_range ** 2

    def camera_focus(self) -> tuple[int, int]:
        """What the camera follows: the look or aim cursor while one is open, else you."""
        from game.screens import LookScreen
        if hasattr(self.screen, "focus"):          # fishing keeps you and your line in view (v0.100.4)
            return self.screen.focus(self)
        if isinstance(self.screen, LookScreen):
            return self.screen.x, self.screen.y
        return self.player.x, self.player.y

    def log(self, message: str) -> None:
        from game import named
        message = named.fix(message)       # "Knif the Swift misses you", not "The Knif the Swift..." (v0.86.0)
        self.messages.append(message)
        self.logged += 1  # a running count, so auto-explore can tell when something was said
        del self.messages[:-MAX_LOG]

    # ---- Walking on its own: auto-explore and travel-to, watched step by step (v0.65.0, user) ----
    animate_walks = False     # main.py turns it on; tests and the bot walk all at once
    walking = None            # the walk under way (a generator: one step each time it's advanced)
    WALK_STEP_DELAY = 0.06    # seconds between steps (about 16 a second)

    def start_walk(self, steps) -> None:
        self.walking = steps
        self.walk_step()          # the first step at once (or the reason it can't start)

    def walk_step(self) -> None:
        """One step of the walk under way, then what follows any action (scenes, talents)."""
        if self.walking is None:
            return
        try:
            next(self.walking)
        except StopIteration:
            self.walking = None
        if self.screen is not None or (self.player and self.player.stats.is_dead):
            self.walking = None
        self.handle_action(None)

    def stop_walk(self) -> None:
        """A key was pressed: stop where you are."""
        if self.walking is not None:
            self.walking.close()
            self.walking = None

    def handle_action(self, action: Action | None) -> None:
        if action is not None:
            p = self.player                  # (Braced, v0.78.0: was the last action a step?)
            p.stepped_last, p.stepped_now = p.stepped_now, False
        if action is not None and action.perform(self):
            self.turn += 1
            self.end_turn()
        self.update_fov()
        from game import story
        if self.story_data.quests:
            story.check(self)
        story.show_next_scene(self)
        from game import talents
        talents.show_offer(self)          # a talent earned: the choice, once nothing else is up

    def update_fov(self) -> None:
        """Work out what the player can see now (fog-of-war maps only)."""
        gm = self.game_map
        if gm.fog:
            radius = self.vision_range
            self.visible = fov.compute(gm.transparent, self.player.x, self.player.y, radius, CELL_ASPECT)
            gm.explored |= self.visible

    def end_turn(self) -> None:
        """Everything that happens after the player acts. A step in a place whose words slow you
        (Gravity, v0.70.0: `Region.time`) lets that many turns pass, the extra ones counted too."""
        times = 1
        if getattr(self, "heavy_step", False) and self.hunt is not None:
            from game import talents
            times = max(1, getattr(self.hunt.contract.region, "time", 1))
            if talents.total(self.player, "no_heavy"):            # Tireless (a trait, v0.77.0)
                times = 1
        if getattr(self, "mud_step", False) and self.hunt is not None:
            times += 1                    # mud and reeds drag at you: a step takes another turn (v0.86.0)
        self.heavy_step = self.mud_step = False
        hunt, player = self.hunt, self.player
        for n in range(times):
            if n:
                if self.hunt is not hunt or self.player is not player or player.stats.is_dead:
                    break                    # (the hunt ended, or the Hunter fell, on the turn before)
                self.turn += 1
            self._end_turn_once()
            self.disengaged = set()       # Runner's covers the turn you step away, no more (v0.86.0)

    def _end_turn_once(self) -> None:
        """Everything that happens after the player acts: creatures take
        their turns (later also hunger, status effects and so on)."""
        self.update_fov()
        p = self.player
        weaponskills.tick(p)
        if p.dazed:
            p.dazed -= 1
            if not p.dazed:
                self.log("Your head clears.")
        gm = self.game_map
        from game import throwing
        throwing.tick(self)              # smoke thins, a lure fades (v0.82.0)
        if gm.trails:                    # ash cools
            for cell in list(gm.trails):
                gm.trails[cell] -= 1
                if gm.trails[cell] <= 0:
                    del gm.trails[cell]
        if self.in_brisering():          # walking the Brisering takes time (data/brisering.json)
            # Distance, not steps (user, v0.50.2): a cell is 0.5 km across but 1 km down, so a step
            # north or south counts double. Waiting or stepping east/west counts one.
            p = self.player
            last = getattr(self, "_bris_last", None)
            vertical = last is not None and last[0] is gm and last[1] == p.x and last[2] != p.y
            before = getattr(self, "bris_steps", 0)
            from game import travel as _tr          # (v0.90.0: open country is slower than the roads)
            moved = last is not None and last[0] is gm and (last[1], last[2]) != (p.x, p.y)
            self.bris_steps = before + (_tr.step_cost(gm, p.x, p.y, vertical) if moved else 1)
            self._bris_last = (gm, p.x, p.y)
            from game import talents
            per = int(self.bris_settings["steps_per_pulse"] * (1 + talents.total(p, "brisering_steps") / 100))
            for _ in range(int(self.bris_steps // per - before // per)):
                self.next_day()
            if last is not None and last[0] is gm and (last[1], last[2]) != (p.x, p.y):
                from game import road
                road.maybe(self)             # people on the road (v0.90.0)
            from game import caravans
            caravans.tick(self, 1, walking=True)   # the Towerway's caravans move as you do (v0.92.0)
        else:
            self._bris_last = None
        self.monsters_act()
        self.townsfolk_act()
        if self.player.is_dead:
            return
        from game import injuries
        _, messages = injuries.tick(self.player, self.game_map is self.city)
        for message in messages:
            self.log(message)
        if self.player.is_dead:
            self.player_down(Wound(injuries.bleeding(self.player) or ["bleeding"]))
            return
        p = self.player
        if getattr(p, "venom", 0) and self.hunt is not None:    # a Venomous creature's poison (v0.83.0)
            p.venom -= 1
            from game import talents as _tal
            every = 4 if _tal.total(p, "poison_resist") else 2
            if p.venom % every == 0:
                p.stats.take_damage(1)
                if p.is_dead:
                    self.player_down(Wound(["poisoned"]))
                    return
        elif getattr(p, "venom", 0):
            p.venom = 0
        self.player.regenerate()
        for message in self.player.tick_supplies():
            self.log(message)
        if self.hunt is not None and self.hunt.race:
            from game import rivals
            rivals.tick(self)
        if self.player.in_miasma:
            from game.artifacts import DRAIN_PER_TURN, drain
            for message in drain(self.player, DRAIN_PER_TURN):
                self.log(message)

    # ---- Creatures ----------------------------------------------------------
    def monsters_act(self) -> None:
        gm, p = self.game_map, self.player
        if not gm.monsters:
            return
        from game import talents as _tal
        if _tal.total(p, "ringing") and self.hunt is not None:       # Ringing (a trait, v0.81.0): they all hear you
            for m in gm.monsters:
                if abs(m.x - p.x) + abs(m.y - p.y) <= 6:
                    m.awake = True
        steps_to_player = None
        for m in list(gm.monsters):
            if self.game_map is not gm or p.is_dead:
                return  # you fainted or died: the rest don't get a turn
            dx, dy = p.x - m.x, p.y - m.y
            sees = (self.visible is not None and self.visible[m.x, m.y]
                    and dx * dx + (dy * CELL_ASPECT) ** 2 <= m.type.sight ** 2)
            if (self.visible is not None and self.visible[m.x, m.y] and not m.type.person
                    and m.type.id not in p.notes.get("seen", [])):
                from game import archive
                archive.note_sighting(self, m)   # you saw it: a note for the Guild archive
            if self.visible is not None and self.visible[m.x, m.y] and not getattr(m, "spotted", False):
                from game import talents as _tal
                fear = _tal.total(p, "fearsome")              # Fearsome (a trait): it hesitates
                if fear and self.rng.randint(1, 100) <= fear:
                    m.staggered = max(m.staggered, 1)
                    self.log(f"The {m.name} sees you and hesitates.")
                if getattr(m, "named", ""):
                    self.log(f"That's {m.name}. The Guild knows this one by name.")
                m.spotted = True                 # the story hears of each creature the first time it's seen
                from game import story
                story.fire(self, "see", monster=m.type.id, marked=bool(getattr(m, "bounty", 0)))
            if sees and not m.awake and not fieldskills.notices(self, m):
                sees = False                     # it looks your way and doesn't see you (Stealth)
            if sees:
                if not m.awake:
                    m.awake = True
                    if m.type.behaviour == "hunt":
                        self.log(f"{m.name} notices you." if m.named else f"A {m.name} notices you.")
                        from game import sound
                        sound.play("creature_alert", gap=4.0)
                    from game import named
                    if m.type.calls or named.has(m, "caller"):      # it raises the alarm (v0.83.0)
                        named.call(self, m)
                m.turns_unseen = 0
            elif m.awake:
                m.turns_unseen += 1
                if m.turns_unseen > MONSTER_PATIENCE:
                    m.awake = False

            if sees and t_opens(m) == "daze" and not m.opened and talents_total(self.player, "daze_immune"):
                m.opened = True                          # Stubborn (a trait, v0.77.0): you can't be dazed
                self.log(f"The {m.name} lets out a booming bellow. You stand your ground.")
            if sees and t_opens(m) == "daze" and not m.opened:   # (v0.49.0) its opening: a bellow that dazes
                m.opened = True
                # Tenacity shakes it off sooner (v0.57.0): a turn less per point above 10, 3 at least
                ten = self.player.stats["tenacity"]
                from game import talents                  # (Clear-Headed: sooner still)
                turns = max(3, DAZE_TURNS - max(0, ten - 10)) - talents.total(self.player, "daze_resist")
                self.player.dazed = max(self.player.dazed, max(1, turns))
                self.log(f"The {m.name} lets out a booming bellow. You're dazed!")
                from game import sound
                sound.play("daze")
            if getattr(m, "bleeding", 0):           # Rend (game/weaponskills.py)
                m.bleeding -= 1
                m.hp -= weaponskills.REND_DAMAGE
                if m.is_dead:
                    self.log(f"The {m.name} bleeds out.")
                    self.slay(m)
                    continue
            if getattr(m, "poisoned", 0):           # poison from a trait (v0.81.0): 1 every other turn
                m.poisoned -= 1
                if m.poisoned % 2 == 0:
                    m.hp -= 1
                    if m.is_dead:
                        self.log(f"The {m.name} succumbs to the poison.")
                        self.slay(m)
                        continue
            if getattr(m, "slowed", 0):             # slowed (Bonebreaker): it acts every other turn
                m.slowed -= 1
                if m.slowed % 2:
                    continue
            if getattr(m, "held", 0):               # Snare: it can't move (it can still fight)
                m.held -= 1
                m.holding = True
            else:
                m.holding = False
            if getattr(m, "staggered", 0):          # Stagger, Throw: it loses this turn
                m.staggered -= 1
                continue
            m.ticks += 1
            turns = 2 if m.speed == "quick" else (m.ticks % 2 if m.speed == "slow" else 1)
            for _ in range(turns):
                if self.game_map is not gm or p.is_dead or m not in gm.monsters:
                    break
                if m.awake and steps_to_player is None:
                    steps_to_player = self.distances_from(p.x, p.y)
                before = (m.x, m.y)
                self.monster_turn(m, steps_to_player)
                if (m.x, m.y) != before:
                    m.charged = abs(m.x - p.x) + abs(m.y - p.y) == 1     # it just closed in (v0.81.0)
                    self.set_strike(m)

    def monster_turn(self, m, steps_to_player) -> None:
        """One creature's action: attack, close in, or one of its own ways (v0.49.0)."""
        gm, p = self.game_map, self.player
        t = m.type
        from game import throwing
        dest = throwing.lured(self, m)                # a lure draws it (v0.82.0)
        if dest is not None:
            key = (dest, self.turn)
            if getattr(self, "_lure_key", None) != key:
                self._lure_key, self._lure_dist = key, self.distances_from(*dest)
            if (m.x, m.y) != dest:
                self.step_monster(m, self._lure_dist)
            return
        dx, dy = p.x - m.x, p.y - m.y
        near = abs(dx) + abs(dy)
        if t.ghost:                       # never fights; keeps its distance; leaves ash behind it
            if m.awake and steps_to_player is not None:
                old = (m.x, m.y)
                if near > 3:
                    self.step_monster(m, steps_to_player)
                elif near < 2:
                    self.step_away(m, steps_to_player)
                if (m.x, m.y) != old and t.trail:
                    gm.trails[old] = TRAIL_TURNS
            elif self.rng.random() < WANDER_CHANCE:
                ddx, ddy = self.rng.choice(STEPS)
                self.try_move_monster(m, m.x + ddx, m.y + ddy)
            return
        if t.burrows and m.awake:          # under the ground it closes in; up, it fights; then down again
            if m.burrowed:
                if near == 1 or m.phase >= BURROW_TURNS:
                    m.burrowed, m.phase = False, 0
                    self.log(f"The ground heaves: a {m.name} surfaces!")
                    return
                m.phase += 1
                self.step_monster(m, steps_to_player)
                return
            m.phase += 1
            if m.phase > SURFACE_TURNS:
                m.burrowed, m.phase = True, 0
                self.log(f"The {m.name} sinks back under the ground.")
                return
        from game import talents as _tal
        flee_at = max(t.flees, _tal.total(p, "make_flee") / 100 if m.touched else 0)   # (Tamer's)
        if getattr(m, "fleeing", 0) and steps_to_player is not None:
            m.fleeing -= 1                           # frightened (Cracking): it runs
            self.step_away(m, steps_to_player)
            return
        if flee_at and m.awake and m.hp <= flee_at * t.hp and steps_to_player is not None:
            self.step_away(m, steps_to_player)       # losing: it runs
            return
        if t.opens == "leap" and m.awake and not m.opened and steps_to_player is not None and 1 < near <= 4:
            spot = min(((p.x + sx, p.y + sy) for sx, sy in STEPS
                        if gm.in_bounds(p.x + sx, p.y + sy) and gm.is_walkable(p.x + sx, p.y + sy)
                        and not gm.monster_at(p.x + sx, p.y + sy) and not gm.npc_at(p.x + sx, p.y + sy)
                        and abs(p.x + sx - m.x) + abs(p.y + sy - m.y) <= 3),
                       key=lambda c: abs(c[0] - m.x) + abs(c[1] - m.y), default=None)
            if spot:
                m.opened = True
                m.x, m.y = spot
                self.log(f"The {m.name} leaps out at you!")
                return
        if near == 1 and (m.awake or t.behaviour == "still") and not t.ghost:   # side by side, not corners
            self.monster_attacks(m)
        elif getattr(m, "holding", False):
            return                          # snared: it can't move (v0.78.0)
        elif t.behaviour == "still" or (t.swims and gm.tile_at(m.x, m.y).symbol == "~" and not m.opened):
            return                          # (a swimmer waits in the water until it leaps)
        elif m.awake and steps_to_player is not None:
            self.step_monster(m, steps_to_player)
        elif self.rng.random() < WANDER_CHANCE:
            ddx, ddy = self.rng.choice(STEPS)
            self.try_move_monster(m, m.x + ddx, m.y + ddy)

    def set_strike(self, m) -> None:
        """Set (Polearms 3, v0.78.0): a creature that steps into reach takes a free strike, once."""
        p, gm = self.player, self.game_map
        if (m not in gm.monsters or m.set_done or m.type.ghost or m.burrowed or p.is_dead
                or not weaponskills.has_passive(p, "polearms") or not weaponskills.in_reach(self, m)):
            return
        from game import combat
        m.set_done = True
        from game import talents
        back = combat.resolve(p, m, self.rng, rolls=1 + talents.total(p, "set_rolls"))
        weaponskills.practise(self, back.hit)
        if not back.hit:
            self.log(f"You set your spear, but miss the {m.name}.")
        elif back.killed:
            self.log(f"You set your spear: the {m.name} runs onto it and dies.")
            self.slay(m)
        else:
            self.log(f"You set your spear: the {m.name} runs onto it ({back.damage}).")

    def step_away(self, m, dist) -> None:
        """Move one step further from the player, if a free cell is."""
        best, best_d = None, dist[m.x, m.y]
        for ddx, ddy in STEPS:
            nx, ny = m.x + ddx, m.y + ddy
            if (0 <= nx < dist.shape[0] and 0 <= ny < dist.shape[1] and best_d < dist[nx, ny] < 10_000
                    and not self.game_map.monster_at(nx, ny) and not self.game_map.npc_at(nx, ny)):
                best, best_d = (nx, ny), dist[nx, ny]
        if best:
            m.x, m.y = best

    def slay(self, m) -> None:
        """A creature the Hunter killed (by a blow, a technique or bleeding): off the map, the kill's
        effects, experience."""
        if m in self.game_map.monsters:
            self.game_map.monsters.remove(m)
        self.on_kill(m)
        from game import talents
        p = self.player
        if talents.total(p, "heal_on_kill") and p.stats.hp < p.stats.max_hp:   # Bloodthirst
            p.stats.heal(talents.total(p, "heal_on_kill"))
        if getattr(m, "bleeding", 0) and talents.total(p, "bleed_kill_heal"):   # Bloodthirst (the claw trait)
            p.stats.heal(talents.total(p, "bleed_kill_heal"))
        xp = round(m.type.xp * (2 if getattr(m, "named", "") else 1) * (1 + talents.total(p, "xp") / 100))
        from game import sound
        sound.play("kill")
        if p.stats.gain_xp(xp):
            self.log(f"You feel stronger. You are now level {p.stats.level}.")
            sound.play("level_up")
            talents.check(self)

    def monster_attacks(self, m) -> None:
        from game import combat, talents
        if id(m) in getattr(self, "disengaged", ()):        # Runner's (a leg trait, v0.86.0): you slipped away
            self.log(f"The {m.name} can't catch you as you slip away.")
            return
        parry = talents.total(self.player, "parry")          # Parrying (a trait, v0.77.0)
        if parry and self.rng.randint(1, 100) <= parry:
            self.log(f"You turn the {m.name}'s attack aside.")
            return
        if m.fumble:                                         # Disarming, Hooked (traits, v0.81.0)
            m.fumble = False
            self.log(f"The {m.name}'s attack goes wide.")
            return
        self.player.bracing = talents.total(self.player, "brace_armour") if m.charged else 0   # Bracing
        m.charged = False
        result = combat.resolve(m, self.player, self.rng)
        self.player.bracing = 0
        from game import sound
        sound.play("hurt" if result.hit else "creature_miss")
        if result.hit and not result.killed:
            from game import named
            if named.has(m, "venomous"):                   # (v0.83.0)
                self.player.venom = max(getattr(self.player, "venom", 0), named.VENOM_TURNS)
                self.log("Its venom burns in the wound.")
            top = m.type.hp * 3 // 2 if named.has(m, "hulking") else m.type.hp
            if named.has(m, "bloodthirsty") and m.hp < top:
                m.hp = min(top, m.hp + 2)
        if not result.hit:
            self.log(f"The {m.name} misses you.")
            self.player.rhythm += talents.total(self.player, "rhythm")      # Rhythm (a trait)
            counter = talents.total(self.player, "counter")              # Counterpunch (a trait, v0.78.0)
            if counter and not m.type.ghost and not m.burrowed and self.rng.randint(1, 100) <= counter:
                back = combat.resolve(self.player, m, self.rng)
                if back.killed:
                    self.log(f"You counter and kill the {m.name}.")
                    self.slay(m)
                    return
                self.log(f"You counter: {'you hit the ' + m.name + f' for {back.damage}' if back.hit else 'you miss'}.")
            if weaponskills.has_passive(self.player, "blades") and not m.type.ghost and not m.burrowed:
                back = combat.resolve(self.player, m, self.rng,          # Riposte: you strike back at once
                                      accuracy=talents.total(self.player, "riposte_accuracy"))
                weaponskills.practise(self, back.hit)
                if not back.hit:
                    self.log(f"You riposte, but miss the {m.name}.")
                elif back.killed:
                    self.log(f"You riposte and kill the {m.name}.")
                    self.slay(m)
                else:
                    self.log(f"You riposte: you hit the {m.name} for {back.damage}.")
            return
        self.log(f"The {m.name} hits you for {result.damage}.")
        from game import injuries
        hurt = injuries.roll_injury(self.player, m.type, result.damage, self.day, self.rng)
        if hurt:
            self.log(f"The blow leaves you with {'' if hurt.name.endswith('s') else 'a '}{hurt.name}! "
                     f"({hurt.effect_text()})")
        from game import talents
        p = self.player
        if talents.total(p, "after_hit_accuracy"):
            p.vengeance = True                   # Vengeful: your next blow
        if not result.killed and talents.total(p, "thorns_back") and m in self.game_map.monsters:   # Thorned
            m.take_damage(talents.total(p, "thorns_back"))
            if m.is_dead:
                self.log(f"The {m.name} tears itself on your armour and dies.")
                self.slay(m)
        if (not result.killed and talents.total(p, "second_wind") and not p.second_wind_used
                and self.hunt is not None and p.stats.hp * 4 < p.stats.max_hp):
            p.second_wind_used = True            # Second Wind: once a hunt
            gained = p.stats.heal(p.stats.max_hp // 3)
            self.log(f"Second wind! You steady yourself. (+{gained} HP)")
        if result.killed:
            self.player_down(m)

    def step_monster(self, m, dist: np.ndarray) -> None:
        """Move one step closer to the player, if a free cell is closer."""
        best, best_d = None, dist[m.x, m.y]
        for ddx, ddy in STEPS:
            nx, ny = m.x + ddx, m.y + ddy
            if (0 <= nx < dist.shape[0] and 0 <= ny < dist.shape[1] and dist[nx, ny] < best_d
                    and not self.game_map.monster_at(nx, ny) and not self.game_map.npc_at(nx, ny)
                    and (nx, ny) != (self.player.x, self.player.y)):
                best, best_d = (nx, ny), dist[nx, ny]
        if best:
            m.x, m.y = best
        elif getattr(m.type, "flanks", False) and dist[m.x, m.y] > 1:
            self.flank(m)                         # the way's blocked: go round (v0.83.0)

    def flank(self, m) -> None:
        """A flanker whose way to you is blocked by another creature looks for another way round: the
        shortest path that treats the other creatures as walls, if there is one (and not too long)."""
        gm, p = self.game_map, self.player
        blocked = {(o.x, o.y) for o in gm.monsters if o is not m}
        dist = {(p.x, p.y): 0}
        frontier = [(p.x, p.y)]
        steps = 0
        while frontier and steps < 30 and (m.x, m.y) not in dist:
            steps += 1
            nxt = []
            for cx, cy in frontier:
                for ddx, ddy in STEPS:
                    nx, ny = cx + ddx, cy + ddy
                    if ((nx, ny) not in dist and gm.in_bounds(nx, ny) and gm.is_walkable(nx, ny)
                            and ((nx, ny) == (m.x, m.y) or ((nx, ny) not in blocked and not gm.npc_at(nx, ny)
                                 and gm.tile_at(nx, ny).symbol not in "<>H"))):
                        dist[(nx, ny)] = steps
                        nxt.append((nx, ny))
            frontier = nxt
        here = dist.get((m.x, m.y))
        if here is None:
            return
        for ddx, ddy in STEPS:
            c = (m.x + ddx, m.y + ddy)
            if dist.get(c, 10_000) < here and c not in blocked and c != (p.x, p.y):
                m.x, m.y = c
                return

    def try_move_monster(self, m, nx: int, ny: int) -> None:
        gm = self.game_map
        over_water = m.type.flies and gm.in_bounds(nx, ny) and gm.tile_at(nx, ny).symbol == "~"
        if ((gm.is_walkable(nx, ny) or over_water) and not gm.monster_at(nx, ny) and not gm.npc_at(nx, ny)
                and (nx, ny) != (self.player.x, self.player.y)):
            if gm.tile_at(nx, ny).symbol not in "<>H":  # creatures don't use the passages
                if not m.type.flies and not m.type.swims and not m.type.ghost:
                    fieldskills.leave_track(self, m.x, m.y)        # tracks (Tracking, v0.56.0)
                m.x, m.y = nx, ny

    def distances_from(self, x: int, y: int) -> np.ndarray:
        """Steps from (x, y) to every cell creatures can walk on (large = unreachable)."""
        gm = self.game_map
        walk = gm.walkable.copy()
        for sym in "<>H":  # creatures don't stand on the passages
            walk &= gm.kinds != SYMBOL_TO_INDEX[sym]
        dist = np.full(walk.shape, 10_000, dtype=np.int32)
        dist[x, y] = 0
        frontier = [(x, y)]
        steps = 0
        while frontier and steps < MONSTER_TRACKING:
            steps += 1
            nxt = []
            for cx, cy in frontier:
                for ddx, ddy in STEPS:
                    nx, ny = cx + ddx, cy + ddy
                    if 0 <= nx < walk.shape[0] and 0 <= ny < walk.shape[1] and walk[nx, ny] and dist[nx, ny] > steps:
                        dist[nx, ny] = steps
                        nxt.append((nx, ny))
            frontier = nxt
        return dist

    # ---- Fainting and death -------------------------------------------------
    def player_down(self, killer) -> None:
        from game.screens import TitleCardScreen
        p, hunt = self.player, self.hunt
        if hunt and self.faints_left() > 0:
            hunt.faints_used += 1
            p.stats.hp = p.stats.max_hp
            self.travel(0, arrive_at="entry")
            left = self.faints_left()
            self.log(getattr(killer, "knocks", f"The {killer.name} knocks you out.") + " You come to at the trail home.")
            self.screen = TitleCardScreen("Knocked out", [
                (getattr(killer, "struck", f"The {killer.name} struck you down."), TEXT),
                ("You come to at the trail home, battered but alive.", DIM), ("", TEXT),
                (f"Faints left on this hunt: {left}" if left else
                 ("One more fall, and it's over." if hunt.faints_earned >= p.faint_limit
                  else "One more fall before you find a new area, and it's over."),
                 TEXT if left else HP_LOW),
            ])
            return
        where = hunt.contract.region.name if hunt else self.game_map.title
        self.log(getattr(killer, "kills", f"The {killer.name} kills you."))
        from game import aging
        aging.record(self, p, getattr(killer, "cause", f"killed by a {killer.name} in {where}"))
        from game import story
        story.rescue(self)
        from game import recovery
        recovery.on_death(self, hunt)        # their pack stays where they fell (v0.85.0)
        story.end_hunt(self, hunt)
        if hunt and hunt.contract.story:
            story.contract_over(self, hunt.contract, False)
        from game import rivals
        rivals.end_race(self, hunt)
        story.fire(self, "death")
        if self.saves:  # permadeath: this Hunter's saves go with them
            self.saves.delete_hunter(p.hunter_id)
        if hunt is None and self.in_brisering():      # (user, v0.89.0) found on the road, brought home
            from game import journey
            heading, found = journey.death_lines(self, p)
            self.screen = TitleCardScreen(heading, [(t, TEXT) for t in found] + [("", TEXT),
                (f"{p.name} died on the way home, on {self.date.short}, having seen "
                 f"{aging.describe(aging.age_of(p, self.day))}.", TEXT), ("", TEXT),
                ("A new Hunter takes up the work.", DIM),
            ], on_continue=lambda e: e.start_new_hunter())
            return
        self.screen = TitleCardScreen("Fallen", [
            (getattr(killer, "epitaph", f"{p.full_name} was killed by a {killer.name}").format(name=p.full_name), TEXT),
            (f"in {where},", TEXT), (f"on {self.date.short},", TEXT),
            (f"having seen {aging.describe(aging.age_of(p, self.day))}.", TEXT), ("", TEXT),
            ("A new Hunter takes up the work.", DIM),
        ], on_continue=lambda e: e.start_new_hunter())

    def die_of_old_age(self) -> None:
        """A Hunter's years run out (game/aging.py), at home or out on a hunt."""
        from game import aging
        from game.screens import TitleCardScreen
        p = self.player
        age = aging.describe(aging.age_of(p, self.day))
        where = "out on a hunt" if self.hunt else "at home in Bytorsskug"
        self.log(f"{p.name}'s years have run out.")
        aging.record(self, p, "died of old age " + ("on a hunt" if self.hunt else "at home"))
        from game import story
        story.rescue(self)
        from game import recovery
        recovery.on_death(self, self.hunt)
        story.end_hunt(self, self.hunt)
        if self.hunt and self.hunt.contract.story:
            story.contract_over(self, self.hunt.contract, False)
        story.fire(self, "death")
        p.stats.hp = 0
        self.passing = True
        if self.saves:
            self.saves.delete_hunter(p.hunter_id)
        self.screen = TitleCardScreen("Passed away", [
            (f"{p.full_name} died of old age", TEXT), (f"{where}, on {self.date.short},", TEXT),
            (f"having seen {age}.", TEXT), ("", TEXT), ("A new Hunter takes up the work.", DIM),
        ], on_continue=lambda e: e.start_new_hunter())

    def retire(self) -> None:
        """The Hunter retires (from the clerk): what they carry goes to the stash, their shards to the
        next Hunter, their name to the Hall of Hunters, and they stay on in the hall to teach."""
        from game import aging
        from game.screens import TitleCardScreen
        p = self.player
        left = []
        things = p.all_items()              # (bag, equipment and artifact slots; v0.69.0)
        for item in things:
            if not self.stash.add(item):
                left.append(item.type.name)
        gift = p.shards
        aging.record(self, p, "retired")
        from game import story
        story.fire(self, "retire")
        self.mentor = aging.mentor_from(p)
        if self.saves:
            self.saves.delete_hunter(p.hunter_id)
        lines = [(f"{p.full_name} retires from the hunt,", TEXT),
                 (f"having seen {aging.describe(aging.age_of(p, self.day))}.", TEXT), ("", TEXT),
                 ("Their gear goes to the guild stash" + (" (what fits)." if left else "."), DIM)]
        if gift:
            lines.append((f"Their {gift} shards go to the next Hunter.", DIM))
        if self.mentor["skills"]:
            lines.append(("They'll stay on in the guild hall to teach.", DIM))
        self.screen = TitleCardScreen("Retired", lines, on_continue=lambda e: e.start_new_hunter(gift))

    def vanish_hunter(self) -> None:
        """"New Hunter" from the title menu (user, v0.51.1): the current Hunter simply vanishes.
        No place in the Hall, no gift, and what they carried is lost; the world stays as it is.
        (Retiring at the clerk is the way to leave properly.) Story items they carried still go
        to the stash, so the story can't be lost with them (my call)."""
        p, hunt = self.player, self.hunt
        from game import story, rivals
        story.rescue(self)
        story.end_hunt(self, hunt)
        if hunt and hunt.contract.story:
            story.contract_over(self, hunt.contract, False)
        rivals.end_race(self, hunt)
        self.screen = None
        self.start_new_hunter()

    def update_mentor(self) -> None:
        """Put the latest retired Hunter in the guild hall (or take the old one away)."""
        from game.dialogue import Townsperson
        from game.entity import NPC
        city = self.city
        city.npcs = [n for n in city.npcs if n.folk_id != "mentor"]
        if not self.mentor or self.mentor_spot is None or "mentor" not in self.townsfolk:
            return
        base = self.townsfolk["mentor"]
        given, *rest = self.mentor["name"].split(" ")
        middle, surname = (rest + ["", ""])[:2]
        folk = Townsperson("mentor", given, middle, surname, base.glyph, base.color,
                           "A retired Hunter, who teaches what they know for less than the trainer.", base.dialogue)
        self.townsfolk["mentor"] = folk
        x, y = self.mentor_spot
        city.npcs.append(NPC(x, y, folk.glyph, folk.color, folk.full_name, folk_id="mentor", home=(x, y), wander=0))

    def start_new_hunter(self, gift: int = 0) -> None:
        """After a death or a retirement: a new Hunter in the same world, the next day."""
        from game import aging
        self.hunt = None
        self.passing = False
        self.update_mentor()
        self.player = self.new_hunter()
        self.player.shards += gift
        from game import works
        if works.active("loaner"):                 # the armoury's loaner gear (v0.60.0)
            works.lend(self)
        self.change_map(self.city, self.player.x, self.player.y)
        self.messages.clear()
        self.next_day()
        p = self.player
        self.log(f"{self.date.short}. A new Hunter, {p.full_name}, joins the Guild, "
                 f"having seen {aging.describe(aging.age_of(p, self.day))}."
                 + (f" They start with the {gift} shards their predecessor left." if gift else ""))
        from game import story
        story.story_so_far(self)        # where the world's story stands, for the new Hunter (v0.66.0)
        story.fire(self, "new_hunter")
        self.autosave()

    # ---- New games and saving ---------------------------------------------------
    def new_game(self) -> None:
        """A fresh world and a fresh Hunter (from the title menu)."""
        from game.items import FloorItem, Item
        self.hunt = None
        self.day, self.turn = 1, 0
        self.city.items = [FloorItem(x, y, Item(self.catalogue[i], n)) for x, y, i, n in self.city_items_at_start]
        self.stash = Inventory(STASH_SLOTS)
        self.home = None
        self.sites, self.site, self.site_return, self.site_items = {}, None, None, {}
        self.reset_stocks()
        self.world_flags = set()
        self.words = set(self.regions.keywords.start)
        if getattr(self, "_brisering", None) is not None:   # a new world: the Brisering unexplored
            self._brisering.explored[:] = False
            self.reveal_landmarks()
        self.bris_steps = 0
        self.reset_work()
        self.orders = []
        from game import archive
        self.library = []
        self.archive = archive.empty()
        self.hall, self.mentor, self.passing = [], None, False
        from game import works
        self.works = works.fresh()                 # the Guild's works (v0.60.0)
        from game import trophies
        self.trophies = trophies.fresh()           # the trophy wall (v0.61.0)
        self.lost = []                             # lost Hunters' packs (v0.85.0)
        self.wilds = {}                            # what's been foraged, and heard at camps (v0.91.0)
        self.angling = {}                          # fishing's world state (v0.94.0)
        self.caravans = {}                         # the Towerway's caravans (v0.92.0)
        self.road = {}                             # people met on the road (v0.90.0)
        works.apply(self)
        from game import homes
        homes.furnish_all(self)
        from game import story
        self.story, self.scene_queue = story.empty(), []
        self.rivals = []
        self.update_mentor()
        self.player = self.new_hunter()
        from game import rivals
        rivals.start_cast(self)
        rivals.place_in_hall(self)
        self.change_map(self.city, self.player.x, self.player.y)
        self.city_return = (self.player.x, self.player.y)
        self.messages.clear()
        self.log(f"It is {self.date.long}.")
        from game import aging
        self.log(f"You are {self.player.full_name}, a new Hunter, having seen "
                 f"{aging.describe(aging.age_of(self.player, self.day))}.")
        self.log("You stand in the guild hall. Contracts are posted on the board here; "
                 "hunts leave from the Wayfinder.")
        self.log("Press ? for the keys, l for past messages, m for the map.")
        if any(n.folk_id == "clerk" for n in self.city.npcs):
            self.log("The guild clerk works from the window at the back of the hall, if you have questions.")
        if any(n.folk_id == "supplier" for n in self.city.npcs):
            self.log("The supplier keeps a shop on the edge of the plaza.")
        if any(n.folk_id == "artificer" for n in self.city.npcs):
            self.log("Bring what you find to the artificer's workshop, near the plaza.")
        if any(n.folk_id == "smith" for n in self.city.npcs):
            self.log("The smith, east of the plaza, makes gear to order from what creatures leave behind.")
        self.screen = None
        self.started = True
        story.fire(self, "new_game")
        story.show_next_scene(self)
        self.autosave()

    @property
    def can_save_here(self) -> bool:
        return self.hunt is None and self.game_map.safe

    def autosave(self) -> None:
        """Save to the autosave slot, if there's a game worth saving."""
        if self.saves is None or not self.started or self.player.is_dead:
            return
        try:
            self.saves.write("autosave", self)
        except OSError as err:
            self.log(f"Autosave failed: {err}")

    def cam_shows(self, x: int, y: int) -> bool:
        """Is (x, y) on screen right now? (True before the first frame.)"""
        cam = getattr(self, "cam", None)
        return cam is None or cam.to_screen(x, y) is not None

    # ---- People --------------------------------------------------------------
    def place_npcs(self, game_map: GameMap) -> None:
        from game.entity import NPC
        if self.shops_given is False:
            return  # no shop data loaded (tools and tests); leave people out
        for x, y, role in game_map.npc_spawns:
            if role == "mentor":            # the latest retired Hunter, if any (update_mentor)
                self.mentor_spot = (x, y)
                continue
            if role == "rival":             # rival Hunters at home (game/rivals.py)
                self.rival_spots.append((x, y))
                continue
            folk = self.townsfolk.get(role)
            if folk is None:
                raise ValueError(f"{game_map.name}: no one called {role!r} in townsfolk.json (NPC at {x},{y})")
            game_map.npcs.append(NPC(x, y, folk.glyph, folk.color, folk.full_name,
                                     folk_id=role, home=(x, y), wander=folk.wander))
        game_map.npc_spawns = []

    # The window open over the map. A property (v0.63.0) so opening one can make its sound.
    @property
    def screen(self):
        return self.__dict__.get("_screen")

    @screen.setter
    def screen(self, value) -> None:
        old = self.__dict__.get("_screen")
        self.__dict__["_screen"] = value
        if value is not None and value is not old:
            from game import sound
            sound.on_screen(value)

    def talk_to(self, npc) -> None:
        """Start a conversation (no time passes)."""
        from game.dialogue import Talk, load_conversation
        from game.screens import DialogueScreen
        folk = self.townsfolk[npc.folk_id]
        self.talk_folk = npc.folk_id           # (who's being talked to: a caravan's choices need it, v0.92.0)
        from game import story
        if npc.folk_id == "clerk":            # back with what the contract asked for: report it (v0.89.0)
            from game import journey
            journey.report(self)
        story.fire(self, "talk", folk=npc.folk_id)   # the story may have something to say first (v0.54.0)
        if self.scene_queue:
            story.show_next_scene(self)
            return
        talk = Talk(self, folk, load_conversation(DATA / "dialogue", folk.dialogue))
        talk.begin()
        self.screen = DialogueScreen(talk)
        if talk.done:  # a node that opened a screen straight away
            self.screen.finish(self)

    def open_vendor(self, what: str) -> None:
        """Open a shop, workshop or the stash (from a conversation)."""
        from game.screens import ShopScreen, StashScreen, TrainingScreen, WorkshopScreen
        kind, _, vid = what.partition(":")
        if kind == "train":
            self.screen = TrainingScreen(vid.split(","))
        elif kind == "mentor":
            self.screen = TrainingScreen(sorted(self.mentor["skills"]) if self.mentor else [], mentor=self.mentor)
        elif kind == "teach":                 # a story mentor (Selda, v0.67.0): townsfolk.json "teaches", "discount"
            folk = self.townsfolk.get(vid)
            raw = (folk.extra or {}) if folk else {}
            teaches = raw.get("teaches", {})
            self.screen = TrainingScreen(list(teaches), mentor={"given": folk.given if folk else vid,
                                                                "skills": teaches, "pay": 1 - raw.get("off", 0.2)})
        elif kind in ("trophies", "butcher"):  # the trophymaster and the butcher (v0.61.0)
            from game.screens import TrophyScreen
            self.screen = TrophyScreen("butcher" if kind == "butcher" else "trophymaster")
        elif kind == "trophy_wall":
            from game import trophies
            from game.screens import ScrollScreen
            self.screen = ScrollScreen.of_lines("The trophy wall", trophies.wall_lines(self))
        elif kind in ("fish_weigh", "fish_book"):   # the tackleman's record book (v0.99.0)
            from game import catches
            from game.screens import ScrollScreen
            self.screen = (ScrollScreen.of_lines("Weighed for the book", catches.weigh(self)) if kind == "fish_weigh"
                           else ScrollScreen.of_lines("The record book", catches.book_lines(self)))
        elif kind in ("contest_weigh", "contest_past"):   # the contests (v0.100.0)
            from game import contests
            from game.screens import ScrollScreen
            self.screen = (ScrollScreen.of_lines("Weighed for the contest", contests.weigh_in(self))
                           if kind == "contest_weigh" else ScrollScreen.of_lines("The contest book", contests.past_lines(self)))
        elif kind == "homes":                  # the property dealer (v0.74.0)
            from game.screens import HomesScreen
            self.screen = HomesScreen(self)
        elif kind == "works":                  # the Guild's works (v0.60.0)
            from game.screens import WorksScreen
            self.screen = WorksScreen()
        elif kind == "hall":
            from game.screens import HallScreen
            self.screen = HallScreen()
        elif kind == "sit_rank":
            from game import ranks
            rank0 = self.player.rank
            self.log(ranks.sit(self))
            if self.player.rank > rank0:      # (v0.64.0, user: more fanfare) a card, and the clerk's word later
                self.screen = ranks.rank_card(self, rank0)
                self.player.flags.add("rank_congrats")
        elif kind == "labour":
            from game import ranks
            from game.screens import ConfirmScreen
            n = ranks.labour_pulses(self.player)
            self.screen = ConfirmScreen(f"Work off the {self.player.dues_owed} shards you owe? It will take {n} "
                                        f"Pulse{'s' if n != 1 else ''} of Guild labour.",
                                        on_yes=lambda e: e.log(ranks.labour(e)))
        elif kind == "retire":
            from game.screens import ConfirmScreen
            self.screen = ConfirmScreen(f"Retire {self.player.full_name}? Their hunting is over; a new Hunter "
                                        "takes their place.", on_yes=lambda e: e.retire())
        elif kind == "jobs":
            from game.screens import JobBoardScreen
            self.screen = JobBoardScreen()
        elif kind == "craft":
            from game.screens import CraftScreen
            self.screen = CraftScreen(vid)
        elif kind == "maps":
            from game.screens import MapsScreen
            self.screen = MapsScreen()
        elif kind == "caravan":                # (v0.92.0) a caravan on the Towerway
            from game import caravans
            caravans.act(self, vid)
        elif kind == "upgrade":
            from game.screens import UpgradeScreen
            self.screen = UpgradeScreen(at="smith", title="The smith: raise a piece", only="gear")
        elif kind == "upgrade_tackle":         # (v0.96.0) the tackleman raises tackle
            from game.screens import UpgradeScreen
            self.screen = UpgradeScreen(at="tackleman", title="The tackleman: raise your tackle", only="tackle")
        elif kind == "library":
            from game.screens import LibraryScreen
            self.screen = LibraryScreen()
        elif kind == "archive":
            from game.screens import ArchiveScreen
            self.screen = ArchiveScreen()
        elif kind == "treat":
            from game.screens import TreatScreen
            self.screen = TreatScreen(vid)
        elif kind == "shop":
            self.screen = ShopScreen(self.shops[vid])
        elif kind == "workshop":
            self.screen = WorkshopScreen(self.workshops[vid])
        else:
            self.screen = StashScreen()

    def townsfolk_act(self) -> None:
        """People who wander drift about near home. They keep off doors and gates."""
        gm = self.game_map
        for n in gm.npcs:
            if n.wander <= 0 or self.rng.random() > 0.3:
                continue
            dx, dy = self.rng.choice(STEPS)
            nx, ny = n.x + dx, n.y + dy
            if (max(abs(nx - n.home[0]), abs(ny - n.home[1])) > n.wander or not gm.is_walkable(nx, ny)
                    or gm.tile_at(nx, ny).symbol in "+G" or (nx, ny) in gm.gates
                    or (nx, ny) == (self.player.x, self.player.y) or gm.npc_at(nx, ny) or gm.monster_at(nx, ny)):
                continue
            n.x, n.y = nx, ny

    # ---- Places and hunts -------------------------------------------------
    def change_map(self, game_map: GameMap, x: int, y: int) -> None:
        self.fishing = None                       # (a line in the water stays behind)
        self.game_map = game_map
        self.explore_seen_items = set()
        self.player.x, self.player.y = x, y
        self.player.in_miasma = (self.hunt is not None        # hunts lie out beyond the Chorus Winds
                                 or str(getattr(self, "site", None) or "").startswith("lost:"))   # and Lost Grounds (v0.87.0)
        self.player.in_light = getattr(game_map, "light", "") == "lit"     # (Brimmed)
        p_ = self.player
        p_.area_kills, p_.coil_used, p_.kick_used, p_.streak = 0, False, False, 0   # (once-an-area traits)
        p_.vault_used = False                                                       # (Pole-vault, v0.86.0)
        if not self.player.in_miasma:
            from game.artifacts import refill
            refill(self.player)  # back in the Brisering: windcatchers fill up
            if self.player.torch_turns:
                self.player.torch_turns = self.player.torch_light = 0  # put out at the gate
        if game_map is getattr(self, "_brisering", None):
            from game import caravans
            caravans.place(self)              # the Towerway's caravans, where they've got to (v0.92.0)
        self.update_fov()

    def on_step(self, from_x: int, from_y: int) -> None:
        """Called after the player moves onto a cell: gates, ways on, the trail home."""
        p, gm = self.player, self.game_map
        gate_id = gm.gates.get((p.x, p.y))
        if gate_id is not None:
            from game import sites
            if sites.here(self):            # out of Ingenfjel or the stead, back onto the Brisering (v0.74.0)
                sites.leave(self)
            else:
                self.gate_reached(gate_id, from_x, from_y)
            return
        from game import talents as _tal
        if (p.x, p.y) in gm.trails and self.hunt is not None and not _tal.total(p, "ash_immune"):   # ash (Ash-walker: no)
            from game import combat
            burn = combat.roll(next((m.type.trail for m in gm.monsters if m.type.trail), "1d3"))
            p.stats.hp -= burn
            self.log(f"The hot ash burns you for {burn}.")
            if p.stats.hp <= 0:
                from types import SimpleNamespace
                self.player_down(SimpleNamespace(name="ashmantle's ash"))
                return
        if self.hunt is None:
            return
        symbol = gm.tile_at(p.x, p.y).symbol
        if symbol == ">":
            self.travel(self.hunt.current + 1, arrive_at="entry")
            self.log("You press on, deeper.")
        elif symbol == "<":
            self.travel(self.hunt.current - 1, arrive_at="far_end")
            self.log("You head back the way you came.")
        elif symbol == "H":
            self.reach_trail_home()

    # ---- The Brisering (v0.46.0; the travel map outside the gates) ----------------------------
    @property
    def brisering(self) -> GameMap:
        """The Brisering travel map: persistent, loaded the first time it's needed."""
        if getattr(self, "_brisering", None) is None:
            self._brisering, _ = GameMap.from_file(DATA / "maps" / "brisering.txt")
            self.bris_settings = json.loads((DATA / "brisering.json").read_text(encoding="utf-8"))
            self.reveal_landmarks()
        return self._brisering

    def reveal_landmarks(self) -> None:
        """Myligast is infinitely tall (lore): it can be seen from anywhere in the Brisering."""
        b = self._brisering
        b.explored |= b.kinds == SYMBOL_TO_INDEX["M"]

    def in_brisering(self) -> bool:
        return getattr(self, "_brisering", None) is not None and self.game_map is self._brisering

    def city_inside(self, gate_id: str) -> tuple[int, int]:
        """The street cell just inside one of the city's gates (where you come back in)."""
        gate = next(pos for pos, g in self.city.gates.items() if g == gate_id)
        from game.explore import STEPS
        from collections import deque
        seen, q = {self.city_start}, deque([self.city_start])
        while q:                                   # the gate's neighbour nearest the guild hall
            c = q.popleft()
            for dx, dy in STEPS:
                n = (c[0] + dx, c[1] + dy)
                if n == gate:
                    return c
                if n not in seen and self.city.in_bounds(*n) and self.city.is_walkable(*n) and n not in self.city.gates:
                    seen.add(n)
                    q.append(n)
        return self.city_start

    def gate_reached(self, gate_id: str, from_x: int | None = None, from_y: int | None = None) -> None:
        """A gate: out of the city into the Brisering (user, 2026-11-19), or back in."""
        g = self.gate_info.get(gate_id, {"name": "gate", "toward": "the Brisering"})
        if self.game_map is self.city:
            bris = self.brisering
            x, y = bris.arrivals[gate_id]
            self.change_map(bris, x, y)
            self.log(f"You pass out through the {g['name']} into the Brisering: {g['toward']}.")
        else:
            x, y = self.city_inside(gate_id)
            from game import road, caravans
            road.clear(self)                  # (anyone left on the road stays there, v0.90.0)
            caravans.abandoned(self)          # (a guard who goes into the city leaves their caravan)
            self.change_map(self.city, x, y)
            self.log(f"You come back into Bytorsskug through the {g['name']}.")
            from game import journey
            c = journey.reportable(self)
            if c is not None:                 # (v0.89.0) the contract is done when the clerk hears it
                self.log(f"Report the contract to the guild clerk: {c.title(self.catalogue)}.")
        self.autosave()

    def open_contracts(self) -> None:
        """The Guild's contracts board, in the guild hall (game/postings.py)."""
        from game.screens import ContractBoardScreen
        from game import postings, rivals
        if self.player.dues_owed > 0:
            self.log(f"The contracts board is closed to you: you owe the Guild {self.player.dues_owed} shards "
                     "in dues. Pay the clerk. (The bounty board and the Wayfinder are still open to you.)")
            return
        if self.rival_taken.get("day") != self.day:
            self.rival_taken = {"day": self.day, "taken": {}}
        taken = {}
        for seed, rid in self.rival_taken["taken"].items():
            r = rivals.by_id(self, rid)
            taken[int(seed)] = rivals.full_name(r) if r else "another Hunter"
        self.screen = ContractBoardScreen(None, postings.board(self), taken)

    def open_artifact(self) -> None:
        """Walk into the Wayfinder: choose three words (game/keywords.py). Rest owed is settled first:
        rest it off here, or set out weary (game/rest.py, v0.88.0)."""
        from game.screens import ArtifactScreen
        from game import story, rest
        story.fire(self, "wayfinder")          # a word from the story first, if it has one (v0.54.0)
        go = lambda e: rest.at_wayfinder(e, lambda e2: setattr(e2, "screen", ArtifactScreen(e2)))
        if self.scene_queue:
            self.after_scenes = go
            story.show_next_scene(self)
            return
        go(self)

    def set_out(self, words: tuple[str, str, str]) -> None:
        """Through the Wayfinder to the place the words make: the Hunter's contract,
        if it's for this place, or a trip of their own."""
        from game import keywords, postings
        from game.hunt import trip
        from game.screens import departure_card
        words = keywords.resolve(self, words, self.rng)
        keywords.learn(self, list(words))
        place = self.regions.place(*words)
        from game import lost_grounds
        ground = lost_grounds.at_place(place.id)
        if ground:                                 # a Lost Ground (roadmap step 5, v0.87.0): never a hunt (user)
            lost_grounds.enter(self, ground)
            return
        contract = postings.matches(self, place) or trip(place, self.catalogue, self.rng)
        self.screen = departure_card(contract, self)

    def begin_hunt(self, contract: Contract) -> None:
        from game import library, story
        writings = library.plan_hunt(self, contract)   # (before the new hunt exists: what's lying about now)
        story_items = story.plan_hunt(self, contract)
        self.hunt = Hunt(contract, self.monster_types)
        self.hunt.writings = writings
        self.hunt.story_items = story_items
        self.player.second_wind_used = False      # (the Second Wind talent: once a hunt)
        from game import rest as _rest
        _rest.begin(self)                         # set out weary? (v0.88.0)
        from game import work
        self.hunt.bounties = work.bounties_for(self, contract.region)
        self.hunt.carried_at_start = self.player.inventory.count_of(contract.artifact_id)
        self.player.artifact_uses.clear()  # working artifacts recover between hunts
        from game import rivals
        rivals.maybe_race(self, contract)
        self.travel(0, arrive_at="entry")
        self.log(f"You step into the Wayfinder, and it carries you out onto the Overland: {contract.region.name}.")
        story.fire(self, "set_out", region=contract.region.id)

    def travel(self, index: int, arrive_at: str) -> None:
        hunt = self.hunt
        first = index > 0 and hunt.areas[index] is None     # a new area: it earns a faint (user, v0.82.0)
        area = hunt.area(index, self.catalogue)
        if area.npc_spawns:          # someone waiting out here (a key hunt's person, v0.67.0)
            if self.player.inventory.count_of(hunt.contract.artifact_id):
                area.npc_spawns = []                      # (already being carried home)
            else:
                self.place_npcs(area)
        hunt.current = index
        from game import maps
        maps.reveal(self, area)          # a bought map: the area starts revealed (v0.84.0)
        self.next_day()  # a Pulse for every move from one area to another
        from game import archive, work
        work.on_area(self, index)
        archive.note_area(self, index)
        fieldskills.on_area(self, index)
        w = self.player.windcatcher                       # Attunement: travelling with Jodebris (v0.57.0)
        if self.hunt is not None and w is not None and w.jodebris > 0:
            from game import attunement
            attunement.practise(self)
        x, y = hunt.entries[index] if arrive_at == "entry" else hunt.far_ends[index]
        self.change_map(area, x, y)
        p = self.player
        if first and hunt.faints_earned < p.faint_limit:
            hunt.faints_earned += 1
            self.log(f"You've marked the way back: if you fall now, you'll be found. "
                     f"(Faints {self.faints_left()}/{p.faint_limit})")
        from game import story
        story.fire(self, "area", region=hunt.contract.region.id, area=index + 1)
        self.autosave()

    def faints_left(self) -> int:
        """Faints you can take on this hunt now: those earned (a new area each), less those used."""
        if self.hunt is None:
            return 0
        return max(0, min(self.hunt.faints_earned, self.player.faint_limit) - self.hunt.faints_used)

    def reach_trail_home(self) -> None:
        from game.screens import ConfirmScreen
        c = self.hunt.contract
        if self.player.inventory.count_of(c.artifact_id) > self.hunt.carried_at_start:
            self.finish_hunt(success=True)
        elif c.free:
            self.screen = ConfirmScreen(
                f"Head back to Bytorsskug? You haven't found what lies deepest here.",
                on_yes=lambda e: e.finish_hunt(success=False),
            )
        else:
            name = self.catalogue[c.artifact_id].name
            self.screen = ConfirmScreen(
                f"Return to the city without the {name}? You keep the contract, and can try again.",
                on_yes=lambda e: e.finish_hunt(success=False),
            )

    def finish_hunt(self, success: bool) -> None:
        """The hunt is over: out through the trail home. Since v0.89.0 (user) the Wayfinder is one way: the
        Hunter comes out at the edge of the Brisering and walks home (game/journey.py). A contract is
        complete only when it's reported to the clerk; a trip's find is simply theirs."""
        from game.screens import TitleCardScreen
        c = self.hunt.contract
        artifact = self.catalogue[c.artifact_id] if c.artifact_id else None
        from game import rivals, story, maps, journey
        maps.note(self)                       # scouted deeply enough? a report for the maps (v0.84.0)
        story.end_hunt(self, self.hunt)
        rivals.end_race(self, self.hunt)
        self.hunt = None
        where = journey.come_out(self, c.region, f"out:{c.region.id}")
        # A completed hunt takes a whole Cycle; turning back, a Pulse. The rest is owed (v0.88.0).
        from game import aging, rest as _rest
        if success and c.free:
            self.player.hunts_done += 1       # (a contract counts when it's reported)
        rest = aging.rest_pulses(self.player)
        fieldskills.practise(self, "survival", 2 if success else 1)    # every trip out there teaches a little
        _rest.end(self)                       # weariness lifts (v0.88.0)
        from game import wilds
        wilds.end_hunt(self)                  # being well fed wears off (v0.91.0)
        self.rest_rate = 0.0                  # (the hunt's own time pays no rest)
        try:
            self.next_day(self.calendar.per_cycle if success else 1)
        finally:
            self.rest_rate = _rest.NATURAL
        if self.passing:      # their years ran out on the way (the card is up)
            return
        _rest.add(self, rest)                 # the rest is owed, not passed (user, v0.88.0)
        rested = _rest.owed_line(self) + "."
        self.log(f"You come out of the miasma at {where}.")
        self.autosave()
        done_jobs = [(f"Done: {j.text(self)}", TEXT) for j in self.player.jobs if j.done]
        lines = [(f"You come out at {where}.", TEXT), ("", TEXT)]
        if success:
            the = "" if getattr(c, "prize_folk", "") else "the "      # (a person, v0.67.0)
            what = f"{recovery_owner(c)} pack" if c.recover else f"{the}{artifact.name}"
            if c.free:
                lines += [(f"Found: {artifact.name}. It's yours.", TEXT), ("", TEXT)]
            else:
                lines += [(f"You carry {what}. The contract is done when you report it to the guild clerk"
                           " in Bytorsskug.", TEXT), ("", TEXT)]
        else:
            lines += ([("You come back without the find.", TEXT)] if c.free
                      else [(f"{recovery_owner(c)} pack remains out there." if c.recover
                             else f"The {artifact.name} remains out there.", TEXT)]) + [("", TEXT)]
            if c.story:
                story.contract_over(self, c, False)
                lines += [("The key hunt stays posted on the Guild's board.", DIM), ("", TEXT)]
            elif not c.free:
                lines += [("The contract is still yours.", DIM), ("", TEXT)]
        lines += done_jobs + ([("", TEXT)] if done_jobs else [])
        lines += [(rested, DIM)]
        heading = ("Trip complete" if (success and c.free) else "Out of the miasma")
        self.screen = TitleCardScreen(heading, lines)
        story.fire(self, "home", success=success, region=c.region.id, free=c.free)

    # ---- Drawing ----------------------------------------------------------
    def render(self, console) -> None:
        console.clear(bg=VOID)
        gm = self.game_map

        # The info panel takes the right-hand side; the map gets the rest.
        view_w = console.width - SIDEBAR_WIDTH
        from game import hud
        top = hud.ROWS if self.hunt is not None else 0     # the hunt line takes the top row (v0.71.0)
        cam = camera.follow(*self.camera_focus(),
                            gm.width, gm.height, view_w, console.height - top)
        if top:
            import dataclasses
            cam = dataclasses.replace(cam, screen_y=cam.screen_y + top)
        self.cam = cam  # remembered for the look cursor
        view = console.rgb[cam.screen_x : cam.screen_x + cam.width,
                           cam.screen_y : cam.screen_y + cam.height]
        view[...] = gm.graphics[cam.map_x : cam.map_x + cam.width,
                                cam.map_y : cam.map_y + cam.height]

        # Tracks (Tracking, v0.56.0): where creatures have walked lately, where you can see.
        if self.hunt is not None and gm.tracks and self.visible is not None:
            for (tx, ty) in fieldskills.fresh_tracks(self):
                spot = cam.to_screen(tx, ty)
                if spot and self.visible[tx, ty]:
                    console.rgb["ch"][spot] = ord(TRACK_GLYPH)
                    console.rgb["fg"][spot] = TRACK_COLOR

        # Camps and foraging spots on the Brisering (v0.91.0), where you've seen them.
        from game import wilds
        for (wx, wy, glyph, colour) in wilds.overlay(self):
            spot = cam.to_screen(wx, wy)
            if spot and gm.explored[wx, wy]:
                console.rgb["ch"][spot] = ord(glyph)
                console.rgb["fg"][spot] = colour

        # Smoke from a smoke jar (v0.82.0).
        for (sx, sy) in gm.smoke:
            spot = cam.to_screen(sx, sy)
            if spot:
                console.rgb["ch"][spot] = ord("░")
                console.rgb["fg"][spot] = (170, 170, 175)

        # Items lying on the floor (drawn before the light, so they dim too).
        for floor_item in gm.items:
            spot = cam.to_screen(floor_item.x, floor_item.y)
            if spot:
                console.rgb["ch"][spot] = ord(floor_item.item.type.glyph)
                console.rgb["fg"][spot] = floor_item.item.type.color

        # People.
        for npc in gm.npcs:
            spot = cam.to_screen(npc.x, npc.y)
            if spot:
                console.rgb["ch"][spot] = ord(npc.char)
                console.rgb["fg"][spot] = npc.color

        # Hot ash (an ashmantle's trail), where you can see it.
        for (tx, ty) in gm.trails:
            spot = cam.to_screen(tx, ty)
            if spot and (not gm.fog or self.visible[tx, ty]):
                console.rgb["ch"][spot] = ord("░")
                console.rgb["fg"][spot] = (170, 120, 90)
        # Creatures, only where you can see them (something burrowing shows as a stir in the ground).
        for m in gm.monsters:
            spot = cam.to_screen(m.x, m.y)
            if spot and (not gm.fog or self.visible[m.x, m.y]):
                console.rgb["ch"][spot] = ord("°" if m.burrowed else m.char)
                console.rgb["fg"][spot] = (120, 110, 100) if m.burrowed else m.color
                if getattr(m, "bounty", 0) and not m.burrowed:      # a marked bounty: gold on red (v0.52.0)
                    console.rgb["fg"][spot] = MARKED_FG
                    console.rgb["bg"][spot] = MARKED_BG

        original = view.copy()  # before any dimming, for remembered cells

        if gm.light == "dark":
            # Dim each cell by its distance from the player.
            xs, ys = np.indices((cam.width, cam.height))
            dist = np.hypot(xs + cam.map_x - self.player.x,
                            (ys + cam.map_y - self.player.y) * CELL_ASPECT)
            light = np.clip(1.0 - (dist / self.light_radius) * (1.0 - DARKEST), DARKEST, 1.0)
            view["fg"] = (view["fg"] * light[..., None]).astype(np.uint8)
            view["bg"] = np.maximum(view["bg"] * light[..., None], VOID).astype(np.uint8)

        if gm.fog:
            self.apply_fog(gm, cam, view, original)

        spot = cam.to_screen(self.player.x, self.player.y)
        if spot:
            console.print(*spot, self.player.char, fg=self.player.color)

        hud.draw(self, console, view_w)
        self.render_sidebar(console, view_w)
        if self.screen is not None:
            self.screen.render(console, self, view_w)

    def apply_fog(self, gm: GameMap, cam, view, original) -> None:
        """Hide what you can't see. Places you've seen before stay on the map,
        drawn dim and colourless, as memory; places you haven't stay dark."""
        area = (slice(cam.map_x, cam.map_x + cam.width), slice(cam.map_y, cam.map_y + cam.height))
        visible, explored = self.visible[area], gm.explored[area]

        remembered = explored & ~visible
        grey = original["fg"][remembered].mean(axis=1, keepdims=True)
        view["fg"][remembered] = (grey * MEMORY_TINT).astype(np.uint8)
        view["bg"][remembered] = VOID

        unseen = ~explored
        view["ch"][unseen] = ord(" ")
        view["bg"][unseen] = VOID

    @staticmethod
    def split_words(place: str, width: int) -> list[str]:
        """A place's words over as few lines as fit, breaking only between words."""
        rows_: list[str] = []
        for word in place.replace("][", "]\n[").split("\n"):
            if rows_ and len(rows_[-1]) + len(word) <= width:
                rows_[-1] += word
            else:
                rows_.append(word)
        return rows_

    def work_lines(self, width: int) -> list[list]:
        """What the Hunter is working on (v0.73.0, off a hunt): the contract (its words, as known),
        then each bounty, √ and green once it's done or the prize is in hand. Lines of (text, colour)."""
        from game import story
        p = self.player
        out = []
        c = p.contract
        if c is not None:
            have = c.artifact_id and any(it.type.id == c.artifact_id for it in p.all_items())
            words = self.split_words(story.words_shown(self, c), width - 2)
            for i, line in enumerate(words):
                out.append([("☼ " if i == 0 else "  ", WORK_DONE if have else ACCENT_PANEL),
                            (line, WORK_DONE if have else TEXT)])
        for job in p.jobs:
            done = job.done
            if job.kind == "kill" and job.want in self.monster_types:
                mt = self.monster_types[job.want]
                glyph, gcol, what = mt.glyph, mt.color, mt.name
            elif job.kind in ("find", "errand") and job.want in self.catalogue.types:
                t = self.catalogue[job.want]
                glyph, gcol, what = t.glyph, t.color, t.name
            elif job.kind == "scout":
                glyph, gcol, what = "»", ACCENT_PANEL, f"scout to area {job.target}"
            else:
                glyph, gcol, what = "·", DIM, job.short()
            mark = " √" if done else ""
            room = width - 2 - len(mark)
            out.append([(glyph + " ", gcol), (what[:room], WORK_DONE if done else TEXT), (mark, WORK_DONE)])
        return out

    def render_work(self, console, x0: int, left: int, width: int, y: int, bottom: int) -> int:
        if self.hunt is not None:           # (on a hunt, the hunt line shows what's here)
            return y
        lines = self.work_lines(width)
        if not lines:
            return y
        if bottom - (y + len(lines) + 1) < MIN_LOG_ROWS:    # no room: one line instead (details in q)
            p = self.player
            bits = []
            if p.contract is not None:
                bits.append("contract")
            if p.jobs:
                bits.append(f"{len(p.jobs)} bount{'y' if len(p.jobs) == 1 else 'ies'}")
            text = " + ".join(bits)
            done = sum(1 for j in p.jobs if j.done)
            lines = [[(text[:width], TEXT)] + ([(" √", WORK_DONE)] if done and len(text) + 2 <= width else [])]
        for pieces in lines:
            cx = left
            for t, color in pieces:
                console.print(cx, y, t, fg=color, bg=PANEL_BG)
                cx += len(t)
            y += 1
        console.print(x0, y, "├" + "─" * (SIDEBAR_WIDTH - 1), fg=RULE, bg=PANEL_BG)
        return y + 1

    def render_sidebar(self, console, x0: int) -> None:
        """Location and turn at the top, then the message log down the rest."""
        console.rgb["bg"][x0:, :] = PANEL_BG
        for y in range(console.height):
            console.print(x0, y, "│", fg=RULE, bg=PANEL_BG)
        left, width = x0 + 2, SIDEBAR_WIDTH - 3

        p, st = self.player, self.player.stats

        # Character: name, health, level, attributes.
        # The full name if it fits ("Ylfa Fencer Hunters"), else without the surname.
        name = p.full_name if len(p.full_name) <= width else p.full_name.rsplit(" ", 1)[0]
        console.print(left, 1, name[:width], fg=TEXT, bg=PANEL_BG)
        hp_text = f"{st.hp}/{st.max_hp}"
        bar_w = width - 4 - len(hp_text)
        filled = round(bar_w * st.hp / st.max_hp) if st.max_hp else 0
        hp_color = HP_GOOD if st.hp * 3 > st.max_hp else HP_LOW
        console.print(left, 2, "HP", fg=DIM, bg=PANEL_BG)
        console.print(left + 3, 2, "█" * filled, fg=hp_color, bg=PANEL_BG)
        console.print(left + 3 + filled, 2, "░" * (bar_w - filled), fg=RULE, bg=PANEL_BG)
        console.print(left + 4 + bar_w, 2, hp_text, fg=TEXT, bg=PANEL_BG)
        # Jodebris, only while a windcatcher is equipped.
        o = 0
        w = p.windcatcher
        if w is not None:
            o = 1
            jb_w = width - 3          # just the bar: Jodebris numbers are never shown (user, v0.41.1)
            jb_fill = round(jb_w * w.jodebris / w.capacity) if w.capacity else 0
            low = w.jodebris * 4 <= w.capacity
            console.print(left, 3, "JB", fg=DIM, bg=PANEL_BG)
            console.print(left + 3, 3, "█" * jb_fill, fg=JODEBRIS_LOW if low else JODEBRIS, bg=PANEL_BG)
            console.print(left + 3 + jb_fill, 3, "░" * (jb_w - jb_fill), fg=RULE, bg=PANEL_BG)
        # Level, rank and XP (v0.73.0: the rank beside the level; XP on its own line if both won't fit)
        from game import ranks
        y = 3 + o
        lv = f"Lv {st.level} "
        rank = ranks.of(p)["name"]
        xp = f"XP {st.xp}/{st.xp_to_next}"
        console.print(left, y, lv, fg=DIM, bg=PANEL_BG)
        console.print(left + len(lv), y, rank[: width - len(lv)], fg=RANK_COLOR, bg=PANEL_BG)
        if len(lv) + len(rank) + 1 + len(xp) <= width:
            console.print(left + width - len(xp), y, xp, fg=DIM, bg=PANEL_BG)
        else:
            y += 1
            console.print(left, y, xp[:width], fg=DIM, bg=PANEL_BG)
        y += 1
        # (Attributes are on the character sheet, c.)

        # Equipment and purse.
        item = p.equipped.get("weapon")
        glyph, color = (item.type.glyph, item.type.color) if item else ("·", DIM)
        console.print(left, y, glyph, fg=color, bg=PANEL_BG)
        console.print(left + 2, y, (item.label if item else "bare hands")[: width - 2],
                      fg=TEXT if item else DIM, bg=PANEL_BG)
        y += 1
        # Armour (v0.75.0): the total, then a mark for each slot (head, chest, legs), lit when worn.
        from game import gear
        worn = gear.worn_armour(p)
        chest = p.equipped.get("chest") or (worn[0] if worn else None)
        console.print(left, y, chest.type.glyph if chest else "·", fg=chest.type.color if chest else DIM,
                      bg=PANEL_BG)
        console.print(left + 2, y, f"armour {p.armor}" if worn or p.armor else "no armour", fg=TEXT if worn else DIM,
                      bg=PANEL_BG)
        for n, (slot, mark) in enumerate(zip(gear.ARMOUR_SLOTS, "∩φπ")):
            piece = p.equipped.get(slot)
            console.print(left + width - 5 + 2 * n, y, piece.type.glyph if piece else mark,
                          fg=piece.type.color if piece else (70, 64, 56), bg=PANEL_BG)
        y += 1
        console.print(left, y, "♦", fg=SHARD, bg=PANEL_BG)
        console.print(left + 2, y, f"{p.shards} shard{'' if p.shards == 1 else 's'}", fg=TEXT, bg=PANEL_BG)
        y += 1
        console.print(x0, y, "├" + "─" * (SIDEBAR_WIDTH - 1), fg=RULE, bg=PANEL_BG)
        y += 1

        # Where you are: the map, and on a hunt the place's words (split between words if they don't
        # fit, v0.54.1). The ground under you is left to the look command (v0.73.0).
        gm = self.game_map
        console.print(left, y, gm.title[:width], fg=TEXT, bg=PANEL_BG)
        y += 1
        if self.hunt:
            for line in self.split_words(self.hunt.contract.region.name, width):
                console.print(left, y, line[:width], fg=DIM, bg=PANEL_BG)
                y += 1
        # When: the date on the calendar (see game/calendar.py). Not on a hunt (v0.64.0, user): the
        # panel needs the room for messages there, and time only moves between areas.
        if not self.hunt:
            for i, line in enumerate(self.date.lines):
                console.print(left, y, line[:width], fg=DATE if i == 0 else DIM, bg=PANEL_BG)
                y += 1
        if self.hunt:
            left_faints = self.faints_left()
            text = f"Faints: {left_faints}/{p.faint_limit}"            # (earned by reaching new areas, v0.82.0)
            console.print(left, y, text, fg=DIM if left_faints else HP_LOW, bg=PANEL_BG)
            y += 1
        from game import rest as _rest              # (v0.88.0) rest owed; weary on a hunt
        if self.hunt and p.weary:
            console.print(left, y, f"Weary: {round(p.weary * 100)}%"[:width], fg=HP_LOW, bg=PANEL_BG)
            y += 1
        elif not self.hunt and _rest.pulses_owed(p):
            n = _rest.pulses_owed(p)
            c, r = divmod(n, self.calendar.per_cycle)
            short = " ".join(([f"{c}C"] if c else []) + ([f"{r}P"] if r else []))
            console.print(left, y, f"Rest owed: {short}"[:width], fg=HP_LOW if n >= _rest.reckon(self) else DIM, bg=PANEL_BG)
            y += 1
        if p.dues_owed:
            console.print(left, y, f"Dues owed: {p.dues_owed}"[:width], fg=HP_LOW, bg=PANEL_BG)
            y += 1
        if p.talent_offers:                 # (v0.58.0)
            console.print(left, y, "Talent to choose: n"[:width], fg=ACCENT_PANEL, bg=PANEL_BG)
            y += 1
        # (A burning torch shows on the hunt line now, v0.71.0: game/hud.py.)
        if p.meal_turns:
            console.print(left, y, "¥", fg=TORCH, bg=PANEL_BG)
            console.print(left + 2, y, f"Mending: {p.meal_turns} turns"[: width - 2], fg=DIM, bg=PANEL_BG)
            y += 1
        if p.injuries:
            from game import injuries
            dots = injuries.bleeding(p)
            console.print(left, y, "!", fg=HP_LOW, bg=PANEL_BG)
            console.print(left + 2, y, f"Injuries: {len(p.injuries)}"[: width - 2], fg=INJURY, bg=PANEL_BG)
            y += 1
            if dots:
                paused = " (paused)" if self.game_map is self.city else ""
                console.print(left + 2, y, (", ".join(dots).capitalize() + paused)[: width - 2], fg=HP_LOW, bg=PANEL_BG)
                y += 1
        console.print(x0, y, "├" + "─" * (SIDEBAR_WIDTH - 1), fg=RULE, bg=PANEL_BG)
        y += 1
        y = self.render_work(console, x0, left, width, y, console.height - 1)

        # The version, in the bottom corner; the log stops above it.
        version = f"v{VERSION}"
        console.print(x0 + SIDEBAR_WIDTH - len(version) - 1, console.height - 1, version, fg=VERSION_COLOR, bg=PANEL_BG)
        log_bottom = console.height - 1

        # The minimap (v toggles it; v0.53.0, user; key moved in v0.53.1): the whole map, in place of the message log
        # (on a tall screen the newest messages still show below it).
        if getattr(self, "show_minimap", False):
            from game import minimap
            room = log_bottom - y
            rows = room if room < 16 else 12
            minimap.draw(console, self, left - 1, y, width + 1, rows, bg=PANEL_BG, max_scale=6)   # big maps: around you
            y += rows
            if room - rows < 4:
                return
            console.print(x0, y, "├" + "─" * (SIDEBAR_WIDTH - 1), fg=RULE, bg=PANEL_BG)
            y += 1

        # Message log: newest at the top, long ones wrapped. No blank lines between them (v0.64.0, user:
        # with an injury showing only one message fitted): the newest is bright, older ones grey,
        # in two alternating greys so where one ends and the next begins still shows.
        for age, message in enumerate(reversed(self.messages)):
            fade = 1.0 if age == 0 else (0.62 if age % 2 else 0.46)
            color = tuple(int(c * fade) for c in TEXT)
            lines = textwrap.wrap(message, width)
            if y + len(lines) > log_bottom:
                return
            for line in lines:
                console.print(left, y, line, fg=color, bg=PANEL_BG)
                y += 1
