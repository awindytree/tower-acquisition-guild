"""Turn keypresses into Actions."""
from __future__ import annotations

from typing import TYPE_CHECKING

import tcod.event

if TYPE_CHECKING:
    from game.engine import Engine

from game.actions import Action, MoveAction, PickUpAction, QuitAction, WaitAction

KeySym = tcod.event.KeySym


def _key(name: str):
    """Look up a KeySym by name. Newer tcod versions spell letter keys in
    upper case (KeySym.W), older ones in lower case (KeySym.w)."""
    for candidate in (name.upper(), name.lower(), name):
        if hasattr(KeySym, candidate):
            return getattr(KeySym, candidate)
    raise KeyError(name)


_DIRECTIONS = {
    # Arrow keys
    "UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0),
    # WASD
    "w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0),
    # Numpad
    "KP_8": (0, -1), "KP_2": (0, 1), "KP_4": (-1, 0), "KP_6": (1, 0),
    # (vi-keys h j k l were dropped in v0.53.1, user: l opens the message log)
}
# Movement is four-way (user, v0.41.0): no diagonal steps, for anyone.

MOVE_KEYS = {_key(name): d for name, d in _DIRECTIONS.items()}
WAIT_KEYS = {_key("PERIOD"), _key("KP_5")}
PICKUP_KEYS = {_key("g"), _key("COMMA")}
INVENTORY_KEY = _key("i")
EQUIPMENT_KEY = _key("e")   # the equipment window (user, v0.69.0)
LOOK_KEY = _key("x")
CHARACTER_KEY = _key("c")
FIRE_KEY = _key("f")
THROW_KEY = _key("h")       # throw (hurl) something: a pot, a jar, a lure, a weapon that can be thrown (v0.82.0)
EXPLORE_KEY = _key("o")
TECHNIQUE_KEY = _key("z")   # ready the weapon's rank-5 technique (v0.55.0; no turn)
BUTCHER_KEY = _key("b")     # butcher the corpse here (v0.61.0)
TALENT_KEY = _key("n")      # choose a talent you've earned (v0.58.0)
SKILLS_KEY = _key("k")      # the skills window (user, v0.59.1)
HISTORY_KEY = _key("l")   # the message log (user, v0.53.1; was m)
TRAVEL_KEY = _key("t")
QUEST_KEY = _key("q")
MINIMAP_KEY = _key("v")   # the minimap in the side panel, on or off (user, v0.53.1; was n)
MAP_KEY = _key("m")       # the whole map, big, over the map view (user, v0.53.1; was v)
HELP_KEYS = {_key("SLASH"), _key("F1")}   # ? (shift + /) or F1
MUTE_KEY = _key("F2")     # sound on or off (v0.63.0)


def _window_sound(event, engine) -> None:
    """The soft clicks of moving through, choosing in and leaving a window (v0.63.0)."""
    from game import sound
    sym = event.sym
    if sym == KeySym.ESCAPE:
        sound.on_key(engine.screen, "cancel")
    elif sym in (KeySym.RETURN, KeySym.KP_ENTER) or _is_number(sym):
        sound.on_key(engine.screen, "confirm")
    elif sym in MOVE_KEYS or sym == KeySym.TAB:
        sound.on_key(engine.screen, "move")


def _is_number(sym) -> bool:
    return any(sym == getattr(KeySym, f"N{i}", None) for i in range(1, 10))


def action_for_event(event: tcod.event.Event, engine: "Engine") -> Action | None:
    if isinstance(event, tcod.event.Quit):
        return QuitAction()

    if isinstance(event, tcod.event.KeyDown) and event.sym == MUTE_KEY:
        from game import sound
        sound.settings["muted"] = not sound.settings.get("muted")
        sound.refresh_volumes()
        sound.save_settings()
        engine.log("Sound off. (F2 turns it back on.)" if sound.settings["muted"] else "Sound on.")
        return None

    # An open screen (like the inventory) gets the keys instead of the map.
    if engine.screen is not None:
        if isinstance(event, tcod.event.KeyDown):
            _window_sound(event, engine)
        return engine.screen.handle(event, engine)

    if isinstance(event, tcod.event.KeyDown):
        if event.sym == KeySym.ESCAPE:
            from game.screens import GameMenuScreen
            engine.screen = GameMenuScreen()
            return None
        if event.sym in MOVE_KEYS:
            dx, dy = MOVE_KEYS[event.sym]
            return MoveAction(dx, dy)
        if event.sym in WAIT_KEYS:
            return WaitAction()
        if event.sym in PICKUP_KEYS:
            return PickUpAction()
        if event.sym == BUTCHER_KEY:
            from game.actions import ButcherAction
            return ButcherAction()
        if event.sym == INVENTORY_KEY:
            from game.screens import InventoryScreen
            engine.screen = InventoryScreen()
        if event.sym == EQUIPMENT_KEY:
            from game.screens import EquipmentScreen
            engine.screen = EquipmentScreen()
            return None
        if event.sym == EXPLORE_KEY:
            from game.actions import ExploreAction
            return ExploreAction()
        if event.sym == FIRE_KEY:
            from game import ranged
            from game.screens import TargetScreen
            why = ranged.can_fire(engine)
            if not why and engine.player.unloaded and ranged.bow(engine.player).type.properties.get("reload"):
                from game.actions import ReloadAction
                return ReloadAction()                   # a crossbow: wind it first (v0.78.0)
            if why:
                engine.log(why)
            else:
                engine.screen = TargetScreen(engine)
            return None
        if event.sym == THROW_KEY:
            from game import throwing
            from game.screens import ThrowScreen, ChoiceScreen
            things = throwing.throwables(engine.player)
            if not things:
                engine.log("You have nothing to throw.")
            elif len(things) == 1:
                engine.screen = ThrowScreen(engine, things[0][1], things[0][2])
            else:
                engine.screen = ChoiceScreen("Throw what?", [
                    (label, lambda e, it=it, r=r: setattr(e, "screen", ThrowScreen(e, it, r))) for label, it, r in things])
            return None
        if event.sym == TRAVEL_KEY:
            from game.screens import TravelScreen
            from game.travel import destinations
            places = destinations(engine)
            if places:
                engine.screen = TravelScreen(places)
            else:
                engine.log("You don't know anywhere to travel to from here yet.")
            return None
        if event.sym == QUEST_KEY:
            from game.screens import QuestLogScreen
            engine.screen = QuestLogScreen()
            return None
        if event.sym == SKILLS_KEY:
            from game.screens import SkillsScreen
            engine.screen = SkillsScreen()
            return None
        if event.sym == TALENT_KEY:
            if engine.player.talent_offers:
                from game.screens import TalentScreen
                engine.screen = TalentScreen()
            else:
                engine.log("You have no talent to choose just now.")
            return None
        if event.sym == TECHNIQUE_KEY:
            from game import weaponskills
            weaponskills.ready(engine)
            return None
        if event.sym == MINIMAP_KEY:
            engine.show_minimap = not getattr(engine, "show_minimap", False)
            return None
        if event.sym == MAP_KEY:
            from game.screens import MapScreen
            engine.screen = MapScreen()
            return None
        if event.sym == HISTORY_KEY:
            from game.screens import HistoryScreen
            engine.screen = HistoryScreen()
            return None
        if event.sym in HELP_KEYS:
            from game.screens import HelpScreen
            engine.screen = HelpScreen()
            return None
        if event.sym == CHARACTER_KEY:
            from game.screens import CharacterScreen
            engine.screen = CharacterScreen()
        if event.sym == LOOK_KEY:
            from game.screens import LookScreen
            engine.screen = LookScreen(engine)

    return None
