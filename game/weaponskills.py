"""Weapon skills and techniques (v0.55.0; design: claude/design-progression.md, stage 1).

Blades, Axes, Hafted and Brawling (bare hands) are skills in data/skills.json, like Marksmanship
for bows. A weapon names its skill (`skill` in its properties). Practising: every melee attack
with that weapon (a hit counts double). Each rank above 1 gives +1 accuracy with it, and ranks 3
and 5 each give +1 damage.

Techniques (data in TECHNIQUES): a passive one at rank 3; an active one at rank 5, readied with
`z` (no turn), used by the next attack with that weapon, then resting for REST turns.
All numbers are placeholders.
"""
from __future__ import annotations

MELEE_SKILLS = ("blades", "axes", "hafted", "brawling")
BOW_SKILL = "marksmanship"
PASSIVE_RANK, ACTIVE_RANK = 3, 5
REST = 20                 # turns before an active technique can be readied again
STAGGER_TURNS = 2         # a staggered creature loses this many turns
REND_TURNS, REND_DAMAGE = 5, 1
LUNGE_ACCURACY = AIM_ACCURACY = 4

TECHNIQUES = {
    "blades": {"passive": ("Riposte", "when a creature misses you in melee, you strike back at once"),
               "active": ("Lunge", "a blow at +4 accuracy and double damage dice")},
    "axes": {"passive": ("Cleave", "a killing blow carries on into another creature beside you"),
             "active": ("Rend", "a blow that leaves the creature bleeding")},
    "hafted": {"passive": ("Crush", "your blows ignore 1 armour"),
               "active": ("Stagger", "a blow that dazes the creature: it loses its next 2 turns")},
    "marksmanship": {"passive": ("Steady hand", "no accuracy lost to distance"),
                     "active": ("Aimed shot", "the next arrow at +4 accuracy and double damage dice")},
    "brawling": {"passive": ("Quick hands", "your first blow against each creature takes no time"),
                 "active": ("Throw", "knock a creature back a step and daze it for a turn")},
}


def melee_skill(player) -> str | None:
    """The skill your melee blows practise: the wielded weapon's, Brawling bare-handed; none for a
    bow's bash (bows are for shooting)."""
    weapon = player.equipped.get("weapon")
    if weapon is None:
        return "brawling"
    props = weapon.type.properties
    if props.get("bash_every"):
        return None
    return props.get("skill")


def weapon_skill(player) -> str | None:
    """The skill of the weapon in hand, bows included."""
    weapon = player.equipped.get("weapon")
    if weapon is None:
        return "brawling"
    props = weapon.type.properties
    return BOW_SKILL if props.get("ammo") else props.get("skill")


def rank(player, skill: str | None) -> int:
    if not skill:
        return 0
    try:
        return player.skill(skill).rank
    except KeyError:
        return 0


def accuracy_bonus(player) -> int:
    r = rank(player, melee_skill(player))
    return max(0, r - 1)


def damage_bonus(player) -> int:
    r = rank(player, melee_skill(player))
    return (r >= 3) + (r >= 5)


def has_passive(player, skill: str) -> bool:
    return weapon_skill(player) == skill and rank(player, skill) >= PASSIVE_RANK


def technique(skill: str, which: str) -> tuple[str, str]:
    return TECHNIQUES[skill][which]


def practise(engine, hit: bool) -> None:
    """A melee attack: practice for the weapon's skill (a hit counts double)."""
    from game import skills
    skill_id = melee_skill(engine.player)
    if not skill_id or skill_id not in engine.skills:
        return
    sk = engine.skills[skill_id]
    for msg in skills.add_practice(sk, engine.player.skill(skill_id),
                                   skills.gain_for(sk, engine.player) * (2 if hit else 1)):
        engine.log(msg)


def ready(engine) -> None:
    """`z`: ready (or put aside) the active technique of the weapon in hand. Takes no time."""
    p = engine.player
    skill = weapon_skill(p)
    if not skill or skill not in TECHNIQUES:
        engine.log("That weapon has no technique to ready.")
        return
    name, _ = technique(skill, "active")
    if rank(p, skill) < ACTIVE_RANK:
        sk = engine.skills.get(skill)
        engine.log(f"{name} comes at {sk.name if sk else skill} rank {ACTIVE_RANK}.")
        return
    if p.readied:
        engine.log(f"You let the {p.readied} go.")
        p.readied = None
        return
    if p.tech_rest > 0:
        engine.log(f"Not yet: you can try {name} again in {p.tech_rest} turns.")
        return
    p.readied = name
    engine.log(f"You ready a {name}: your next {'shot' if skill == BOW_SKILL else 'blow'} uses it.")


def spend(player) -> str | None:
    """The readied technique, used up by this attack (and resting)."""
    used, player.readied = player.readied, None
    if used:
        from game import talents                 # (Quick Recovery)
        player.tech_rest = max(1, REST - talents.total(player, "tech_rest"))
    return used


def tick(player) -> None:
    if player.tech_rest > 0:
        player.tech_rest -= 1


def sheet_lines(engine, skill_id: str) -> list[str]:
    """For the character sheet: what this rank gives and the techniques."""
    p = engine.player
    r = rank(p, skill_id)
    out = []
    if skill_id in MELEE_SKILLS:
        out.append(f"+{max(0, r - 1)} accuracy, +{(r >= 3) + (r >= 5)} damage with it.")
    if skill_id in TECHNIQUES:
        for which, at in (("passive", PASSIVE_RANK), ("active", ACTIVE_RANK)):
            name, what = technique(skill_id, which)
            state = "yours" if r >= at else f"at rank {at}"
            key = " (z to ready)" if which == "active" and r >= at else ""
            out.append(f"{name} ({state}): {what}{key}.")
    return out
