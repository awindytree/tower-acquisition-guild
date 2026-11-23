"""Light on the Overland: lit or dark, by the Duel and where a place lies (v0.93.0).

The lore (user, 2026-11-23): the Overland has no "day" within a Pulse. The planet's axial tilt is
110 degrees, so through a Duel one pole faces the star and the other is dark; the Light Duel and
the Dark Duel are the Overland's day and night. Myligast stands on the equator; Bytorsskug, 9 km to
its south, is in the southern hemisphere, so the Light Duel lights the south and the Dark Duel the
north. (North of Myligast, the game starts at the beginning of a Dark Duel.) The world is dark:
nearly pitch black in a Dark Duel, and a Light Duel's brightest is about 700 lux.

In the game a place is lit or dark (never "day" or "night"):
- A hunt place's land word says whether it's under the open sky ("sky") or sheltered ("dark":
  caves, thick canopy...). Sheltered places are always dark.
- A feature word may fix the light ("lit" or "dark"): the miasma's distortion (Daybreak, Midnight).
- Otherwise the place is lit when its half of the Overland faces the star: a place lies the way its
  Hunters come out (`journey.edge_for`), north or south of the equator through Myligast.

Old data values still load: "day" -> lit (or sky, on a land word), "torch" and "night" -> dark.
"""
from __future__ import annotations

import math
import weakref
import zlib

LIT, DARK, SKY = "lit", "dark", "sky"
_OLD = {"day": LIT, "torch": DARK, "night": DARK, "unlit": DARK}
_engine = None   # the running game, for the Duel (a weak reference)


def norm(value: str | None, default: str = DARK) -> str:
    """A light value in the current words: lit, dark or sky."""
    if not value:
        return default
    return _OLD.get(value, value)


def watch(engine) -> None:
    """The engine whose calendar decides the Duel (the newest one; there is one per game)."""
    global _engine
    _engine = weakref.ref(engine)


def duel() -> str:
    """'Light Duel' or 'Dark Duel' now (a Light Duel when no game is running)."""
    e = _engine() if _engine else None
    try:
        return e.date.duel if e is not None else "Light Duel"
    except Exception:
        return "Light Duel"


def lit_half(which: str | None = None) -> str:
    """The half of the Overland facing the star: 'south' in a Light Duel, 'north' in a Dark Duel."""
    return "south" if (which or duel()).lower().startswith("light") else "north"


def half_of(bearing: float) -> str:
    """North or south of the equator, for a compass bearing from Myligast (east and west count as south:
    a place due east or west sits on the line; the edge's jitter puts most to one side)."""
    return "north" if math.cos(math.radians(bearing)) > 1e-9 else "south"


def place_bearing(style: str, seed_text: str) -> float:
    """The compass bearing from Myligast a place lies on: its land's direction, jittered by the place."""
    from game import journey
    base = journey.DIRECTIONS.get(style, 180)
    return (base + (zlib.crc32(seed_text.encode()) % (2 * journey.SPREAD + 1)) - journey.SPREAD) % 360


def light_for(land: str, feature: str | None, bearing: float, which: str | None = None) -> str:
    """Lit or dark, from the land word's light, the feature word's, and where the place lies."""
    if feature in (LIT, DARK):
        return feature
    if land == DARK:
        return DARK
    return LIT if half_of(bearing) == lit_half(which) else DARK


def describe(light: str) -> str:
    return "lit" if light == LIT else "dark"
