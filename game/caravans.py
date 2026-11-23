"""Caravans on the Towerway (design-return-journey.md stage 4, part 2; v0.92.0).

User: caravans on the Towerway that trade or ask for an escort. The Towerway is Whisper Poet's road,
now the main east-west route; the stretch inside the Brisering is about three Pulses' travel (lore).
Everything else is the assistant's draft (data/caravans.json).

- **On the road:** `count` caravans travel the Towerway between the Brisering's western edge and
  Bytorsskug's west gate (`path`). Each moves a road cell for every step the Hunter takes on the
  Brisering, or `per_pulse` cells for each Pulse that passes while the Hunter is elsewhere. In town they
  trade `town_wait` Pulses, then head back west; past the edge they're gone, and after `next_wait` a new
  one comes in. They hold still while a fight's on near them, or the Hunter's in the way. World state
  `engine.caravans` (saved as `world.caravans`).
- **Meeting one** (on the Brisering, they're people you can talk to, `caravan:ID`): trade (each has its
  own few goods, `goods`, and buys supplies and materials), walk along with them (`walk`: travel-to
  that keeps beside them), hire on as a guard (`escort`), or hear the road's news (a rumour).
- **Company:** within `company_cells` of a caravan, nobody on the road troubles you (game/road.py).
- **Guarding** (`escort`): see them to the end of their road (the city's west gate, or the western
  edge). You're paid on arrival (`base` + `per_km`, earnings: dues apply) if you were with them
  (within `near`) for at least `share` of the way. While you guard them, raiders may come (`raid` a
  step, at most once a trip): a road encounter of its own ("Raiders"), where letting them take a crate
  halves the pay.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "caravans.json"
COLOR = (220, 190, 110)
_data: dict | None = None
_cache: dict = {}


def data() -> dict:
    global _data
    if _data is None:
        _data = json.loads(DATA.read_text(encoding="utf-8"))
    return _data


# ---- The road ---------------------------------------------------------------------------------------------
def path(engine) -> list:
    """The Towerway's cells from the western edge (index 0) to just outside the west gate."""
    gm = engine.brisering
    if _cache.get("map") is gm:
        return _cache["path"]
    from collections import deque
    start = gm.arrivals["west"]
    prev = {start: None}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in prev and gm.in_bounds(*n) and gm.tile_at(*n).symbol in "R=I" and n not in gm.gates:
                prev[n] = (x, y)
                q.append(n)
    far = min(prev, key=lambda c: (c[0], c[1]))          # the westmost road cell: the edge
    cells = []
    c = far
    while c is not None:
        cells.append(c)
        c = prev[c]
    _cache.update(map=gm, path=cells)
    return cells


def state(engine) -> dict:
    st = engine.__dict__.setdefault("caravans", {})
    st.setdefault("list", [])
    st.setdefault("next_id", 1)
    st.setdefault("spawn", 0)          # cells of time until the next caravan comes in from the west
    st.setdefault("escort", None)
    if not st.get("started"):
        st["started"] = True
        rng = random.Random(engine.day * 7 + 3)
        n, L = data()["count"], len(path(engine))
        for i in range(n):                    # spread along the road, alternately east and west
            _spawn(engine, rng, at=int((i + 0.5) * (L - 1) / n), going=1 if i % 2 == 0 else -1)
    return st


def _spawn(engine, rng, at: int = 0, going: int = 1) -> dict:
    from game import named
    st = engine.caravans
    cid = st["next_id"]
    st["next_id"] = cid + 1
    c = {"id": cid, "leader": named.maker().given_name(rng), "pos": float(at), "dir": going, "wait": 0.0,
         "seed": rng.getrandbits(32)}
    st["list"].append(c)
    make_shop(engine, c, fresh=True)
    return c


def make_shop(engine, c: dict, fresh: bool = False) -> None:
    """The caravan's own little shop (not saved: rebuilt from the caravan); its stock is (saved)."""
    from game.shops import Shop
    from game.stock import Stock
    d = data()
    sid = f"caravan:{c['id']}"
    engine.shops[sid] = Shop(sid, f"{c['leader']}'s caravan", f"{c['leader']}", "", (), tuple(d["buys"]),
                             d["sell_rate"])
    if fresh or sid not in engine.stocks:
        rng = random.Random(c["seed"])
        lo, hi = d["picks"]
        picks = rng.sample(d["goods"], rng.randint(lo, hi))
        entries = []
        for item_id, a, b, x in picks:
            if item_id in engine.catalogue.types:
                n = rng.randint(a, b)
                entries.append({"id": item_id, "price": max(1, round(engine.catalogue[item_id].value * x)),
                                "max": n, "restock": 10 ** 6})
        for item_id, chance, price in d["rare"]:
            if item_id in engine.catalogue.types and rng.random() < chance:
                entries.append({"id": item_id, "price": price, "max": 1, "restock": 10 ** 6})
        engine.stocks[sid] = Stock.from_data(entries, engine.catalogue, engine.day)


