"""The journey home (user, 2026-11-23; design: claude/design-return-journey.md, stage 2).

**The Wayfinder is one way** (user): it sends a traveller out, but can't bring them back. The trail
home (and a Lost Ground's way back) brings a Hunter out at **the edge of the Brisering**, and they walk
home to Bytorsskug.
- **Where:** on the side that matches the place's land, as the Brisering's own terrain runs
  (`DIRECTIONS`, compass degrees from Myligast), at `EDGE_KM` from Myligast, jittered by the place
  (`SPREAD` degrees), on ground the city can be reached from. About 80-120 km from home: 4-5 Pulses.
- **A contract is complete only once it's reported to the guild clerk in Bytorsskug** (user):
  talking to the clerk with the prize reports it (`report`, from Engine.talk_to): the "Contract
  complete" card, the story's ending, a recovery's pay, the hunt counted. A trip of your own has nothing
  to report.
- **The walk:** travel-to on the Brisering may cross ground you haven't seen (you can see Myligast; you
  know the way). Bleeding and poison keep running out here.
- **Dying on the Brisering** (user): a card of its own; a caravan or travellers find the remains.
"""
from __future__ import annotations

import math
import zlib

EDGE_KM = 92            # how far from Myligast a Hunter comes out (the Brisering's radius is 99 km)
BAND_KM = 6             # ...give or take
SPREAD = 20             # degrees either side of the land's direction, by place
KM_X, KM_Y = 0.5, 1.0   # the travel map's scale (game/brisering: a cell is 0.5 km across, 1 km down)
DIRECTIONS = {          # compass degrees from Myligast: where each kind of land comes out (draft)
    "mountains": 0, "caves": 20, "ruins": 90, "marsh": 135, "forest": 180, "plains": 225, "grassland": 270,
}
COMPASS = ["northern", "north-eastern", "eastern", "south-eastern", "southern", "south-western", "western",
           "north-western"]
_cache: dict = {}


def _centre(gm) -> tuple[float, float]:
    from game.tiles import SYMBOL_TO_INDEX
    import numpy as np
    m = np.argwhere(gm.kinds == SYMBOL_TO_INDEX["M"])
    return float(m[:, 0].mean()), float(m[:, 1].mean())


def km(gm, x: float, y: float, frm=None) -> float:
    cx, cy = frm or _centre(gm)
    return math.hypot((x - cx) * KM_X, (y - cy) * KM_Y)


def bearing(gm, x: float, y: float) -> float:
    cx, cy = _centre(gm)
    return math.degrees(math.atan2((x - cx) * KM_X, -(y - cy) * KM_Y)) % 360


def _edge_cells(engine) -> list:
    """Walkable cells near the edge that Bytorsskug can be reached from (cached per map)."""
    gm = engine.brisering
    if _cache.get("map") is gm:
        return _cache["cells"]
    from collections import deque
    start = [a for a in gm.arrivals.values()]
    seen = set(start)
    q = deque(start)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and gm.in_bounds(*n) and gm.is_walkable(*n) and n not in gm.gates:
                seen.add(n)
                q.append(n)
    centre = _centre(gm)
    cells = [(x, y, bearing(gm, x, y)) for (x, y) in seen
             if abs(km(gm, x, y, centre) - EDGE_KM) <= BAND_KM and (x, y) not in gm.landmarks]
    _cache.update(map=gm, cells=cells)
    return cells


def direction_of(region) -> float:
    return DIRECTIONS.get(getattr(region, "style", ""), 180)


def edge_for(engine, region, seed_text: str) -> tuple[int, int]:
    """Where a Hunter comes out from this place: the land's direction, jittered by the place."""
    want = (direction_of(region) + (zlib.crc32(seed_text.encode()) % (2 * SPREAD + 1)) - SPREAD) % 360
    cells = _edge_cells(engine)
    best = min(cells, key=lambda c: (min(abs(c[2] - want), 360 - abs(c[2] - want)), c[0], c[1]))
    return best[0], best[1]


