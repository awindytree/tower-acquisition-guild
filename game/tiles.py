"""Tile definitions.

Every kind of terrain is one TileType. The map stores a small integer per cell
(an index into TILE_TYPES), plus a "variant" number so grass, floors and water
don't all look identical.

To add terrain: add a TileType below, then use its symbol in a map file.
Glyphs can be any character in the font's CP437 set: letters, symbols like
♣ ≈ ∙ ° ▲, and the box-drawing and block characters.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

Color = tuple[int, int, int]

# The layout tcod's console uses for each cell: character, foreground, background.
graphic_dt = np.dtype([("ch", np.int32), ("fg", "3B"), ("bg", "3B")])

GROUND = (12, 10, 9)
VOID = (8, 7, 6)  # empty screen and solid rock


@dataclass(frozen=True)
class TileType:
    name: str                  # used in messages: "The stone wall blocks your way."
    symbol: str                # character used in map text files
    walkable: bool
    transparent: bool          # can you see through it? (used later for field of view)
    glyphs: str                # picked at random per cell; repeat one to make it more common
    colors: tuple[Color, ...]  # also picked at random per cell
    bg: Color = GROUND
    hide_when_buried: bool = False  # walls deep inside rock are left blank
    # Draw with line pieces that join up with neighbouring walls of the same
    # type (═ ║ ╔ ╗ ╚ ╝ ╠ ╣ ╦ ╩ ╬); glyphs is ignored. For built walls.
    joined: bool = False
    # Joined walls also join toward these map symbols (v0.100.2, user: a door, window or the city wall
    # beside a corner keeps it a corner, not a straight piece).
    joins: str = ""
    # Glyphs with a colour of their own, whatever colors says (e.g. white glints on water).
    glyph_colors: tuple = ()   # ((glyph, color), ...)


TILE_TYPES: list[TileType] = [
    # Built walls: the city wall, the guild hall, ruins. Dark shade (user, v0.100.2; solid blocks from
    # v0.42.0, joined lines before that).
    TileType("stone wall", "#", walkable=False, transparent=False,
             glyphs="▓", colors=((150, 136, 120),), bg=(30, 26, 23),
             hide_when_buried=True),
    # Houses: double lines joined to their neighbours (user, v0.100.2; solid blocks from v0.42.0).
    TileType("house", "h", walkable=False, transparent=False,
             glyphs="█", colors=((168, 138, 104),), bg=(30, 24, 19),
             hide_when_buried=True, joined=True, joins="+WL#"),
    # Natural rock: caves and dungeons. Drawn as rough stone.
    TileType("rough stone", "%", walkable=False, transparent=False,
             glyphs="▒", colors=((94, 85, 76), (86, 78, 70)), bg=(34, 30, 27),
             hide_when_buried=True),
    TileType("flagstone", ".", walkable=True, transparent=True,
             glyphs="." * 11 + ",", colors=((104, 93, 82), (94, 84, 74))),
    TileType("doorway", "+", walkable=True, transparent=True,
             glyphs="◘", colors=((200, 140, 70),)),
    TileType("grass", ",", walkable=True, transparent=True,
             glyphs="\"',.`" + " " * 2, colors=((84, 120, 54), (98, 138, 62), (72, 104, 48)),
             bg=(14, 18, 11)),
    # Grassland and marsh (v0.70.0): tall grass and reeds you can walk through but not see through.
    TileType("tall grass", "g", walkable=True, transparent=False,
             glyphs="ⁿⁿ\"", colors=((150, 170, 80), (130, 156, 70), (168, 180, 96)), bg=(18, 22, 10)),
    TileType("mud", "e", walkable=True, transparent=True,
             glyphs=".,∙. ", colors=((104, 96, 62), (92, 84, 56)), bg=(16, 15, 10)),
    TileType("reeds", "r", walkable=True, transparent=False,
             glyphs="ƒ⌠ƒ", colors=((150, 146, 84), (126, 132, 72)), bg=(16, 17, 10)),
    TileType("tree", "T", walkable=False, transparent=False,
             glyphs="♣♠", colors=((70, 128, 60), (58, 110, 52)), bg=(14, 18, 11),
             hide_when_buried=True),
    TileType("water", "~", walkable=False, transparent=True,
             glyphs="≈~" * 5 + ".'", colors=((86, 140, 190), (70, 120, 172)), bg=(14, 26, 40),
             glyph_colors=((".", (235, 240, 245)), ("'", (235, 240, 245)))),   # glints: always white
    # ---- Hunts: ways between areas, and the way back to the city ----
    TileType("way deeper", ">", walkable=True, transparent=True,
             glyphs="»", colors=((240, 150, 70),)),
    TileType("way back", "<", walkable=True, transparent=True,
             glyphs="«", colors=((240, 150, 70),)),
    TileType("trail home", "H", walkable=True, transparent=True,
             glyphs="≡", colors=((250, 215, 120),)),
    TileType("city gate", "G", walkable=True, transparent=True,
             glyphs="∩", colors=((240, 160, 80),), bg=(40, 30, 20)),
    TileType("cave floor", "c", walkable=True, transparent=True,
             glyphs="." * 8 + "∙,", colors=((90, 82, 74), (82, 75, 68)), bg=(14, 12, 11)),
    TileType("cobblestones", ":", walkable=True, transparent=True,
             glyphs="∙∙∙·", colors=((112, 104, 96), (100, 93, 86)), bg=(24, 22, 20)),
    TileType("bridge", "=", walkable=True, transparent=True,
             glyphs="═", colors=((150, 112, 72),), bg=(34, 24, 16)),
    TileType("bridge", "I", walkable=True, transparent=True,       # running north-south
             glyphs="║", colors=((150, 112, 72),), bg=(34, 24, 16)),
    TileType("shop floor", "m", walkable=True, transparent=True,
             glyphs="." * 5 + "_", colors=((150, 112, 70), (138, 102, 64)), bg=(34, 24, 15)),
    TileType("notice board", "N", walkable=False, transparent=True,
             glyphs="¶", colors=((225, 205, 160),), bg=(30, 24, 16)),
    TileType("guild stash", "C", walkable=False, transparent=True,
             glyphs="$", colors=((170, 120, 70),), bg=(24, 17, 11)),
    TileType("workshop floor", "k", walkable=True, transparent=True,
             glyphs="." * 4 + "∙", colors=((140, 128, 112), (124, 114, 100)), bg=(26, 24, 22)),
    TileType("bookshelves", "b", walkable=False, transparent=False,
             glyphs="╫", colors=((170, 120, 80), (150, 104, 70)), bg=(36, 24, 16)),
    TileType("wooden floor", "w", walkable=True, transparent=True,
             glyphs="." * 6 + "_", colors=((120, 88, 58), (108, 80, 52)), bg=(24, 17, 11)),
    TileType("well", "O", walkable=False, transparent=True,
             glyphs="○", colors=((130, 170, 210),), bg=(24, 22, 20)),
    # The Wayfinder (v0.44.0): walk into it to choose three words and be carried out
    # onto the Overland. PLACEHOLDER name and look.
    TileType("Wayfinder", "Y", walkable=False, transparent=False,
             glyphs="▓", colors=((150, 220, 210), (130, 200, 196)), bg=(20, 40, 44)),
    # The Guild's two boards (v0.44.0), in the guild hall: contracts, and bounties and scouting.
    TileType("contracts board", "P", walkable=False, transparent=True,
             glyphs="¶", colors=((240, 200, 120),), bg=(30, 24, 16)),
    TileType("bounties board", "J", walkable=False, transparent=True,
             glyphs="¶", colors=((200, 220, 160),), bg=(30, 24, 16)),
    # A service window (v0.54.0): set in a wall; walk into it to talk to whoever's behind it
    # (";window=x,y folk_id" in the map file). The guild clerk's, for now.
    TileType("service window", "W", walkable=False, transparent=True,
             glyphs="▬", colors=((205, 220, 230),), bg=(52, 58, 64)),
    # The Guild's works (v0.60.0): what each improvement adds to the hall.
    TileType("plaque", "L", walkable=False, transparent=False,
             glyphs="■", colors=((214, 176, 96),), bg=(52, 44, 30)),
    # Monuments (v0.68.0): statues and the like, with their stories (data/monuments.json;
    # ";monument=x,y id" in the map file). Walk into one to read it.
    TileType("statue", "S", walkable=False, transparent=True,
             glyphs="♀", colors=((176, 150, 104),), bg=(40, 36, 30)),
    # A Hunter's home (v0.74.0): furniture appears as it's bought. Walk into it to use it.
    TileType("bed", "n", walkable=False, transparent=True,
             glyphs="╥", colors=((206, 150, 110),)),
    TileType("chest", "q", walkable=False, transparent=True,
             glyphs="$", colors=((200, 160, 90),), bg=(34, 26, 16)),
    TileType("trophy shelves", "j", walkable=False, transparent=True,
             glyphs="Ω", colors=((200, 178, 140),)),
    TileType("fish tank", "a", walkable=False, transparent=True,                  # (v0.99.0)
             glyphs="≈", colors=((110, 170, 210),), bg=(20, 40, 60)),
    TileType("forge", "F", walkable=False, transparent=True,                     # (v0.76.0)
             glyphs="▲", colors=((235, 120, 60),), bg=(44, 26, 18)),
    TileType("workbench", "d", walkable=False, transparent=True,
             glyphs="╦", colors=((190, 150, 100),)),
    TileType("training dummy", "U", walkable=False, transparent=True,
             glyphs="τ", colors=((190, 160, 110),)),
    TileType("cot", "Z", walkable=False, transparent=True,
             glyphs="╥", colors=((200, 196, 180),)),
    TileType("bunk", "K", walkable=False, transparent=True,
             glyphs="╤", colors=((176, 140, 100),)),
    TileType("weapon rack", "E", walkable=False, transparent=True,
             glyphs="╪", colors=((176, 184, 196),)),
    # The trophy wall (v0.61.0), in the trophymaster's lodge: the records, mounted.
    # Walk into it to read them. PLACEHOLDER look.
    TileType("trophy wall", "D", walkable=False, transparent=False,
             glyphs="Ω", colors=((222, 200, 160),), bg=(60, 40, 26)),
    # ---- The Brisering travel map (v0.46.0; tools/brisering/build_brisering.py) ----
    TileType("the miasma", "X", walkable=False, transparent=True,
             glyphs="░▒░░", colors=((96, 76, 116), (84, 66, 102)), bg=(22, 16, 28)),
    TileType("Myligast", "M", walkable=False, transparent=False,
             glyphs="█", colors=((226, 226, 236),), bg=(60, 60, 70)),
    TileType("Bytorsskug", "B", walkable=False, transparent=False,
             glyphs="▓", colors=((190, 160, 120),), bg=(40, 32, 24)),
    TileType("mountains", "A", walkable=False, transparent=False,
             glyphs="▲▲▲^", colors=((156, 146, 136), (138, 128, 118)), bg=(34, 30, 27)),
    TileType("hills", "^", walkable=True, transparent=True,
             glyphs="^", colors=((150, 132, 98), (132, 116, 86)), bg=(22, 20, 14)),
    TileType("woods", "f", walkable=True, transparent=True,
             glyphs="♣♠♣", colors=((70, 128, 60), (58, 110, 52), (80, 140, 66)), bg=(14, 20, 11)),
    TileType("ruins", "u", walkable=True, transparent=True,
             glyphs="π..∙", colors=((150, 146, 138), (128, 124, 118)), bg=(24, 22, 20)),
    TileType("village", "V", walkable=False, transparent=False,
             glyphs="⌂", colors=((226, 196, 150),), bg=(40, 32, 24)),
    TileType("boga circuit", "Q", walkable=True, transparent=True,
             glyphs="∙", colors=((250, 236, 200),), bg=(120, 86, 48)),
    TileType("road", "R", walkable=True, transparent=True,
             glyphs="∙∙·", colors=((176, 140, 92), (160, 126, 82)), bg=(30, 24, 16)),
    TileType("dirt path", "-", walkable=True, transparent=True,
             glyphs="." * 3 + "∙,", colors=((120, 98, 70), (108, 88, 62)), bg=(20, 17, 12)),
]

SYMBOL_TO_INDEX: dict[str, int] = {t.symbol: i for i, t in enumerate(TILE_TYPES)}

# Anything off the edge of the map counts as wall.
WALL_INDEX = SYMBOL_TO_INDEX["#"]
