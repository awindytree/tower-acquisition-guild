"""Living off the Brisering (design-return-journey.md stage 4, part 1; v0.91.0): foraging spots, camps
and cooking. User: foraging spots and camp sites on the Brisering, which could become a staging area
before hunts. All names, numbers and recipes are the assistant's drafts (data/wilds.json).

- **Foraging spots** (`spots`): berry thickets, herb patches and mushroom rings, scattered on the
  Brisering by kind of ground (seeded, so the same every game). Stand on one and pick up (g): what it
  gives goes in your pack (more with Harvesting 3+), and it grows back in `regrow` Pulses. World state
  `engine.wilds["picked"]` {"x,y": day picked}.
- **Camps** (`camps`): one every `spacing_km` along each road, just off it. Walk into one (it's a
  campfire, not walkable) for the camp window: cook, make camp, or listen to the travellers there.
  - **Cook** (`cook`): data recipes into dishes: hunter's stew (eat it, and your next hunt starts
    well fed: more max HP until it's over), herb broth (heals, stops bleeding and poison), trail cakes
    (a longer ration).
  - **Make camp** (`make_camp`): a Pulse by the fire: full HP, bleeding and poison stop, and nobody on
    the road troubles you while you sleep.
  - **Travellers' talk:** once a Cycle at each camp, a rumour, sometimes a Wayfinder word.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "wilds.json"
_data: dict | None = None
_cache: dict = {}


def data() -> dict:
    global _data
    if _data is None:
        _data = json.loads(DATA.read_text(encoding="utf-8"))
    return _data


def state(engine) -> dict:
    st = engine.__dict__.setdefault("wilds", {})
    st.setdefault("picked", {})
    st.setdefault("heard", {})
    return st


def _key(x, y) -> str:
    return f"{x},{y}"


# ---- Where things are (worked out from the Brisering map, the same every game) ----------------------------
def spots(engine) -> dict:
    """{(x, y): kind} foraging spots."""
    gm = engine.brisering
    if _cache.get("spots_map") is gm:
        return _cache["spots"]
    rng = random.Random(211)
    out = {}
    taken = set(gm.landmarks) | set(gm.gates)
    for kind, k in sorted(data()["forage"]["kinds"].items()):
        cells = [(x, y) for x in range(gm.width) for y in range(gm.height)
                 if gm.tile_at(x, y).symbol in k["on"] and (x, y) not in taken and (x, y) not in out]
        for c in rng.sample(cells, min(k["count"], len(cells))):
            out[c] = kind
    _cache.update(spots_map=gm, spots=out)
    return out


def camps(engine) -> set:
    """Camp cells: one every spacing_km along each road from the gates, beside the road."""
    gm = engine.brisering
    if _cache.get("camps_map") is gm:
        return _cache["camps"]
    from collections import deque
    from game import journey
    roads = "R=I"
    every = data()["camps"]["spacing_km"]
    out = set()
    for gate, start in sorted(gm.arrivals.items()):
        seen = {start: 0.0}
        q = deque([start])
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if n in seen or not gm.in_bounds(*n) or gm.tile_at(*n).symbol not in roads:
                    continue
                seen[n] = seen[(x, y)] + (journey.KM_Y if dy else journey.KM_X)
                q.append(n)
        marks = sorted(c for c, d in seen.items() if d >= every and d % every < 1.0)
        for (x, y) in marks:
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                n = (x + dx, y + dy)
                if gm.in_bounds(*n) and gm.is_walkable(*n) and gm.tile_at(*n).symbol not in roads \
                        and n not in gm.landmarks and n not in gm.gates and all(abs(n[0] - c[0]) + abs(n[1] - c[1]) > 6 for c in out):
                    out.add(n)
                    break
    _cache.update(camps_map=gm, camps=out)
    return out


def is_camp(engine, x, y) -> bool:
    return engine.in_brisering() and (x, y) in camps(engine)


def blocks(engine, x, y) -> bool:
    """A camp's fire is in the way (walk into it for the camp window)."""
    return is_camp(engine, x, y)


# ---- Foraging ---------------------------------------------------------------------------------------------
def ready(engine, cell) -> bool:
    day = state(engine)["picked"].get(_key(*cell))
    return day is None or engine.day - day >= data()["forage"]["regrow"]


