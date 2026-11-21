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
LOOK_KEY = _key("x")
CHARACTER_KEY = _key("c")
FIRE_KEY = _key("f")
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


def action_for_event(event: tcod.event.Event, engine: "Engine") -> Action | None:
    if isinstance(event, tcod.event.Quit):
        return QuitAction()

    # An open screen (like the inventory) gets the keys instead of the map.
    if engine.screen is not None:
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
        if event.sym == EXPLORE_KEY:
            from game.actions import ExploreAction
            return ExploreAction()
        if event.sym == FIRE_KEY:
            from game import ranged
            from game.screens import TargetScreen
            why = ranged.can_fire(engine)
            if why:
                engine.log(why)
            else:
                engine.screen = TargetScreen(engine)
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
