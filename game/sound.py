"""Sound effects and ambience (v0.63.0).

The user's direction: the assistant makes the sounds (moody and ambient; tools/sound/make_sounds.py
builds them from code into data/sounds/); the user makes the music (none yet). Soundscapes play
everywhere; music only at key moments and places, like Bytorsskug.

How it works:
- Playback uses python-tcod's own audio (SDL), so nothing new to install. `init()` opens the
  default sound device and a BasicMixer, which mixes on its own thread. Every failure is caught:
  if sound can't start, the game runs silent, and `status()` says why (the sound window shows it).
- `play(event)`: a one-off sound. data/sounds.json maps game events to files (several files =
  one picked at random) and a volume each, so a sound is swapped by editing that file.
- `update(engine)` (each frame, from main.py): picks the ambience loop for where the Hunter is
  (the city's streets, inside a building, the guild hall, the Brisering, each kind of land out in
  the miasma, day or night) and crossfades to it; sets the Wayfinder's hum by how near it is;
  and plays music for the place if data/sounds.json names some (WAV files in data/music/).
- Settings (volumes 0-10 for everything, effects, ambience and music; mute) are the player's,
  kept in saves/settings.json, not in any save.

Nothing here runs in tests or the balance bot: until `init()` succeeds every call does nothing
except note the event in `played` (so tests can check that the right sounds would play).
"""
from __future__ import annotations

import json
import random
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOUNDS = DATA / "sounds"
MUSIC = DATA / "music"

DEFAULTS = {"master": 8, "effects": 8, "ambience": 6, "music": 7, "muted": False}
FADE = 1.5            # seconds: ambience and music crossfade
EMITTER_RANGE = 14.0  # cells: how far off the Wayfinder's hum can be heard (rows count double)

settings: dict = dict(DEFAULTS)
played: list[str] = []          # recent events (tests read it)
_mixer = None
_device = None
_cache: dict = {}
_status = "Sound hasn't started."
_settings_path: Path | None = None
_loops: dict = {}               # "ambience" / "emitter" / "music" -> [name, channel, base volume]
_rng = random.Random()
_last: dict = {}                # event -> time it last played (some are rate-limited)


# ---- Data -----------------------------------------------------------------------------------
_table: dict | None = None


def table() -> dict:
    global _table
    if _table is None:
        _table = json.loads((DATA / "sounds.json").read_text(encoding="utf-8"))
    return _table


def event_files(event: str) -> list[str]:
    e = table()["events"].get(event)
    if e is None:
        return []
    files = e["files"] if isinstance(e, dict) else e
    return [files] if isinstance(files, str) else list(files)


def event_volume(event: str) -> float:
    e = table()["events"].get(event)
    return e.get("volume", 1.0) if isinstance(e, dict) else 1.0


