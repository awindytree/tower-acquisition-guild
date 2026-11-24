"""Townsfolk and conversations.

Townsfolk are defined in data/townsfolk.json; each has a conversation in
data/dialogue/<id>.json (see data/dialogue/_README.md for the format).
A conversation is a set of nodes: something said, then choices. Choices and
nodes can have conditions ("if") and effects ("do"). Talking takes no time.

Flags follow the persistence rule: "hunter" flags belong to the Hunter (lost
when they die); "world" flags belong to Bytorsskug (they outlive Hunters).
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Townsperson:
    id: str
    given: str
    middle: str
    surname: str
    glyph: str
    color: tuple
    description: str
    dialogue: str
    wander: int = 0
    extra: dict = None    # anything else in townsfolk.json (story people: hall_spot, teaches, off, hall; v0.67.0)

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.given, self.middle, self.surname) if part)


def load_townsfolk(path: str | Path) -> dict[str, Townsperson]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    folk = {}
    for tid, d in raw.items():
        if tid.startswith("_"):
            continue
        given, middle, surname = (list(d["name"]) + ["", "", ""])[:3]
        folk[tid] = Townsperson(tid, given, middle, surname, d.get("glyph", "@"),
                                tuple(d.get("color", (240, 200, 120))), d.get("description", ""),
                                d.get("dialogue", tid), d.get("wander", 0), dict(d))
    return folk


@dataclass
class Conversation:
    id: str
    start: list            # [{"if": [...], "node": id}, ...]
    nodes: dict


_cache: dict[str, Conversation] = {}


def load_conversation(folder: str | Path, conv_id: str) -> Conversation:
    path = Path(folder) / f"{conv_id}.json"
    key = str(path)
    if key not in _cache:
        d = json.loads(path.read_text(encoding="utf-8"))
        start = d["start"]
        if isinstance(start, str):
            start = [{"node": start}]
        conv = Conversation(conv_id, start, d["nodes"])
        for entry in conv.start:  # check links now rather than mid-conversation
            _check(conv, entry["node"])
        for node in conv.nodes.values():
            for choice in node.get("choices", []):
                if "goto" in choice:
                    _check(conv, choice["goto"])
        _cache[key] = conv
    return _cache[key]


def _check(conv: Conversation, node_id: str) -> None:
    if node_id not in conv.nodes:
        raise ValueError(f"Conversation {conv.id!r}: no node {node_id!r}")


# ---- Conditions and effects ----------------------------------------------------------------
def holds(engine, condition: str) -> bool:
    negate = condition.startswith("!")
    cond = condition[1:] if negate else condition
    kind, _, rest = cond.partition(":")
    p = engine.player
    if kind == "flag":
        scope, _, name = rest.partition(":")
        result = name in (p.flags if scope == "hunter" else engine.world_flags)
    elif kind == "item":
        item_id, _, n = rest.partition(":")
        result = p.inventory.count_of(item_id) >= int(n or 1)
    elif kind == "shards":
        result = p.shards >= int(rest)
    elif kind == "skill":
        skill_id, _, n = rest.partition(":")
        result = p.skill(skill_id).rank >= int(n)
    elif kind == "level":
        result = p.stats.level >= int(rest)
    elif kind == "duel":
        result = engine.date.duel == rest
    elif kind == "holiday":
        result = engine.date.intercalary > 0
    elif kind == "dues":
        result = p.dues_owed > 0
    elif kind == "jobs_done":
        result = any(j.done for j in p.jobs)
    elif kind == "caravan_escort":          # (v0.92.0) this caravan would take a guard
        from game import caravans
        result = caravans.offers_escort(engine)
    elif kind == "rank_ready":
        from game import ranks
        result = ranks.ready(p)
    elif kind == "rank":
        result = p.rank + 1 >= int(rest)            # rank:3 = at least the third rank
    elif kind == "mentor_teaches":
        result = bool(engine.mentor and engine.mentor["skills"])
    elif kind == "writings":
        result = any(i.type.writing for i in p.inventory.items)
    elif kind == "notes":
        from game import archive
        result = archive.has_notes(p)
    elif kind == "injured":
        result = bool(p.injuries)
    elif kind == "home":                    # owns a home (v0.74.0)
        result = getattr(engine, "home", None) is not None
    elif kind == "trophies":                # carrying a trophy (v0.61.0)
        result = any(i.trophy is not None for i in p.inventory.items)
    elif kind == "orders_ready":
        from game import crafting
        result = bool(crafting.ready_orders(engine))
    else:
        from game import story
        result = story.holds(engine, kind, rest)
        if result is None:
            raise ValueError(f"Unknown dialogue condition {condition!r}")
    return result != negate


def all_hold(engine, conditions) -> bool:
    return all(holds(engine, c) for c in conditions or [])


def apply(engine, effects) -> str | None:
    """Apply effects. Returns a screen to open ("shop:ID", "workshop:ID", "stash", "train:IDS") if any."""
    from game.items import Item
    p = engine.player
    opens = None
    for effect in effects or []:
        kind, _, rest = effect.partition(":")
        if kind in ("set", "clear"):
            scope, _, name = rest.partition(":")
            flags = p.flags if scope == "hunter" else engine.world_flags
            (flags.add if kind == "set" else flags.discard)(name)
        elif kind == "give":
            item_id, _, n = rest.partition(":")
            item = Item(engine.catalogue[item_id], int(n or 1))
            if not p.inventory.add(item):
                engine.game_map.items.append(_floor(p, item))
                engine.log(f"Your pack is full; the {item.type.name} is set at your feet.")
        elif kind == "take":
            item_id, _, n = rest.partition(":")
            left = int(n or 1)
            for i in reversed(range(len(p.inventory.items))):
                it = p.inventory.items[i]
                if left and it.type.id == item_id:
                    took = min(left, it.count)
                    p.inventory.remove(i, took)
                    left -= took
        elif kind == "shards":
            p.shards = max(0, p.shards + int(rest))
        elif kind in ("shop", "workshop"):
            opens = effect
        elif kind == "stash":
            opens = "stash"
        elif kind == "pay_dues":
            engine.log(engine.pay_dues())
        elif kind == "collect_jobs":
            from game import work
            engine.log(work.collect(engine))
        elif kind == "jobs":
            opens = "jobs"
        elif kind == "craft":
            opens = effect   # "craft:smith"
        elif kind == "upgrade":
            opens = "upgrade"   # (v0.76.0: the smith raises gear)
        elif kind == "upgrade_tackle":
            opens = "upgrade_tackle"   # (v0.96.0: the tackleman raises tackle)
        elif kind == "maps":
            opens = "maps"      # (v0.84.0: the cartographer's maps)
        elif kind.startswith("caravan_"):
            opens = "caravan:" + kind[8:]      # (v0.92.0: trade, walk along, hire on as a guard)
        elif kind == "hand_in_writings":
            from game import library
            engine.log(library.hand_in(engine))
        elif kind == "report_notes":
            from game import archive
            engine.log(archive.report(engine))
        elif kind == "word_lesson":         # the Wayfinder study's scholar (v0.60.0)
            from game import works
            engine.log(works.word_lesson(engine))
        elif kind == "contest_collect":     # the contests' angler (v0.100.0)
            from game import contests
            engine.log(contests.collect(engine))
        elif kind in ("library", "archive", "mentor", "hall", "retire", "sit_rank", "labour", "works",
                      "trophies", "butcher", "trophy_wall", "homes", "fish_weigh", "fish_book",
                      "contest_weigh", "contest_past"):
            opens = kind
        elif kind == "treat":
            opens = effect   # "treat:healer"
        elif kind == "collect_orders":
            from game import crafting
            engine.log(crafting.collect(engine))
        elif kind == "train":
            opens = effect   # "train:marksmanship" (several: "train:a,b")
        elif kind == "teach":
            opens = effect   # "teach:FOLK": a mentor from townsfolk.json ("teaches", "discount"; v0.67.0)
        elif kind == "carry":  # "carry:ITEM:FOLK": pick someone up (they become ITEM in the pack; v0.67.0)
            item_id, _, folk = rest.partition(":")
            item = Item(engine.catalogue[item_id])
            if p.inventory.add(item):
                gm = engine.game_map
                gm.npcs = [n for n in gm.npcs if n.folk_id != folk]
                engine.log(f"You get {item.type.name} up, an arm over your shoulders. ({item.slots} slots of your pack.)")
            else:
                free = max(0, p.inventory.capacity - p.inventory.used)
                engine.log(f"You'd need {item.slots} slots of room in your pack to carry {item.type.name}; you have "
                           f"{free}. Leave something behind (d in your pack) and try again.")
        else:
            from game import story
            if not story.apply(engine, kind, rest):
                raise ValueError(f"Unknown dialogue effect {effect!r}")
    return opens


def _floor(p, item):
    from game.items import FloorItem
    return FloorItem(p.x, p.y, item)


class _Values(dict):
    def __missing__(self, key):   # an unknown {word}: a story counter not counted yet is 0
        return 0


def fill(engine, text: str, extra: dict | None = None) -> str:
    """Fill in {given}, {name}, {calling}, {date}, {pulse}, {dues}, {earned}, any story
    counter by name ({example_dogs}), and anything in extra (a rival's words, say)."""
    p = engine.player
    from game.names import calling
    values = _Values(getattr(engine, "story", {}).get("counters", {}))
    from game import ranks
    nxt = ranks.next_rank(p)
    values.update(given=p.name, name=p.full_name, calling=calling(p), date=engine.date.short,
                  pulse=engine.date.pulse or "a holiday", dues=p.dues_owed, earned=p.earned,
                  rank=ranks.of(p)["name"], next_rank=nxt["name"] if nxt else "", rank_fee=nxt["fee"] if nxt else 0,
                  rank_needs=ranks.describe_next(p), labour=ranks.labour_pulses(p))
    values.update(extra or {})
    return text.format_map(values)


# ---- A conversation in progress --------------------------------------------------------------
@dataclass
class Talk:
    """Where a conversation stands: the node, what was said, and the choices on offer."""
    engine: object
    speaker: Townsperson
    conv: Conversation
    node_id: str = ""
    text: str = ""
    choices: list = field(default_factory=list)
    opens: str | None = None   # a screen to open when the talk ends
    done: bool = False
    rng: random.Random = field(default_factory=random.Random)

    def begin(self) -> None:
        for entry in self.conv.start:
            if all_hold(self.engine, entry.get("if")):
                self.show(entry["node"])
                return
        self.done = True

    def show(self, node_id: str) -> None:
        node = self.conv.nodes[node_id]
        self.node_id = node_id
        text = node.get("text", "")
        if isinstance(text, list):
            text = self.rng.choice(text)
        elif isinstance(text, dict):      # {"variants": [...]}: one not used yet in this world (v0.66.0)
            from game import story
            text = story.text(self.engine, f"node:{self.speaker.id}:{node_id}", text)
        extra = {}
        if self.speaker.id.startswith("rival:"):
            from game import rivals
            extra = rivals.values(self.engine, self.speaker.id)
        elif self.speaker.id.startswith("caravan:"):
            from game import caravans
            extra = caravans.values(self.engine, self.speaker.id)
        elif self.speaker.id == "tackleman":
            from game import fishing
            extra = {"fish_tip": fishing.tip(self.engine, self.rng)}
        elif self.speaker.id == "angler":
            from game import contests
            extra = {"contest": contests.describe(self.engine)}
        self.text = fill(self.engine, text, extra)
        if node.get("rumor"):          # small talk that may pass on a word (game/rumors.py)
            from game import rumors
            self.text = rumors.tell(self.engine, self.speaker.id, self.rng)
        self.opens = apply(self.engine, node.get("do")) or self.opens
        self.choices = [c for c in node.get("choices", []) if all_hold(self.engine, c.get("if"))]
        if not self.choices:
            self.choices = [{"text": "(Leave)", "end": True}]
        if any(node_id == entry["node"] for entry in self.conv.start):
            from game import story
            self.choices = story.talk_choices(self.engine, self.speaker.id) + self.request_choices() + self.choices
        # Fill in choice text too ("Pay my dues ({dues} shards).")
        self.choices = [dict(c, text=fill(self.engine, c["text"], extra)) for c in self.choices]

    def request_choices(self) -> list:
        """'Here's the … you asked for' for each of this person's requests the Hunter can fill;
        'About your request…' for the rest."""
        from game import work
        out = []
        for r in work.requests_for(self.engine, self.speaker.id):
            thing = r.thing(self.engine.catalogue)
            if work.can_hand_over(self.engine, r) is not None:
                if r.kind in ("item", "errand"):
                    offer = f"Here's the {self.engine.catalogue[r.want].real_name} you wanted."
                elif r.kind == "material":
                    offer = f"Here's the {thing} you wanted."
                elif r.kind == "fish":
                    offer = f"Here's a {self.engine.catalogue[r.want].real_name} for you."
                else:
                    offer = f"I have a broken {self.engine.catalogue.rarities[r.want].name} artifact for you."
                out.append({"text": f"{offer} ({r.reward} shards)", "request": r.id})
            else:
                out.append({"text": f"About your request for {thing}...", "request_info": r.id})
        return out
        if self.opens:
            self.done = True

    def pick(self, index: int) -> None:
        from game import story, work
        choice = self.choices[index]
        if "story_talk" in choice:   # a line the story gives this person (data/story)
            t = story.talk_entry(self.engine, choice["story_talk"])
            if t["id"] not in self.engine.story["seen"]:
                self.engine.story["seen"].append(t["id"])
            reply = t.get("reply", "")
            self.text = story.text(self.engine, f"talk:{t['id']}", reply)
            self.opens = apply(self.engine, t.get("do")) or self.opens
            story.check(self.engine)
            if self.opens:
                self.done = True
                return
            self.choices = [{"text": t.get("leave", "(Leave)"), "end": True}]
            return
        if "request" in choice or "request_info" in choice:
            rid = choice.get("request", choice.get("request_info"))
            r = next((r for r in self.engine.requests if r.id == rid), None)
            if r is None:
                self.done = True
                return
            if "request" in choice:
                self.engine.log(work.hand_over(self.engine, r))
                self.text = self.rng.choice(["Just what I wanted. Here, as promised.", "Wonderful! Here's your pay.",
                                             "That's the one. Thank you, Hunter."])
            else:
                work.reveal(self.engine, [r])
                left = r.expires - self.engine.day
                self.text = (f"I'm after {r.thing(self.engine.catalogue)}. I'll pay {r.reward} shards. "
                             f"The notice stays up {left} more Pulse{'s' if left != 1 else ''}.")
            self.choices = [{"text": "(Leave)", "end": True}]
            return
        self.opens = apply(self.engine, choice.get("do")) or self.opens
        if self.opens or choice.get("end") or "goto" not in choice:
            self.done = True
        else:
            self.show(choice["goto"])
