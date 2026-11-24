"""Fishing collections (v0.99.0): stage 5 of claude/design-fishing.md. All the assistant's drafts.

- **The Angler's Log** (`p`): the Hunter's own, like field notes (it dies with them). A fish is
  *hooked* once you've had one on the line, *caught* once you've landed one, and *known* after five:
  only then does the log show where and how it bites. Best weight, how many, quirks seen.
- **The record book** (world state `engine.angling["records"]` {fish: {kg, who, day}}): the tackleman
  weighs your catch for the Watermen and Anglers' Guild; a new heaviest pays by tier.
- **Sets** (`data/fish.json` `sets`): land every kind of fish in a kind of water and the tackleman's
  Guild sends a reward, once per Hunter.
- **Named fish** (world state `engine.angling["named"]`): every lake, the city river and the
  Brisering's river hold one fish the anglers know by name ("Old Setly"): one of the biggest kinds
  that lives there, about twice the size, harder to hook and hold. Caught once, ever.
"""
from __future__ import annotations

import random
import zlib

from game import fishing

LEVELS = ("", "hooked", "caught", "known")
KNOWN_AFTER = 5
NAMED_BITE = 0.004          # a turn, when the named fish could be there and takes the bait
NAMED_KG = (2.0, 2.8)       # times its kind's usual weight
NAMED_STRENGTH = 1.4
NAMED_STAMINA = 2.0
RECORD_PAY = {1: 6, 2: 12, 3: 25, 4: 50, 5: 100}


# ---- The log ---------------------------------------------------------------------------------------------
def log(player) -> dict:
    return player.__dict__.setdefault("fishlog", {})


def hooked(player, fid: str) -> None:
    log(player).setdefault(fid, {"n": 0, "best": 0.0, "quirks": []})


def landed(engine, s, item) -> list[str]:
    """Note a landed fish in the log. Returns any lines to tell (new kind, known, a set done)."""
    p = engine.player
    entry = log(p).setdefault(s.fish, {"n": 0, "best": 0.0, "quirks": []})
    out = []
    first = entry["n"] == 0
    entry["n"] += 1
    entry["best"] = max(entry["best"], item.catch["kg"])
    q = item.catch.get("quirk")
    if q and q not in entry["quirks"]:
        entry["quirks"].append(q)
    name = fishing.species()[s.fish]["name"]
    if first:
        out.append(f"A new kind for your Angler's Log: the {name}.")
    if entry["n"] == KNOWN_AFTER:
        out.append(f"You know the {name}'s ways now: your log has where and how it bites.")
    out += check_sets(engine)
    return out


def level(player, fid: str) -> int:
    e = log(player).get(fid)
    if e is None:
        return 0
    return 3 if e["n"] >= KNOWN_AFTER else 2 if e["n"] else 1


def sets() -> dict:
    return fishing.data().get("sets", {})


def members(kind: str) -> list[str]:
    return sorted(fid for fid, f in fishing.species().items() if kind in f["waters"])


def check_sets(engine) -> list[str]:
    """A set's reward, the first time this Hunter has landed every kind in it."""
    from game.items import Item
    p = engine.player
    out = []
    for kind, st in sets().items():
        flag = f"fishset:{kind}"
        if flag in p.flags or any(log(p).get(f, {}).get("n", 0) == 0 for f in members(kind)):
            continue
        p.flags.add(flag)
        p.guild_pay(st.get("shards", 0), "fishing")
        gift = st.get("gift")
        text = f"Every kind of fish in {st['name']}! The Watermen and Anglers send {st.get('shards', 0)} shards"
        if gift:
            item = Item(engine.catalogue[gift])
            fishing._give(engine, item)
            text += f" and {fishing._a(item.type.name)}"
        out.append(text + ".")
    return out


# ---- Named fish ------------------------------------------------------------------------------------------
def named_state(engine) -> dict:
    return engine.angling.setdefault("named", {})


def named_for(engine, key: str, kind: str, side: str) -> dict | None:
    """The named fish of a persistent water (lakes, the city river, the Brisering's river), or None:
    {fid, name}. Worked out from the water's key, so it's always the same one."""
    if not (key in ("city", "river") or key.startswith("lake:")):
        return None
    ctx = {"side": side, "key": key, "pulse": "", "holiday": False}
    kinds = [fid for fid, f in fishing.species().items() if kind in f["waters"] and f["tier"] >= 2
             and not f.get("pulses") and not f.get("holiday") and fishing.present(fid, ctx)]
    if not kinds:
        return None
    r = random.Random(zlib.crc32(f"named/{key}".encode()))
    top = max(fishing.species()[f]["tier"] for f in kinds)
    pool = sorted(f for f in kinds if fishing.species()[f]["tier"] >= top - 1)
    fid = r.choice(pool)
    from game import named
    pattern = r.choice(fishing.data()["named_patterns"])
    return {"fid": fid, "name": pattern.format(n=named.maker().given_name(r))}


def named_caught(engine, key: str) -> dict | None:
    return named_state(engine).get(key)


def named_bite(engine, s, rng) -> str | None:
    """Does the water's named fish take the bait this turn? Its fish id, or None."""
    if s.miasma:
        return None
    nf = named_for(engine, s.key, s.kind, s.side)
    if nf is None or named_caught(engine, s.key):
        return None
    f = fishing.species()[nf["fid"]]
    if s.band not in f["depth"] or (f["light"] != "any" and f["light"] != s.light):
        return None
    like = f["baits"].get(s.bait_key, 0)
    if like <= 0 or rng.random() >= NAMED_BITE * like:
        return None
    return nf["fid"]


