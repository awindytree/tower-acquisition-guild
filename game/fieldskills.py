"""Field skills (v0.56.0; design: claude/design-progression.md, stage 2): what makes a Hunter good
at hunting rather than just fighting. All numbers are placeholders.

- Tracking (Acumen): creatures leave tracks you can see (longer-lasting with rank); rank 2, you
  sense roughly how many creatures an area holds when you enter it (the number itself at 4);
  rank 3, a marked bounty shows on the minimap in its area; rank 4+, creatures near you show on
  the minimap unseen. Practice: entering an area for the first time on a hunt; kills.
- Stealth (Celerity): a creature that sees you notices you only by chance (always at rank 1, less
  each rank); a blow at a creature that hasn't noticed you gets +2 accuracy and +1 damage per two
  ranks. Practice: a creature failing to notice you (once each), a blow struck unnoticed.
- Harvesting (Physicality): creatures leave materials more often (+5% a rank above 1), and one more
  of each at rank 5 (balance pass 3; was ranks 3 and 5). Practice: each material a kill leaves.
- Survival (Fortitude): a shorter rest after hunts (-10% a rank above 1), rations mend for longer,
  torches burn longer, and from rank 4 bleeding and poison last half as long. Practice: coming
  home from a hunt, eating a ration, lighting a torch.
"""
from __future__ import annotations

FIELD_SKILLS = ("tracking", "stealth", "harvesting", "survival")
TRACK_TURNS = 10            # how long tracks last at rank 1; +10 a rank
SENSE_RANK, SENSE_EXACT_RANK, BOUNTY_RANK, NEAR_RANK = 2, 4, 3, 4
NEAR_RADIUS = 6             # at rank 4; +2 a rank after
NOTICE_STEP, NOTICE_FLOOR = 0.12, 0.25
SNEAK_ACCURACY = 2


def rank(engine_or_player, skill: str) -> int:
    p = getattr(engine_or_player, "player", engine_or_player)
    try:
        return p.skill(skill).rank
    except KeyError:
        return 1


def practise(engine, skill: str, times: int = 1) -> None:
    from game import skills
    if skill not in engine.skills:
        return
    sk = engine.skills[skill]
    for msg in skills.add_practice(sk, engine.player.skill(skill), skills.gain_for(sk, engine.player) * times):
        engine.log(msg)


# ---- Tracking ----------------------------------------------------------------------------------------
def _tal(engine_or_player, key: str) -> int:
    from game import talents
    return talents.total(getattr(engine_or_player, "player", engine_or_player), key)


def track_turns(engine) -> int:
    return TRACK_TURNS * rank(engine, "tracking") + _tal(engine, "track")


def leave_track(engine, x: int, y: int) -> None:
    """A creature stepped off (x, y): a track, until it fades."""
    engine.game_map.tracks[(x, y)] = engine.turn


def fresh_tracks(engine) -> list[tuple[int, int]]:
    gm = engine.game_map
    life = track_turns(engine)
    old = [c for c, t in gm.tracks.items() if engine.turn - t > life]
    for c in old:
        del gm.tracks[c]
    return list(gm.tracks)


def on_area(engine, index: int) -> None:
    """Entering a hunt area: the first time on this hunt, practice; from rank 2, a sense of what's here."""
    hunt = engine.hunt
    if hunt is None:
        return
    sensed = hunt.__dict__.setdefault("sensed", set())
    if index in sensed:
        return
    sensed.add(index)
    practise(engine, "tracking")
    r = rank(engine, "tracking")
    if r < SENSE_RANK:
        return
    n = sum(1 for m in engine.game_map.monsters if not m.type.ghost)
    if r >= SENSE_EXACT_RANK:
        what = "no creatures" if n == 0 else f"{n} creature{'s' if n != 1 else ''}"
    else:
        what = ("no sign of creatures" if n == 0 else "signs of a few creatures" if n <= 3
                else "signs of several creatures" if n <= 7 else "signs of many creatures")
    engine.log(f"You read the ground: {what} here.")


