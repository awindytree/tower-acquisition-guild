"""Rival Hunters: other members of the Guild, with lives of their own (world state).

A small cast (data/rivals.json). Each Pulse, a rival at home and rested may take a
contract off a gate board (it shows as taken there that day), fill a request or take an
odd job. A hunt off-screen takes its depth in Pulses and a Cycle, then the rest; its
outcome is rolled from their level and the danger. Successes bring experience (your
level curve) and an artifact for the workshop to sell; some rivals die. They age like you,
retire, die of old age, and are remembered in the Hall of Hunters; new ones join.

Sometimes a rival goes after the same contract as you: a race. They move through the
hunt's areas at their own pace (seen when they're in your area; you can't fight each
other), and whoever reaches the prize first has it.
"""
from __future__ import annotations

import json
import random
from collections import deque
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
LADDER = [(1, 1), (2, 2), (4, 3), (6, 4), (8, 5)]   # (level, danger): how dangerous rivals go, by level


@lru_cache(maxsize=1)
def settings() -> dict:
    return json.loads((DATA / "rivals.json").read_text(encoding="utf-8"))


def COLOR() -> tuple:
    """How rivals look on the map (data/rivals.json "color")."""
    return tuple(settings().get("color", (80, 180, 255)))


def full_name(r: dict) -> str:
    return f"{r['given']} {r['calling']} Hunters"


def level_for(xp: int) -> int:
    from game.stats import xp_for_level
    lv = 1
    while xp >= xp_for_level(lv + 1):
        lv += 1
    return lv


# ---- The cast -----------------------------------------------------------------------------------------
def make(engine, rng: random.Random, level: int | None = None) -> dict:
    from game import aging
    from game.names import NameMaker
    from game.stats import xp_for_level
    s = settings()
    taken = {r["given"] for r in engine.rivals} | {engine.player.name}
    maker = NameMaker(DATA / "names.json")
    given = maker.given_name(rng)
    for _ in range(20):
        if given not in taken:
            break
        given = maker.given_name(rng)
    level = level or 1
    age = aging.roll_age(rng) + (level - 1) * aging.calendar().per_judgment // 2   # experience takes years
    engine.next_rival_id += 1
    return {"id": engine.next_rival_id, "given": given, "calling": rng.choice(s["callings"]),
            "temperament": rng.choice(sorted(s["temperaments"])), "born": engine.day - age,
            "joined": engine.day, "xp": xp_for_level(level), "level": level, "hunts": 0,
            "status": "home", "ready": engine.day, "back": 0, "trip": None, "news": [],
            "judgments_seen": aging.total_judgments(age)}


def start_cast(engine) -> None:
    """A new game: the Guild's other Hunters, of mixed experience."""
    rng = random.Random(engine.rng.random())
    engine.rivals, engine.next_rival_id = [], 0
    lo, hi = settings()["start_levels"]
    for _ in range(settings()["count"]):
        r = make(engine, rng, rng.randint(lo, hi))
        r["hunts"] = rng.randint(0, 4 * r["level"])
        r["ready"] = engine.day + rng.randint(0, 60)    # not all rested at once
        engine.rivals.append(r)
    engine.rival_taken = {"day": engine.day, "taken": {}}


def home(engine) -> list[dict]:
    return [r for r in engine.rivals if r["status"] == "home"]


def by_id(engine, rid) -> dict | None:
    return next((r for r in engine.rivals if str(r["id"]) == str(rid)), None)


def news(engine, r: dict, text: str, tell: bool = True) -> None:
    """Something a rival did: kept as their news (what they talk about), and told if you're in the city."""
    r["news"] = (r["news"] + [text])[-3:]
    if tell and engine.hunt is None:
        engine.log(f"{full_name(r)} {text}")


