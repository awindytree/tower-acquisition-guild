"""People on the road (user, 2026-11-23; design: claude/design-return-journey.md, stage 3).

User: there should be risk on the walk home, but hostile fauna isn't lore-accurate for the Brisering;
people are the danger. Highwaymen, a toll on the road, desperate locals, deserters, failed Hunters gone
bad (not Bermann outcasts): the Brisering is full of settlements, open ground and Hunters coming home
with finds, a rich hunting ground for highwaymen. Encounters can turn into fights; fighting people will
carry a consequence after v1.0 (recorded here, `engine.road`, nothing acts on it yet).

- **When** (`maybe`, after each step on the Brisering): a chance per step, higher on a road or bridge
  (watched) than off it, times what you carry (`worth`: shards, artifacts, a contract's prize); never
  within `quiet_km` of Bytorsskug; at most one a Pulse.
- **What** (`data/road.json` "encounters"): a toll (on a road), a robbery (more likely the more you
  carry), hungry people. Shown in an `EncounterScreen`: a few lines and choices.
- **Choices:** pay / hand it over / give; talk them down (Bargaining, Acumen); bluff (rank, level, how
  many of them); run (Celerity, how many of them); go around (a toll: a Pulse lost); refuse (hungry
  people: they may snatch something); fight (they come at you, on the map, with the usual combat).
- **People** are combatants in the monsters.json format (`"person": true`): no corpse, no bestiary, no
  bounties; a body drops its purse. Most run when hurt (`flees`).
All numbers and words are the assistant's drafts.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "road.json"
ROADS = "R=I"           # road, bridges
_data: dict | None = None
_types: dict | None = None


def data() -> dict:
    global _data
    if _data is None:
        _data = json.loads(DATA.read_text(encoding="utf-8"))
    return _data


def people_types() -> dict:
    global _types
    if _types is None:
        from game.monsters import type_from_dict
        _types = {pid: type_from_dict(pid, d) for pid, d in data()["people"].items()}
    return _types


def state(engine) -> dict:
    """World state (saved as world.road): what's happened on the road. The post-1.0 consequence of
    fighting people will read it (user)."""
    st = engine.__dict__.setdefault("road", {})
    for k in ("met", "fought", "killed", "paid"):
        st.setdefault(k, 0)
    st.setdefault("log", [])
    st.setdefault("last_day", -1)
    return st


def note(engine, kind: str, choice: str, **more) -> None:
    st = state(engine)
    st["log"] = (st["log"] + [{"day": engine.day, "kind": kind, "choice": choice, **more}])[-50:]


# ---- What you carry ---------------------------------------------------------------------------------------
def worth(engine) -> int:
    """What a robber would see in you: shards, broken artifacts (at the Artificer's buying price), and the
    contract's prize."""
    from game import artifacts
    p = engine.player
    total = p.shards
    for it in p.inventory.items:
        if it.type.kind == "artifact":
            try:
                total += artifacts.broken_price(it.type) * it.count if it.type.repairs_to else it.type.value // 2
            except Exception:
                total += it.type.value // 4
    c = p.contract
    if c is not None and c.artifact_id and p.inventory.count_of(c.artifact_id):
        total += 100
    return total


def most_wanted(engine):
    """What robbers ask for: the contract's prize, else the most valuable artifact, else None (shards)."""
    p = engine.player
    c = p.contract
    if c is not None and c.artifact_id and p.inventory.count_of(c.artifact_id) and \
            not engine.catalogue[c.artifact_id].properties.get("no_drop"):
        return next(it for it in p.inventory.items if it.type.id == c.artifact_id)
    arts = [it for it in p.inventory.items if it.type.kind == "artifact" and not it.type.properties.get("locked")]
    return max(arts, key=lambda it: it.type.value) if arts else None


# ---- When -------------------------------------------------------------------------------------------------
def on_road(engine) -> bool:
    p = engine.player
    return engine.game_map.tile_at(p.x, p.y).symbol in ROADS


def chance(engine) -> float:
    """This step's chance of meeting someone."""
    from game import journey
    ch = data()["chance"]
    gm, p = engine.game_map, engine.player
    import numpy as np
    from game.tiles import SYMBOL_TO_INDEX
    b = np.argwhere(gm.kinds == SYMBOL_TO_INDEX["B"])
    if journey.km(gm, p.x, p.y, (float(b[:, 0].mean()), float(b[:, 1].mean()))) < ch["quiet_km"]:
        return 0.0
    base = ch["road"] if on_road(engine) else ch["off_road"]
    return base * min(ch["lure_cap"], 1 + worth(engine) / ch["lure"])


def maybe(engine) -> None:
    """After a step on the Brisering: someone on the road?"""
    if engine.screen is not None or engine.hunt is not None or engine.player.stats.is_dead:
        return
    gm, p = engine.game_map, engine.player
    gm.monsters = [m for m in gm.monsters if not (m.type.person and abs(m.x - p.x) + abs(m.y - p.y) > 20)]
    if any(m.type.person for m in gm.monsters):
        return                          # (a fight's still on; those who ran far are gone)
    st = state(engine)
    if st["last_day"] == engine.day or engine.day < st.get("quiet_until", -1):
        return
    if engine.rng.random() >= chance(engine):
        return
    st["last_day"] = engine.day
    meet(engine, pick(engine))


def pick(engine) -> str:
    rng = engine.rng
    enc = data()["encounters"]
    w = worth(engine)
    road = on_road(engine)
    kinds, weights = [], []
    for k, e in enc.items():
        if e.get("road_only") and not road:
            continue
        kinds.append(k)
        weights.append(e["weight"] + (w / e["lure_weight"] if e.get("lure_weight") else 0))
    return rng.choices(kinds, weights)[0]


# ---- Meeting them -----------------------------------------------------------------------------------------
def meet(engine, kind: str) -> None:
    """Someone on the road: make the encounter and open its window."""
    from game.screens import EncounterScreen
    e = data()["encounters"][kind]
    rng = engine.rng
    p = engine.player
    lo, hi = e["count"]
    n = rng.randint(lo, hi)
    if kind != "beggars" and p.stats.level < 4:
        n = min(n, 2)
    who = [rng.choice(e["who"]) for _ in range(n)]
    if kind == "robbery" and p.stats.level < 5:
        who = ["deserter" if w == "failed_hunter" else w for w in who]
    enc = {"kind": kind, "title": e["title"], "who": who, "demand": toll(engine), "tried": []}
    want = most_wanted(engine) if kind == "robbery" else None
    enc["want"] = want
    enc["want_name"] = want.type.name if want else f"{enc['demand']} shards"
    text = rng.choice(e["text"]).format(demand=enc["demand"], want=_the(enc["want_name"], want))
    enc["text"] = text
    st = state(engine)
    st["met"] += 1
    engine.log(f"{e['title']}: " + ("someone" if n == 1 else f"{n} of them") + " in your way.")
    engine.screen = EncounterScreen(enc)


def _the(name: str, item) -> str:
    return f"the {name}" if item is not None else name


def toll(engine) -> int:
    p = engine.player
    return max(5, min(200, round(8 + p.shards * 0.15 + p.stats.level * 2)))


def _pct(x: float) -> int:
    return max(5, min(85, round(x)))


def talk_chance(engine, enc) -> int:
    from game import bargaining  # noqa: F401  (Bargaining's rank)
    p = engine.player
    rank = p.skill("bargaining").rank if "bargaining" in getattr(engine, "skills", {}) else 1
    return _pct(25 + 10 * (rank - 1) + 3 * (p.stats["acumen"] - 10) + (5 if p.rank >= 1 else 0)
                - (15 if enc["kind"] == "robbery" else 0))


def bluff_chance(engine, enc) -> int:
    p = engine.player
    hard = sum(1 for w in enc["who"] if w == "failed_hunter")
    return _pct(15 + 10 * p.rank + 2 * p.stats.level - 8 * (len(enc["who"]) - 1) - 10 * hard)


def run_chance(engine, enc) -> int:
    p = engine.player
    return _pct(40 + 4 * (p.stats["celerity"] - 10) - 10 * (len(enc["who"]) - 1))


def choices(engine, enc) -> list[tuple[str, str]]:
    """[(key, label)] for this encounter, as things stand."""
    p = engine.player
    k, tried = enc["kind"], enc["tried"]
    out = []
    if k == "toll":
        out.append(("pay", f"Pay the toll ({enc['demand']} shards)" if p.shards >= enc["demand"]
                    else f"Pay what you have ({p.shards} shards)"))
    elif k == "robbery":
        out.append(("hand", f"Hand over {_the(enc['want_name'], enc['want'])}"))
    else:
        if p.inventory.count_of("ration"):
            out.append(("feed", "Give them a ration"))
        if p.shards >= 5:
            out.append(("give", "Give them 5 shards"))
        out.append(("refuse", "Shake your head and walk on"))
    if k != "beggars" and "talk" not in tried:
        out.append(("talk", f"Talk them down ({talk_chance(engine, enc)}%)"))
    if k != "beggars" and "bluff" not in tried:
        out.append(("bluff", f"Stand your ground: a Hunter of the Guild ({bluff_chance(engine, enc)}%)"))
    if k != "beggars":
        out.append(("run", f"Run ({run_chance(engine, enc)}%)"))
    if k == "toll":
        out.append(("around", "Turn back and go round another way (a Pulse)"))
    out.append(("fight", "Fight"))
    return out


def choose(engine, enc, key: str) -> tuple[list[str], bool]:
    """Do it. Returns (lines to show, whether it's over: False = choose again)."""
    p = engine.player
    rng = engine.rng
    st = state(engine)
    k = enc["kind"]
    roll = rng.randint(1, 100)
    if key == "pay":
        paid = min(p.shards, enc["demand"])
        p.shards -= paid
        st["paid"] += paid
        note(engine, k, key, paid=paid)
        if paid < enc["demand"] // 2:
            item = most_wanted(engine)
            if item is not None:
                p.inventory.items.remove(item)
                return [f"You hand over {paid} shards. It isn't enough: they take the {item.type.name} too, and let you go."], True
        return [f"You count out {paid} shards. They step aside, and wish you a good walk home."], True
    if key == "hand":
        item = enc["want"]
        if item is not None and item in p.inventory.items:
            p.inventory.items.remove(item)
            note(engine, k, key, item=item.type.id)
            return [f"You hand over the {item.type.name}. They melt back off the road with it."], True
        paid = min(p.shards, enc["demand"])
        p.shards -= paid
        st["paid"] += paid
        note(engine, k, key, paid=paid)
        return [f"You hand over {paid} shards. They melt back off the road."], True
    if key == "feed":
        p.inventory.remove(next(i for i, it in enumerate(p.inventory.items) if it.type.id == "ration"), 1)
        note(engine, k, key)
        return [_grateful(engine)], True
    if key == "give":
        p.shards -= 5
        st["paid"] += 5
        note(engine, k, key)
        return [_grateful(engine)], True
    if key == "refuse":
        note(engine, k, key)
        if roll <= 40:
            loose = [it for it in p.inventory.items if it.type.kind == "consumable" and it.type.stackable]
            if loose:
                it = rng.choice(loose)
                p.inventory.remove(p.inventory.items.index(it), 1)
                return [f"One of them darts in and away again with a {it.type.name} from your pack."], True
        return ["They watch you go. Nobody follows."], True
    if key == "talk":
        enc["tried"].append("talk")
        if roll <= talk_chance(engine, enc):
            note(engine, k, key, ok=True)
            return ["You talk, and keep talking. In the end they wave you through, mostly to be rid of you."], True
        if k == "toll":
            enc["demand"] = round(enc["demand"] * 1.5)
            return [f"They don't care for your tone. The toll's {enc['demand']} shards now."], False
        return start_fight(engine, enc, "They've heard it all before. They come at you.")
    if key == "bluff":
        enc["tried"].append("bluff")
        if roll <= bluff_chance(engine, enc):
            note(engine, k, key, ok=True)
            return ["You let them see the Guild's mark, and how little you care for their odds. They think better of it."], True
        return start_fight(engine, enc, "They don't believe a word of it.")
    if key == "run":
        if roll <= run_chance(engine, enc):
            note(engine, k, key, ok=True)
            engine.next_day()
            return ["You're off the road and away before they can close. It costs you some of the day."], True
        return start_fight(engine, enc, "You don't get far. They're on you.")
    if key == "around":
        note(engine, k, key)
        engine.next_day()
        return ["You turn back and find another way round. It takes the better part of a day."], True
    return start_fight(engine, enc, "So be it.")


def _grateful(engine) -> str:
    """Thanks, and now and then a word for the Wayfinder (a traveller's rumour)."""
    rng = engine.rng
    if rng.random() < 0.3:
        from game import keywords
        kw = engine.regions.keywords
        unknown = [w for slot in ("danger", "land", "feature") for w in kw.ordinary(slot) if w not in engine.words]
        if unknown:
            w = rng.choice(unknown)
            keywords.learn(engine, [w])
            shown = next((kw.words[s][w].shown for s in ("danger", "land", "feature") if w in kw.words[s]), w)
            return f"They thank you, and one of them tells you of a place they once heard of: {shown}."
    return "They thank you, and go on their way."


def start_fight(engine, enc, line: str) -> tuple[list[str], bool]:
    """They come at you: on the map, awake, around you."""
    from game.monsters import Monster
    p, gm = engine.player, engine.game_map
    st = state(engine)
    st["fought"] += 1
    note(engine, enc["kind"], "fight")
    spots = [(p.x + dx, p.y + dy) for r in (1, 2, 3) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
             if max(abs(dx), abs(dy)) == r]
    free = [s for s in spots if gm.in_bounds(*s) and gm.is_walkable(*s) and not gm.monster_at(*s)
            and (s[0], s[1]) != (p.x, p.y) and s not in gm.gates]
    for pid in enc["who"]:
        if not free:
            break
        x, y = free.pop(0)
        m = Monster.spawn(people_types()[pid], x, y)
        m.awake = True
        gm.monsters.append(m)
    return [line], True


def on_kill(engine, monster) -> None:
    """Someone on the road is dead (Engine.on_kill): their purse is on the ground. Recorded."""
    from game.items import FloorItem, Item
    st = state(engine)
    st["killed"] += 1
    note(engine, "fight", "killed", who=monster.type.id)
    purse = engine.rng.randint(3, 15) * monster.type.tier
    engine.game_map.items.append(FloorItem(monster.x, monster.y, Item(engine.catalogue["shard"], purse)))
    if not any(m.type.person for m in engine.game_map.monsters if m is not monster):
        engine.log("The road is quiet again.")


def clear(engine) -> None:
    """Leaving the Brisering: anyone still about goes back to the roadside."""
    gm = getattr(engine, "_brisering", None)
    if gm is not None:
        gm.monsters = [m for m in gm.monsters if not m.type.person]
