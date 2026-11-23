"""The story skeleton: quests, story flags and counters, scenes on events, story lines in
conversations, and story items hidden in hunts. All of it is written in data/story/*.json
(see data/story/_README.md); nothing story-specific lives in code.

Progress is world state by default (the story goes on when a Hunter dies, as the city
does); a quest can be marked "scope": "hunter" to belong to one Hunter instead.

Kinds of story (v0.66.0, user; design: claude/design-story-presentation.md): a quest can be a
"chapter" (the main story), "paralogue" (a storylet), "log" (a Character Log: a person's story),
"hunter_log" or "calling" (a Hunter's own: these default to scope hunter). Each has a heading,
"Chapter 1: Well Past Due", shown on a title card when it begins and ends. Any text can be
{"variants": [...]}: the game picks one this world hasn't used yet, and a variant can have
conditions. Date conditions (date:...) are refused where they'd hold a story step back for longer
than a Cycle. A new Hunter gets "The Story So Far" (chapters' recaps).

Conditions and effects are shared with conversations (game/dialogue.py), so a dialogue
choice can start a quest and a scene can check a flag. The story adds:
  conditions: quest:Q (active)  quest:Q:STAGE  done:Q  started:Q  failed:Q  seen:SCENE
              count:NAME>=N (also > < <= = !=)  on_hunt  region:PLACE  word:ID  knows:ID  event:KEY=VALUE (scenes)
              (v0.66.0) date:turning_pulse  date:holiday  date:duel=light|dark  date:pulse=NAME  date:cycle=N
              date:reckon=N  date:judgment=N; calling:NAME  gender:NAME  sensitive  age>=N (Judgments)
              hall>=N (Hunters remembered)  fallen:CALLING (a Hunter of that calling has died)
  effects:    start:Q  advance:Q  stage:Q:STAGE  finish:Q  fail:Q  note:Q:TEXT
              count:NAME:+N / -N / =N  scene:SCENE  hide:ITEM:REGION[:AREA]  message:TEXT
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "story"
EVENTS = ("new_game", "new_hunter", "set_out", "area", "kill", "pickup", "home", "pulse", "retire", "death",
          "contract_done", "contract_failed",
          "talk", "wayfinder", "see", "bounty_paid", "load",   # v0.67.0: load (a save was loaded)
          "lost_ground",   # v0.87.0: arriving at a Lost Ground (ground=ID, first=True/False)
          "manual")   # "manual": never fired; played only by a scene:ID effect   # v0.54.0: talk (folk=ID), see (monster=ID, marked)


# ---- Kinds of story (v0.66.0) ------------------------------------------------------------------------------
KINDS = {   # kind -> (heading, order in the quest log, scope by default)
    "chapter": ("Chapter {number}: {title}", 1, "world"),
    "paralogue": ("Paralogue {number}: {title}", 2, "world"),
    "log": ("Character Log {number}: {title}", 3, "world"),
    "calling": ("{calling} Calling: {title}", 4, "hunter"),
    "hunter_log": ("Hunter Log {number}: {title}", 5, "hunter"),
    "quest": ("{title}", 6, "world"),
}
# Dates that come round less often than once a Cycle: never allowed to hold a story step back (user).
RARE_DATES = ("date:turning_pulse", "date:turning_day", "date:holiday", "date:duel=", "date:cycle=", "date:reckon=", "date:judgment=")
MOVES = ("advance:", "stage:", "finish:", "fail:", "post:", "bounty:")


def heading(q: dict) -> str:
    kind = q.get("kind", "quest")
    fmt = KINDS.get(kind, KINDS["quest"])[0]
    if kind == "calling" and not q.get("calling"):
        fmt = "Calling: {title}"
    return fmt.format(number=q.get("number", "?"), title=q.get("title", ""), calling=q.get("calling", ""))


def _rare(conds) -> list:
    return [c for c in conds or [] if isinstance(c, str) and c.lstrip("!").startswith(RARE_DATES)]


def check_dates(where: str, conds, effects=None) -> None:
    """The user's calendar rule: a date may start or colour a story, but never hold a step back for
    longer than a Cycle. A stage's `until`, or a scene or talk line that moves a quest on, may not
    wait on a rarer date."""
    rare = _rare(conds)
    if rare and (effects is None or any(isinstance(e, str) and e.startswith(MOVES) for e in effects)):
        raise ValueError(f"{where}: {rare[0]!r} comes round less than once a Cycle, so it can't hold a story "
                         "step back (it may start a quest or add colour; see data/story/_README.md)")


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
                kind = q.get("kind", "quest")
                if kind not in KINDS:
                    raise ValueError(f"{path.name}: quest {qid!r}: kind must be one of {tuple(KINDS)}")
                if kind not in ("quest", "calling") and "number" not in q:
                    raise ValueError(f"{path.name}: quest {qid!r}: a {kind} needs a number")
                q.setdefault("scope", KINDS[kind][2])
                for st in stages:
                    check_dates(f"{path.name}: quest {qid!r}, stage {st['id']!r} (until)", st.get("until"))
                self.quests[qid] = q
            for sid, sc in raw.get("scenes", {}).items():
                if sc.get("on") == "day":          # the old name (v0.93.0: the Overland says Pulse)
                    sc["on"] = "pulse"
                if sc.get("on") not in EVENTS:
                    raise ValueError(f"{path.name}: scene {sid!r}: 'on' must be one of {EVENTS}")
                check_dates(f"{path.name}: scene {sid!r}", sc.get("if"), sc.get("do") or [])
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
                check_dates(f"{path.name}: talk {t['id']!r}", t.get("if"), t.get("do") or [])
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
    if q.get("kind", "quest") == "quest":
        engine.log(f"New quest: {q['title']}.")
    else:
        engine.log(f"{heading(q)} begins.")
        if q.get("cards", True):
            card(engine, heading_parts(q), [(fill(engine, q.get("title", "")), "accent"), ("", "text"),
                                            (text(engine, f"quest:{qid}:intro", q.get("intro", "")), "text")])
    _enter(engine, qid, first)


def _enter(engine, qid: str, stage_id: str) -> None:
    st = state(engine, qid)
    st["stage"] = stage_id
    sd = stage_def(engine, qid, stage_id)
    if sd.get("log"):
        st["log"].append(text(engine, f"quest:{qid}:{stage_id}:log", sd["log"]))
    # the goal's variant is chosen now; it's filled in when shown (counts in it stay current)
    st["goal"] = text(engine, f"quest:{qid}:{stage_id}:goal", sd["goal"], filled=False) if sd.get("goal") else ""
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
        st["log"].append(text(engine, f"quest:{qid}:done_log", q["done_log"]))
    if q.get("kind", "quest") == "quest":
        engine.log(f"Quest complete: {q['title']}.")
    else:
        engine.log(f"{heading(q)}: complete.")
        if q.get("cards", True):
            card(engine, heading_parts(q), [(fill(engine, q.get("title", "")), "accent"), ("", "text"),
                                            (text(engine, f"quest:{qid}:outro", q.get("outro", "")), "text"),
                                            ("", "text"), ("Complete", "dim")])
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
    event = "pulse" if event == "day" else event     # the old name (v0.93.0)
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
    """A scene: its effects now; its pages (if any) on screen as soon as nothing else is. Its pages are queued
    before its effects run, so whatever those bring (a chapter's card, a tip) comes after them (v0.67.0)."""
    from game.dialogue import apply
    sc = engine.story_data.scenes[sid]
    if sid not in engine.story["seen"]:
        engine.story["seen"].append(sid)
    if sc.get("pages"):
        engine.scene_queue.append(sid)
    apply(engine, sc.get("do"))


def show_next_scene(engine) -> None:
    if engine.screen is not None:
        return
    if engine.scene_queue:
        from game.screens import SceneScreen, TitleCardScreen
        nxt = engine.scene_queue.pop(0)
        if isinstance(nxt, tuple):            # a title card (v0.66.0): ("card", heading, lines)
            _, head, lines = nxt
            from game.screens import TEXT, DIM, ACCENT
            colours = {"text": TEXT, "dim": DIM, "accent": ACCENT}
            engine.screen = TitleCardScreen(head, [(t, colours.get(c, TEXT)) for t, c in lines])
        else:
            engine.screen = SceneScreen(nxt)
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
    if kind == "visited":          # visited:ID: anyone has been to that Lost Ground (v0.87.0)
        return rest in s.get("grounds", {})
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
    # ---- v0.66.0: the calendar, and the Hunter (for variant lines and Hunters' own stories) ----
    if kind == "date":
        return date_holds(engine, rest)
    p = engine.player
    if kind == "calling":
        from game.names import calling
        return calling(p).lower() == rest.lower()
    if kind == "gender":
        return getattr(p, "gender", "") == rest
    if kind == "sensitive":
        return "jodebris_sensitive" in p.flags
    if kind == "fallen":           # fallen:CALLING: a Hunter of that calling has died (the Hall remembers)
        return any(e.get("cause", "") not in ("retired", "") and f" {rest.lower()} " in f" {e['name'].lower()} "
                   for e in engine.hall)
    m = _COUNT.match(kind)         # age>=N (the Hunter's age in Judgments), hall>=N (Hunters remembered)
    if m and m.group(1) in ("age", "hall"):
        from game import aging
        if m.group(1) == "age":
            turns, judgments = aging.split(engine.day - p.born)
            v = turns * aging.judgments_per_turn() + judgments
        else:
            v = len(engine.hall)
        n = int(m.group(3))
        return {">=": v >= n, "<=": v <= n, ">": v > n, "<": v < n, "=": v == n, "!=": v != n}[m.group(2)]
    return None


def date_holds(engine, rest: str) -> bool:
    """date:turning_pulse (the first Pulse of a Turn; the old date:turning_day still works), date:holiday (the holiday Pulses after a Duel),
    date:duel=light|dark, date:pulse=NAME, date:cycle=N, date:reckon=N, date:judgment=N."""
    d = engine.date
    if rest in ("turning_pulse", "turning_day"):
        return (d.intercalary == 0 and d.duel.lower().startswith("light") and d.judgment == 1 and d.reckon == 1
                and d.cycle == 1 and d.pulse_number == 1)
    if rest == "holiday":
        return d.intercalary > 0
    key, _, value = rest.partition("=")
    if key == "duel":
        return d.duel.lower().startswith(value.lower())
    if key == "pulse":
        return d.intercalary == 0 and d.pulse.lower() == value.lower()
    if key in ("cycle", "reckon", "judgment"):
        return d.intercalary == 0 and getattr(d, key) == int(value)
    raise ValueError(f"Can't read the condition date:{rest!r}")


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
    # ---- v0.67.0 (Chapter 1) ----
    elif kind == "card":           # card:HEADING|LINE|LINE...: a title card (an act's name, say)
        head, *lines = rest.split("|")
        card(engine, head, [(fill(engine, l), "accent" if i == 0 else "text") for i, l in enumerate(lines)])
    elif kind == "appear":         # appear:FOLK: a story person takes their place in the guild hall, for good
        s.setdefault("folk", [])
        if rest not in s["folk"]:
            s["folk"].append(rest)
        place_folk(engine)
    elif kind == "remember":       # remember:FOLK[:CAUSE]: a story person goes into the Hall of Hunters ("hall" opens it)
        _remember(engine, *rest.split(":", 1))
    elif kind == "to_stash":       # to_stash:ITEM: from the Hunter's pack into the guild stash
        _to_stash(engine, rest)
    elif kind == "fund":           # fund:PROJECT:N: N shards toward one of the Guild's works ("works" opens them)
        from game import works
        pid, _, n = rest.partition(":")
        for line in works.give(engine, pid, int(n), works.DUES):
            engine.log(line)
    elif kind == "shelve":         # shelve:WRITING: the Academy library has it (to be read there)
        if rest not in engine.library:
            engine.catalogue[rest]
            engine.library.append(rest)
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
                            c.get("guardian", ""), rank_index(c), False, c.get("prize_folk", ""),
                            int(c.get("guardians", 1))))
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



