"""The story skeleton: quests, story flags and counters, scenes on events, story lines in
conversations, and story items hidden in hunts. All of it is written in data/story/*.json
(see data/story/_README.md); nothing story-specific lives in code.

Progress is world state by default (the story goes on when a Hunter dies, as the city
does); a quest can be marked "scope": "hunter" to belong to one Hunter instead.

Conditions and effects are shared with conversations (game/dialogue.py), so a dialogue
choice can start a quest and a scene can check a flag. The story adds:
  conditions: quest:Q (active)  quest:Q:STAGE  done:Q  started:Q  failed:Q  seen:SCENE
              count:NAME>=N (also > < <= = !=)  on_hunt  region:PLACE  word:ID  knows:ID  event:KEY=VALUE (scenes)
  effects:    start:Q  advance:Q  stage:Q:STAGE  finish:Q  fail:Q  note:Q:TEXT
              count:NAME:+N / -N / =N  scene:SCENE  hide:ITEM:REGION[:AREA]  message:TEXT
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "story"
EVENTS = ("new_game", "new_hunter", "set_out", "area", "kill", "pickup", "home", "day", "retire", "death",
          "contract_done", "contract_failed",
          "talk", "wayfinder", "see", "bounty_paid",
          "manual")   # "manual": never fired; played only by a scene:ID effect   # v0.54.0: talk (folk=ID), see (monster=ID, marked)


class StoryData:
    """Everything written in a story folder: quests, scenes and talk, merged from every file."""

    def __init__(self, folder: str | Path | None = DATA) -> None:
        self.quests: dict[str, dict] = {}
        self.scenes: dict[str, dict] = {}
        self.talk: list[dict] = []
        self.contracts: dict[str, dict] = {}
        self.bounties: dict[str, dict] = {}
        if folder is None or not Path(folder).exists():
            return
        for path in sorted(Path(folder).glob("*.json")):
            if path.name.startswith("_"):
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            for qid, q in raw.get("quests", {}).items():
                stages = q.get("stages", [])
                if not stages:
                    raise ValueError(f"{path.name}: quest {qid!r} has no stages")
                ids = [s["id"] for s in stages]
                if len(set(ids)) != len(ids):
                    raise ValueError(f"{path.name}: quest {qid!r} has two stages with the same id")
                self.quests[qid] = q
            for sid, sc in raw.get("scenes", {}).items():
                if sc.get("on") not in EVENTS:
                    raise ValueError(f"{path.name}: scene {sid!r}: 'on' must be one of {EVENTS}")
                self.scenes[sid] = sc
            for cid, c in raw.get("contracts", {}).items():
                for key in ("words", "title", "prize"):
                    if key not in c:
                        raise ValueError(f"{path.name}: story contract {cid!r} needs a {key!r}"
                                         + (" (since v0.44.0 a key hunt names its place by three keywords, "
                                            "not a region)" if key == "words" and "region" in c else ""))
                if not (isinstance(c["words"], list) and len(c["words"]) == 3):
                    raise ValueError(f"{path.name}: story contract {cid!r}: words must be [danger, land, feature]")
                self.contracts[cid] = c
            for bid, b in raw.get("bounties", {}).items():   # story bounties (v0.54.0)
                for key in ("words", "title", "reward"):
                    if key not in b:
                        raise ValueError(f"{path.name}: story bounty {bid!r} needs a {key!r}")
                self.bounties[bid] = b
            for i, t in enumerate(raw.get("talk", [])):
                t.setdefault("id", f"{path.stem}:{i}")
                self.talk.append(t)


def empty() -> dict:
    """World story state: quests, scenes seen, counters, items waiting to be found, and every
    item the story has hidden (so they're never lost with a Hunter)."""
    return {"quests": {}, "seen": [], "counters": {}, "hidden": [], "items": [], "posted": [], "completed": []}


# ---- Where a quest's state lives --------------------------------------------------------------------
def _quests(engine, qid: str) -> dict:
    q = engine.story_data.quests.get(qid, {})
    return engine.player.quests if q.get("scope") == "hunter" else engine.story["quests"]


def state(engine, qid: str) -> dict | None:
    return _quests(engine, qid).get(qid)


def stage_def(engine, qid: str, stage_id: str) -> dict:
    return next(s for s in engine.story_data.quests[qid]["stages"] if s["id"] == stage_id)


def active(engine) -> list[str]:
    out = []
    for qid in engine.story_data.quests:
        st = state(engine, qid)
        if st and not st.get("done") and not st.get("failed"):
            out.append(qid)
    return out


# ---- Changing quests --------------------------------------------------------------------------------
def start(engine, qid: str) -> None:
    if qid not in engine.story_data.quests:
        raise ValueError(f"No quest {qid!r} in data/story")
    if state(engine, qid):
        return  # already started (or over)
    first = engine.story_data.quests[qid]["stages"][0]["id"]
    _quests(engine, qid)[qid] = {"stage": None, "log": [], "started": engine.day}
    q = engine.story_data.quests[qid]
    engine.log(f"New quest: {q['title']}.")
    _enter(engine, qid, first)


def _enter(engine, qid: str, stage_id: str) -> None:
    st = state(engine, qid)
    st["stage"] = stage_id
    sd = stage_def(engine, qid, stage_id)
    if sd.get("log"):
        st["log"].append(fill(engine, sd["log"]))
    from game.dialogue import apply
    opens = apply(engine, sd.get("do"))
    if opens:
        engine.open_vendor(opens)


def advance(engine, qid: str, to: str | None = None) -> None:
    """On to the named stage, or the next one; past the last, the quest is done."""
    st = state(engine, qid)
    if not st or st.get("done") or st.get("failed"):
        return
    stages = engine.story_data.quests[qid]["stages"]
    if to is None:
        cur = stage_def(engine, qid, st["stage"])
        to = cur.get("next")
        if to is None:
            i = [s["id"] for s in stages].index(st["stage"])
            to = stages[i + 1]["id"] if i + 1 < len(stages) else "done"
    if to == "done":
        finish(engine, qid)
    else:
        _enter(engine, qid, to)


def finish(engine, qid: str) -> None:
    st = state(engine, qid)
    if not st or st.get("done"):
        return
    q = engine.story_data.quests[qid]
    st["done"] = True
    st["ended"] = engine.day
    if q.get("done_log"):
        st["log"].append(fill(engine, q["done_log"]))
    engine.log(f"Quest complete: {q['title']}.")
    from game.dialogue import apply
    apply(engine, q.get("on_done"))


def fail(engine, qid: str) -> None:
    st = state(engine, qid)
    if not st or st.get("done") or st.get("failed"):
        return
    st["failed"] = True
    st["ended"] = engine.day
    engine.log(f"Quest failed: {engine.story_data.quests[qid]['title']}.")


def check(engine) -> None:
    """Move any quest on whose current stage's 'until' conditions now hold (several, if they chain)."""
    from game.dialogue import all_hold
    for _ in range(20):
        moved = False
        for qid in active(engine):
            sd = stage_def(engine, qid, state(engine, qid)["stage"])
            if sd.get("until") and all_hold(engine, sd["until"]):
                advance(engine, qid)
                moved = True
        if not moved:
            return


# ---- Events and scenes -----------------------------------------------------------------------------------
def fire(engine, event: str, **ctx) -> None:
    """Something happened (see EVENTS): play the scenes waiting for it, then move quests on."""
    from game.dialogue import all_hold
    if not engine.story_data.scenes and not engine.story_data.quests:
        return
    engine.story_event = {"event": event, **{k: str(v) for k, v in ctx.items()}}
    try:
        for sid, sc in engine.story_data.scenes.items():
            if sc["on"] != event:
                continue
            if sc.get("once", True) and sid in engine.story["seen"]:
                continue
            if all_hold(engine, sc.get("if")):
                play(engine, sid)
    finally:
        engine.story_event = {}
    check(engine)


def play(engine, sid: str) -> None:
    """A scene: its effects now; its pages (if any) on screen as soon as nothing else is."""
    from game.dialogue import apply
    sc = engine.story_data.scenes[sid]
    if sid not in engine.story["seen"]:
        engine.story["seen"].append(sid)
    apply(engine, sc.get("do"))
    if sc.get("pages"):
        engine.scene_queue.append(sid)


def show_next_scene(engine) -> None:
    if engine.screen is not None:
        return
    if engine.scene_queue:
        from game.screens import SceneScreen
        engine.screen = SceneScreen(engine.scene_queue.pop(0))
    elif getattr(engine, "after_scenes", None):     # something waiting for the scenes to end (v0.54.0)
        then, engine.after_scenes = engine.after_scenes, None
        then(engine)


# ---- Story items hidden in hunts -------------------------------------------------------------------------
def plan_hunt(engine, contract) -> list:
    """Story items waiting in this hunt's region: [[item, area index], ...]. They leave the waiting
    list now and come back to it if the hunt ends without them (end_hunt)."""
    out, keep = [], []
    for item, region, area in engine.story["hidden"]:
        if region == contract.region.id:
            out.append([item, min(area if area is not None else contract.depth - 1, contract.depth - 1)])
        else:
            keep.append([item, region, area])
    engine.story["hidden"] = keep
    return out


def end_hunt(engine, hunt) -> None:
    """A hunt is over: story items not picked up wait again, for the next hunt in that region."""
    if hunt is None:
        return
    for item, area in hunt.story_items:
        if not (engine.player.inventory.count_of(item) or engine.stash.count_of(item)):
            engine.story["hidden"].append([item, hunt.contract.region.id, area])


def rescue(engine) -> None:
    """A Hunter has died: the story items they carried go to the guild stash (the Guild sees to it),
    or back into hiding if it's full."""
    p = engine.player
    for item in list(p.inventory.items):
        if item.type.id in engine.story["items"]:
            p.inventory.items.remove(item)
            if engine.stash.add(item):
                engine.log(f"The Guild recovers the {item.type.name} and puts it in the stash.")
            else:
                region = engine.hunt.contract.region.id if engine.hunt else None
                if region:
                    engine.story["hidden"].append([item.type.id, region, None])


# ---- Conditions and effects (used by game/dialogue.py) ---------------------------------------------------------
_COUNT = re.compile(r"^([\w.]+)\s*(>=|<=|!=|>|<|=)\s*(-?\d+)$")


def holds(engine, kind: str, rest: str) -> bool | None:
    """A story condition, or None if `kind` isn't one."""
    s = engine.story
    if kind == "quest":
        qid, _, stage = rest.partition(":")
        st = state(engine, qid)
        on = bool(st) and not st.get("done") and not st.get("failed")
        return on and (not stage or st["stage"] == stage)
    if kind in ("done", "started", "failed"):
        st = state(engine, rest)
        return bool(st) and (kind == "started" or bool(st.get(kind)))
    if kind == "seen":
        return rest in s["seen"]
    if kind == "posted":
        return rest in s.get("posted", [])
    if kind == "completed":
        return rest in s.get("completed", [])
    if kind == "count":
        m = _COUNT.match(rest)
        if not m:
            raise ValueError(f"Can't read the condition count:{rest!r} (write it like count:boars>=3)")
        name, op, n = m.group(1), m.group(2), int(m.group(3))
        v = s["counters"].get(name, 0)
        return {">=": v >= n, "<=": v <= n, ">": v > n, "<": v < n, "=": v == n, "!=": v != n}[op]
    if kind == "on_hunt":
        return engine.hunt is not None
    if kind == "region":           # region:DANGER/LAND/FEATURE: on a trip to that place
        return engine.hunt is not None and engine.hunt.contract.region.id == rest
    if kind == "word":             # word:ID: on a trip whose place uses that word
        return engine.hunt is not None and rest in engine.hunt.contract.region.place
    if kind == "knows":            # knows:ID: the word is known
        return rest in engine.words
    if kind == "event":
        key, _, value = rest.partition("=")
        return getattr(engine, "story_event", {}).get(key) == value
    if kind == "taken":            # taken:CONTRACT: the Hunter holds that story contract (v0.54.0)
        c = engine.player.contract
        return c is not None and c.story == rest
    if kind == "bounty":           # bounty:ID: the Hunter holds that story bounty
        return any(j.story == rest for j in engine.player.jobs)
    if kind == "bounty_done":      # bounty_done:ID: ...and has done it (not yet paid)
        return any(j.story == rest and j.done for j in engine.player.jobs)
    return None


def apply(engine, kind: str, rest: str) -> bool:
    """A story effect. Returns False if `kind` isn't one."""
    s = engine.story
    if kind == "start":
        start(engine, rest)
    elif kind == "advance":
        advance(engine, rest)
    elif kind == "stage":
        qid, _, stage = rest.partition(":")
        if state(engine, qid):
            advance(engine, qid, stage)
    elif kind == "finish":
        finish(engine, rest)
    elif kind == "fail":
        fail(engine, rest)
    elif kind == "note":
        qid, _, text = rest.partition(":")
        if state(engine, qid):
            state(engine, qid)["log"].append(fill(engine, text))
    elif kind == "count":
        name, _, change = rest.partition(":")
        v = s["counters"].get(name, 0)
        s["counters"][name] = int(change[1:]) if change.startswith("=") else v + int(change or 1)
    elif kind == "scene":
        play(engine, rest)
    elif kind == "hide":
        parts = rest.split(":")
        engine.catalogue[parts[0]]  # fail early on a wrong id
        s["hidden"].append([parts[0], parts[1], int(parts[2]) - 1 if len(parts) > 2 else None])
        if parts[0] not in s["items"]:
            s["items"].append(parts[0])
    elif kind == "message":
        engine.log(fill(engine, rest))
    elif kind == "post":
        post(engine, rest)
    elif kind == "unpost":
        if rest in s.get("posted", []):
            s["posted"].remove(rest)
    elif kind == "only":           # only:contracts:ID, only:bounties:ID, only:clear (v0.54.0)
        board, _, cid = rest.partition(":")
        if board == "clear":
            s["only"] = {}
        else:
            s.setdefault("only", {})[board] = cid
    elif kind == "bounty":         # bounty:ID: post a story bounty on the bounty board
        post_bounty(engine, rest)
    elif kind == "learn":          # learn:WORD[,WORD...]: words for the Wayfinder (game/keywords.py)
        from game import keywords
        keywords.learn(engine, [w.strip() for w in rest.split(",") if w.strip()])
    else:
        return False
    return True


def fill(engine, text: str) -> str:
    from game.dialogue import fill as dialogue_fill
    return dialogue_fill(engine, text)


# ---- Story contracts: key hunts posted on the Guild's contracts board -------------------------------------
def place_of(engine, c: dict):
    return engine.regions["/".join(c["words"])]


def post(engine, cid: str) -> None:
    """Put a story contract up on the Guild's contracts board (once; not again after it's done)."""
    c = engine.story_data.contracts.get(cid)
    if c is None:
        raise ValueError(f"No story contract {cid!r} in data/story")
    s = engine.story
    s.setdefault("posted", [])
    if cid in s["posted"] or cid in s.get("completed", []):
        return
    engine.catalogue[c["prize"]]          # fail early on a wrong id
    s["posted"].append(cid)
    if c.get("story_item", True) and c["prize"] not in s["items"]:   # the prize is a story item: never lost
        s["items"].append(c["prize"])
    place_of(engine, c)                   # fail early on a wrong word
    engine.log(f"{c.get('posted_line', 'A key hunt is posted on the Guild' + chr(39) + 's contracts board')}: "
               f"{fill(engine, c['title'])}.")


STORY_JOB_IDS = 900000     # story bounties' job ids start here (ordinary ones count up from 1)


def post_bounty(engine, bid: str) -> None:
    """Put a story bounty up on the bounty board (once). A kill bounty marks `creature` (or the one the
    board would pick for that place); kept when the board is renewed; rivals leave it alone."""
    b = engine.story_data.bounties.get(bid)
    if b is None:
        raise ValueError(f"No story bounty {bid!r} in data/story")
    s = engine.story
    s.setdefault("bounties", [])
    if any(j.story == bid for j in engine.job_board + engine.player.jobs):
        return                     # already up, or already taken
    from game import work
    place = engine.regions["/".join(b["words"])]
    kind = b.get("kind", "kill")
    want = b.get("creature") or b.get("artifact") or ""
    if kind == "kill" and not want:
        import random
        want = work.bounty_creature(engine, place, random.Random(bid)).id
    jid = STORY_JOB_IDS + len(s["bounties"])     # (a fresh id each time it's posted: after a death it can go up again)
    job = work.Job(jid, kind, place.id, 1, 1, int(b["reward"]), 0, want, story=bid, title=fill(engine, b["title"]))
    engine.job_board.insert(0, job)
    s["bounties"].append(bid)
    engine.log(f"A bounty is posted on the Guild's bounty board: {job.title}.")


def only(engine, board: str) -> str | None:
    """The one story posting a board is limited to right now (only:...), if any."""
    return engine.story.get("only", {}).get(board)


def rank_index(c: dict) -> int:
    from game import ranks
    want = c.get("rank", 0)
    if isinstance(want, int):
        return want
    names = [r["name"].lower() for r in ranks.table()]
    if want.lower() not in names:
        raise ValueError(f"Story contract rank {want!r} isn't a rank in data/ranks.json")
    return names.index(want.lower())


def posted_contracts(engine) -> list:
    """The story contracts on the board today, as contracts you can take."""
    import zlib
    from game.hunt import Contract, depth_of
    out = []
    for cid in engine.story.get("posted", []):
        c = engine.story_data.contracts.get(cid)
        if not c:
            continue
        place = place_of(engine, c)
        danger = place.danger[0]
        out.append(Contract(place, c["prize"], danger, c.get("depth", depth_of(place, danger)),
                            zlib.crc32(f"{cid}:{engine.day}".encode()), "", cid, fill(engine, c["title"]),
                            c.get("guardian", ""), rank_index(c)))
    return out


def contract_over(engine, contract, success: bool) -> list[str]:
    """A story contract's hunt has ended. Done: off the board, its effects, an event. Not: it stays up.
    Returns lines for the end-of-hunt card."""
    cid = contract.story
    c = engine.story_data.contracts.get(cid)
    if c is None:
        return []
    from game.dialogue import apply
    if success:
        s = engine.story
        if cid in s.get("posted", []):
            s["posted"].remove(cid)
        s.setdefault("completed", []).append(cid)
        apply(engine, c.get("on_done"))
        fire(engine, "contract_done", contract=cid)
        return [fill(engine, line) for line in c.get("done_text", [])]
    fire(engine, "contract_failed", contract=cid)
    return []


# ---- Story lines in conversations -----------------------------------------------------------------------------
def talk_choices(engine, folk_id: str) -> list:
    """Extra choices the story gives this person right now."""
    from game.dialogue import all_hold
    out = []
    for t in engine.story_data.talk:
        if t["folk"] != folk_id:
            continue
        if t.get("once", True) and t["id"] in engine.story["seen"]:
            continue
        if all_hold(engine, t.get("if")):
            out.append({"text": t["text"], "story_talk": t["id"]})
    return out


def talk_entry(engine, tid: str) -> dict:
    return next(t for t in engine.story_data.talk if t["id"] == tid)