def by_id(engine, cid: int):
    return next((c for c in state(engine)["list"] if c["id"] == cid), None)


def cell_of(engine, c) -> tuple:
    p = path(engine)
    return p[max(0, min(len(p) - 1, int(c["pos"])))]


def heading(c) -> str:
    return "town" if c["wait"] > 0 and c["dir"] == -1 else ("east" if c["dir"] == 1 else "west")


def tick(engine, cells: float, walking: bool) -> None:
    """Time passes for the caravans: `cells` of road. `walking`: a step of the Hunter's on the Brisering
    (they're on the map: they hold for fights and for the Hunter, and a guard's company is counted)."""
    st = state(engine)
    d = data()
    L = len(path(engine))
    gm = engine.brisering if walking else None
    p = engine.player
    for c in list(st["list"]):
        if c["wait"] > 0:
            c["wait"] -= cells
            continue
        if walking:
            x, y = cell_of(engine, c)
            if any(m.type.person and abs(m.x - x) + abs(m.y - y) <= 10 for m in gm.monsters):
                continue                       # a fight on the road: they hold
            step = 1 if c["dir"] == 1 else -1
            nxt = path(engine)[max(0, min(L - 1, int(c["pos"]) + step))]
            if (p.x, p.y) == nxt:
                continue                       # you're in the way
        c["pos"] += c["dir"] * cells * d["speed"]
        if walking:
            escort_step(engine, c)
        if c["dir"] == 1 and c["pos"] >= L - 1:          # at the west gate: trading in town
            c["pos"], c["dir"], c["wait"] = L - 1, -1, d["town_wait"] * d["per_pulse"]
            arrive(engine, c, "town")
        elif c["dir"] == -1 and c["pos"] <= 0:           # past the edge: gone west
            arrive(engine, c, "edge")
            st["list"].remove(c)
            engine.shops.pop(f"caravan:{c['id']}", None)
            engine.stocks.pop(f"caravan:{c['id']}", None)
            st["spawn"] = d["next_wait"] * d["per_pulse"]
    if len(st["list"]) < d["count"]:
        st["spawn"] -= cells
        if st["spawn"] <= 0:
            _spawn(engine, random.Random(engine.day * 31 + st["next_id"]), at=0, going=1)
    if engine.in_brisering():
        place(engine)


def place(engine) -> None:
    """The caravans on the Brisering map, as people you can talk to."""
    from game.entity import NPC
    from game.dialogue import Townsperson
    gm = engine.brisering
    gm.npcs = [n for n in gm.npcs if not n.folk_id.startswith("caravan:")]
    for c in state(engine)["list"]:
        if c["wait"] > 0 and c["dir"] == -1:
            continue                           # trading in the city
        fid = f"caravan:{c['id']}"
        if fid not in engine.townsfolk:
            engine.townsfolk[fid] = Townsperson(fid, c["leader"], "Caravaner", "", "@", COLOR,
                                                "A Towerway caravan: wagons, pack animals, a few hired hands, "
                                                "and someone in charge who wants to keep moving.", "caravan")
        if f"caravan:{c['id']}" not in engine.shops:
            make_shop(engine, c)
        x, y = cell_of(engine, c)
        gm.npcs.append(NPC(x, y, "@", COLOR, f"{c['leader']} Caravaner", folk_id=fid, home=(x, y), wander=0))


def near(engine, cells: int) -> bool:
    """A caravan within `cells` of the Hunter on the Brisering (their company)."""
    if not engine.in_brisering():
        return False
    p = engine.player
    for c in state(engine)["list"]:
        if c["wait"] > 0 and c["dir"] == -1:
            continue
        x, y = cell_of(engine, c)
        if abs(x - p.x) + abs(y - p.y) <= cells:
            return True
    return False


# ---- Talking to one -----------------------------------------------------------------------------------------
def talking(engine):
    fid = getattr(engine, "talk_folk", "") or ""
    return by_id(engine, int(fid.split(":")[1])) if fid.startswith("caravan:") else None


def values(engine, folk_id: str) -> dict:
    c = by_id(engine, int(folk_id.split(":")[1]))
    if c is None:
        return {}
    rng = random.Random(c["seed"] + engine.day)
    return {"caravan_line": rng.choice(data()["lines"][heading(c)]), "caravan_leader": c["leader"]}


def offers_escort(engine) -> bool:
    c = talking(engine)
    if c is None or state(engine)["escort"] is not None:
        return False
    left = (len(path(engine)) - 1 - c["pos"]) if c["dir"] == 1 else c["pos"]
    return left >= data()["escort"]["min_cells"] and not (c["wait"] > 0)


