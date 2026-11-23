"""Fishing (v0.94.0): stage 1 of claude/design-fishing.md.

The user (2026-11-23): fishing "unnecessarily deep... it could almost be its own game"; the Watermen
and Anglers' Guild (surname Waters) and its tackleman; miasma fishing is a thing, with its own vibes
and challenges (a later stage); a turn-based tension fight, to be judged in play; a Hunter who makes
their living mostly from fishing is called an Angler. Everything else here is the assistant's draft.

The act:
- **Cast** (r): with a rod and bait in the pack, aim at water within the rod's reach. A turn.
- **Wait**: each turn the fish that could be there (the water, its depth band, lit or dark, the bait)
  may bite. Tells come in the log; some are false. A bite gives a short window to **strike**.
- **The fight**: each turn, reel, hold, give line, or steer left or right. The fish acts by its
  temperament (data `tempers`, `moves`). Tension builds (it keeps 40% of the last turn's); past the
  rod's power the line snaps. Slack too long and the hook comes free. Line out past the rod's line and
  it's stripped. Reel it to the bank to land it. Fish of a tier up to your Angling rank show what
  they're about to do.
- **Landed**: keep it (a fish item with its weight) or let it go (a little practice).

Waters (`waters(gm, place)`): every body of water on a map, found by flood fill. The city's are all the
city river. On the Brisering: river (100+ cells, strung out), lake (25+), pond. A cell's depth band
is its distance to the bank: shore 1, shallow 2, deep 3+. A water's light follows the Duel by which
side of Myligast it lies (game/sky.py); the city is south.

World state `engine.angling` (saved as `world.angling`): {"dug": {"x,y": day}} (worm digging).
Hunter state: `Player.income` {"hunting", "fishing"} for the middle name (game/names.py).
"""
from __future__ import annotations

import json
import random
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
BANDS = ("shore", "shallow", "deep")

# ---- Numbers (placeholders) --------------------------------------------------------------------
TIER_BITE = {1: 0.06, 2: 0.042, 3: 0.028, 4: 0.016, 5: 0.009}   # chance a turn per fish that could bite
TIER_STRENGTH = {1: 24, 2: 38, 3: 56, 4: 74, 5: 100}             # its pull
TIER_STAMINA = {1: 6, 2: 10, 3: 16, 4: 22, 5: 32}
FALSE_TELL = 0.06        # a turn's chance of a false tell
AMBIENT_TELL = 0.12
KEEP = 0.4               # tension kept from one turn to the next
ACT = {"reel": 1.3, "hold": 1.0, "give": 0.35, "left": 0.8, "right": 0.8}
TIRE = {"reel": 1, "hold": 2, "give": 1, "left": 1, "right": 1}
RETRIEVE = 3             # line won back by a reel (less for a heavy fish: / (1 + kg / HEAVY))
HEAVY = 8
SLACK = 10               # tension below this is slack
SNAG = 0.35              # a veer not steered against
TEAR = 0.30              # reeling into a thrash
REPEAT = 0.4             # a fish's chance to do again what it just did
START_TENSION = 20
STRIKE_SPOOK = 3         # turns the water's put down by a strike at nothing
DIG_REGROW = 9           # Pulses before dug ground has worms again
SOFT = set(",ef")        # grass, mud, woods: ground you can dig (by water)
INCOME_MIN = 50          # shards earned before the middle name can follow the money


def data() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = json.loads((DATA / "fish.json").read_text(encoding="utf-8"))
    return _DATA


_DATA = None


def species() -> dict:
    return data()["species"]


def type_id(fid: str) -> str:
    return f"fish_{fid}"


def register(catalogue) -> None:
    """An item type for every fish (once per catalogue)."""
    from game.items import ItemType
    for fid, f in species().items():
        tid = type_id(fid)
        if tid in catalogue.types:
            continue
        catalogue.types[tid] = ItemType(
            id=tid, real_name=f["name"], glyph=f.get("glyph", data()["glyph"]), color=tuple(f["color"]),
            kind="fish", real_description=f["description"] + " The tackleman buys fish by weight.",
            value=0, properties={"fish": fid, "tier": f["tier"]})


