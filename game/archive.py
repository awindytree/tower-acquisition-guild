"""The Guild archive: bestiary entries and scouting reports.

Out on a hunt, a Hunter keeps field notes (Hunter state, lost if they die):
creatures seen, creatures killed, and how deep they got into each region.
Reported to the guild clerk, the notes go into the archive (world state, kept
for every Hunter after), and the Guild pays a small fee for what's new. The
Guild only wants what's useful to Hunters; general lore goes to the Academy.

Bestiary levels: 1 seen (what it looks like, where), 2 killed (how it
fights), 3 killed KILLS_FOR_FULL times (what it leaves, what it does to you).
All numbers are placeholders.
"""
from __future__ import annotations

KILLS_FOR_FULL = 5     # kills (by any Hunters, reported) for a full bestiary entry
FEE_PER_LEVEL = 2      # shards per new bestiary level, times the creature's tier
FEE_PER_AREA = 3


def kills_for_full() -> int:
    """Fewer with the Guild's archive wing (v0.60.0)."""
    from game import works
    return works.active("bestiary_kills") or KILLS_FOR_FULL




def empty() -> dict:
    return {"creatures": {}, "regions": {}}   # id -> {"seen": bool, "kills": n}; id -> deepest area


# ---- Notes, out on a hunt -------------------------------------------------------------------
def note_sighting(engine, monster) -> None:
    seen = engine.player.notes.setdefault("seen", [])
    if monster.type.id not in seen:
        seen.append(monster.type.id)


def note_kill(engine, monster) -> None:
    note_sighting(engine, monster)
    kills = engine.player.notes.setdefault("kills", {})
    kills[monster.type.id] = kills.get(monster.type.id, 0) + 1


def note_area(engine, index: int) -> None:
    if engine.hunt is None:
        return
    reached = engine.player.notes.setdefault("reached", {})
    rid = engine.hunt.contract.region.id
    reached[rid] = max(reached.get(rid, 0), index + 1)


def has_notes(player) -> bool:
    n = player.notes
    return bool(n.get("seen") or n.get("kills") or n.get("reached") or n.get("mapped"))


# ---- The archive -------------------------------------------------------------------------------
def level(archive: dict, creature_id: str) -> int:
    c = archive["creatures"].get(creature_id)
    if not c:
        return 0
    if c.get("kills", 0) >= kills_for_full():
        return 3
    return 2 if c.get("kills", 0) else (1 if c.get("seen") else 0)


def report(engine) -> str:
    """Hand the Hunter's notes to the clerk: they go into the archive; the Guild pays for what's new.
    The Guild's own fee: no dues are taken from it (like odd jobs)."""
    p, arc = engine.player, engine.archive
    notes = p.notes
    if not has_notes(p):
        return "You have no field notes to report."
    pay, new_entries, new_areas = 0, 0, 0
    for cid in set(notes.get("seen", [])) | set(notes.get("kills", {})):
        if cid not in engine.monster_types:
            continue
        before = level(arc, cid)
        c = arc["creatures"].setdefault(cid, {"seen": False, "kills": 0})
        c["seen"] = True
        c["kills"] += notes.get("kills", {}).get(cid, 0)
        gained = level(arc, cid) - before
        if gained:
            new_entries += 1
            pay += gained * FEE_PER_LEVEL * engine.monster_types[cid].tier
    for rid, deepest in notes.get("reached", {}).items():
        if rid not in engine.regions:
            continue
        before = arc["regions"].get(rid, 0)
        if deepest > before:
            arc["regions"][rid] = deepest
            new_areas += deepest - before
            pay += (deepest - before) * FEE_PER_AREA * engine.regions[rid].danger[0]
    from game import maps                   # scouting reports, for the cartographer (v0.84.0)
    new_maps, map_pay = maps.report(engine)
    pay += map_pay
    p.notes = {}
    from game import works                  # (the archive wing pays half again)
    pay = round(pay * (1 + works.active("notes") / 100))
    p.guild_pay(pay)
    if not pay:
        return "The clerk files your notes, but there's nothing in them the archive didn't already have."
    parts = []
    if new_entries:
        parts.append(f"{new_entries} bestiary entr{'ies' if new_entries != 1 else 'y'}")
    if new_areas:
        parts.append(f"{new_areas} area{'s' if new_areas != 1 else ''} of scouting")
    if new_maps:
        parts.append(f"{new_maps} place{'s' if new_maps != 1 else ''} for the cartographer")
    return f"The clerk files your notes ({' and '.join(parts)}) and pays you {pay} shards."


# ---- What the archive says ---------------------------------------------------------------------
def creature_lines(engine, creature_id: str, catalogue) -> list[str]:
    """The bestiary entry, as much as the archive knows."""
    t = engine.monster_types[creature_id]
    lv = level(engine.archive, creature_id)
    kills = engine.archive["creatures"].get(creature_id, {}).get("kills", 0)
    kw = engine.regions.keywords
    homes = ", ".join(sorted(w.shown for w in kw.words["land"].values() if not w.data.get("story")
                             and (set(w.data.get("styles", {})) | {w.data.get("style")}) & set(t.habitats))) or "unknown"
    lines = [t.description, f"Found in: {homes}."]
    if lv >= 2:
        lines.append(f"Danger: tier {t.tier}. Hits for {t.damage}; about {t.hp} HP; armour {t.armor}. "
                     f"Accuracy {t.accuracy}, evasion {t.evasion}. "
                     + ("Hunts by sight." if t.behaviour == "hunt" else "Never moves; strikes what comes near."))
    else:
        lines.append("Kill one and report it to learn how it fights.")
    if lv >= 3:
        drops = ", ".join(f"{catalogue[i].real_name} ({round(c * 100)}%)" for i, c, *_ in t.drops) or "nothing"
        lines.append(f"Leaves: {drops}.")
        if t.injures:
            from game import injuries
            lines.append("Can leave you with: " + ", ".join(injuries.table()[i].name for i in t.injures) + ".")
    elif lv == 2:
        lines.append(f"Kills reported: {kills} of {kills_for_full()} for a full entry.")
    return lines


def region_lines(engine, region_id: str) -> list[str]:
    r = engine.regions[region_id]
    deepest = engine.archive["regions"].get(region_id, 0)
    lo, hi = r.danger
    lines = [f"Danger {lo}, {r.depth or '?'} areas deep, {r.style_text()}. "
             + ("Hunted by day." if r.light == "day" else "Dark: bring light."),
             f"Deepest reported: area {deepest}." if deepest else "No Hunter has reported scouting it yet."]
    filed = engine.archive.get("maps", {}).get(region_id)
    if filed:
        lines.append(f"Scouted for the maps by {filed['by']}: the cartographer can draw it.")
    known = [engine.monster_types[c].name for c in engine.archive["creatures"]
             if c in engine.monster_types and set(r.all_styles()) & set(engine.monster_types[c].habitats)]
    lines.append("Creatures on record there: " + (", ".join(sorted(known)) if known else "none yet") + ".")
    return lines
