"""Balance simulator: a simple bot plays Hunters through hunts with the real game rules,
and writes what happened to a JSON file for report.py.

    python tools/balance/sim.py --hunters 20 --hunts 30 --seed 1 --out sim.json
    python tools/balance/sim.py --region quiet/green/daybreak ...   (every hunt at one place)

The bot is deliberately plain, a careful but unskilled player: it explores each
area, fights what it meets in melee (or shoots, with a bow and arrows), drinks a
draught when low, eats when hurt, bandages bleeding, lights torches in the dark,
rests (waits for natural healing) when hurt and nothing is in view, goes deeper
until it has the artifact, then walks home. It turns back when it's low on
health with nothing left to drink. Between hunts it consigns every
artifact, sells materials, hands in writings, reports notes, pays dues, sees the
healer, restocks supplies (keeping back enough for the next dues), and buys better armour and weapons when it can.
It picks a danger by level ("ladder"; any land and feature), or always one place (--region).
Since v0.61 (stage 7) it also: takes a contract from the Guild's board at its danger when one is
there (else a trip of its own); takes bounties and scouting jobs from the bounty board (the best
paid it may take, up to two), goes to their places, hunts the marked creature or the artifact, and
collects the pay; hauls home a corpse that would beat the trophy wall's record (if it fits), hands
trophies to the trophymaster and has the butcher break down the rest; and trains skills with
spare shards (its weapon's skill first, then the field skills). It still doesn't fill requests,
commission gear or pay into the Guild's works beyond its dues. --plain turns the new habits off.

Nothing here changes the game; it only drives it. Runs headless (no window).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import os
os.environ.setdefault("TAG_NO_STORY", "1")   # the bot plays the hunting game, not the story
sys.path.insert(0, str(ROOT))

try:
    import tcod  # noqa: F401  (the real one, if installed: only its event module is touched)
    import tcod.event  # noqa: F401
except ImportError:  # headless: a stand-in with just what the game's modules import
    class _AnyKey(type):            # every key name the game asks for exists, as a distinct number
        _ids: dict = {}
        def __getattr__(cls, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return cls._ids.setdefault(name, len(cls._ids) + 1)
    ev = types.ModuleType("tcod.event")
    ev.KeySym = _AnyKey("KeySym", (), {})
    class _E: ...
    ev.Event, ev.Quit, ev.KeyDown = _E, type("Quit", (_E,), {}), type("KeyDown", (_E,), {})
    t = types.ModuleType("tcod"); t.event = ev
    sys.modules["tcod"], sys.modules["tcod.event"] = t, ev

from game import injuries, ranged, shops as shops_mod, artifacts, library, archive  # noqa: E402
from game.actions import MoveAction, PickUpAction, WaitAction, UseAction, FireAction  # noqa: E402
from game.engine import Engine  # noqa: E402
from game.explore import next_step as explore_step  # noqa: E402
from game.game_map import GameMap  # noqa: E402
from game.hunt import load_regions, make_contracts  # noqa: E402
from game.items import Catalogue  # noqa: E402
from game.monsters import load_monster_types  # noqa: E402
from game.player import Player  # noqa: E402
from game.artifacts import load_workshops  # noqa: E402
from game.shops import load_shops  # noqa: E402
from game.travel import next_step as travel_step  # noqa: E402
from game import combat  # noqa: E402

DATA = ROOT / "data"
LADDER = [(1, 1), (3, 2), (5, 3), (7, 4), (9, 5)]   # (from level, danger) since v0.44.0
# How careful the bot is (v0.81.1). "careful" is the bot as it always was; "reckless" (--profile reckless)
# drinks and eats later, rests less, turns back only at the edge, and climbs the ladder two levels sooner:
# closer to how a person plays, to see where Hunters die.
PROFILES = {
    "careful": {"drink": 0.4, "eat": 0.7, "rest_below": 0.6, "rest_to": 0.9, "turn_back": 0.3,
                "ladder": [(1, 1), (3, 2), (5, 3), (7, 4), (9, 5)]},
    "reckless": {"drink": 0.2, "eat": 0.4, "rest_below": 0.3, "rest_to": 0.6, "turn_back": 0.1,
                 "ladder": [(1, 1), (2, 2), (3, 3), (5, 4), (7, 5)]},
}
PROFILE = PROFILES["careful"]
SELL_ALL = False        # --sell-all: sell every material and never raise gear (the bot before v0.80.0)
WEARY = None            # --weary S: set out at weariness S (0-1) every hunt (v0.88.0 calibration)
WEARY_FROM = 0          # --weary-from N: ...from the Nth hunt (0-based) on
DANGER = None           # --danger D: always hunt at danger D (within rank)
KILL_AT = None          # --kill-first-at N: the first Hunter falls in the deepest area of their Nth hunt (v0.87.2)
RECOVER = False         # --recover: go after your own fallen Hunters' packs, and use the guild stash (v0.87.2)
PLAIN = False           # --plain: the pre-stage-7 bot (trips only, no bounties, trophies or training)
TRAIN_ORDER = ["survival", "stealth", "harvesting", "tracking", "medicine"]   # after the weapon's skill
TRAIN_RESERVE = 60      # shards kept back (beyond the next dues) when training
MAX_ACTIONS = 12000     # per hunt, before the bot gives up ("stuck")
WANT = {"healing_draught": 3, "ration": 4, "bandage": 2, "torch": 3, "poultice": 1}


# ---- Setting up ------------------------------------------------------------------------------
def make_engine(seed: int) -> Engine:
    random.seed(seed)
    cat = Catalogue.load(DATA / "items.json")
    city, start = GameMap.from_file(DATA / "maps" / "city.txt")
    rng = random.Random(seed)
    new = lambda: Player.new(DATA / "player.json", cat, *start, rng=rng)
    e = Engine(city, new(), cat, load_regions(DATA / "keywords.json"), load_monster_types(DATA / "monsters.json"),
               new_hunter=new, saves=None, shops=load_shops(DATA / "shops.json", cat),
               workshops=load_workshops(DATA / "workshops.json"))
    e.rng = random.Random(seed + 1)
    e.words = set(e.regions.keywords.all_ids())   # the bot knows every word
    e.new_game()
    return e


def act(e, action) -> None:
    e.handle_action(action)


def index_of(p, item_id):
    return next((i for i, it in enumerate(p.inventory.items) if it.type.id == item_id), None)


def clear_screens(e) -> None:
    """Answer whatever window is open: yes to confirmations, carry on past title cards; take the
    first talent on offer (v0.58.0)."""
    from game import talents
    while e.player.talent_offers:
        talents.choose(e, e.player.talent_offers[0][0])
    for _ in range(5):
        s = e.screen
        if s is None:
            return
        e.screen = None
        if getattr(s, "on_yes", None):
            s.on_yes(e)
        elif getattr(s, "on_continue", None):
            s.on_continue(e)


# ---- On a hunt -------------------------------------------------------------------------------
def visible_monsters(e):
    # (an ashmantle can't be fought, and a burrowed wyrm can't be reached: the bot ignores them)
    return [m for m in e.game_map.monsters if e.visible is not None and e.visible[m.x, m.y]
            and not m.type.ghost and not m.burrowed]


def look_after_self(e, rec) -> bool:
    """Drink, eat, bandage, light a torch. Returns True if a turn was spent."""
    p = e.player
    st = p.stats
    for kind, item in (("bleeding", "bandage"), ("poisoned", "poultice")):
        if kind in injuries.bleeding(p) and index_of(p, item) is not None:
            rec["used"][item] = rec["used"].get(item, 0) + 1
            act(e, UseAction(index_of(p, item)))
            return True
    if st.hp < st.max_hp * PROFILE["drink"]:
        for item in ("healing_tonic", "healing_draught"):
            if index_of(p, item) is not None:
                rec["used"][item] = rec["used"].get(item, 0) + 1
                act(e, UseAction(index_of(p, item)))
                return True
    if st.hp < st.max_hp * PROFILE["eat"] and p.meal_turns == 0 and index_of(p, "ration") is not None:
        rec["used"]["ration"] = rec["used"].get("ration", 0) + 1
        act(e, UseAction(index_of(p, "ration")))
        return True
    if e.game_map.light == "torch" and p.torch_turns == 0 and index_of(p, "torch") is not None:
        rec["used"]["torch"] = rec["used"].get("torch", 0) + 1
        act(e, UseAction(index_of(p, "torch")))
        return True
    return False


def can_heal(p) -> bool:
    return any(index_of(p, i) is not None for i in ("healing_tonic", "healing_draught"))


def step_towards(e, spot, beside=False) -> bool:
    step = travel_step(e, spot, beside)
    if step is None:
        return False
    act(e, MoveAction(*step))
    return True


def head_home(e) -> bool:
    """One step towards the way back (or the trail home)."""
    gm = e.game_map
    sym = "H" if e.hunt.current == 0 else "<"
    spot = e.hunt.entries[e.hunt.current]
    if gm.tile_at(*spot).symbol != sym:
        return False
    p = e.player
    if (p.x, p.y) == spot:               # standing on it (as you do after a faint): take it
        if sym == "H":
            e.reach_trail_home()
        else:
            e.travel(e.hunt.current - 1, arrive_at="far_end")
        return True
    return step_towards(e, spot)


def hunt_turn(e, rec, state) -> None:
    p, gm = e.player, e.game_map
    if look_after_self(e, rec):
        return
    race = e.hunt.race or {}
    if race.get("outcome") == "rival" and not state["retreat"]:   # a rival got the prize first: go home
        state["retreat"] = True
        rec["turned_back"] = True
    seen = visible_monsters(e)
    adjacent = [m for m in seen if abs(m.x - p.x) + abs(m.y - p.y) == 1]   # four-way: side by side only
    low = p.stats.hp < p.stats.max_hp * PROFILE["turn_back"] and not can_heal(p)
    if low and not state["retreat"]:
        state["retreat"] = True
        rec["turned_back"] = True
    if adjacent:
        act(e, MoveAction(adjacent[0].x - p.x, adjacent[0].y - p.y))
        return
    # (a swimmer that can't reach you, or anything that hasn't come in 30 turns, isn't worth waiting for)
    hunting = [m for m in seen if m.type.behaviour == "hunt" and not m.type.swims
               and state.setdefault("waited", {}).get(id(m), 0) < 30]
    # Rest when nothing's about: natural healing (stopped while bleeding).
    from game import rest as _rest                # (weary from half: resting in the field doesn't heal, v0.88.0)
    if not hunting and not injuries.bleeding(p) and p.weary < _rest.NO_HEAL_FROM:
        if p.stats.hp < p.stats.max_hp * PROFILE["rest_below"]:
            state["resting"] = True
        if state.get("resting") and p.stats.hp < p.stats.max_hp * PROFILE["rest_to"]:
            rec["rested"] = rec.get("rested", 0) + 1
            act(e, WaitAction())
            return
    state["resting"] = False
    if hunting and ranged.bow(p) and ranged.can_fire(e) is None:
        target = min(hunting, key=lambda m: max(abs(m.x - p.x), abs(m.y - p.y)))
        if ranged.in_range(e, target.x, target.y):
            act(e, FireAction(target.x, target.y))
            return
    if hunting and not state["retreat"]:
        target = min(hunting, key=lambda m: max(abs(m.x - p.x), abs(m.y - p.y)))
        if target.awake:
            state["waited"][id(target)] = state["waited"].get(id(target), 0) + 1
            act(e, WaitAction())     # let it come to you
        elif not step_towards(e, (target.x, target.y), beside=True):
            act(e, WaitAction())
        return
    # A corpse here: haul it if it would make the trophy wall (and fits), else butcher it (v0.61.0).
    corpses = [f for f in gm.items_at(p.x, p.y) if f.item.trophy is not None]
    if corpses:
        if not PLAIN and worth_hauling(e, corpses[-1].item):
            act(e, PickUpAction())
            if corpses[-1] not in gm.items:
                rec["hauled"] = rec.get("hauled", 0) + 1
                return
        from game.actions import ButcherAction
        act(e, ButcherAction())
        return
    # Pick up what's here (not arrows already shot past: the bot just takes everything).
    if gm.items_at(p.x, p.y) and p.inventory.items is not None:
        before = len(gm.items)
        PickUpAction().perform(e)
        if len(gm.items) < before:
            return
        e.explore_seen_items.add((p.x, p.y))    # (no room for it: don't keep coming back)
    have = p.inventory.count_of(e.hunt.contract.artifact_id) > e.hunt.carried_at_start
    if have and not state["retreat"] and bounty_pending(e):
        # a bounty here isn't done: find the marked creature (or the artifact) in the last area
        marked = [m for m in visible_monsters(e) if m.bounty]
        for m in marked:
            if step_towards(e, (m.x, m.y), beside=True):
                return
        step, why = explore_step(e) if e.hunt.current == e.hunt.contract.depth - 1 else (None, "")
        if step is not None:
            act(e, MoveAction(*step))
            return
        if e.hunt.current < e.hunt.contract.depth - 1:
            for x in range(gm.width):
                for y in range(gm.height):
                    if gm.tile_at(x, y).symbol == ">" and gm.explored[x, y] and step_towards(e, (x, y)):
                        return
    if have or state["retreat"]:
        if not head_home(e):
            state["stuck"] += 50
            act(e, WaitAction())
        return
    # The prize, if it's in sight.
    target = e.hunt.contract.artifact_id
    for f in gm.items:
        if f.item.type.id == target and gm.explored[f.x, f.y]:
            if step_towards(e, (f.x, f.y)):
                return
    step, why = explore_step(e)
    if step is not None:
        act(e, MoveAction(*step))
        return
    # Explored: deeper.
    for x in range(gm.width):
        for y in range(gm.height):
            if gm.tile_at(x, y).symbol == ">" and gm.explored[x, y]:
                if step_towards(e, (x, y)):
                    return
    # Nothing left but through a creature that won't come to you (with four-way movement one can
    # hold a corridor): go and fight it.
    for m in sorted(visible_monsters(e), key=lambda m: abs(m.x - p.x) + abs(m.y - p.y)):
        if step_towards(e, (m.x, m.y), beside=True):
            return
    state["stuck"] += 50
    state["retreat"] = True
    act(e, WaitAction())


def bounty_pending(e) -> bool:
    """A bounty or scouting job held for this place, not done yet."""
    place = e.hunt.contract.region.id
    return any(j.region == place and not j.done for j in e.player.jobs)


def worth_hauling(e, item) -> bool:
    """Would this body make the trophy wall (heavier than the record, or a new quirk), and is there
    room for it with two slots to spare?"""
    from game import trophies
    st = trophies.state(e)
    mid = item.type.properties["monster"]
    rec = st["records"].get(mid)
    quirk = item.trophy.get("quirk", "")
    record = rec is None or item.trophy["kg"] > rec["kg"] or (quirk and quirk not in st["curios"].get(mid, {}))
    inv = e.player.inventory
    have = inv.count_of(e.hunt.contract.artifact_id) > e.hunt.carried_at_start
    spare = 2 if have else 4          # room for the prize and what turns up on the way
    return bool(record) and inv.used + item.slots + spare <= inv.capacity


def forced_death(e, contract) -> str:
    """(--kill-first-at) The Hunter falls in the deepest area of this hunt, carrying what they carry."""
    class Blow:
        name = "hollow brute"
    p = e.player
    e.begin_hunt(contract)
    clear_screens(e)
    for i in range(1, contract.depth):
        e.travel(i, arrive_at="entry")
    clear_screens(e)
    e.hunt.faints_used = e.hunt.faints_earned
    e.player_down(Blow)
    clear_screens(e)
    return "died" if e.player is not p else "done"


def walk_home(e, p, rec) -> str:
    """(v0.89.0) Out at the edge of the Brisering: walk home, and report the contract to the clerk."""
    from game import journey
    clear_screens(e)
    d0 = e.day
    journey.home_now(e)
    clear_screens(e)
    rec["walk_pulses"] = e.day - d0
    if e.player is not p:
        return "died"
    if journey.reportable(e) is not None:
        journey.report(e)
        clear_screens(e)
        while e.scene_queue:
            from game import story
            story.show_next_scene(e)
            clear_screens(e)
    return "done"


def run_hunt(e, contract, rec) -> str:
    p = e.player
    from game import rest                    # (v0.88.0) rest off what's owed first, or set out weary
    rest.rest_here(e)
    if e.passing:                            # their years ran out while resting
        clear_screens(e)
        return "died"
    if WEARY and rec["n"] >= WEARY_FROM:
        p.weary_next = WEARY
    e.begin_hunt(contract)
    clear_screens(e)
    state = {"retreat": False, "stuck": 0}
    for n in range(MAX_ACTIONS):
        if e.player is not p:
            return "died"
        if e.hunt is None:
            return walk_home(e, p, rec)
        if e.screen is not None:
            if type(e.screen).__name__ == "TitleCardScreen" and e.screen.heading == "Knocked out":
                rec["faints"] += 1
            clear_screens(e)
            continue
        hunt_turn(e, rec, state)
        if state["stuck"] > 3000:
            break
    rec["stuck"] = True
    if e.hunt is not None and e.player is p:
        e.finish_hunt(success=False)
        clear_screens(e)
        walk_home(e, p, rec)
    return "stuck"


# ---- In the city -------------------------------------------------------------------------------
def city_phase(e, rec) -> None:
    p = e.player
    cat = e.catalogue
    inc, cost = rec["income"], rec["costs"]
    supplier = e.shops["supplier"]
    workshop = next(iter(e.workshops))
    from game import work, trophies
    if not PLAIN:
        # Bounties first (a find bounty hands over the artifact itself).
        s0 = p.shards
        work.collect(e)
        inc["bounties"] = inc.get("bounties", 0) + p.shards - s0
        # Trophies: the trophymaster takes records; the butcher breaks down the rest.
        for i in reversed(trophies.pack_trophies(e)):
            s0 = p.shards
            ok, _ = trophies.assess(e, i, e.rng)
            if ok:
                inc["trophies"] = inc.get("trophies", 0) + p.shards - s0
                rec["records"] = rec.get("records", 0) + 1
        for i in reversed(trophies.pack_trophies(e)):
            trophies.butcher_at_shop(e, i)
    # Artifacts: consign every broken one (selling it broken when it can't pay its half of the repair).
    while True:
        i = next((i for i, it in enumerate(p.inventory.items) if it.type.is_broken_artifact
                  and not it.type.properties.get("locked")), None)
        if i is None:
            break
        t = p.inventory.items[i].type
        rec["artifacts"].append(t.rarity.id)
        s0 = p.shards
        ok, _ = artifacts.consign(p, i, e.stock(workshop), cat)
        if not ok:
            artifacts.sell_broken(p, i)
        inc["artifacts"] += p.shards - s0
    # Materials it's gathered this hunt, by kind (equipment stage 6), before anything's sold or used.
    from game import gear
    rec["mats"] = {it.type.id: it.count - rec["mats0"].get(it.type.id, 0) for it in p.inventory.items
                   if it.type.kind == "material" and it.count > rec["mats0"].get(it.type.id, 0)}
    # Materials its own gear is made from are kept for raising it (unless --sell-all).
    keep_mats = set()
    if not SELL_ALL:
        for slot in gear.WORN:
            worn = p.equipped.get(slot)
            if worn is not None and gear.gear_type(worn.type):
                for fam in gear.data()["types"][gear.gear_type(worn.type)]["families"]:
                    keep_mats.update(gear.families()[fam])
    # Materials (and spare weapons, armour) to the supplier.
    for i in reversed(range(len(p.inventory.items))):
        it = p.inventory.items[i]
        if it.type.id in keep_mats:
            continue
        if (it.type.kind == "material" or (it.type.kind in ("weapon", "armor") and not p.is_equipped(it)
                                            and it.type.id not in ("arrow",))):
            for _ in range(it.count):
                j = index_of(p, it.type.id)
                if j is None:
                    break
                s0 = p.shards
                ok, _ = shops_mod.sell(p, supplier, j, e.stock("supplier"))
                if not ok:
                    break
                inc["materials" if it.type.kind == "material" else "gear"] += p.shards - s0
    # Writings and notes.
    s0 = p.shards
    library.hand_in(e)
    inc["writings"] += p.shards - s0
    s0 = p.shards
    archive.report(e)
    inc["notes"] += p.shards - s0
    # Dues.
    s0 = p.shards
    if p.dues_owed:
        e.pay_dues()
    cost["dues"] += s0 - p.shards
    # The healer.
    for inj in list(p.injuries):
        t = injuries.table()[inj.id]
        if t.severity == "serious" and p.shards >= t.fee:
            injuries.treat(p, inj.id)
            cost["healer"] += t.fee
    # Keep back what the next dues will be (20% of what's been earned), as a sensible player would.
    keep = p.dues_owed + int(p.earned * e.guild.get("dues_share", 0.2)) + 1
    spend = lambda price: p.shards - price >= keep
    # Supplies.
    stock = e.stock("supplier")
    want = dict(WANT)
    if ranged.bow(p):
        want[ranged.bow(p).type.properties.get("ammo", "arrow")] = 30
    if not SELL_ALL:
        want["materials_pouch"] = 1             # (v0.80.0: kept materials ride in it)
    for item_id, n in want.items():
        while p.inventory.count_of(item_id) < n:
            line = next((l for l in stock.shown() if l.item_id == item_id), None)
            if line is None or not spend(line.price):
                break
            ok, _ = shops_mod.buy(p, cat[item_id], line.price, line.bundle)
            if not ok:
                break
            stock.take(line, e.day)
            cost["supplies"] += line.price
    # Sit for the next rank when ready and it can be afforded on top of the dues.
    from game import ranks
    nxt = ranks.next_rank(p)
    if nxt and ranks.ready(p) and spend(nxt["fee"]):
        cost["rank"] = cost.get("rank", 0) + nxt["fee"]
        ranks.sit(e)
        rec["ranked_up"] = ranks.of(p)["name"]
    if not PLAIN and not SELL_ALL:
        # Raising gear at the smith (equipment stage 6): the weapon, then chest, legs, head, while the
        # materials and fee allow, and only where a failure can't destroy the piece.
        tried = True
        while tried:
            tried = False
            for slot in ("weapon", "chest", "legs", "head"):
                worn = p.equipped.get(slot)
                if worn is None or not gear.has_tier(worn):
                    continue
                to = worn.tier + 1
                if gear.destroy_chance(to) or gear.blocked(e, worn, "smith") or not spend(gear.shard_cost(to) + TRAIN_RESERVE):
                    continue
                s0 = p.shards
                out, _ = gear.upgrade(e, worn, "smith")
                cost["upgrades"] = cost.get("upgrades", 0) + s0 - p.shards
                rec.setdefault("upgrades", []).append(f"{slot} +{to} {out}")
                tried = True
        rec["tiers"] = {s: p.equipped[s].tier for s in gear.WORN if p.equipped.get(s) is not None}
    if not PLAIN:
        # Training: the weapon's skill first, then the field skills, with what's spare.
        from game import skills, weaponskills
        for sid in [weaponskills.weapon_skill(p)] + TRAIN_ORDER:
            if sid is None or sid not in e.skills:
                continue
            sk = e.skills[sid]
            price = skills.cost_for(p, sk)
            if price is not None and skills.is_ready(sk, p.skill(sid)) and spend(price + TRAIN_RESERVE):
                ok, _ = skills.train(p, sk)
                if ok:
                    cost["training"] = cost.get("training", 0) + price
                    rec.setdefault("trained", []).append(f"{sid} {p.skill(sid).rank}")
        # Bounties and scouting: the best paid it may take, at or below its danger.
        from game import ranks
        top = min(ranks.max_danger(p.rank), ladder_danger(p))
        while len(p.jobs) < work.MAX_JOBS:
            options = [j for j in e.job_board if not j.story and e.regions[j.region].danger[0] <= top]
            if not options:
                break
            ok, _ = work.take_job(e, max(options, key=lambda j: j.reward))
            if not ok:
                break
    # Better armour or weapon from the shop, keeping a reserve. (v0.80.0: armour by slot, head, chest
    # and legs, and a piece's tier counts; before, the old "armor" slot was gone and it rebought chest
    # armour every hunt.)
    reserve = 40
    armour_score = lambda t, tier=0: t.properties.get("armor", 0) + tier // 2
    weapon_score = lambda t, tier=0: combat.average(t.properties.get("damage", "1d2")) + tier // 2
    if RECOVER:
        stash_gear(e, rec, armour_score, weapon_score)
    for slot, score in (("chest", armour_score), ("legs", armour_score), ("head", armour_score), ("weapon", weapon_score)):
        cur = p.equipped.get(slot)
        cur_score = score(cur.type, cur.tier) if cur else 0
        if slot == "weapon" and cur and ranged.bow(p):
            continue  # an archer keeps their bow
        kind = "weapon" if slot == "weapon" else "armor"
        options = [l for l in stock.shown() if cat[l.item_id].kind == kind
                   and (kind == "weapon" or gear.armour_slot(cat[l.item_id]) == slot)
                   and cat[l.item_id].properties.get("range") is None and l.item_id != "arrow"
                   and not cat[l.item_id].properties.get("reach")       # (the bot doesn't strike at reach)
                   and score(cat[l.item_id], l.tier) > cur_score and p.shards - l.price >= reserve + keep]
        if options:
            line = max(options, key=lambda l: score(cat[l.item_id]))
            ok, _ = shops_mod.buy(p, cat[line.item_id], line.price, line.bundle)
            if ok:
                stock.take(line, e.day)
                cost["gear"] += line.price
                new = p.inventory.items[index_of(p, line.item_id)]
                p.equip(new)
                rec["bought"].append(line.item_id)


def stash_gear(e, rec, armour_score, weapon_score) -> None:
    """(--recover) Wear what's better in the guild stash; take its materials for raising gear."""
    from game import gear
    p = e.player
    for slot, score in (("chest", armour_score), ("legs", armour_score), ("head", armour_score), ("weapon", weapon_score)):
        cur = p.equipped.get(slot)
        if slot == "weapon" and cur and ranged.bow(p):
            continue
        kind = "weapon" if slot == "weapon" else "armor"
        best = None
        for it in e.stash.items:
            t = it.type
            if t.kind != kind or t.properties.get("range") or t.properties.get("reach"):
                continue
            if kind == "armor" and gear.armour_slot(t) != slot:
                continue
            if score(t, it.tier) > (score(cur.type, cur.tier) if cur else 0) and (best is None or score(t, it.tier) > score(best.type, best.tier)):
                best = it
        if best is not None and p.inventory.can_add(best):
            e.stash.items.remove(best)
            p.inventory.add(best)
            p.equip(best)
            rec.setdefault("from_stash", []).append(f"{best.type.id} +{best.tier}")
    for it in list(e.stash.items):
        if it.type.kind == "material" and p.inventory.can_add(it):
            e.stash.items.remove(it)
            p.inventory.add(it)
            rec.setdefault("stash_mats", 0)
            rec["stash_mats"] += it.count


