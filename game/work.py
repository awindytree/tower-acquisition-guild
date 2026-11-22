"""Ways to earn beyond contracts: the Guild's bounties and scouting, and requests from the city.

The bounty board (in the guild hall; also through the clerk; user, 2026-11-19): bounties (kill a
particular marked creature, or find a particular artifact) and scouting, each at a place.
  cull:  kill N creatures of at least tier T at a place (three keywords, game/keywords.py)
  scout: reach area K of a place
The board is world state (refreshed every Cycle); the jobs a Hunter takes are
theirs (lost if they die). Up to MAX_JOBS at once. Pay is collected from the
clerk; the Guild takes no dues from it. Holding a job opens its gate even
without a contract (and even while dues are owed): an odd-job outing.

Requests (on the plaza notice board): a townsperson wants a thing and pays
well for it. Either a specific kind of broken artifact (the Hunter must have
identified it to hand it over) or any broken artifact of a given rarity.
Hand it over by talking to them. Requests are world state: they stay up until
filled or until they expire, whoever the Hunter is.

All wording, amounts and rewards are PLACEHOLDERS (data/work.json).
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_JOBS = 2


@dataclass
class Job:
    id: int
    kind: str            # "kill" (a bounty on one marked creature), "find" (a bounty on an artifact),
                         # "scout" (reach an area), or "cull" (older saves: kill N of a tier)
    region: str          # the place (three keywords, game/keywords.py)
    target: int          # creatures to kill, the area number to reach; 1 for bounties
    tier: int = 1        # cull: the weakest kind that counts
    reward: int = 0
    progress: int = 0
    want: str = ""       # kill: the creature id; find: the artifact id
    story: str = ""      # a story bounty (data/story "bounties", v0.54.0): its id
    title: str = ""      # ...and its title on the board

    @property
    def done(self) -> bool:
        return self.progress >= self.target

    def describe(self, regions, catalogue=None, monster_types=None) -> str:
        r = regions[self.region]
        if self.kind == "kill":
            what = monster_types[self.want].name if monster_types and self.want in monster_types else self.want.replace("_", " ")
            return f"Bounty: the marked {what} at {r.name}"
        if self.kind == "find":
            what = catalogue[self.want].real_name if catalogue is not None and self.want in catalogue.types else self.want.replace("_", " ")
            return f"Bounty: a {what}, at {r.name}"
        if self.kind == "cull":
            what = "creatures" if self.tier <= 1 else f"tier {self.tier}+ creatures"
            return f"Cull {self.target} {what} in {r.name}"
        return f"Scout {r.name} as far as area {self.target}"

    def text(self, engine) -> str:
        return self.describe(engine.regions, engine.catalogue, engine.monster_types)

    def label(self, engine) -> str:
        """Short, for a board's list (the place is in the details)."""
        if self.title:
            return "☼ " + self.title
        if self.kind == "kill":
            return f"Bounty: the marked {engine.monster_types[self.want].name}" if self.want in engine.monster_types else "Bounty"
        if self.kind == "find":
            return f"Bounty: a {engine.catalogue[self.want].real_name}" if self.want in engine.catalogue.types else "Bounty"
        if self.kind == "scout":
            return f"Scout as far as area {self.target}"
        return self.short()

    def short(self) -> str:
        """Without the place."""
        if self.kind == "kill":
            return f"Kill the marked {self.want.replace('_', ' ')}"
        if self.kind == "find":
            return f"Find a {self.want.replace('_', ' ')}"
        if self.kind == "cull":
            what = "creatures" if self.tier <= 1 else f"tier {self.tier}+ creatures"
            return f"Cull {self.target} {what}"
        return f"Scout as far as area {self.target}"

    def status(self) -> str:
        if self.done:
            if self.kind == "find":
                return "found: bring it to the clerk to be paid"
            return "done: collect your pay from the clerk"
        if self.kind == "kill":
            return "it lies deepest in, marked; not yet killed"
        if self.kind == "find":
            return "somewhere in the deepest area; not yet found"
        if self.kind == "cull":
            return f"{self.progress}/{self.target} killed"
        return f"furthest: area {self.progress} of {self.target}"