def spot_here(engine):
    if not engine.in_brisering():
        return None
    p = engine.player
    return spots(engine).get((p.x, p.y))


def gather(engine) -> bool:
    """g on a foraging spot. True if a turn was spent."""
    from game.items import Item
    from game import fieldskills
    p = engine.player
    kind = spot_here(engine)
    if kind is None:
        return False
    k = data()["forage"]["kinds"][kind]
    if not ready(engine, (p.x, p.y)):
        engine.log(f"The {k['name']} has been picked over. It'll grow back.")
        return False
    item_id, lo, hi = k["gives"]
    from game import talents
    n = (engine.rng.randint(lo, hi) + (1 if fieldskills.rank(p, "harvesting") >= 3 else 0)
         + talents.total(p, "forage"))                # (an artifact: v0.101.0)
    item = Item(engine.catalogue[item_id], n)
    if not p.inventory.add(item):
        engine.log("Your pack is full.")
        return False
    state(engine)["picked"][_key(p.x, p.y)] = engine.day
    fieldskills.practise(engine, "harvesting", 1)
    engine.log(f"You gather from the {k['name']}: {item.label}.")
    return True


# ---- Camps -----------------------------------------------------------------------------------------------
def recipes() -> dict:
    return data()["recipes"]


def can_cook(engine, rid: str) -> bool:
    p = engine.player
    return all(p.inventory.count_of(i) >= n for i, n in recipes()[rid]["needs"].items())


SHORT = {"wild_berries": "berries", "healing_herbs": "herbs", "earthy_mushrooms": "mushrooms", "ration": "ration",
         "fish_fillet": "fillets"}


def needs_text(engine, rid: str) -> str:
    """'berries 1, mushrooms 2, ration 1'."""
    cat = engine.catalogue
    return ", ".join(f"{SHORT.get(i, cat[i].name)} {n}" for i, n in recipes()[rid]["needs"].items())


def cook(engine, rid: str) -> str:
    """Cook one: the ingredients go in, the dish comes out. A turn by the fire."""
    from game.items import Item
    p = engine.player
    if not can_cook(engine, rid):
        return f"You don't have what it needs: {needs_text(engine, rid)}."
    for i, n in recipes()[rid]["needs"].items():
        for _ in range(n):
            idx = next(j for j, it in enumerate(p.inventory.items) if it.type.id == i)
            p.inventory.remove(idx, 1)
    dish = Item(engine.catalogue[rid])
    if not p.inventory.add(dish):
        engine.game_map.items.append(__import__("game.items", fromlist=["FloorItem"]).FloorItem(p.x, p.y, dish))
    from game import fieldskills
    fieldskills.practise(engine, "survival", 1)
    msg = f"You cook {dish.label} over the fire."
    engine.log(msg)
    return msg


def make_camp(engine) -> str:
    """A Pulse by the fire: full HP, bleeding and poison stop. Nobody on the road troubles you."""
    from game import road
    p = engine.player
    for i in p.injuries:
        i.dot_left = 0
    engine.next_day()
    road.state(engine)["last_day"] = engine.day          # (nobody troubles you the morning after, either)
    if engine.passing:
        return ""
    p.stats.hp = p.stats.max_hp
    msg = "You make camp and sleep by the fire. You wake rested, your wounds cleaned and bound."
    engine.log(msg)
    return msg


def listen(engine, cell) -> str:
    """The travellers at a camp: a rumour once a Cycle (sometimes a word for the Wayfinder)."""
    st = state(engine)
    k = _key(*cell)
    cycle = engine.day // engine.calendar.per_cycle
    if st["heard"].get(k) == cycle:
        return "The fire's quiet. Nobody here has anything new to tell."
    st["heard"][k] = cycle
    rng = engine.rng
    if rng.random() < 0.5:
        from game import keywords
        kw = engine.regions.keywords
        unknown = [w for slot in ("danger", "land", "feature") for w in kw.ordinary(slot) if w not in engine.words]
        if unknown:
            w = rng.choice(unknown)
            keywords.learn(engine, [w])
            shown = next((kw.words[s][w].shown for s in ("danger", "land", "feature") if w in kw.words[s]), w)
            return f"A traveller by the fire talks about a place they heard of, out past the edge: {shown}."
    return rng.choice([
        "Travellers share the fire and the news: prices in Bytorsskug, a bridge that's watched, a Hunter who didn't come back.",
        "A carter swears the Towerway's busier than it's been in Judgments. Everyone agrees, and nobody knows why.",
        "Someone's seen lights out past the edge of the Brisering. Nobody believes them, and nobody laughs.",
    ])


