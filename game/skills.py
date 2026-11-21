"""Skills: things a Hunter gets better at. The first is Identification.

Skill definitions live in data/skills.json. A Hunter's own progress is a
SkillState per skill (rank and practice), kept on the Player.

Ranks rise by practice up to a point (self_taught_to); past that, a full
practice bar only makes you *ready*, and a trainer charges shards for the
next rank. Acumen makes each bit of practice count for more.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillDef:
    id: str
    name: str
    description: str
    max_rank: int
    self_taught_to: int
    practice_per_rank: int
    training_cost: dict[int, int]   # rank -> shards to train up to it
    attribute: str = "acumen"       # the attribute that makes practice count for more
    practice_base: int = 2          # practice per session before the attribute bonus

    def needed(self, rank: int) -> int:
        """Practice to fill the bar from `rank` to the next."""
        return self.practice_per_rank * rank


def load_skills(path: str | Path) -> dict[str, SkillDef]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {sid: SkillDef(sid, d["name"], d.get("description", ""), d["max_rank"], d["self_taught_to"],
                          d["practice_per_rank"], {int(k): v for k, v in d.get("training_cost", {}).items()},
                          d.get("attribute", "acumen"), d.get("practice_base", 2))
            for sid, d in raw.items() if not sid.startswith("_")}


@dataclass
class SkillState:
    rank: int = 1
    practice: int = 0


def practice_gain(acumen: int, base: int = 2) -> int:
    """How much one session teaches: the skill's base, plus 1 for every 2 points
    of its attribute over 10."""
    return base + max(0, (acumen - 10) // 2)


def gain_for(skill: SkillDef, player) -> int:
    base = practice_gain(player.stats[skill.attribute], skill.practice_base)
    from game import talents                    # Quick Study, Born Fighter, Woodwise (v0.58.0)
    pct = talents.practice_pct(player, skill.id) if hasattr(player, "talents") else 0
    return max(1, round(base * (1 + pct / 100))) if pct else base


def is_ready(skill: SkillDef, state: SkillState) -> bool:
    """Practised enough for the next rank, but it has to be trained."""
    return state.rank < skill.max_rank and state.practice >= skill.needed(state.rank)


def add_practice(skill: SkillDef, state: SkillState, amount: int) -> list[str]:
    """Practise. Returns messages for the log (rank ups, readiness)."""
    messages = []
    if state.rank >= skill.max_rank:
        return messages
    was_ready = is_ready(skill, state)
    state.practice += amount
    while state.rank < skill.max_rank and state.practice >= skill.needed(state.rank):
        if state.rank >= skill.self_taught_to:
            state.practice = skill.needed(state.rank)   # the bar stays full until you train
            if not was_ready:
                messages.append(f"You've learned all you can of {skill.name} on your own. "
                                f"Rank {state.rank + 1} needs training.")
            break
        state.practice -= skill.needed(state.rank)
        state.rank += 1
        messages.append(f"Your {skill.name} improves to rank {state.rank}.")
    return messages


def training_cost(skill: SkillDef, state: SkillState, discount: float = 1.0, cap: int | None = None) -> int | None:
    """Shards to train the next rank, or None if there's nothing to train. A mentor (game/aging.py)
    trains for less (discount), but no further than their own rank (cap)."""
    if state.rank >= skill.max_rank or state.rank < skill.self_taught_to:
        return None
    if cap is not None and state.rank >= cap:
        return None
    cost = skill.training_cost.get(state.rank + 1)
    return None if cost is None else int(cost * discount)


def rank_discount(player) -> float:
    """The share of the fee a Hunter pays, after their rank's training discount (game/ranks.py)."""
    from game import ranks
    return 1.0 - ranks.privilege(player, "training_discount", 0)


def works_discount() -> float:
    """The training corner (the Guild's works, v0.60.0)."""
    from game import works
    return 1 - works.active("training") / 100


def cost_for(player, skill: SkillDef, discount: float = 1.0, cap: int | None = None) -> int | None:
    """What this Hunter would pay to train the next rank (rank discount included)."""
    return training_cost(skill, player.skill(skill.id), discount * rank_discount(player) * works_discount(), cap)


def train(player, skill: SkillDef, discount: float = 1.0, cap: int | None = None) -> tuple[bool, str]:
    state = player.skill(skill.id)
    cost = training_cost(skill, state, discount * rank_discount(player) * works_discount(), cap)
    if cost is None:
        if state.rank >= skill.max_rank:
            return False, f"You've mastered {skill.name}. There's nothing left to teach you."
        if cap is not None and state.rank >= cap and state.rank >= skill.self_taught_to:
            return False, f"That's as far as I can take you in {skill.name}."
        return False, f"You can still improve {skill.name} by practice alone."
    if not is_ready(skill, state):
        return False, f"You need more practice before training {skill.name} rank {state.rank + 1}."
    if player.shards < cost:
        return False, f"Training costs {cost} shards. You don't have enough."
    player.shards -= cost
    state.rank += 1
    state.practice = 0
    return True, f"You train {skill.name} to rank {state.rank} for {cost} shards."
