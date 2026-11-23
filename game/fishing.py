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
Hunter state: `Player.income` {"hunting", "fishing"}; the middle name follows the last 1,000 shards
(game/livings.py).
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
THREAT = 3               # in the miasma, an awake creature this close ends your fishing (v0.98.0)
SPLASH = 0.05            # a fight's turn in the miasma draws a creature, by this a turn (+ per danger)
DRAG_AT = 0.7            # a dragger on a run pulls you in when tension is past this share of the strain
HOOKJAW_LIVES = 0.5      # a landed hookjaw tears free and comes for you
SOFT = set(",ef")        # grass, mud, woods: ground you can dig (by water)


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
    sizes: list = field(default_factory=list)  # body index -> cells (v0.97.0)
    keys: list = field(default_factory=list)   # body index -> its stock key: "city", "river", "lake:x,y", "pond:x,y"
    sides: list = field(default_factory=list)  # body index -> north / south / east / west of Myligast
    names: list = field(default_factory=list)  # body index -> a name (lakes) or ""


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
            kind = _kind(cells, where, gm)
            out.kinds.append(kind)
            out.sizes.append(len(cells))
            corner = min(cells, key=lambda c: (c[1], c[0]))
            out.keys.append("city" if kind == "city_river" else "river" if kind == "river"
                            else f"{kind}:{corner[0]},{corner[1]}")
            out.sides.append(_side(gm, cells, where))
            out.names.append(_lake_name(out.keys[-1]) if kind == "lake" else "")
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


