"""Screens that open over the map, like the inventory.

While a screen is open, it gets the keypresses instead of the map.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import tcod.event

from game.actions import Action, DropAction, EquipAction, FireAction, QuitAction, TravelAction, UseAction, article
from game.hunt import danger_pips

if TYPE_CHECKING:
    from game.engine import Engine

KeySym = tcod.event.KeySym

FRAME = (150, 136, 120)
TEXT = (233, 223, 204)
DIM = (150, 138, 122)
BG = (20, 18, 16)
HIGHLIGHT = (58, 46, 34)


def _key(name: str):
    for candidate in (name.upper(), name.lower()):
        if hasattr(KeySym, candidate):
            return getattr(KeySym, candidate)
    raise KeyError(name)


UP_KEYS = {KeySym.UP, KeySym.KP_8, _key("w")}          # (j and k dropped, v0.59.2: k is the skills window)
DOWN_KEYS = {KeySym.DOWN, KeySym.KP_2, _key("s")}
CLOSE_KEYS = {KeySym.ESCAPE, _key("i")}
DROP_KEY = _key("d")
EQUIP_KEY = _key("e")
USE_KEY = _key("u")


def draw_box(console, x: int, y: int, w: int, h: int, title: str = "", frame=None, title_fg=None) -> None:
    """A filled panel with a double-line border and an optional title."""
    frame = frame or FRAME
    console.rgb["bg"][x : x + w, y : y + h] = BG
    console.rgb["ch"][x : x + w, y : y + h] = ord(" ")
    console.print(x, y, "╔" + "═" * (w - 2) + "╗", fg=frame, bg=BG)
    for row in range(y + 1, y + h - 1):
        console.print(x, row, "║", fg=frame, bg=BG)
        console.print(x + w - 1, row, "║", fg=frame, bg=BG)
    console.print(x, y + h - 1, "╚" + "═" * (w - 2) + "╝", fg=frame, bg=BG)
    if title:
        console.print(x + 2, y, f" {title} ", fg=title_fg or TEXT, bg=BG)


TIP_FRAME = (110, 175, 170)    # tips (how to play) wear a sea-glass frame; story scenes the usual one (v0.66.0)


def fit_window(console, list_len: int, extra: list, top: int = 3) -> tuple[int, int, list]:
    """Size a list window: `top` rows above the list (border, tabs, gap), the list,
    a gap, the `extra` lines (details, notices) in full, a gap, the help line, the border.
    Returns (height, visible list rows, extra lines). The list gives way first (down
    to 3 rows); only if that's not enough are the extra lines cut, ending in "..."."""
    max_h = console.height - 2
    room = max_h - top - len(extra) - 4
    list_len = max(list_len, 1)
    visible = max(min(3, list_len), min(list_len, room))  # short lists only take what they need
    if top + visible + len(extra) + 4 > max_h:
        keep = max(1, max_h - top - visible - 4)
        extra = extra[:keep]
        text, color = extra[-1]
        extra[-1] = (text[:-3] + "..." if text else "...", color)   # (… isn't in the font: v0.64.0)
    return top + visible + len(extra) + 4, visible, extra


def wrapped(text: str, width: int, color) -> list:
    return [(line, color) for line in textwrap.wrap(text, width)]


class InventoryScreen:
    """The bag. (Since v0.69.0, user: what's equipped is out of the bag, in the equipment window, e;
    Tab switches to it.)"""

    def __init__(self) -> None:
        self.selected = 0

    @staticmethod
    def rows(engine) -> list:
        """("item", index) for each thing in the bag."""
        return [("item", i) for i in range(len(engine.player.inventory.items))]

    def handle(self, event: tcod.event.Event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        if event.sym in CLOSE_KEYS:
            engine.screen = None
            return None
        if event.sym == KeySym.TAB:
            engine.screen = EquipmentScreen()
            return None
        if not rows:
            return None
        if event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(rows)
            return None
        if event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(rows)
            return None
        self.selected = min(self.selected, len(rows) - 1)
        kind, i = rows[self.selected]
        if event.sym == DROP_KEY:
            return DropAction(i)
        if event.sym == EQUIP_KEY:
            return EquipAction(i)
        if event.sym == USE_KEY:
            return UseAction(i)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        p = engine.player
        inv = p.inventory
        items = inv.items
        rows = self.rows(engine)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        w = min(area_w - 2, 48)

        if rows:
            item = items[rows[self.selected][1]]
            extra = wrapped(item_details(item, engine), w - 4, DIM)
        else:
            extra = []
        lines = [(r, it.label, it.type.glyph, it.type.color, TEXT) for r, it in enumerate(items)]
        if not lines:
            lines = [(None, "You carry nothing.", "", DIM, DIM)]

        h, list_rows, extra = fit_window(console, len(lines), extra, top=2)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, f"Inventory {inv.used}/{inv.capacity}")
        # A carousel (user, v0.93.1): the selected item on the top row, the rest of the bag following
        # it and wrapping round to the start, each shown once.
        here = next((n for n, line in enumerate(lines) if line[0] == self.selected), 0)
        shown = [lines[(here + k) % len(lines)] for k in range(min(list_rows, len(lines)))]
        for row, (r, text, glyph, gcolor, tcolor) in enumerate(shown):
            bg = HIGHLIGHT if r is not None and r == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, y + 2 + row] = bg
            if glyph:
                console.print(x + 2, y + 2 + row, glyph, fg=gcolor, bg=bg)
            console.print(x + (4 if r is not None else 2), y + 2 + row, text[: w - 7], fg=tcolor, bg=bg)
        for row, (text, color) in enumerate(extra):
            console.print(x + 2, y + 2 + list_rows + 1 + row, text, fg=color, bg=BG)
        keys = "↑↓  e equip  u use  d drop  Tab equipment"
        console.print(x + 2, y + h - 2, keys[: w - 4], fg=DIM, bg=BG)


def item_details(item, engine: "Engine") -> str:
    """An item's description, worth and numbers, for the inventory and equipment windows."""
    worth = item_worth(item, engine)
    details = f"{worth} {item.type.description}" if item.type.rarity else f"{item.type.description} {worth}"
    props = item.type.properties
    if "damage" in props:
        details += f" Damage {props['damage']}."
    if "armor" in props and not item.type.rarity:
        from game import gear
        details += f" {gear.SLOT_NAMES[gear.armour_slot(item.type)]} armour {props['armor']}."
    if "heal" in props and not item.type.rarity:
        details += f" Heals {props['heal']}."
    from game import gear
    if gear.has_tier(item):                       # (v0.75.0)
        bonus = gear.tier_text(item)
        details += f" Tier +{item.tier}" + (f": {bonus}." if bonus else ".")
        if item.traits:
            details += " Traits: " + "; ".join(gear.trait_line(item, t) for t in item.traits) + "."
        elif item.tier < gear.TRAIT_EVERY:
            details += f" At +{gear.TRAIT_EVERY} it takes on a trait."
    return details


GEAR_SLOTS = (("weapon", "Weapon", "bare hands"), ("head", "Head", "nothing"), ("chest", "Chest", "nothing"),
              ("legs", "Legs", "nothing"), ("windcatcher", "Windcatcher", "none"))   # (head and legs: v0.75.0)
TACKLE_ROWS = (("rod", "Rod", "the best in your pack"), ("reel", "Reel", "by hand"), ("line", "Line", "the rod's cord"),
               ("hook", "Hook", "a small hook"), ("float", "Float", "none"))           # (v0.96.0, game/fishing.py)
SLOT_INFO = {s: (label, empty) for s, label, empty in GEAR_SLOTS + TACKLE_ROWS}


def gear_stat(item, engine: "Engine") -> list[tuple[str, tuple]]:
    """The short numbers beside an equipped thing: pieces of (text, colour)."""
    from game.engine import JODEBRIS, JODEBRIS_LOW
    t = item.type
    props = t.properties
    if props.get("windcatcher"):                       # a bar, never numbers (user, v0.41.1)
        share = max(0.0, min(1.0, item.jodebris / item.capacity)) if item.capacity else 0.0
        fill = round(share * 10)
        low = share <= 0.25
        return [("█" * fill, JODEBRIS_LOW if low else JODEBRIS), ("░" * (10 - fill), (100, 90, 78))]
    from game import gear
    if t.kind == "tackle" and props.get("tackle_slot"):
        T = item.tier
        sl = props["tackle_slot"]
        if sl == "rod":
            text = f"reach {props.get('reach', 2) + T // 5}, strain {props.get('power', 40) + 3 * T}"
        elif sl == "reel":
            text = f"reel {props.get('retrieve', 2.5) + 0.1 * T:.1f}, drag {props.get('drag', 0) + T}%, line {props.get('capacity', 26) + T}"
        elif sl == "line":
            text = f"strength {props.get('strength', 20) + 3 * T}, " + ["unseen", "faint", "plain"][min(2, props.get('visibility', 2))]
        elif sl == "hook":
            from game import fishing
            text = f"{fishing.SIZE_NAMES.get(props.get('size', 1), '')}, hold {props.get('hold', 0) + 2 * T}%"
        else:
            text = props.get("float", "float") + (f", +{props.get('window')} to strike" if props.get("window") else "") \
                + (f", +{props.get('bite', 0) + 2 * T}% bites" if props.get("bite", 0) + 2 * T else "")
        return [(text, DIM)]
    if t.kind == "weapon":
        text = props.get("damage", "")
        if gear.damage(item):
            text += f"+{gear.damage(item)}"
        if "range" in props:
            text += f", range {props['range']}"
        return [(text, DIM)]
    if t.kind == "armor":
        text = f"armour {props.get('armor', 0) + gear.armour(item)}"
        if gear.max_hp(item):
            text += f", +{gear.max_hp(item)} HP"
        return [(text, DIM)]
    if t.working:
        parts = [f"{label} +{props[k]}" for k, label in (("light", "light"), ("armor", "armour"),
                                                        ("accuracy", "accuracy"), ("evasion", "evasion")) if k in props]
        if props.get("use"):
            from game import artifacts
            parts.append(f"use {artifacts.uses_left(engine.player, t)} left")
        return [(", ".join(parts), DIM)]
    return []