def where_text(engine, x: int, y: int) -> str:
    """'the northern edge of the Brisering, about 96 km from Bytorsskug'."""
    gm = engine.brisering
    side = COMPASS[int(((bearing(gm, x, y) + 22.5) % 360) // 45)]
    from game.tiles import SYMBOL_TO_INDEX
    import numpy as np
    b = np.argwhere(gm.kinds == SYMBOL_TO_INDEX["B"])
    home = km(gm, x, y, (float(b[:, 0].mean()), float(b[:, 1].mean())))
    return f"the {side} edge of the Brisering, about {round(home)} km from Bytorsskug"


def come_out(engine, region, seed_text: str) -> str:
    """Put the Hunter at the Brisering's edge for this place. Returns where, in words."""
    gm = engine.brisering
    x, y = edge_for(engine, region, seed_text)
    engine.site = None
    engine.change_map(gm, x, y)
    engine._bris_last = (x, y)
    return where_text(engine, x, y)


# ---- Reporting to the clerk --------------------------------------------------------------------------------
def reportable(engine):
    """The Hunter's contract, if they're home in Bytorsskug with what it asked for."""
    p = engine.player
    c = p.contract
    if c is None or c.free or engine.hunt is not None or engine.game_map is not engine.city:
        return None
    if c.job:
        return None
    return c if c.artifact_id and p.inventory.count_of(c.artifact_id) > 0 else None


def report(engine) -> bool:
    """Report the contract to the clerk (Engine.talk_to): the card first, then the story's scenes."""
    c = reportable(engine)
    if c is None:
        return False
    from game import story, rest
    from game.screens import TEXT, DIM
    p = engine.player
    p.contract = None
    p.hunts_done += 1
    queued = len(engine.scene_queue)
    if c.recover:
        from game import recovery
        told = recovery.complete(engine, c)
        heading = "Recovery complete"
    elif c.story:
        told = story.contract_over(engine, c, True)
        heading = engine.story_data.contracts.get(c.story, {}).get("card_heading", "Key hunt complete")
    else:
        t = engine.catalogue[c.artifact_id]
        told = [f"Recovered: {t.name}", "The clerk marks the contract done. What you brought back is yours."]
        heading = "Contract complete"
        engine.log(f"You report the contract to the clerk: {c.title(engine.catalogue)}. It's done.")
    lines = [(t, TEXT) for t in told] + ([("", TEXT)] if told else []) + [(rest.owed_line(engine) + ".", DIM)]
    engine.scene_queue.insert(queued, ("card", heading, lines))   # (before the scenes the story queued)
    return True


# ---- Dying out here ----------------------------------------------------------------------------------------
def death_lines(engine, player) -> tuple[str, list[str]]:
    """The card for a Hunter who falls on the Brisering (user: found by a caravan, brought to the Guild)."""
    gm = engine.game_map
    side = bearing(gm, player.x, player.y)
    finder = ("A Towerway caravan" if 225 <= side <= 315 else "Travellers on the road")
    return "Lost on the Brisering", [
        f"{finder} found the remains of {player.full_name} and brought them home to the Hunters' Guild.",
    ]


def home_now(engine) -> None:
    """(Tests and the balance bot.) Walk home to Bytorsskug from the Brisering at once: travel-to the
    nearest gate, step by step, stopping for nothing but the screens it opens."""
    from game import travel
    for _ in range(20):
        if engine.game_map is engine.city or engine.player.stats.is_dead or not engine.in_brisering():
            return
        dests = [d for d in travel.destinations(engine) if d[0].startswith("Bytorsskug")]
        p = engine.player
        label, spot, beside = min(dests, key=lambda d: abs(d[1][0] - p.x) + abs(d[1][1] - p.y))
        travel.travel(engine, label, spot, beside)
        engine.screen = None


def home_at_once(engine, report_it: bool = True) -> None:
    """(Tests.) Home from the Brisering without walking each step: the Pulses the walk would take
    (25 km a Pulse) pass, and the Hunter is put inside the nearest gate. Then, if they're back with what
    their contract asked for, it's reported (as talking to the clerk does)."""
    if engine.in_brisering():
        gm, p = engine.brisering, engine.player
        gate, (gx, gy) = min(((g, xy) for xy, g in gm.gates.items()),
                             key=lambda t: km(gm, p.x, p.y, t[1]))
        engine.next_day(max(1, round(km(gm, p.x, p.y, (gx, gy)) / 25)))
        engine.change_map(engine.city, *engine.city_inside(gate))
    if report_it and reportable(engine) is not None:
        report(engine)
        from game import story
        engine.screen = None
        while engine.scene_queue:             # (the card and any scenes: shown, then dismissed)
            story.show_next_scene(engine)
            if engine.screen is None:
                break
            engine.screen = None
