"""The v0.103.0 music (tools/sound/make_music.py runs this): the user liked Bytorsskug and asked for more.

- **The Tower's Shadow** (title screen and the opening crawl): Bytorsskug's falling figure (A G F E) as
  the game's motif, stated low by brass and choir, then by the fiddle. D minor, 54 beats a minute.
- **The Brisering** (the open land inside the Chorus Winds): wide and sparse: open fifths, a wandering
  flute, a harp, the wind swelling and falling. D Dorian, 50 beats a minute.
- **The miasma**, four pieces with no beat to hold on to, quiet under the land's own soundscape:
  - *the wilds* (forests, plains, grassland): a low cluster, plucks that come when they like, a chime that
    bends out of tune;
  - *the deep* (caves): very low drones, bowed glass beating against itself, drips;
  - *stone* (ruins, mountains): a low bell tolling at odd times, a humming choir, minor seconds;
  - *the mire* (marsh): murky, sliding pitches, slow bubbles.
- **Stingers** for the big cards (data/sounds/st_*.ogg): the hunt begins, a hunt or contract complete,
  out of the miasma, knocked out, fallen, a new rank, a chapter.

Everything is the assistant's: placeholders for the user's ear.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from make_music import (BAR, BEAT, MUSIC, adsr, bowed, cello, drum, finish, hz, pad, pan, place, pluck)
from make_sounds import RATE, band, bell, low, rng_for, t

SOUNDS_OUT = Path(__file__).resolve().parents[2] / "data" / "sounds"


# ---- More voices ------------------------------------------------------------------------------------
def choir(midis, dur: float, rng, vowel=(700, 1150, 2600)) -> np.ndarray:
    """Voices on "ah": harmonics shaped by three formants, slowly drifting apart."""
    tail = 2.0
    tt = t(dur + tail)
    x = np.zeros(len(tt))
    for m in midis:
        for det in (-0.08, 0.0, 0.09):
            f = hz(m + det)
            wob = 1 + 0.003 * np.sin(2 * np.pi * rng.uniform(4.5, 5.5) * tt + rng.uniform(0, 6))
            ph = 2 * np.pi * f * np.cumsum(wob) / RATE
            for k in range(1, 24):
                fk = f * k
                if fk > 5000:
                    break
                g = sum(np.exp(-((fk - F) / (F * 0.18)) ** 2) * a for F, a in zip(vowel, (1, 0.6, 0.25)))
                x += np.sin(k * ph) * (g + 0.02) / k ** 0.5
    return x * adsr(len(tt), 1.8, 0.5, 0.9, tail + 0.8) / (3 * len(midis))


def flute(midi: float, dur: float, rng) -> np.ndarray:
    tail = 0.5
    tt = t(dur + tail)
    depth = np.clip((tt - 0.3) / 0.6, 0, 1) * 0.004
    ph = 2 * np.pi * hz(midi) * np.cumsum(1 + depth * np.sin(2 * np.pi * 4.8 * tt)) / RATE
    x = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    breath = band(rng.standard_normal(len(tt)), hz(midi) * 0.8, hz(midi) * 3) * 0.12
    return (x + breath) * adsr(len(tt), 0.15, 0.2, 0.85, tail + 0.3)


def brass(midis, dur: float, rng) -> np.ndarray:
    """Low horns: a saw whose filter opens with the note."""
    tail = 1.0
    tt = t(dur + tail)
    n = len(tt)
    x = np.zeros(n)
    for m in midis:
        f = hz(m)
        for k in range(1, 14):
            x += np.sin(2 * np.pi * f * k * tt + rng.uniform(0, 0.3)) / k
    open_ = adsr(n, 0.6, 0.8, 0.6, tail + 0.4)
    bright = low(x, 500) * (1 - open_) + low(x, 1400) * open_
    return bright * adsr(n, 0.35, 0.6, 0.8, tail + 0.4) / len(midis)


def glass(midi: float, dur: float, rng, beat: float = 0.7) -> np.ndarray:
    """Bowed glass: bell partials that swell instead of strike, two of them beating."""
    tail = 2.0
    tt = t(dur + tail)
    f = hz(midi)
    x = np.zeros(len(tt))
    for ratio, a in ((1, 1), (2.76, 0.35), (5.4, 0.12)):
        x += a * (np.sin(2 * np.pi * f * ratio * tt) + np.sin(2 * np.pi * (f * ratio + beat) * tt))
    return x * adsr(len(tt), 2.0, 0.5, 0.8, tail + 1.0) * 0.5


def wind(dur: float, rng, lo=200, hi=1200) -> np.ndarray:
    n = int(dur * RATE)
    x = band(rng.standard_normal(n), lo, hi)
    k = max(4, int(dur / 3))
    swell = np.interp(np.linspace(0, k, n), np.arange(k + 1), rng.uniform(0.1, 1, k + 1))
    return x * low(swell, 1) * 0.5


def harp(midi: float, rng) -> np.ndarray:
    return pluck(midi, 3.0, rng, damp=0.997)


def bend(midi: float, dur: float, to: float, rng) -> np.ndarray:
    """A tone that slides from one pitch to another (the miasma bending things)."""
    tt = t(dur)
    f = hz(midi) * (hz(to) / hz(midi)) ** np.clip(tt / dur, 0, 1)
    ph = 2 * np.pi * np.cumsum(f) / RATE
    x = np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)
    return x * adsr(len(tt), dur * 0.3, 0.2, 0.8, dur * 0.4)


def drone(n: int, midis, length: float, gains=None, cut: float = 400, periods=3) -> np.ndarray:
    tt = np.arange(n) / RATE
    breath = 0.8 + 0.2 * np.sin(2 * np.pi * tt / (length / periods))
    x = np.zeros(n)
    for m, g in zip(midis, gains or [1] * len(midis)):
        x += g * np.sin(2 * np.pi * hz(m) * tt) + 0.15 * g * np.sin(2 * np.pi * hz(m) * 2.002 * tt)
    return low(x * breath, cut)


class Score:
    """A stereo loop buffer to place notes in (whatever runs past the end wraps round)."""
    def __init__(self, length: float, seed: str):
        self.length = length
        self.n = int(length * RATE)
        self.L, self.R = np.zeros(self.n), np.zeros(self.n)
        self.rng = rng_for(seed)

    def add(self, x, start, gain, where=0.0):
        l, r = pan(x, where)
        place(self.L, l, start, gain)
        place(self.R, r, start, gain)


TRIAD = {"Dm": (50, 3), "C": (48, 4), "Bb": (46, 4), "Am": (45, 3), "G": (43, 4), "F": (41, 4), "A": (45, 4),
         "Gm": (43, 3), "Em": (40, 3), "Dsus": (50, 5)}


def chord(name, octave=0):
    r, third = TRIAD[name]
    r += 12 * octave
    return [r, r + third, r + 7] if third != 5 else [r, r + 5, r + 7]


# ---- The Tower's Shadow (the title) ------------------------------------------------------------------
TITLE_BEAT = 60 / 54
TITLE_BAR = 4 * TITLE_BEAT


def the_tower() -> np.ndarray:
    bars = (["Dm"] * 4 + ["Dm", "Bb", "F", "C"] + ["Dm", "Bb", "Gm", "A"] + ["Bb", "F", "C", "Dm"]
            + ["Bb", "Gm", "A", "Dm"])
    s = Score(len(bars) * TITLE_BAR, "music/the_tower")
    B, b = TITLE_BAR, TITLE_BEAT
    s.add(drone(s.n, [38, 45], s.length, [1, 0.5]), 0, 0.17)
    for i, name in enumerate(bars):
        g = 0.05 if i < 4 else 0.08 if i < 12 else 0.1 if i < 16 else 0.06
        s.add(choir(chord(name, 1), B, s.rng), i * B, g, -0.3)
        s.add(pad(chord(name, 1), B, s.rng), i * B, 0.05, 0.3)
    # the motif, low: A G F E, then the answer F E D
    for bar, notes in ((5, [(0, 57, 2), (2, 55, 1), (3, 53, 1)]), (6, [(0, 52, 4)]),
                       (7, [(0, 53, 2), (2, 52, 1), (3, 50, 1)]), (8, [(0, 52, 4)]),
                       (13, [(0, 57, 2), (2, 55, 1), (3, 53, 1)]), (14, [(0, 52, 3), (3, 53, 1)]),
                       (15, [(0, 55, 2), (2, 52, 2)]), (16, [(0, 50, 4)])):
        for beat, m, beats in notes:
            s.add(brass([m, m - 12], beats * b, s.rng), (bar - 1) * B + beat * b, 0.14, 0.1)
    # the fiddle answers, high
    for bar, beat, m, beats in ((9, 0, 69, 2), (9, 2, 67, 1), (9, 3, 65, 1), (10, 0, 64, 2), (10, 2, 62, 2),
                                (11, 0, 67, 2), (11, 2, 65, 1), (11, 3, 64, 1), (12, 0, 69, 4),
                                (17, 0, 74, 2), (17, 2, 72, 1), (17, 3, 69, 1), (18, 0, 70, 3), (18, 3, 67, 1),
                                (19, 0, 69, 4), (20, 0, 62, 4)):
        s.add(bowed(m, beats * b, s.rng), (bar - 1) * B + beat * b, 0.12, -0.15)
    # harp under the fiddle's sections
    for i, name in enumerate(bars):
        if 8 <= i < 12 or 16 <= i < 19:
            for k, m in enumerate(chord(name, 1) + [chord(name, 1)[0] + 12]):
                s.add(harp(m, s.rng), i * B + k * b, 0.1, 0.5)
    # glass, and a deep toll at each section's start
    for bar, beat, m in ((1, 0, 86), (3, 2, 81), (8, 3, 84), (12, 2, 81), (16, 3, 86), (20, 1, 81)):
        s.add(bell(hz(m), 5.0, decay=1.3), (bar - 1) * B + beat * b, 0.045, s.rng.uniform(-0.6, 0.6))
    for bar in (1, 5, 9, 13, 17):
        s.add(bell(hz(38), 6.0, decay=0.8), (bar - 1) * B, 0.09, 0)
        s.add(drum(2.0, s.rng), (bar - 1) * B, 0.2, 0)
    return finish(s.L, s.R, 0.10, verb=4.0, wet=0.38, seed="music/the_tower/verb")


# ---- The Brisering --------------------------------------------------------------------------------------
BRIS_BEAT = 60 / 50
BRIS_BAR = 4 * BRIS_BEAT


def the_brisering() -> np.ndarray:
    bars = ["Dsus", "Dm", "C", "Dm", "G", "Am", "C", "Dm"] * 2 + ["F", "C", "G", "Dm", "Bb", "C", "Dsus", "Dm"]
    s = Score(len(bars) * BRIS_BAR, "music/the_brisering")
    B, b = BRIS_BAR, BRIS_BEAT
    s.add(drone(s.n, [38, 45, 50], s.length, [0.8, 0.6, 0.3], cut=500, periods=4), 0, 0.12)
    s.add(wind(s.length, s.rng), 0, 0.12, -0.4)
    s.add(wind(s.length, rng_for("music/the_brisering/wind2"), 400, 2000), 0, 0.06, 0.5)
    for i, name in enumerate(bars):
        r = chord(name)[0]
        s.add(pad([r + 12, r + 19], B, s.rng), i * B, 0.06, 0)              # open fifths, wide
        # a slow harp: root, fifth, octave, spread out
        for k, m in enumerate([r + 12, r + 19, r + 24]):
            if (i + k) % 3 != 2:
                s.add(harp(m, s.rng), i * B + k * b * 1.3 + s.rng.uniform(0, 0.05), 0.09, 0.4)
    # the flute wanders over the second and third parts
    tune = [(9, 0, 74, 3), (9, 3, 76, 1), (10, 0, 72, 2), (10, 2, 69, 2), (11, 0, 72, 2), (11, 2, 74, 2),
            (12, 0, 69, 4), (13, 0, 67, 2), (13, 2, 71, 2), (14, 0, 69, 4), (15, 0, 72, 2), (15, 2, 67, 2),
            (16, 0, 69, 4), (18, 0, 72, 2), (18, 2, 76, 2), (19, 0, 74, 4), (20, 0, 69, 3), (20, 3, 67, 1),
            (21, 0, 65, 2), (21, 2, 69, 2), (22, 0, 67, 4), (23, 0, 69, 4)]
    for bar, beat, m, beats in tune:
        s.add(flute(m, beats * b, s.rng), (bar - 1) * B + beat * b, 0.1, -0.2)
    for bar, beat, m in ((4, 2, 86), (8, 3, 81), (16, 1, 84), (24, 2, 86)):
        s.add(bell(hz(m), 5.0, decay=1.5), (bar - 1) * B + beat * b, 0.035, s.rng.uniform(-0.7, 0.7))
    return finish(s.L, s.R, 0.065, verb=4.5, wet=0.4, seed="music/the_brisering/verb")


# ---- The miasma ----------------------------------------------------------------------------------------
MIASMA_LEVEL = 0.05      # quiet: the land's own soundscape is the main thing out there


def _events(s: Score, every: float, jitter: float, fn, start: float = 0.0):
    """Things that come when they like: roughly every `every` seconds, never on a beat."""
    tpos = start + s.rng.uniform(0, every)
    while tpos < s.length:
        fn(tpos)
        tpos += every * s.rng.uniform(1 - jitter, 1 + jitter)


def miasma_wilds() -> np.ndarray:
    s = Score(88.0, "music/miasma_wilds")
    s.add(drone(s.n, [38, 39, 45], s.length, [0.7, 0.35, 0.4], cut=350, periods=2), 0, 0.2)   # D and E-flat rub
    for k, (start, ch) in enumerate(((0, [50, 53, 57]), (22, [49, 53, 56]), (44, [50, 53, 58]), (66, [48, 51, 55]))):
        s.add(pad(ch, 22, s.rng), start, 0.07, -0.3 if k % 2 else 0.3)
    notes = [50, 53, 55, 56, 57, 60, 62, 63]
    _events(s, 2.6, 0.7, lambda tp: s.add(pluck(s.rng.choice(notes), 2.5, s.rng, 0.992), tp, 0.12,
                                          s.rng.uniform(-0.6, 0.6)))
    def chime(tp):
        m = s.rng.choice([81, 84, 86, 87])
        x = bell(hz(m), 4.0, decay=1.6)
        tt = t(4.0)
        drift = np.sin(2 * np.pi * hz(m) * (1 - 0.03 * tt / 4) * tt) * np.exp(-tt * 1.4) * 0.6   # out of tune
        s.add(x + drift, tp, 0.04, s.rng.uniform(-0.8, 0.8))
    _events(s, 13, 0.5, chime, 4)
    s.add(wind(s.length, s.rng, 150, 600), 0, 0.08, 0)
    return finish(s.L, s.R, MIASMA_LEVEL, verb=4.0, wet=0.45, seed="music/miasma_wilds/verb")


def miasma_deep() -> np.ndarray:
    s = Score(92.0, "music/miasma_deep")
    s.add(drone(s.n, [26, 33, 38], s.length, [1, 0.5, 0.25], cut=220, periods=2), 0, 0.3)
    for start, m in ((0, 62), (18, 63), (37, 61), (55, 62), (74, 57)):
        s.add(glass(m, 16, s.rng, beat=s.rng.uniform(0.4, 1.2)), start, 0.06, s.rng.uniform(-0.5, 0.5))
    _events(s, 3.5, 0.8, lambda tp: s.add(pluck(s.rng.choice([86, 89, 91, 93]), 0.6, s.rng, 0.98), tp, 0.06,
                                          s.rng.uniform(-0.9, 0.9)))
    _events(s, 11, 0.5, lambda tp: s.add(cello(s.rng.choice([38, 39, 41]), 5, s.rng), tp, 0.07, 0.2), 6)
    return finish(s.L, s.R, MIASMA_LEVEL, verb=6.0, wet=0.55, bright=2200, seed="music/miasma_deep/verb")


def miasma_stone() -> np.ndarray:
    s = Score(96.0, "music/miasma_stone")
    s.add(drone(s.n, [38, 45], s.length, [0.6, 0.4], cut=300, periods=2), 0, 0.16)
    for k, ch in enumerate(([50, 51, 57], [48, 50, 55], [50, 53, 56], [46, 50, 51])):
        s.add(choir(ch, 24, s.rng, vowel=(450, 800, 2500)), k * 24, 0.08, -0.2 if k % 2 else 0.2)
    _events(s, 9.0, 0.6, lambda tp: s.add(bell(hz(s.rng.choice([38, 39, 43])), 7.0, decay=0.7), tp, 0.13,
                                          s.rng.uniform(-0.3, 0.3)))
    _events(s, 16, 0.4, lambda tp: s.add(bell(hz(s.rng.choice([74, 75, 81])), 5.0, decay=1.2), tp, 0.03,
                                         s.rng.uniform(-0.8, 0.8)), 7)
    s.add(wind(s.length, s.rng, 100, 500), 0, 0.07, 0)
    return finish(s.L, s.R, MIASMA_LEVEL, verb=5.0, wet=0.5, seed="music/miasma_stone/verb")


def miasma_mire() -> np.ndarray:
    s = Score(90.0, "music/miasma_mire")
    s.add(drone(s.n, [33, 38, 40], s.length, [0.6, 0.6, 0.25], cut=260, periods=3), 0, 0.22)
    for start, (a, b_) in ((0, (50, 49)), (15, (53, 55)), (30, (49, 47)), (45, (56, 53)), (60, (50, 51)),
                           (75, (55, 50))):
        s.add(bend(a, 14, b_, s.rng), start, 0.05, s.rng.uniform(-0.6, 0.6))
        s.add(low(bend(a - 12, 14, b_ - 12, s.rng), 400), start + 0.5, 0.06, 0)
    def bubble(tp):
        m = s.rng.choice([45, 48, 50, 52])
        x = bend(m, 0.5, m + s.rng.choice([5, 7]), s.rng) * np.exp(-np.linspace(0, 6, int(0.5 * RATE)))
        s.add(low(x, 700), tp, 0.12, s.rng.uniform(-0.7, 0.7))
    _events(s, 2.8, 0.8, bubble)
    return finish(s.L, s.R, MIASMA_LEVEL, verb=4.0, wet=0.5, bright=1800, seed="music/miasma_mire/verb")


MUSIC.update({"the_tower": the_tower, "the_brisering": the_brisering, "miasma_wilds": miasma_wilds,
              "miasma_deep": miasma_deep, "miasma_stone": miasma_stone, "miasma_mire": miasma_mire})


# ---- Stingers -------------------------------------------------------------------------------------------
def _sting(length: float, seed: str):
    s = Score(length + 6, seed)          # (room for the tails; the reverb doesn't wrap: trimmed below)
    return s


def _end(s: Score, length: float, peak: float = 0.6) -> np.ndarray:
    from make_sounds import reverb
    L, R = reverb(s.L, 2.5, 0.35, 3500, "sting/L"), reverb(s.R, 2.5, 0.35, 3500, "sting/R")
    n = min(len(L), len(R))
    out = np.stack([L[:n], R[:n]], axis=1)
    idx = np.nonzero(np.abs(out).max(axis=1) > 0.002 * np.abs(out).max())[0]
    out = out[: idx[-1] + 1]
    f = int(0.3 * RATE)
    out[-f:] *= np.linspace(1, 0, f)[:, None]
    return np.tanh(out / 0.9) * 0.9 * (peak / (np.abs(out).max() + 1e-9))


def st_begin() -> np.ndarray:
    """The hunt begins: the Wayfinder's pull, a rising, uneasy chord."""
    s = _sting(4, "music/st_begin")
    s.add(brass([38, 45], 3.0, s.rng), 0, 0.3)
    s.add(choir([50, 56, 57], 3.5, s.rng), 0.4, 0.25, -0.2)
    s.add(bend(62, 2.5, 69, s.rng), 0.6, 0.12, 0.3)
    for k, m in enumerate((81, 86, 88)):
        s.add(bell(hz(m), 3.0, decay=1.5), 1.2 + k * 0.35, 0.08, -0.5 + k * 0.5)
    return _end(s, 4)


