"""The Watermen and Anglers' Guild's contests (v0.100.0): stage 6 of claude/design-fishing.md.

The user's lore: the Watermen and Anglers' Guild (surname Waters) and its tackleman; fishing is
common and fish a staple. The contests, their names, fees and prizes are the assistant's drafts
(data/fish.json "contests").

- **The Holiday Contest** runs through the four holiday Pulses after each Duel: at the city river
  after a Light Duel, at the Brisering's river after a Dark Duel.
- **The Reckon's weigh-in** runs through the first Cycle of every Reckon (but the first of a Duel,
  straight after the holidays), always at the city river.

Each is for one kind of fish, picked from those of its tiers that live at that water in that light.
Weigh in with the waterman (the fish has to be that kind, caught at that water while the contest
runs; you keep it). The entry fee is paid at your first weigh-in. When the contest is over, the
heaviest fish wins: the WAG's anglers and the Guild's other Hunters enter too. A prize waits with
the waterman for the Hunter who won it.

World state: `engine.angling["contest"]` (the one running, or none), `["contest_log"]` (the last
few results), `["prize"]` (a prize not yet collected, with whose it is).
"""
from __future__ import annotations

import random

from game import fishing

WATER_KIND = {"city": "city_river", "river": "river"}
WATER_NAME = {"city": "the city river", "river": "the Brisering's river"}
LOG_KEEP = 8
ORDINAL = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth"}


def settings() -> dict:
    return fishing.data()["contests"]


def state(engine) -> dict:
    return engine.angling


def current(engine) -> dict | None:
    return state(engine).get("contest")


# ---- When -------------------------------------------------------------------------------------------
def starts(date) -> str | None:
    """'grand' or 'small' when a contest starts on this date, else None."""
    if date.intercalary == 1:
        return "grand"
    if not date.intercalary and date.cycle == 1 and date.pulse_number == 1 and (date.judgment, date.reckon) != (1, 1):
        return "small"
    return None


def next_start(engine, kind: str) -> int:
    """Pulses until the next contest of this kind starts."""
    cal = engine.calendar
    limit = cal.per_half + 2 if kind == "grand" else cal.per_reckon * 2 + 2
    for n in range(1, limit):
        if starts(cal.date(engine.day + n)) == kind:
            return n
    return limit


def _when(engine, day: int) -> str:
    return engine.calendar.date(day).short


# ---- Each Pulse -------------------------------------------------------------------------------------
def refresh(engine) -> None:
    """Called as Pulses pass: a contest over is settled; a new one may begin."""
    c = current(engine)
    if c is not None and engine.day > c["end"]:
        settle(engine)
        c = None
    if c is None:
        kind = starts(engine.date)
        if kind:
            begin(engine, kind)


def pool(kind: str, water: str, light: str) -> list[str]:
    """The fish a contest could be for."""
    s = settings()[kind]
    lo, hi = s["tiers"]
    out = []
    for fid, f in sorted(fishing.species().items()):
        if WATER_KIND[water] not in f["waters"] or not lo <= f["tier"] <= hi:
            continue
        if f.get("where") or f.get("share") is not None or f.get("pulses"):
            continue
        if f.get("holiday") and kind != "grand":
            continue
        if f["light"] not in ("any", light):
            continue
        out.append(fid)
    return out


def begin(engine, kind: str, rng=None) -> dict | None:
    from game import sky
    s = settings()[kind]
    d = engine.date
    water = s["water"] if isinstance(s["water"], str) else s["water"].get(d.duel, "city")
    light = sky.light_for(sky.SKY, None, 180.0, d.duel)
    rng = rng or random.Random(engine.day * 7349 + 3)
    fids = pool(kind, water, light)
    if not fids:
        return None
    fid = rng.choice(fids)
    c = {"kind": kind, "name": s["name"], "start": engine.day, "end": engine.day + s["pulses"] - 1,
         "key": water, "fish": fid, "fee": s["fee"], "entered": False, "best": 0.0, "who": ""}
    state(engine)["contest"] = c
    engine.log(f"The Watermen and Anglers' Guild's {s['name']} begins: the heaviest "
               f"{fishing.species()[fid]['name']} from {WATER_NAME[water]} wins. Weigh in with the waterman "
               f"by the end of {_when(engine, c['end'])}.")
    return c


