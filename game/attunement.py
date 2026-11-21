"""Attunement (v0.57.0; design: claude/design-progression.md, stage 3): a Hunter's feel for Jodebris
and the artifacts it drives. Governed by Tenacity; trained by the artificer. Placeholders.

- Windcatcher drain: -10% a rank above 1 (carried over turn to turn, so fractions count).
- Rank 3: an artifact with limited uses gets one more each hunt.
- Rank 5: a fourth artifact slot.
Practice: using an artifact; moving between areas on a hunt with Jodebris in your windcatcher.
"""
from __future__ import annotations

SKILL = "attunement"
EXTRA_USE_RANK, EXTRA_SLOT_RANK = 3, 5
BASE_SLOTS = 3


def rank(player) -> int:
    try:
        return player.skill(SKILL).rank
    except KeyError:
        return 1


def drain_factor(player) -> float:
    from game import talents                     # (Jodebris Sense)
    return max(0.5, 1.0 - 0.1 * (rank(player) - 1)) * (1 - talents.total(player, "drain") / 100)


def extra_uses(player) -> int:
    from game import talents                     # (Tinkerer)
    return (1 if rank(player) >= EXTRA_USE_RANK else 0) + talents.total(player, "extra_uses")


def slot_count(player) -> int:
    return BASE_SLOTS + (1 if rank(player) >= EXTRA_SLOT_RANK else 0)


def sync_slots(player) -> None:
    """Grow the artifact slots when Attunement reaches rank 5 (they never shrink)."""
    want = slot_count(player)
    if len(player.artifact_slots) < want:
        player.artifact_slots += [None] * (want - len(player.artifact_slots))


def practise(engine, times: int = 1) -> None:
    from game import skills
    if SKILL not in engine.skills:
        return
    sk = engine.skills[SKILL]
    for msg in skills.add_practice(sk, engine.player.skill(SKILL), skills.gain_for(sk, engine.player) * times):
        engine.log(msg)
    sync_slots(engine.player)


def sheet_lines(engine, skill_id: str) -> list[str]:
    if skill_id != SKILL:
        return []
    p = engine.player
    r = rank(p)
    out = [f"Your windcatcher drains {round(drain_factor(p) * 100)}% as fast."]
    out.append("Artifacts with limited uses get one more each hunt." if r >= EXTRA_USE_RANK
               else f"At rank {EXTRA_USE_RANK}: one more use each hunt from limited artifacts.")
    out.append("A fourth artifact slot." if r >= EXTRA_SLOT_RANK else f"At rank {EXTRA_SLOT_RANK}: a fourth artifact slot.")
    return out
