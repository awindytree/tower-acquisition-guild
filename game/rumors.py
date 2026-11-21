"""Rumours and small talk (v0.47.0): now and then, someone in the plaza passes on one of
the Wayfinder's words (user, 2026-11-19: "in rarer cases, townsfolk may simply pass on a
word as part of a rumor or small chat"). Lines and chances: data/rumors.json."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def settings() -> dict:
    return json.loads((DATA / "rumors.json").read_text(encoding="utf-8"))


def tell(engine, folk_id: str, rng) -> str:
    """What this person has to say today: maybe a word you don't know (learned), else small talk.
    Once a Pulse each: asking again the same Pulse gets the same answer."""
    s = settings()
    told = engine.__dict__.setdefault("rumors_told", {})     # folk id -> (day, line)
    if folk_id in told and told[folk_id][0] == engine.day:
        return told[folk_id][1]
    kw = engine.regions.keywords
    unknown = [w for w in kw.all_ids(ordinary=True) if w not in engine.words]
    if unknown and rng.random() < s["chance"]:
        word = kw.word(rng.choice(sorted(unknown)))
        line = rng.choice(s["word_lines"]).format(word=word.shown)
        from game import keywords
        keywords.learn(engine, [word.id])
    else:
        line = rng.choice(s["chatter"])
    told[folk_id] = (engine.day, line)
    return line
