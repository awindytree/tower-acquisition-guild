"""Maps in the Guild archive (roadmap step 4, v0.84.0; user).

The same words always give the same place, so the Guild can keep maps. A Hunter who scouts a place
deeply enough (every area entered, and at least half of it explored all told: user) and reports it with
their field notes files a scouting report; the Guild's cartographer turns reports into proper maps, which
Hunters buy from him at his window once the Cartographer's Study is built (a Guild works project, user).
Reports and filed maps are world state (they survive death, like the words); a bought map is the
Hunter's (lost with them, like their skills). A map shows the whole place: every area starts revealed.

Price (user): "around 100 shards", a 2–3 on a 1–5 scale of what you'd expect: BASE + PER_DANGER × danger
(75 at danger 1, 135 at danger 5), less with Bargaining.
"""
from __future__ import annotations

SCOUTED_SHARE = 0.5      # how much of the place explored, all areas together (user)
BASE, PER_DANGER = 60, 15
REPORT_FEE = 10          # what the clerk pays for a scouting report, times the danger (draft)


def explored_share(hunt) -> float:
    """How much of the walkable ground of this hunt's place has been explored, all areas together
    (areas not yet entered count as unexplored)."""
    seen = total = 0
    for gm in hunt.areas:
        if gm is None:
            continue
        walk = gm.walkable
        total += int(walk.sum())
        seen += int((gm.explored & walk).sum())
    if any(a is None for a in hunt.areas):
        return 0.0
    return seen / total if total else 0.0


def scouted(hunt) -> bool:
    """Every area entered, and at least half the place explored (user)."""
    return all(a is not None for a in hunt.areas) and explored_share(hunt) >= SCOUTED_SHARE


def note(engine) -> None:
    """At the end of a hunt: a note for the archive if the place was scouted deeply enough."""
    hunt = engine.hunt
    if hunt is None or not scouted(hunt):
        return
    place = hunt.contract.region.id
    mapped = engine.player.notes.setdefault("mapped", [])
    if place not in mapped and place not in filed(engine):
        mapped.append(place)
        engine.log("You've seen enough of this place to report it for the Guild's maps.")


def filed(engine) -> dict:
    """{place id: {"day", "by"}}: places the Guild has a scouting report of (world state)."""
    return engine.archive.setdefault("maps", {})


def report(engine) -> tuple[int, int]:
    """File the Hunter's scouting reports (with their field notes). Returns (new maps, pay)."""
    p = engine.player
    new, pay = 0, 0
    for place in p.notes.get("mapped", []):
        if place in engine.regions and place not in filed(engine):
            filed(engine)[place] = {"day": engine.day, "by": p.full_name}
            new += 1
            pay += REPORT_FEE * engine.regions[place].danger[0]
    return new, pay


def price(engine, place: str) -> int:
    from game import bargaining
    return bargaining.pay(engine.player, BASE + PER_DANGER * engine.regions[place].danger[0])


def for_sale(engine) -> list[str]:
    """Filed places, the gentlest first."""
    return sorted((pl for pl in filed(engine) if pl in engine.regions),
                  key=lambda pl: (engine.regions[pl].danger[0], pl))


def buy(engine, place: str) -> tuple[bool, str]:
    p = engine.player
    if place in p.maps:
        return False, "You already have that map."
    cost = price(engine, place)
    if p.shards < cost:
        return False, f"That one's {cost} shards."
    p.shards -= cost
    p.maps.add(place)
    from game import keywords, sound
    keywords.learn(engine, keywords.split(place))      # (a map names its words)
    sound.play("pay")
    return True, f"You buy the map of {engine.regions[place].name} for {cost} shards."


def reveal(engine, game_map) -> None:
    """On a hunt at a place you have the map of: the area starts revealed."""
    hunt = engine.hunt
    if hunt is not None and hunt.contract.region.id in engine.player.maps and game_map.fog:
        game_map.explored[...] = True