# ---- Weights, labels, worth ---------------------------------------------------------------------
def weight_text(kg: float) -> str:
    return f"{round(kg * 1000)} g" if kg < 1 else f"{kg:.1f} kg"


def label(item) -> str:
    q = item.catch.get("quirk", "")
    qn = data()["quirks"].get(q, {}).get("name", "")
    return f"{qn + ' ' if qn else ''}{item.type.real_name} ({weight_text(item.catch['kg'])})"


def value(item) -> int:
    f = species().get(item.type.properties.get("fish", ""), {})
    return max(1, round(f.get("per_kg", 1) * item.catch.get("kg", 0)))


def slots(kg: float) -> int:
    return 1 if kg < 5 else 2 if kg < 20 else 3


def make(fid: str, rng, water: str, day: int):
    """A fish of this kind, its weight and any quirk rolled."""
    from game.items import Item
    f = species()[fid]
    usual, spread = f["kg"]
    kg = usual * max(0.35, rng.gauss(1.0, spread))
    quirk = ""
    if rng.random() < data().get("quirk_chance", 0):
        quirk = rng.choice(sorted(data()["quirks"]))
        kg *= data()["quirks"][quirk].get("kg", 1.0)
    kg = round(kg, 3)
    return Item(_catalogue_type(fid), catch={"kg": kg, "quirk": quirk, "water": water, "day": day})


_TYPES: dict = {}


def _catalogue_type(fid: str):
    return _TYPES[fid]


def bind(catalogue) -> None:
    """Remember the catalogue's fish types (from the Engine)."""
    register(catalogue)
    for fid in species():
        _TYPES[fid] = catalogue.types[type_id(fid)]


# ---- Waters ------------------------------------------------------------------------------------
@dataclass
class Waters:
    body: dict = field(default_factory=dict)   # (x, y) -> body index
    kinds: list = field(default_factory=list)  # body index -> water kind
    band: dict = field(default_factory=dict)   # (x, y) -> 0 shore, 1 shallow, 2 deep


def place(engine) -> str | None:
    """'city', 'brisering', 'miasma' (a hunt or a Lost Ground) or None (anywhere else)."""
    if engine.hunt is not None or str(getattr(engine, "site", "") or "").startswith("lost:"):
        return "miasma"
    if engine.game_map is engine.city:
        return "city"
    if engine.in_brisering():
        return "brisering"
    return None