def _side(gm, cells: list, where: str) -> str:
    """Which way from Myligast a water lies (the city is south)."""
    if where != "brisering":
        return "south"
    from game import journey
    cx = sum(c[0] for c in cells) / len(cells)
    cy = sum(c[1] for c in cells) / len(cells)
    b = journey.bearing(gm, cx, cy)
    return ("north", "east", "south", "west")[int(((b + 45) % 360) // 90)]


def _lake_name(key: str) -> str:
    """A placeholder name for a lake: a Starsong given name in one of data's patterns."""
    import zlib
    from game import named
    r = random.Random(zlib.crc32(key.encode()))
    return r.choice(data()["lake_names"]).format(n=named.maker().given_name(r))


def _kind(cells: list, where: str, gm=None) -> str:
    if where == "city":
        return "city_river"
    if where != "brisering":                     # the miasma (v0.98.0): by the area's land
        style = getattr(gm, "style", "") or ""
        return {"marsh": "marsh", "caves": "cave_pool"}.get(style, "miasma_pond")
    xs, ys = [c[0] for c in cells], [c[1] for c in cells]
    fill = len(cells) / ((max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1))
    if len(cells) >= 100 and fill < 0.3:
        return "river"
    return "lake" if len(cells) >= 25 else "pond"


def light_at(engine, x: int, y: int, where: str) -> str:
    """Lit or dark: the water's half of the Overland, by the Duel (the city is south of Myligast)."""
    from game import sky
    if where == "miasma":                        # a hunt area is lit or dark as a whole (game/sky.py)
        return "lit" if getattr(engine.game_map, "light", "dark") == "lit" else "dark"
    if where == "brisering":
        from game import journey
        b = journey.bearing(engine.game_map, x, y)
    else:
        b = 180.0
    return sky.light_for(sky.SKY, None, b)


# ---- Tackle ------------------------------------------------------------------------------------
def rod(player):
    """The rod you've rigged (the tackle's rod slot), else the best one in the pack, or None."""
    held = (getattr(player, "equipped", None) or {}).get("rod")
    if held is not None:
        return held
    rods = [it for it in player.inventory.items if it.type.properties.get("rod")]
    return max(rods, key=lambda it: (it.type.properties.get("power", 0), it.type.properties.get("reach", 0)),
               default=None)


# ---- Tackle (stage 2, v0.96.0) -------------------------------------------------------------------
# Five slots of their own (the equipment window's Tackle section): rod, reel, line, hook, float (a float
# or a sinker). Only a rod is needed: without the rest you fish with the rod's own cord, a small hook and
# line pulled in by hand. Each piece has tiers (game/gear.py; raised by the tackleman, or at home) and,
# every 5 tiers, a trait from its pool in data/traits.json (fish_* keys, summed by tackle_total).
TACKLE_SLOTS = ("rod", "reel", "line", "hook", "float")
BARE = {"retrieve": 2.5, "drag": 0, "capacity": 26, "strength": 20, "visibility": 2, "size": 1, "hold": 0}
PER_TIER = {"rod": {"power": 3}, "reel": {"retrieve": 0.1, "drag": 1, "capacity": 1}, "line": {"strength": 3},
            "hook": {"hold": 2}, "float": {"bite": 2}}
SIZE_NAMES = {1: "small", 2: "middling", 3: "large"}


def tackle_total(player, key: str) -> float:
    """A fish_* key summed over the traits of the tackle you've rigged."""
    from game import gear, artifacts
    total = sum(t.properties.get(key, 0) for t in artifacts.carried(player))   # fishing artifacts (v0.98.0)
    for slot in TACKLE_SLOTS:
        item = (getattr(player, "equipped", None) or {}).get(slot)
        if item is None or not item.traits:
            continue
        pool = gear.pool_of(item)
        for tid in item.traits:
            total += pool.get(tid, {}).get("effects", {}).get(key, 0)
    return total


def kit(player) -> dict:
    """What your tackle adds up to: reach, power (rod + line), retrieve, drag, capacity, visibility,
    hook size and hold, float or sinker, the strike window, bites, reading."""
    eq = getattr(player, "equipped", None) or {}
    r = rod(player)
    t = lambda slot: eq.get(slot)
    def prop(item, key, default):
        return item.type.properties.get(key, default) if item is not None else default
    def tier(item):
        return item.tier if item is not None else 0
    reel, line, hook, flo = t("reel"), t("line"), t("hook"), t("float")
    k = {
        "reach": prop(r, "reach", 2) + tier(r) // 5 + int(tackle_total(player, "fish_reach")),
        "power": prop(r, "power", 40) + PER_TIER["rod"]["power"] * tier(r) + tackle_total(player, "fish_power"),
        "retrieve": prop(reel, "retrieve", BARE["retrieve"]) + PER_TIER["reel"]["retrieve"] * tier(reel)
                    + tackle_total(player, "fish_retrieve"),
        "drag": min(60, prop(reel, "drag", BARE["drag"]) + PER_TIER["reel"]["drag"] * tier(reel)
                    + tackle_total(player, "fish_drag")),
        "capacity": prop(reel, "capacity", BARE["capacity"]) + PER_TIER["reel"]["capacity"] * tier(reel)
                    + tackle_total(player, "fish_capacity"),
        "strength": prop(line, "strength", BARE["strength"]) + PER_TIER["line"]["strength"] * tier(line)
                    + tackle_total(player, "fish_strength"),
        "visibility": max(0, prop(line, "visibility", BARE["visibility"]) - int(tackle_total(player, "fish_unseen"))),
        "size": prop(hook, "size", BARE["size"]),
        "hold": min(80, prop(hook, "hold", BARE["hold"]) + PER_TIER["hook"]["hold"] * tier(hook)
                    + tackle_total(player, "fish_hold")),
        "rig": prop(flo, "float", "none"),
        "window": prop(flo, "window", 0) + int(tackle_total(player, "fish_window")),
        "true_tells": bool(prop(flo, "true_tells", 0) or tackle_total(player, "fish_true_tells")),
        "bite": prop(flo, "bite", 0) + PER_TIER["float"]["bite"] * tier(flo) + tackle_total(player, "fish_bite"),
        "read": int(tackle_total(player, "fish_read")),
        "tire": int(tackle_total(player, "fish_tire")),
        "snag_guard": min(90, tackle_total(player, "fish_snag_guard")),
        "slack_guard": min(90, tackle_total(player, "fish_slack_guard")),
        "set": bool(tackle_total(player, "fish_set")),
        "keep_bait": bool(tackle_total(player, "fish_keep_bait")),
        "any_size": bool(tackle_total(player, "fish_any_size")),
        "deep": bool(tackle_total(player, "fish_deep")),
        "quiet": int(tackle_total(player, "fish_quiet")),
        "spent": tackle_total(player, "fish_spent"),
        "run_line": tackle_total(player, "fish_run_line"),
    }
    return k


def bait_band(k: dict, band: str) -> str:
    """Where your bait sits: without a sinker it never gets below shallow water (a float rig with
    Deep Drop does)."""
    if band == "deep" and k["rig"] != "sinker" and not (k["rig"] == "float" and k["deep"]):
        return "shallow"
    return band


def size_class(kg: float) -> int:
    return 1 if kg < 0.6 else 2 if kg < 5 else 3


def tier_text(item) -> str:
    """What a tackle piece's tier adds (for the item windows)."""
    slot, T = item.type.properties.get("tackle_slot"), item.tier
    if not T:
        return ""
    if slot == "rod":
        parts = [f"+{3 * T} strain"] + ([f"+{T // 5} reach"] if T >= 5 else [])
    elif slot == "reel":
        parts = [f"+{0.1 * T:.1f} retrieve", f"+{T}% drag", f"+{T} line"]
    elif slot == "line":
        parts = [f"+{3 * T} strength"]
    elif slot == "hook":
        parts = [f"+{2 * T}% hold"]
    else:
        parts = [f"+{2 * T}% bites"]
    return ", ".join(parts)


def step_gain(item_type, tier: int) -> str:
    slot = item_type.properties.get("tackle_slot")
    return {"rod": "+3 strain" + (", +1 reach" if tier % 5 == 0 else ""), "reel": "+0.1 retrieve, +1% drag, +1 line",
            "line": "+3 strength", "hook": "+2% hold", "float": "+2% bites"}.get(slot, "")


def kit_lines(player) -> list[str]:
    """The rig, for the cast window and the tackleman: one short line each."""
    k = kit(player)
    eq = getattr(player, "equipped", None) or {}
    def name(slot, bare):
        it = eq.get(slot)
        return it.label if it is not None else bare
    rig = {"float": "float", "sinker": "sinker"}.get(k["rig"], "no float or sinker")
    return [f"Strain {k['power'] + k['strength']:.0f} (rod {k['power']:.0f} + line {k['strength']:.0f}), "
            f"line {k['capacity']:.0f}, reel {k['retrieve']:.1f}, drag {k['drag']:.0f}%.",
            f"Hook {SIZE_NAMES.get(k['size'], k['size'])}; {rig}"
            + ("; your bait won't reach deep water." if bait_band(k, 'deep') != 'deep' else "; it reaches deep water.")]


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
    if where is None:
        return "There's no water here to fish."
    w = waters(gm, where)
    if (x, y) not in w.body:
        return "That isn't water."
    reach = kit(p)["reach"]
    if ranged.distance(p.x, p.y, x, y) > reach:
        return f"Out of reach: your {r.type.name} casts {reach}."
    if not engine.in_vision(x, y) or not _clear_line(gm, p.x, p.y, x, y):
        return "You can't see a way to cast there."
    return ""


def can_start(engine) -> str:
    """Why you can't start fishing here ('' if you can)."""
    p = engine.player
    if rod(p) is None:
        return "You have no rod or line. The tackleman by the river sells them."
    where = place(engine)
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
    if r is None or where is None:
        return []
    w = waters(gm, where)
    reach = kit(p)["reach"]
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
    b = w.body[(x, y)]
    kind = w.kinds[b]
    name = f"{w.names[b]} (a lake)" if w.names[b] else data()['waters'][kind]['name'].capitalize()
    text = f"{name}, {BANDS[w.band[(x, y)]]}, {light_at(engine, x, y, where)}."
    left = fished_share(engine, w.keys[b], kind, w.sizes[b])
    if left < 0.5:
        text += " It's been fished hard; it'll come back, given time."
    elif left < 0.85:
        text += " It's been fished lately."
    return text


# ---- Who's there -------------------------------------------------------------------------------
def present(fid: str, ctx: dict | None) -> bool:
    """Is this fish in this water now (v0.97.0)? Some keep to one side of Myligast (where), some to only
    some lakes or ponds (share, picked per water), some to certain Pulses or the holidays."""
    if not ctx:
        return True
    f = species()[fid]
    if f.get("where") and ctx.get("side") not in f["where"]:
        return False
    if f.get("share") is not None and ctx.get("key", "").startswith(("lake:", "pond:")):
        import zlib
        if zlib.crc32(f"{ctx['key']}/{fid}".encode()) % 1000 >= f["share"] * 1000:
            return False
    if f.get("pulses") and (ctx.get("holiday") or ctx.get("pulse") not in f["pulses"]):
        return False
    if f.get("holiday") and not ctx.get("holiday"):
        return False
    if ctx.get("max_tier") and f["tier"] > ctx["max_tier"]:
        return False
    return True


def candidates(kind: str, band: str, light: str, bait: str, k: dict | None = None, ctx: dict | None = None,
               stock=None) -> list:
    """[(fish id, chance a turn)] for this water, depth, light and bait. With a rig (`kit`): a visible line
    puts wary fish off (more in the light), and floats, sinkers and traits can add bites. With `ctx`
    (side, key, pulse, holiday): only the fish in this water now. `stock(fid)`: the share of it left."""
    k = k or {}
    more = 1 + k.get("bite", 0) / 100
    vis = k.get("visibility", 0)
    out = []
    for fid, f in species().items():
        if kind not in f["waters"] or band not in f["depth"]:
            continue
        if f["light"] != "any" and f["light"] != light:
            continue
        if not present(fid, ctx):
            continue
        like = f["baits"].get(bait, 0) * (stock(fid) if stock else 1)
        if like > 0:
            shy = 1.0
            if f.get("wary") and vis:
                shy = max(0.2, 1 - (0.3 if light == "lit" else 0.1) * vis)
            out.append((fid, TIER_BITE[f["tier"]] * like * more * shy))
    return out


# ---- Stock: what a water holds, and how it comes back (v0.97.0) ---------------------------------------
def cap(fid: str, kind: str, size: int) -> int:
    """How many of this fish a water holds when it's left alone."""
    base = data()["stock"]["cap"][str(species()[fid]["tier"])]
    factor = {"pond": 0.5, "river": 1.5, "city_river": 1.0}.get(kind, min(2.0, max(0.6, size / 60)))
    return max(1, round(base * factor))


def _stock(engine) -> dict:
    return engine.angling.setdefault("stock", {})


def level(engine, key: str, fid: str, full: int) -> int:
    """How many are left: full unless fished, and one back every few Pulses (by tier)."""
    entry = _stock(engine).get(key, {}).get(fid)
    if entry is None:
        return full
    n, since = entry
    every = data()["stock"]["regrow"][str(species()[fid]["tier"])]
    back = (engine.day - since) // every
    if back:
        n = min(full, n + back)
        since += back * every
        if n >= full:
            _stock(engine)[key].pop(fid, None)
            return full
        _stock(engine)[key][fid] = [n, since]
    return n


def take(engine, key: str, fid: str, full: int) -> None:
    n = level(engine, key, fid, full)
    entry = _stock(engine).setdefault(key, {}).get(fid)
    _stock(engine)[key][fid] = [max(0, n - 1), entry[1] if entry else engine.day]


def fished_share(engine, key: str, kind: str, size: int) -> float:
    """How much of a water's fish is left, all kinds together (1.0 = untouched)."""
    kinds = [fid for fid, f in species().items() if kind in f["waters"]]
    if not kinds:
        return 1.0
    have = sum(level(engine, key, fid, cap(fid, kind, size)) for fid in kinds)
    return have / sum(cap(fid, kind, size) for fid in kinds)


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
    kit: dict = field(default_factory=dict)   # the rig as cast (v0.96.0)
    water_band: str = ""            # the water's own depth (band is where the bait sits)
    key: str = ""                   # the water's stock key (v0.97.0)
    miasma: bool = False            # a hunt's water (v0.98.0)
    size: int = 0
    side: str = "south"
    wname: str = ""
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
    k = kit(p)
    water_band = BANDS[w.band[(x, y)]]
    b = w.body[(x, y)]
    s = Session(x, y, (p.x, p.y), w.kinds[b], bait_band(k, water_band), light_at(engine, x, y, where),
                rod(p), bait_type, bait.type.properties.get("bait", ""), kit=k, water_band=water_band,
                key=w.keys[b], size=w.sizes[b], side=w.sides[b], wname=w.names[b], miasma=(where == "miasma"))
    engine.fishing = s
    engine.fishing_last = (x, y, bait_type)
    note(s, f"You cast your {bait.type.name} into {s.wname or data()['waters'][s.kind]['name']}, {s.water_band} water"
         + (f" (it sits {s.band} without a sinker)." if s.band != s.water_band else "."))
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
    if (p.x, p.y) != s.stand or p.stats.is_dead or place(engine) is None \
            or not any(it is s.rod for it in p.all_items()):
        engine.fishing = None
        return False
    if place(engine) == "miasma":                # out there, nothing waits while you fish (v0.98.0)
        near = [m for m in engine.game_map.monsters if getattr(m, "awake", False)
                and abs(m.x - p.x) + abs(m.y - p.y) <= THREAT and not getattr(m, "burrowed", False)]
        if near:
            end(engine, f"The {near[0].name} is coming for you. You drop the line.")
            return False
    return True


def shows_coming(engine, s: Session) -> bool:
    from game import fieldskills
    rank = fieldskills.rank(engine, "angling")
    return species()[s.fish]["tier"] <= rank + s.kit.get("read", 0) or rank >= 3


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
        s.spooked = max(1, STRIKE_SPOOK - s.kit.get("quiet", 0) * 2)
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
            if rng.random() < 0.5 and not _is_lure(engine, s) and not s.kit.get("keep_bait"):
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
    d = engine.date
    ctx = {"side": s.side, "key": s.key, "pulse": d.pulse, "holiday": bool(d.intercalary)}
    if s.miasma:                       # the miasma: the danger word decides how big; no stock (made fresh)
        ctx["max_tier"] = danger(engine) + 1
        stock = None
    else:
        stock = lambda fid: level(engine, s.key, fid, cap(fid, s.kind, s.size)) / cap(fid, s.kind, s.size)
    cands = candidates(s.kind, s.band, s.light, s.bait_key, s.kit, ctx, stock)
    roll = rng.random()
    total = 0.0
    for fid, chance in cands:
        total += chance
        if roll < total:
            return _bite(engine, s, fid, rng)
    if rng.random() < FALSE_TELL:
        s.false_tell = True
        note(s, rng.choice(data()["tells"]["false"]) + (" (Only the current.)" if s.kit.get("true_tells") else ""))
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
    s.window = ((1 if f.get("wary") else 2) + (1 if fieldskills.rank(engine, "angling") >= 2 else 0)
                + s.kit.get("window", 0))
    note(s, data()["tells"]["bite"][f["temper"]])
    from game import sound
    sound.play("fish_bite")
    return True


def _hook(engine, s: Session, rng) -> bool:
    from game import fieldskills
    f = species()[s.fish]
    if f.get("wary") and fieldskills.rank(engine, "angling") < 2 and not s.kit.get("set") and rng.random() < 0.25:
        s.phase = "wait"
        note(s, "You strike, but it's too quick for you.")
        if not _is_lure(engine, s):
            _use_bait(engine, s)
        return True
    item = make(s.fish, rng, s.kind, engine.day)
    s.kg, s.quirk = item.catch["kg"], item.catch["quirk"]
    big = s.kit.get("size", 1) - size_class(s.kg)       # a hook too big for its mouth misses it (v0.96.0)
    if big > 0 and not s.kit.get("any_size") and rng.random() < 0.35 * big:
        s.phase = "wait"
        note(s, "You strike, but the hook's too big for its mouth. It's gone.")
        if not _is_lure(engine, s):
            _use_bait(engine, s)
        return True
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
    """The strain the rig takes before the line goes: the rod's power plus the line's strength (a biter's
    teeth take some off)."""
    k = s.kit or {}
    pw = k.get("power", s.rod.type.properties.get("power", 40)) + k.get("strength", BARE["strength"])
    return pw * (0.85 if species()[s.fish]["temper"] == "biter" else 1.0)


def max_line(s: Session) -> float:
    return (s.kit or {}).get("capacity", BARE["capacity"])


def hold_chance(s: Session, chance: float) -> float:
    """A chance of the hook coming free, after the hook's hold, and worse for a hook too small for the fish."""
    k = s.kit or {}
    small = size_class(s.kg) - k.get("size", 1)
    if small > 0 and not k.get("any_size"):
        chance = chance * (1 + 0.6 * small) + 0.05 * small
    return chance * (1 - k.get("hold", 0) / 100)


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
    k = s.kit or {}
    if move in ("run", "dive"):
        pull *= 1 - k.get("drag", 0) / 100                # the reel's drag eases a run
    factor = ACT[cmd]
    if move == "sulk" and cmd == "reel":
        factor *= 0.8
    if move == "dive" and cmd == "reel":
        factor *= 1.35
    s.tension = s.tension * KEEP + pull * factor
    gain = 0.0
    if cmd == "reel":
        gain = (k.get("retrieve", RETRIEVE) / (1 + s.kg / HEAVY) + (1 if move == "sulk" else 0)
                + ((2 + k.get("spent", 0)) if move == "spent" else 0))
    elif cmd == "give":
        gain = -2
    if move == "run":
        gain -= max(0, 2 - k.get("run_line", 0))
    if move == "lurch":                       # the miasma's fish aren't always where they are (v0.98.0)
        gain += rng.choice((-3, 3))
    s.line -= gain
    s.stamina = max(0.0, s.stamina - TIRE[cmd] - (k.get("tire", 0) if cmd == "hold" else 0)
                    - (1 if move in ("run", "thrash", "dive") else 0))
    s.move = move
    note(s, m["text"])
    lost = ""
    if s.miasma:
        splash(engine, s, rng)
    f = species()[s.fish]
    if f.get("drags") and move in ("run", "dive") and cmd != "give" and s.tension > DRAG_AT * power(s):
        hurt = min(engine.player.stats.hp - 1, rng.randint(2, 4) + f["tier"])
        if hurt > 0:
            engine.player.stats.hp -= hurt
        end(engine, f"The {f['name']} drags you off your feet and into the water! You let go of it and "
                    f"haul yourself out ({hurt} HP).")
        return True
    if move == "thrash" and cmd == "reel" and rng.random() < hold_chance(s, TEAR):
        lost = "The hook tears free as you haul into its thrashing."
    elif move == "run" and rng.random() < hold_chance(s, 0.0):
        lost = "It runs, and the little hook rips out of its mouth."
    elif move in ("left", "right") and cmd != ("right" if move == "left" else "left") \
            and rng.random() < SNAG * (1 - k.get("snag_guard", 0) / 100):
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
        if s.slack >= 2 and rng.random() < hold_chance(s, 0.4) * (1 - k.get("slack_guard", 0) / 100):
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
    if s.fish == "hookjaw" and s.miasma and rng.random() < HOOKJAW_LIVES:
        if _eel_comes(engine, s):
            fieldskills.practise(engine, "angling", f["tier"])
            end(engine, "You haul the hookjaw up to the bank, and it tears free of the hook and comes for you!")
            return True
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
        if not s.miasma:
            take(engine, s.key, s.fish, cap(s.fish, s.kind, s.size))   # it's out of the water now (v0.97.0)
        p = engine.player
        if p.inventory.add(item):
            end(engine, f"You keep the {item.label}. (r to cast again)")
        else:
            from game.items import FloorItem
            engine.game_map.items.append(FloorItem(p.x, p.y, item))
            end(engine, f"No room in your pack: the {item.label} is at your feet. (r to cast again)")
        return False
    if cmd == "gut":
        if not s.miasma:
            take(engine, s.key, s.fish, cap(s.fish, s.kind, s.size))
        end(engine, gut(engine, s, item, _rng(engine)) + " (r to cast again)")
        return True
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


# ---- The tackleman's word on what's biting --------------------------------------------------------
def tip(engine, rng=None) -> str:
    """A fish, where it's biting and on what, this Duel (the tackleman's "What's biting?")."""
    from game import sky
    rng = rng or _rng(engine)
    fid = rng.choice(sorted(k for k, f in species().items() if f["tier"] <= 4))
    f = species()[fid]
    if f.get("miasma"):                      # he's never fished the miasma himself (v0.98.0)
        waters_ = " or ".join(data()["waters"][w]["short"] for w in f["waters"])
        bait = max(f["baits"], key=f["baits"].get)
        bait = {"worms": "a worm", "grubs": "a grub", "dough": "dough", "spinner": "a spinner"}.get(bait, bait)
        return (f"Out in the miasma? Never been. Hunters tell me about {plural(f['name'])}: {waters_}, "
                f"{' or '.join(f['depth'])} water, and they'll take {bait}. The deeper the danger, the bigger "
                "what bites, they say." + (" And mind it doesn't pull you in." if f.get("drags") else ""))
    lit = sky.lit_half()
    dark = "north" if lit == "south" else "south"
    side = {"lit": lit, "dark": dark}.get(f["light"])
    where = []
    for w in f["waters"]:
        if w == "city_river":
            if f["light"] in ("any", "lit" if lit == "south" else "dark"):
                where.append("the city river")
            continue
        sides = [x for x in (f.get("where") or ["north", "south", "east", "west"]) if side is None or x == side
                 or (side == "south" and x in ("east", "west"))]
        if f.get("where") and not sides:
            continue
        noun = {"river": "river", "lake": "lakes", "pond": "ponds"}[w]
        some = "some of " if f.get("share") is not None and w in ("lake", "pond") else ""
        if f.get("where"):
            where.append(f"{some}the {' and '.join(x + 'ern' for x in sides)} {noun}")
        elif side:
            where.append(f"{some}the {side}ern {noun}")
        else:
            where.append(f"{some}the {noun}")
    bait = max(f["baits"], key=f["baits"].get)
    bait = {"worms": "a worm", "grubs": "a grub", "dough": "dough", "spinner": "a spinner"}.get(bait, bait)
    band = " or ".join(f["depth"])
    if not where:
        return (f"The {f['name']}? Not this Duel, not round here. It keeps to the "
                + ("light" if f["light"] == "lit" else "dark") + ", and its waters are on the wrong side of it.")
    places = where[0] if len(where) == 1 else ", ".join(where[:-1]) + " and " + where[-1]
    light = {"lit": " while the light's on them", "dark": " in the dark"}.get(f["light"], "")
    when = ""
    if f.get("holiday"):
        when = " But only in the holiday Pulses, between the Duels."
    elif f.get("pulses"):
        when = f" But only on {' and '.join(f['pulses'])}."
    deep = " You'll want a sinker." if f["depth"] == ["deep"] else ""
    return (f"{plural(f['name']).capitalize()} are in {places}{light}, {band} water. Try {bait}.{deep}"
            + (" Wary, mind. Strike quick." if f.get("wary") else "") + when)


def plural(name: str) -> str:
    if name.endswith(("fish", "carp", "char", "perch", "bream", "back", "cat", "trout", "pike", "tench",
                      "dace", "chub", "loach", "beard")):
        return name
    return name + ("es" if name.endswith(("ch", "sh", "s", "x")) else "s")


# ---- The miasma (stage 4, v0.98.0) -----------------------------------------------------------------
def danger(engine) -> int:
    hunt = getattr(engine, "hunt", None)
    return int(getattr(getattr(hunt, "contract", None), "danger", 1) or 1) if hunt else 1


def splash(engine, s: Session, rng) -> None:
    """A fish fighting on a line draws what's out there: the nearest sleeping creature may wake."""
    if rng.random() >= SPLASH * (1 + danger(engine) / 3):
        return
    p = engine.player
    near = sorted((abs(m.x - p.x) + abs(m.y - p.y), i) for i, m in enumerate(engine.game_map.monsters)
                  if not getattr(m, "awake", False) and abs(m.x - p.x) + abs(m.y - p.y) <= 16)
    if near:
        m = engine.game_map.monsters[near[0][1]]
        m.awake = True
        note(s, "The splashing carries. Something out there has heard it.")


def _eel_comes(engine, s: Session) -> bool:
    """A landed hookjaw tears free and comes at you: the creature, awake, in the water at your feet."""
    from game.monsters import Monster
    t = (getattr(engine, "monster_types", None) or {}).get("hookjaw_eel")
    if t is None:
        return False
    p, gm = engine.player, engine.game_map
    w = waters(gm, "miasma")
    spots = sorted((abs(c[0] - p.x) + abs(c[1] - p.y), c) for c in w.body if not gm.monster_at(*c))
    if not spots or spots[0][0] > 3:
        return False
    x, y = spots[0][1]
    m = Monster.spawn(t, x, y)
    m.awake = True
    gm.monsters.append(m)
    return True


def gut(engine, s: Session, item, rng) -> str:
    """Gut a fish where you stand: what was inside it. (Its meat and scales are for a later stage.)"""
    from game.items import Item
    g = data()["guts"]["miasma" if s.miasma else "home"]
    p = engine.player
    name = item.type.name
    found = []
    roll = rng.random()
    if s.miasma and roll < g.get("bottle", 0):
        from game import keywords
        kw = engine.regions.keywords
        unknown = sorted(w for w in kw.all_ids(ordinary=True) if w not in engine.words)
        if unknown:
            word = kw.word(rng.choice(unknown))
            keywords.learn(engine, [word.id], say=False)
            return (f"You gut the {name}. Inside: a stoppered bottle with a scrap of paper in it, "
                    f"in a hand you don't know. It names a place. You learn the word {word.shown}.")
    roll -= g.get("bottle", 0)
    if s.miasma and roll < g.get("artifact", 0) and getattr(engine, "hunt", None) is not None:
        from game.hunt import pick_artifact
        region = engine.hunt.contract.region
        aid = pick_artifact(region, danger(engine), engine.catalogue, rng)
        art = Item(engine.catalogue[aid])
        _give(engine, art)
        return f"You gut the {name}. Something hard in its belly: {art.type.name}, swallowed whole."
    roll -= g.get("artifact", 0)
    if roll < g.get("shards", 0):
        n = rng.randint(5, 20) * danger(engine) if s.miasma else rng.randint(1, 6)
        p.earn(n, "fishing")
        found.append(f"{n} shard{'s' if n != 1 else ''} it had swallowed")
    from game import sound
    sound.play("butcher")
    return f"You gut the {name}." + (" Inside: " + ", ".join(found) + "." if found else " Nothing inside but fish.")


def _give(engine, item) -> None:
    from game.items import FloorItem
    p = engine.player
    if not p.inventory.add(item):
        engine.game_map.items.append(FloorItem(p.x, p.y, item))