# ---- Each Pulse -----------------------------------------------------------------------------------------
def day(engine) -> None:
    from game import aging
    s = settings()
    rng = engine.rng
    if engine.rival_taken.get("day") != engine.day:      # a new day: new boards
        engine.rival_taken = {"day": engine.day, "taken": {}}
    for r in list(engine.rivals):
        if r["status"] == "hunting" and r["back"] <= engine.day and not race_running(engine, r):
            come_home(engine, r, won=(r["trip"] or {}).get("decided"))
        # The years.
        age = engine.day - r["born"]
        js = aging.total_judgments(age)
        if js > r["judgments_seen"]:
            r["judgments_seen"] = js
            past_old = js - aging.to_judgments(aging.settings()["old_age_from"])
            if past_old >= 0 and rng.random() < aging.settings()["old_age_chance"] * (past_old + 1):
                gone(engine, r, "died of old age")
                continue
            if (r["status"] == "home" and js >= aging.to_judgments(s["retire_from"])
                    and rng.random() < s["retire_chance"]):
                gone(engine, r, "retired")
                continue
        # A rested rival at home finds something to do.
        if r["status"] == "home" and r["ready"] <= engine.day:
            roll = rng.random()
            d = s["daily"]
            if roll < d["contract"]:
                take_from_board(engine, r)
            elif roll < d["contract"] + d["request"] and engine.requests:
                req = rng.choice(engine.requests)
                engine.requests.remove(req)
                who = engine.townsfolk[req.folk_id].full_name if req.folk_id in engine.townsfolk else "someone"
                news(engine, r, f"filled {who}'s request for {req.thing(engine.catalogue)}.")
            elif roll < d["contract"] + d["request"] + d["job"] and [j for j in engine.job_board if not j.story]:
                job = rng.choice([j for j in engine.job_board if not j.story])
                engine.job_board.remove(job)
                news(engine, r, f"took a job off the bounty board: {job.text(engine)}.")
    engine.rivals = [r for r in engine.rivals if r["status"] != "gone"]
    if len(engine.rivals) < s["count"] and rng.random() < s["join_chance"]:
        r = make(engine, rng)
        engine.rivals.append(r)
        if engine.hunt is None:
            engine.log(f"A new Hunter, {full_name(r)}, has joined the Guild.")
    place_in_hall(engine)


def rank(r: dict) -> int:
    from game import ranks
    return ranks.rank_for(r["hunts"], r["level"])


def ladder_danger(r: dict) -> int:
    """How dangerous a contract a rival goes for: by level, within their rank."""
    from game import ranks
    want = max([d for lv, d in LADDER if r["level"] >= lv] or [1])
    return min(want, ranks.max_danger(rank(r)))


def take_from_board(engine, r: dict) -> None:
    """A rival takes a contract off the Guild's board (game/postings.py)."""
    from game import postings
    taken = engine.rival_taken["taken"]
    mine = {engine.hunt.contract.seed if engine.hunt else None,
            engine.player.contract.seed if engine.player.contract else None}
    top = ladder_danger(r)
    board = [c for c in postings.generated(engine, engine.day)
             if str(c.seed) not in taken and c.seed not in mine and c.danger <= top]
    if not board:
        return
    c = min(board, key=lambda c: (abs(c.danger * 2 - r["level"]), c.depth))
    taken[str(c.seed)] = r["id"]
    set_out(engine, r, c, race=False)


def set_out(engine, r: dict, c, race: bool) -> None:
    r["status"] = "hunting"
    r["back"] = engine.day + c.depth + engine.calendar.per_cycle
    r["trip"] = {"region": c.region.id, "danger": c.danger, "depth": c.depth, "artifact": c.artifact_id,
                 "race": race}


def odds(r: dict, danger: int) -> tuple[float, float]:
    s = settings()
    gap = r["level"] - 2 * danger
    clamp = lambda d: max(d["low"], min(d["high"], d["base"] + d["per_level"] * gap))
    return clamp(s["success"]), clamp(s["death"])


