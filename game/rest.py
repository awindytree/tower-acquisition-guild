"""The rest you owe (user, 2026-11-23; design: claude/design-return-journey.md, stage 1).

A hunt no longer passes the Hunter's rest at once. It leaves a **debt** (`Player.rest_owed`, in Pulses:
`aging.rest_pulses`, the same size as the old rest), and the Hunter sells, sorts and trains first.
- **Every Pulse that passes off a hunt pays it down** at the natural rate (1 a Pulse), whatever the
  Hunter is doing; each also heals a tenth of their HP.
- **A bed pays it faster** (user's order, slowest to fastest): no bed, the Guild dormitory's bunks,
  the stead, the Ingenfjel home, the Bytorsskug home. Sleeping there passes the Pulses needed to pay
  it all, at that rate (`sleep`).
- **At the Wayfinder** (`at_wayfinder`) whatever's still owed is rested off where you stand (no bed),
  or, while it's less than a Reckon, the Hunter may **set out weary**: `Player.weary` = owed ÷
  `WORST` (80 Pulses: 8 Cycles 8 Pulses), from 0 to 1, for that hunt. The debt isn't paid; it's still
  owed, on top of the next rest, when they come home.
- **Weary** (user's anchors, calibrated with the balance bot): 50% tough but not ruined, like a level-1
  Hunter at danger 2 in starting gear; 80% a fool's game; 100% very nearly a death sentence.
"""
from __future__ import annotations

import math

WORST = 80                 # 8 Cycles 8 Pulses owed: the worst weariness (user)
NATURAL = 1.0              # Pulses of debt paid per Pulse, with no bed (user: the slowest)
HEAL_PER_PULSE = 0.1       # a Pulse off a hunt heals a tenth of max HP
# The Guild dormitory's bunks: 1 + the works tier's "rest" % (25, then 40: 1.25, 1.4); homes: homes.json rest_rate
# Weariness at 100% (scaled by Player.weary): calibrated (balance report, v0.88.0)
WEARY_HP = 0.8             # share of max HP lost
WEARY_ACCURACY = 10
WEARY_EVASION = 10
WEARY_HEAL = 6.0           # natural healing takes (1 + this × weary) times as long...
NO_HEAL_FROM = 0.5         # ...and stops altogether from this weariness: resting in the field doesn't restore you
WEARY_DAMAGE = 3           # blows land softer


def reckon(engine) -> int:
    return engine.calendar.per_reckon


def owed(player) -> float:
    return getattr(player, "rest_owed", 0.0)


def pulses_owed(player) -> int:
    return math.ceil(owed(player) - 1e-9)


def text(pulses: float, per_cycle: int = 9) -> str:
    n = math.ceil(pulses - 1e-9)
    c, p = divmod(n, per_cycle)
    parts = ([f"{c} Cycle{'s' if c != 1 else ''}"] if c else []) + ([f"{p} Pulse{'s' if p != 1 else ''}"] if p else [])
    return " and ".join(parts) if parts else "nothing"


def owed_line(engine) -> str:
    """'Rest owed: 8 Cycles and 4 Pulses' (or 'Rested')."""
    p = engine.player
    return f"Rest owed: {text(owed(p), engine.calendar.per_cycle)}" if pulses_owed(p) else "Rested"


def weariness(player) -> float:
    return min(1.0, owed(player) / WORST)


def add(engine, pulses: int) -> None:
    p = engine.player
    p.rest_owed = owed(p) + pulses


def passed(engine, pulses: int, rate: float = NATURAL) -> None:
    """Pulses have passed off a hunt (Engine.next_day): the debt goes down, and the Hunter heals."""
    p = engine.player
    if engine.hunt is not None or p is None:
        return
    if owed(p):
        p.rest_owed = max(0.0, owed(p) - pulses * rate)
    if p.stats.hp < p.stats.max_hp:
        p.stats.hp = min(p.stats.max_hp, p.stats.hp + max(1, int(p.stats.max_hp * HEAL_PER_PULSE)) * pulses)


def dorm_rate() -> float:
    from game import works
    return NATURAL + works.active("rest") / 100


def sleep(engine, rate: float, where: str) -> int:
    """Sleep off everything owed at `rate`. Returns the Pulses slept (at least one: a night's sleep)."""
    p = engine.player
    n = max(1, math.ceil(owed(p) / rate - 1e-9))
    engine.rest_rate = rate
    try:
        engine.next_day(n)
    finally:
        engine.rest_rate = NATURAL
    if engine.passing:              # their years ran out while they slept (the card is up)
        return n
    p.rest_owed = 0.0
    p.stats.hp = p.stats.max_hp
    engine.log(f"You sleep {where}" + (f" for {text(n, engine.calendar.per_cycle)}" if n > 1 else "")
               + " and wake rested.")
    return n


