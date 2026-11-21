"""Tower Acquisition Guild — entry point.

Run with:  python main.py
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).parent


def report_crash(exc_type, exc, tb) -> None:
    """When launched from Play.bat there's no terminal to show errors, so save
    the details to crash.log and pop up a message pointing to it."""
    try:
        from game.version import VERSION
    except Exception:
        VERSION = "unknown"
    details = f"Tower Acquisition Guild v{VERSION}\n\n" + "".join(traceback.format_exception(exc_type, exc, tb))
    log_path = ROOT / "crash.log"
    log_path.write_text(details, encoding="utf-8")
    if sys.stderr:  # None when there's no terminal
        print(details, file=sys.stderr)
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, f"The game crashed. Details were saved to:\n{log_path}",
            "Tower Acquisition Guild", 0x10,
        )


# Set up before anything else loads, so even a missing library gets reported.
sys.excepthook = report_crash

import tcod.console
import tcod.context
import tcod.event
import tcod.tileset

from game.engine import Engine
from game.game_map import GameMap
from game.input_handlers import action_for_event
from game.hunt import load_regions
from game.items import Catalogue
from game.monsters import load_monster_types
from game.player import Player
from game.saves import SaveSystem
from game.shops import load_shops
from game.artifacts import load_workshops
from game.skills import load_skills
from game import font
from game.version import VERSION
from game.screens import TitleScreen

FONT = ROOT / "data" / "font_8x16.png"
START_MAP = ROOT / "data" / "maps" / "city.txt"
ITEMS = ROOT / "data" / "items.json"
REGIONS = ROOT / "data" / "regions.json"
MONSTERS = ROOT / "data" / "monsters.json"
SAVES = ROOT / "saves"
SHOPS = ROOT / "data" / "shops.json"
WORKSHOPS = ROOT / "data" / "workshops.json"
SKILLS = ROOT / "data" / "skills.json"
NEW_PLAYER = ROOT / "data" / "player.json"

# The screen grows to fill the window. These are the fewest cells it may
# have; the zoom level is the largest whole number that still fits them.
MIN_COLUMNS = 64   # 40 for the map + 24 for the info panel
MIN_ROWS = 20


def make_console(context: tcod.context.Context) -> tcod.console.Console:
    """A console that exactly fills the window, with every cell zoomed by the
    same whole number in both directions, so the pixel font stays crisp and
    keeps its 8x16 shape."""
    cols, rows = context.recommended_console_size()  # cells that fit at 1x
    zoom = max(1, min(cols // MIN_COLUMNS, rows // MIN_ROWS))
    return context.new_console(MIN_COLUMNS, MIN_ROWS, magnification=zoom, order="F")


def main() -> None:
    # One sheet: CP437, then the letters it lacks (þ, Þ: game/font.py), in one charmap.
    tileset = tcod.tileset.load_tilesheet(FONT, 16, font.rows(), font.charmap(tcod.tileset.CHARMAP_CP437))

    game_map, (start_x, start_y) = GameMap.from_file(START_MAP)
    catalogue = Catalogue.load(ITEMS)
    player = Player.new(NEW_PLAYER, catalogue, start_x, start_y)
    engine = Engine(game_map, player, catalogue, load_regions(REGIONS), load_monster_types(MONSTERS),
                    new_hunter=lambda: Player.new(NEW_PLAYER, catalogue, start_x, start_y),
                    saves=SaveSystem(SAVES), shops=load_shops(SHOPS, catalogue),
                    workshops=load_workshops(WORKSHOPS), skills=load_skills(SKILLS))
    engine.screen = TitleScreen()  # New Game, Continue, Load or Quit

    with tcod.context.new(
        columns=60,
        rows=24,
        tileset=tileset,
        title=f"Tower Acquisition Guild v{VERSION}",
        vsync=True,
        sdl_window_flags=tcod.context.SDL_WINDOW_RESIZABLE | tcod.context.SDL_WINDOW_MAXIMIZED,
    ) as context:
        last = time.monotonic()
        while True:
            # Rebuilt every time, so resizing the window just works.
            console = make_console(context)
            engine.render(console)
            context.present(console, integer_scaling=True)

            # wait() sleeps until there's input, so the game uses no CPU while idle;
            # a moving screen (the opening crawl) wakes it ~30 times a second instead.
            screen = engine.screen
            if getattr(screen, "animating", False):
                events = list(tcod.event.wait(timeout=1 / 30))
                now = time.monotonic()
                screen.tick(engine, min(0.25, now - last))
                last = now
            else:
                events = tcod.event.wait()
                last = time.monotonic()
            for event in events:
                engine.handle_action(action_for_event(event, engine))


if __name__ == "__main__":
    main()
