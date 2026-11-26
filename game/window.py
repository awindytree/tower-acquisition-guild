"""Fullscreen (v0.100.11, user: F11 or Alt+Enter).

F11, or Alt with Enter, switches between a window and the whole screen ("desktop" fullscreen: the
screen's own resolution, so nothing flickers or changes mode). The console is rebuilt to fit every
frame, so the game simply fills the screen at the largest whole-number zoom that fits.

The choice is remembered in saves/window.json, so the next start opens the same way.
"""
from __future__ import annotations

import json
from pathlib import Path

_path: Path | None = None


def is_toggle(event) -> bool:
    """F11, or Alt+Enter (either Enter key, either Alt)."""
    import tcod.event
    if not isinstance(event, tcod.event.KeyDown):
        return False
    ks = tcod.event.KeySym
    if event.sym == ks.F11:
        return True
    enters = {ks.RETURN, getattr(ks, "KP_ENTER", ks.RETURN)}
    return event.sym in enters and bool(event.mod & tcod.event.Modifier.ALT)


def _desktop_flag():
    try:
        import tcod.sdl.video
        return tcod.sdl.video.WindowFlags.FULLSCREEN_DESKTOP
    except (ImportError, AttributeError):
        import tcod.context
        return tcod.context.SDL_WINDOW_FULLSCREEN_DESKTOP


def is_fullscreen(context) -> bool:
    window = getattr(context, "sdl_window", None)
    return bool(window is not None and window.fullscreen)


def set_fullscreen(context, on: bool) -> bool:
    """Switch the window to fullscreen or back. False if there's no window to switch."""
    window = getattr(context, "sdl_window", None)
    if window is None:
        return False
    window.fullscreen = _desktop_flag() if on else 0
    save(on)
    return True


def toggle(context) -> bool:
    return set_fullscreen(context, not is_fullscreen(context))


def load(path: Path) -> bool:
    """Remember where the choice is kept; True if the last run ended fullscreen."""
    global _path
    _path = path
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("fullscreen"))
    except (OSError, ValueError, AttributeError):
        return False


def save(on: bool) -> None:
    if _path is None:
        return
    try:
        _path.parent.mkdir(parents=True, exist_ok=True)
        _path.write_text(json.dumps({"fullscreen": bool(on)}), encoding="utf-8")
    except OSError:
        pass
