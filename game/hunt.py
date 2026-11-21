"""Hunts: contracts from the gate boards, and the chain of areas you explore.

A Region is what lies beyond one city gate (data/regions.json).
A Contract is one job on that gate's board: which artifact, how dangerous,
how deep. A Hunt is a contract in progress: a chain of generated areas.
Areas are generated the first time you enter them, then kept, so walking
back through one finds it as you left it.
"""
from __future__ import annotations

import json
import random
import zlib
from dataclasses import dataclass
from pathlib import Path

from game import procgen
from game.game_map import GameMap
from game.items import Catalogue
from game.monsters import MonsterType, choose_spawns


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    gate: str
    style: str
    light: str
    danger: tuple[int, int]
    area_size: tuple[int, int]
    artifacts: tuple[str, ...]
    # Places made from the Wayfinder's keywords (game/keywords.py, v0.44.0):
    place: tuple[str, ...] = ()   # (danger word, land word, feature word)
    depth: int = 0                # number of areas (0: from the danger)
    creatures: float = 1.0        # multiplier on how many creatures
    favour: str = ""              # a creature that turns up far more often
    rarity_up: int = 0            # finds rolled as if the danger were this much higher
    writings: float = 1.0         # multiplier on the chance of a writing


def load_regions(path: str | Path):
    """The places the Wayfinder's words lead to (v0.44.0: the gate regions are gone).
    Kept under this name for older callers; see game/keywords.py."""
    from game.keywords import load_places
    return load_places(path)


# How likely each rarity is, by contract danger (1-5). Higher danger, rarer finds.
RARITY_WEIGHTS = {
    1: {"common": 80, "uncommon": 20},
    2: {"common": 55, "uncommon": 35, "rare": 10},
    3: {"common": 30, "uncommon": 40, "rare": 25, "very_rare": 5},
    4: {"common": 15, "uncommon": 30, "rare": 35, "very_rare": 15, "legendary": 5},
    5: {"common": 5, "uncommon": 20, "rare": 35, "very_rare": 25, "legendary": 12, "unique": 3},
}


def pick_artifact(region: "Region", danger: int, catalogue: Catalogue, rng: random.Random) -> str:
    """A broken artifact for a contract: rarity by danger, then any artifact of
    that rarity (limited to the region's list, if it has one)."""
    pool = [t for t in catalogue.artifacts() if not region.artifacts or t.id in region.artifacts]
    by_rarity: dict[str, list[str]] = {}
    for t in sorted(pool, key=lambda t: t.id):
        by_rarity.setdefault(t.rarity.id, []).append(t.id)
    danger = max(1, min(5, danger + getattr(region, "rarity_up", 0)))
    weights = {r: w for r, w in RARITY_WEIGHTS[danger].items() if r in by_rarity}
    if not weights:  # the region has nothing at these rarities: take any of its artifacts
        return rng.choice(sorted(t.id for t in pool))
    rarity = rng.choices(list(weights), weights=list(weights.values()))[0]
    return rng.choice(by_rarity[rarity])


@dataclass(frozen=True)
class Contract:
    region: Region
    artifact_id: str
    danger: int     # 1-5
    depth: int      # number of areas
    seed: int
    job: str = ""   # an odd-job outing: no artifact (artifact_id ""), just the job's description
    story: str = ""        # a story contract (data/story "contracts"): its id
    story_title: str = ""  # ...and its title on the board
    guardian: str = ""     # a creature waiting by the prize (story contracts)
    min_rank: int = 0      # the Guild rank a story contract is posted for (index into data/ranks.json)
    free: bool = False     # no contract: a trip of your own through the Wayfinder (v0.44.0)

    def title(self, catalogue: Catalogue) -> str:
        if self.story_title:
            return self.story_title
        if self.job:
            return f"Odd job: {self.job}"
        if self.free:
            return f"A trip to {self.region.name}"
        t = catalogue[self.artifact_id]
        rarity = f" ({t.rarity.name})" if t.rarity else ""
        return f"Recover the {t.name}{rarity}"