@dataclass
class Request:
    id: int
    folk_id: str
    kind: str            # "item" (a specific kind), "rarity" (any broken artifact of a rarity), "material",
                         # or "errand" (a particular artifact lying at a place: v0.47.0)
    want: str            # item id, or rarity id
    reward: int
    expires: int         # the last day it stands
    count: int = 1       # how many (materials)
    place: str = ""      # errand: the place (three keywords) where it lies
    where: str = ""      # errand: the place as shown, [..][..][..]

    def thing(self, catalogue) -> str:
        if self.kind == "errand":
            return f"the {catalogue[self.want].real_name} lying at {self.where}"
        if self.kind == "item":
            return f"a {catalogue[self.want].real_name}"
        if self.kind == "material":
            return f"{self.count} {catalogue[self.want].real_name}"
        return f"any {catalogue.rarities[self.want].name} Tower Artifact (broken)"

    def matches(self, item) -> bool:
        t = item.type
        if self.kind == "errand":          # they know what they sent you for: no identifying needed
            return t.id == self.want
        if self.kind in ("item", "material"):
            return t.id == self.want and t.identified  # you have to know what it is
        return (t.is_broken_artifact and t.rarity is not None and t.rarity.id == self.want
                and not t.properties.get("locked"))     # (Chapter 1's Unique isn't anyone's to have)


