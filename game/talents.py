"""Talents (v0.58.0; design: claude/design-progression.md, stage 4).

The user's direction: a big pool (data/talents.json, 50 for now); at every third level (3, 6, 9...)
a Hunter is offered three at random from those they don't have and qualify for, and keeps one,
like a run upgrade. Hunter's own: lost on death.

Effects are numbers, summed over the talents a Hunter has (`total(player, key)`), read where each
applies. The keys:
  armor, evasion, accuracy, damage (melee), ranged_accuracy, ranged_damage, range, crit (% chance a
  landed blow does double damage), heal_on_kill, second_wind, low_hp_damage, after_hit_accuracy,
  solo_accuracy, max_hp, faints, injury_chance (% less), daze_resist (turns), thorn_resist,
  wound (% shorter bleeding/poison), heal_rate (turns sooner), attr:<attribute>, ration (% more),
  draught (+HP), carry (slots), sight, track (turns), notice (% less), sneak_damage,
  material_chance (%), material_extra, rest (% shorter), brisering_steps (% more), drain (% slower),
  extra_uses, identify (rarity tiers), shards_found (%), bounty_pay (%), request_pay (%),
  dues (points off the share), practice_all / practice_weapon / practice_field (%), xp (%),
  tech_rest (turns); fishing (v0.100.0): fish_bite (%), fish_window (turns), fish_gut (more from
  gutting), and any other fish_* key a tackle trait uses (game/fishing.py: tackle_total).
"""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "talents.json"


@lru_cache(maxsize=1)
def data() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def pool() -> dict:
    return data()["talents"]


def every() -> int:
    return data().get("every", 3)


def total(player, key: str) -> int:
    """A key summed over the Hunter's talents and, since v0.77.0, the traits of their worn gear
    (game/gear.py), so a trait can use any talent key."""
    from game import gear
    t = getattr(player, "talents", None)
    p = pool()
    own = sum(p[tid]["effects"].get(key, 0) for tid in t if tid in p) if t else 0
    return own + gear.trait_total(player, key)


def has(player, key: str) -> bool:
    return total(player, key) > 0


def qualifies(player, tid: str) -> bool:
    req = pool()[tid].get("requires")
    if not req:
        return True
    if "talent" in req and req["talent"] not in player.talents:
        return False
    if "attribute" in req:
        attr, least = req["attribute"]
        if player.stats.attributes[attr] < least:
            return False
    return True


def earned(player) -> int:
    """How many talents this Hunter's level has earned."""
    return player.stats.level // every()


def check(engine, rng: random.Random | None = None) -> None:
    """After experience: roll the offers for any talent level reached (once each)."""
    p = engine.player
    rng = rng or engine.rng
    while len(p.talents) + len(p.talent_offers) < earned(p):
        offered = {t for offer in p.talent_offers for t in offer}
        choices = [t for t in pool() if t not in p.talents and t not in offered and qualifies(p, t)]
        if not choices:
            break
        offer = rng.sample(sorted(choices), min(data().get("offer", 3), len(choices)))
        p.talent_offers.append(offer)
        engine.talent_later = False
        engine.log("You've earned a talent. Press n to choose it.")


def choose(engine, tid: str) -> str:
    """Take a talent from the first offer."""
    p = engine.player
    if not p.talent_offers or tid not in p.talent_offers[0]:
        raise ValueError(f"{tid!r} isn't on offer")
    p.talent_offers.pop(0)
    p.talents.append(tid)
    from game import injuries
    injuries.apply_to_stats(p)          # attribute and HP talents take effect at once
    name = pool()[tid]["name"]
    engine.log(f"Talent: {name}. {pool()[tid]['description']}")
    return name


def show_offer(engine) -> None:
    """Open the choice, if one's waiting and nothing else is on screen."""
    if engine.screen is None and engine.player.talent_offers and not getattr(engine, "talent_later", False):
        from game.screens import TalentScreen
        engine.screen = TalentScreen()


def practice_pct(player, skill_id: str) -> int:
    from game import weaponskills, fieldskills
    pct = total(player, "practice_all")
    if skill_id in weaponskills.MELEE_SKILLS or skill_id in weaponskills.RANGED_SKILLS:
        pct += total(player, "practice_weapon")
    if skill_id in fieldskills.FIELD_SKILLS:
        pct += total(player, "practice_field")
    return pct