# ---- Starting up ----------------------------------------------------------------------------
def load_settings(path: Path) -> None:
    global _settings_path
    _settings_path = path
    try:
        settings.update({k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass


def save_settings() -> None:
    if _settings_path is None:
        return
    try:
        _settings_path.parent.mkdir(parents=True, exist_ok=True)
        _settings_path.write_text(json.dumps(settings), encoding="utf-8")
    except OSError:
        pass


def init(settings_path: Path | None = None) -> bool:
    """Open the sound device. Returns False (and the game stays silent) if it can't."""
    global _mixer, _device, _status
    if settings_path is not None:
        load_settings(settings_path)
    try:
        import warnings
        import tcod.sdl.audio as audio
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")              # (BasicMixer is deprecated in tcod 19; it still works)
            if hasattr(audio, "get_default_playback"):   # tcod 19+ (SDL3)
                _device = audio.get_default_playback().open()
            else:                                        # tcod 13.5-18 (SDL2)
                _device = audio.open()
            try:
                _mixer = audio.BasicMixer(_device)
            except TypeError:
                _mixer = audio.BasicMixer(device=_device)
        _status = "Sound is on."
        return True
    except Exception as exc:          # no sound device, an old tcod, anything: play on in silence
        _mixer = _device = None
        _status = f"Sound couldn't start ({type(exc).__name__}: {exc}). The game is silent."
        return False


def status() -> str:
    return _status


def active() -> bool:
    return _mixer is not None


def _fail(exc: Exception) -> None:
    """Something went wrong mid-game: stop trying, stay silent, keep the reason."""
    global _mixer, _status
    _mixer = None
    _status = f"Sound stopped ({type(exc).__name__}: {exc}). The game is silent."


def _load(name: str, folder: Path = SOUNDS):
    """A WAV file as the sound device wants it (cached)."""
    if name in _cache:
        return _cache[name]
    import numpy as np
    with wave.open(str(folder / f"{name}.wav"), "rb") as w:
        rate, chans, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    dtype = {1: np.uint8, 2: "<i2", 4: "<i4"}[width]
    x = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    x = (x - 128) / 128 if width == 1 else x / float(2 ** (8 * width - 1))
    x = x.reshape(-1, chans)
    snd = _device.convert(x, rate)
    _cache[name] = snd
    return snd


# ---- Playing ---------------------------------------------------------------------------------
def _vol(kind: str) -> float:
    if settings.get("muted"):
        return 0.0
    return settings["master"] / 10 * settings[kind] / 10


def play(event: str, volume: float = 1.0, gap: float = 0.0) -> None:
    """A one-off sound for a game event. gap: don't repeat it within this many seconds."""
    played.append(event)
    del played[:-50]
    if _mixer is None:
        return
    import time
    now = time.monotonic()
    if gap and now - _last.get(event, -1e9) < gap:
        return
    _last[event] = now
    files = event_files(event)
    v = _vol("effects") * event_volume(event) * volume
    if not files or v <= 0:
        return
    try:
        _mixer.play(_load(_rng.choice(files)), volume=v)
    except Exception as exc:
        _fail(exc)


_walk_steps = 0


def step(symbol: str, walking: bool = False) -> None:
    """A footstep on this kind of ground (data/sounds.json "steps": map symbol -> sound).
    While auto-exploring or travelling (quick steps), every other one, a little softer."""
    global _walk_steps
    kind = table()["steps"].get(symbol)
    if not kind:
        return
    if walking:
        _walk_steps += 1
        if _walk_steps % 2:
            return
        play(f"step_{kind}", 0.7)
    else:
        play(f"step_{kind}")


def _set_loop(slot: str, name: str | None, kind: str, base: float = 1.0, folder: Path = SOUNDS) -> None:
    """Start, change or stop a looping sound in a slot, crossfading."""
    cur = _loops.get(slot)
    if cur and cur[0] == name:
        cur[2] = base
        _apply_volume(slot, kind)
        return
    if cur:
        _retire(cur[1])
        _loops.pop(slot, None)
    if name is None or _mixer is None:
        return
    try:
        ch = _mixer.play(_load(name, folder), volume=_vol(kind) * base, loops=-1)
        _loops[slot] = [name, ch, base]
    except FileNotFoundError:
        pass
    except Exception as exc:
        _fail(exc)


def _channel_lock(ch):
    """The channel's own lock (tcod: an RLock that its mixing and fadeout() take), held while changing
    the channel from the game's thread; nothing if this tcod has none."""
    import contextlib
    lock = getattr(ch, "_lock", None)
    return lock if lock is not None and hasattr(lock, "__enter__") else contextlib.nullcontext()


def _retire(ch) -> None:
    """Fade a looping channel out, for good. (v0.64.1, user: the title screen's wind went on playing
    under every hunt.) tcod loops a sound by re-queuing it from the channel's end-of-sound callback,
    and fadeout() doesn't clear that callback, so a faded loop started itself again: clear it first.
    (v0.65.1, user's crash: 0.64.1 also emptied the channel's queue later, from this thread, while the
    audio thread was mixing it: "pop from empty list". Nothing here touches the queue now; the
    callback is cleared under the channel's own lock, so the audio thread never sees it half-done.)"""
    try:
        with _channel_lock(ch):
            ch.on_end_callback = None
            ch.fadeout(FADE)
    except Exception:
        pass



def _apply_volume(slot: str, kind: str) -> None:
    cur = _loops.get(slot)
    if cur and hasattr(cur[1], "volume"):
        try:
            cur[1].volume = _vol(kind) * cur[2]
        except Exception:
            pass


def refresh_volumes() -> None:
    """After the settings change: the loops follow at once."""
    for slot, kind in (("ambience", "ambience"), ("emitter", "ambience"), ("music", "music")):
        _apply_volume(slot, kind)


def stop_all() -> None:
    for slot in list(_loops):
        _set_loop(slot, None, "ambience")


# ---- Where am I? ---------------------------------------------------------------------------------
INDOOR = set(".wkm")      # floors inside buildings in the city (streets are : - , = I)


def place_key(engine) -> str:
    """The soundscape for where the Hunter is: a key into data/sounds.json "ambience"."""
    scr = type(getattr(engine, "screen", None)).__name__
    if scr in ("TitleScreen", "CrawlScreen") or getattr(engine, "player", None) is None:
        return "title"
    gm = engine.game_map
    if engine.hunt is not None:
        style = getattr(gm, "style", "") or engine.hunt.contract.region.style   # (this area's terrain, v0.70.0)
        night = gm.light == "torch"
        return f"{style}_night" if night and f"{style}_night" in table()["ambience"] else style
    if getattr(engine, "in_brisering", None) and engine.in_brisering():
        return "brisering"
    from game import lost_grounds
    gid = lost_grounds.here(engine)
    if gid:                          # a Lost Ground: its own "ambience" key, else its land word's terrain (v0.87.0)
        g = lost_grounds.grounds()[gid]
        key = g.get("ambience")
        if not key and engine.regions is not None and g["place"] in engine.regions:
            key = engine.regions[g["place"]].style
        key = key or "caves"
        night = f"{key}_night"
        return night if gm.light == "torch" and night in table()["ambience"] else key
    p = engine.player
    hall = getattr(gm, "hall", None)
    if hall and hall[0] <= p.x < hall[0] + 20 and hall[1] <= p.y < hall[1] + 11:
        return "hall"
    if gm.tile_at(p.x, p.y).symbol in INDOOR:
        return "interior"
    return "city"


def emitter_volume(engine) -> float:
    """How loud the Wayfinder's hum is here: 1 beside it, fading to 0 at EMITTER_RANGE."""
    gm = engine.game_map
    if engine.hunt is not None or gm is not getattr(engine, "city", None):
        return 0.0
    spots = getattr(gm, "_wayfinder_cells", None)
    if spots is None:
        spots = [(x, y) for x in range(gm.width) for y in range(gm.height) if gm.tile_at(x, y).symbol == "Y"]
        gm._wayfinder_cells = spots
    if not spots:
        return 0.0
    p = engine.player
    d = min(((x - p.x) ** 2 + (2 * (y - p.y)) ** 2) ** 0.5 for x, y in spots)
    return max(0.0, 1 - d / EMITTER_RANGE) ** 1.5


def update(engine) -> None:
    """Each frame: the right ambience, the Wayfinder's hum, the place's music."""
    if _mixer is None:
        return
    key = place_key(engine)
    amb = table()["ambience"].get(key)
    _set_loop("ambience", amb, "ambience")
    hum = emitter_volume(engine) if key not in ("title",) else 0.0
    _set_loop("emitter", "loop_wayfinder" if hum > 0.01 else None, "ambience", hum)
    tune = table().get("music", {}).get(key)
    _set_loop("music", tune, "music", 1.0, MUSIC)


# ---- Windows and moments -------------------------------------------------------------------------
QUIET_SCREENS = {"TitleScreen", "CrawlScreen", "LookScreen", "TargetScreen", "SoundScreen"}
CARD_SOUNDS = {"The hunt begins": "wayfinder", "Knocked out": "faint", "Fallen": "death",
               "Passed away": "death", "Bounty done": "bounty_done", "Back in Bytorsskug": "hunt_return",
               "Contract not done": "hunt_return", "Retired": "hunt_return",
               "Out of the miasma": "hunt_return", "Lost on the Brisering": "death"}     # (v0.89.0)


def on_screen(screen) -> None:
    """A window has opened: its sound (a title card's is the moment's own)."""
    name = type(screen).__name__
    if name in QUIET_SCREENS:
        return
    if name == "TitleCardScreen":
        heading = getattr(screen, "heading", "")
        play(CARD_SOUNDS.get(heading) or ("hunt_complete" if "complete" in heading.lower() else "ui_popup"))
    elif name == "SceneScreen":
        play("ui_popup")
    elif name == "TalentScreen":
        play("talent")
    else:
        play("ui_open", gap=0.15)


def on_key(screen, kind: str) -> None:
    """A key pressed in a window: kind is move, confirm or cancel."""
    if type(screen).__name__ in ("CrawlScreen",):
        return
    play({"move": "ui_move", "confirm": "ui_confirm", "cancel": "ui_cancel"}[kind], gap=0.03)