def come_home(engine, r: dict, won: bool | None = None) -> None:
    """A rival's hunt ends: rolled, unless a race decided it (won True/False)."""
    from game import aging
    trip = r["trip"]
    region = engine.regions[trip["region"]].name if trip["region"] in engine.regions else "the wild"
    success, death = odds(r, trip["danger"])
    if won is None and engine.rng.random() < death:
        gone(engine, r, f"killed in {region}")
        return
    ok = won if won is not None else engine.rng.random() < success
    r["status"], r["trip"] = "home", None
    r["ready"] = engine.day + aging.settings()["rest_pulses"]
    if ok:
        r["hunts"] += 1
        r["xp"] += settings()["xp_per_danger"] * trip["danger"]
        from game import works
        works.rival_trickle(engine, engine.rng)     # their dues: a trickle to the Guild's works (v0.60.0)
        before = r["level"]
        r["level"] = level_for(r["xp"])
        art = engine.catalogue[trip["artifact"]] if trip["artifact"] in engine.catalogue.types else None
        if art and art.repairs_to:      # sold through the workshop: it goes up for sale, repaired
            working = engine.catalogue[art.repairs_to]
            for wid in engine.workshops:
                engine.stock(wid).add(working.id, working.value)
                break
        rarity = art.rarity.name.lower() if art and art.rarity else ""
        what = f"{'an' if rarity[:1] in 'aeiou' else 'a'} {rarity} artifact" if rarity else "what they went for"
        news(engine, r, f"came back from {region} with {what}." + (" They're stronger for it." if r["level"] > before else ""),
             tell=bool(trip.get("race")))
        from game import trophies                   # now and then a body for the trophy wall (v0.64.0, user)
        said = trophies.rival_trophy(engine, full_name(r), trip, engine.rng)
        if said:
            news(engine, r, said)
    else:
        news(engine, r, f"came back from {region} empty-handed.", tell=bool(trip.get("race")))


def gone(engine, r: dict, cause: str) -> None:
    """A rival's story ends: remembered in the Hall of Hunters."""
    from game import aging
    r["status"] = "gone"
    from game import ranks
    engine.hall.append({"name": full_name(r), "rank": ranks.name(rank(r)), "age": engine.day - r["born"], "level": r["level"],
                        "hunts": r["hunts"], "joined": r["joined"], "ended": engine.day, "cause": cause})
    word = {"retired": "has retired from the hunt."}.get(cause, f"is dead: {cause}.")
    if engine.hunt is None:
        engine.log(f"{full_name(r)} {word}")


# ---- In the guild hall --------------------------------------------------------------------------------------
def register(engine, r: dict) -> str:
    """Make the rival someone you can talk to (and look at). Returns their folk id."""
    from game.dialogue import Townsperson
    fid = f"rival:{r['id']}"
    from game import ranks
    engine.townsfolk[fid] = Townsperson(fid, r["given"], r["calling"], "Hunters", "@", COLOR(),
                                        f"A Hunter of the Guild: {ranks.name(rank(r))}, level {r['level']}.", "rival")
    return fid


def place_in_hall(engine) -> None:
    """Rivals at home stand about the guild hall (at the city map's rival spots)."""
    from game.dialogue import Townsperson
    from game.entity import NPC
    city = engine.city
    city.npcs = [n for n in city.npcs if not n.folk_id.startswith("rival:")]
    spots = list(engine.rival_spots)
    for r in home(engine):
        if not spots:
            break
        x, y = spots.pop(0)
        fid = register(engine, r)
        if (engine.player.x, engine.player.y) == (x, y) and engine.game_map is city:
            continue
        city.npcs.append(NPC(x, y, "@", COLOR(), full_name(r), folk_id=fid, home=(x, y), wander=0))


def values(engine, folk_id: str) -> dict:
    """Words for a rival's conversation (data/dialogue/rival.json)."""
    from game import aging
    from game.dialogue import fill
    r = by_id(engine, folk_id.split(":", 1)[1])
    if r is None:
        return {}
    s = settings()
    rng = random.Random(engine.turn * 31 + r["id"])
    greet = fill(engine, rng.choice(s["temperaments"][r["temperament"]]))
    race = fill(engine, rng.choice(s["race_lines"][r["temperament"]]))
    last = r["news"][-1] if r["news"] else "hasn't been out since joining."
    from game import ranks
    return {"rival_name": full_name(r), "rival_given": r["given"], "rival_greeting": greet, "rival_race_line": race,
            "rival_rank": ranks.name(rank(r)),
            "rival_level": r["level"], "rival_hunts": r["hunts"],
            "rival_age": aging.describe(engine.day - r["born"]),
            "rival_news": _first_person(last)}


def _first_person(text: str) -> str:
    """Their news in their own words: 'came back from ... They're stronger for it.' ->
    'I came back from ... I'm stronger for it.'"""
    if text.startswith("hasn't"):
        return "I haven't been out since I joined."
    return "I " + text.replace(" They're ", " I'm ")