def make_named(engine, s, rng) -> None:
    """The named fish is on the line: bigger, stronger, slower to tire."""
    nf = named_for(engine, s.key, s.kind, s.side)
    s.named = nf["name"]
    f = fishing.species()[s.fish]
    s.kg = round(f["kg"][0] * rng.uniform(*NAMED_KG), 2)
    s.quirk = "old"
    s.strength *= NAMED_STRENGTH
    s.max_stamina = s.stamina = s.max_stamina * NAMED_STAMINA


def named_landed(engine, s, item) -> str:
    item.catch["named"] = s.named
    named_state(engine)[s.key] = {"fid": s.fish, "name": s.named, "who": engine.player.full_name,
                                  "day": engine.day, "kg": s.kg}
    return f"That's {s.named}! The anglers will talk about this one for a long time."


def rumour(engine, rng) -> str | None:
    """The tackleman on a named fish still out there."""
    w = fishing.waters(engine.brisering, "brisering") if hasattr(engine, "brisering") else None
    keys = [("city", "city_river", "south", "the city river"), ("river", "river", "south", "the Brisering's river")]
    if w is not None:
        keys += [(w.keys[b], "lake", w.sides[b], w.names[b]) for b, k in enumerate(w.kinds) if k == "lake"]
    rng.shuffle(keys)
    for key, kind, side, where in keys:
        nf = named_for(engine, key, kind, side)
        if nf and not named_caught(engine, key):
            fname = fishing.species()[nf["fid"]]["name"]
            return (f"They say there's one in {where} they call {nf['name']}: a {fname}, near enough "
                    "twice the size of any other. Plenty have hooked it. Nobody's landed it.")
    return None


# ---- The record book -------------------------------------------------------------------------------------
def records(engine) -> dict:
    return engine.angling.setdefault("records", {})


def weigh(engine) -> list[str]:
    """The tackleman weighs every fish in your pack for the record book. Lines to tell."""
    p = engine.player
    out = []
    recs = records(engine)
    for it in p.inventory.items:
        if it.catch is None:
            continue
        fid = it.type.properties.get("fish", "")
        rec = recs.get(fid)
        kg = it.catch["kg"]
        if rec is None or kg > rec["kg"]:
            recs[fid] = {"kg": kg, "who": p.full_name, "day": engine.day}
            pay = RECORD_PAY.get(fishing.species()[fid]["tier"], 6)
            p.earn(pay, "fishing")
            beat = f", beating {rec['who']}'s {fishing.weight_text(rec['kg'])}" if rec else ""
            out.append(f"A record {fishing.species()[fid]['name']}: {fishing.weight_text(kg)}{beat}. ({pay} shards)")
    if not out:
        out.append("Nothing in your pack beats the book.")
    return out


def book_lines(engine) -> list[str]:
    recs = records(engine)
    lines = ["The Watermen and Anglers' Guild's record book: the heaviest of each kind weighed here.", ""]
    for fid, f in sorted(fishing.species().items(), key=lambda kv: (kv[1]["tier"], kv[1]["name"])):
        r = recs.get(fid)
        if r:
            lines.append(f"{f['name'].capitalize()}: {fishing.weight_text(r['kg'])}, {r['who']}")
    if len(lines) == 2:
        lines.append("No one's weighed in yet.")
    caught = named_state(engine)
    if caught:
        lines += ["", "The named, landed:"]
        for key, n in caught.items():
            lines.append(f"{n['name']} ({fishing.species()[n['fid']]['name']}, {fishing.weight_text(n['kg'])}), by {n['who']}")
    return lines


# ---- The log window ----------------------------------------------------------------------------------------
GROUPS = (("city_river", "The city river"), ("river", "The Brisering's river"), ("lake", "The lakes"),
          ("pond", "The ponds"), ("marsh", "Miasma: marsh water"), ("cave_pool", "Miasma: cave pools"),
          ("miasma_pond", "Miasma: pools"))


def log_lines(player) -> list[tuple[str, int]]:
    """(text, level) lines for the Angler's Log; level -1 for headings."""
    S = fishing.species()
    out = []
    total = sum(1 for f in S if level(player, f) >= 2)
    out.append((f"Kinds caught: {total} of {len(S)}.", -1))
    for kind, title in GROUPS:
        kinds = members(kind)
        got = sum(1 for f in kinds if level(player, f) >= 2)
        st = sets().get(kind)
        mark = " (set done)" if f"fishset:{kind}" in player.flags else ""
        out.append(("", -2))
        out.append((f"{title}: {got} of {len(kinds)}{mark}", -1))
        for fid in sorted(kinds, key=lambda f: (S[f]["tier"], S[f]["name"])):
            lv = level(player, fid)
            f = S[fid]
            if lv == 0:
                out.append((f"  ?  (tier {f['tier']})", 0))
                continue
            e = log(player)[fid]
            text = f"  {f['name']}  T{f['tier']}"
            if lv >= 2:
                text += f"  x{e['n']}, best {fishing.weight_text(e['best'])}"
                if e["quirks"]:
                    text += f", {', '.join(e['quirks'])}"
            else:
                text += "  (hooked, not landed)"
            out.append((text, lv))
            if lv >= 3:
                bait = ", ".join(b for b, v in sorted(f["baits"].items(), key=lambda kv: -kv[1]))
                when = (" Only in the holidays." if f.get("holiday") else
                        f" Only on {', '.join(f['pulses'])}." if f.get("pulses") else "")
                where = f" {', '.join(f['where'])} of the tower;" if f.get("where") else ""
                out.append((f"     {'/'.join(f['depth'])} water,{where} {f['light'] if f['light'] != 'any' else 'lit or dark'};"
                            f" takes {bait}.{when}", 3))
    return out