def st_complete() -> np.ndarray:
    """A hunt or contract done: the motif, resolved to the major."""
    s = _sting(5, "music/st_complete")
    for k, (m, d) in enumerate(((69, 0.5), (67, 0.5), (65, 0.5), (66, 2.5))):
        s.add(bowed(m, d, s.rng), k * 0.45, 0.3, -0.15)
    s.add(choir([50, 54, 57], 3.5, s.rng), 1.35, 0.25, 0.2)
    s.add(brass([38, 50], 3.0, s.rng), 1.35, 0.25)
    for k, m in enumerate((74, 78, 81, 86)):
        s.add(harp(m, s.rng), 1.35 + k * 0.12, 0.15, 0.4)
    return _end(s, 5)


def st_out() -> np.ndarray:
    """Out of the miasma (or home): a breath of relief."""
    s = _sting(4, "music/st_out")
    s.add(pad([50, 57, 62, 66], 3.0, s.rng), 0, 0.35)
    for k, m in enumerate((62, 66, 69, 74)):
        s.add(harp(m, s.rng), 0.1 + k * 0.18, 0.2, -0.3 + k * 0.2)
    s.add(flute(69, 2.0, s.rng), 0.6, 0.15, -0.2)
    return _end(s, 4)


def st_faint() -> np.ndarray:
    """Knocked out: everything slides away."""
    s = _sting(3, "music/st_faint")
    s.add(bend(62, 2.5, 55, s.rng), 0, 0.25, -0.2)
    s.add(bend(65, 2.5, 56, s.rng), 0.05, 0.2, 0.2)
    s.add(drum(2.0, s.rng), 0, 0.5)
    return _end(s, 3)