def danger_pips(danger: int) -> str:
    return "■" * danger + "∙" * (5 - danger)


def depth_of(region: Region, danger: int) -> int:
    return region.depth or min(5, 2 + danger)


def make_contracts(region: Region, day: int, catalogue: Catalogue, count: int = 3) -> list[Contract]:
    """Contracts for one place on a given day (same day and place, same contracts).
    (The Guild's board, game/postings.py, posts across many places.)"""
    rng = random.Random(zlib.crc32(f"{region.id}/{day}".encode()))
    contracts = []
    for _ in range(count):
        danger = rng.randint(*region.danger)
        depth = depth_of(region, danger)
        artifact = pick_artifact(region, danger, catalogue, rng)
        for _ in range(6):  # try not to post the same artifact twice on one board
            if all(c.artifact_id != artifact for c in contracts):
                break
            artifact = pick_artifact(region, danger, catalogue, rng)
        # No reward: the Guild doesn't pay Hunters for hunts (it collects dues).
        contracts.append(Contract(region, artifact, danger, depth, rng.getrandbits(32)))
    return contracts


def trip(region: Region, catalogue: Catalogue, rng: random.Random) -> Contract:
    """A trip of your own to a place: no contract, but every place has a find at its far end,
    rolled each trip (my call, v0.44.0)."""
    danger = region.danger[0]
    return Contract(region, pick_artifact(region, danger, catalogue, rng), danger, depth_of(region, danger),
                    rng.getrandbits(32), free=True)