def minimap_creatures(engine, gm) -> list:
    """Creatures Tracking puts on the minimap though you can't see them: a marked bounty in its
    area (rank 3), anything near you (rank 4+)."""
    if engine.hunt is None or gm is not engine.game_map:
        return []
    r = rank(engine, "tracking")
    p = engine.player
    out = []
    for m in gm.monsters:
        if r >= BOUNTY_RANK and getattr(m, "bounty", 0):
            out.append(m)
        elif r >= NEAR_RANK:
            radius = NEAR_RADIUS + 2 * (r - NEAR_RANK)
            if abs(m.x - p.x) + abs(m.y - p.y) <= radius and not getattr(m, "burrowed", False):
                out.append(m)
    return out


# ---- Stealth -----------------------------------------------------------------------------------------
def notice_chance(engine) -> float:
    return max(NOTICE_FLOOR, 1.0 - NOTICE_STEP * (rank(engine, "stealth") - 1) - _tal(engine, "notice") / 100)


def notices(engine, m) -> bool:
    """A creature that sees you: does it notice you this turn?"""
    chance = notice_chance(engine)
    if chance >= 1.0 or engine.rng.random() < chance:     # (no roll at rank 1: it always notices)
        return True
    if not getattr(m, "slipped", False):          # practice: once for each creature you slip past
        m.slipped = True
        practise(engine, "stealth")
    return False


def sneak_bonus(engine, target) -> tuple[int, int]:
    """(accuracy, damage) for a blow at a creature that hasn't noticed you."""
    if getattr(target, "awake", True):
        return 0, 0
    return SNEAK_ACCURACY, rank(engine, "stealth") // 2 + _tal(engine, "sneak_damage")


# ---- Harvesting --------------------------------------------------------------------------------------
def drop_chance_bonus(engine) -> float:
    return 0.05 * (rank(engine, "harvesting") - 1) + _tal(engine, "material_chance") / 100


def extra_count(engine) -> int:
    r = rank(engine, "harvesting")
    return (r >= 5) + _tal(engine, "material_extra")   # (balance pass 3, user: rank 5 only; was 3 and 5)


# ---- Survival ----------------------------------------------------------------------------------------
def rest_factor(player) -> float:
    from game import works                       # (the dormitory)
    return (max(0.5, 1.0 - 0.1 * (rank(player, "survival") - 1)) * (1 - _tal(player, "rest") / 100)
            * (1 - works.active("rest") / 100))


def ration_turns(player, base: int) -> int:
    return base + 2 * (rank(player, "survival") - 1)


def torch_turns(player, base: int) -> int:
    return int(base * (1 + 0.1 * (rank(player, "survival") - 1)))


def wound_turns(player, base: int) -> int:
    turns = base // 2 if rank(player, "survival") >= 4 else base
    return round(turns * (1 - _tal(player, "wound") / 100))           # (Thick Blood)


# ---- The character sheet -----------------------------------------------------------------------------
def sheet_lines(engine, skill_id: str) -> list[str]:
    p = engine.player
    r = rank(p, skill_id)
    if skill_id == "tracking":
        out = [f"Tracks last {track_turns(engine)} turns."]
        out.append("You sense how many creatures an area holds" + (" (the number)." if r >= SENSE_EXACT_RANK else ".")
                   if r >= SENSE_RANK else f"At rank {SENSE_RANK}: a sense of what an area holds.")
        out.append("A marked bounty shows on your minimap." if r >= BOUNTY_RANK
                   else f"At rank {BOUNTY_RANK}: a marked bounty on your minimap.")
        out.append(f"Creatures within {NEAR_RADIUS + 2 * (r - NEAR_RANK)} steps show on your minimap." if r >= NEAR_RANK
                   else f"At rank {NEAR_RANK}: creatures near you on your minimap.")
        return out
    if skill_id == "stealth":
        return [f"A creature that sees you notices you {round(notice_chance(engine) * 100)}% of the time.",
                f"Unnoticed, your blows get +{SNEAK_ACCURACY} accuracy and +{r // 2} damage."]
    if skill_id == "harvesting":
        return [f"Materials {round(drop_chance_bonus(engine) * 100)}% more often"
                + (f", {extra_count(engine)} more of each." if extra_count(engine) else ".")]
    if skill_id == "survival":
        out = [f"Rest after a hunt: {round(rest_factor(p) * 100)}% as long. "
               f"Rations mend {2 * (r - 1)} turns longer; torches burn {10 * (r - 1)}% longer."]
        if r >= 4:
            out.append("Bleeding and poison last half as long.")
        return out
    return []