def st_fallen() -> np.ndarray:
    """Fallen, passed away, lost on the Brisering: a low toll and the motif falling all the way."""
    s = _sting(7, "music/st_fallen")
    s.add(bell(hz(38), 7.0, decay=0.6), 0, 0.35)
    for k, (m, d) in enumerate(((57, 0.9), (55, 0.9), (53, 0.9), (52, 1.5), (50, 3.0))):
        s.add(cello(m, d, s.rng), 0.4 + k * 0.9, 0.3, 0.1)
    s.add(choir([38, 45, 50], 5.0, s.rng, vowel=(450, 800, 2500)), 1.5, 0.2, -0.2)
    return _end(s, 7)


def st_rank() -> np.ndarray:
    """A new rank: the motif, rising instead of falling."""
    s = _sting(5, "music/st_rank")
    for k, m in enumerate((62, 64, 65, 69)):
        s.add(brass([m, m - 12], 0.7 if k < 3 else 2.8, s.rng), k * 0.5, 0.3)
    s.add(choir([50, 57, 62], 3.0, s.rng), 1.5, 0.25, -0.2)
    for k, m in enumerate((86, 90, 93)):
        s.add(bell(hz(m), 3.5, decay=1.4), 1.6 + k * 0.25, 0.08, -0.5 + k * 0.5)
    return _end(s, 5)


def st_chapter() -> np.ndarray:
    """A chapter begins or ends: the Tower's toll, the motif once in the fiddle."""
    s = _sting(6, "music/st_chapter")
    s.add(bell(hz(38), 6.0, decay=0.7), 0, 0.3)
    s.add(drone(int(6 * RATE), [38, 45], 6.0, cut=300), 0, 0.2)
    for k, (m, d) in enumerate(((69, 1.0), (67, 0.5), (65, 0.5), (64, 3.0))):
        s.add(bowed(m, d, s.rng), 0.8 + [0, 1.0, 1.5, 2.0][k], 0.25, -0.15)
    s.add(bell(hz(86), 4.0, decay=1.4), 2.0, 0.06, 0.6)
    return _end(s, 6)


STINGERS = {"st_begin": st_begin, "st_complete": st_complete, "st_out": st_out, "st_faint": st_faint,
            "st_fallen": st_fallen, "st_rank": st_rank, "st_chapter": st_chapter}
