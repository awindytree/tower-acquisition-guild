"""The Wayfinder's keywords, and the places they lead to (user, 2026-11-19).

Three words, one per slot (danger, land, feature), make a place on the Overland,
like .hack's Chaos Gates. The same words always lead to the same place: the
layout of each area is seeded from the words (game/hunt.py); what's in it is
rolled fresh each trip. Data: data/keywords.json (all placeholders).

A place is a `Region` (game/hunt.py) with id "danger/land/feature", so the rest
of the game (contracts, hunts, the archive, saves) treats it like the old gate
regions. `PlaceBook` builds them on demand: `engine.regions["quiet/green/daybreak"]`.
"""
from __future__ import annotations

import json
import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

SLOTS = ("danger", "land", "feature")
SLOT_NAMES = {"danger": "Danger", "land": "Land", "feature": "Feature"}
ANY = "*"   # "anything": the artifact picks a word for this slot


@dataclass(frozen=True)
class Word:
    id: str
    slot: str
    text: str
    data: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def shown(self) -> str:
        return f"[{self.text}]"


class Keywords:
    def __init__(self, path: str | Path) -> None:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.words: dict[str, dict[str, Word]] = {}
        for slot in SLOTS:
            self.words[slot] = {wid: Word(wid, slot, d["word"], d) for wid, d in raw[slot].items()}
        self.start: list[str] = list(raw.get("start", []))
        self.rank_words: dict[int, list[str]] = {int(k): v for k, v in raw.get("rank_words", {}).items()}
        # Grammar (user, 2026-11-19): danger and land words are adjectives or verbs; features are nouns.
        for slot, allowed_pos in (("danger", ("adjective", "verb")), ("land", ("adjective", "verb")), ("feature", ("noun",))):
            for w in self.words[slot].values():
                if w.data.get("pos") not in allowed_pos:
                    raise ValueError(f"Keyword {w.id!r} ({slot}): pos must be {' or '.join(allowed_pos)}")
        from game import procgen
        for w in self.words["land"].values():
            if w.data["style"] not in procgen.STYLES:
                raise ValueError(f"Keyword {w.id!r}: style must be one of {list(procgen.STYLES)}")
        for wid in self.start + [w for ws in self.rank_words.values() for w in ws]:
            self.word(wid)   # (raises if unknown)

    def word(self, wid: str) -> Word:
        for slot in SLOTS:
            if wid in self.words[slot]:
                return self.words[slot][wid]
        raise KeyError(f"No keyword {wid!r}")

    def slot_of(self, wid: str) -> str:
        return self.word(wid).slot

    def valid(self, d: str, l: str) -> bool:
        """A place can't have a verb for both its danger and its land word (user)."""
        return not (self.words["danger"][d].data["pos"] == "verb" and self.words["land"][l].data["pos"] == "verb")

    def all_ids(self, ordinary: bool = False) -> list[str]:
        return [wid for slot in SLOTS for wid in self.words[slot] if not (ordinary and self.words[slot][wid].data.get("story"))]

    def ordinary(self, slot: str) -> list[str]:
        """The slot's words, less story words ("story": true, v0.67.0): those are only ever learned
        through the story, so the boards, rumours and the Guild scholar never hand them out."""
        return sorted(wid for wid, w in self.words[slot].items() if not w.data.get("story"))


def place_id(danger: str, land: str, feature: str) -> str:
    return f"{danger}/{land}/{feature}"


def split(pid: str) -> tuple[str, str, str]:
    parts = pid.split("/")
    if len(parts) != 3:
        raise KeyError(pid)
    return parts[0], parts[1], parts[2]


def make_place(kw: Keywords, d: str, l: str, f: str):
    from game.hunt import Region
    dw, lw, fw = kw.words["danger"][d], kw.words["land"][l], kw.words["feature"][f]
    if not kw.valid(d, l):
        raise KeyError(f"{d}/{l}/{f}: two verbs")
    danger = int(dw.data["danger"])
    return Region(
        id=place_id(d, l, f), name=f"{dw.shown}{lw.shown}{fw.shown}", gate="Wayfinder",
        style=lw.data["style"], light=fw.data.get("light", lw.data.get("light", "torch")),
        danger=(danger, danger), area_size=tuple(lw.data.get("area_size", (72, 40))), artifacts=(),
        place=(d, l, f), depth=int(dw.data.get("depth", min(5, 2 + danger))),
        creatures=float(fw.data.get("creatures", 1.0)), favour=fw.data.get("favour", ""),
        rarity_up=int(fw.data.get("rarity_up", 0)), writings=float(fw.data.get("writings", 1.0)),
        sight=float(fw.data.get("sight", 1.0)))