# ---- Weighing in --------------------------------------------------------------------------------------
def counts(c: dict, item) -> bool:
    """Does this fish count for the contest?"""
    if item.catch is None or item.type.properties.get("fish") != c["fish"]:
        return False
    k = item.catch.get("key") or ("city" if item.catch.get("water") == "city_river" else "")
    return k == c["key"] and c["start"] <= item.catch.get("day", -1) <= c["end"]


def weigh_in(engine) -> list[str]:
    """The waterman weighs your fish for the contest that's on. Lines to tell."""
    c = current(engine)
    p = engine.player
    if c is None:
        return ["There's no contest on just now.", "", describe(engine)]
    name = fishing.species()[c["fish"]]["name"]
    fish = [it for it in p.inventory.items if counts(c, it)]
    if not fish:
        return [f"You've no {name} from {WATER_NAME[c['key']]} caught since {c['name']} began.",
                "Only those count. Catch one there and bring it back before it's over."]
    out = []
    if not c["entered"] or c.get("who") != p.full_name:
        if p.shards < c["fee"]:
            return [f"The entry's {c['fee']} shards, and you haven't got them."]
        p.shards -= c["fee"]
        c["entered"], c["who"], c["best"] = True, p.full_name, 0.0
        out.append(f"You pay the {c['fee']}-shard entry. The waterman writes your name in the book.")
    heaviest = max(it.catch["kg"] for it in fish)
    if heaviest > c["best"]:
        was = c["best"]
        c["best"] = heaviest
        out.append(f"Your {name} weighs {fishing.weight_text(heaviest)}"
                   + (f", better than your {fishing.weight_text(was)}." if was else ".") + " That's your entry.")
    else:
        out.append(f"Nothing heavier than the {fishing.weight_text(c['best'])} you've already weighed.")
    out.append(f"You keep your fish. The contest's settled after {_when(engine, c['end'])}.")
    return out