def waters(gm, where: str) -> Waters:
    cached = getattr(gm, "_waters", None)
    if cached is not None:
        return cached
    from game import tiles
    W = tiles.SYMBOL_TO_INDEX["~"]
    kinds = gm.kinds
    wet = kinds == W
    out = Waters()
    for x0 in range(gm.width):
        for y0 in range(gm.height):
            if not wet[x0, y0] or (x0, y0) in out.body:
                continue
            idx = len(out.kinds)
            q, cells = deque([(x0, y0)]), []
            out.body[(x0, y0)] = idx
            while q:
                x, y = q.popleft()
                cells.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < gm.width and 0 <= ny < gm.height and wet[nx, ny] and (nx, ny) not in out.body:
                        out.body[(nx, ny)] = idx
                        q.append((nx, ny))
            out.kinds.append(_kind(cells, where))
    # depth bands: distance from the bank, four-way
    q = deque()
    for (x, y) in out.body:
        if any(not (0 <= x + dx < gm.width and 0 <= y + dy < gm.height) or not wet[x + dx, y + dy]
               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            out.band[(x, y)] = 0
            q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (x + dx, y + dy)
            if c in out.body and c not in out.band:
                out.band[c] = min(2, out.band[(x, y)] + 1)
                q.append(c)
    # The Brisering's river is narrow and moving (a cell or two across at this scale): it's all
    # shallow, running water. (Its fish say so in data/fish.json.)
    for c in out.band:
        if out.kinds[out.body[c]] == "river":
            out.band[c] = 1
    gm._waters = out
    return out


def _kind(cells: list, where: str) -> str:
    if where == "city":
        return "city_river"
    if where != "brisering":
        return "miasma"
    xs, ys = [c[0] for c in cells], [c[1] for c in cells]
    fill = len(cells) / ((max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1))
    if len(cells) >= 100 and fill < 0.3:
        return "river"
    return "lake" if len(cells) >= 25 else "pond"


def light_at(engine, x: int, y: int, where: str) -> str:
    """Lit or dark: the water's half of the Overland, by the Duel (the city is south of Myligast)."""
    from game import sky
    if where == "brisering":
        from game import journey
        b = journey.bearing(engine.game_map, x, y)
    else:
        b = 180.0
    return sky.light_for(sky.SKY, None, b)


# ---- Tackle ------------------------------------------------------------------------------------
def rod(player):
    """The best rod in the pack (most power), or None."""
    rods = [it for it in player.inventory.items if it.type.properties.get("rod")]
    return max(rods, key=lambda it: (it.type.properties.get("power", 0), it.type.properties.get("reach", 0)),
               default=None)


def baits(player) -> list:
    """Bait and lure kinds in the pack, one item each, in pack order."""
    seen, out = set(), []
    for it in player.inventory.items:
        b = it.type.properties.get("bait")
        if b and it.type.id not in seen:
            seen.add(it.type.id)
            out.append(it)
    return out


def bait_named(player, type_id: str):
    return next((it for it in player.inventory.items if it.type.id == type_id), None)


# ---- Where you can cast ------------------------------------------------------------------------
def _clear_line(gm, x0, y0, x1, y1) -> bool:
    """Nothing opaque between here and there (the end cells don't count)."""
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err, x, y = dx + dy, x0, y0
    while (x, y) != (x1, y1):
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
        if (x, y) != (x1, y1) and not gm.transparent[x, y]:
            return False
    return True


def why_not(engine, x: int, y: int) -> str:
    """Why you can't cast there ('' if you can)."""
    from game import ranged
    p, gm = engine.player, engine.game_map
    r = rod(p)
    where = place(engine)
    if r is None:
        return "You have no rod or line. The tackleman sells them."
    if where in (None, "miasma"):
        return "These waters are the miasma's. Not with this tackle."
    w = waters(gm, where)
    if (x, y) not in w.body:
        return "That isn't water."
    if ranged.distance(p.x, p.y, x, y) > r.type.properties.get("reach", 2):
        return f"Out of reach: your {r.type.name} casts {r.type.properties.get('reach', 2)}."
    if not engine.in_vision(x, y) or not _clear_line(gm, p.x, p.y, x, y):
        return "You can't see a way to cast there."
    return ""


def can_start(engine) -> str:
    """Why you can't start fishing here ('' if you can)."""
    p = engine.player
    if rod(p) is None:
        return "You have no rod or line. The tackleman by the river sells them."
    where = place(engine)
    if where == "miasma":
        return "These waters are the miasma's. Not with this tackle."
    if where is None:
        return "There's no water here to fish."
    if not baits(p):
        return "You've no bait. The tackleman sells it, and worms can be dug from soft ground by water (g)."
    if not spots(engine):
        return f"No water within your {rod(p).type.name}'s reach that you can see."
    return ""


def spots(engine) -> list:
    """Water cells you could cast to, deepest and farthest first."""
    from game import ranged
    p, gm = engine.player, engine.game_map
    r, where = rod(p), place(engine)
    if r is None or where in (None, "miasma"):
        return []
    w = waters(gm, where)
    reach = r.type.properties.get("reach", 2)
    out = []
    for dx in range(-reach, reach + 1):
        for dy in range(-reach, reach + 1):
            c = (p.x + dx, p.y + dy)
            if c in w.body and not why_not(engine, *c):
                out.append(c)
    return sorted(out, key=lambda c: (-w.band[c], -ranged.distance(p.x, p.y, *c), c))


def describe_spot(engine, x: int, y: int) -> str:
    where = place(engine)
    w = waters(engine.game_map, where)
    kind = w.kinds[w.body[(x, y)]]
    return f"{data()['waters'][kind]['name'].capitalize()}, {BANDS[w.band[(x, y)]]}, {light_at(engine, x, y, where)}."


# ---- Who's there -------------------------------------------------------------------------------
def candidates(kind: str, band: str, light: str, bait: str) -> list:
    """[(fish id, chance a turn)] for this water, depth, light and bait."""
    out = []
    for fid, f in species().items():
        if kind not in f["waters"] or band not in f["depth"]:
            continue
        if f["light"] != "any" and f["light"] != light:
            continue
        like = f["baits"].get(bait, 0)
        if like > 0:
            out.append((fid, TIER_BITE[f["tier"]] * like))
    return out


# ---- A session at the water --------------------------------------------------------------------
@dataclass
class Session:
    x: int
    y: int
    stand: tuple
    kind: str
    band: str
    light: str
    rod: object
    bait: str                       # the bait's item type id
    bait_key: str = ""              # what kind of bait it is (worms, grubs, dough, spinner)
    phase: str = "wait"             # wait, bite, fight, landed, over
    spooked: int = 0
    false_tell: bool = False
    fish: str = ""                  # the fish on the line (species id)
    kg: float = 0.0
    quirk: str = ""
    window: int = 0
    tension: float = 0.0
    stamina: float = 0.0
    max_stamina: float = 0.0
    strength: float = 0.0
    line: float = 0.0
    move: str = ""                  # what it did last turn
    coming: str = ""                # what it's about to do
    slack: int = 0
    turns: int = 0
    log: list = field(default_factory=list)
    caught: object = None           # the landed Item


def _rng(engine):
    return getattr(engine, "rng", None) or random


def note(s: Session, text: str) -> None:
    s.log.append(text)
    del s.log[:-4]


def cast(engine, x: int, y: int, bait_type: str) -> tuple[bool, str]:
    why = why_not(engine, x, y)
    if why:
        return False, why
    p = engine.player
    bait = bait_named(p, bait_type)
    if bait is None:
        return False, "You've no bait. Worms, grubs, dough or a lure: the tackleman sells them, and worms can be dug."
    where = place(engine)
    w = waters(engine.game_map, where)
    s = Session(x, y, (p.x, p.y), w.kinds[w.body[(x, y)]], BANDS[w.band[(x, y)]], light_at(engine, x, y, where),
                rod(p), bait_type, bait.type.properties.get("bait", ""))
    engine.fishing = s
    engine.fishing_last = (x, y, bait_type)
    note(s, f"You cast your {bait.type.name} into {data()['waters'][s.kind]['name']}, {s.band} water.")
    from game import sound
    sound.play("cast")
    return True, ""


def end(engine, text: str = "") -> None:
    s = getattr(engine, "fishing", None)
    if s is not None:
        s.phase = "over"
    engine.fishing = None
    if text:
        engine.log(text)


def still_on(engine) -> bool:
    """Is the session still going (not moved away, not knocked down, same map)?"""
    s = getattr(engine, "fishing", None)
    if s is None:
        return False
    p = engine.player
    if (p.x, p.y) != s.stand or p.stats.is_dead or place(engine) in (None, "miasma") \
            or s.rod not in p.inventory.items:
        engine.fishing = None
        return False
    return True


def shows_coming(engine, s: Session) -> bool:
    from game import fieldskills
    rank = fieldskills.rank(engine, "angling")
    return species()[s.fish]["tier"] <= rank or rank >= 3


def _use_bait(engine, s: Session) -> None:
    it = bait_named(engine.player, s.bait)
    if it is not None and not it.type.properties.get("lure"):
        engine.player.inventory.remove(engine.player.inventory.items.index(it), 1)


def _lose_lure(engine, s: Session) -> None:
    it = bait_named(engine.player, s.bait)
    if it is not None and it.type.properties.get("lure"):
        engine.player.inventory.remove(engine.player.inventory.items.index(it), 1)
        note(s, f"Your {it.type.name} goes with it.")


def step(engine, cmd: str) -> bool:
    """One choice at the water. Returns True when a turn passes."""
    if not still_on(engine):
        return False
    s: Session = engine.fishing
    rng = _rng(engine)
    s.turns += 1
    if s.phase in ("wait", "bite") and cmd == "stop":
        end(engine, "You reel in.")
        return False
    if s.phase == "landed":
        return _landed(engine, s, cmd)
    if s.phase == "fight":
        return _fight(engine, s, cmd, rng)
    if cmd == "strike":
        if s.phase == "bite":
            return _hook(engine, s, rng)
        s.spooked = STRIKE_SPOOK
        note(s, "You strike at nothing. " + ("It was only the current." if s.false_tell else "")
             + " You've put them down for a while.")
        s.false_tell = False
        return True
    # wait
    s.false_tell = False
    if s.phase == "bite":
        s.window -= 1
        if s.window <= 0:
            s.phase = "wait"
            if rng.random() < 0.5 and not _is_lure(engine, s):
                _use_bait(engine, s)
                note(s, "It's gone, and your bait with it.")
                if bait_named(engine.player, s.bait) is None:
                    end(engine, "You're out of that bait. You reel in.")
            else:
                note(s, "It's gone.")
        else:
            note(s, "The float's still under...")
        return True
    if s.spooked:
        s.spooked -= 1
        return True
    cands = candidates(s.kind, s.band, s.light, s.bait_key)
    roll = rng.random()
    total = 0.0
    for fid, chance in cands:
        total += chance
        if roll < total:
            return _bite(engine, s, fid, rng)
    if rng.random() < FALSE_TELL:
        s.false_tell = True
        note(s, rng.choice(data()["tells"]["false"]))
    elif rng.random() < AMBIENT_TELL:
        note(s, rng.choice(data()["tells"]["ambient"]))
    return True




def _is_lure(engine, s: Session) -> bool:
    it = bait_named(engine.player, s.bait)
    return bool(it and it.type.properties.get("lure"))


def _bite(engine, s: Session, fid: str, rng) -> bool:
    from game import fieldskills
    f = species()[fid]
    s.phase, s.fish = "bite", fid
    s.window = (1 if f.get("wary") else 2) + (1 if fieldskills.rank(engine, "angling") >= 2 else 0)
    note(s, data()["tells"]["bite"][f["temper"]])
    from game import sound
    sound.play("fish_bite")
    return True


def _hook(engine, s: Session, rng) -> bool:
    from game import fieldskills
    f = species()[s.fish]
    if f.get("wary") and fieldskills.rank(engine, "angling") < 2 and rng.random() < 0.25:
        s.phase = "wait"
        note(s, "You strike, but it's too quick for you.")
        if not _is_lure(engine, s):
            _use_bait(engine, s)
        return True
    item = make(s.fish, rng, s.kind, engine.day)
    s.kg, s.quirk = item.catch["kg"], item.catch["quirk"]
    ratio = s.kg / f["kg"][0]
    s.strength = TIER_STRENGTH[f["tier"]] * ratio ** 0.4
    s.max_stamina = s.stamina = TIER_STAMINA[f["tier"]] * ratio ** 0.5
    from game import ranged
    s.line = 8 + 3 * ranged.distance(s.stand[0], s.stand[1], s.x, s.y)
    s.tension, s.slack, s.move = START_TENSION, 0, ""
    s.coming = _next_move(s, rng)
    s.phase = "fight"
    if not _is_lure(engine, s):
        _use_bait(engine, s)
    fieldskills.practise(engine, "angling")
    note(s, "You set the hook! " + ("Something small." if s.kg < 0.5 else "Something with some fight in it."
                                    if s.kg < 3 else "Something heavy." if s.kg < 15 else "Something very heavy."))
    return True


def _next_move(s: Session, rng) -> str:
    if s.stamina <= 0:
        return "spent"
    if s.move and s.move != "spent" and rng.random() < REPEAT:
        return s.move
    weights = data()["tempers"][species()[s.fish]["temper"]]
    keys = sorted(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def power(s: Session) -> float:
    pw = s.rod.type.properties.get("power", 60)
    return pw * (0.85 if species()[s.fish]["temper"] == "biter" else 1.0)


def max_line(s: Session) -> float:
    return s.rod.type.properties.get("line", 24)


def _fight(engine, s: Session, cmd: str, rng) -> bool:
    if cmd == "cut":
        _lose_lure(engine, s)
        end(engine, "You cut the line and let it go.")
        return True
    if cmd not in ACT:
        return False
    move = s.coming
    m = data()["moves"][move]
    pull = s.strength * (0.45 + 0.55 * max(0.0, s.stamina) / s.max_stamina) * m["pull"] * rng.uniform(0.85, 1.15)
    factor = ACT[cmd]
    if move == "sulk" and cmd == "reel":
        factor *= 0.8
    if move == "dive" and cmd == "reel":
        factor *= 1.35
    s.tension = s.tension * KEEP + pull * factor
    gain = 0.0
    if cmd == "reel":
        gain = RETRIEVE / (1 + s.kg / HEAVY) + (1 if move == "sulk" else 0) + (2 if move == "spent" else 0)
    elif cmd == "give":
        gain = -2
    if move == "run":
        gain -= 2
    s.line -= gain
    s.stamina = max(0.0, s.stamina - TIRE[cmd] - (1 if move in ("run", "thrash", "dive") else 0))
    s.move = move
    note(s, m["text"])
    lost = ""
    if move == "thrash" and cmd == "reel" and rng.random() < TEAR:
        lost = "The hook tears free as you haul into its thrashing."
    elif move in ("left", "right") and cmd != ("right" if move == "left" else "left") and rng.random() < SNAG:
        lost = "It wraps the line round a snag. The line parts."
        _lose_lure(engine, s)
    elif s.tension > power(s):
        lost = "Too much strain: the line snaps!" if species()[s.fish]["temper"] != "biter" \
            else "Its teeth and the strain together: the line parts!"
        _lose_lure(engine, s)
    elif s.line > max_line(s):
        lost = "It strips the last of your line, and it snaps."
        _lose_lure(engine, s)
    else:
        s.slack = s.slack + 1 if (s.tension < SLACK and cmd == "give") else 0   # (only giving line goes slack)
        if s.slack >= 2 and rng.random() < 0.4:
            lost = "The line's gone slack too long. The hook falls free."
    if lost:
        from game import fieldskills
        fieldskills.practise(engine, "angling")
        end(engine, lost)
        return True
    if s.line <= 0:
        return _land(engine, s, rng)
    s.coming = _next_move(s, rng)
    return True


def _land(engine, s: Session, rng) -> bool:
    from game import fieldskills, sound
    f = species()[s.fish]
    from game.items import Item
    item = Item(_catalogue_type(s.fish), catch={"kg": s.kg, "quirk": s.quirk, "water": s.kind, "day": engine.day})
    s.caught, s.phase = item, "landed"
    fieldskills.practise(engine, "angling", f["tier"] * 2)
    note(s, f"You land {_a(item.label)}!")
    sound.play("fish_landed")
    return True


def _landed(engine, s: Session, cmd: str) -> bool:
    item = s.caught
    if cmd == "keep":
        p = engine.player
        if p.inventory.add(item):
            end(engine, f"You keep the {item.label}. (r to cast again)")
        else:
            from game.items import FloorItem
            engine.game_map.items.append(FloorItem(p.x, p.y, item))
            end(engine, f"No room in your pack: the {item.label} is at your feet. (r to cast again)")
        return False
    if cmd == "release":
        from game import fieldskills
        fieldskills.practise(engine, "angling")
        end(engine, f"You let the {item.type.name} go. It hangs a moment, then it's gone. (r to cast again)")
        return False
    return False


def _a(text: str) -> str:
    return ("an " if text[0] in "aeiou" else "a ") + text


# ---- Digging for worms -------------------------------------------------------------------------
def dig(engine) -> str | None:
    """g on soft ground by water, off a hunt, with nothing else here: dig for worms (a turn).
    Returns the message, or None if this isn't digging ground."""
    p, gm = engine.player, engine.game_map
    where = place(engine)
    if where not in ("city", "brisering"):
        return None
    from game import tiles
    if tiles.TILE_TYPES[gm.kinds[p.x, p.y]].symbol not in SOFT:
        return None
    w = waters(gm, where)
    if not any((p.x + dx, p.y + dy) in w.body for dx in range(-2, 3) for dy in range(-1, 2)):
        return None
    state = engine.angling.setdefault("dug", {})
    key = f"{p.x},{p.y}"
    if engine.day - state.get(key, -10 ** 9) < DIG_REGROW:
        return "You've dug here lately. Nothing left but mud."
    state[key] = engine.day
    rng = _rng(engine)
    if rng.random() < 0.35:
        return "You dig in the soft ground by the water, and find nothing."
    n = rng.randint(1, 3)
    from game.items import Item
    item = Item(engine.catalogue["worms"], n)
    if not p.inventory.add(item):
        return "You find worms, but there's no room in your pack for them."
    return f"You dig in the soft ground by the water and turn up {n} worm{'s' if n > 1 else ''}."


# ---- Income --------------------------------------------------------------------------------------
def angler(player) -> bool:
    """Has this Hunter made most of their living from fishing? (Not used for the middle name since
    v0.94.1: the user didn't want the calling to change on its own.)"""
    inc = getattr(player, "income", None) or {}
    total = sum(inc.values())
    return total >= INCOME_MIN and inc.get("fishing", 0) * 2 > total


# ---- The tackleman's word on what's biting --------------------------------------------------------
def tip(engine, rng=None) -> str:
    """A fish, where it's biting and on what, this Duel (the tackleman's "What's biting?")."""
    from game import sky
    rng = rng or _rng(engine)
    fid = rng.choice(sorted(k for k, f in species().items() if f["tier"] <= 4))
    f = species()[fid]
    lit = sky.lit_half()
    dark = "north" if lit == "south" else "south"
    where = []
    for w in f["waters"]:
        if w == "city_river":
            if f["light"] in ("any", "lit" if lit == "south" else "dark"):
                where.append("the city river")
            continue
        name = {"river": "the river", "lake": "the lakes", "pond": "the ponds"}[w]
        side = {"lit": lit, "dark": dark}.get(f["light"])
        where.append(f"the {side}ern {name[4:]}" if side else name)
    bait = max(f["baits"], key=f["baits"].get)
    bait = {"worms": "a worm", "grubs": "a grub", "dough": "dough", "spinner": "a spinner"}.get(bait, bait)
    band = " or ".join(f["depth"])
    if not where:
        return (f"The {f['name']}? Not in the city this Duel. It keeps to the "
                + ("light" if f["light"] == "lit" else "dark") + ", and the river's on the wrong side of it.")
    places = where[0] if len(where) == 1 else ", ".join(where[:-1]) + " and " + where[-1]
    light = {"lit": " while the light's on them", "dark": " in the dark"}.get(f["light"], "")
    return (f"{plural(f['name']).capitalize()} are in {places}{light}, {band} water. Try {bait}."
            + (" Wary, mind. Strike quick." if f.get("wary") else ""))


def plural(name: str) -> str:
    if name.endswith(("fish", "carp", "char", "perch", "bream", "back")):
        return name
    return name + ("es" if name.endswith(("ch", "sh", "s", "x")) else "s")
