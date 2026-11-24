"""The look command: describing what's at a spot on the map.

What you're told depends on what you can see. In fog-of-war areas, a spot
in view shows everything; a spot you've seen before shows only what you
remember (the ground and items, not creatures); a spot you've never seen
shows nothing.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.engine import Engine

TEXT = (233, 223, 204)
DIM = (150, 138, 122)
WARN = (240, 120, 40)
ACCENT = (230, 160, 80)

# How dangerous a creature looks, by its tier.
THREAT = {1: "Looks like a minor threat.", 2: "Looks dangerous.",
          3: "Looks very dangerous.", 4: "Looks deadly."}


def health_words(hp: int, max_hp: int) -> str:
    share = hp / max_hp if max_hp else 0
    if share >= 1:
        return "unhurt"
    if share > 0.66:
        return "lightly wounded"
    if share > 0.33:
        return "wounded"
    return "badly wounded"


def can_see(engine: "Engine", x: int, y: int) -> bool:
    gm = engine.game_map
    return not gm.fog or bool(engine.visible[x, y])


def has_seen(engine: "Engine", x: int, y: int) -> bool:
    gm = engine.game_map
    return not gm.fog or bool(gm.explored[x, y])


def targets(engine: "Engine") -> list[tuple[int, int]]:
    """Interesting spots in view (creatures, people, items), nearest first."""
    gm, p = engine.game_map, engine.player
    spots = {(m.x, m.y) for m in gm.monsters} | {(n.x, n.y) for n in gm.npcs} | {(f.x, f.y) for f in gm.items}
    spots = [s for s in spots if gm.in_bounds(*s) and can_see(engine, *s) and engine.in_vision(*s)]
    return sorted(spots, key=lambda s: max(abs(s[0] - p.x), abs(s[1] - p.y) * 2))


def describe(engine: "Engine", x: int, y: int) -> tuple[str, list[tuple[str, tuple]]]:
    """(heading, [(line, colour), ...]) for whatever is at (x, y)."""
    gm, p = engine.game_map, engine.player
    if not gm.in_bounds(x, y) or not has_seen(engine, x, y):
        return "Unknown", [("You haven't seen what's there.", DIM)]

    lines: list[tuple[str, tuple]] = []
    if (x, y) == (p.x, p.y):
        st = p.stats
        heading = f"{p.full_name} (you)"
        lines.append((f"Level {st.level} Hunter, {health_words(st.hp, st.max_hp)} ({st.hp}/{st.max_hp} HP).", TEXT))
    elif can_see(engine, x, y) and (m := gm.monster_at(x, y)):
        t = m.type
        heading = m.name if getattr(m, "named", "") else t.name.capitalize()
        if t.description:
            lines.append((t.description, DIM))
        state = health_words(m.hp, t.hp).capitalize()
        if t.behaviour == "still":
            notice = "It doesn't move."
        else:
            notice = "It has noticed you." if m.awake else "It hasn't noticed you."
        lines.append((f"{state}. {notice}", TEXT))
        from game import mastery
        pa, pd = mastery.prey_bonus(engine.player, m)
        if pa:                                   # knowing your prey (v0.59.0)
            kills = engine.player.prey.get(t.id, 0)
            lines.append((f"You know its ways: {kills} killed ({'+1 accuracy, +1 damage' if pd else '+1 accuracy'}).", ACCENT))
        if getattr(m, "bleeding", 0) or getattr(m, "staggered", 0):   # (your techniques, v0.55.0)
            lines.append((" ".join(w for w in ("It's bleeding." if m.bleeding else "",
                                               "It's reeling." if m.staggered else "") if w), ACCENT))
        from game import named
        for line in named.look_lines(m):
            lines.append((line, WARN))
        tier = min(4, t.tier + 1) if getattr(m, "named", "") else t.tier     # (a named one: a step worse)
        lines.append((THREAT.get(tier, ""), WARN if tier >= 3 else TEXT))
    elif can_see(engine, x, y) and (n := gm.npc_at(x, y)):
        heading = n.name
        folk = engine.townsfolk.get(n.folk_id)
        if folk and folk.description:
            lines.append((folk.description, TEXT))
        lines.append(("Walk into them to talk.", DIM))
    else:
        heading = gm.tile_at(x, y).name.capitalize()
        if gm.tile_at(x, y).symbol == "N":
            lines.append(("Notices from the people of Bytorsskug, asking for things they'll pay for. "
                          "Walk into it to read them.", TEXT))
        if gm.tile_at(x, y).symbol == "L":
            lines.append(("A brass plaque naming those who paid for the Guild's works. Walk into it to read it.", TEXT))
        if gm.tile_at(x, y).symbol in "UZKE" and gm.hall:
            lines.append(("Part of the Guild's works. The plaque by the door says who paid for it.", DIM))
        if gm.tile_at(x, y).symbol == "D":
            lines.append(("The trophy wall: the records the trophymaster keeps, mounted. Walk into it to read them.", TEXT))
        if gm.tile_at(x, y).symbol == "C":
            lines.append(("The guild hall's stash chest. Walk into it to store things or take them out. "
                          "What's in it passes to the next Hunter.", TEXT))

    from game import wilds                 # (v0.91.0) a camp or a foraging spot on the Brisering
    wl = wilds.look_lines(engine, x, y) if gm.explored[x, y] or not gm.fog else None
    if wl:
        heading = wl[0]
        lines.insert(0, (wl[1], TEXT))
    from game import fishing               # (v0.94.0) water you could fish
    where = fishing.place(engine)
    if where in ("city", "brisering") and gm.tile_at(x, y).symbol == "~" and (gm.explored[x, y] or not gm.fog):
        lines.append((fishing.describe_spot(engine, x, y) + " With a rod and bait, fish it (r).", TEXT))
    # Items lying here (remembered ones too).
    here = gm.items_at(x, y)
    if here:
        names = ", ".join(f.item.floor_label for f in here)
        lines.append((f"Lying here: {names}.", TEXT))
        if len(here) == 1 and here[0].item.trophy is not None:
            it = here[0].item
            from game import trophies
            lines.append((f"About {trophies.weight_text(it.trophy['kg'])}. Pick it up (g) to haul it home as a "
                          f"trophy ({it.slots} slot{'s' if it.slots > 1 else ''}), or butcher it (b) for materials.", DIM))
        elif len(here) == 1:
            lines.append((here[0].item.type.description, DIM))
    if (x, y) in gm.windows:              # a service window
        who = next((n for n in gm.npcs if n.folk_id == gm.windows[(x, y)]), None)
        heading = f"{who.name}'s window" if who else "A service window"
        lines.insert(0, ((f"Walk into it to talk to {who.name}." if who else "No one's behind it just now."), TEXT))
    from game import homes
    if (x, y) in getattr(gm, "home_doors", {}):            # a house that can be a Hunter's home (v0.74.0)
        hid = gm.home_doors[(x, y)]
        h = homes.data()["homes"][hid]
        mine = homes.owned(engine) == hid
        heading = "Your home" if mine else h["name"][0].upper() + h["name"][1:]
        lines.insert(0, (("Your own place." if mine else f"For sale, for {h['price']} shards: see the property dealer."), TEXT))
    sym_here = gm.tile_at(x, y).symbol
    if sym_here in "nqjFda" and homes.owned(engine):
        lines.insert(0, ({"n": "Your bed: walk into it to sleep off the rest you owe, heal, and mend minor injuries.",
                          "q": "Your chest: walk into it to put things in or take them out.",
                          "j": "Your trophy shelves: walk into them to put a trophy up or take one down.",
                          "a": "Your fish tank: walk into it to put a fish in or take one out.",
                          "F": "Your forge: walk into it to raise a weapon or armour piece, up to +3.",
                          "d": "Your workbench: walk into it to repair a Common artifact"
                               + (", or raise a weapon or armour piece up to +3." if homes.smithing_key(engine) == "workbench" else ".")}[sym_here], TEXT))
    from game import monuments
    mon = monuments.at(gm, x, y)
    if mon:                               # a statue and its story (v0.68.0)
        heading = mon["name"]
        lines.insert(0, (mon.get("look", "") + " Walk into it to read the inscription.", TEXT))
    if (x, y) in gm.landmarks:            # a named place on the Brisering
        heading = gm.landmarks[(x, y)]
        lines.insert(0, (f"A {gm.tile_at(x, y).name}.", TEXT))
    if heading != gm.tile_at(x, y).name.capitalize() and (x, y) != (p.x, p.y):
        lines.append((f"On {gm.tile_at(x, y).name}.", DIM))
    if not can_see(engine, x, y):
        lines.insert(0, ("You remember this place; it's out of sight now.", DIM))
    return heading, lines