# ---- Who else is fishing ------------------------------------------------------------------------------
def field(engine, c: dict) -> list[tuple[str, float]]:
    """The other entrants and their heaviest: [(name, kg)]. The same for a contest however often asked."""
    s = settings()
    k = s[c["kind"]]
    rng = random.Random(c["start"] * 131 + len(c["fish"]))
    names = []
    try:
        from game import rivals
        home = sorted(rivals.home(engine), key=lambda r: r["id"])
        rng.shuffle(home)
        names += [rivals.full_name(r) for r in home[: k["entrants"] // 2]]
    except Exception:
        pass
    from game import named
    maker = named.maker()
    while len(names) < k["entrants"]:
        names.append(f"{maker.given_name(rng)} {rng.choice(s['anglers'])}")
    usual, spread = fishing.species()[c["fish"]]["kg"]
    return [(n, round(max(usual * max(0.35, rng.gauss(1.0, spread)) for _ in range(k["tries"])), 3)) for n in names]


def settle(engine) -> dict:
    """The contest is over: who won, and a prize for the Hunter if they placed."""
    c = state(engine).pop("contest")
    s = settings()[c["kind"]]
    board = field(engine, c)
    you = c.get("who") if c.get("entered") and c.get("best") else ""
    if you:
        board.append((you, c["best"]))
    board.sort(key=lambda e: -e[1])
    fish = fishing.species()[c["fish"]]["name"]
    winner, kg = board[0]
    place = next((i + 1 for i, (n, _) in enumerate(board) if you and n == you), 0)
    result = {"name": c["name"], "fish": c["fish"], "key": c["key"], "end": c["end"], "winner": winner,
              "kg": kg, "you": you, "place": place, "of": len(board)}
    log = state(engine).setdefault("contest_log", [])
    log.append(result)
    del log[:-LOG_KEEP]
    text = (f"{c['name'][0].upper() + c['name'][1:]} is over: {winner} won with a {fish} of "
            f"{fishing.weight_text(kg)}.")
    if place:
        text += f" You came {ORDINAL.get(place, str(place))} of {len(board)}."
        if place <= len(s["prizes"]):
            shards, item = s["prizes"][place - 1]
            if item == "tackle":
                item = random.Random(c["start"]).choice(settings()["tackle"])
            state(engine)["prize"] = {"who": you, "shards": shards, "item": item, "name": c["name"], "place": place}
            text += " The waterman has your prize."
    engine.log(text)
    try:
        from game import rivals
        r = next((r for r in engine.rivals if rivals.full_name(r) == winner), None)
        if r is not None:
            rivals.news(engine, r, f"won {c['name']} with a {fish} of {fishing.weight_text(kg)}.", tell=False)
    except Exception:
        pass
    return result


# ---- Prizes ---------------------------------------------------------------------------------------------
def prize_for(engine) -> dict | None:
    pr = state(engine).get("prize")
    return pr if pr and pr.get("who") == engine.player.full_name else None


def collect(engine) -> str:
    from game.items import Item
    pr = prize_for(engine)
    if pr is None:
        return "The waterman has nothing waiting for you."
    p = engine.player
    p.earn(pr["shards"], "fishing")
    got = [f"{pr['shards']} shards"]
    if pr.get("item"):
        iid, _, n = pr["item"].partition("*")
        t = engine.catalogue[iid]
        item = Item(t, int(n or 1))
        fishing._give(engine, item)
        got.append(t.label(item.count) if item.count > 1 else fishing._a(t.name))
    del state(engine)["prize"]
    from game import sound
    sound.play("pay")
    return f"Your prize for {ORDINAL.get(pr['place'], 'placing')} place in {pr['name']}: " + " and ".join(got) + "."


# ---- Telling ----------------------------------------------------------------------------------------------
def describe(engine) -> str:
    """The waterman on the contests: the one on, or when the next ones are."""
    c = current(engine)
    p = engine.player
    if c is not None:
        name = fishing.species()[c["fish"]]["name"]
        left = c["end"] - engine.day
        when = "today's the last Pulse of it" if left <= 0 else f"{left} more Pulse{'s' if left != 1 else ''} to go"
        text = (f"It's {c['name']}: the heaviest {name} from {WATER_NAME[c['key']]}, {when}. "
                f"Entry's {c['fee']} shards, paid when you first weigh in. Catch it there, bring it here.")
        if c.get("entered") and c.get("who") == p.full_name:
            text += f" You're in, with {fishing.weight_text(c['best'])}."
        return text
    small, grand = next_start(engine, "small"), next_start(engine, "grand")
    s = settings()
    text = (f"Nothing on just now. {s['small']['name'][0].upper() + s['small']['name'][1:]} starts in {small} "
            f"Pulse{'s' if small != 1 else ''}, at the city river. {s['grand']['name'][0].upper() + s['grand']['name'][1:]} "
            f"is in the holidays after the Duel, {grand} Pulse{'s' if grand != 1 else ''} off.")
    if prize_for(engine):
        text += " And I've your prize here."
    return text


def past_lines(engine) -> list[str]:
    log = state(engine).get("contest_log", [])
    if not log:
        return ["No contests settled yet in the book."]
    out = ["The Watermen and Anglers' Guild's contests, the latest last:", ""]
    for r in log:
        fish = fishing.species()[r["fish"]]["name"]
        line = (f"{r['name'][0].upper() + r['name'][1:]} ({_when(engine, r['end'])}, a {fish}): {r['winner']}, "
                f"{fishing.weight_text(r['kg'])}")
        if r.get("place"):
            line += f". You: {ORDINAL.get(r['place'], str(r['place']))} of {r['of']}"
        out.append(line + ".")
    return out