def worth(e, it) -> int:
    from game import gear
    return gear.value(it) * it.count if it.type.kind in ("weapon", "armor") else it.type.value * it.count


def stash_worth(e) -> int:
    return sum(worth(e, it) for it in e.stash.items)


def pack_worth(e, rec) -> dict:
    """A fallen Hunter's pack: what it held, by kind, in shards."""
    from game.items import Item
    out = {"danger": e.regions[rec["place"]].danger[0], "area": rec["area"], "shards": rec["shards"],
           "equipment": 0, "materials": 0, "other": 0, "tiers": []}
    for entry in rec["items"]:
        it = Item.from_entry(entry, e.catalogue)
        k = it.type.kind
        bucket = "equipment" if k in ("weapon", "armor", "artifact") else "materials" if k == "material" else "other"
        out[bucket] += worth(e, it)
        if it.tier:
            out["tiers"].append(f"{it.type.id} +{it.tier}")
    return out


def ladder_danger(p) -> int:
    return max(d for lv, d in PROFILE["ladder"] if p.stats.level >= lv)


def pick_contract(e, region_id=None):
    """Where to go (v0.44.0; stage 7): a held bounty's place first; else a contract from the
    Guild's board at the danger the Hunter's level suits (within their rank), not one a rival
    took; else a trip to a place of that danger. --region names a place (danger/land/feature).
    Returns (contract, kind)."""
    from game import ranks, postings
    from game.hunt import trip
    p = e.player
    if region_id is not None:
        return trip(e.regions[region_id], e.catalogue, e.rng), "trip"
    top = ranks.max_danger(p.rank)
    want = min(top, DANGER if DANGER else ladder_danger(p))
    if RECOVER:                     # your own fallen Hunter's pack first, when your rank allows it
        from game import recovery
        mine = [c for c in recovery.postings(e) if c.recover["kind"] == "own" and c.danger <= top]
        if mine:
            postings.take(e, mine[0])
            return mine[0], "recovery"
    if not PLAIN:
        for j in p.jobs:
            if not j.done and j.region in e.regions:
                place = e.regions[j.region]
                return (postings.matches(e, place) or trip(place, e.catalogue, e.rng)), "bounty"
        taken = e.rival_taken["taken"] if e.rival_taken.get("day") == e.day else {}
        board = [c for c in postings.generated(e, e.day) if c.danger == want and str(c.seed) not in taken
                 and c.seed not in taken]
        if board:
            postings.take(e, board[0])
            return board[0], "contract"
    from game.keywords import random_place
    place = random_place(e, want, e.rng)
    return trip(place, e.catalogue, e.rng), "trip"