# ---- Title cards, headings, variants, the story so far (v0.66.0) -------------------------------------------
def heading_parts(q: dict) -> str:
    """The card's big heading: the heading without the title for numbered kinds ("Chapter 1"),
    with the title below it; for others the title itself."""
    h = heading(q)
    return h.split(": ", 1)[0] if ": " in h else h


def card(engine, head: str, lines: list) -> None:
    """Queue a title card: shown once nothing else is on screen, in turn with scenes."""
    out = [(t, c) for t, c in lines if t is not None]
    while out and not out[-1][0]:            # (no trailing blank lines, e.g. a quest with no intro)
        out.pop()
    engine.scene_queue.append(("card", head, out))


def _variant_options(engine, value) -> list:
    from game.dialogue import all_hold
    out = []
    for i, v in enumerate(value["variants"]):
        if isinstance(v, str):
            out.append((i, v))
        elif all_hold(engine, v.get("if")):
            out.append((i, v["text"]))
    return out


def text(engine, key: str, value, filled: bool = True) -> str:
    """Text from the story files, filled in. {"variants": [...]} (a string, or {"text", "if"}): one
    this world hasn't used for `key` yet whose conditions hold; once all have been used they come
    round again. A plain list picks at random (as conversations always have)."""
    import random
    if isinstance(value, dict) and "variants" in value:
        options = _variant_options(engine, value) or [(0, value["variants"][0] if isinstance(value["variants"][0], str)
                                                       else value["variants"][0]["text"])]
        used = engine.story.setdefault("variants", {}).setdefault(key, [])
        fresh = [o for o in options if o[0] not in used] or options
        if len(fresh) == len(options) and used and all(o[0] in used for o in options):
            used.clear()
        i, chosen = random.choice(fresh)
        if i not in used:
            used.append(i)
    elif isinstance(value, list):
        chosen = random.choice(value) if value else ""
    else:
        chosen = value or ""
    return fill(engine, chosen) if filled else chosen


