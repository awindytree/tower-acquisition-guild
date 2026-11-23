"""How a Hunter makes their living, and the middle name that follows it (user, 2026-11-23, v0.95.0).

The user: a middle name is how a person makes their living. "If more than 50% of the last 1,000 shards
earned comes from fishing, the calling changes to Angler. If it comes from hunts, it does the weapon
calling. Then whatever other callings we add later would be in that pool too."

- Every shard earned (`Player.earn`, `Player.guild_pay`) is noted with how it was made in a ledger of
  the last `WINDOW` shards (`Player.ledger`, oldest first, trimmed from the front).
- When one way of earning holds **more than half** of the window, it becomes the Hunter's living
  (`Player.living`). Until then the living stays what it was: a new Hunter is a hunter, and no one
  flips back and forth on a near-even split.
- The middle name: `LIVINGS[living]` (fishing: Angler), or, for hunting, the weapon used most
  (game/names.py). New livings go in `LIVINGS` and pass their source to `earn`.

"Hunting" is everything else for now: hunts, bounties, selling artifacts and materials, trophies,
caravan pay.
"""
from __future__ import annotations

WINDOW = 1000                    # the last this-many shards earned (user)
LIVINGS = {"fishing": "Angler"}  # living -> middle name; hunting uses the weapon


def note(player, source: str, amount: int) -> None:
    """Shards earned this way: into the ledger, and the living follows if one now holds more than half."""
    if amount <= 0:
        return
    led = player.ledger
    if led and led[-1][0] == source:
        led[-1][1] += amount
    else:
        led.append([source, amount])
    total = sum(n for _, n in led)
    while total > WINDOW and led:            # trim the oldest down to the window
        over = total - WINDOW
        if led[0][1] <= over:
            total -= led.pop(0)[1]
        else:
            led[0][1] -= over
            total = WINDOW
    shares = shares_of(player)
    for how, n in shares.items():
        if n * 2 > WINDOW:
            player.living = how
            break


def shares_of(player) -> dict:
    """Shards in the window, by how they were made."""
    out: dict = {}
    for how, n in player.ledger:
        out[how] = out.get(how, 0) + n
    return out


def calling(player) -> str | None:
    """The middle name for the Hunter's living, or None for hunting (the weapon decides)."""
    return LIVINGS.get(getattr(player, "living", "hunting"))


NAMES = {"hunting": "hunting", "fishing": "fishing"}


def sheet_line(player) -> str:
    """For the character sheet: the living, and how the last shards were made."""
    sh = shares_of(player)
    total = sum(sh.values())
    living = getattr(player, "living", "hunting")
    head = f"You make your living by {NAMES.get(living, living)}."
    if not total:
        return head + " (Your middle name follows whatever earns you more than half of your last 1,000 shards.)"
    parts = ", ".join(f"{NAMES.get(h, h)} {round(100 * n / total)}%" for h, n in sorted(sh.items(), key=lambda kv: -kv[1]))
    return (f"{head} Your last {total:,} shards: {parts}. More than half of the last 1,000 from one kind "
            "of work, and your middle name follows it.")