class EquipmentScreen:
    """What the Hunter has on, slot by slot (user, v0.69.0): weapon, armour, windcatcher, then the
    artifact slots. e takes off, u uses an artifact, Enter picks something from the bag for the
    slot (swapping), Tab goes to the bag. Equipping takes a turn, as in the inventory."""

    def __init__(self) -> None:
        self.selected = 0
        self.picking = None          # None, or the bag indices that fit the selected slot
        self.pick = 0
        self.notice = ""

    @staticmethod
    def rows(engine) -> list:
        from game import attunement
        attunement.sync_slots(engine.player)
        return ([("gear", s) for s, _, _ in GEAR_SLOTS] + [("art", n) for n in range(len(engine.player.artifact_slots))]
                + [("gear", s) for s, _, _ in TACKLE_ROWS])

    @staticmethod
    def fits(engine, row) -> list[int]:
        p = engine.player
        kind, slot = row
        return [i for i, it in enumerate(p.inventory.items)
                if (p.goes_in_artifact_slot(it) if kind == "art" else p.slot_for(it) == slot)]

    def held(self, engine, row):
        kind, slot = row
        return engine.player.equipped.get(slot) if kind == "gear" else engine.player.artifact_slots[slot]

    def handle(self, event: tcod.event.Event, engine: "Engine") -> Action | None:
        from game.actions import ArtifactSlotAction, UnequipAction
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        self.selected = min(self.selected, len(rows) - 1)
        row = rows[self.selected]
        if self.picking is not None:                 # choosing something from the bag
            if event.sym == KeySym.ESCAPE:
                self.picking = None
            elif event.sym in UP_KEYS:
                self.pick = (self.pick - 1) % len(self.picking)
            elif event.sym in DOWN_KEYS:
                self.pick = (self.pick + 1) % len(self.picking)
            elif event.sym in CONFIRM_KEYS:
                index = self.picking[self.pick]
                self.picking = None
                return EquipAction(index, row[1] if row[0] == "art" else None)
            return None
        self.notice = ""
        if event.sym == KeySym.ESCAPE:      # (e takes off in here; Esc closes)
            engine.screen = None
        elif event.sym == KeySym.TAB:
            engine.screen = InventoryScreen()
        elif event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(rows)
        elif event.sym in CONFIRM_KEYS:
            fits = self.fits(engine, row)
            if fits:
                self.picking, self.pick = fits, 0
            else:
                self.notice = "Nothing in your pack fits here."
        elif event.sym == EQUIP_KEY:
            if self.held(engine, row) is None:
                self.notice = "Nothing's there."
            elif row[0] == "gear":
                return UnequipAction(row[1])
            else:
                return ArtifactSlotAction(row[1], "unequip")
        elif event.sym == USE_KEY and row[0] == "art" and self.held(engine, row) is not None:
            return ArtifactSlotAction(row[1], "use")
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        p = engine.player
        rows = self.rows(engine)
        self.selected = min(self.selected, len(rows) - 1)
        w = min(area_w - 2, 58)
        label_w = 13

        # The lines: (row index or None, label, glyph, glyph colour, name, name colour, stat pieces)
        lines = []
        if self.picking is None:
            for r, (kind, slot) in enumerate(rows):
                if kind == "art" and slot == 0:
                    lines.append((None, f"Artifacts ({len(p.equipped_artifacts)}/{len(p.artifact_slots)})",
                                  "", ACCENT, "", ACCENT, []))
                if kind == "gear" and slot == "rod":
                    lines.append((None, "Tackle", "", ACCENT, "", ACCENT, []))
                item = self.held(engine, (kind, slot))
                label = SLOT_INFO[slot][0] if kind == "gear" else f"  {slot + 1}"
                empty = SLOT_INFO[slot][1] if kind == "gear" else "(empty)"
                if item is None:
                    lines.append((r, label, "·", DIM, empty, DIM, []))
                else:
                    lines.append((r, label, item.type.glyph, item.type.color, item.label, TEXT,
                                  gear_stat(item, engine)))
            sel_item = self.held(engine, rows[self.selected])
            title = "Equipment"
            keys = "↑↓  e take off  u use  Enter swap  Tab pack  Esc"
        else:
            kind, slot = rows[self.selected]
            name = SLOT_INFO[slot][0] if kind == "gear" else f"artifact slot {slot + 1}"
            for n, i in enumerate(self.picking):
                it = p.inventory.items[i]
                lines.append((n, "", it.type.glyph, it.type.color, it.label, TEXT, gear_stat(it, engine)))
            sel_item = p.inventory.items[self.picking[self.pick]]
            title = f"Equip: {name.lower() if kind == 'gear' else name}"
            keys = "↑↓ select  Enter equip  Esc back"
            label_w = 0
        extra = wrapped(item_details(sel_item, engine), w - 4, DIM) if sel_item is not None else \
            [("Empty. Enter picks something from your pack for it.", DIM)]
        if self.notice:
            extra = [(self.notice, ACCENT)] + extra
        h, list_rows, extra = fit_window(console, len(lines), extra, top=2)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, title)
        current = self.selected if self.picking is None else self.pick
        here = next((n for n, line in enumerate(lines) if line[0] == current), 0)
        first = max(0, min(here - list_rows // 2, len(lines) - list_rows))
        for row, (r, label, glyph, gcolor, name, ncolor, stat) in enumerate(lines[first : first + list_rows]):
            yy = y + 2 + row
            bg = HIGHLIGHT if r is not None and r == current else BG
            console.rgb["bg"][x + 1 : x + w - 1, yy] = bg
            if r is None:                                   # a heading
                console.print(x + 2, yy, label[: w - 4], fg=gcolor, bg=bg)
                continue
            cx = x + 2
            if label_w:
                console.print(cx, yy, label, fg=DIM, bg=bg)
                cx += label_w
            console.print(cx, yy, glyph, fg=gcolor, bg=bg)
            stat_w = sum(len(t) for t, _ in stat)
            room = x + w - 2 - (cx + 2) - (stat_w + 1 if stat_w else 0)
            console.print(cx + 2, yy, name[:max(0, room)], fg=ncolor, bg=bg)
            sx = x + w - 2 - stat_w
            for text, color in stat:
                console.print(sx, yy, text, fg=color, bg=bg)
                sx += len(text)
        for row, (text, color) in enumerate(extra):
            console.print(x + 2, y + 2 + list_rows + 1 + row, text, fg=color, bg=BG)
        console.print(x + 2, y + h - 2, keys[: w - 4], fg=DIM, bg=BG)


def item_worth(item, engine: "Engine") -> str:
    """The value line under an item's description (artifacts get their own)."""
    from game import artifacts
    t = item.type
    if t.is_broken_artifact:
        known = "" if t.identified else " Use (u) to study it."
        return f"{t.rarity.name} Tower Artifact, broken.{known}"
    if t.properties.get("windcatcher"):
        from game.artifacts import charge_words
        return (f"{t.rarity.name} windcatcher, {charge_words(item)}. "
                "Equip it (e) to power your artifacts out in the miasma; it drains as turns pass "
                "and refills in Bytorsskug.")
    if t.working:
        extra = ""
        if "uses_per_hunt" in t.properties:
            extra = f" Uses left this hunt: {artifacts.uses_left(engine.player, t)}."
        where = "" if any(item is i for i in engine.player.equipped_artifacts) else " Works only when equipped (e)."
        return f"{t.rarity.name} Tower Artifact, working. {artifacts.effect_text(t)}{extra}{where}"
    if t.writing:
        from game import library
        return f"The Academy librarian would pay {library.payment(engine, t)} shards for it."
    if item.catch is not None:                  # (v0.94.0)
        from game import fishing
        c = item.catch
        q = fishing.data()["quirks"].get(c.get("quirk", ""), {}).get("note", "")
        water = fishing.data()["waters"].get(c.get("water", ""), {}).get("name", "")
        return (f"{fishing.weight_text(c['kg'])}, {item.slots} slot{'s' if item.slots > 1 else ''}."
                + (f" {q}" if q else "") + (f" From {water}." if water else "")
                + f" Worth {fishing.value(item)} shards; the fishmonger pays 70% of that, the tackleman half."
                + " u: gut it.")
    if item.trophy is not None:                 # (v0.61.0)
        from game import trophies
        rec = trophies.state(engine)["records"].get(t.properties["monster"])
        q = item.trophy.get("quirk", "")
        note = (" " + trophies.data()["quirks"][q]["note"]) if q in trophies.data()["quirks"] else ""
        mark = (f"The record is {trophies.weight_text(rec['kg'])} ({rec['who']})." if rec
                else "There's no record for one yet.")
        return f"{trophies.weight_text(item.trophy['kg'])}, {item.slots} slot{'s' if item.slots > 1 else ''}.{note} {mark}"
    from game import gear
    value = gear.value(item)
    return f"Worth {value} shard{'' if value == 1 else 's'}{' each' if item.count > 1 else ''}."


CONFIRM_KEYS = {KeySym.RETURN, KeySym.KP_ENTER}
NUMBER_KEYS = {getattr(KeySym, f"N{i}"): i - 1 for i in range(1, 10)}  # 1-9 pick a choice
DIGIT_KEYS = {getattr(KeySym, f"N{i}"): i for i in range(0, 10) if hasattr(KeySym, f"N{i}")}   # 0-9 (travel-to)
ACCENT = (240, 160, 80)


def spaced(text: str) -> str:
    """'HUNT' -> 'H U N T': letter-spaced capitals for headings."""
    return " ".join(text.upper())


class ContractBoardScreen:
    """Contracts. With no region: the Guild's contracts board (v0.44.0); Enter takes one
    as your contract. With a region: that place's contracts; Enter sets out."""

    def __init__(self, region, contracts, taken: dict | None = None) -> None:
        self.region = region
        self.contracts = contracts
        self.taken = taken or {}     # contract seed -> the rival Hunter who took it today
        self.selected = 0

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(self.contracts)
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(self.contracts)
        elif event.sym in CONFIRM_KEYS:
            from game import ranks
            contract = self.contracts[self.selected]
            if contract.seed in self.taken and not ranks.privilege(engine.player, "first_pick", False):
                engine.log(f"{self.taken[contract.seed]} has already taken that contract.")
                return None
            closed = None if contract.job else ranks.contract_closed(engine.player, contract)
            if closed:
                engine.log(f"That contract is posted for {ranks.plural(closed)} and above.")
                return None
            from game import story
            held = story.only(engine, "contracts") if self.region is None else None
            if held and contract.story != held:
                engine.log("The clerk asked you to take the one marked for you first.")
                return None
            if self.region is None:        # the Guild's board: the posting becomes your contract
                from game import postings
                engine.screen = None
                engine.log(postings.take(engine, contract))
            else:
                engine.screen = departure_card(contract, engine)
        return None

    @staticmethod
    def blurb(cat, c, engine=None) -> str:
        if c.story and engine is not None:
            from game import story
            return story.fill(engine, engine.story_data.contracts[c.story].get("description", ""))
        if c.job:
            return f"{c.job}. No artifact to bring back: go out, do the job, come home."
        if engine is not None and c.region.place:
            from game import postings
            return postings.describe(engine, c)
        return cat[c.artifact_id].description

    def details(self, engine, w: int) -> list:
        """The selected contract's lines below the list: (text, colour)."""
        from game import ranks
        cat = engine.catalogue
        c = self.contracts[self.selected]
        if c.story:
            head = [(engine.story_data.contracts.get(c.story, {}).get("heading", "☼ A key hunt"), ACCENT)]
        elif c.job:
            head = [("Odd job", ACCENT)]
        elif c.recover:
            head = [("A recovery", ACCENT)]
        else:
            head = [(cat[c.artifact_id].name.capitalize(), TEXT)]
        desc = wrapped(self.blurb(cat, c, engine), w - 4, DIM)
        from game import story as _story
        tail = [(f"{_story.words_shown(engine, c)}  {danger_pips(c.danger)}  {c.depth} areas", TEXT)]
        closed = None if c.job else ranks.contract_closed(engine.player, c)
        from game import story
        held = story.only(engine, "contracts") if self.region is None else None
        if closed:
            tail.append((f"Posted for {ranks.plural(closed)} and above", WARN))
        elif held and c.story != held:
            tail += wrapped("The clerk asked you to take the one marked for you first.", w - 4, WARN)
        elif c.seed in self.taken:
            pick = " (you outrank them: take it if you like)" if ranks.privilege(engine.player, "first_pick", False) else ""
            tail += wrapped(f"Taken by {self.taken[c.seed]}{pick}", w - 4, WARN)
        return head, desc, tail

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import ranks
        cat = engine.catalogue
        w = min(area_w - 2, 58)
        head, desc, tail = self.details(engine, w)
        room = console.height - 2 - (len(self.contracts) + 6)      # rows left for the details
        if len(head) + len(desc) + len(tail) > room:               # cut the description to fit, ending in "…"
            keep = max(0, room - len(head) - len(tail))
            desc = desc[:keep]
            if desc:
                desc[-1] = (desc[-1][0][: w - 7] + "...", desc[-1][1])
        detail = (head + desc + tail)[: max(0, room)]
        h = min(console.height - 2, len(self.contracts) + 6 + len(detail))
        x, y = (area_w - w) // 2, max(0, (console.height - h) // 2)
        if self.region is None:
            draw_box(console, x, y, w, h, "The Guild: Contracts")
            mine = engine.player.contract
            head = f"Yours: {mine.title(cat)}" if mine else "Take one, then choose its words at the Wayfinder."
            console.print(x + 2, y + 1, head[: w - 4], fg=DIM, bg=BG)
        else:
            draw_box(console, x, y, w, h, f"{self.region.name}: Contracts")
        for i, c in enumerate(self.contracts):
            row = y + 3 + i
            bg = HIGHLIGHT if i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            pips = danger_pips(c.danger)
            from game import story
            held = story.only(engine, "contracts") if self.region is None else None
            gone = ((c.seed in self.taken and not ranks.privilege(engine.player, "first_pick", False))
                    or (not c.job and ranks.contract_closed(engine.player, c))
                    or (held is not None and c.story != held))
            label = ("☼ " if c.story else "") + c.title(cat)
            console.print(x + 2, row, label[: w - 10], fg=CANT if gone else (ACCENT if c.story else TEXT), bg=bg)
            console.print(x + w - 2 - len(pips), row, pips, fg=CANT if gone else ACCENT, bg=bg)
        top = y + 4 + len(self.contracts)
        for i, (line, color) in enumerate(detail):
            console.print(x + 2, top + i, line[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 1, (" ↑↓ choose  Enter take  Esc leave " if self.region is None
                                         else " ↑↓ choose  Enter accept  Esc leave ")[: w - 4], fg=DIM, bg=BG)


class TitleCardScreen:
    """A full-screen announcement. Any key continues."""

    def __init__(self, heading: str, lines: list[tuple[str, tuple]], on_continue=None) -> None:
        self.heading = heading
        from game import named
        self.lines = [(named.fix(t), c) for t, c in lines]   # (text, colour) pairs, centred
        self.on_continue = on_continue

    def handle(self, event, engine: "Engine") -> Action | None:
        if isinstance(event, tcod.event.KeyDown):
            engine.screen = None
            if self.on_continue:
                self.on_continue(engine)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        console.rgb["bg"][:area_w, :] = (10, 9, 8)
        console.rgb["ch"][:area_w, :] = ord(" ")
        block = [("─── ♦ ───", FRAME), ("", TEXT), (spaced(self.heading), ACCENT), ("", TEXT)]
        width = max(20, min(area_w - 4, 60))   # long lines (a story's words) wrap rather than run off the edge
        for text, color in self.lines:
            block += [(line, color) for line in (textwrap.wrap(text, width) or [""])]
        block += [("", TEXT), ("─── ♦ ───", FRAME), ("", TEXT), ("press any key", DIM)]
        top = max(0, (console.height - len(block)) // 2)
        for i, (text, color) in enumerate(block[: console.height]):
            text = text[: area_w - 2]
            console.print((area_w - len(text)) // 2, top + i, text, fg=color, bg=(10, 9, 8))


class ConfirmScreen:
    """A yes/no question. y or Enter says yes; n or Esc says no."""

    def __init__(self, question: str, on_yes, on_no=None) -> None:
        self.question = question
        self.on_yes = on_yes
        self.on_no = on_no

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if event.sym in CONFIRM_KEYS or event.sym == _key("y"):
            engine.screen = None
            self.on_yes(engine)
        elif event.sym in (KeySym.ESCAPE, _key("n")):
            engine.screen = None
            if self.on_no:
                self.on_no(engine)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        w = min(area_w - 2, 46)
        lines = textwrap.wrap(self.question, w - 4)
        h = len(lines) + 4
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h)
        for i, line in enumerate(lines):
            console.print(x + 2, y + 1 + i, line, fg=TEXT, bg=BG)
        console.print(x + 2, y + h - 2, "y yes   n no", fg=DIM, bg=BG)


CRAWL_FILE = Path(__file__).resolve().parent.parent / "data" / "crawl.txt"


def crawl_paragraphs(path=None) -> list[str]:
    """The opening crawl's paragraphs (data/crawl.txt: ";" lines are comments, a blank line
    breaks paragraphs, lines within a paragraph are joined)."""
    text = Path(path or CRAWL_FILE).read_text(encoding="utf-8") if Path(path or CRAWL_FILE).exists() else ""
    paras, cur = [], []
    for line in text.splitlines():
        if line.startswith(";"):
            continue
        if line.strip():
            cur.append(line.strip())
        elif cur:
            paras.append(" ".join(cur)); cur = []
    if cur:
        paras.append(" ".join(cur))
    return paras


class CrawlScreen:
    """The opening crawl (user, v0.51.0): the text rises slowly from the bottom of the
    screen. Any key speeds it up (again to slow it), Esc skips it. When the last line has
    gone off the top, on_done(engine) runs. Driven by tick(engine, dt), which main.py calls
    while `animating` is true."""

    animating = True
    SPEED = 1.0      # rows a second
    FAST = 6.0
    WIDTH = 60       # widest the text runs
    BG = (6, 6, 8)

    def __init__(self, on_done, paragraphs=None) -> None:
        self.on_done = on_done
        self.paragraphs = crawl_paragraphs() if paragraphs is None else paragraphs
        self.pos = 0.0           # rows risen so far
        self.fast = False
        self.done = False
        self.height = 24         # updated by render
        self.lines: list[str] = []
        self.wrapped_for = None

    def wrap(self, width: int) -> list[str]:
        if self.wrapped_for != width:
            out = []
            for i, para in enumerate(self.paragraphs):
                if i:
                    out.append("")
                out += textwrap.wrap(para, width) or [""]
            self.lines, self.wrapped_for = out, width
        return self.lines

    def finish(self, engine) -> None:
        if not self.done:
            self.done = True
            self.animating = False
            engine.screen = None
            self.on_done(engine)

    def tick(self, engine, dt: float) -> None:
        if self.done:
            return
        self.pos += dt * (self.FAST if self.fast else self.SPEED)
        if self.pos > self.height + len(self.lines) + 1:
            self.finish(engine)

    def handle(self, event, engine) -> Action | None:
        if isinstance(event, tcod.event.KeyDown):
            if event.sym == KeySym.ESCAPE:
                self.finish(engine)
            else:
                self.fast = not self.fast
        return None

    def render(self, console, engine, area_w: int) -> None:
        console.rgb["bg"][:, :] = self.BG
        console.rgb["ch"][:, :] = ord(" ")
        self.height = console.height
        w = min(console.width - 4, self.WIDTH)
        lines = self.wrap(w)
        x = (console.width - w) // 2
        top = console.height - int(self.pos)
        for i, line in enumerate(lines):
            y = top + i
            if 0 <= y < console.height - 1:
                # fade towards the top and bottom edges
                edge = min(y, console.height - 2 - y)
                k = min(1.0, 0.35 + edge / 5)
                fg = tuple(int(c * k) for c in (226, 210, 178))
                console.print(x + (w - len(line)) // 2, y, line, fg=fg, bg=self.BG)
        hint = "any key: faster   Esc: skip" if not self.fast else "any key: slower   Esc: skip"
        console.print(console.width - len(hint) - 1, console.height - 1, hint, fg=FRAME, bg=self.BG)


class ArtifactScreen:
    """The Wayfinder (v0.44.0): choose three words, one per slot (danger, land,
    feature), and it carries you to the place they make. Each slot can also be left
    on "anything". Takes no time until you go."""

    def __init__(self, engine: "Engine") -> None:
        from game import keywords
        self.cols = list(keywords.SLOTS)
        self.col = 0
        # start on the first known word in each slot ("anything" is just above it)
        self.picks = {slot: 1 if len(self.options(engine, slot)) > 1 else 0 for slot in self.cols}
        self.notice = ""
        c = engine.player.contract
        if c is not None:
            self.use_words(engine, c.region.place)
        elif engine.player.jobs:          # no contract: start on the words of a bounty you hold (v0.54.0)
            job = next((j for j in engine.player.jobs if not j.done), engine.player.jobs[0])
            if job.region in engine.regions:
                self.use_words(engine, engine.regions[job.region].place)

    def options(self, engine, slot: str) -> list:
        """(word id, label, allowed) for a column: "anything" first, then known words."""
        from game import keywords
        out = [(keywords.ANY, "(anything)", True)]
        words = keywords.known(engine, slot)
        if slot == "danger":
            words.sort(key=lambda w: (int(w.data["danger"]), w.text))
        else:
            words.sort(key=lambda w: w.text)
        out += [(w.id, w.shown, keywords.allowed(engine, w)) for w in words]
        return out

    def fits(self, engine, slot: str, wid: str) -> bool:
        """Does this word go with what's chosen in the other slots? (Danger and land can't both
        be verbs, data/keywords.json; incompatible words are greyed and skipped over.)"""
        from game import keywords
        if wid == keywords.ANY or slot == "feature":
            return True
        kw = engine.regions.keywords
        other = self.options(engine, "land" if slot == "danger" else "danger")[self.picks["land" if slot == "danger" else "danger"]][0]
        if other == keywords.ANY:
            return True
        return kw.valid(wid, other) if slot == "danger" else kw.valid(other, wid)

    def use_words(self, engine, words) -> None:
        for slot, wid in zip(self.cols, words):
            ids = [o[0] for o in self.options(engine, slot)]
            if wid in ids:
                self.picks[slot] = ids.index(wid)

    def choice(self, engine) -> list:
        return [self.options(engine, slot)[self.picks[slot]] for slot in self.cols]

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        slot = self.cols[self.col]
        opts = self.options(engine, slot)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
            engine.log("You step back from the Wayfinder.")
        elif event.sym in (KeySym.LEFT, KeySym.KP_4, _key("a"), _key("h")):
            self.col = (self.col - 1) % len(self.cols)
        elif event.sym in (KeySym.RIGHT, KeySym.KP_6, KeySym.TAB, _key("d"), _key("l")):
            self.col = (self.col + 1) % len(self.cols)
        elif event.sym in UP_KEYS or event.sym in DOWN_KEYS:
            step = -1 if event.sym in UP_KEYS else 1
            i = self.picks[slot]
            for _ in range(len(opts)):          # skip words that don't go with the other slots
                i = (i + step) % len(opts)
                if self.fits(engine, slot, opts[i][0]):
                    break
            self.picks[slot] = i
        elif event.sym == _key("c") and engine.player.contract is not None:
            self.use_words(engine, engine.player.contract.region.place)
            self.notice = "Your contract's words."
        elif event.sym in CONFIRM_KEYS:
            chosen = self.choice(engine)
            if not all(self.fits(engine, slot, wid) for slot, (wid, _, _) in zip(self.cols, chosen)):
                return None     # (can't happen by moving the cursor: those words are skipped)
            bad = [label for _, label, ok in chosen if not ok]
            if bad:
                from game import ranks
                self.notice = (f"The Guild hasn't cleared you for {bad[0]} places: "
                               f"you're a {ranks.of(engine.player)['name']}.")
                return None
            engine.screen = None
            engine.set_out(tuple(wid for wid, _, _ in chosen))
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import keywords, postings
        from game.hunt import danger_pips
        w = min(area_w - 2, 60)
        colw = (w - 4) // 3
        lists = [self.options(engine, slot) for slot in self.cols]
        rows = max(len(l) for l in lists)
        chosen = self.choice(engine)
        info = []
        ids = [wid for wid, _, _ in chosen]
        if keywords.ANY not in ids and not engine.regions.keywords.valid(ids[0], ids[1]):
            info.append((f"{chosen[0][1]}{chosen[1][1]}{chosen[2][1]}", CANT))
        elif all(wid != keywords.ANY for wid, _, _ in chosen):
            place = engine.regions.place(*(wid for wid, _, _ in chosen))
            light = "lit" if place.light == "lit" else "dark"
            info.append((f"{place.name}", ACCENT))
            info.append((f"Danger {danger_pips(place.danger[0])}  {place.depth} areas  {place.style_text()}, {light}", TEXT))
            if postings.matches(engine, place):
                info += wrapped("Your contract is here: " + engine.player.contract.title(engine.catalogue), w - 4, TEXT)
            for job in engine.player.jobs:
                if job.region == place.id and not job.done:
                    info += wrapped("Your bounty is here: " + job.label(engine).removeprefix("☼ "), w - 4, TEXT)
        else:
            info.append(("The Wayfinder chooses from the words you know.", DIM))
        c = engine.player.contract
        here = "/".join(ids) if keywords.ANY not in ids else None
        if c is not None and not (here is not None and here in engine.regions
                                  and postings.matches(engine, engine.regions[here])):
            from game import story as _story
            info += wrapped(f"Your contract: {_story.words_shown(engine, c)} (c to choose those words).", w - 4, DIM)
        if self.notice:
            info += wrapped(self.notice, w - 4, WARN)
        h = min(console.height - 2, rows + 7 + len(info))
        x, y = (area_w - w) // 2, max(0, (console.height - h) // 2)
        draw_box(console, x, y, w, h, "The Wayfinder")
        room = max(1, (y + h - 2 - len(info)) - (y + 2))      # word rows that fit
        mid = y + 2 + (room - 1) // 2                          # the picks' row, the same in every column
        for i, slot in enumerate(self.cols):
            cx = x + 2 + i * colw
            console.print(cx, y + 1, keywords.SLOT_NAMES[slot], fg=ACCENT if i == self.col else DIM, bg=BG)
            # A carousel (user, v0.70.1): the pick sits on the middle row and the words wheel round
            # it, wrapping from the last to the first, fading with distance. Each word shows once.
            n = len(lists[i])
            above, below = min((room - 1) // 2, (n - 1) // 2), min(room // 2, n // 2)
            for k in range(-above, below + 1):
                j = (self.picks[slot] + k) % n
                wid, label, ok = lists[i][j]
                row = mid + k
                sel = k == 0
                bg = HIGHLIGHT if sel and i == self.col else BG
                if sel:
                    console.rgb["bg"][cx - 1 : cx - 1 + colw, row] = bg
                near = TEXT if sel else (DIM if abs(k) <= 2 else (118, 108, 96))
                fg = near if ok and self.fits(engine, slot, wid) else (82, 74, 66)   # (unfit: well dimmed)
                console.print(cx, row, (("►" if sel else " ") + label)[: colw - 1], fg=fg, bg=bg)
        top = y + h - 2 - len(info)
        for k, (line, color) in enumerate(info):
            console.print(x + 2, top + k, line[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 1, " ←→ slot  ↑↓ word  Enter go  Esc "[: w - 4], fg=DIM, bg=BG)


def place_traits(region, engine: "Engine") -> list[str]:
    """What the words make of a place (v0.100.9, user: the departure card should say): its terrain, its
    light, and each thing a word changes."""
    out = []
    terrain = region.style_text()
    out.append(f"Terrain: {terrain}" + (", a different one each area" if len(region.all_styles()) > 1 else ""))
    light = "lit" if region.light == "lit" else "dark: bring light"
    out.append(f"Light: {light}" + (", and it doesn't carry far" if region.sight < 1 else ""))
    def beasts(mid):
        t = engine.monster_types.get(mid)
        n = t.name if t else mid.replace("_", " ")
        return n + ("es" if n.endswith(("s", "sh", "ch")) else "s")
    if region.only:
        out.append(f"Nothing lives here but {beasts(region.only)}")
    if region.creatures > 1:
        out.append("Many more creatures than usual" if region.creatures >= 2 else "More creatures than usual")
    elif region.creatures < 1:
        out.append("Fewer creatures than usual")
    if region.favour and not region.only:
        out.append(f"Thick with {beasts(region.favour)}")
    if region.alert:
        out.append("The creatures are awake and watchful")
    if region.time > 1:
        out.append("Heavy going: every step takes " + ("two turns" if region.time == 2 else f"{region.time} turns"))
    if region.rarity_up > 0:
        out.append("Richer finds than its danger")
    if region.rarity_chance > 0:
        out.append("The prize may be a rarity higher")
    if region.writings > 1:
        out.append("Writings turn up more often")
    for iid, _lo, _hi in region.items:
        t = engine.catalogue.types.get(iid)
        many = t.label(2).split(" ", 1)[1] if t else iid
        out.append(f"{many.capitalize()} lying about")
    return out


def departure_card(contract, engine: "Engine") -> TitleCardScreen:
    cat = engine.catalogue
    region = contract.region
    lines = [
        (contract.title(cat), TEXT),
        ("", TEXT),
        (f"The Wayfinder carries you to {region.name}", DIM),
        (f"Danger {danger_pips(contract.danger)}   {contract.depth} areas deep", DIM),
    ]
    lines += [(t, DIM) for t in place_traits(region, engine)]
    return TitleCardScreen("The hunt begins", lines, on_continue=lambda e: e.begin_hunt(contract))


# ---- Menus ------------------------------------------------------------------------
class MenuScreen:
    """A list of choices. ↑↓ to pick, Enter to choose, Esc to go back."""

    title = ""

    def __init__(self) -> None:
        self.selected = 0
        self.notice = ""   # a line of feedback, e.g. why something can't be done

    def options(self, engine: "Engine") -> list[tuple[str, bool, object]]:
        """(label, enabled, what to do) for each choice."""
        raise NotImplementedError

    def on_escape(self, engine: "Engine"):
        return None

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        opts = self.options(engine)
        if event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(opts)
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(opts)
        elif event.sym == KeySym.ESCAPE:
            return self.on_escape(engine)
        elif event.sym in CONFIRM_KEYS:
            label, enabled, choose = opts[self.selected]
            if not enabled:
                self.notice = self.disabled_reason(label, engine)
                return None
            self.notice = ""
            return choose(engine)
        return None

    def disabled_reason(self, label: str, engine: "Engine") -> str:
        return "You can't do that right now."

    def draw_options(self, console, engine, x: int, y: int, w: int) -> None:
        for i, (label, enabled, _) in enumerate(self.options(engine)):
            bg = HIGHLIGHT if i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, y + i] = bg
            console.print(x + 2, y + i, label[: w - 4], fg=TEXT if enabled else DIM, bg=bg)

    def width(self, engine) -> int:
        return 40

    def render(self, console, engine: "Engine", area_w: int) -> None:
        opts = self.options(engine)
        w = min(area_w - 2, self.width(engine))
        notice = textwrap.wrap(self.notice, w - 4) if self.notice else []
        h = len(opts) + 4 + (len(notice) + 1 if notice else 0)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, self.title)
        self.draw_options(console, engine, x, y + 2, w)
        for i, line in enumerate(notice):
            console.print(x + 2, y + len(opts) + 3 + i, line, fg=ACCENT, bg=BG)


def describe(info: dict | None) -> str:
    """One line about what's in a save slot."""
    if info is None:
        return "empty"
    if info.get("damaged"):
        return "damaged"
    where = "on a hunt" if info.get("on_hunt") else info.get("where", "")
    when = info.get("date") or f"Pulse {info['day']}"
    return f"{info['name']}, Lv {info['level']}, {when}, {where}"


def describe_short(info: dict | None) -> str:
    """describe(), without the surname (every Hunter's is Hunters) or the date."""
    if info is None or info.get("damaged"):
        return describe(info)
    where = "on a hunt" if info.get("on_hunt") else info.get("where", "")
    name = info["name"].removesuffix(" Hunters")
    return f"{name}, Lv {info['level']}, {where}"


class TitleScreen(MenuScreen):
    """The first thing you see: continue, load, start a new Hunter, or quit."""

    def options(self, engine):
        auto = engine.saves.summary("autosave") if engine.saves else None
        can_continue = bool(auto) and not auto.get("damaged")
        if not self.placed:          # start on Continue when there's something to continue
            self.placed = True
            self.selected = 2 if can_continue else 0
        return [
            ("New Game", True, self.new_game),
            ("New Hunter", can_continue, self.new_hunter),
            ("Continue", can_continue, self.continue_game),
            ("Load game", True, lambda e: self.open(e, SlotScreen("load", back=self))),
            ("Sound", True, lambda e: setattr(e, "screen", SoundScreen(back=self))),
            ("Quit", True, lambda e: QuitAction()),
        ]

    def disabled_reason(self, label, engine):
        if label == "New Hunter":
            return "There's no world yet to send a new Hunter into. Start a New Game."
        return "There's no autosave to continue from."

    def new_hunter(self, engine):
        """A fresh Hunter in the autosave's world (user, v0.51.1). The current Hunter vanishes:
        no Hall, no gift, their things lost. Warned first."""
        auto = engine.saves.summary("autosave")
        name = auto["name"]

        def go(e):
            from game.saves import SaveError
            try:
                e.saves.load("autosave", e)
            except SaveError as err:
                e.screen = self
                self.notice = str(err)
                return
            e.vanish_hunter()
        engine.screen = ConfirmScreen(
            f"Start a new Hunter in this world? {name} will vanish: no place in the Hall of Hunters, "
            "and everything they carry is lost. (To retire them properly, see the guild clerk.)",
            on_yes=go, on_no=lambda e: setattr(e, "screen", self))

    def continue_game(self, engine):
        from game.saves import SaveError
        try:
            engine.saves.load("autosave", engine)
        except SaveError as err:
            self.notice = str(err)

    def __init__(self) -> None:
        super().__init__()
        self.placed = False      # start on Continue when there's an autosave

    def new_game(self, engine):
        """A factory reset (user, v0.51.0): a fresh world and a fresh Hunter, as if the game
        had never been played. The autosave goes (warned first); save slots are kept."""
        def begin(e):
            e.screen = CrawlScreen(lambda e2: e2.new_game())
        auto = engine.saves.summary("autosave") if engine.saves else None
        if auto and not auto.get("damaged"):
            engine.screen = ConfirmScreen(
                f"Start a new game? Everything in the autosave ({describe(auto)}) will be gone: "
                "the Hunter and the world. Games in save slots are kept.",
                on_yes=begin,
                on_no=lambda e: setattr(e, "screen", self),
            )
        else:
            begin(engine)

    def open(self, engine, screen):
        engine.screen = screen

    def render(self, console, engine, area_w):
        console.rgb["bg"][:, :] = (10, 9, 8)
        console.rgb["ch"][:, :] = ord(" ")
        cx = console.width // 2
        top = max(1, console.height // 2 - 8)
        for i, (text, color) in enumerate([
            ("─── ♦ ───", FRAME), ("", TEXT), (spaced("Tower Acquisition Guild"), ACCENT),
        ]):   # (v0.62.2, user: no city name on the title screen)
            text = text[: console.width - 2]
            console.print(cx - len(text) // 2, top + i, text, fg=color, bg=(10, 9, 8))
        w = min(console.width - 2, 60)
        x, y = cx - w // 2, top + 5
        opts = self.options(engine)
        for i, (label, enabled, _) in enumerate(opts):
            bg = HIGHLIGHT if i == self.selected else (10, 9, 8)
            console.rgb["bg"][x : x + w, y + i] = bg
            console.print(x + 2, y + i, label, fg=TEXT if enabled else DIM, bg=bg)
        auto = engine.saves.summary("autosave") if engine.saves else None
        if auto and not auto.get("damaged"):
            # (v0.68.2, user: the date, cut to "Light Duel: Erku", told you nothing; who and where instead)
            console.print(x + 14, y + 2, describe_short(auto)[: w - 16], fg=DIM,
                          bg=HIGHLIGHT if self.selected == 2 else (10, 9, 8))
        if self.notice:
            console.print(cx - len(self.notice[: w]) // 2, y + len(opts) + 1, self.notice[:w],
                          fg=ACCENT, bg=(10, 9, 8))
        from game.version import VERSION
        version = f"v{VERSION}"
        console.print(console.width - len(version) - 1, console.height - 1, version, fg=FRAME, bg=(10, 9, 8))


class GameMenuScreen(MenuScreen):
    """Esc during play."""

    title = "Menu"

    def options(self, engine):
        return [
            ("Resume", True, lambda e: setattr(e, "screen", None)),
            ("Save game", engine.can_save_here, lambda e: setattr(e, "screen", SlotScreen("save", back=self))),
            ("Load game", True, lambda e: setattr(e, "screen", SlotScreen("load", back=self))),
            ("Sound", True, lambda e: setattr(e, "screen", SoundScreen(back=self))),
            ("Save and quit", True, lambda e: QuitAction()),
        ]

    def disabled_reason(self, label, engine):
        return "You can only save in a safe place, like Bytorsskug. (Your progress is autosaved.)"

    def on_escape(self, engine):
        engine.screen = None


class ChoiceScreen(MenuScreen):
    """A few things to do (v0.79.0: the Ingenfjel workbench, which does two jobs). Esc closes."""

    def __init__(self, title: str, choices: list) -> None:
        super().__init__()
        self.title = title
        self.choices = choices       # [(label, function(engine))]

    def options(self, engine):
        return [(label, True, fn) for label, fn in self.choices]

    def on_escape(self, engine):
        engine.screen = None

    def width(self, engine) -> int:
        """Wide enough for the title and the longest choice (v0.88.0)."""
        return max(40, len(self.title) + 6, max((len(label) for label, _ in self.choices), default=0) + 8)


class ArtificyScreen:
    """The home workbench (user, v0.79.0): repair a Common artifact yourself, from your pack or your
    home chest. No fee; it takes a Pulse. You need to know what it is first (study it with u)."""

    def __init__(self) -> None:
        self.selected = 0
        self.notice = ""

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import homes
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = homes.repairable(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
            self.notice = ""
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
            self.notice = ""
        elif event.sym in CONFIRM_KEYS and rows:
            store, item = rows[min(self.selected, len(rows) - 1)]
            ok, self.notice = homes.repair_at_home(engine, store, item)
            if ok:
                engine.log(self.notice)
                engine.screen = self
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import homes
        w = min(area_w - 2, 58)
        rows = homes.repairable(engine)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        extra = []
        if rows:
            store, item = rows[self.selected]
            why = homes.repair_blocked(item)
            extra += wrapped(why or "Repair it: no fee, a Pulse's work.", w - 4, CANT if why else TEXT)
        else:
            extra += wrapped("You have no broken artifacts here, in your pack or your home chest.", w - 4, DIM)
        extra += wrapped("Common artifacts only; the Artificer does the rest.", w - 4, DIM)
        if self.notice:
            extra += [("", DIM)] + wrapped(self.notice, w - 4, ACCENT)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, "Your workbench: artifacts")
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for i, (store, it) in enumerate(rows[first : first + visible]):
            row, bg = y + 3 + i, HIGHLIGHT if first + i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            ok = homes.repair_blocked(it) is None
            tag = it.type.rarity.name + (", chest" if store is not engine.player.inventory else "")
            console.print(x + 2, row, it.type.glyph, fg=it.type.color, bg=bg)
            console.print(x + 4, row, it.type.name[: w - 8 - len(tag)], fg=TEXT if ok else CANT, bg=bg)
            console.print(x + w - 2 - len(tag), row, tag, fg=DIM, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  Enter repair  Esc"[: w - 4], fg=DIM, bg=BG)


class MapsScreen:
    """The cartographer's maps (v0.84.0): every place the Guild has a scouting report of, the gentlest
    first; Enter buys one. A map you own shows the whole place on every hunt there."""

    def __init__(self) -> None:
        self.selected = 0
        self.notice = ""

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import maps
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = maps.for_sale(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
            self.notice = ""
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
            self.notice = ""
        elif event.sym in CONFIRM_KEYS and rows:
            ok, self.notice = maps.buy(engine, rows[min(self.selected, len(rows) - 1)])
            if ok:
                engine.log(self.notice)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import maps
        p = engine.player
        w = min(area_w - 2, 60)
        rows = maps.for_sale(engine)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        extra = []
        if rows:
            r = engine.regions[rows[self.selected]]
            extra += wrapped(" ".join(region_text_lines(r)), w - 4, DIM)
            by = maps.filed(engine)[rows[self.selected]]["by"]
            extra += wrapped(f"From the report of {by}.", w - 4, DIM)
        else:
            extra += wrapped("No maps yet. Scout a place properly (every area, and half the ground) and report it "
                             "to the clerk with your field notes.", w - 4, DIM)
        if self.notice:
            extra += [("", DIM)] + wrapped(self.notice, w - 4, ACCENT)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, "The cartographer's maps")
        purse = f"♦ {p.shards} shards"
        console.print(x + w - 2 - len(purse), y + 1, purse, fg=TEXT, bg=BG)
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for i, place in enumerate(rows[first : first + visible]):
            row, bg = y + 3 + i, HIGHLIGHT if first + i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            owned = place in p.maps
            cost = maps.price(engine, place)
            tag = "yours" if owned else f"{cost} ♦"
            name = engine.regions[place].name
            console.print(x + 2, row, name[: w - 6 - len(tag)], fg=DIM if owned else (TEXT if p.shards >= cost else CANT), bg=bg)
            console.print(x + w - 2 - len(tag), row, tag, fg=DIM, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  Enter buy  Esc"[: w - 4], fg=DIM, bg=BG)


def region_text_lines(r) -> list[str]:
    lo = r.danger[0]
    return [f"Danger {lo}, {r.depth or '?'} areas, {r.style_text()}.",
            "Lit." if r.light == "lit" else "Dark: bring light."]


class SlotScreen(MenuScreen):
    """Pick a slot to save into or load from."""

    def __init__(self, mode: str, back) -> None:
        super().__init__()
        self.mode = mode      # "save" or "load"
        self.back = back      # the screen to return to
        self.title = "Save game" if mode == "save" else "Load game"

    def slots(self):
        from game.saves import AUTOSAVE, SLOTS
        return list(SLOTS) if self.mode == "save" else [AUTOSAVE, *SLOTS]

    def options(self, engine):
        from game.saves import SLOT_NAMES
        opts = []
        for slot in self.slots():
            info = engine.saves.summary(slot)
            usable = self.mode == "save" or (info is not None and not info.get("damaged"))
            label = f"{SLOT_NAMES[slot]:<9} {describe_short(info)}"
            opts.append((label, usable, lambda e, s=slot: self.choose(e, s)))
        return opts

    def disabled_reason(self, label, engine):
        return "There's nothing in that slot to load." if "empty" in label else "That save is damaged."

    def on_escape(self, engine):
        engine.screen = self.back

    def choose(self, engine, slot):
        from game.saves import SLOT_NAMES, SaveError
        info = engine.saves.summary(slot)
        name = SLOT_NAMES[slot]
        if self.mode == "save":
            def do_save(e):
                e.saves.write(slot, e)
                e.screen = None
                e.log(f"Saved to {name}.")
            if info is not None:
                engine.screen = ConfirmScreen(f"Overwrite {name} ({describe(info)})?",
                                              on_yes=do_save, on_no=lambda e: setattr(e, "screen", self))
            else:
                do_save(engine)
            return None

        def do_load(e):
            try:
                e.saves.load(slot, e)
                e.log(f"Loaded {name}.")
            except SaveError as err:
                self.notice = str(err)
                e.screen = self
        if engine.started:
            engine.screen = ConfirmScreen(f"Load {name} ({describe(info)})? Anything since your last save will be lost.",
                                          on_yes=do_load, on_no=lambda e: setattr(e, "screen", self))
        else:
            do_load(engine)
        return None

    def render(self, console, engine, area_w):
        full = not engine.started
        width = console.width if full else area_w
        if full:
            console.rgb["bg"][:, :] = (10, 9, 8)
            console.rgb["ch"][:, :] = ord(" ")
        opts = self.options(engine)
        w = min(width - 2, 56)
        notice = textwrap.wrap(self.notice, w - 4) if self.notice else []
        # The selected slot's date, under the list.
        info = engine.saves.summary(self.slots()[min(self.selected, len(opts) - 1)])
        detail = (info.get("date") or f"Pulse {info['day']}") if info and not info.get("damaged") else ""
        notice = ([detail] if detail else []) + ([""] if detail and notice else []) + notice
        h = len(opts) + 6 + (len(notice) + 1 if notice else 0)
        x, y = (width - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, self.title)
        if self.mode == "save":
            console.print(x + 2, y + 1, "Choose a slot.", fg=DIM, bg=BG)
        self.draw_options(console, engine, x, y + 3, w)
        for i, line in enumerate(notice):
            color = DIM if detail and i == 0 else ACCENT
            console.print(x + 2, y + len(opts) + 4 + i, line[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose   Enter select   Esc back"[: w - 4], fg=DIM, bg=BG)


# ---- Shops ------------------------------------------------------------------------
TAB_KEYS = {KeySym.TAB, KeySym.LEFT, KeySym.RIGHT}
CANT = (120, 108, 96)


def artifacts_effect(t) -> str:
    from game import artifacts
    return artifacts.effect_text(t)


def buy_from(engine, vendor_id: str, index: int) -> tuple[bool, str]:
    """Buy the index-th thing a vendor has on show, taking it from their stock."""
    from game import shops
    stock = engine.stock(vendor_id)
    line = stock.shown()[index]
    if line.count <= 0:
        return False, "Sold out. More should come in before long."
    from game import bargaining
    ok, msg = shops.buy(engine.player, engine.catalogue[line.item_id], bargaining.pay(engine.player, line.price), line.bundle,
                        line.tier)
    if ok:
        stock.take(line, engine.day)
        bargaining.practise(engine)
    return ok, msg


class ShopScreen:
    """Buy from or sell to a shop. ←/→ or Tab switches between Buy and Sell."""

    def __init__(self, shop) -> None:
        self.shop = shop
        self.tab = "buy"
        self.selected = 0
        self.notice = ""

    def rows(self, engine):
        """(glyph, colour, label, price or None, enabled) for the current tab."""
        p = engine.player
        if self.tab == "buy":
            rows = []
            for line in engine.stock(self.shop.id).shown():
                t = engine.catalogue[line.item_id]
                what = t.label(line.bundle) + (f" +{line.tier}" if line.tier else "")
                label = f"{what}  x{line.count}" if line.count else f"{what}  (sold out)"
                from game import bargaining
                price = bargaining.pay(p, line.price)
                rows.append((t.glyph, t.color, label, price, line.count > 0 and p.shards >= price))
            return rows
        rows = []
        from game import gear
        for item in p.inventory.items:
            price = self.shop.buy_price(item.type, gear.value(item))
            if price is not None:
                from game import bargaining
                price = bargaining.paid(p, price)
            label = item.label + (" (equipped)" if p.is_equipped(item) else "")
            rows.append((item.type.glyph, item.type.color, label, price,
                         price is not None and not p.is_equipped(item)))
        return rows

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import shops
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in TAB_KEYS:
            self.tab = "sell" if self.tab == "buy" else "buy"
            self.selected, self.notice = 0, ""
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
        elif event.sym in CONFIRM_KEYS and rows:
            if self.tab == "buy":
                ok, msg = buy_from(engine, self.shop.id, self.selected)
            else:
                ok, msg = shops.sell(engine.player, self.shop, self.selected, engine.stock(self.shop.id))
                self.selected = min(self.selected, max(0, len(engine.player.inventory.items) - 1))
                if ok:
                    from game import bargaining
                    bargaining.practise(engine)
            self.notice = msg
            if ok:
                engine.log(msg)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        p = engine.player
        rows = self.rows(engine)
        w = min(area_w - 2, 54)
        self.selected = min(self.selected, max(0, len(rows) - 1))

        # Details of the selected item (in full), and the last result.
        extra = []
        if rows:
            t = (engine.catalogue[engine.stock(self.shop.id).shown()[self.selected].item_id] if self.tab == "buy"
                 else p.inventory.items[self.selected].type)
            props = t.properties
            stats = "".join(f" {k.capitalize()} {props[k]}." for k in ("damage", "armor", "heal") if k in props)
            text = (f"{t.rarity.name}. {artifacts_effect(t)} {t.description}" if t.rarity and t.working
                    else t.description + stats)
            extra += wrapped(text, w - 4, DIM)
        if self.notice:
            extra += [("", DIM)] + wrapped(self.notice, w - 4, ACCENT)
        list_len = max(len(engine.stock(self.shop.id).shown()), len(p.inventory.items), 4)
        h, visible, extra = fit_window(console, list_len, extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, self.shop.name)

        # Tabs and purse.
        for i, (tab, label) in enumerate((("buy", " Buy "), ("sell", " Sell "))):
            tx = x + 2 + i * 8
            active = self.tab == tab
            console.print(tx, y + 1, label, fg=BG if active else DIM, bg=ACCENT if active else BG)
        purse = f"♦ {p.shards} shards"
        console.print(x + w - 2 - len(purse), y + 1, purse, fg=TEXT, bg=BG)

        # The list.
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        if not rows:
            console.print(x + 2, y + 3, "You have nothing to sell.", fg=DIM, bg=BG)
        for r, (glyph, color, label, price, enabled) in enumerate(rows[first : first + visible]):
            i = first + r
            row = y + 3 + r
            bg = HIGHLIGHT if i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            console.print(x + 2, row, glyph, fg=color, bg=bg)
            console.print(x + 4, row, label[: w - 16], fg=TEXT if enabled else CANT, bg=bg)
            tag = f"{price} ♦" if price is not None else "-"
            console.print(x + w - 2 - len(tag), row, tag, fg=TEXT if enabled else CANT, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text, fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  Enter buy/sell  ←→ tab  Esc"[: w - 4], fg=DIM, bg=BG)


# ---- Looking ------------------------------------------------------------------------
CURSOR_BG = (200, 160, 80)
CURSOR_FG = (20, 16, 12)


class LookScreen:
    """Move a cursor around the map and read what's there. Takes no time."""

    def __init__(self, engine: "Engine") -> None:
        self.x, self.y = engine.player.x, engine.player.y
        self.cycle = -1  # position in the Tab list

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import look
        from game.input_handlers import LOOK_KEY, MOVE_KEYS
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if event.sym in (KeySym.ESCAPE, LOOK_KEY) or event.sym in CONFIRM_KEYS:
            engine.screen = None
        elif event.sym == KeySym.TAB:
            spots = look.targets(engine)
            if spots:
                self.cycle = (self.cycle + 1) % len(spots)
                self.x, self.y = spots[self.cycle]
        elif event.sym in MOVE_KEYS:
            dx, dy = MOVE_KEYS[event.sym]
            nx, ny = self.x + dx, self.y + dy
            if engine.game_map.in_bounds(nx, ny) and engine.in_vision(nx, ny):   # the camera follows
                self.x, self.y = nx, ny
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import look
        spot = engine.cam.to_screen(self.x, self.y)
        if spot:
            console.rgb["bg"][spot] = CURSOR_BG
            console.rgb["fg"][spot] = CURSOR_FG

        heading, lines = look.describe(engine, self.x, self.y)
        w = min(area_w - 2, 52)
        body = []
        for text, color in lines:
            body += [(part, color) for part in textwrap.wrap(text, w - 4)] if text else []
        h = len(body) + 4
        # Keep the panel out of the way of the cursor: top or bottom of the view.
        cursor_low = spot is not None and spot[1] > console.height // 2
        x = (area_w - w) // 2
        y = 1 if cursor_low else console.height - h - 1
        draw_box(console, x, y, w, h, heading)
        for i, (text, color) in enumerate(body):
            console.print(x + 2, y + 1 + i, text, fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "move to look  Tab next  Esc done"[: w - 4], fg=DIM, bg=BG)


# ---- The Artificer's workshop -------------------------------------------------------------
from game.artifacts import LOCKED as LOCKED_LINE   # (v0.67.0: one line, in game/artifacts.py)


class WorkshopScreen:
    """Repair, sell or consign broken Tower Artifacts; train skills.
    ←/→ or Tab switches between Artifacts and Training."""

    def __init__(self, workshop) -> None:
        self.workshop = workshop
        self.tab = "artifacts"
        self.tabs = ["artifacts", "buy"] + (["training"] if workshop.trains else [])
        self.selected = 0
        self.notice = ""

    def broken(self, engine) -> list[int]:
        """Inventory indexes of broken artifacts, then working ones in the bag (v0.52.0: the
        artificer buys those too)."""
        items = engine.player.inventory.items
        return ([i for i, item in enumerate(items) if item.type.is_broken_artifact]
                + [i for i, item in enumerate(items) if item.type.kind == "artifact" and item.type.working])

    def rows(self, engine) -> list:
        if self.tab == "artifacts":
            return self.broken(engine)
        if self.tab == "buy":
            return [(engine.catalogue[l.item_id], l) for l in engine.stock(self.workshop.id).shown()]
        return list(self.workshop.trains)

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import artifacts, skills
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
            return None
        if event.sym in TAB_KEYS and len(self.tabs) > 1:
            step = -1 if event.sym == KeySym.LEFT else 1
            self.tab = self.tabs[(self.tabs.index(self.tab) + step) % len(self.tabs)]
            self.selected, self.notice = 0, ""
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
        elif not rows:
            return None
        elif self.tab == "buy" and event.sym in CONFIRM_KEYS:
            ok, msg = buy_from(engine, self.workshop.id, self.selected)
            self.report(engine, ok, msg)
        elif self.tab == "training" and event.sym in CONFIRM_KEYS:
            skill = engine.skills[rows[self.selected]]
            ok, msg = skills.train(engine.player, skill)
            self.report(engine, ok, msg)
        elif self.tab == "artifacts":
            index = rows[self.selected]
            item = engine.player.inventory.items[index]
            t = item.type
            if t.working:
                if event.sym == _key("b"):
                    if engine.player.is_equipped(item):
                        self.report(engine, False, f"Take off the {t.name} first.")
                    else:
                        self.confirm(engine, f"Sell the {t.name} for {artifacts.working_price(t, engine.player)} shards?",
                                     lambda: artifacts.sell_working(engine.player, index, engine.stock(self.workshop.id)))
            elif t.properties.get("locked") and event.sym in (_key("r"), _key("b"), _key("c")):
                self.report(engine, False, LOCKED_LINE)   # (Chapter 1's Unique: nobody can place it)
            elif event.sym == _key("r"):
                ok, msg = artifacts.repair(engine.player, index, engine.catalogue)
                if ok:
                    from game import bargaining
                    bargaining.practise(engine)
                self.report(engine, ok, msg)
            elif event.sym == _key("b"):
                self.confirm(engine, f"Sell the {t.name} broken, as it is, for {artifacts.broken_price(t, engine.player)} shards?",
                             lambda: artifacts.sell_broken(engine.player, index))
            elif event.sym == _key("c"):
                pay = f"{artifacts.consign_payout(t, engine.player)} shards" if t.identified else "an unknown sum"
                share = artifacts.consign_share(t, engine.player)
                if engine.player.shards < share:
                    self.report(engine, False, f"Consigning it means paying your half of the repair first: "
                                               f"{share} shards. You don't have enough.")
                    return None
                self.confirm(engine, f"Consign the {t.name} to the workshop? You pay your half of the repair "
                                     f"({share} shards) and are paid {pay} now. The artifact is gone for good.",
                             lambda: artifacts.consign(engine.player, index, engine.stock(self.workshop.id),
                                                       engine.catalogue))
        return None

    def report(self, engine, ok: bool, msg: str) -> None:
        self.notice = msg
        if ok:
            engine.log(msg)
        self.selected = min(self.selected, max(0, len(self.rows(engine)) - 1))

    def confirm(self, engine, question: str, deal) -> None:
        """Ask first: selling and consigning can't be undone. Back here either way."""
        def yes(e):
            ok, msg = deal()
            if ok:
                from game import bargaining
                bargaining.practise(e)
            self.report(e, ok, msg)
            e.screen = self

        def no(e):
            e.screen = self
        engine.screen = ConfirmScreen(question, on_yes=yes, on_no=no)

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import artifacts, skills
        p = engine.player
        rows = self.rows(engine)
        w = min(area_w - 2, 58)
        self.selected = min(self.selected, max(0, len(rows) - 1))

        # The details under the list (in full), for the current tab.
        extra = []
        if self.tab == "artifacts":
            if rows and p.inventory.items[rows[self.selected]].type.working:
                item = p.inventory.items[rows[self.selected]]
                t = item.type
                worn = p.is_equipped(item)
                extra = wrapped(artifacts.effect_text(t), w - 4, DIM) + [
                    (f"b  Sell it         +{artifacts.working_price(t, p)} ♦" + ("  (take it off first)" if worn else ""),
                     CANT if worn else TEXT)]
            elif rows and p.inventory.items[rows[self.selected]].type.properties.get("locked"):
                extra = wrapped(LOCKED_LINE, w - 4, DIM)
            elif rows:
                t = p.inventory.items[rows[self.selected]].type
                fee = artifacts.repair_fee(t, p)
                share = artifacts.consign_share(t, p)
                # (v0.64.0, user) what you pay shows as −, what you're paid as +
                pay = (f"-{share}, +{artifacts.consign_payout(t, p)} ♦" if t.identified
                       else f"-{share}, +? ♦  (unidentified)")
                known = (f"Repaired, it will be: {artifacts.effect_text(engine.catalogue[t.repairs_to])}"
                         if t.identified else "You don't know what it is. The artificer won't say until it's repaired.")
                extra = wrapped(known, w - 4, DIM) + [
                    (f"r  Repair it       -{fee} ♦", TEXT if p.shards >= fee else CANT),
                    (f"b  Sell it broken  +{artifacts.broken_price(t, p)} ♦", TEXT),
                    (f"c  Consign it      {pay}", TEXT if p.shards >= share else CANT)]
            help_text = "↑↓ choose  r repair  b sell  c consign  ←→ Esc"
        elif self.tab == "buy":
            if rows:
                t = rows[self.selected][0]
                extra = wrapped(f"{t.rarity.name}. {artifacts.effect_text(t)} {t.description}", w - 4, DIM)
            help_text = "↑↓ choose  Enter buy  ←→ tab  Esc"
        else:
            skill, state = engine.skills[rows[self.selected]], p.skill(rows[self.selected])
            if state.rank >= skill.max_rank:
                status = "Mastered."
            elif state.rank < skill.self_taught_to:
                status = f"Practice {state.practice}/{skill.needed(state.rank)}. Improves by practice alone for now."
            elif skills.is_ready(skill, state):
                status = "Ready to train."
            else:
                status = f"Practice {state.practice}/{skill.needed(state.rank)} before training."
            extra = wrapped(status, w - 4, TEXT) + wrapped(skill.description, w - 4, DIM)
            help_text = "↑↓ choose  Enter train  ←→ tab  Esc"
        if self.notice:
            extra += [("", DIM)] + wrapped(self.notice, w - 4, ACCENT)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, self.workshop.name)

        labels = {"artifacts": " Artifacts ", "buy": " Buy ", "training": " Training "}
        tx = x + 2
        for tab in self.tabs:
            label = labels[tab]
            active = self.tab == tab
            console.print(tx, y + 1, label, fg=BG if active else DIM, bg=ACCENT if active else BG)
            tx += len(label) + 1
        purse = f"♦ {p.shards} shards"
        console.print(x + w - 2 - len(purse), y + 1, purse, fg=TEXT, bg=BG)

        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        if self.tab == "artifacts":
            if not rows:
                console.print(x + 2, y + 3, "You have no artifacts in your pack to show.", fg=DIM, bg=BG)
            for r, index in enumerate(rows[first : first + visible]):
                t = p.inventory.items[index].type
                row, bg = y + 3 + r, HIGHLIGHT if first + r == self.selected else BG
                console.rgb["bg"][x + 1 : x + w - 1, row] = bg
                console.print(x + 2, row, t.glyph, fg=t.color, bg=bg)
                name = t.name + ("  (working)" if t.working else "")
                console.print(x + 4, row, name[: w - 18], fg=TEXT, bg=bg)
                console.print(x + w - 2 - len(t.rarity.name), row, t.rarity.name, fg=t.rarity.color, bg=bg)
        elif self.tab == "buy":
            if not rows:
                console.print(x + 2, y + 3, "Nothing for sale right now.", fg=DIM, bg=BG)
            for r, (t, line) in enumerate(rows[first : first + visible]):
                row, bg = y + 3 + r, HIGHLIGHT if first + r == self.selected else BG
                console.rgb["bg"][x + 1 : x + w - 1, row] = bg
                from game import bargaining
                price = bargaining.pay(p, line.price)
                ok = line.count > 0 and p.shards >= price
                console.print(x + 2, row, t.glyph, fg=t.color, bg=bg)
                name = f"{t.name}  x{line.count}" if line.count else f"{t.name}  (sold out)"
                console.print(x + 4, row, name[: w - 18], fg=TEXT if ok else CANT, bg=bg)
                tag = f"{price} ♦"
                console.print(x + w - 2 - len(tag), row, tag, fg=TEXT if ok else CANT, bg=bg)
        else:
            for r, sid in enumerate(rows[first : first + visible]):
                skill, state = engine.skills[sid], p.skill(sid)
                row, bg = y + 3 + r, HIGHLIGHT if first + r == self.selected else BG
                console.rgb["bg"][x + 1 : x + w - 1, row] = bg
                console.print(x + 2, row, f"{skill.name}  rank {state.rank}", fg=TEXT, bg=bg)
                cost = skills.cost_for(p, skill)
                tag = f"rank {state.rank + 1}: {cost} ♦" if cost is not None else "-"
                ok = cost is not None and skills.is_ready(skill, state) and p.shards >= cost
                console.print(x + w - 2 - len(tag), row, tag, fg=TEXT if ok else CANT, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, help_text[: w - 4], fg=DIM, bg=BG)


# ---- The character sheet ------------------------------------------------------------------


# ---- The guild stash ----------------------------------------------------------------------
def gear_worth(item) -> int:
    from game import gear
    return gear.value(item) * max(1, item.count)


class StashScreen:
    """Your pack on the left, the guild stash on the right. ←→ or Tab picks a side;
    Enter moves the selected thing (a whole stack) across; o sorts the side you're on. Takes no time.
    The stash belongs to the guild hall: the next Hunter inherits it."""

    def __init__(self, store=None, title: str = "Guild stash", name: str = "Stash", only=None,
                 only_why: str = "") -> None:
        # (v0.74.0: also a home's chest and trophy shelves: `store` gives the Inventory, `only`
        # says what may go into it from the pack)
        self.side = "pack"
        self.selected = {"pack": 0, "stash": 0}
        self.notice = ""
        self.store = store
        self.title = title
        self.name = name
        self.only = only
        self.only_why = only_why

    def lists(self, engine):
        return {"pack": engine.player.inventory, "stash": self.store(engine) if self.store else engine.stash}

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        src = self.lists(engine)[self.side]
        n = len(src.items)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in TAB_KEYS:
            self.side = "stash" if self.side == "pack" else "pack"
            self.notice = ""
        elif event.sym in UP_KEYS and n:
            self.selected[self.side] = (self.selected[self.side] - 1) % n
        elif event.sym in DOWN_KEYS and n:
            self.selected[self.side] = (self.selected[self.side] + 1) % n
        elif event.sym in CONFIRM_KEYS and n:
            self.move(engine)
        elif event.sym == _key("o") and n > 1:
            self.sort(engine)
        return None

    SORTS = ("kind", "name", "worth")
    KIND_ORDER = ("weapon", "armor", "tackle", "artifact", "consumable", "material", "fish", "trophy",
                  "writing", "treasure", "misc", "key")

    def sort(self, engine) -> None:
        """o: put the side you're on in order: by kind, then by name, then by worth, each press the next
        (v0.100.9, user: a sort for a stash of 20-30 things). The order stays."""
        self.sort_n = (getattr(self, "sort_n", -1) + 1) % len(self.SORTS)
        mode = self.SORTS[self.sort_n]
        inv = self.lists(engine)[self.side]
        kind = {k: i for i, k in enumerate(self.KIND_ORDER)}
        name = lambda it: it.label.lower()
        keys = {"kind": lambda it: (kind.get(it.type.kind, len(kind)), name(it)),
                "name": name,
                "worth": lambda it: (-gear_worth(it), name(it))}
        picked = inv.items[min(self.selected[self.side], len(inv.items) - 1)]
        inv.items.sort(key=keys[mode])
        self.selected[self.side] = next(i for i, it in enumerate(inv.items) if it is picked)
        self.notice = f"{'Pack' if self.side == 'pack' else self.name} sorted by {mode}. (o again: by " \
                      f"{self.SORTS[(self.sort_n + 1) % len(self.SORTS)]})"

    def move(self, engine) -> None:
        p = engine.player
        lists = self.lists(engine)
        src, dst = (lists["pack"], lists["stash"]) if self.side == "pack" else (lists["stash"], lists["pack"])
        i = min(self.selected[self.side], len(src.items) - 1)
        item = src.items[i]
        if self.side == "pack" and p.is_equipped(item):
            self.notice = f"Take off the {item.type.name} before stashing it."
            return
        if self.side == "pack" and self.only is not None and not self.only(item):
            self.notice = self.only_why or "That doesn't go there."
            return
        if not dst.can_add(item):
            self.notice = (f"The {self.name.lower()} is full." if self.side == "pack"
                           else f"You have no room in your pack for {article(item.label)}.")
            return
        src.remove(i)
        dst.add(item)
        verb = "stash" if self.side == "pack" else "take"
        self.notice = f"You {verb} {article(item.label)}."
        self.selected[self.side] = max(0, min(i, len(src.items) - 1))

    def render(self, console, engine: "Engine", area_w: int) -> None:
        p = engine.player
        lists = self.lists(engine)
        w = min(area_w - 2, 60)
        h = console.height - 2
        x, y = (area_w - w) // 2, 1
        draw_box(console, x, y, w, h, self.title)
        col_w = (w - 3) // 2
        visible = h - 8
        for c, side in enumerate(("pack", "stash")):
            inv = lists[side]
            cx = x + 1 + c * (col_w + 1)
            active = self.side == side
            title = f" Pack {inv.used}/{inv.capacity} " if side == "pack" else f" {self.name} {inv.used}/{inv.capacity} "
            console.print(cx + 1, y + 1, title, fg=BG if active else DIM, bg=ACCENT if active else BG)
            items = inv.items
            sel = min(self.selected[side], max(0, len(items) - 1))
            first = max(0, min(sel - visible // 2, len(items) - visible))
            if not items:
                console.print(cx + 1, y + 3, "(empty)", fg=DIM, bg=BG)
            for r, item in enumerate(items[first : first + visible]):
                i = first + r
                row = y + 3 + r
                bg = HIGHLIGHT if active and i == sel else BG
                console.rgb["bg"][cx : cx + col_w, row] = bg
                console.print(cx + 1, row, item.type.glyph, fg=item.type.color, bg=bg)
                equipped = side == "pack" and (p.is_equipped(item) or (self.only is not None and not self.only(item)))
                console.print(cx + 3, row, item.label[: col_w - 4], fg=CANT if equipped else TEXT, bg=bg)
        for row in range(y + 1, y + h - 4):
            console.print(x + 1 + col_w, row, "│", fg=FRAME, bg=BG)
        if self.notice:
            console.print(x + 2, y + h - 3, self.notice[: w - 4], fg=ACCENT, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  Enter move  ←→ side  o sort  Esc"[: w - 4], fg=DIM, bg=BG)


# ---- Conversations ------------------------------------------------------------------------
class DialogueScreen:
    """Talking to someone: what they say, then numbered choices.
    ↑↓ and Enter, or a number key; Esc leaves. Takes no time."""

    def __init__(self, talk) -> None:
        self.talk = talk
        self.selected = 0

    def finish(self, engine: "Engine") -> None:
        engine.screen = None
        if self.talk.opens:
            engine.open_vendor(self.talk.opens)

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        n = len(self.talk.choices)
        number = NUMBER_KEYS.get(event.sym)
        if event.sym == KeySym.ESCAPE:
            self.finish(engine)
        elif event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % n
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % n
        elif event.sym in CONFIRM_KEYS or (number is not None and number < n):
            self.talk.pick(number if number is not None else self.selected)
            self.selected = 0
            if self.talk.done:
                self.finish(engine)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        w = min(area_w - 2, 60)
        said = wrapped(self.talk.text, w - 4, TEXT)
        options = []
        for i, choice in enumerate(self.talk.choices):
            for j, (line, _) in enumerate(wrapped(choice["text"], w - 8, TEXT)):
                options.append((i, ("%d. " % (i + 1) if j == 0 else "   ") + line))
        h = min(console.height - 2, len(said) + len(options) + 6)
        x, y = (area_w - w) // 2, console.height - h - 1  # along the bottom, so the speaker stays in view
        draw_box(console, x, y, w, h, self.talk.speaker.full_name)
        row = y + 1
        for line, color in said:
            console.print(x + 2, row, line, fg=color, bg=BG)
            row += 1
        row += 1
        for i, line in options:
            if row >= y + h - 2:
                break
            bg = HIGHLIGHT if i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            console.print(x + 2, row, line, fg=ACCENT if i == self.selected else TEXT, bg=bg)
            row += 1
        console.print(x + 2, y + h - 2, "↑↓ or 1-9 choose   Enter   Esc leave"[: w - 4], fg=DIM, bg=BG)


# ---- Shooting -----------------------------------------------------------------------------
PATH_BG = (90, 62, 34)
WARN = (230, 120, 90)


class TargetScreen(LookScreen):
    """Aim the bow: the cursor starts on the nearest creature in range; Tab cycles
    through creatures in view and in range; the movement keys move the cursor.
    Enter or f shoots (a turn passes); Esc puts the bow down."""

    last_target = None  # the creature shot at last, to aim at it again

    def __init__(self, engine: "Engine") -> None:
        super().__init__(engine)
        targets = self.targets(engine)
        last = TargetScreen.last_target
        if last is not None and (last.x, last.y) in targets:
            self.x, self.y = last.x, last.y
            self.cycle = targets.index((last.x, last.y))
        elif targets:
            self.x, self.y = targets[0]
            self.cycle = 0

    @staticmethod
    def targets(engine) -> list[tuple[int, int]]:
        from game import look, ranged
        p, gm = engine.player, engine.game_map
        spots = [(m.x, m.y) for m in gm.monsters
                 if look.can_see(engine, m.x, m.y) and ranged.in_range(engine, m.x, m.y)]
        return sorted(spots, key=lambda s: ranged.distance(p.x, p.y, *s))

    def handle(self, event, engine: "Engine") -> Action | None:
        from game.input_handlers import FIRE_KEY, MOVE_KEYS
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in CONFIRM_KEYS or event.sym == FIRE_KEY:
            engine.screen = None
            TargetScreen.last_target = engine.game_map.monster_at(self.x, self.y)
            return FireAction(self.x, self.y)
        elif event.sym == KeySym.TAB:
            spots = self.targets(engine)
            if spots:
                self.cycle = (self.cycle + 1) % len(spots)
                self.x, self.y = spots[self.cycle]
        elif event.sym in MOVE_KEYS:
            dx, dy = MOVE_KEYS[event.sym]
            nx, ny = self.x + dx, self.y + dy
            if engine.game_map.in_bounds(nx, ny) and engine.in_vision(nx, ny):   # the camera follows
                self.x, self.y = nx, ny
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import look, ranged
        p = engine.player
        path, creature = ranged.flight(engine, self.x, self.y)
        for cell in path:
            spot = engine.cam.to_screen(*cell)
            if spot:
                console.rgb["bg"][spot] = PATH_BG
        spot = engine.cam.to_screen(self.x, self.y)
        if spot:
            console.rgb["bg"][spot] = CURSOR_BG
            console.rgb["fg"][spot] = CURSOR_FG

        weapon = ranged.bow(p)
        ammo = weapon.type.properties.get("ammo", "arrow")
        arrows = p.inventory.count_of(ammo)
        dist = ranged.distance(p.x, p.y, self.x, self.y)
        rng_max = ranged.bow_range(engine.player, weapon)
        lines = []
        if (self.x, self.y) == (p.x, p.y):
            heading = "Take aim"
            lines.append(("Tab picks the nearest creature in range; the movement keys move the aim.", TEXT))
        elif not look.can_see(engine, self.x, self.y):
            heading = "Can't see there"
            lines.append(("You can only shoot at what you can see.", WARN))
        elif dist > rng_max:
            heading = "Out of range"
            lines.append((f"That's {dist:.0f} away; your {weapon.type.name} reaches {rng_max}.", WARN))
        elif creature is not None:
            heading = creature.name.capitalize()
            in_the_way = (creature.x, creature.y) != (self.x, self.y)
            if in_the_way:
                lines.append((f"The {creature.name} is in the way: the arrow would hit it first.", WARN))
            chance = ranged.hit_chance(p, creature, ranged.distance(p.x, p.y, creature.x, creature.y))
            lines.append((f"Chance to hit: {chance}%", TEXT))
        else:
            heading = "No target"
            blocked = path and path[-1] != (self.x, self.y)
            lines.append(("Something solid is in the way." if blocked else "Nothing there to hit.", DIM))
        lines.append((f"{weapon.type.name.capitalize()}, range {rng_max}. {arrows} {engine.catalogue[ammo].label(2)[2:] if arrows != 1 else engine.catalogue[ammo].name} left.", DIM))

        w = min(area_w - 2, 52)
        body = []
        for text, color in lines:
            body += wrapped(text, w - 4, color)
        h = len(body) + 4
        cursor_low = spot is not None and spot[1] > console.height // 2
        x = (area_w - w) // 2
        y = 1 if cursor_low else console.height - h - 1
        draw_box(console, x, y, w, h, heading)
        for i, (text, color) in enumerate(body):
            console.print(x + 2, y + 1 + i, text, fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "Enter/f shoot  Tab next  move to aim  Esc"[: w - 4], fg=DIM, bg=BG)


class EncounterScreen:
    """Someone on the road (game/road.py, v0.90.0): what they say, then a choice; then what happened.
    ↑↓ or 1-9 and Enter. It can't be waved away with Esc: they're in your way."""

    def __init__(self, enc: dict) -> None:
        self.enc = enc
        self.selected = 0
        self.result: list[str] | None = None
        self.over = False

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import road
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if self.result is not None:
            if self.over:
                engine.screen = None
            else:
                self.result, self.selected = None, 0
            return None
        opts = road.choices(engine, self.enc)
        if event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(opts)
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(opts)
        elif event.sym in DIGIT_KEYS and 1 <= DIGIT_KEYS[event.sym] <= len(opts):
            self.selected = DIGIT_KEYS[event.sym] - 1
            return self.pick(engine)
        elif event.sym in CONFIRM_KEYS:
            return self.pick(engine)
        return None

    def pick(self, engine) -> Action | None:
        from game import road
        key = road.choices(engine, self.enc)[self.selected][0]
        self.result, self.over = road.choose(engine, self.enc, key)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import road
        w = min(area_w - 2, 64)
        if self.result is not None:
            body = [l for t in self.result for l in wrapped(t, w - 4, TEXT)]
            foot = " any key "
            opts = []
        else:
            body = wrapped(self.enc["text"], w - 4, TEXT)
            opts = road.choices(engine, self.enc)
            foot = " ↑↓ or 1-9 choose  Enter "
        h = len(body) + (len(opts) + 1 if opts else 0) + 4
        x, y = (area_w - w) // 2, max(0, (console.height - h) // 2)
        draw_box(console, x, y, w, h, self.enc["title"])
        for i, (t, c) in enumerate(body):
            console.print(x + 2, y + 2 + i, t, fg=c, bg=BG)
        top = y + 3 + len(body)
        for i, (_, label) in enumerate(opts):
            sel = i == self.selected
            if sel:
                console.rgb["bg"][x + 1: x + w - 1, top + i] = HIGHLIGHT
            console.print(x + 2, top + i, f"{i + 1}. {label}"[: w - 4], fg=ACCENT if sel else TEXT,
                          bg=HIGHLIGHT if sel else BG)
        console.print(x + 2, y + h - 1, foot[: w - 4], fg=DIM, bg=BG)


class VaultScreen:
    """Pole-vault (v0.86.0): which way? A direction vaults; Esc doesn't."""

    def handle(self, event, engine: "Engine") -> Action | None:
        from game.input_handlers import MOVE_KEYS
        from game.actions import VaultAction
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if event.sym in MOVE_KEYS:
            engine.screen = None
            return VaultAction(*MOVE_KEYS[event.sym])
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        text = " Vault which way? (a direction; Esc: don't) "
        w = min(area_w - 2, len(text) + 2)
        x = (area_w - w) // 2
        draw_box(console, x, 1, w, 3, "Pole-vault")
        console.print(x + 1, 2, text[: w - 2], fg=TEXT, bg=BG)


class ThrowScreen(LookScreen):
    """Aim a throw (v0.82.0): the cursor starts on the nearest creature within reach; Tab cycles them;
    the movement keys move it. Enter or h throws (a turn passes); Esc puts it away."""

    def __init__(self, engine: "Engine", item, reach: int) -> None:
        super().__init__(engine)
        self.item, self.reach = item, reach
        spots = self.targets(engine)
        if spots:
            self.x, self.y = spots[0]
            self.cycle = 0

    def targets(self, engine) -> list:
        from game import look, ranged
        p, gm = engine.player, engine.game_map
        weapon = self.item is p.equipped.get("weapon")
        spots = [(m.x, m.y) for m in gm.monsters if look.can_see(engine, m.x, m.y)
                 and ranged.distance(p.x, p.y, m.x, m.y) <= self.reach
                 and not (weapon and abs(m.x - p.x) + abs(m.y - p.y) <= 1)]
        return sorted(spots, key=lambda s: ranged.distance(p.x, p.y, *s))

    def handle(self, event, engine: "Engine") -> Action | None:
        from game.input_handlers import THROW_KEY, MOVE_KEYS
        from game.actions import ThrowAction
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in CONFIRM_KEYS or event.sym == THROW_KEY:
            engine.screen = None
            return ThrowAction(self.item, self.x, self.y)
        elif event.sym == KeySym.TAB:
            spots = self.targets(engine)
            if spots:
                self.cycle = (getattr(self, "cycle", -1) + 1) % len(spots)
                self.x, self.y = spots[self.cycle]
        elif event.sym in MOVE_KEYS:
            dx, dy = MOVE_KEYS[event.sym]
            nx, ny = self.x + dx, self.y + dy
            if engine.game_map.in_bounds(nx, ny) and engine.in_vision(nx, ny):
                self.x, self.y = nx, ny
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import ranged, throwing, combat
        p = engine.player
        path, creature = ranged.flight(engine, self.x, self.y)
        for cell in path:
            spot = engine.cam.to_screen(*cell)
            if spot:
                console.rgb["bg"][spot] = PATH_BG
        spot = engine.cam.to_screen(self.x, self.y)
        if spot:
            console.rgb["bg"][spot] = CURSOR_BG
            console.rgb["fg"][spot] = CURSOR_FG
        weapon = self.item is p.equipped.get("weapon")
        name = self.item.type.name
        why = throwing.why_not(engine, self.item, self.reach, self.x, self.y)
        lines = []
        if why:
            heading = "Throw " + name
            lines.append((why, WARN if (self.x, self.y) != (p.x, p.y) else TEXT))
        else:
            heading = creature.name.capitalize() if creature is not None else "Throw " + name
            if weapon and creature is not None:
                dist = ranged.distance(p.x, p.y, creature.x, creature.y)
                lines.append((f"Chance to hit: {combat.hit_chance(p.accuracy - int(dist // 3), creature.evasion)}%", TEXT))
            elif not weapon:
                what = {"flash": "Everything within a cell of where it lands loses a turn.",
                        "smoke": "A cloud of smoke that blocks sight for a while.",
                        "lure": "Creatures that haven't seen you, or have lost you, go to it."}[self.item.type.properties["throw"]]
                lines.append((what, TEXT))
        if weapon:
            lines.append((f"{name.capitalize()}: thrown up to {self.reach}." + (" It comes back to your hand."
                          if throwing_returns(self.item) else " It stays where it lands."), DIM))
        else:
            lines.append((f"Thrown up to {self.reach}. {p.inventory.count_of(self.item.type.id)} left.", DIM))
        w = min(area_w - 2, 52)
        body = []
        for text, color in lines:
            body += wrapped(text, w - 4, color)
        h = len(body) + 4
        cursor_low = spot is not None and spot[1] > console.height // 2
        x = (area_w - w) // 2
        y = 1 if cursor_low else console.height - h - 1
        draw_box(console, x, y, w, h, heading)
        for i, (text, color) in enumerate(body):
            console.print(x + 2, y + 1 + i, text, fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "Enter/h throw  Tab next  move to aim  Esc"[: w - 4], fg=DIM, bg=BG)


def throwing_returns(item) -> bool:
    from game import gear
    return gear.gear_type(item.type) == "knife"


# ---- Training (opened from a conversation: "train:marksmanship") ---------------------------
class TrainingScreen:
    """Pay to train skills past what practice alone can teach. Enter trains; Esc leaves."""

    def __init__(self, skill_ids: list[str], mentor: dict | None = None) -> None:
        self.skill_ids = skill_ids
        self.selected = 0
        self.notice = ""
        self.mentor = mentor   # a retired Hunter teaching (game/aging.py): cheaper, up to their rank

    def terms(self, sid) -> dict:
        if self.mentor is None:
            return {}
        from game.aging import MENTOR_DISCOUNT
        return {"discount": self.mentor.get("pay", MENTOR_DISCOUNT), "cap": self.mentor["skills"].get(sid, 1)}

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import skills
        if not isinstance(event, tcod.event.KeyDown):
            return None
        n = len(self.skill_ids)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % n
            self.notice = ""
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % n
            self.notice = ""
        elif event.sym in CONFIRM_KEYS:
            sid = self.skill_ids[self.selected]
            ok, msg = skills.train(engine.player, engine.skills[sid], **self.terms(sid))
            self.notice = msg
            if ok:
                engine.log(msg)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import skills
        p = engine.player
        w = min(area_w - 2, 56)
        skill, state = engine.skills[self.skill_ids[self.selected]], p.skill(self.skill_ids[self.selected])
        if state.rank >= skill.max_rank:
            status = "Mastered."
        elif state.rank < skill.self_taught_to:
            status = f"Practice {state.practice}/{skill.needed(state.rank)}. Improves by practice alone for now."
        elif skills.is_ready(skill, state):
            status = "Ready to train."
        else:
            status = f"Practice {state.practice}/{skill.needed(state.rank)} before training."
        # (v0.64.0, user: the notice was cut off and the list didn't scroll) the notice comes right
        # after the status, so if anything has to be cut it's the end of the skill's description
        extra = wrapped(status, w - 4, TEXT)
        title = "Training"
        if self.mentor is not None:
            cap = self.mentor["skills"].get(self.skill_ids[self.selected], 1)
            from game.aging import MENTOR_DISCOUNT
            off = round((1 - self.mentor.get("pay", MENTOR_DISCOUNT)) * 100)
            extra = wrapped(f"{self.mentor['given']} teaches at {off}% off the trainer's price, up to rank {cap}.", w - 4, ACCENT) + extra
            title = f"Training with {self.mentor['given']}"
        if self.notice:
            extra += wrapped(self.notice, w - 4, ACCENT)
        extra += wrapped(skill.description, w - 4, DIM)
        h, visible, extra = fit_window(console, len(self.skill_ids), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, title)
        purse = f"♦ {p.shards} shards"
        console.print(x + w - 2 - len(purse), y + 1, purse, fg=TEXT, bg=BG)
        n = len(self.skill_ids)
        first = max(0, min(self.selected - visible // 2, n - visible))
        for r, sid in enumerate(self.skill_ids[first:first + visible]):
            sk, st = engine.skills[sid], p.skill(sid)
            row, bg = y + 3 + r, HIGHLIGHT if first + r == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            console.print(x + 2, row, f"{sk.name}  rank {st.rank}", fg=TEXT, bg=bg)
            cost = skills.cost_for(p, sk, **self.terms(sid))
            tag = f"rank {st.rank + 1}: {cost} ♦" if cost is not None else "-"
            ok = cost is not None and skills.is_ready(sk, st) and p.shards >= cost
            console.print(x + w - 2 - len(tag), row, tag, fg=TEXT if ok else CANT, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  Enter train  Esc"[: w - 4], fg=DIM, bg=BG)


# ---- Scrolling text: the message history and the key reference -----------------------------
PAGE_KEYS = {KeySym.PAGEUP: -1, KeySym.PAGEDOWN: 1,
             _key("LEFTBRACKET"): -1, _key("RIGHTBRACKET"): 1}   # [ and ] page too (user, v0.59.2)


class ScrollScreen:
    """A tall window of text lines that scrolls: ↑↓ a line, [ ] or PgUp/PgDn a page,
    Home/End to the ends; Esc (or the key that opened it) closes."""

    title = ""
    start_at_end = False
    close_keys: set = set()

    def __init__(self) -> None:
        self.top = None  # first line shown (None: not placed yet)

    @classmethod
    def of_lines(cls, title: str, text: list[str]) -> "ScrollScreen":
        """A window of fixed text (each string a paragraph), e.g. the plaque."""
        screen = cls()
        screen.title = title

        def lines(engine, width):
            out = []
            for para in text:
                out += wrapped(para, width, TEXT) or [("", TEXT)]
            return out
        screen.lines = lines
        return screen

    def lines(self, engine, width: int) -> list[tuple[str, tuple]]:
        raise NotImplementedError

    def footer(self) -> str:
        return "↑↓ scroll  [ ] or PgUp/PgDn page  Home/End  Esc"

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if self.top is None:      # (a key before the first draw)
            self.top = 0
        if event.sym == KeySym.ESCAPE or event.sym in self.close_keys:
            engine.screen = None
        elif event.sym in UP_KEYS:
            self.top -= 1
        elif event.sym in DOWN_KEYS:
            self.top += 1
        elif event.sym in PAGE_KEYS:
            self.top += PAGE_KEYS[event.sym] * self.page
        elif event.sym == KeySym.HOME:
            self.top = 0
        elif event.sym == KeySym.END:
            self.top = 10 ** 9
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        w = min(area_w - 2, 70)
        h = console.height - 2
        x, y = (area_w - w) // 2, 1
        text = self.lines(engine, w - 4)
        self.page = h - 4
        last = max(0, len(text) - self.page)
        if self.top is None:
            self.top = last if self.start_at_end else 0
        self.top = max(0, min(self.top, last))
        draw_box(console, x, y, w, h, self.title)
        for i, (line, color) in enumerate(text[self.top : self.top + self.page]):
            console.print(x + 2, y + 1 + i, line[: w - 4], fg=color, bg=BG)
        if last:
            where = f" {self.top + 1}-{min(len(text), self.top + self.page)} of {len(text)} "
            console.print(x + w - 2 - len(where), y + h - 1, where, fg=DIM, bg=BG)
        console.print(x + 2, y + h - 2, self.footer()[: w - 4], fg=DIM, bg=BG)


class HistoryScreen(ScrollScreen):
    """Every message since the game began or was loaded (up to the last 500), oldest at the top."""

    title = "Messages"
    start_at_end = True

    def __init__(self) -> None:
        super().__init__()
        from game.input_handlers import HISTORY_KEY
        self.close_keys = {HISTORY_KEY}

    def lines(self, engine, width: int):
        out = []
        n = len(engine.messages)
        for i, message in enumerate(engine.messages):
            color = TEXT if i >= n - 5 else DIM  # the newest few stand out
            for j, part in enumerate(textwrap.wrap(message, width - 2) or [""]):
                out.append((("- " if j == 0 else "  ") + part, color))
        return out or [("No messages yet.", DIM)]


class AnglersLogScreen(ScrollScreen):
    """The Angler's Log (v0.99.0, game/catches.py): every kind of fish by water, what you know of it."""

    title = "Angler's Log"

    def __init__(self) -> None:
        super().__init__()
        from game.input_handlers import LOG_KEY
        self.close_keys = {LOG_KEY}

    def lines(self, engine, width: int):
        from game import catches
        colors = {-2: TEXT, -1: ACCENT, 0: DIM, 1: DIM, 2: TEXT, 3: TEXT}
        out = []
        for text, lv in catches.log_lines(engine.player):
            for j, part in enumerate(textwrap.wrap(text, width - 2, subsequent_indent="     ") or [""]):
                out.append((part, colors.get(lv, TEXT)))
        return out


KEY_REFERENCE = [
    ("Moving", [
        ("Arrows, WASD", "move"),
        ("Numpad", "move (no diagonals)"),
        (". or numpad 5", "wait a turn"),
        ("Bump a creature", "attack it"),
        ("Bump a person", "talk"),
        ("o", "auto-explore (hunts)"),
        ("t", "travel to a known place"),
    ]),
    ("Acting", [
        ("g or ,", "pick up what's here (a corpse last, as a trophy)"),
        ("b", "butcher the corpse here, for materials"),
        ("f", "aim and shoot a bow or crossbow"),
        ("h", "throw a pot, jar, lure or throwable weapon"),
        ("r", "fish: cast a line into water in reach (rod and bait)"),
        ("p", "the Angler's Log: every fish, and what you know of it"),
        ("j + direction", "pole-vault two cells (a staff trait)"),
        ("x", "look (Tab: next thing in view)"),
    ]),
    ("Windows", [
        ("i", "inventory (e equip, u use, d drop)"),
        ("e", "equipment (e take off, Enter swap)"),
        ("c", "character sheet"),
        ("k", "skills"),
        ("q", "quest log"),
        ("z", "ready your technique"),
        ("n", "choose a talent"),
        ("m", "the whole map"),
        ("v", "panel: minimap or messages"),
        ("l", "message log"),
        ("? or F1", "this key reference"),
        ("F2", "sound on or off"),
        ("Esc", "menu: save, load, quit"),
    ]),
    ("Aiming (after f)", [
        ("Tab", "next creature in range"),
        ("Move keys", "move the aim"),
        ("Enter or f", "shoot"),
    ]),
    ("In windows and conversations", [
        ("Up and down", "choose"),
        ("[ ] PgUp PgDn", "a page up or down"),
        ("Left/right, Tab", "switch tabs or sides"),
        ("Enter", "confirm (buy, sell, train...)"),
        ("1-9", "pick a choice when talking"),
        ("Esc", "close"),
    ]),
    ("In the city", [
        ("Gates", "step on one: the Brisering"),
        ("Guild stash", "chest in the stash room"),
        ("o (in the stash)", "sort: kind, name, worth"),
        ("Notice board", "requests, in the plaza"),
        ("Guild clerk", "at the window: dues, rank, pay"),
        ("Esc, Save game", "save (only in the city)"),
    ]),
]


class HelpScreen(ScrollScreen):
    """The key reference."""

    title = "Keys"

    def __init__(self) -> None:
        super().__init__()
        from game.input_handlers import HELP_KEYS
        self.close_keys = set(HELP_KEYS)

    def lines(self, engine, width: int):
        key_w = min(17, width // 2 - 1)
        out = []
        for heading, rows in KEY_REFERENCE:
            if out:
                out.append(("", TEXT))
            out.append((heading, ACCENT))
            for keys, what in rows:
                parts = textwrap.wrap(what, width - key_w - 1) or [""]
                out.append((f"{keys:<{key_w}} {parts[0]}", TEXT))
                for more in parts[1:]:
                    out.append((" " * (key_w + 1) + more, TEXT))
        return out


# ---- Travel-to ----------------------------------------------------------------------------
class TravelScreen:
    """Pick a known place; the Hunter walks there step by step (game/travel.py).
    ↑↓ or a number and Enter; Esc cancels. Every place is numbered (v0.64.0, user: the numbers
    stopped at 9). Typing a number goes there as soon as no longer number could be meant (with
    14 places, 3 goes at once; 1 waits for a second digit or Enter, so 1 then 2 is 12)."""

    def __init__(self, places: list) -> None:
        self.places = places
        self.selected = 0
        self.typed = ""

    def _go(self, engine):
        label, spot, beside = self.places[self.selected]
        engine.screen = None
        return TravelAction(label, spot, beside)

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        n = len(self.places)
        digit = DIGIT_KEYS.get(event.sym)
        if digit is not None:
            typed = self.typed + str(digit)
            if not (0 < int(typed) <= n):
                typed = str(digit)
            if not (0 < int(typed) <= n):
                self.typed = ""
                return None
            self.typed, self.selected = typed, int(typed) - 1
            if int(typed) * 10 > n:          # nothing longer could be meant
                self.typed = ""
                return self._go(engine)
            return None
        self.typed = ""
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % n
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % n
        elif event.sym in CONFIRM_KEYS:
            return self._go(engine)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        w = min(area_w - 2, 52)
        hint = wrapped("Walks there a step at a time; stops if anything comes up.", w - 4, DIM)
        h, visible, extra = fit_window(console, len(self.places), hint, top=2)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, "Travel to")
        first = max(0, min(self.selected - visible // 2, len(self.places) - visible))
        for r, (label, _, _) in enumerate(self.places[first : first + visible]):
            i = first + r
            row, bg = y + 2 + r, HIGHLIGHT if i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            width = len(str(len(self.places)))
            prefix = f"{i + 1:>{width}}. "
            console.print(x + 2, row, (prefix + label[0].upper() + label[1:])[: w - 4], fg=TEXT, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 3 + visible + i, text, fg=color, bg=BG)
        keys = "↑↓ or a number  Enter go  Esc" if len(self.places) > 9 else "↑↓ or 1-9 choose  Enter go  Esc"
        console.print(x + 2, y + h - 2, keys[: w - 4], fg=DIM, bg=BG)

class CharacterScreen(ScrollScreen):
    """The character sheet, in three tabs (user, v0.72.0; before, one long scrolling page):
    Hunter (who, bars, attributes one at a time, fighting numbers, condition), Guild (rank and
    what the next one takes, money and dues, words and notes) and Calling (calling, prey,
    talents). ←→ or Tab change tab; on Hunter, ↑↓ pick an attribute to read about; elsewhere
    they scroll if a tab runs long. Esc or c closes. Lines are built from coloured pieces."""

    GOOD = (140, 205, 120)
    HP_BAR = (200, 72, 60)
    XP_BAR = (120, 165, 225)
    GOLD = (232, 196, 100)
    RULE = (90, 80, 70)
    TABS = ("hunter", "guild", "calling")
    TAB_NAMES = {"hunter": "Hunter", "guild": "Guild", "calling": "Calling"}

    def __init__(self) -> None:
        super().__init__()
        from game.input_handlers import CHARACTER_KEY
        self.close_keys = {CHARACTER_KEY}
        self.tab = "hunter"
        self.attr = 0

    @property
    def title(self):
        return self._title

    def footer(self) -> str:
        if self.tab == "hunter":
            return "↑↓ attribute  ←→ tab  e equipment  k skills  Esc"
        return "←→ tab  ↑↓ scroll  e equipment  k skills  Esc"

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        tabs = self.TABS
        if tabs and event.sym in (KeySym.LEFT, KeySym.RIGHT, KeySym.TAB, KeySym.KP_4, KeySym.KP_6) \
                or (tabs and event.sym in (_key("a"), _key("d"))):
            step = -1 if event.sym in (KeySym.LEFT, KeySym.KP_4, _key("a")) else 1
            self.tab = tabs[(tabs.index(self.tab) + step) % len(tabs)]
            self.top = 0
            return None
        if tabs and self.tab == "hunter" and (event.sym in UP_KEYS or event.sym in DOWN_KEYS):
            from game.stats import ATTRIBUTES
            self.attr = (self.attr + (-1 if event.sym in UP_KEYS else 1)) % len(ATTRIBUTES)
            return None
        from game.input_handlers import EQUIPMENT_KEY, SKILLS_KEY
        if tabs and event.sym == EQUIPMENT_KEY:
            engine.screen = EquipmentScreen()
            return None
        if tabs and event.sym == SKILLS_KEY:
            engine.screen = SkillsScreen()
            return None
        return super().handle(event, engine)

    # A line is a list of (text, colour) pieces.
    def heading(self, name: str, width: int) -> list:
        return [(f"── {name} ", ACCENT), ("─" * max(0, width - len(name) - 4), self.RULE)]

    def bar(self, label: str, now: int, most: int, color, width: int = 20, note: str = "") -> list:
        filled = 0 if most <= 0 else round(width * max(0, min(now, most)) / most)
        return [(f"{label:<4}", DIM), ("█" * filled, color), ("░" * (width - filled), self.RULE),
                (f" {now}/{most}", TEXT), (note, DIM)]

    @staticmethod
    def side_by_side(left: list, right: list, lw: int) -> list:
        """Two columns of lines: the left padded to `lw` characters."""
        out = []
        for i in range(max(len(left), len(right))):
            a = left[i] if i < len(left) else []
            b = right[i] if i < len(right) else []
            n = sum(len(t) for t, _ in a)
            out.append(a + [(" " * max(1, lw - n), TEXT)] + b)
        return out

    def lines(self, engine, width: int):
        self._title = engine.player.full_name
        return {"hunter": self.hunter_lines, "guild": self.guild_lines,
                "calling": self.calling_lines}[self.tab](engine, width)

    # ---- Hunter --------------------------------------------------------------------------------------
    def hunter_lines(self, engine, width: int):
        from game.engine import JODEBRIS, HP_LOW
        from game.stats import ATTRIBUTES
        from game import aging, ranks, artifacts, injuries
        p, st = engine.player, engine.player.stats
        rank = ranks.of(p)["name"]
        L: list[list] = []
        L.append([(f"Level {st.level} ", TEXT), (rank, self.GOLD),
                  (f"  ·  {p.gender.capitalize()}" if p.gender else "", DIM),
                  (f"  ·  {aging.describe(aging.age_of(p, engine.day))}", DIM)])
        bw = max(8, min(20, (width - 26) // 2))
        hp = self.bar("HP", st.hp, st.max_hp, HP_LOW if st.hp * 3 < st.max_hp else self.HP_BAR, bw)
        xp = self.bar("XP", st.xp, st.xp_to_next, self.XP_BAR, bw)
        if sum(len(t) for t, _ in hp + xp) + 3 <= width:
            L.append(hp + [("   ", TEXT)] + xp)
        else:
            L += [hp, xp]
        w = p.windcatcher
        L.append([("JB  ", DIM), (f"{w.type.name}: {artifacts.charge_words(w)}", JODEBRIS)] if w is not None
                 else [("JB  ", DIM), ("no windcatcher", self.RULE)])

        lw = max(24, width // 2)
        # Attributes, with what's raising or lowering them; the picked one is described below.
        left = [self.heading("Attributes", lw - 2)]
        for i, a in enumerate(ATTRIBUTES):
            base, now = st.attributes[a.key], st[a.key]
            why = []
            age = p.age_mods.get(a.key, 0) if hasattr(p, "age_mods") and isinstance(p.age_mods, dict) else 0
            if age:
                why.append(f"{age:+d} age")
            hurt = now - base - age
            if hurt:
                why.append(f"{hurt:+d} injury" if hurt < 0 else f"{hurt:+d}")
            sel = i == self.attr
            row = [("►" if sel else " ", ACCENT), (f"{a.name:<12}", TEXT if sel else DIM), (f"{now:>3}", TEXT)]
            if why:
                diff = now - base
                row.append((f" ({', '.join(why)})", self.GOOD if diff > 0 else WARN))
            left.append(row)
        # Fighting, then condition
        dmg = p.damage_dice + (f"{p.damage_bonus:+d}" if p.damage_bonus else "")
        rw = width - lw
        right = [self.heading("In a fight", rw)]
        right.append([("Accuracy ", DIM), (f"{p.accuracy:<4}", TEXT), ("Armour ", DIM), (f"{p.armor}", TEXT)])
        right.append([("Evasion  ", DIM), (f"{p.evasion:<4}", TEXT), ("Damage ", DIM), (dmg, TEXT)])
        if p.light_bonus:
            right.append([("Light    ", DIM), (f"+{p.light_bonus}", self.GOLD)])
        if p.dazed:
            right.append([("Dazed", WARN), (f" {p.dazed} more turns", DIM)])
        if p.readied:
            right.append([("Readied ", DIM), (p.readied, self.GOLD)])
        elif p.tech_rest:
            right.append([("Technique rests ", DIM), (f"{p.tech_rest}", TEXT)])
        # Condition, under the fight numbers: injuries, faints, dues, things waiting for you
        cond = []
        for inj in p.injuries:
            it = injuries.table()[inj.id]
            if it.mends is None:
                when = "needs a healer"
            else:
                left_p = max(0, it.mends - (engine.day - inj.since))
                when = f"mends in {left_p} Pulse{'s' if left_p != 1 else ''}"
            cond.append((f"! {it.name}: {it.effect_text()}; {when}", WARN))   # (running bleeds: the side panel)
        if engine.hunt:
            faints = engine.faints_left()
            cond.append((f"Faints {faints}/{p.faint_limit}" + ("" if engine.hunt.faints_earned >= p.faint_limit
                                                               else " (a new area earns one)"), DIM if faints else WARN))
        if p.dues_owed:
            cond.append((f"Dues owed ♦ {p.dues_owed}: pay the clerk", WARN))
        from game import rest as _rest              # (v0.88.0)
        if engine.hunt and p.weary:
            cond.append((_rest.weary_line(p.weary) + ": less HP, accuracy and evasion, slower healing", WARN))
        elif not engine.hunt and _rest.pulses_owed(p):
            cond.append((_rest.owed_line(engine) + ": sleep it off (a bed is quicker), or it's rested off at the Wayfinder",
                         WARN if _rest.pulses_owed(p) >= _rest.reckon(engine) else DIM))
        if p.talent_offers:
            cond.append(("A talent to choose: press n", ACCENT))
        from game import skills as skills_mod
        ready = sum(1 for sid, sk in engine.skills.items() if skills_mod.is_ready(sk, p.skill(sid)))
        if ready:
            cond.append((f"{ready} ready to train (k)", self.GOOD))
        if cond:
            right.append([("", TEXT)])
            right.append(self.heading("Condition", rw))
            for t, c in cond:
                for line, cc in wrapped(t, rw, c):
                    right.append([(line, cc)])
        # The picked attribute's description, under the attributes
        at = ATTRIBUTES[self.attr]
        left.append([("", TEXT)])
        for line, c in wrapped(f"{at.name}: {at.description}", lw - 2, DIM):
            left.append([(line, c)])
        L += self.side_by_side(left, right, lw)
        return L

    # ---- Guild ---------------------------------------------------------------------------------------
    def guild_lines(self, engine, width: int):
        from game import ranks, archive, keywords
        p = engine.player
        L: list[list] = []
        def note(t, color=DIM, indent="  "):
            for line, c in wrapped(t, width - len(indent), color):
                L.append([(indent, DIM), (line, c)])
        L.append(self.heading("Rank", width))
        nxt = ranks.next_rank(p)
        L.append([("Rank ", DIM), (ranks.of(p)["name"], self.GOLD)] +
                 ([("   next: ", DIM), (nxt["name"], self.GOLD)] if nxt else [("   the highest there is", DIM)]))
        if nxt is not None:
            for label, have, need in (("Hunts", p.hunts_done, nxt["hunts"]), ("Level", p.stats.level, nxt["level"])):
                row = self.bar(label, min(have, need), need, self.GOOD if have >= need else self.XP_BAR, 12)
                row[0] = (f"{label:<6}", DIM)
                row.append(("  √" if have >= need else "", self.GOOD))
                L.append([("  ", TEXT)] + row)
            fee_ok = p.shards >= nxt["fee"]
            L.append([("  Fee   ", DIM), (f"♦ {nxt['fee']}", TEXT), (f"  (you have ♦ {p.shards})", self.GOOD if fee_ok else DIM)])
            if ranks.ready(p):
                note("Ready: sit for it at the clerk's window.", self.GOOD)
        L.append([("", TEXT)])
        L.append(self.heading("Money and dues", width))
        share = engine.dues_share
        total = p.earned + p.earned_free
        L.append([("Earned this Judgment ", DIM), (f"♦ {total}", TEXT)])
        if p.earned_free:
            note(f"{p.earned_free} of it is Guild pay, which owes no dues.")
        L.append([("Dues so far ", DIM), (f"♦ {engine.dues_so_far}", self.GOLD),
                  (f"  ({round(share * 100)}% of ♦ {p.earned}, due next Judgment)", DIM)])
        if p.dues_owed:
            L.append([("Dues owed now ", WARN), (f"♦ {p.dues_owed}", WARN), ("  pay the clerk", DIM)])
        L.append([("", TEXT)])
        L.append(self.heading("Words and notes", width))
        kw = engine.regions.keywords
        counts = []
        for slot in keywords.SLOTS:
            ordinary = kw.ordinary(slot)
            known = sum(1 for wid in kw.words[slot] if wid in engine.words)
            counts.append(f"{known} {slot}")
        L.append([("Wayfinder words known ", DIM), (", ".join(counts), TEXT)])
        if archive.has_notes(p):
            n = p.notes
            note(f"Field notes for the clerk: {len(n.get('seen', []))} creatures seen, "
                 f"{sum(n.get('kills', {}).values())} kills, {len(n.get('reached', {}))} places scouted.", ACCENT, "")
        else:
            L.append([("No field notes to report.", DIM)])
        return L

    # ---- Calling -------------------------------------------------------------------------------------
    def calling_lines(self, engine, width: int):
        from game import mastery, talents
        p = engine.player
        L: list[list] = []
        L.append(self.heading("Calling", width))
        for line, c in wrapped(mastery.calling_line(p), width, TEXT):
            L.append([(line, c)])
        from game import livings                     # (v0.95.0) the living the middle name follows
        for line, c in wrapped(livings.sheet_line(p), width, DIM):
            L.append([(line, c)])
        L.append([("", TEXT)])
        L.append(self.heading("Prey", width))
        prey = mastery.prey_lines(engine)
        if not prey:
            L.append([("No kills yet.", DIM)])
        for name, n, what in prey[:8]:
            L.append([(f"{name[:20].capitalize():<20}", TEXT), (f"{n:>4} ", self.GOLD), (what, DIM)])
        if len(prey) > 8:
            L.append([(f"and {len(prey) - 8} more kinds", DIM)])
        L.append([("", TEXT)])
        L.append(self.heading(f"Talents ({len(p.talents)})", width))
        for tid in p.talents:
            t = talents.pool().get(tid)
            if t:
                L.append([("☼ ", self.GOLD), (t["name"], TEXT)])
                for line, c in wrapped(t["description"], width - 2, DIM):
                    L.append([("  ", DIM), (line, c)])
        if p.talent_offers:
            L.append([("A talent to choose: press n", ACCENT)])
        lvl = (p.stats.level // talents.every() + 1) * talents.every()
        L.append([("Next talent at level ", DIM), (str(lvl), TEXT)])
        return L

    def text(self, engine, width: int = 66) -> str:
        """The whole sheet as plain text, every tab (for tests and searching)."""
        keep_tab = self.tab
        parts = []
        for tab in (self.TABS or (None,)):
            if tab is not None:
                self.tab = tab
            parts.append(" ".join("".join(t for t, _ in pieces) for pieces in self.lines(engine, width)))
        self.tab = keep_tab
        return " ".join(" ".join(parts).split())

    def render(self, console, engine: "Engine", area_w: int) -> None:
        w = min(area_w - 2, 70)
        h = console.height - 2
        x, y = (area_w - w) // 2, 1
        rows = self.lines(engine, w - 4)
        top_rows = 0                                    # (the tabs sit on the top border)
        self.page = h - 4 - top_rows
        last = max(0, len(rows) - self.page)
        if self.top is None:
            self.top = 0
        self.top = max(0, min(self.top, last))
        draw_box(console, x, y, w, h, self.title)
        if self.TABS:                                   # the tabs, on the top border at the right
            labels = [f" {self.TAB_NAMES[tab]} " for tab in self.TABS]
            tx = x + w - 2 - sum(len(l) + 1 for l in labels) + 1
            for tab, label in zip(self.TABS, labels):
                sel = tab == self.tab
                console.print(tx, y, label, fg=TEXT if sel else DIM, bg=HIGHLIGHT if sel else BG)
                tx += len(label) + 1
        for i, pieces in enumerate(rows[self.top : self.top + self.page]):
            cx = x + 2
            for t, color in pieces:
                room = x + w - 2 - cx
                if room <= 0:
                    break
                console.print(cx, y + 1 + top_rows + i, t[:room], fg=color, bg=BG)
                cx += len(t[:room])
        if last:
            where = f" {self.top + 1}-{min(len(rows), self.top + self.page)} of {len(rows)} "
            console.print(x + w - 2 - len(where), y + h - 1, where, fg=DIM, bg=BG)
        console.print(x + 2, y + h - 2, self.footer()[: w - 4], fg=DIM, bg=BG)


SKILL_GROUPS = [   # (heading, skill ids) for the skills window; anything not listed goes under "Other"
    ("Weapons", ["blades", "knives", "axes", "hafted", "brawling", "claws", "whips", "staves", "polearms",
                 "marksmanship", "crossbows"]),
    ("In the field", ["tracking", "stealth", "harvesting", "survival", "medicine", "angling"]),
    ("Knowledge and trade", ["identification", "scholarship", "bargaining"]),
    ("Jodebris", ["attunement"]),
]


class SkillsScreen(CharacterScreen):
    """Every skill, grouped, with rank, practice and what it gives (k, v0.59.1: moved off the character
    sheet, which had grown long). Scrolls; Esc or k closes."""

    TABS = ()

    def __init__(self) -> None:
        super().__init__()
        from game.input_handlers import SKILLS_KEY
        self.close_keys = {SKILLS_KEY}

    def footer(self) -> str:
        return "↑↓ scroll  [ ] page  Esc or k close"

    def lines(self, engine, width: int):
        p = engine.player
        self._title = f"Skills: {p.full_name}"
        L: list[list] = []
        listed = [sid for _, ids in SKILL_GROUPS for sid in ids]
        groups = SKILL_GROUPS + [("Other", [sid for sid in engine.skills if sid not in listed])]
        for heading, ids in groups:
            ids = [sid for sid in ids if sid in engine.skills]
            if not ids:
                continue
            if L:
                L.append([("", TEXT)])
            L.append(self.heading(heading, width))
            L += self.skill_rows(engine, ids, width)
        return L

    def skill_rows(self, engine, ids, width: int):
        p = engine.player
        L: list[list] = []
        names = [r.name for r in sorted(engine.catalogue.rarities.values(), key=lambda r: r.tier)]
        from game import skills as skills_mod
        for sid in ids:
            skill = engine.skills[sid]
            state = p.skill(sid)
            row = [(f"{skill.name:<15}", TEXT), (f"rank {state.rank}  ", self.GOLD)]
            if state.rank >= skill.max_rank:
                row.append(("mastered", self.GOOD))
            else:
                need = skill.needed(state.rank)
                filled = round(10 * min(state.practice, need) / need)
                ready = skills_mod.is_ready(skill, state)
                row += [("█" * filled, self.GOOD if ready else self.XP_BAR), ("░" * (10 - filled), self.RULE),
                        (f" {state.practice}/{need}", DIM)]
                if ready:
                    row.append(("  ready to train", self.GOOD))
            L.append(row)
            note = ""
            if sid == "scholarship":
                note = f"Reads writings up to difficulty {state.rank}. Writings read: {len(p.read_writings)}."
            elif sid == "medicine":
                from game import medicine
                extra = ", and bandages mend minor injuries" if state.rank >= medicine.MEND_MINOR_RANK else ""
                note = f"Bandages and poultices work {medicine.chance(p)}% of the time{extra}."
            elif sid == "identification":
                broken = engine.catalogue.artifacts()
                known = sum(1 for t in broken if t.id in p.known_artifacts)
                note = f"Up to {names[min(state.rank, len(names)) - 1]}. Kinds identified: {known} of {len(broken)}."
            from game import weaponskills, fieldskills, attunement, bargaining
            for extra in (weaponskills.sheet_lines(engine, sid) + fieldskills.sheet_lines(engine, sid)
                          + attunement.sheet_lines(engine, sid) + bargaining.sheet_lines(engine, sid)):
                note = (note + " " + extra).strip()
            if note:
                for line, c in wrapped(note, width - 2, DIM):
                    L.append([("  ", DIM), (line, c)])
        return L


# ---- Odd jobs (from the guild clerk) and the plaza notice board ----------------------------
class JobBoardScreen:
    """The bounty board (v0.45.0): bounties and scouting. Board (take one with Enter) and Yours
    (progress; d drops one).
    ←→ or Tab switches. Takes no time."""

    def __init__(self) -> None:
        self.tab = "board"
        self.selected = 0
        self.notice = ""

    def rows(self, engine):
        return engine.job_board if self.tab == "board" else engine.player.jobs

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import work
        from game.input_handlers import _key
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in TAB_KEYS:
            self.tab = "yours" if self.tab == "board" else "board"
            self.selected, self.notice = 0, ""
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
        elif rows and self.tab == "board" and event.sym in CONFIRM_KEYS:
            ok, self.notice = work.take_job(engine, rows[self.selected])
            if ok:
                engine.log(self.notice)
            self.selected = max(0, min(self.selected, len(self.rows(engine)) - 1))
        elif rows and self.tab == "yours" and event.sym == _key("d"):
            self.notice = work.drop_job(engine, rows[self.selected])
            self.selected = max(0, min(self.selected, len(self.rows(engine)) - 1))
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import work
        w = min(area_w - 2, 58)
        rows = self.rows(engine)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        extra = []
        if rows:
            from game import ranks
            job = rows[self.selected]
            region = engine.regions[job.region]
            extra.append((f"{region.name}  {danger_pips(region.danger[0])}  {region.depth} areas"[: w - 4], TEXT))
            how = {"kill": "The marked creature waits in the deepest area. Kill it on a trip there",
                   "find": "It lies somewhere in the deepest area. Bring it to the clerk (any of that kind will do)",
                   "scout": "Go that far on any trip there", "cull": "Do it on any trip there"}[job.kind]
            extra += wrapped(f"{how}; the Guild pays, and takes no dues from it.", w - 4, DIM)
            from game import story
            held = story.only(engine, "bounties")
            if job.story and engine.story_data.bounties.get(job.story, {}).get("description"):
                extra = wrapped(story.fill(engine, engine.story_data.bounties[job.story]["description"]), w - 4, ACCENT) + extra
            if self.tab == "board" and region.danger[0] > ranks.max_danger(engine.player.rank):
                extra.append((f"Posted for {ranks.plural(ranks.name(ranks.lowest_rank_for_danger(region.danger[0])))} and above", WARN))
            elif self.tab == "board" and held and job.story != held:
                extra += wrapped("The clerk asked you to take the one marked for you first.", w - 4, WARN)
            if self.tab == "yours":
                extra += wrapped(f"Progress: {job.status()}.", w - 4, TEXT)
        else:
            extra += wrapped("No jobs posted right now. New ones go up every Cycle." if self.tab == "board"
                             else "You haven't taken any jobs.", w - 4, DIM)
        if self.notice:
            extra += [("", DIM)] + wrapped(self.notice, w - 4, ACCENT)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, "Bounties and scouting")
        tx = x + 2
        for tab, label in (("board", " Board "), ("yours", f" Yours {len(engine.player.jobs)}/{work.MAX_JOBS} ")):
            active = self.tab == tab
            console.print(tx, y + 1, label, fg=BG if active else DIM, bg=ACCENT if active else BG)
            tx += len(label) + 1
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for r, job in enumerate(rows[first : first + visible]):
            row, bg = y + 3 + r, HIGHLIGHT if first + r == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            tag = f"{job.reward} ♦"
            color = ACCENT if (self.tab == "yours" and job.done) or job.story else TEXT
            from game import ranks, story
            held = story.only(engine, "bounties")
            if self.tab == "board" and (engine.regions[job.region].danger[0] > ranks.max_danger(engine.player.rank)
                                        or (held and job.story != held)):
                color = CANT
            console.print(x + 2, row, job.label(engine)[: w - 6 - len(tag)], fg=color, bg=bg)
            console.print(x + w - 2 - len(tag), row, tag, fg=TEXT, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        keys = "↑↓ choose  Enter take  ←→ tab  Esc" if self.tab == "board" else "↑↓ choose  d drop  ←→ tab  Esc"
        console.print(x + 2, y + h - 2, keys[: w - 4], fg=DIM, bg=BG)


class RequestBoardScreen:
    """The plaza notice board: what the people of Bytorsskug are asking for.
    Hand things over by talking to whoever asked. Esc closes."""

    def __init__(self) -> None:
        self.selected = 0

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        n = len(engine.requests)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS and n:
            self.selected = (self.selected - 1) % n
        elif event.sym in DOWN_KEYS and n:
            self.selected = (self.selected + 1) % n
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import work
        w = min(area_w - 2, 58)
        reqs = engine.requests
        self.selected = max(0, min(self.selected, len(reqs) - 1))
        extra = []
        if reqs:
            r = reqs[self.selected]
            folk = engine.townsfolk[r.folk_id]
            left = r.expires - engine.day
            extra += wrapped(f"{folk.full_name} wants {r.thing(engine.catalogue)}, and will pay {r.reward} shards. "
                             f"Up for {left} more Pulse{'s' if left != 1 else ''}. Talk to them to hand it over.",
                             w - 4, DIM)
            if r.kind == "item":
                extra += wrapped("They want that kind exactly: you'll need to have identified it.", w - 4, DIM)
            if r.kind == "errand":
                extra += wrapped(f"Choose {r.where} at the Wayfinder; it lies somewhere in the deepest area.", w - 4, DIM)
            if r.kind == "fish" and work.can_hand_over(engine, r) is None:
                extra += wrapped("Fresh from the water: any you've landed will do. Ask the tackleman what's biting.",
                                 w - 4, DIM)
            if r.kind == "material":
                have_n = engine.player.inventory.count_of(r.want)
                extra += wrapped(f"Creatures leave these. You have {have_n}.", w - 4,
                                 ACCENT if have_n >= r.count else DIM)
            elif work.can_hand_over(engine, r) is not None:
                extra += wrapped("You have one.", w - 4, ACCENT)
        else:
            extra += wrapped("Nothing posted right now. New notices go up every Cycle.", w - 4, DIM)
        h, visible, extra = fit_window(console, max(len(reqs), 1), extra, top=2)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, "Notice board")
        first = max(0, min(self.selected - visible // 2, len(reqs) - visible))
        for i, r in enumerate(reqs[first : first + visible]):
            row, bg = y + 2 + i, HIGHLIGHT if first + i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            tag = f"{r.reward} ♦"
            have = work.can_hand_over(engine, r) is not None
            text = r.thing(engine.catalogue)
            text = text[0].upper() + text[1:]
            console.print(x + 2, row, text[: w - 6 - len(tag)], fg=ACCENT if have else TEXT, bg=bg)
            console.print(x + w - 2 - len(tag), row, tag, fg=TEXT, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 3 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ read  Esc close"[: w - 4], fg=DIM, bg=BG)


# ---- Commissions (the smith) ----------------------------------------------------------------
class CraftScreen:
    """What a crafter makes (Enter commissions it: materials and fee up front),
    and your orders with them. ←→ or Tab switches. Takes no time."""

    def __init__(self, crafter: str) -> None:
        self.crafter = crafter
        self.tab = "make"
        self.selected = 0
        self.notice = ""

    def rows(self, engine):
        from game import crafting
        return engine.recipes[self.crafter] if self.tab == "make" else crafting.my_orders(engine, self.crafter)

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import crafting
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in TAB_KEYS:
            self.tab = "orders" if self.tab == "make" else "make"
            self.selected, self.notice = 0, ""
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
        elif rows and self.tab == "make" and event.sym in CONFIRM_KEYS:
            ok, self.notice = crafting.commission(engine, self.crafter, rows[self.selected])
            if ok:
                engine.log(self.notice)
        elif self.tab == "orders" and event.sym in CONFIRM_KEYS and crafting.ready_orders(engine, self.crafter):
            self.notice = crafting.collect(engine, self.crafter)
            engine.log(self.notice)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import crafting
        cat, p = engine.catalogue, engine.player
        w = min(area_w - 2, 58)
        rows = self.rows(engine)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        extra = []
        if self.tab == "make" and rows:
            r = rows[self.selected]
            t = cat[r.item]
            props = t.properties
            stats = ", ".join(f"{k} {props[k]}" for k in ("damage", "armor", "range") if k in props)
            extra += wrapped(f"{t.description} ({stats})" if stats else t.description, w - 4, DIM)
            for m, n in r.materials:
                have = p.inventory.count_of(m)
                mt = cat[m]
                extra.append((f"  {mt.name}: {have}/{n}", TEXT if have >= n else CANT))
            extra.append((f"  fee: {r.fee} shards   ready in {r.pulses} Pulses", TEXT if p.shards >= r.fee else CANT))
        elif self.tab == "orders":
            if rows:
                o = rows[self.selected]
                left = o.ready - engine.day
                extra += wrapped("Ready. Enter to collect." if left <= 0 else f"Ready in {left} Pulse{'s' if left != 1 else ''}.",
                                 w - 4, ACCENT if left <= 0 else DIM)
            else:
                extra += wrapped("You have nothing on order.", w - 4, DIM)
        if self.notice:
            extra += [("", DIM)] + wrapped(self.notice, w - 4, ACCENT)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        name = engine.townsfolk[self.crafter].full_name if self.crafter in engine.townsfolk else self.crafter
        draw_box(console, x, y, w, h, name)
        tx = x + 2
        for tab, label in (("make", " Commission "), ("orders", f" Orders {len(crafting.my_orders(engine))}/{crafting.MAX_ORDERS} ")):
            active = self.tab == tab
            console.print(tx, y + 1, label, fg=BG if active else DIM, bg=ACCENT if active else BG)
            tx += len(label) + 1
        purse = f"♦ {p.shards} shards"
        console.print(x + w - 2 - len(purse), y + 1, purse, fg=TEXT, bg=BG)
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for i, row_obj in enumerate(rows[first : first + visible]):
            row, bg = y + 3 + i, HIGHLIGHT if first + i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            t = cat[row_obj.item]
            if self.tab == "make":
                ok = not crafting.missing(engine, row_obj) and p.shards >= row_obj.fee
                tag = f"{row_obj.fee} ♦"
            else:
                ok = row_obj.ready <= engine.day
                tag = "ready" if ok else f"{row_obj.ready - engine.day} Pulses"
            console.print(x + 2, row, t.glyph, fg=t.color, bg=bg)
            console.print(x + 4, row, t.name[: w - 18], fg=TEXT if ok else CANT, bg=bg)
            console.print(x + w - 2 - len(tag), row, tag, fg=ACCENT if ok and self.tab == "orders" else TEXT, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        keys = ("↑↓ choose  Enter commission  ←→ tab  Esc" if self.tab == "make"
                else "↑↓ choose  Enter collect  ←→ tab  Esc")
        console.print(x + 2, y + h - 2, keys[: w - 4], fg=DIM, bg=BG)


# ---- Raising gear (equipment stage 2, v0.76.0) ----------------------------------------------
class UpgradeScreen:
    """Raise a weapon or armour piece a tier: at the smith (materials and a fee, any tier; the fee is
    only taken if it works) or at home on a forge or workbench (materials only, up to +3; materials
    from the home chest count too). Lists what you wear, then what's in the pack. A try that could
    destroy the piece asks first. Takes no time."""

    def __init__(self, at: str = "smith", title: str = "Raise a piece", only: str | None = None) -> None:
        self.at = at
        self.only = only          # "gear" (weapons and armour) or "tackle" (v0.96.0); None: both
        self.title = title
        self.selected = 0
        self.notice = ""

    def rows(self, engine) -> list:
        from game import gear, fishing
        p = engine.player
        slots = {"gear": gear.SLOTS, "tackle": fishing.TACKLE_SLOTS}.get(self.only, gear.SLOTS + fishing.TACKLE_SLOTS)
        worn = [p.equipped[s] for s in slots if p.equipped.get(s) is not None and gear.has_tier(p.equipped[s])]
        def fits(it):
            tackle = it.type.kind == "tackle"
            return gear.has_tier(it) and (self.only is None or (self.only == "tackle") == tackle)
        return worn + [it for it in p.inventory.items if fits(it)]

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import gear
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
            self.notice = ""
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
            self.notice = ""
        elif event.sym in CONFIRM_KEYS and rows:
            item = rows[min(self.selected, len(rows) - 1)]
            why = gear.blocked(engine, item, self.at)
            if why:
                self.notice = why
                return None
            to = item.tier + 1
            def go(e, item=item, back=self):
                outcome, msg = gear.upgrade(e, item, back.at)
                e.log(msg)
                back.notice = msg
                e.screen = back
            risk = gear.destroy_chance(to)
            if risk:
                engine.screen = ConfirmScreen(
                    f"Raise the {item.label} to +{to}? {gear.chance(to)}% chance of success. If it fails, "
                    f"{risk}% of the time the piece is destroyed.", on_yes=go,
                    on_no=lambda e, back=self: setattr(e, "screen", back))
            else:
                go(engine)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import gear
        cat, p = engine.catalogue, engine.player
        w = min(area_w - 2, 58)
        rows = self.rows(engine)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        extra = []
        if rows:
            item = rows[self.selected]
            to = item.tier + 1
            if self.at == "home" and to > gear.HOME_MAX:
                extra += wrapped(f"Past +{gear.HOME_MAX} is the smith's work.", w - 4, DIM)
            else:
                odds = f"To +{to}: {gear.chance(to)}% chance of success"
                risk = gear.destroy_chance(to)
                extra.append((odds + (f"; a failure destroys it {risk}% of the time." if risk else "."),
                              CANT if risk else TEXT))
                for mid, n in gear.material_bill(item.type, to).items():
                    have = gear.have(engine, mid, self.at)
                    extra.append((f"  {cat[mid].name}: {have}/{n}", TEXT if have >= n else CANT))
                if self.at in gear.PAID:
                    fee = gear.shard_cost(to)
                    extra.append((f"  fee: {fee} shards, only on success", TEXT if p.shards >= fee else CANT))
                else:
                    extra.append(("  no fee; materials in your home chest count", DIM))
                extra += wrapped("If it fails, the materials are lost" + ("; the fee isn't taken." if self.at in gear.PAID else "."),
                                 w - 4, DIM)
        else:
            extra += wrapped("You have no weapon or armour to work on.", w - 4, DIM)
        if self.notice:
            extra += [("", DIM)] + wrapped(self.notice, w - 4, ACCENT)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, self.title)
        if self.at in gear.PAID:
            purse = f"♦ {p.shards} shards"
            console.print(x + w - 2 - len(purse), y + 1, purse, fg=TEXT, bg=BG)
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for i, it in enumerate(rows[first : first + visible]):
            row, bg = y + 3 + i, HIGHLIGHT if first + i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            ok = gear.blocked(engine, it, self.at) is None
            tag = "worn" if p.is_equipped(it) else ""
            console.print(x + 2, row, it.type.glyph, fg=it.type.color, bg=bg)
            console.print(x + 4, row, it.label[: w - 14], fg=TEXT if ok else CANT, bg=bg)
            console.print(x + w - 2 - len(tag), row, tag, fg=DIM, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  Enter raise it  Esc"[: w - 4], fg=DIM, bg=BG)


# ---- The healer ------------------------------------------------------------------------------
class TreatScreen:
    """Your injuries and what the healer charges for each; Enter pays and treats. Takes no time."""

    def __init__(self, healer: str) -> None:
        self.healer = healer
        self.selected = 0
        self.notice = ""

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import injuries
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = engine.player.injuries
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
        elif rows and event.sym in CONFIRM_KEYS:
            ok, self.notice = injuries.treat(engine.player, rows[self.selected].id)
            if ok:
                engine.log(self.notice)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import injuries
        p = engine.player
        w = min(area_w - 2, 58)
        rows = p.injuries
        self.selected = max(0, min(self.selected, len(rows) - 1))
        extra = []
        if rows:
            inj = rows[self.selected]
            it = injuries.table()[inj.id]
            extra += wrapped(it.description, w - 4, DIM)
            extra += wrapped(it.effect_text(), w - 4, WARN)
            if it.mends is not None:
                left = max(0, it.mends - (engine.day - inj.since))
                extra += wrapped(f"Minor: it mends on its own in {left} Pulse{'s' if left != 1 else ''}.", w - 4, DIM)
            else:
                extra += wrapped("Serious: it won't mend on its own.", w - 4, DIM)
        else:
            extra += wrapped("Nothing wrong with you that I can fix.", w - 4, DIM)
        if self.notice:
            extra += [("", DIM)] + wrapped(self.notice, w - 4, ACCENT)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        name = engine.townsfolk[self.healer].full_name if self.healer in engine.townsfolk else self.healer
        draw_box(console, x, y, w, h, name)
        console.print(x + 2, y + 1, "Treatment", fg=DIM, bg=BG)
        purse = f"♦ {p.shards} shards"
        console.print(x + w - 2 - len(purse), y + 1, purse, fg=TEXT, bg=BG)
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for i, inj in enumerate(rows[first : first + visible]):
            it = injuries.table()[inj.id]
            row, bg = y + 3 + i, HIGHLIGHT if first + i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            tag = f"{injuries.fee(it)} ♦"
            console.print(x + 2, row, it.name.capitalize()[: w - 6 - len(tag)],
                          fg=TEXT if p.shards >= injuries.fee(it) else CANT, bg=bg)
            console.print(x + w - 2 - len(tag), row, tag, fg=TEXT, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  Enter treat  Esc close"[: w - 4], fg=DIM, bg=BG)


# ---- Writings and the Academy library ----------------------------------------------------------
class ReadingScreen(ScrollScreen):
    """A writing's text. Esc closes (back to the library, if opened from there)."""

    def __init__(self, title: str, text: str, back=None) -> None:
        super().__init__()
        self.title = title
        self.text = text
        self.back = back

    def footer(self) -> str:
        return "↑↓ scroll  Esc close"

    def handle(self, event, engine: "Engine") -> Action | None:
        super().handle(event, engine)
        if engine.screen is None and self.back is not None:
            engine.screen = self.back
        return None

    def lines(self, engine, width: int):
        out = []
        for para in self.text.split("\n"):
            out += wrapped(para, width, TEXT) + [("", TEXT)]
        return out[:-1]


class LibraryScreen:
    """The Academy library: every writing Hunters have brought back. Enter reads one."""

    def __init__(self) -> None:
        self.selected = 0

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = engine.library
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
        elif rows and event.sym in CONFIRM_KEYS:
            w = engine.catalogue[rows[self.selected]].writing
            engine.screen = ReadingScreen(w["title"], w["text"], back=self)
            from game import library
            library.teach(engine, engine.catalogue[rows[self.selected]])   # (only with the Scholarship for it)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import library
        cat = engine.catalogue
        w = min(area_w - 2, 58)
        rows = engine.library
        self.selected = max(0, min(self.selected, len(rows) - 1))
        total = len([t for t in library.writings(cat) if not t.properties.get("story") or t.id in rows])   # (story writings count once shelved)
        extra = []
        if rows:
            t = cat[rows[self.selected]]
            extra += wrapped(f"{t.appearance[1].split(' Read it')[0]} Enter to read.", w - 4, DIM)
        else:
            extra += wrapped("The Hunters' shelf is empty. Bring back what you find written out there.", w - 4, DIM)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, "The Academy library")
        console.print(x + 2, y + 1, f"Brought back by Hunters: {len(rows)} of {total} known"[: w - 4], fg=DIM, bg=BG)
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for i, wid in enumerate(rows[first : first + visible]):
            row, bg = y + 3 + i, HIGHLIGHT if first + i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            console.print(x + 2, row, cat[wid].writing["title"][: w - 4], fg=TEXT, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  Enter read  Esc close"[: w - 4], fg=DIM, bg=BG)


# ---- The Guild archive ------------------------------------------------------------------------------
class ArchiveScreen:
    """The Guild archive: the bestiary and scouting reports. ←→ or Tab switches."""

    LEVELS = {1: "sighted", 2: "fought", 3: "full entry"}

    def __init__(self) -> None:
        self.tab = "bestiary"
        self.selected = 0

    def rows(self, engine) -> list[str]:
        from game import archive
        if self.tab == "bestiary":
            known = [c for c in engine.monster_types if archive.level(engine.archive, c)]
            return sorted(known, key=lambda c: (engine.monster_types[c].tier, engine.monster_types[c].name))
        # places some Hunter has reported scouting (there are hundreds of places)
        reported = [r for r in engine.archive.get("regions", {}) if r in engine.regions]
        return sorted(reported, key=lambda r: (engine.regions[r].danger, engine.regions[r].name))

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in TAB_KEYS:
            self.tab = "regions" if self.tab == "bestiary" else "bestiary"
            self.selected = 0
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import archive
        w = min(area_w - 2, 60)
        rows = self.rows(engine)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        extra = []
        if rows:
            rid = rows[self.selected]
            lines = (archive.creature_lines(engine, rid, engine.catalogue) if self.tab == "bestiary"
                     else archive.region_lines(engine, rid))
            for line in lines:
                extra += wrapped(line, w - 4, DIM)
        else:
            extra += wrapped("Nothing on record yet. Report what you see out there to the clerk.", w - 4, DIM)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, "The Guild archive")
        tx = x + 2
        known = len([c for c in engine.monster_types if archive.level(engine.archive, c)])
        for tab, label in (("bestiary", f" Bestiary {known}/{len(engine.monster_types)} "), ("regions", " Scouting ")):
            active = self.tab == tab
            console.print(tx, y + 1, label, fg=BG if active else DIM, bg=ACCENT if active else BG)
            tx += len(label) + 1
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for i, rid in enumerate(rows[first : first + visible]):
            row, bg = y + 3 + i, HIGHLIGHT if first + i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            if self.tab == "bestiary":
                name, tag = engine.monster_types[rid].name, self.LEVELS[archive.level(engine.archive, rid)]
            else:
                r = engine.regions[rid]
                name, tag = r.name, (f"to area {engine.archive['regions'][rid]}" if rid in engine.archive["regions"]
                                     else "unscouted")
            shown = name if name.startswith("[") else name.capitalize()   # (keyword places keep their case)
            console.print(x + 2, row, shown[: w - 6 - len(tag)], fg=TEXT, bg=bg)
            console.print(x + w - 2 - len(tag), row, tag, fg=DIM, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  ←→ tab  Esc close"[: w - 4], fg=DIM, bg=BG)


# ---- The Hall of Hunters -------------------------------------------------------------------------------
class HallScreen(ScrollScreen):
    """Every Hunter who has retired or died, newest first: name, age, level, hunts, how it ended."""

    title = "The Hall of Hunters"

    def footer(self) -> str:
        return "↑↓ scroll  Esc close"

    def lines(self, engine, width: int):
        from game import aging, recovery
        if not engine.hall:
            return wrapped("No names here yet. Every Hunter who retires or falls is remembered in the hall.", width, DIM)
        out = []
        for entry in reversed(engine.hall):
            date = engine.calendar.date(entry["ended"]).short
            out.append((entry["name"], ACCENT))
            rank = f"{entry['rank']}, l" if entry.get("rank") else "L"
            out += wrapped(f"{rank}evel {entry['level']}, {entry['hunts']} hunt{'s' if entry['hunts'] != 1 else ''} completed; "
                           f"{entry['cause']} on {date}, having seen {aging.describe(entry['age'])}."
                           + recovery.hall_line(entry, engine), width, TEXT)
            out.append(("", TEXT))
        return out[:-1]


# ---- The story: scenes and the quest log ------------------------------------------------------------------
class SceneScreen:
    """A scripted scene (data/story): pages of text, one at a time (any key turns the page),
    then choices if it has any (↑↓ or 1-9, Enter). Takes no time."""

    def __init__(self, scene_id: str, engine=None) -> None:
        self.scene_id = scene_id
        self.texts = None     # each page's text, variants chosen once (v0.66.0)
        self.page = 0
        self.selected = 0
        self.sub = 0          # first line shown, when a page is taller than the screen
        self.more = False

    def scene(self, engine) -> dict:
        return engine.story_data.scenes[self.scene_id]

    def choices(self, engine) -> list:
        from game.dialogue import all_hold
        return [c for c in self.scene(engine).get("choices", []) if all_hold(engine, c.get("if"))]

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import story
        from game.dialogue import apply
        if not isinstance(event, tcod.event.KeyDown):
            return None
        pages = self.scene(engine)["pages"]
        if self.more:                          # the rest of a long page first
            self.sub += max(1, getattr(self, "room", 12) - 1)    # (one line kept, for context)
            return None
        if self.page < len(pages) - 1:
            self.page += 1
            self.sub = 0
            return None
        choices = self.choices(engine)
        if not choices:
            engine.screen = None
            story.show_next_scene(engine)
            return None
        number = NUMBER_KEYS.get(event.sym)
        if event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(choices)
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(choices)
        elif event.sym in CONFIRM_KEYS or (number is not None and number < len(choices)):
            choice = choices[number if number is not None else self.selected]
            engine.screen = None
            opens = apply(engine, choice.get("do"))
            story.check(engine)
            if opens:
                engine.open_vendor(opens)
            else:
                story.show_next_scene(engine)
        return None

    def text_lines(self, engine, w: int) -> list:
        """This page's text, wrapped: a blank line between paragraphs (blank lines in the text),
        never two in a row (v0.54.1, user: popups looked oddly cut)."""
        from game import story
        pages = self.scene(engine)["pages"]
        if self.texts is None:            # variants are picked once, when the scene first shows
            self.texts = [story.text(engine, f"scene:{self.scene_id}:{i}",
                                     pg["text"] if isinstance(pg, dict) else pg) for i, pg in enumerate(pages)]
        page = pages[self.page]
        speaker = page.get("speaker", "") if isinstance(page, dict) else ""
        lines = []
        if speaker:
            lines.append((story.fill(engine, speaker), ACCENT))
        paras = [p.strip() for p in self.texts[self.page].split("\n")]
        for i, para in enumerate(paras):
            if para:
                lines += wrapped(para, w - 4, TEXT)
            elif lines and lines[-1][0]:
                lines.append(("", TEXT))
        return lines

    def choice_lines(self, engine, w: int) -> list:
        """The choices, numbered; a long one wraps under its own text, not under a new number."""
        from game import story
        out = []
        for i, c in enumerate(self.choices(engine)):
            parts = textwrap.wrap(story.fill(engine, c["text"]), w - 7) or [""]
            colour = ACCENT if i == self.selected else TEXT
            out.append((f"{i + 1}. {parts[0]}", colour))
            out += [(f"   {more}", colour) for more in parts[1:]]
        return out

    def render(self, console, engine: "Engine", area_w: int) -> None:
        sc = self.scene(engine)
        w = min(area_w - 2, 64)
        last = self.page == len(sc["pages"]) - 1
        text = self.text_lines(engine, w)
        choices = self.choice_lines(engine, w) if last else []
        room = console.height - 2 - 4                     # rows inside the box, less the footer
        self.room = room
        body = text + ([("", TEXT)] + choices if choices else [])
        # Too long for the screen: show it a screenful at a time (any key shows more).
        self.more = len(body) > room and self.sub + room < len(body)
        if len(body) > room:
            body = body[self.sub : self.sub + room]
        footer = ("any key: more" if self.more else
                  ("↑↓ choose  Enter" if choices else "any key: continue") if last else "any key: next page")
        h = len(body) + 4
        style = sc.get("style")
        if style not in ("popup", "tip"):     # a popup (v0.54.0) or a tip (v0.66.0) sits over the map
            console.rgb["bg"][:area_w, :] = (10, 9, 8)
            console.rgb["ch"][:area_w, :] = ord(" ")
        x, y = (area_w - w) // 2, (console.height - h) // 2
        if style == "tip":                   # how to play, not what's happening: its own look
            draw_box(console, x, y, w, h, sc.get("title") or "Tip", frame=TIP_FRAME, title_fg=TIP_FRAME)
        else:
            draw_box(console, x, y, w, h, sc.get("title", ""))
        for i, (t, color) in enumerate(body):
            console.print(x + 2, y + 1 + i, t[: w - 4], fg=color, bg=BG)
        pages = f" {self.page + 1}/{len(sc['pages'])} " if len(sc["pages"]) > 1 else ""
        console.print(x + 2, y + h - 2, footer[: w - 4], fg=DIM, bg=BG)
        if pages:
            console.print(x + w - 2 - len(pages), y + h - 1, pages, fg=DIM, bg=BG)


class WorksScreen:
    """The Guild's works (v0.60.0), from the clerk: every project, the Guild's focus, progress, and
    paying in. ↑↓ a project, ←→ how much to give, Enter gives it. Esc leaves."""

    AMOUNTS = [10, 50, 100, 500, 1000]

    def __init__(self) -> None:
        self.selected = 0
        self.amount = 1
        self.notice = ""

    def rows(self, engine):
        from game import works
        return list(works.projects())

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import works
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(rows)
        elif event.sym in (KeySym.LEFT, KeySym.KP_4, _key("a")):
            self.amount = max(0, self.amount - 1)
        elif event.sym in (KeySym.RIGHT, KeySym.KP_6, _key("d")):
            self.amount = min(len(self.AMOUNTS), self.amount + 1)
        elif event.sym in CONFIRM_KEYS:
            pid = rows[self.selected]
            want = engine.player.shards if self.amount >= len(self.AMOUNTS) else self.AMOUNTS[self.amount]
            ok, self.notice = works.contribute(engine, pid, want)
            if ok:
                engine.log(self.notice)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import works
        p = engine.player
        rows = self.rows(engine)
        w = min(area_w - 2, 70)
        h = console.height - 2
        x, y = (area_w - w) // 2, 1
        draw_box(console, x, y, w, h, "The Guild's works")
        focus = works.focus(engine)
        st = works.state(engine)
        for i, pid in enumerate(rows):
            proj = works.projects()[pid]
            n = works.tiers_done(engine, pid)
            done = works.finished(engine, pid)
            row = y + 1 + i
            bg = HIGHLIGHT if i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            name = works.tier_name(pid, min(n, len(proj["tiers"]) - 1)) if not done else proj["name"]
            mark = "built" if done else (f"{st['progress'].get(pid, 0)}/{works.next_tier(engine, pid)['cost']}")
            console.print(x + 2, row, ("» " if pid == focus else "  ") + name[: w - 22], fg=CANT if done else (ACCENT if pid == focus else TEXT), bg=bg)
            console.print(x + w - 2 - len(mark), row, mark, fg=DIM if done else TEXT, bg=bg)
        pid = rows[self.selected]
        proj = works.projects()[pid]
        info = wrapped(proj["what"], w - 4, TEXT)
        if pid == focus:
            info += wrapped("The Guild is working on this now: dues go to it.", w - 4, ACCENT)
        elif not works.finished(engine, pid) and focus:
            info += wrapped(f"The Guild is working on {works.projects()[focus]['name'].lower()} now; "
                            "you can still pay toward this.", w - 4, DIM)
        givers = st["givers"].get(pid, {})
        if givers:
            mine = givers.get(p.full_name, 0)
            info += wrapped(f"Given so far toward this: {sum(givers.values())} shards"
                            + (f", {mine} of them yours." if mine else "."), w - 4, DIM)
        top = y + 2 + len(rows)
        for i, (t, c) in enumerate(info[: h - len(rows) - 6]):
            console.print(x + 2, top + i, t, fg=c, bg=BG)
        amount = "all you have" if self.amount >= len(self.AMOUNTS) else f"{self.AMOUNTS[self.amount]}"
        console.print(x + 2, y + h - 3, f"Give: ← {amount} ♦ →    (you have {p.shards})"[: w - 4], fg=TEXT, bg=BG)
        if self.notice:
            console.print(x + 2, y + h - 4, self.notice[: w - 4], fg=ACCENT, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ project  ←→ amount  Enter give  Esc"[: w - 4], fg=DIM, bg=BG)


class TalentScreen:
    """Choose one of three talents (v0.58.0): 1-3 or ↑↓ and Enter. Esc puts the choice off (n brings
    it back); the three on offer stay the same until you choose."""

    def __init__(self) -> None:
        self.selected = 0

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import talents
        if not isinstance(event, tcod.event.KeyDown):
            return None
        offer = engine.player.talent_offers[0] if engine.player.talent_offers else []
        if not offer or event.sym == KeySym.ESCAPE:
            engine.screen = None
            engine.talent_later = True             # (put off: n brings it back)
            return None
        if event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(offer)
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(offer)
        elif event.sym in NUMBER_KEYS and NUMBER_KEYS[event.sym] < len(offer):
            self.selected = NUMBER_KEYS[event.sym]
            talents.choose(engine, offer[self.selected])
            engine.screen = None
            talents.show_offer(engine)
        elif event.sym in CONFIRM_KEYS:
            talents.choose(engine, offer[self.selected])
            engine.screen = None
            talents.show_offer(engine)            # another waiting? (several levels at once)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import talents
        p = engine.player
        offer = p.talent_offers[0] if p.talent_offers else []
        w = min(area_w - 2, 62)
        body = []
        for i, tid in enumerate(offer):
            t = talents.pool()[tid]
            chosen = i == self.selected
            body.append((f"{i + 1}. {t['name']}", ACCENT if chosen else TEXT, chosen))
            body += [(f"   {line}", TEXT if chosen else DIM, chosen) for line in textwrap.wrap(t["description"], w - 7)]
            body.append(("", TEXT, False))
        h = len(body) + 5
        x, y = (area_w - w) // 2, max(0, (console.height - h) // 2)
        n = len(p.talents) + 1
        draw_box(console, x, y, w, h, f"Talent {n}: choose one")
        for i, (t, colour, chosen) in enumerate(body):
            row = y + 1 + i
            console.rgb["bg"][x + 1 : x + w - 1, row] = HIGHLIGHT if chosen else BG
            console.print(x + 2, row, t[: w - 4], fg=colour, bg=HIGHLIGHT if chosen else BG)
        more = f"  ({len(p.talent_offers) - 1} more after this)" if len(p.talent_offers) > 1 else ""
        console.print(x + 2, y + h - 2, ("1-3 or ↑↓ Enter choose   Esc later (n)" + more)[: w - 4], fg=DIM, bg=BG)


class MapScreen:
    """The whole current map, as big as fits over the map view (m since v0.53.1; v0.53.0, user). Explored
    ground only on fog-of-war maps. Takes no time; Esc or m closes."""

    def handle(self, event, engine: "Engine") -> Action | None:
        from game.input_handlers import MAP_KEY
        if isinstance(event, tcod.event.KeyDown) and event.sym in (KeySym.ESCAPE, MAP_KEY, *CONFIRM_KEYS):
            engine.screen = None
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import minimap
        gm = engine.game_map
        w, h = area_w - 2, console.height - 2
        x, y = 1, 1
        title = gm.title + (f": {engine.hunt.contract.region.name}" if engine.hunt else "")
        draw_box(console, x, y, w, h, title[: w - 4])
        console.rgb["bg"][x + 1 : x + w - 1, y + 1 : y + h - 2] = (0, 0, 0)
        minimap.draw(console, engine, x + 1, y + 1, w - 2, h - 4, bg=(0, 0, 0))
        legend = [("■", minimap.PLAYER, " you  "), ("■", minimap.WAY, " ways and gates  "),
                  ("■", minimap.CREATURE, " creature  "), ("■", minimap.MARKED, " marked  "),
                  ("■", minimap.PERSON, " people  ")]
        cx = x + 2
        for mark, colour, label in legend:
            if cx + 1 + len(label) > x + w - 12:
                break
            console.print(cx, y + h - 2, mark, fg=colour, bg=BG)
            console.print(cx + 1, y + h - 2, label, fg=DIM, bg=BG)
            cx += 1 + len(label)
        close = "Esc or m close"
        console.print(x + w - 2 - len(close), y + h - 2, close, fg=DIM, bg=BG)


def contract_now(engine: "Engine", c) -> str:
    """What to do next for the Hunter's contract (v0.100.10, user: the log said the same before and after
    the find was in hand)."""
    from game import recovery
    what = f"{recovery.owner(c.recover['name'])} pack" if c.recover else f"the {engine.catalogue[c.artifact_id].name}"
    have = any(it.type.id == c.artifact_id for it in engine.player.all_items())
    on_it = engine.hunt is not None and engine.hunt.contract is c or (
        engine.hunt is not None and engine.hunt.contract.region.id == c.region.id and not engine.hunt.contract.free)
    if have and on_it:
        return f"you have {what}. Get back to the trail home (≡, in the first area) to come out of the miasma."
    if have:
        return (f"you have {what}. Take it to the guild clerk in Bytorsskug to complete the contract."
                if engine.hunt is None else f"you have {what}. Take it to the guild clerk in Bytorsskug.")
    if on_it:
        return f"find {what} in the deepest area (area {c.depth}), then get back to the trail home."
    area = f"area {c.recover['area']}" if c.recover else "the deepest area"
    return (f"set out from the Wayfinder in the plaza with these words, find {what} in {area}, and bring it "
            "back to the trail home.")


class QuestLogScreen:
    """The quest log (q): quests under way and finished, each with its story so far. ←→ or Tab
    switches; ↑↓ picks a quest."""

    def __init__(self) -> None:
        self.tab = "current"
        self.selected = 0

    def rows(self, engine) -> list:
        """Under way: the Hunter's contract, their bounties and scouting jobs (v0.52.0, user: taken
        work belongs in the log), then story quests. Finished: story quests."""
        from game import story
        out = []
        p = engine.player
        if self.tab == "current":
            if p.contract is not None and not p.contract.story:
                out.append(("contract", p.contract))
            out += [("job", j) for j in p.jobs]
        quests = []
        for qid, q in engine.story_data.quests.items():
            st = story.state(engine, qid)
            if not st:
                continue
            over = st.get("done") or st.get("failed")
            if (self.tab == "current") != bool(over):
                quests.append(qid)
        # (v0.66.0) chapters first, then paralogues, character logs, callings, Hunter logs, other quests
        def order(qid):
            q = engine.story_data.quests[qid]
            n = q.get("number", 0)
            return (story.KINDS.get(q.get("kind", "quest"), story.KINDS["quest"])[1], n if isinstance(n, int) else 0)
        return out + [("quest", qid) for qid in sorted(quests, key=order)]

    def row_title(self, engine, row) -> str:
        kind, what = row
        if kind == "contract":
            return "Contract: " + what.title(engine.catalogue)
        if kind == "job":
            return what.label(engine) + ("  (done)" if what.done else "")
        from game import story
        return story.heading(engine.story_data.quests[what])

    def details(self, engine, row, w: int) -> list:
        from game import story, postings, hunt
        kind, what = row
        out = []
        if kind == "contract":
            c = what
            out += wrapped(postings.describe(engine, c), w, TEXT)
            out += wrapped(f"Words: {c.region.name}   Danger {hunt.danger_pips(c.danger)}   {c.depth} areas", w, DIM)
            out += wrapped("Now: " + contract_now(engine, c), w, ACCENT)
            return out
        if kind == "job":
            j = what
            out += wrapped(j.text(engine), w, TEXT)
            out += wrapped(f"Pay: {j.reward} shards, from the Guild.", w, DIM)
            out += wrapped("Now: " + j.status(), w, ACCENT)
            return out
        st = story.state(engine, what)
        if not (st.get("done") or st.get("failed")):
            goal = st.get("goal")
            if goal is None:          # (saves from before v0.66.0)
                g = story.stage_def(engine, what, st["stage"]).get("goal")
                goal = g if isinstance(g, str) else ""
            if goal:
                out += wrapped("Now: " + story.fill(engine, goal), w, ACCENT)
        elif st.get("failed"):
            out += wrapped("Failed.", w, WARN)
        for entry in reversed(st["log"]):        # newest first: if it's long, the oldest give way
            out += wrapped(entry, w, DIM)
        return out

    def handle(self, event, engine: "Engine") -> Action | None:
        if not isinstance(event, tcod.event.KeyDown):
            return None
        from game.input_handlers import QUEST_KEY
        rows = self.rows(engine)
        if event.sym in (KeySym.ESCAPE, QUEST_KEY):
            engine.screen = None
        elif event.sym in TAB_KEYS:
            self.tab = "finished" if self.tab == "current" else "current"
            self.selected = 0
        elif event.sym in UP_KEYS and rows:
            self.selected = (self.selected - 1) % len(rows)
        elif event.sym in DOWN_KEYS and rows:
            self.selected = (self.selected + 1) % len(rows)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import story
        w = min(area_w - 2, 62)
        rows = self.rows(engine)
        self.selected = max(0, min(self.selected, len(rows) - 1))
        extra = []
        if rows:
            extra += self.details(engine, rows[self.selected], w - 4)
        else:
            extra += wrapped("Nothing under way." if self.tab == "current" else "Nothing finished yet.", w - 4, DIM)
        h, visible, extra = fit_window(console, max(len(rows), 1), extra)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, "Quests")
        tx = x + 2
        for tab, label in (("current", " Under way "), ("finished", " Finished ")):
            active = self.tab == tab
            console.print(tx, y + 1, label, fg=BG if active else DIM, bg=ACCENT if active else BG)
            tx += len(label) + 1
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for i, r in enumerate(rows[first : first + visible]):
            row, bg = y + 3 + i, HIGHLIGHT if first + i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            fg = ACCENT if r[0] == "quest" else TEXT
            console.print(x + 2, row, self.row_title(engine, r)[: w - 4], fg=fg, bg=bg)
        for i, (text, color) in enumerate(extra):
            console.print(x + 2, y + 4 + visible + i, text[: w - 4], fg=color, bg=BG)
        console.print(x + 2, y + h - 2, "↑↓ choose  ←→ tab  Esc or q close"[: w - 4], fg=DIM, bg=BG)


# ---- Trophies (v0.61.0) ------------------------------------------------------------------------
class TrophyScreen:
    """The trophies in your pack, for the trophymaster (hand one in: a record goes on the wall and
    pays) or the butcher (break one down into materials). ↑↓ and Enter; Esc leaves."""

    def __init__(self, mode: str = "trophymaster") -> None:
        self.mode = mode            # "trophymaster" or "butcher"
        self.selected = 0
        self.notice = ""

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import trophies
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = trophies.pack_trophies(engine)
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif rows and event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(rows)
        elif rows and event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(rows)
        elif rows and event.sym in CONFIRM_KEYS:
            i = rows[min(self.selected, len(rows) - 1)]
            if self.mode == "butcher":
                self.notice = trophies.butcher_at_shop(engine, i)
            else:
                _, self.notice = trophies.assess(engine, i, engine.rng)
            engine.log(self.notice)
            self.selected = min(self.selected, max(0, len(trophies.pack_trophies(engine)) - 1))
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import trophies
        rows = trophies.pack_trophies(engine)
        items = engine.player.inventory.items
        w = min(area_w - 2, 64)
        notice = wrapped(self.notice, w - 4, ACCENT) if self.notice else []
        title = "The trophymaster" if self.mode == "trophymaster" else "The butcher"
        if not rows:
            intro = [("You carry no trophies.", DIM)]
        elif self.mode == "trophymaster":
            intro = wrapped("Hand one in. A record goes up on the wall, and he pays for it.", w - 4, DIM)
        else:
            intro = wrapped("He'll break one down into materials for you. He pays nothing for it.", w - 4, DIM)
        h, visible, notice = fit_window(console, len(rows), notice, top=2 + len(intro) + 1)
        x, y = (area_w - w) // 2, (console.height - h) // 2
        draw_box(console, x, y, w, h, title)
        row = y + 2
        for text, color in intro:
            console.print(x + 2, row, text, fg=color, bg=BG)
            row += 1
        row += 1
        self.selected = min(self.selected, max(0, len(rows) - 1))
        first = max(0, min(self.selected - visible // 2, len(rows) - visible))
        for n, i in enumerate(rows[first:first + visible]):
            it = items[i]
            bg = HIGHLIGHT if first + n == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            console.print(x + 2, row, it.type.glyph, fg=it.type.color, bg=bg)
            rec = trophies.state(engine)["records"].get(it.type.properties["monster"])
            mark = f"record {trophies.weight_text(rec['kg'])}" if rec and self.mode == "trophymaster" else ""
            console.print(x + 4, row, it.label[: w - 8 - len(mark)], fg=TEXT, bg=bg)
            if mark:
                console.print(x + w - 2 - len(mark), row, mark, fg=DIM, bg=bg)
            row += 1
        row = y + 2 + len(intro) + 1 + max(visible, 1) + 1
        for text, color in notice:
            console.print(x + 2, row, text, fg=color, bg=BG)
            row += 1
        keys = ("↑↓ choose  Enter hand it in  Esc" if self.mode == "trophymaster" else "↑↓ choose  Enter break it down  Esc")
        console.print(x + 2, y + h - 2, keys[: w - 4], fg=DIM, bg=BG)


# ---- Sound (v0.63.0) ------------------------------------------------------------------------------
class SoundScreen:
    """Volumes (0-10) for everything, effects, ambience and music; mute; a test sound. From the
    title menu and the game menu. ↑↓ a row, ←→ change it, Enter on Mute or Test; Esc goes back.
    Settings are saved at once (saves/settings.json), apart from any save."""

    ROWS = [("master", "Everything"), ("effects", "Sound effects"), ("ambience", "Ambience"),
            ("music", "Music"), ("muted", "Mute (F2)"), ("test", "Play a test sound"), ("back", "Back")]

    def __init__(self, back=None) -> None:
        self.back = back
        self.selected = 0
        self.notice = ""

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import sound
        if not isinstance(event, tcod.event.KeyDown):
            return None
        key, _ = self.ROWS[self.selected]
        step = {KeySym.LEFT: -1, KeySym.KP_4: -1, _key("a"): -1, KeySym.RIGHT: 1, KeySym.KP_6: 1, _key("d"): 1}.get(event.sym)
        if event.sym == KeySym.ESCAPE or (event.sym in CONFIRM_KEYS and key == "back"):
            engine.screen = self.back
        elif event.sym in UP_KEYS:
            self.selected = (self.selected - 1) % len(self.ROWS)
        elif event.sym in DOWN_KEYS:
            self.selected = (self.selected + 1) % len(self.ROWS)
        elif step and key in ("master", "effects", "ambience", "music"):
            sound.settings[key] = max(0, min(10, sound.settings[key] + step))
            sound.refresh_volumes()
            sound.save_settings()
            if key in ("master", "effects"):
                sound.play("ui_move")
        elif (event.sym in CONFIRM_KEYS or step) and key == "muted":
            sound.settings["muted"] = not sound.settings.get("muted")
            sound.refresh_volumes()
            sound.save_settings()
        elif event.sym in CONFIRM_KEYS and key == "test":
            sound.play("shards")
            self.notice = ("Playing a test sound. If you heard nothing, check the volumes above and "
                           "your computer's sound." if sound.active() else sound.status())
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import sound
        w = min(area_w - 2, 52)
        status = wrapped(sound.status(), w - 4, DIM if sound.active() else (230, 110, 90))
        notice = wrapped(self.notice, w - 4, ACCENT) if self.notice else []
        h = len(self.ROWS) + 5 + len(status) + (len(notice) + 1 if notice else 0)
        x, y = (area_w - w) // 2, max(0, (console.height - h) // 2)
        draw_box(console, x, y, w, h, "Sound")
        for i, (key, label) in enumerate(self.ROWS):
            row = y + 2 + i
            bg = HIGHLIGHT if i == self.selected else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            console.print(x + 2, row, label, fg=TEXT, bg=bg)
            if key in ("master", "effects", "ambience", "music"):
                v = sound.settings[key]
                bar = "■" * v + "·" * (10 - v)
                console.print(x + w - 17, row, f"{bar} {v:>2}", fg=ACCENT if not sound.settings.get("muted") else DIM, bg=bg)
            elif key == "muted":
                console.print(x + w - 6, row, "on" if sound.settings.get("muted") else "off", fg=ACCENT, bg=bg)
        row = y + 2 + len(self.ROWS) + 1
        for text, color in status + ([("", TEXT)] if notice else []) + notice:
            console.print(x + 2, row, text, fg=color, bg=BG)
            row += 1
        console.print(x + 2, y + h - 2, "↑↓ choose  ←→ change  Enter  Esc back"[: w - 4], fg=DIM, bg=BG)


# ---- A Hunter's home: the property dealer (v0.74.0) -------------------------------------------------
class HomesScreen:
    """The property dealer: Homes (the three places: price, what each takes; Enter buys, asking
    first) and Improvements (for the home you own: bed, chest, trophy shelves; Enter buys the next
    step). ←→ or Tab switch. Takes no time."""

    TABS = ("homes", "improve")

    def __init__(self, engine) -> None:
        from game import homes
        self.tab = "improve" if homes.owned(engine) else "homes"
        self.selected = {"homes": 0, "improve": 0}
        self.notice = ""

    def rows(self, engine):
        from game import homes
        if self.tab == "homes":
            return list(homes.data()["homes"])
        return list(homes.data()["improvements"])

    def handle(self, event, engine: "Engine") -> Action | None:
        from game import homes
        if not isinstance(event, tcod.event.KeyDown):
            return None
        rows = self.rows(engine)
        sel = self.selected[self.tab]
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in TAB_KEYS:
            self.tab = "improve" if self.tab == "homes" else "homes"
            self.notice = ""
        elif event.sym in UP_KEYS:
            self.selected[self.tab] = (sel - 1) % len(rows)
            self.notice = ""
        elif event.sym in DOWN_KEYS:
            self.selected[self.tab] = (sel + 1) % len(rows)
            self.notice = ""
        elif event.sym in CONFIRM_KEYS:
            key = rows[sel]
            if self.tab == "homes":
                why = homes.can_buy(engine, key)
                if why:
                    self.notice = why
                    return None
                h = homes.data()["homes"][key]
                old = homes.owned(engine)
                extra = (f" You'd sell {homes.data()['homes'][old]['name']} back for {homes.refund(engine)}; "
                         "its improvements stay with it, and your things come with you.") if old else ""
                def yes(e, key=key, back=self):
                    ok, msg = homes.buy(e, key)
                    e.log(msg)
                    back.notice = msg
                    back.tab = "improve" if ok else back.tab
                    e.screen = back
                engine.screen = ConfirmScreen(f"Buy {h['name']} for {h['price']} shards?{extra}",
                                              on_yes=yes, on_no=lambda e, back=self: setattr(e, "screen", back))
            else:
                ok, msg = homes.improve(engine, key)
                self.notice = msg
                if ok:
                    engine.log(msg)
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import homes
        d = homes.data()
        mine = homes.owned(engine)
        rows = self.rows(engine)
        w = min(area_w - 2, 60)
        sel = min(self.selected[self.tab], len(rows) - 1)
        lines = []          # (text, colour, enabled)
        if self.tab == "homes":
            for hid in rows:
                h = d["homes"][hid]
                state = "yours" if hid == mine else f"♦ {h['price']}"
                lines.append((f"{h['name'][0].upper() + h['name'][1:]}", state, hid == mine or not homes.can_buy(engine, hid)))
            h = d["homes"][rows[sel]]
            takes = ", ".join(f"{d['improvements'][k]['name'].lower()} (up to {n})" if n > 1 else d['improvements'][k]['name'].lower()
                              for k, n in h["most"].items() if n)
            extra = wrapped(f"{h['description']} Takes: {takes}.", w - 4, DIM)
        else:
            if not mine:
                extra = wrapped("You don't have a home yet. Buy one first (←→ for the homes).", w - 4, DIM)
            for key in rows:
                imp = d["improvements"][key]
                t = homes.tier(engine, key)
                top = homes.most(mine, key) if mine else 0
                if not mine or top == 0:
                    state, ok = "-", False
                elif t >= top:
                    state, ok = "done", False
                else:
                    cost = imp["tiers"][t]["cost"]
                    state, ok = f"♦ {cost}", engine.player.shards >= cost
                size = ""
                if t and imp["tiers"][t - 1].get("slots"):
                    size = f" ({imp['tiers'][t - 1]['slots']})"
                lines.append((f"{imp['name']}{size}" + (f"  {t}/{top}" if mine and top > 1 else ""), state, ok))
            if mine:
                key = rows[sel]
                imp = d["improvements"][key]
                t = homes.tier(engine, key)
                nxt = imp["tiers"][t] if t < len(imp["tiers"]) else None
                more = f" Next: room for {nxt['slots']}." if nxt and nxt.get("slots") else ""
                extra = wrapped(imp["description"] + more, w - 4, DIM)
        if self.notice:
            extra = [(self.notice, ACCENT)] + extra
        h_, list_rows, extra = fit_window(console, len(lines), extra, top=3)
        x, y = (area_w - w) // 2, (console.height - h_) // 2
        draw_box(console, x, y, w, h_, "Homes" + (f": {d['homes'][mine]['short']} is yours" if mine else ""))
        tx = x + 2
        for tab, label in (("homes", " Homes "), ("improve", " Improvements ")):
            active = tab == self.tab
            console.print(tx, y + 1, label, fg=BG if active else DIM, bg=ACCENT if active else BG)
            tx += len(label) + 1
        for r, (text, state, ok) in enumerate(lines[:list_rows]):
            row = y + 3 + r
            bg = HIGHLIGHT if r == sel else BG
            console.rgb["bg"][x + 1 : x + w - 1, row] = bg
            console.print(x + 2, row, text[: w - 14], fg=TEXT if ok else DIM, bg=bg)
            console.print(x + w - 2 - len(state), row, state, fg=ACCENT if ok and state.startswith("♦") else DIM, bg=bg)
        for r, (text, color) in enumerate(extra):
            console.print(x + 2, y + 3 + list_rows + 1 + r, text, fg=color, bg=BG)
        console.print(x + 2, y + h_ - 2, "↑↓ choose  Enter buy  ←→ tab  Esc"[: w - 4], fg=DIM, bg=BG)


# ---- Fishing (v0.94.0, game/fishing.py) ------------------------------------------------------------
FISH_FRAME = (90, 150, 190)


def fish_focus(engine: "Engine", cells: list, box_h: int) -> tuple[int, int]:
    """Where the camera looks while fishing (v0.100.4, user: the cast window hid the Hunter): the middle
    of you and your line, set so both sit in the strip of map above a window of box_h rows."""
    xs, ys = [c[0] for c in cells], [c[1] for c in cells]
    view_h = getattr(getattr(engine, "cam", None), "height", 20)
    free = max(1, view_h - box_h - 1)
    return (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2 + view_h // 2 - free // 2


def fish_box_y(console, engine: "Engine", cells: list, h: int) -> int:
    """The window's top row: at the bottom unless that would cover you or your line; then at the top;
    failing both, wherever it covers least."""
    rows = [sp[1] for sp in (engine.cam.to_screen(*c) for c in cells) if sp]
    options = [console.height - h - 1, 1]
    return min(options, key=lambda y: (sum(y <= r < y + h for r in rows), options.index(y)))


class CastScreen(LookScreen):
    """Aim a cast: the cursor starts on your last spot, or the deepest water in reach; Tab cycles the
    water you can reach; b changes the bait. Enter or r casts (a turn); Esc puts the rod away."""
    box_h = 10

    def focus(self, engine: "Engine") -> tuple[int, int]:
        return fish_focus(engine, [(engine.player.x, engine.player.y), (self.x, self.y)], self.box_h)

    def __init__(self, engine: "Engine") -> None:
        super().__init__(engine)
        from game import fishing
        p = engine.player
        self.baits = [it.type.id for it in fishing.baits(p)]
        last = engine.fishing_last
        self.bait = 0
        if last and last[2] in self.baits:
            self.bait = self.baits.index(last[2])
        spots = fishing.spots(engine)
        if last and (last[0], last[1]) in spots:
            self.x, self.y = last[0], last[1]
        elif spots:
            self.x, self.y = spots[0]

    def handle(self, event, engine: "Engine") -> Action | None:
        from game.input_handlers import FISH_KEY, MOVE_KEYS
        from game.actions import CastAction
        from game import fishing
        if not isinstance(event, tcod.event.KeyDown):
            return None
        if event.sym == KeySym.ESCAPE:
            engine.screen = None
        elif event.sym in CONFIRM_KEYS or event.sym == FISH_KEY:
            if not self.baits:
                return None
            if fishing.why_not(engine, self.x, self.y):
                return None
            engine.screen = None
            return CastAction(self.x, self.y, self.baits[self.bait])
        elif event.sym == KeySym.TAB:
            spots = fishing.spots(engine)
            if spots:
                self.cycle = (self.cycle + 1) % len(spots)
                self.x, self.y = spots[self.cycle]
        elif event.sym == _key("b") and self.baits:
            self.bait = (self.bait + 1) % len(self.baits)
        elif event.sym in MOVE_KEYS:
            dx, dy = MOVE_KEYS[event.sym]
            nx, ny = self.x + dx, self.y + dy
            if engine.game_map.in_bounds(nx, ny) and engine.in_vision(nx, ny):
                self.x, self.y = nx, ny
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import fishing
        p = engine.player
        spot = engine.cam.to_screen(self.x, self.y)
        if spot:
            console.rgb["bg"][spot] = CURSOR_BG
            console.rgb["fg"][spot] = CURSOR_FG
        rod = fishing.rod(p)
        why = fishing.why_not(engine, self.x, self.y)
        lines = [(why, WARN)] if why else [(fishing.describe_spot(engine, self.x, self.y), TEXT)]
        lines.append((f"{rod.type.name.capitalize()}: casts {fishing.kit(p)['reach']}.", DIM))
        for text in fishing.kit_lines(p):
            lines.append((text, DIM))
        if self.baits:
            bt = engine.catalogue[self.baits[self.bait]]
            n = p.inventory.count_of(bt.id)
            kind = "lure" if bt.properties.get("lure") else "bait"
            more = f" (b: {len(self.baits)} kinds)" if len(self.baits) > 1 else ""
            lines.append((f"{kind.capitalize()}: {bt.label(n)}{more}.", DIM))
        w = min(area_w - 2, 72)
        body = []
        for text, color in lines:
            body += wrapped(text, w - 4, color)
        h = len(body) + 4
        self.box_h = h
        x = (area_w - w) // 2
        y = fish_box_y(console, engine, [(p.x, p.y), (self.x, self.y)], h)
        draw_box(console, x, y, w, h, "Cast where?", frame=FISH_FRAME)
        for i, (text, color) in enumerate(body):
            console.print(x + 2, y + 1 + i, text, fg=color, bg=BG)
        console.print(x + 2, y + h - 2, ("Enter/r cast  Tab water  b bait  Esc" if w >= 42 else "Enter cast  Tab water  b bait  Esc")[: w - 4], fg=DIM, bg=BG)


def _bar(console, x: int, y: int, width: int, share: float, color, empty=(60, 54, 48)) -> None:
    share = max(0.0, min(1.0, share))
    fill = round(share * width)
    console.print(x, y, "█" * fill, fg=color, bg=BG)
    console.print(x + fill, y, "░" * (width - fill), fg=empty, bg=BG)


class FishScreen:
    """A line in the water (v0.94.0). Waiting: . wait, Enter or space strike, Esc reel in. On the line:
    r reel, h hold, g give line, a/← and d/→ steer, c cut it loose. Landed: Enter keep, x let it go.
    Every choice but reeling in or keeping is a turn."""

    WAIT_KEYS = {_key("PERIOD"), KeySym.KP_5}
    box_h = 12

    def focus(self, engine: "Engine") -> tuple[int, int]:
        p, s = engine.player, engine.fishing
        cells = [(p.x, p.y)] + ([(s.x, s.y)] if s is not None else [])
        return fish_focus(engine, cells, self.box_h)

    def handle(self, event, engine: "Engine") -> Action | None:
        from game.actions import FishAction
        if not isinstance(event, tcod.event.KeyDown):
            return None
        s = engine.fishing
        if s is None:
            engine.screen = None
            return None
        k = event.sym
        if s.phase == "landed":
            if k in CONFIRM_KEYS or k == _key("k"):
                return FishAction("keep")
            if k == _key("x"):
                return FishAction("release")
            if k == _key("g"):
                return FishAction("gut")
            return None
        if s.phase == "fight":
            cmd = {_key("r"): "reel", _key("h"): "hold", _key("g"): "give", KeySym.LEFT: "left", _key("a"): "left",
                   KeySym.KP_4: "left", KeySym.RIGHT: "right", _key("d"): "right", KeySym.KP_6: "right",
                   _key("c"): "cut"}.get(k)
            return FishAction(cmd) if cmd else None
        if k == KeySym.ESCAPE:
            return FishAction("stop")
        if k in CONFIRM_KEYS or k == KeySym.SPACE:
            return FishAction("strike")
        if k in self.WAIT_KEYS:
            return FishAction("wait")
        return None

    def render(self, console, engine: "Engine", area_w: int) -> None:
        from game import fishing
        s = engine.fishing
        if s is None:
            return
        p = engine.player
        w = min(area_w - 2, 56)
        body: list = []
        if s.phase == "landed":
            item = s.caught
            title = "Landed!"
            body.append((item.label.capitalize(), ACCENT))
            body += wrapped(fishing.species()[s.fish]["description"], w - 4, TEXT)
            body += wrapped(item_worth(item, engine), w - 4, DIM)
            keys = "Enter keep  x let it go  g gut it"
        elif s.phase == "fight":
            title = "On the line!"
            bw = w - 16
            rows = [("Tension", s.tension / fishing.power(s),
                     (230, 90, 70) if s.tension > 0.8 * fishing.power(s) else (230, 190, 90)
                     if s.tension > 0.55 * fishing.power(s) else (110, 190, 120) if s.tension >= fishing.SLACK
                     else (120, 140, 170)),
                    ("Line out", s.line / fishing.max_line(s), (150, 180, 210)),
                    ("Fish", s.stamina / s.max_stamina if s.max_stamina else 0, (200, 170, 120))]
            body += [("", None)] * len(rows)
            body.append(("", None))
            if fishing.shows_coming(engine, s):
                m = fishing.data()["moves"][s.coming]
                body += wrapped("Next: " + m["coming"] + " " + m.get("answer", ""), w - 4, ACCENT)
            else:                                   # (v0.100.4, user: which move when wasn't clear)
                body.append(("Next: you can't read this one yet.", DIM))
                body += wrapped(fishing.data().get("fight_guide", ""), w - 4, DIM)
            keys = "r reel  h hold  g give  a/d steer  c cut"
        else:
            title = f"Fishing: {fishing.data()['waters'][s.kind]['short']}, {s.band}"
            bt = engine.catalogue[s.bait]
            body.append((f"{s.rod.type.name.capitalize()}, {bt.label(max(1, p.inventory.count_of(bt.id)))}.", DIM))
            if s.phase == "bite":
                body.append(("A bite! Strike now (Enter), or it's gone.", ACCENT))
            keys = ". wait  Enter strike  Esc reel in"
        log = [line for text in s.log[-4:] for line in wrapped(text, w - 4, TEXT)]
        body += [("", None)] + log[-4:]
        h = len(body) + 4
        self.box_h = h
        x = (area_w - w) // 2
        y = fish_box_y(console, engine, [(p.x, p.y), (s.x, s.y)], h)
        draw_box(console, x, y, w, h, title, frame=FISH_FRAME)
        for i, (text, color) in enumerate(body):
            if color is not None:
                console.print(x + 2, y + 1 + i, text[: w - 4], fg=color, bg=BG)
        if s.phase == "fight":
            for i, (name, share, color) in enumerate(rows):
                console.print(x + 2, y + 1 + i, name, fg=DIM, bg=BG)
                _bar(console, x + 12, y + 1 + i, bw, share, color)
        console.print(x + 2, y + h - 2, keys[: w - 4], fg=DIM, bg=BG)