def load_settings(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---- Generating ------------------------------------------------------------------------------
def make_jobs(engine, rng: random.Random) -> list[Job]:
    """The bounty board (user, 2026-11-19): bounties (kill a particular, marked creature, or find
    a particular artifact) and scouting (reach an area of a place). At places of every danger;
    rank decides which a Hunter may take."""
    s = engine.work
    jobs = []
    kw = engine.regions.keywords
    weights = {int(d): w for d, w in s.get("danger_weights", {"1": 4, "2": 3, "3": 2, "4": 1.5, "5": 1}).items()}
    for _ in range(s["jobs_on_board"]):
        engine.next_work_id += 1
        danger = rng.choices(list(weights), weights=list(weights.values()))[0]
        from game.keywords import random_place
        region = random_place(engine, danger, rng)
        danger = region.danger[0]
        roll = rng.random()
        if roll < s["kill_chance"]:
            mtype = bounty_creature(engine, region, rng)
            if mtype is not None:
                reward = round((s["kill_base"] + s["kill_per_tier"] * mtype.tier + s["per_danger"] * danger) * s.get("bounty_pay", 1.0))   # (balance pass 3: × 0.6)
                jobs.append(Job(engine.next_work_id, "kill", region.id, 1, mtype.tier, reward, 0, mtype.id))
                continue
        if roll < s["kill_chance"] + s["find_chance"] or (region.depth or 5) < 2:   # (one area: nothing to scout)
            from game.hunt import pick_artifact
            art = engine.catalogue[pick_artifact(region, danger, engine.catalogue, rng)]
            reward = round((int(art.rarity.broken_price * s["find_reward"]) + s["per_danger"] * danger) * s.get("bounty_pay", 1.0))   # (balance pass 3: × 0.6)
            jobs.append(Job(engine.next_work_id, "find", region.id, 1, 1, reward, 0, art.id))
            continue
        area = rng.randint(2, max(2, region.depth or 5))
        reward = round((s["scout_base"] + area * s["scout_per_area"] + s["per_danger"] * danger) * s.get("bounty_pay", 1.0))   # (balance pass 3: × 0.6)
        jobs.append(Job(engine.next_work_id, "scout", region.id, area, 1, reward))
    return jobs


def bounty_creature(engine, region, rng: random.Random):
    """A creature for a kill bounty: the toughest kind the place's deepest area allows, from its
    land (or its favoured creature)."""
    from game.monsters import tier_cap
    depth = region.depth or 3
    cap = tier_cap(region.danger[0], depth - 1)
    pool = [t for t in engine.monster_types.values()
            if (t.lives(region.style_for(depth - 1), region.light) or t.id == region.favour) and t.tier <= cap
            and t.behaviour != "still" and not t.ghost]
    if not pool:
        return None
    top = max(t.tier for t in pool)
    return rng.choice(sorted((t for t in pool if t.tier == top), key=lambda t: t.id))


def bounties_for(engine, region) -> list:
    """What waits for the Hunter at this place: bounties taken, and errands posted on the notice
    board: [[id, kind, want], ...] (an errand's item is placed like a find bounty's)."""
    out = [[j.id, j.kind, j.want] for j in engine.player.jobs
           if j.region == region.id and j.kind in ("kill", "find") and not j.done]
    out += [[r.id, "errand", r.want] for r in engine.requests if r.kind == "errand" and r.place == region.id]
    return out


def reveal(engine, requests) -> None:
    """Hearing of an errand teaches the place's words (user, 2026-11-19)."""
    from game import keywords
    for r in requests:
        if r.kind == "errand" and r.place in engine.regions:
            keywords.learn(engine, list(engine.regions[r.place].place))


def make_requests(engine, rng: random.Random, count: int) -> list[Request]:
    """New requests: each from someone without one up already, never for something already asked for."""
    s = engine.work
    cat = engine.catalogue
    asking = {r.folk_id for r in engine.requests}
    wanted = {(r.kind, r.want) for r in engine.requests}
    who = [f for f in s["requesters"] if f in engine.townsfolk and f not in asking]  # one request each
    out = []
    for _ in range(count):
        if not who:
            break
        engine.next_work_id += 1
        folk = who.pop(rng.randrange(len(who)))
        expires = engine.day + s["request_days"]
        if rng.random() < s.get("errand_chance", 0):
            # an errand: something lying at a place (user: hearing of it teaches the place's words)
            from game.keywords import random_place
            from game.hunt import pick_artifact
            danger = rng.choice(s.get("errand_dangers", [1, 2]))
            place = random_place(engine, danger, rng)
            want = pick_artifact(place, danger, cat, rng)
            if ("errand", want) not in wanted:
                reward = int(cat[want].rarity.broken_price * s.get("errand_reward", 4)) + s["per_danger"] * danger
                wanted.add(("errand", want))
                out.append(Request(engine.next_work_id, folk, "errand", want, reward, expires, 1, place.id, place.name))
                continue
        counts = {m: c for m, c in s.get("material_counts", {}).items()
                  if m in cat.types and ("material", m) not in wanted}
        if counts and rng.random() < s.get("material_chance", 0):
            want = rng.choice(sorted(counts))
            n = rng.randint(*counts[want])
            wanted.add(("material", want))
            reward = round(cat[want].value * n * s.get("material_reward", 1.5))
            out.append(Request(engine.next_work_id, folk, "material", want, reward, expires, n))
            continue
        rarity = rng.choices(list(s["request_rarities"]), weights=list(s["request_rarities"].values()))[0]
        kinds = sorted(t.id for t in cat.artifacts() if t.rarity.id == rarity and ("item", t.id) not in wanted
                       and not t.properties.get("locked"))
        if kinds and (rng.random() < s["specific_chance"] or ("rarity", rarity) in wanted):
            want = rng.choice(kinds)
            wanted.add(("item", want))
            reward = int(cat[want].value * s["specific_reward"])
            out.append(Request(engine.next_work_id, folk, "item", want, reward, expires))
        elif ("rarity", rarity) not in wanted:
            r = cat.rarities[rarity]
            reward = int(r.broken_price * s["rarity_reward"])
            wanted.add(("rarity", rarity))
            out.append(Request(engine.next_work_id, folk, "rarity", rarity, reward, expires))
    return out


def refresh(engine) -> None:
    """Called as days pass: a new job board every Cycle; requests expire and new ones go up."""
    s = engine.work
    rng = random.Random(engine.day * 7919 + 17)
    if engine.day - engine.jobs_posted >= s["board_every"]:
        engine.jobs_posted = engine.day
        engine.job_board = [j for j in engine.job_board if j.story] + make_jobs(engine, rng)   # story bounties stay
    before = len(engine.requests)
    engine.requests = [r for r in engine.requests if r.expires >= engine.day]
    if len(engine.requests) < before:
        engine.log("A request on the plaza notice board has been taken down.")
    if engine.day - engine.requests_posted >= s["board_every"]:
        engine.requests_posted = engine.day
        new = make_requests(engine, rng, max(0, s["requests_open"] - len(engine.requests)))
        engine.requests += new
        if new:
            engine.log("New requests are up on the plaza notice board.")


# ---- Progress ----------------------------------------------------------------------------------
def on_kill(engine, monster) -> None:
    if engine.hunt is None:
        return
    region = engine.hunt.contract.region.id
    mark = getattr(monster, "bounty", 0)
    for job in engine.player.jobs:
        if job.kind == "kill" and mark and job.id == mark and not job.done:
            job.progress = 1
            engine.log(f"Bounty done: you've killed the marked {monster.type.name}. "
                       "Collect the bounty from the clerk.")
            bounty_card(engine, f"You've killed the marked {monster.type.name}.")
    for job in engine.player.jobs:
        if job.kind == "cull" and job.region == region and not job.done and monster.type.tier >= job.tier:
            job.progress += 1
            if job.done:
                engine.log(f"Job done: {job.text(engine)}. Collect your pay from the clerk.")


def on_pickup(engine, item_id: str) -> None:
    """Picking up the artifact a find bounty asks for (anywhere: the Guild wants one of that kind)."""
    for job in engine.player.jobs:
        if job.kind == "find" and job.want == item_id and not job.done:
            job.progress = 1
            engine.log(f"That's the {engine.catalogue[item_id].real_name} the bounty asks for. "
                       "Bring it to the clerk.")
            bounty_card(engine, f"You've found the {engine.catalogue[item_id].real_name} the bounty asks for.")


def bounty_card(engine, what: str) -> None:
    """A little fanfare when a bounty's target is killed or found (v0.52.0, user)."""
    if engine.hunt is None or engine.screen is not None:
        return
    from game.screens import TitleCardScreen, TEXT, DIM
    engine.screen = TitleCardScreen("Bounty done", [
        (what, TEXT), ("", TEXT),
        ("Get back to the trail home safely, then see the clerk to be paid.", DIM)])


def on_area(engine, index: int) -> None:
    if engine.hunt is None:
        return
    region = engine.hunt.contract.region.id
    for job in engine.player.jobs:
        if job.kind == "scout" and job.region == region and not job.done and index + 1 > job.progress:
            job.progress = index + 1
            if job.done:
                engine.log(f"Job done: {job.text(engine)}. Collect your pay from the clerk.")


# ---- Taking, paying, handing over ------------------------------------------------------------
def take_job(engine, job: Job) -> tuple[bool, str]:
    p = engine.player
    from game import story
    held = story.only(engine, "bounties")
    if held and job.story != held:
        return False, "The clerk asked you to take the one marked for you first."
    if len(p.jobs) >= MAX_JOBS:
        return False, f"You can hold {MAX_JOBS} at once. Finish or drop one first."
    from game import ranks
    danger = engine.regions[job.region].danger[0]
    if danger > ranks.max_danger(p.rank):
        return False, f"That's posted for {ranks.name(ranks.lowest_rank_for_danger(danger))}s and above."
    engine.job_board.remove(job)
    p.jobs.append(job)
    from game import keywords
    keywords.learn(engine, list(engine.regions[job.region].place), say=False)
    return True, f"You take it: {job.text(engine)}. Pay: {job.reward} shards."


def drop_job(engine, job: Job) -> str:
    engine.player.jobs.remove(job)
    return f"You drop it: {job.text(engine)}."


def collect(engine) -> str:
    """Pay for every finished job (from the clerk). The Guild pays for odd jobs, and takes no
    dues from that pay (user, 2026-11-18): it doesn't count as earnings."""
    p = engine.player
    missing = []
    for j in p.jobs:      # a find bounty is paid for the artifact itself: hand it over
        if j.kind == "find" and j.done:
            if p.inventory.count_of(j.want):
                inv = p.inventory
                inv.remove(next(i for i, it in enumerate(inv.items) if it.type.id == j.want), 1)
            else:
                j.progress = 0
                missing.append(engine.catalogue[j.want].real_name)
    done = [j for j in p.jobs if j.done]
    if not done:
        if missing:
            return f"The clerk wants the {missing[0]} itself, and you don't have it with you."
        return "You have no finished jobs to be paid for."
    from game import talents                      # (Guild Favourite)
    total = round(sum(j.reward for j in done) * (1 + talents.total(p, "bounty_pay") / 100))
    p.jobs = [j for j in p.jobs if not j.done]
    p.guild_pay(total)
    from game import sound
    sound.play("pay")
    from game import story
    for j in done:
        if j.story:
            story.fire(engine, "bounty_paid", bounty=j.story)
    return f"The clerk pays you {total} shards for {len(done)} job{'s' if len(done) > 1 else ''}."


def requests_for(engine, folk_id: str) -> list[Request]:
    return [r for r in engine.requests if r.folk_id == folk_id]


def can_hand_over(engine, request: Request) -> int | None:
    """The inventory index of something that fills the request, if the Hunter has it."""
    inv = engine.player.inventory
    if request.kind == "material" and inv.count_of(request.want) < request.count:
        return None
    for i, item in enumerate(inv.items):
        if request.matches(item):
            return i
    return None


def hand_over(engine, request: Request) -> str:
    inv = engine.player.inventory
    i = can_hand_over(engine, request)
    item = inv.items[i]
    name = item.type.name
    left = request.count
    while left > 0:  # a stack, or several if a stack ever got split
        i = next(j for j, it in enumerate(inv.items) if request.matches(it))
        left -= inv.remove(i, left).count
    from game import ranks
    from game import talents                      # (Well Liked)
    bonus = round(request.reward * (ranks.privilege(engine.player, "request_bonus", 0)
                                    + talents.total(engine.player, "request_pay") / 100))
    engine.player.earn(request.reward + bonus)
    engine.requests.remove(request)
    if request.kind == "material":
        name = f"{request.count} {name}"
    extra = f" (and {bonus} more, for your rank)" if bonus else ""
    return f"You hand over the {name} and are paid {request.reward} shards{extra}."


# ---- Saving ----------------------------------------------------------------------------------------
def jobs_to_list(jobs) -> list:
    return [asdict(j) for j in jobs]


def jobs_from_list(data) -> list[Job]:
    return [Job(**d) for d in data]


def requests_to_list(requests) -> list:
    return [asdict(r) for r in requests]


def requests_from_list(data) -> list[Request]:
    return [Request(**d) for d in data]
