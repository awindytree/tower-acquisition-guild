"""The Guild's contracts board (user, 2026-11-19; v0.44.0).

"Go to [Thundering][Midnight][Bog Witch] and retrieve the [broken artifact / story
item] reported in our most recent scouting report." Each posting names a place
(three keywords) and what to bring back. Story key hunts are posted here too.

Taking a posting makes it the Hunter's contract (one at a time, Hunter state).
The Hunter then walks into the Wayfinder and chooses those words; a trip
to the contract's place is the contract's hunt. Taking a posting teaches its
words (as in .hack, boards are one way words are learned).
"""
from __future__ import annotations

import random
import zlib

from game.hunt import Contract, pick_artifact, depth_of

POSTINGS = 6          # generated postings a day (my call)


def generated(engine, day: int) -> list[Contract]:
    """Today's postings (same day, same postings): a spread of dangers, each at a place
    picked from all the words, known or not."""
    kw = engine.regions.keywords
    rng = random.Random(zlib.crc32(f"guild/{day}".encode()))
    words = {slot: sorted(kw.words[slot]) for slot in ("danger", "land", "feature")}
    by_danger: dict[int, list[str]] = {}
    for wid in words["danger"]:
        by_danger.setdefault(int(kw.words["danger"][wid].data["danger"]), []).append(wid)
    out = []
    dangers = sorted(by_danger)
    for i in range(POSTINGS):
        danger = dangers[min(len(dangers) - 1, i * len(dangers) // POSTINGS)]   # a spread, low to high
        d = rng.choice(by_danger[danger])
        land = [l for l in words["land"] if kw.valid(d, l)]           # never two verbs
        place = engine.regions.place(d, rng.choice(land), rng.choice(words["feature"]))
        artifact = pick_artifact(place, danger, engine.catalogue, rng)
        for _ in range(6):    # not the same artifact twice on the board
            if all(c.artifact_id != artifact for c in out):
                break
            artifact = pick_artifact(place, danger, engine.catalogue, rng)
        out.append(Contract(place, artifact, danger, depth_of(place, danger), rng.getrandbits(32)))
    return sorted(out, key=lambda c: c.danger)


def board(engine) -> list[Contract]:
    """Everything on the contracts board today: key hunts first."""
    from game import story
    return story.posted_contracts(engine) + generated(engine, engine.day)


def describe(engine, c: Contract) -> str:
    """The posting's wording."""
    if c.story:
        return ""
    t = engine.catalogue[c.artifact_id]
    return (f"Go to {c.region.name} and retrieve the {t.name}"
            f"{f' ({t.rarity.name})' if t.rarity else ''} reported in our most recent scouting report.")


def take(engine, c: Contract) -> str:
    """The posting becomes the Hunter's contract (replacing any other). Its words are learned."""
    from game import keywords
    p = engine.player
    old = p.contract
    p.contract = c
    keywords.learn(engine, list(c.region.place))
    words = c.region.name
    swap = f" (in place of {old.title(engine.catalogue)})" if old and old.seed != c.seed else ""
    return f"You take the contract{swap}: {c.title(engine.catalogue)}. Step into the Wayfinder and choose {words}."


def matches(engine, region) -> Contract | None:
    """The Hunter's contract, if it's for this place."""
    c = engine.player.contract
    return c if c is not None and c.region.id == region.id else None
