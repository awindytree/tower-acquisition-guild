"""Monuments (v0.68.0): statues and the like in persistent places, each with its story.

data/monuments.json: {id: {"name": shown as the heading, "look": the look command's line,
"title": the reading window's title, "text": [paragraphs]}}. A map places one with
";monument=x,y id". Walking into it opens its text; the look command describes it; travel-to
lists it. The texts are lore for the user to write.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "monuments.json"
_cache: dict | None = None


def table() -> dict:
    global _cache
    if _cache is None:
        raw = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}
        _cache = {k: v for k, v in raw.items() if not k.startswith("_")}
    return _cache


def at(game_map, x: int, y: int) -> dict | None:
    mid = getattr(game_map, "monuments", {}).get((x, y))
    return table().get(mid) if mid else None


def read(engine, x: int, y: int) -> bool:
    """Walking into a monument: open its text. True if there was one."""
    m = at(engine.game_map, x, y)
    if not m:
        return False
    from game.screens import ScrollScreen
    engine.screen = ScrollScreen.of_lines(m.get("title", m["name"]), m.get("text", []))
    return True
