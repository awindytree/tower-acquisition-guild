"""Anything that occupies a cell: the player now, monsters and items later."""
from __future__ import annotations

from dataclasses import dataclass

from game.tiles import Color


@dataclass
class Entity:
    x: int
    y: int
    char: str
    color: Color
    name: str

    def move(self, dx: int, dy: int) -> None:
        self.x += dx
        self.y += dy


@dataclass
class NPC(Entity):
    """A person of the city (data/townsfolk.json). Walk into them to talk. Never fights."""
    folk_id: str = ""
    home: tuple[int, int] = (0, 0)   # where they were placed
    wander: int = 0                  # how far from home they stray (0 = stays put)