STABLE_FLOOR_CYCLES = 1        # the straw won't take you below a Cycle owed (user, v0.100.5)


def stable_sleep(engine) -> int:
    """Sleep in the straw of the boga stables by the Towerway gate (user, v0.100.5): free, at the plain
    rate, and it only takes you down to a Cycle of rest owed. Returns the Pulses slept."""
    p = engine.player
    floor = STABLE_FLOOR_CYCLES * engine.calendar.per_cycle
    if owed(p) <= floor + 1e-9:
        engine.log("You're as rested as straw will get you. A proper bed would do the rest." if owed(p) > 0
                   else "You're rested. The straw is for those who aren't.")
        return 0
    n = max(1, math.ceil(owed(p) - floor - 1e-9))
    engine.rest_rate = NATURAL
    try:
        engine.next_day(n)
    finally:
        engine.rest_rate = NATURAL
    if engine.passing:
        return n
    p.rest_owed = float(floor)
    p.stats.hp = p.stats.max_hp
    engine.log(f"You sleep in the straw for {text(n, engine.calendar.per_cycle)}, among the boga. "
               f"You wake stiff, still owing {text(pulses_owed(p), engine.calendar.per_cycle)} of rest.")
    return n


def where_to_rest(engine) -> str:
    """Where this Hunter can sleep it off."""
    from game import homes, works
    out = ["the straw in the boga stables by the Towerway gate"]
    if works.active("rest") or any(engine.city.tile_at(x, y).symbol == "K"
                                   for x in range(engine.city.width) for y in range(engine.city.height)):
        out.append("the Guild's bunks")
    if homes.owned(engine) and (engine.home or {}).get("built", {}).get("bed"):
        out.append("your own bed")
    return out[0] if len(out) == 1 else ", ".join(out[:-1]) + " or " + out[-1]


def rest_here(engine) -> int:
    """Rest off everything owed where you stand (no bed: the slowest)."""
    p = engine.player
    n = pulses_owed(p)
    if n:
        engine.next_day(n)
        if engine.passing:          # their years ran out (the card is up)
            return n
        p.rest_owed = 0.0
        p.stats.hp = p.stats.max_hp
        engine.log(f"You rest for {text(n, engine.calendar.per_cycle)} before you go out again.")
    return n


def weary_line(w: float) -> str:
    pct = round(w * 100)
    word = ("a little tired" if pct < 25 else "tired" if pct < 50 else "worn" if pct < 80
            else "exhausted" if pct < 100 else "dead on your feet")
    return f"Weary: {pct}% ({word})"


def at_wayfinder(engine, go) -> None:
    """Stepping into the Wayfinder (user, v0.100.5): owing a Reckon or more of rest, it won't take you
    through; owing less, it asks whether you'll go weary. Resting is done elsewhere (the stables, the
    Guild's bunks, a bed of your own). `go(engine)` opens the word window."""
    from game.screens import ChoiceScreen
    p = engine.player
    p.weary_next = 0.0
    n = pulses_owed(p)
    if not n:
        go(engine)
        return
    per = engine.calendar.per_cycle
    if n >= reckon(engine):
        engine.log(f"The Wayfinder won't take you through like this: you owe {text(n, per)} of rest. "
                   f"Sleep it off first: {where_to_rest(engine)}.")
        return
    w = weariness(p)

    def weary(e):
        e.screen = None
        e.player.weary_next = w
        go(e)

    def not_yet(e):
        e.screen = None
        e.log(f"Somewhere to sleep it off: {where_to_rest(e)}.")

    engine.screen = ChoiceScreen(f"Rest owed: {text(n, per)}. Go anyway?", [
        (f"Set out anyway. {weary_line(w)}", weary),
        ("Not yet: rest first", not_yet),
    ])


def begin(engine) -> None:
    """A hunt begins (Engine.begin_hunt): weariness chosen at the Wayfinder takes hold."""
    p = engine.player
    p.weary = getattr(p, "weary_next", 0.0)
    p.weary_next = 0.0
    from game import injuries
    injuries.apply_to_stats(p)
    p.stats.hp = p.stats.max_hp
    if p.weary:
        engine.log(f"You set out before you've rested. {weary_line(p.weary)}.")


def end(engine) -> None:
    """The hunt is over: weariness lifts (the debt it came from is still owed)."""
    p = engine.player
    if getattr(p, "weary", 0.0):
        p.weary = 0.0
        from game import injuries
        injuries.apply_to_stats(p)


def max_hp_loss(player, full: int) -> int:
    return int(full * WEARY_HP * getattr(player, "weary", 0.0))