class Hunt:
    def __init__(self, contract: Contract, monster_types: dict[str, MonsterType] | None = None) -> None:
        self.contract = contract
        self.monster_types = monster_types or {}
        self.faints_used = 0
        self.areas: list[GameMap | None] = [None] * contract.depth
        self.entries: list[tuple[int, int]] = [(0, 0)] * contract.depth
        self.far_ends: list[tuple[int, int]] = [(0, 0)] * contract.depth
        self.current = 0
        # How many of the target artifact you already carried when you set out,
        # so one from an earlier hunt doesn't count for this one.
        self.carried_at_start = 0
        self.writings: list = [None] * contract.depth  # the writing (if any) lying in each area (game/library.py)
        self.story_items: list = []   # [[item, area index], ...]: story items hidden here (game/story.py)
        self.race: dict | None = None  # a rival after the same prize (game/rivals.py)
        self.bounties: list = []       # [[job id, "kill"/"find", creature/artifact id], ...] (game/work.py)

    def area(self, index: int, catalogue: Catalogue) -> GameMap:
        """The map for area `index`, generated on first visit."""
        if self.areas[index] is None:
            self.areas[index] = self._generate(index, catalogue)
        return self.areas[index]

    def _generate(self, index: int, catalogue: Catalogue) -> GameMap:
        c, region = self.contract, self.contract.region
        seed = zlib.crc32(f"{c.seed}/{index}".encode())
        # Same words, same place (user): a keyword place's layout comes from its words;
        # what's in it (creatures, loose finds) from this trip's seed.
        layout = zlib.crc32(f"place:{region.id}/{index}".encode()) if region.place else seed
        w, h = region.area_size
        plan = procgen.generate(region.style, layout, w, h)
        rng = random.Random(seed + 1)
        procgen.scatter_loot(plan, rng, c.danger)

        last = index == c.depth - 1
        rows = [list(r) for r in plan.rows]
        if last and any(kind == "kill" and want in self.monster_types and self.monster_types[want].swims
                        for _, kind, want in self.bounties) and not any("~" in r for r in rows):
            # a marked swimmer needs water: a small pool at a dead end, for this trip (v0.49.1)
            near = {plan.entry, plan.far_end} | {p for p, d in procgen._distances(plan.rows, plan.entry).items() if d <= 6}
            procgen.dead_end_pool(rows, near, random.Random(seed + 7))
            plan.rows = ["".join(r) for r in rows]
        ex, ey = plan.entry
        rows[ey][ex] = "H" if index == 0 else "<"          # the way you came in
        fx, fy = plan.far_end
        if last:
            if c.artifact_id:
                plan.items.append((fx, fy, c.artifact_id, 1))   # the prize, at the far end
        else:
            rows[fy][fx] = ">"                              # the way on

        game_map, _ = GameMap.from_rows(["".join(r) for r in rows],
                                        name=f"{region.id}_{index + 1}", light=region.light)
        game_map.title = f"Area {index + 1} of {c.depth}"
        game_map.fog = True
        game_map.item_spawns = plan.items
        game_map.place_items(catalogue)

        # Creatures: anywhere open, but not close to where you come in.
        dist = procgen._distances(plan.rows, plan.entry)
        spots = [p for p, d in dist.items() if d > 10 and p != plan.far_end]
        water = [(x, y) for y, row in enumerate(plan.rows) for x, ch in enumerate(row) if ch == "~"
                 and any(dist.get((x + dx, y + dy), 0) > 6 for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)))]
        game_map.monsters = choose_spawns(self.monster_types, region.style, c.danger, index, spots, rng,
                                          more=region.creatures, favour=region.favour, light=region.light,
                                          water=water)
        if last and c.guardian and c.guardian in self.monster_types:   # a story contract's guardian, by the prize
            near = sorted((p for p, d in dist.items() if p != plan.far_end
                           and 1 <= max(abs(p[0] - fx), abs(p[1] - fy)) <= 3), key=lambda p: (p[1], p[0]))
            if near:
                from game.monsters import Monster
                gx, gy = rng.choice(near)
                game_map.monsters = [m for m in game_map.monsters if (m.x, m.y) != (gx, gy)]
                game_map.monsters.append(Monster.spawn(self.monster_types[c.guardian], gx, gy))
        if last and self.bounties:      # bounties: a marked creature, or the artifact, deepest in
            from game.monsters import Monster
            open_spots = sorted(p for p, d in dist.items() if d > 12 and p not in (plan.entry, plan.far_end)
                                and not any((m.x, m.y) == p for m in game_map.monsters)) or sorted(dist)
            for job_id, kind, want in self.bounties:
                bx, by = rng.choice(open_spots)
                open_spots = [p for p in open_spots if p != (bx, by)] or open_spots
                if kind == "kill" and want in self.monster_types:
                    if self.monster_types[want].swims:           # a swimmer waits in the water
                        wet = sorted((x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == "~"
                                     and not any((m.x, m.y) == (x, y) for m in game_map.monsters))
                        if wet:
                            bx, by = rng.choice(wet)
                    m = Monster.spawn(self.monster_types[want], bx, by)
                    m.bounty = job_id
                    m.name = f"marked {m.name}"
                    game_map.monsters.append(m)
                elif kind in ("find", "errand") and want in catalogue.types:
                    game_map.item_spawns = [(bx, by, want, 1)]
                    game_map.place_items(catalogue)
        if index < len(self.writings) and self.writings[index]:   # a writing, somewhere off the beaten track
            far = [p for p, d in dist.items() if d > 15 and p not in (plan.far_end, plan.entry)] or list(dist)
            wx, wy = rng.choice(sorted(far))
            game_map.item_spawns = [(wx, wy, self.writings[index], 1)]
            game_map.place_items(catalogue)
        for item_id, area in self.story_items:          # story items: at the far end, or near it
            if area == index:
                spots = [p for p, d in dist.items() if p not in (plan.entry, plan.far_end)] or list(dist)
                sx, sy = max(sorted(spots), key=lambda p: dist[p])   # as deep in as the area goes
                game_map.item_spawns = [(sx, sy, item_id, 1)]
                game_map.place_items(catalogue)
        self.entries[index] = plan.entry
        self.far_ends[index] = plan.far_end
        return game_map