# ---- The run ---------------------------------------------------------------------------------------
def summary(p) -> dict:
    return {"level": p.stats.level, "hp": p.stats.max_hp, "shards": p.shards,
            "weapon": p.equipped["weapon"].type.id if "weapon" in p.equipped else None,
            "armor": p.equipped["armor"].type.id if "armor" in p.equipped else None,
            "injuries": [i.id for i in p.injuries], "talents": list(p.talents), "rank": p.rank,
            "skills": {sid: st.rank for sid, st in p.skills.items() if st.rank > 1}}


def run(hunters: int, hunts: int, seed: int, region: str | None) -> dict:
    e = make_engine(seed)
    out = {"hunters": [], "settings": {"hunters": hunters, "hunts": hunts, "seed": seed, "region": region, "plain": PLAIN}}
    for h in range(hunters):
        if h:
            e.player = e.new_hunter()
            e.change_map(e.city, *e.city_start)
        p = e.player
        career = {"start": summary(p), "attributes": dict(p.stats.attributes),
                  "kit": [it.type.id for it in p.inventory.items], "hunts": []}
        for n in range(hunts):
            if p.dues_owed:
                e.pay_dues()
            if p.dues_owed:          # can't pay: stuck owing
                career["stuck_owing"] = n
                career["end"] = {"died": False, "level": p.stats.level}
                break
            c, kind = pick_contract(e, region)
            rec = {"kind": kind, "n": n, "level": p.stats.level, "region": f"danger {c.danger}", "place": c.region.id, "danger": c.danger, "depth": c.depth,
                   "day0": e.day, "turn0": e.turn, "hp_max": p.stats.max_hp, "shards0": p.shards,
                   "earned0": p.earned, "xp0": p.stats.xp, "faints": 0, "used": {}, "artifacts": [],
                   "bought": [], "turned_back": False, "stuck": False,
                   "kills": {}, "injuries": [],
                   "income": {"found": 0, "artifacts": 0, "materials": 0, "gear": 0, "writings": 0, "notes": 0},
                   "costs": {"dues": 0, "healer": 0, "supplies": 0, "gear": 0, "rank": 0}}
            inj0 = {i.id for i in p.injuries}
            logged0 = e.logged
            kills0 = dict(p.notes.get("kills", {}))
            mats0 = sum(it.count for it in p.inventory.items if it.type.kind == "material")
            rec["mats0"] = {it.type.id: it.count for it in p.inventory.items if it.type.kind == "material"}
            shards_before = p.shards
            stash0 = stash_worth(e)
            if h == 0 and KILL_AT is not None and n == KILL_AT:
                outcome = forced_death(e, c)
            else:
                outcome = run_hunt(e, c, rec)
            if kind == "recovery":
                rec["stash_gain"] = stash_worth(e) - stash0
            rec["jobs_done"] = sum(1 for j in p.jobs if j.done)
            if kind == "bounty" and e.player is p:     # two tries at a bounty, then drop it
                tries = career.setdefault("tries", {})
                for j in list(p.jobs):
                    if j.region == c.region.id and not j.done:
                        tries[str(j.id)] = tries.get(str(j.id), 0) + 1
                        if tries[str(j.id)] >= 2:
                            p.jobs.remove(j)
                            rec["dropped_job"] = True
            if e.player is p and p.contract is not None and outcome != "died" and \
                    p.inventory.count_of(c.artifact_id) > 0 and kind == "contract":
                p.contract = None
            if outcome == "died":
                if e.lost and e.lost[-1]["kind"] == "own" and e.lost[-1]["day"] >= rec["day0"]:
                    career["pack"] = pack_worth(e, e.lost[-1])
                rec["outcome"] = "died"
                rec["turns"] = e.turn - rec["turn0"]
                career["hunts"].append(rec)
                career["end"] = {"died": True, "level": p.stats.level}
                break
            got = p.inventory.count_of(c.artifact_id) > 0
            if kind == "recovery":           # (the pack goes to the Guild on the way home)
                got = any(r["id"] == c.recover["id"] and r["recovered"] for r in e.lost)
                rec["recovered"] = c.recover["name"]
            rec["outcome"] = "success" if (outcome == "done" and got) else ("stuck" if outcome == "stuck" else "abandoned")
            rec["turns"] = e.turn - rec["turn0"]
            rec["pulses"] = e.day - rec["day0"]
            rec["xp"] = p.stats.xp - rec["xp0"]
            rec["income"]["found"] = p.shards - shards_before
            kills = p.notes.get("kills", {})
            rec["kills"] = {k: v - kills0.get(k, 0) for k, v in kills.items() if v - kills0.get(k, 0)}
            rec["materials"] = sum(it.count for it in p.inventory.items if it.type.kind == "material") - mats0
            new_msgs = e.messages[-(e.logged - logged0):] if e.logged > logged0 else []
            # every injury taken on the hunt (minor ones mend during the rest, so count them as they happen)
            rec["injuries"] = [m for m in new_msgs if m.startswith("The blow leaves you with")]
            rec["writings"] = sum(1 for it in p.inventory.items if it.type.writing)
            city_phase(e, rec)
            rec.pop("mats0", None)
            rec["shards1"] = p.shards
            rec["level1"] = p.stats.level
            career["hunts"].append(rec)
        else:
            career["end"] = {"died": False, "level": p.stats.level}
        career["final"] = summary(p)
        out["hunters"].append(career)
        print(f"hunter {h + 1}/{hunters}: {len(career['hunts'])} hunts, level {p.stats.level}, "
              f"{'died' if career['end']['died'] else 'alive'}", flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hunters", type=int, default=10)
    ap.add_argument("--hunts", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--region", default=None)
    ap.add_argument("--out", default="sim.json")
    ap.add_argument("--weary", type=float, default=None, help="set out at this weariness (0-1) every hunt")
    ap.add_argument("--weary-from", type=int, default=0, help="...from this hunt (0-based) on")
    ap.add_argument("--danger", type=int, default=None, help="always this danger (within rank)")
    ap.add_argument("--kill-first-at", type=int, default=None, help="the first Hunter dies on this hunt (0-based)")
    ap.add_argument("--recover", action="store_true", help="take own-pack recovery contracts; use the guild stash")
    ap.add_argument("--plain", action="store_true", help="the bot as it was before stage 7")
    ap.add_argument("--sell-all", action="store_true", help="sell every material; never raise gear (as before v0.80.0)")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="careful",
                    help="careful (the bot as it always was) or reckless (closer to a person: see PROFILES)")
    a = ap.parse_args()
    PROFILE = PROFILES[a.profile]
    PLAIN = a.plain
    RECOVER = a.recover
    KILL_AT = a.kill_first_at
    WEARY = a.weary
    WEARY_FROM = a.weary_from
    DANGER = a.danger
    SELL_ALL = a.sell_all
    t0 = time.time()
    result = run(a.hunters, a.hunts, a.seed, a.region)
    result["seconds"] = round(time.time() - t0, 1)
    Path(a.out).write_text(json.dumps(result), encoding="utf-8")
    print(f"done in {result['seconds']}s -> {a.out}")