def open_camp(engine, cell) -> None:
    from game.screens import ChoiceScreen
    rows = []
    for rid in recipes():
        name = recipes()[rid].get("name", engine.catalogue[rid].name)
        rows.append((f"Cook {name} ({needs_text(engine, rid)})" if can_cook(engine, rid)
                     else f"{name[0].upper() + name[1:]}: needs {needs_text(engine, rid)}",
                     lambda e, rid=rid: _done(e, cook(e, rid), cell)))
    rows.append(("Make camp and sleep here (a Pulse)", lambda e: _done(e, make_camp(e), None)))
    rows.append(("Listen to the travellers", lambda e: _done(e, listen(e, cell), cell)))
    engine.screen = ChoiceScreen("A camp by the road", rows)


def _done(engine, msg: str, cell) -> None:
    engine.screen = None
    if msg and msg not in engine.messages[-1:]:
        engine.log(msg)
    if cell is not None:
        open_camp(engine, cell)
        engine.screen.notice = msg


# ---- Dishes -----------------------------------------------------------------------------------------------
def eat_dish(engine, index: int) -> bool:
    """u on a dish with "fed" (stew: your next hunt starts well fed) or "cures" (broth). True: a turn."""
    p = engine.player
    item = p.inventory.items[index]
    props = item.type.properties
    if props.get("fed"):
        if getattr(p, "fed", 0) and engine.hunt is not None:
            engine.log("You're still well fed.")
            return False
        p.inventory.remove(index, 1)
        p.fed = props["fed"]
        from game import injuries
        injuries.apply_to_stats(p)
        engine.log(f"You eat the {item.type.name}. You're well fed: more max HP"
                   + (" until this hunt is over." if engine.hunt is not None else " on your next hunt, until it's over."))
        return True
    if props.get("cures"):
        p.inventory.remove(index, 1)
        for i in p.injuries:
            i.dot_left = 0
        gained = p.stats.heal(props.get("heal", 0))
        engine.log(f"You drink the {item.type.name}. Bleeding and poison stop. (+{gained} HP)")
        return True
    return False


def fed_bonus(player, full: int) -> int:
    return int(full * getattr(player, "fed", 0) / 100)


def end_hunt(engine) -> None:
    """The hunt's over: being well fed wears off."""
    p = engine.player
    if getattr(p, "fed", 0):
        p.fed = 0
        from game import injuries
        injuries.apply_to_stats(p)


# ---- Drawing ----------------------------------------------------------------------------------------------
def overlay(engine):
    """[(x, y, glyph, colour)] for the Brisering's camps and foraging spots."""
    if not engine.in_brisering():
        return []
    out = []
    c = data()["camps"]
    for (x, y) in camps(engine):
        out.append((x, y, c["glyph"], tuple(c["color"])))
    kinds = data()["forage"]["kinds"]
    for (x, y), kind in spots(engine).items():
        col = tuple(kinds[kind]["color"])
        if not ready(engine, (x, y)):
            col = tuple(v // 2 for v in col)
        out.append((x, y, kinds[kind]["glyph"], col))
    return out


def look_lines(engine, x, y) -> tuple[str, str] | None:
    """(heading, line) for a camp or a foraging spot."""
    if not engine.in_brisering():
        return None
    if (x, y) in camps(engine):
        return "A camp", data()["camps"]["look"] + " Walk into it to cook, make camp, or listen."
    kind = spots(engine).get((x, y))
    if kind:
        k = data()["forage"]["kinds"][kind]
        tail = " Stand on it and pick up (g) to gather." if ready(engine, (x, y)) else " Picked over; it'll grow back."
        return k["name"][0].upper() + k["name"][1:], k["look"] + tail
    return None
