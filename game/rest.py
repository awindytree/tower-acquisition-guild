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
    """Stepping into the Wayfinder: rest first, or set out weary, or not at all. `go(engine)` opens the
    word window once that's settled."""
    from game.screens import ChoiceScreen
    p = engine.player
    p.weary_next = 0.0
    n = pulses_owed(p)
    if not n:
        go(engine)
        return
    w = weariness(p)

    def rest_first(e):
        e.screen = None
        rest_here(e)
        if not e.passing:
            go(e)

    if n >= reckon(engine):
        # Too much owed to set out, but resting here is always open (v0.100.4, user: with no bed and no
        # dormitory, the Wayfinder refused you and offered no way to rest).
        def not_now(e):
            e.screen = None
            e.log("A bed pays rest off quicker: the Guild's bunks, once it has a dormitory, or a home of your own.")
        engine.screen = ChoiceScreen(f"Rest owed: {text(n, engine.calendar.per_cycle)}: too much to set out", [
            (f"Rest it off here first ({n} Pulses)", rest_first),
            ("Not now", not_now),
        ])
        return

    def weary(e):
        e.screen = None
        e.player.weary_next = w
        go(e)

    engine.screen = ChoiceScreen(f"Rest owed: {text(n, engine.calendar.per_cycle)}", [
        (f"Rest it off here first ({n} Pulses)", rest_first),
        (f"Set out anyway. {weary_line(w)}", weary),
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