class PlaceBook(Mapping):
    """Every place the words can make, built when first asked for. Looks like the
    old dict of regions: `book[id]`, `id in book`, `book.values()`."""

    def __init__(self, keywords: Keywords) -> None:
        self.keywords = keywords
        self._cache: dict = {}

    def __getitem__(self, pid: str):
        if pid not in self._cache:
            try:
                d, l, f = split(pid)
                self._cache[pid] = make_place(self.keywords, d, l, f)
            except KeyError:
                raise KeyError(pid) from None
        return self._cache[pid]

    def __contains__(self, pid) -> bool:
        try:
            self[pid]
            return True
        except (KeyError, TypeError):
            return False

    def __iter__(self):
        w, kw = self.keywords.words, self.keywords
        return (place_id(d, l, f) for d in w["danger"] for l in w["land"] if kw.valid(d, l) for f in w["feature"])

    def __len__(self) -> int:
        return sum(1 for _ in iter(self))

    def place(self, d: str, l: str, f: str):
        return self[place_id(d, l, f)]


def load_places(path: str | Path) -> PlaceBook:
    """The places. Takes data/keywords.json (or, for older callers, any file in
    the data folder: the keywords file beside it is used)."""
    path = Path(path)
    if path.name != "keywords.json":
        path = path.with_name("keywords.json")
    return PlaceBook(Keywords(path))


# ---- Knowing words (world state: engine.words) ---------------------------------------------------
def learn(engine, wids, say: bool = True) -> list[str]:
    """Add words to what the Guild and the city know. Returns the ones that were new."""
    kw = engine.regions.keywords
    new = [w for w in wids if w not in engine.words and w in kw.all_ids()]
    for w in new:
        engine.words.add(w)
    if new and say:
        shown = " ".join(kw.word(w).shown for w in new)
        engine.log(f"New {'word' if len(new) == 1 else 'words'} for the Wayfinder: {shown}.")
    return new


def known(engine, slot: str) -> list[Word]:
    kw = engine.regions.keywords
    return [w for wid, w in kw.words[slot].items() if wid in engine.words]


def allowed(engine, word: Word) -> bool:
    """Rank still limits danger (user, 2026-11-18): the artifact takes danger words
    only up to the Hunter's rank (my call, for now)."""
    if word.slot != "danger":
        return True
    from game import ranks
    if int(word.data["danger"]) <= ranks.max_danger(engine.player.rank):
        return True
    # (v0.67.0) a key hunt open to the Hunter's rank opens its own danger word, whatever the rank
    from game import story
    return any(c.region.place and c.region.place[0] == word.id and not ranks.contract_closed(engine.player, c)
               for c in story.posted_contracts(engine))


def resolve(engine, choice: tuple[str, str, str], rng: random.Random) -> tuple[str, str, str]:
    """Fill "anything" slots: a word at random from the KNOWN words in that slot (user,
    2026-11-19), that fits the other slot, and (danger) within the Hunter's rank."""
    kw = engine.regions.keywords
    out = []
    for slot, wid in zip(SLOTS, choice):
        if wid == ANY:
            every = [w for w in kw.words[slot].values() if allowed(engine, w)]
            pool = [w for w in every if w.id in engine.words] or every
            if slot == "danger" and choice[1] != ANY:      # never two verbs
                pool = [w for w in pool if kw.valid(w.id, choice[1])]
            if slot == "land":
                pool = [w for w in pool if kw.valid(out[0], w.id)]
            wid = rng.choice(sorted(pool, key=lambda w: w.id)).id
        out.append(wid)
    return out[0], out[1], out[2]


def random_place(engine, danger: int, rng: random.Random):
    """A place of the given danger, from all the words (for the Guild's boards): grammatical."""
    kw = engine.regions.keywords
    dwords = [w for w in kw.ordinary("danger") if int(kw.words["danger"][w].data["danger"]) == danger] or kw.ordinary("danger")
    d = rng.choice(dwords)
    land = [w for w in kw.ordinary("land") if kw.valid(d, w)]
    return engine.regions.place(d, rng.choice(land), rng.choice(kw.ordinary("feature")))