# ---- The race ---------------------------------------------------------------------------------------------------
def maybe_race(engine, contract) -> None:
    """You've taken a contract: a rival at home may go after the same prize."""
    s = settings()
    if not contract.artifact_id or contract.story or contract.free or engine.rng.random() >= s["race_chance"]:
        return
    ready = [r for r in home(engine)]
    if not ready:
        return
    r = engine.rng.choice(ready)
    rt = s["race_turns"]
    set_out(engine, r, contract, race=True)
    engine.hunt.race = {"rival": r["id"], "start": engine.turn,
                        "per_area": max(rt["min"], rt["base"] - rt["per_level"] * r["level"]), "outcome": None}
    engine.log(f"{full_name(r)} has taken the same contract. It's a race for the "
               f"{engine.catalogue[contract.artifact_id].name}.")
    place_in_hall(engine)


def race_running(engine, r: dict) -> bool:
    h = engine.hunt
    return bool(h and h.race and str(h.race["rival"]) == str(r["id"]) and h.race["outcome"] is None)


def _path(area, start, goal) -> list:
    prev = {start: None}
    q = deque([start])
    while q:
        c = q.popleft()
        if c == goal:
            break
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):   # four-way, like everyone else
            n = (c[0] + dx, c[1] + dy)
            if n not in prev and area.in_bounds(*n) and area.is_walkable(*n):
                prev[n] = c
                q.append(n)
    if goal not in prev:
        return [start]
    out, c = [], goal
    while c is not None:
        out.append(c)
        c = prev[c]
    return out[::-1]


def tick(engine) -> None:
    """Each turn of a hunt with a race on: move the rival along; at the end, they take the prize."""
    h = engine.hunt
    if h is None or not h.race:
        return
    gm = engine.game_map
    gm.npcs = [n for n in gm.npcs if not n.folk_id.startswith("rival:")]
    if h.race["outcome"] is not None:   # the race is over: they've gone (no one left standing in a doorway)
        return
    r = by_id(engine, h.race["rival"])
    if r is None:
        h.race["outcome"] = "you"
        return
    progress = (engine.turn - h.race["start"]) / h.race["per_area"]
    depth = h.contract.depth
    if progress >= depth:
        h.race["outcome"] = "rival"
        last = h.area(depth - 1, engine.catalogue)
        last.items = [f for f in last.items if f.item.type.id != h.contract.artifact_id]
        name = engine.catalogue[h.contract.artifact_id].name
        engine.log(f"A shout from deeper in: {full_name(r)} has the {name}. The race is lost.")
        return
    index = int(progress)
    if index != h.current:
        return
    if not hasattr(h, "race_paths"):
        h.race_paths = {}
    if index not in h.race_paths:
        h.race_paths[index] = _path(gm, h.entries[index], h.far_ends[index])
    path = h.race_paths[index]
    x, y = path[min(len(path) - 1, int((progress - index) * len(path)))]
    if (x, y) == (engine.player.x, engine.player.y) or gm.monster_at(x, y):
        x, y = h.race.get("at", (x, y))
        if (x, y) == (engine.player.x, engine.player.y):
            return
    h.race["at"] = (x, y)
    from game.entity import NPC
    gm.npcs.append(NPC(x, y, "@", COLOR(), full_name(r), folk_id=register(engine, r), home=(x, y), wander=0))
    if not h.race.get("seen") and engine.visible is not None and engine.visible[x, y]:
        h.race["seen"] = True
        engine.log(f"You catch sight of {full_name(r)}, heading deeper.")


def on_pickup(engine, item_id: str) -> None:
    """You have the prize: the rival gives up."""
    h = engine.hunt
    if not h or not h.race or h.race["outcome"] is not None or item_id != h.contract.artifact_id:
        return
    h.race["outcome"] = "you"
    r = by_id(engine, h.race["rival"])
    engine.game_map.npcs = [n for n in engine.game_map.npcs if not n.folk_id.startswith("rival:")]
    if r:
        engine.log(f"You beat {full_name(r)} to it. Somewhere behind you, they turn for home.")


def end_race(engine, hunt) -> None:
    """The hunt is over: the rival's trip ends by the race (or rolls on, if you left it undecided)."""
    if hunt is None or not getattr(hunt, "race", None):
        return
    r = by_id(engine, hunt.race["rival"])
    if r is None or r["status"] != "hunting":
        return
    outcome = hunt.race["outcome"]
    r["back"] = engine.day + engine.calendar.per_cycle
    if outcome is not None:
        r["trip"]["decided"] = outcome == "rival"
    hunt.race["outcome"] = hunt.race["outcome"] or "left"