def pay_for(engine, c) -> int:
    from game import journey
    e = data()["escort"]
    left = (len(path(engine)) - 1 - c["pos"]) if c["dir"] == 1 else c["pos"]
    return round(e["base"] + e["per_km"] * left * journey.KM_X)


def act(engine, what: str) -> None:
    """A conversation's choice (dialogue effects caravan_trade / caravan_walk / caravan_escort)."""
    c = talking(engine)
    if c is None:
        return
    if what == "trade":
        from game.screens import ShopScreen
        engine.screen = ShopScreen(engine.shops[f"caravan:{c['id']}"])
    elif what == "walk":
        walk_with(engine, c)
    elif what == "escort":
        st = state(engine)
        st["escort"] = {"id": c["id"], "pay": pay_for(engine, c), "with": 0, "steps": 0, "crate": False,
                        "to": "town" if c["dir"] == 1 else "edge"}
        where = "Bytorsskug's west gate" if c["dir"] == 1 else "the western edge of the Brisering"
        engine.log(f"You hire on as a guard for {c['leader']}'s caravan, as far as {where}: "
                   f"{st['escort']['pay']} shards if you see them there.")
        walk_with(engine, c)


def walk_with(engine, c) -> None:
    """Walk along beside the caravan (watched, like travel-to); any key stops it."""
    gen = walk_steps(engine, c["id"])
    if engine.animate_walks:
        engine.start_walk(gen)
    else:
        for _ in gen:
            pass


def walk_steps(engine, cid: int):
    """Keep beside the caravan, step by step, until it reaches the end of its road, or something
    happens (a screen opens, you're hurt, it's gone)."""
    from game.actions import MoveAction, WaitAction
    from game import travel
    p = engine.player
    for _ in range(3000):
        c = by_id(engine, cid)
        if c is None or not engine.in_brisering() or engine.screen is not None or p.stats.is_dead:
            return
        if c["wait"] > 0:
            engine.log(f"{c['leader']}'s caravan has reached the city.")
            return
        hp = p.stats.hp
        x, y = cell_of(engine, c)
        if abs(x - p.x) + abs(y - p.y) <= 2:
            act_ = WaitAction()
        else:
            step = travel.next_step(engine, (x, y), True)
            act_ = MoveAction(*step) if step else WaitAction()
        if act_.perform(engine):
            engine.turn += 1
            engine.end_turn()
        if p.stats.hp < hp or engine.screen is not None:
            return
        yield


# ---- Guarding one -----------------------------------------------------------------------------------------
def escort_step(engine, c) -> None:
    """A step of a caravan's on the map: if you're guarding it, were you with it? Raiders?"""
    st = state(engine)
    es = st["escort"]
    if es is None or es["id"] != c["id"]:
        return
    es["steps"] += 1
    x, y = cell_of(engine, c)
    p = engine.player
    if abs(x - p.x) + abs(y - p.y) <= data()["escort"]["near"]:
        es["with"] += 1
        if engine.screen is None and not es.get("raided") and not any(m.type.person for m in engine.brisering.monsters) \
                and engine.rng.random() < data()["escort"]["raid"]:
            es["raided"] = True                # (at most one raid a trip)
            from game import road
            road.meet(engine, "raid")


def arrive(engine, c, where: str) -> None:
    """A caravan reaches the end of its road: a guard is paid (or not)."""
    st = state(engine)
    es = st["escort"]
    if es is None or es["id"] != c["id"]:
        return
    st["escort"] = None
    share = es["with"] / max(1, es["steps"])
    if share >= data()["escort"]["share"]:
        pay = es["pay"] // 2 if es["crate"] else es["pay"]
        engine.player.earn(pay)
        engine.log(f"{c['leader']}'s caravan is safely in. They pay you {pay} shards"
                   + (", less for the crate the raiders took." if es["crate"] else "."))
    else:
        engine.log(f"{c['leader']}'s caravan got in without you. No pay for a guard who wasn't there.")


def abandoned(engine) -> None:
    """The Hunter left the Brisering (or the caravan) while guarding: the job's off."""
    st = state(engine)
    if st.get("escort") is not None:
        c = by_id(engine, st["escort"]["id"])
        st["escort"] = None
        engine.log(f"You leave {c['leader'] if c else 'the'}'s caravan to its road. No pay.")


def to_save(engine) -> dict:
    st = state(engine)
    return {k: v for k, v in st.items()}


def from_save(engine, d: dict | None) -> None:
    engine.caravans = dict(d or {})
    st = state(engine)
    for c in st["list"]:
        make_shop(engine, c)