def recap(engine) -> list[str]:
    """The story so far: each finished chapter's recap, then the current chapter's stage recap."""
    out = []
    chapters = sorted((q.get("number", 0), qid) for qid, q in engine.story_data.quests.items()
                      if q.get("kind") == "chapter")
    for _, qid in chapters:
        q, st = engine.story_data.quests[qid], state(engine, qid)
        if not st:
            continue
        if st.get("done"):
            if q.get("recap"):
                out.append(text(engine, f"quest:{qid}:recap", q["recap"]))
        elif not st.get("failed"):
            sd = stage_def(engine, qid, st["stage"])
            line = sd.get("recap") or q.get("recap_now")
            if line:
                out.append(text(engine, f"quest:{qid}:{st['stage']}:recap", line))
    return out


def story_so_far(engine) -> None:
    """For a new Hunter (not a new game): a card telling where the world's story stands."""
    lines = recap(engine)
    if lines:
        body = []
        for line in lines:
            body += [(line, "text"), ("", "text")]
        card(engine, "The Story So Far", body[:-1])



# ---- Key hunts whose words must be found (v0.67.0, Chapter 1) --------------------------------------------------
def hidden_words(engine, c) -> bool:
    """A story contract posted with "hidden_words": its words aren't given; they have to be learned."""
    return bool(getattr(c, "story", "")) and bool(engine.story_data.contracts.get(c.story, {}).get("hidden_words"))


