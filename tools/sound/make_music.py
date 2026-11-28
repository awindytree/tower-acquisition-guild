"""Make TAG's music from code (v0.102.0): nothing recorded.

    python tools/sound/make_music.py              (writes data/music/*.wav)

The user asked the assistant to try music for Bytorsskug (2026-11-28). The user makes the game's music
otherwise; this is the assistant's attempt, a placeholder for the user to judge by ear.

**Bytorsskug** ("The City in the Tower's Shadow"): a slow piece in D Dorian at 60 beats a minute, 24
bars of 4 (96 seconds), that loops without a seam. A low drone (the Tower, always there), a pad, a
plucked ostinato (the city going about its business), a bowed melody with a Nordic lilt (the old,
Scandinavian-rooted names), glass chimes (shards were windcatcher glass) in the middle, and a cello
under the second half. Moody and warm: a lit city in a very dark world.

Stereo, 16-bit, 22,050 Hz (the game converts it for the sound card). Every part is built from fixed
seeds, so running this again gives the same file. Needs only numpy (and make_sounds' building blocks).
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_sounds import RATE, band, bell, low, rng_for, t  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "music"
LEVEL = 0.10          # loudness (RMS): a little above the city's ambience (0.09), under the effects
BPM = 60
BEAT = 60 / BPM
BAR = 4 * BEAT


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


# ---- Voices ------------------------------------------------------------------------------------
def adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    """Attack, decay to sustain s, hold, release over the last r seconds (all in seconds but s)."""
    e = np.full(n, s)
    na, nd, nr = int(a * RATE), int(d * RATE), int(r * RATE)
    na = min(na, n)
    e[:na] = np.linspace(0, 1, na) if na else e[:na]
    if nd and na + nd < n:
        e[na:na + nd] = np.linspace(1, s, nd)
    if nr and nr < n:
        e[-nr:] *= np.linspace(1, 0, nr) ** 1.5
    return e


def bowed(midi: float, dur: float, rng, bright: float = 2600, vib: float = 5.2) -> np.ndarray:
    """A bowed string: harmonics falling away, a vibrato that comes in after the attack, a little bow
    noise. Rings on a moment past its length."""
    tail = 0.6
    tt = t(dur + tail)
    n = len(tt)
    depth = np.clip((tt - 0.25) / 0.5, 0, 1) * 0.0045
    phase = 2 * np.pi * hz(midi) * np.cumsum(1 + depth * np.sin(2 * np.pi * vib * tt + rng.uniform(0, 6))) / RATE
    x = np.zeros(n)
    for k in range(1, 12):
        x += np.sin(k * phase) / k ** 1.25 * (1 if k % 2 else 0.8)
    x = low(x, bright)
    x += low(band(rng.standard_normal(n), 1500, 5000), 6000) * 0.02
    env = adsr(n, 0.12, 0.3, 0.8, tail + 0.25)
    return x * env


def cello(midi: float, dur: float, rng) -> np.ndarray:
    return bowed(midi, dur, rng, bright=1100, vib=4.6) * 0.9


def pad(midis, dur: float, rng) -> np.ndarray:
    """A soft chord: detuned saws, filtered dark, slow in and out."""
    tail = 1.5
    tt = t(dur + tail)
    x = np.zeros(len(tt))
    for m in midis:
        for det in (-0.06, 0.0, 0.07):
            f = hz(m + det)
            ph = rng.uniform(0, 2 * np.pi)
            for k in range(1, 9):
                x += np.sin(2 * np.pi * f * k * tt + ph * k) / k
    x = low(x, 900)
    return x * adsr(len(tt), 1.4, 0.5, 0.85, tail + 0.6) / len(midis)


def pluck(midi: float, dur: float, rng, damp: float = 0.994) -> np.ndarray:
    """Karplus-Strong, vectorised by period: a plucked string with a soft, woody top."""
    n = int(dur * RATE)
    p = max(2, int(round(RATE / hz(midi))))
    buf = low(rng.uniform(-1, 1, p * 4), 2500)[:p]
    out = np.empty(n)
    i = 0
    while i < n:
        k = min(p, n - i)
        out[i:i + k] = buf[:k]
        buf = damp * 0.5 * (buf + np.roll(buf, -1))
        i += k
    out *= np.exp(-np.linspace(0, dur * 1.2, n))
    a = int(0.004 * RATE)
    out[:a] *= np.linspace(0, 1, a)
    return out


def drum(dur: float, rng) -> np.ndarray:
    """A soft frame drum, felt more than heard."""
    tt = t(dur)
    body = np.sin(2 * np.pi * (58 + 30 * np.exp(-tt * 18)) * tt) * np.exp(-tt * 5)
    skin = low(rng.standard_normal(len(tt)), 900) * np.exp(-tt * 30) * 0.3
    return body + skin


# ---- The score --------------------------------------------------------------------------------------
D = 50   # D3
CHORDS = {   # chord: (root midi in octave 3, third: 3 minor / 4 major, extra)
    "Dm": (50, 3), "C": (48, 4), "Bb": (46, 4), "Am": (45, 3), "G": (43, 4), "F": (41, 4), "A": (45, 3),
}
BARS = (["Dm"] * 4                                           # 1-4: the drone, the city waking
        + ["Dm", "C", "Bb", "C", "Dm", "Am", "G", "A"]       # 5-12: the tune
        + ["Bb", "F", "C", "Dm"]                             # 13-16: glass
        + ["Dm", "F", "G", "Am", "Bb", "C"]                  # 17-22: the tune again, with a cello
        + ["Dm", "Dm"])                                      # 23-24: back to the drone
LENGTH = len(BARS) * BAR

# melody: (bar 1-based, beat 0-based, midi, beats)
TUNE = [
    (5, 0, 69, 2), (5, 2, 67, 1), (5, 3, 65, 1),
    (6, 0, 64, 3), (6, 3, 67, 1),
    (7, 0, 65, 2), (7, 2, 62, 1), (7, 3, 65, 1),
    (8, 0, 64, 4),
    (9, 0, 69, 1.5), (9, 1.5, 72, 0.5), (9, 2, 74, 2),
    (10, 0, 72, 1), (10, 1, 71, 1), (10, 2, 69, 2),
    (11, 0, 71, 1), (11, 1, 69, 1), (11, 2, 67, 2),
    (12, 0, 69, 4),
    (17, 0, 74, 2), (17, 2, 72, 1), (17, 3, 69, 1),
    (18, 0, 72, 3), (18, 3, 69, 1),
    (19, 0, 71, 2), (19, 2, 74, 2),
    (20, 0, 76, 2), (20, 2, 72, 1), (20, 3, 71, 1),
    (21, 0, 74, 2), (21, 2, 69, 1), (21, 3, 65, 1),
    (22, 0, 64, 2), (22, 2, 67, 1), (22, 3, 64, 1),
    (23, 0, 62, 4),
]
CELLO = [(17, 38, 4), (18, 41, 4), (19, 43, 4), (20, 45, 4), (21, 46, 4), (22, 48, 4), (23, 38, 8)]
CHIMES = [(13, 0, 86), (13, 2.5, 81), (14, 1, 77), (14, 3, 84), (15, 0.5, 79), (15, 2, 88), (16, 0, 86),
          (16, 1.5, 81), (16, 3, 74), (8, 3, 81), (24, 2, 86)]


def place(buf: np.ndarray, x: np.ndarray, start: float, gain: float = 1.0) -> None:
    """Add x into the loop buffer at `start` seconds; whatever runs past the end wraps to the start,
    so the loop has no seam."""
    i = int(start * RATE) % len(buf)
    n = len(x)
    while n > 0:
        k = min(n, len(buf) - i)
        buf[i:i + k] += x[len(x) - n:len(x) - n + k] * gain
        n -= k
        i = 0


def pan(x: np.ndarray, where: float):
    """where: -1 left, 0 middle, 1 right (constant power)."""
    a = (where + 1) * np.pi / 4
    return x * np.cos(a), x * np.sin(a)


def wrap_reverb(x: np.ndarray, seconds: float, mix: float, bright: float, seed: str) -> np.ndarray:
    """Reverb whose tail wraps round, so the loop's end rings into its start."""
    rng = rng_for(seed)
    n = int(seconds * RATE)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 6, n))
    ir = low(ir, bright)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    N = len(x)
    y = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(np.concatenate([ir, np.zeros(N - n)])), N)   # circular
    return x * (1 - mix) + y * mix


def bytorsskug() -> np.ndarray:
    n = int(LENGTH * RATE)
    L, R = np.zeros(n), np.zeros(n)
    rng = rng_for("music/bytorsskug")

    def add(x, start, gain, where):
        l, r = pan(x, where)
        place(L, l, start, gain)
        place(R, r, start, gain)

    # the drone: D and A, low, the whole way, breathing on a period that divides the loop
    tt = np.arange(n) / RATE
    breath = 0.8 + 0.2 * np.sin(2 * np.pi * tt / (LENGTH / 3))
    drone = (np.sin(2 * np.pi * hz(38) * tt) + 0.5 * np.sin(2 * np.pi * hz(45) * tt)
             + 0.2 * np.sin(2 * np.pi * hz(50) * tt + 0.3)) * breath
    drone = low(drone + 0.15 * np.sin(2 * np.pi * hz(38) * 2.003 * tt), 400)
    add(drone, 0, 0.16, 0)

    # the pad: each bar's chord, louder in the tune's sections
    for b, name in enumerate(BARS):
        root, third = CHORDS[name]
        notes = [root + 12, root + 12 + third, root + 19]
        g = 0.07 if b < 4 or b >= 22 else 0.11
        add(pad(notes, BAR, rng), b * BAR, g, -0.35 if b % 2 else 0.35)

    # the ostinato: eighth notes up and down the chord, quiet at the edges
    for b, name in enumerate(BARS[:22]):
        root, third = CHORDS[name]
        r = root + (12 if root < 46 else 0)
        pattern = [r, r + 7, r + 12, r + 12 + third, r + 12, r + 7, r + 12, r + 7]
        edge = 0.55 if b < 2 else 0.8 if b < 4 else 1.0
        for k, m in enumerate(pattern):
            if b < 2 and k % 2:
                continue                                   # it starts sparse
            g = (0.16 if k % 4 == 0 else 0.11) * edge * rng.uniform(0.85, 1.05)
            add(pluck(m, 2.2, rng), b * BAR + k * BEAT / 2 + rng.uniform(0, 0.012), g, 0.45)

    # the tune
    for bar, beat, m, beats in TUNE:
        add(bowed(m, beats * BEAT, rng), (bar - 1) * BAR + beat * BEAT, 0.16, -0.15)
    # the cello under the second half
    for bar, m, beats in CELLO:
        add(cello(m, beats * BEAT, rng), (bar - 1) * BAR, 0.14, 0.2)
    # glass
    for bar, beat, m in CHIMES:
        x = bell(hz(m), 5.0, decay=1.4)
        add(x, (bar - 1) * BAR + beat * BEAT, 0.05, rng.uniform(-0.7, 0.7))
    # a soft heartbeat through the tune's sections
    for b in list(range(4, 12)) + list(range(16, 22)):
        add(drum(1.5, rng), b * BAR, 0.18, 0)
        add(drum(1.5, rng), b * BAR + 2.5 * BEAT, 0.09, 0)

    L = wrap_reverb(L, 3.2, 0.32, 3500, "music/verb/L")
    R = wrap_reverb(R, 3.2, 0.32, 3500, "music/verb/R")
    out = np.stack([L, R], axis=1)
    out = np.tanh(out / 0.9) * 0.9
    out *= LEVEL / (np.sqrt(np.mean(out ** 2)) + 1e-12)      # by loudness, to sit with the ambience
    return out * min(1.0, 0.95 / (np.abs(out).max() + 1e-9))


def write(name: str, x: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


MUSIC = {"bytorsskug": bytorsskug}

if __name__ == "__main__":
    for name in sys.argv[1:] or MUSIC:
        write(name, MUSIC[name]())
        print("wrote", name)