def words_shown(engine, c) -> str:
    """The contract's words as the Hunter knows them: [?] for any not yet learned (hidden-word key hunts)."""
    if not hidden_words(engine, c):
        return c.region.name
    kw = engine.regions.keywords
    return "".join(kw.word(w).shown if w in engine.words else "[?]" for w in c.region.place)



# ---- Story people, the Hall, the stash (v0.67.0) ---------------------------------------------------------------
def place_folk(engine) -> None:
    """Put the story's people in the guild hall (townsfolk.json "hall_spot": [dx, dy] from the hall's
    corner, or the nearest free floor to it). Called after any change and whenever the hall is rebuilt."""
    from game import works
    city = engine.city
    if city is None or city.hall is None or not engine.townsfolk:
        return
    hx, hy = city.hall
    for fid in engine.story.get("folk", []):
        folk = engine.townsfolk.get(fid)
        if folk is None or any(n.folk_id == fid for n in city.npcs):
            continue
        dx, dy = (folk.extra or {}).get("hall_spot", [9, 5])
        want = (hx + dx, hy + dy)
        free = [(x, y) for x in range(hx, hx + 20) for y in range(hy, hy + 11)
                if city.in_bounds(x, y) and city.is_walkable(x, y) and not city.npc_at(x, y)
                and city.tile_at(x, y).symbol not in "HG<>"]
        if not free:
            continue
        x, y = min(free, key=lambda c: (abs(c[0] - want[0]) + abs(c[1] - want[1]), c))
        works.place_person(engine, fid, x, y)


def _remember(engine, fid: str, cause: str = "retired") -> None:
    """A story person into the Hall of Hunters, from townsfolk.json "hall"."""
    from game import aging
    folk = engine.townsfolk.get(fid)
    if folk is None or any(e.get("name") == folk.full_name for e in engine.hall):
        return
    h = (folk.extra or {}).get("hall", {})
    c = aging.calendar()
    age = h.get("age_turns", 2) * c.per_turn + h.get("age_judgments", 0) * c.per_judgment
    from game import ranks
    engine.hall.append({"name": folk.full_name, "rank": h.get("rank", ranks.name(min(3, len(ranks.table()) - 1))),
                        "age": age, "level": h.get("level", 1), "hunts": h.get("hunts", 0),
                        "joined": engine.day - h.get("served_judgments", 0) * c.per_judgment, "ended": engine.day, "cause": cause})


def _to_stash(engine, item_id: str) -> None:
    p = engine.player
    for i in reversed(range(len(p.inventory.items))):
        it = p.inventory.items[i]
        if it.type.id == item_id:
            if p.is_equipped(it):
                continue
            item = p.inventory.remove(i, it.count)
            if engine.stash.add(item):
                engine.log(f"The {item.type.name} goes into the guild stash.")
            else:
                p.inventory.add(item)
            return
