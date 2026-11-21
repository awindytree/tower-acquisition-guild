"""Make TAG's sound effects and ambience loops (v0.63.0), from code: nothing recorded.

    python tools/sound/make_sounds.py            (writes data/sounds/*.wav)
    python tools/sound/make_sounds.py hit miss   (only these)

The user's direction: moody and ambient, not chiptune. Soft attacks, filtered noise, low
tones, glassy chimes (shards were windcatcher glass), reverb. Every sound is built from a
fixed seed, so running this again gives the same files. Needs only numpy.

Sounds are 16-bit mono WAV at 22,050 Hz (small files; the game converts them to the sound
card's format when it loads them). Ambience loops are 16 seconds and loop seamlessly.
All of it is a placeholder for the user to judge by ear.
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

RATE = 22050
OUT = Path(__file__).resolve().parents[2] / "data" / "sounds"
LOOP = 16.0          # seconds, for ambience


# ---- Building blocks -------------------------------------------------------------------------
def rng_for(name: str) -> np.random.Generator:
    return np.random.default_rng(abs(hash_str(name)) % (2 ** 32))


def hash_str(s: str) -> int:
    h = 2166136261
    for c in s.encode():
        h = (h ^ c) * 16777619 % 2 ** 32
    return h


def t(dur: float) -> np.ndarray:
    return np.arange(int(dur * RATE)) / RATE


def env(n: int, attack: float = 0.005, release: float = 0.1, curve: float = 3.0) -> np.ndarray:
    """A soft attack, then an exponential-ish fall to silence over the rest."""
    a = max(1, int(attack * RATE))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a) ** 2
    rest = n - a
    if rest > 0:
        x = np.linspace(0, 1, rest)
        e[a:] = (1 - x) ** curve
    r = min(n, max(1, int(release * RATE)))
    e[-r:] *= np.linspace(1, 0, r) ** 0.5
    return e


def sine(freq, dur: float, phase: float = 0.0) -> np.ndarray:
    """A sine; freq can be a number or an array (a sweep)."""
    n = int(dur * RATE)
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    return np.sin(2 * np.pi * np.cumsum(f) / RATE + phase)


def noise(dur: float, rng) -> np.ndarray:
    return rng.standard_normal(int(dur * RATE))


@np.errstate(over="ignore")
def band(x: np.ndarray, lo: float, hi: float, soft: float = 0.3) -> np.ndarray:
    """Band-pass by FFT, with soft edges (soft: share of the edge frequency)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / RATE)
    m = np.ones_like(f)
    if lo > 0:
        m *= 1 / (1 + np.exp(-(f - lo) / max(1.0, lo * soft)))
    if hi < RATE / 2:
        m *= 1 / (1 + np.exp((f - hi) / max(1.0, hi * soft)))
    return np.fft.irfft(X * m, len(x))


def low(x, hi, soft=0.3):
    return band(x, 0, hi, soft)


def high(x, lo, soft=0.3):
    return band(x, lo, RATE / 2, soft)


def reverb(x: np.ndarray, seconds: float = 1.2, mix: float = 0.3, bright: float = 3000, seed: str = "verb") -> np.ndarray:
    """Convolution with a decaying noise tail: a soft room or cave."""
    rng = rng_for(seed)
    n = int(seconds * RATE)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 7, n))
    ir = low(ir, bright)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    y = np.fft.irfft(np.fft.rfft(np.concatenate([x, np.zeros(n)])) * np.fft.rfft(np.concatenate([ir, np.zeros(len(x))])),
                     len(x) + n)
    out = np.concatenate([x, np.zeros(n)]) * (1 - mix) + y * mix
    return trim(out)


def trim(x: np.ndarray, floor: float = 1e-4) -> np.ndarray:
    idx = np.nonzero(np.abs(x) > floor * (np.abs(x).max() + 1e-12))[0]
    return x[: idx[-1] + 1] if len(idx) else x


def mix(*parts) -> np.ndarray:
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[: len(p)] += p
    return out


def at(x: np.ndarray, start: float, total: float | None = None) -> np.ndarray:
    """x, starting `start` seconds in (padded with silence before)."""
    pad = np.zeros(int(start * RATE))
    y = np.concatenate([pad, x])
    if total is not None:
        n = int(total * RATE)
        y = np.concatenate([y, np.zeros(max(0, n - len(y)))])[:n]
    return y


def bell(freq: float, dur: float, partials=((1, 1), (2.76, 0.45), (5.4, 0.2), (8.93, 0.08)), decay: float = 4.0) -> np.ndarray:
    """An inharmonic bell or glass tone."""
    tt = t(dur)
    out = np.zeros(len(tt))
    for ratio, amp in partials:
        out += amp * np.sin(2 * np.pi * freq * ratio * tt) * np.exp(-tt * decay * ratio ** 0.5)
    a = int(0.003 * RATE)
    out[:a] *= np.linspace(0, 1, a)
    return out


def pluck(freq: float, dur: float, rng, damp: float = 0.996) -> np.ndarray:
    """A plucked string (Karplus-Strong)."""
    n = int(dur * RATE)
    p = max(2, int(RATE / freq))
    buf = list(rng.uniform(-1, 1, p))
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = damp * 0.5 * (buf[i % p] + buf[(i + 1) % p])
    return out


def norm(x: np.ndarray, peak: float = 0.8) -> np.ndarray:
    m = np.abs(x).max()
    return x * (peak / m) if m > 0 else x


def seamless(x: np.ndarray, fade: float = 1.5) -> np.ndarray:
    """Make a loop of LOOP seconds from a longer buffer: its tail crossfades into its head."""
    n, f = int(LOOP * RATE), int(fade * RATE)
    assert len(x) >= n + f
    head = x[:n].copy()
    w = np.linspace(0, 1, f)
    head[:f] = head[:f] * np.sqrt(w) + x[n:n + f] * np.sqrt(1 - w)
    return head


def slow_lfo(n: int, rng, rate: float = 0.15, depth: float = 0.5) -> np.ndarray:
    """A wandering amplitude between 1 - depth and 1."""
    k = max(4, int(n / RATE * rate * 2) + 4)
    pts = rng.uniform(0, 1, k)
    curve = np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)
    curve = low(curve - curve.mean(), 2) + curve.mean()
    curve = (curve - curve.min()) / (np.ptp(curve) + 1e-9)
    return 1 - depth + depth * curve


AMBIENCE_RMS = 0.09   # ambience loops are matched by loudness, not by peak
# (v0.64.0, user: the wind was loud next to everything else) some are quieter than the rest
AMBIENCE_LEVEL = {"amb_brisering": 0.045, "amb_caves": 0.06, "amb_forest": 0.055, "amb_forest_night": 0.055,
                  "amb_ruins": 0.055, "amb_mountains": 0.055, "amb_plains": 0.05, "amb_plains_night": 0.05}


def write(name: str, x: np.ndarray, peak: float = 0.8) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if name.startswith("amb_"):
        x = x * (AMBIENCE_LEVEL.get(name, AMBIENCE_RMS) / (np.sqrt(np.mean(x ** 2)) + 1e-12))
        x = np.tanh(x / 0.7) * 0.7            # (a gentle limit on the odd loud moment)
    else:
        x = norm(x, peak)
    data = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(OUT / f"{name}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


# ---- The sounds --------------------------------------------------------------------------------
SOUNDS: dict = {}


def sound(name: str, peak: float = 0.8):
    def deco(fn):
        SOUNDS[name] = (fn, peak)
        return fn
    return deco


# Interface: quiet, soft, glassy. Heard a lot, so they must never grate.
@sound("ui_move", 0.25)
def _():
    r = rng_for("ui_move")
    x = band(noise(0.03, r), 1800, 4000) * env(int(0.03 * RATE), 0.001, 0.02, 4)
    return mix(x * 0.5, sine(1400, 0.04) * env(int(0.04 * RATE), 0.001, 0.03, 6) * 0.4)


@sound("ui_confirm", 0.4)
def _():
    a = bell(659, 0.5, decay=6) * 0.7
    b = at(bell(988, 0.6, decay=6), 0.06)
    return reverb(mix(a, b), 0.8, 0.25)


@sound("ui_cancel", 0.35)
def _():
    a = bell(523, 0.4, decay=7)
    b = at(bell(392, 0.5, decay=7), 0.07)
    return reverb(mix(a * 0.8, b), 0.6, 0.2)


@sound("ui_open", 0.3)
def _():
    r = rng_for("ui_open")
    n = noise(0.16, r)
    sweep = band(n, 500, 2500) * np.sin(np.linspace(0, np.pi, len(n))) ** 2
    return sweep


@sound("ui_popup", 0.45)
def _():
    return reverb(mix(bell(330, 1.2, decay=3) * 0.8, bell(495, 1.2, decay=3) * 0.4), 1.4, 0.3)


@sound("ui_error", 0.4)
def _():
    k = sine(np.linspace(150, 110, int(0.09 * RATE)), 0.09) * env(int(0.09 * RATE), 0.002, 0.05, 2)
    return mix(k, at(k, 0.12))


# Footsteps: quiet; a few of each so they don't repeat exactly.
def _step(name, lo, hi, dur, knock=0.0, kfreq=120, seed=0):
    r = rng_for(f"{name}{seed}")
    n = int(dur * RATE)
    x = band(noise(dur, r), lo, hi) * env(n, 0.002, dur * 0.6, 5)
    if knock:
        x = mix(x, sine(np.linspace(kfreq * 1.2, kfreq, n), dur) * env(n, 0.001, dur * 0.5, 6) * knock)
    return x


for _i in range(3):
    SOUNDS[f"step_stone_{_i + 1}"] = (lambda i=_i: _step("stone", 300, 2500, 0.07, 0.6, 110 + 15 * i, i), 0.22)
    SOUNDS[f"step_grass_{_i + 1}"] = (lambda i=_i: _step("grass", 1500, 6000, 0.11, 0.0, 0, i), 0.16)
    SOUNDS[f"step_wood_{_i + 1}"] = (lambda i=_i: _step("wood", 200, 1200, 0.08, 0.9, 170 + 20 * i, i), 0.22)
    SOUNDS[f"step_dirt_{_i + 1}"] = (lambda i=_i: _step("dirt", 250, 1800, 0.09, 0.3, 90, i), 0.18)


# Combat
@sound("hit", 0.75)
def _():
    r = rng_for("hit")
    n = int(0.16 * RATE)
    body = low(noise(0.16, r), 900) * env(n, 0.001, 0.1, 5)
    thump = sine(np.linspace(140, 60, n), 0.16) * env(n, 0.001, 0.1, 4)
    return reverb(mix(body * 0.7, thump), 0.4, 0.15)


@sound("crit", 0.85)
def _():
    r = rng_for("crit")
    n = int(0.3 * RATE)
    body = low(noise(0.3, r), 1200) * env(n, 0.001, 0.2, 4)
    thump = sine(np.linspace(120, 45, n), 0.3) * env(n, 0.001, 0.2, 3)
    ring = bell(1760, 0.6, decay=5) * 0.25
    return reverb(mix(body * 0.8, thump, ring), 0.9, 0.3)


@sound("miss", 0.4)
def _():
    r = rng_for("miss")
    n = int(0.22 * RATE)
    x = noise(0.22, r)
    swoosh = mix(*[band(x, f, f * 1.8) * (np.sin(np.linspace(0, np.pi, n)) ** 2) * w
                   for f, w in ((400, 0.6), (900, 0.4))])
    return swoosh


@sound("hurt", 0.75)
def _():
    r = rng_for("hurt")
    n = int(0.25 * RATE)
    thud = sine(np.linspace(90, 50, n), 0.25) * env(n, 0.001, 0.15, 3)
    breath = band(noise(0.25, r), 300, 1100) * env(n, 0.01, 0.2, 3) * 0.5
    return reverb(mix(thud, breath), 0.5, 0.2)


@sound("kill", 0.8)
def _():
    r = rng_for("kill")
    n = int(0.6 * RATE)
    thud = sine(np.linspace(110, 35, n), 0.6) * env(n, 0.002, 0.4, 2.5)
    body = low(noise(0.6, r), 500) * env(n, 0.002, 0.3, 4) * 0.6
    return reverb(mix(thud, body), 1.6, 0.35, bright=1500)


@sound("creature_alert", 0.45)
def _():
    n = int(1.0 * RATE)
    e = np.sin(np.linspace(0, np.pi, n)) ** 1.5
    a = sine(146.8, 1.0) * e
    b = sine(155.6, 1.0) * e * 0.8            # a minor second: unease
    c = sine(73.4, 1.0) * e * 0.6
    return reverb(low(mix(a, b, c), 1200), 1.2, 0.3)


@sound("bow", 0.6)
def _():
    r = rng_for("bow")
    twang = pluck(110, 0.35, r, 0.99) * env(int(0.35 * RATE), 0.001, 0.2, 2)
    n = int(0.15 * RATE)
    whoosh = at(band(noise(0.15, r), 1500, 5000) * np.sin(np.linspace(0, np.pi, n)) ** 2 * 0.3, 0.02)
    return mix(low(twang, 2500), whoosh)


@sound("arrow_hit", 0.6)
def _():
    r = rng_for("arrow_hit")
    n = int(0.08 * RATE)
    return mix(band(noise(0.08, r), 400, 2500) * env(n, 0.001, 0.05, 6), sine(220, 0.08) * env(n, 0.001, 0.05, 6) * 0.6)


@sound("technique", 0.7)
def _():
    r = rng_for("technique")
    n = int(0.35 * RATE)
    rise = band(noise(0.35, r), 600, 3000) * np.linspace(0, 1, n) ** 2 * 0.5
    tone = sine(np.linspace(220, 440, n), 0.35) * np.linspace(0, 1, n) ** 3 * 0.4
    strike = at(SOUNDS["crit"][0](), 0.33)
    return mix(rise, tone, strike * 0.8)


@sound("burst", 0.85)
def _():
    r = rng_for("burst")
    n = int(0.9 * RATE)
    whomp = low(noise(0.9, r), 700) * env(n, 0.004, 0.6, 2.5)
    crackle = (r.random(n) < 0.004) * r.uniform(-1, 1, n)
    crackle = band(crackle, 1500, 6000) * env(n, 0.05, 0.6, 1.5) * 3
    return reverb(mix(whomp, crackle), 0.8, 0.25)


@sound("daze", 0.45)
def _():
    n = int(0.9 * RATE)
    tt = t(0.9)
    f = 330 + 25 * np.sin(2 * np.pi * 6 * tt)
    return reverb(sine(f, 0.9) * env(n, 0.02, 0.5, 1.5) * 0.6 + sine(f * 1.5, 0.9) * env(n, 0.02, 0.5, 2) * 0.3, 0.8, 0.3)


@sound("faint", 0.7)
def _():
    n = int(2.2 * RATE)
    fall = sine(np.linspace(220, 70, n), 2.2) * env(n, 0.05, 1.0, 1.5) * 0.5
    beat = np.zeros(n)
    for s in (0.3, 0.6, 1.3, 1.6):
        k = sine(55, 0.12) * env(int(0.12 * RATE), 0.002, 0.08, 4)
        beat = mix(beat, at(k, s))
    return reverb(low(mix(fall, beat[:n]), 800), 1.5, 0.35)


@sound("death", 0.75)
def _():
    toll = bell(98, 4.0, partials=((1, 1), (2.0, 0.5), (2.76, 0.35), (5.4, 0.12)), decay=0.9)
    under = sine(49, 4.0) * env(int(4.0 * RATE), 0.3, 2, 1.2) * 0.3
    return reverb(mix(toll, under), 3.0, 0.4, bright=1800)


@sound("level_up", 0.55)
def _():
    notes = (293.7, 349.2, 440.0, 587.3)     # D F A D: a little dark, still a lift
    parts = [at(bell(f, 1.4, decay=2.5) * 0.7, i * 0.12) for i, f in enumerate(notes)]
    return reverb(mix(*parts), 2.0, 0.35)


@sound("talent", 0.5)
def _():
    n = int(1.6 * RATE)
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    chord = mix(*[sine(f, 1.6) * e * w for f, w in ((261.6, 0.5), (392.0, 0.4), (523.3, 0.3), (622.3, 0.2))])
    shimmer = high(noise(1.6, rng_for("talent")), 6000) * e * 0.05
    return reverb(mix(chord, shimmer), 2.0, 0.35)


@sound("rank_up", 0.6)
def _():
    def brass(f, d):
        tt = t(d)
        saw = sum(np.sin(2 * np.pi * f * k * tt) / k for k in range(1, 12))
        return low(saw, 1400) * env(len(tt), 0.08, d * 0.5, 1.5)
    return reverb(mix(brass(146.8, 1.2) * 0.6, at(brass(220.0, 1.6), 0.4) * 0.6), 2.0, 0.35, bright=2000)


# The world
@sound("pickup", 0.4)
def _():
    r = rng_for("pickup")
    n = int(0.12 * RATE)
    return band(noise(0.12, r), 800, 4000) * np.sin(np.linspace(0, np.pi, n)) ** 3


@sound("shards", 0.5)
def _():
    # windcatcher glass (lore): a few small, bright, inharmonic clinks
    glass = ((1, 1), (2.32, 0.5), (4.25, 0.25))
    parts = [at(bell(f, 0.5, partials=glass, decay=9), s) for f, s in ((2637, 0), (3136, 0.05), (2793, 0.11))]
    return reverb(mix(*parts), 0.6, 0.2, bright=7000)


@sound("butcher", 0.6)
def _():
    r = rng_for("butcher")
    n = int(0.3 * RATE)
    chop = low(noise(0.3, r), 1500) * env(n, 0.001, 0.15, 6)
    wet = band(noise(0.3, r), 300, 900) * env(n, 0.02, 0.2, 2) * (0.6 + 0.4 * np.sin(2 * np.pi * 18 * t(0.3)))
    return mix(chop, wet * 0.5, at(SOUNDS["hit"][0]() * 0.3, 0.0))


@sound("drink", 0.5)
def _():
    parts = []
    for i, f in enumerate((180, 150, 200)):
        n = int(0.09 * RATE)
        parts.append(at(sine(np.linspace(f, f * 1.6, n), 0.09) * env(n, 0.005, 0.05, 3), 0.11 * i))
    return low(mix(*parts), 1500)


@sound("eat", 0.45)
def _():
    r = rng_for("eat")
    parts = [at(band(noise(0.05, r), 1200, 5000) * env(int(0.05 * RATE), 0.001, 0.03, 5), s) for s in (0, 0.13, 0.27)]
    return mix(*parts)


@sound("bandage", 0.4)
def _():
    r = rng_for("bandage")
    n = int(0.35 * RATE)
    x = noise(0.35, r)
    tear = band(x, 2000, 7000) * np.abs(np.sin(2 * np.pi * 30 * t(0.35))) * np.sin(np.linspace(0, np.pi, n))
    return tear


@sound("torch", 0.55)
def _():
    r = rng_for("torch")
    n = int(0.9 * RATE)
    whoosh = low(noise(0.9, r), 1200) * env(n, 0.02, 0.6, 3) * 0.7
    crackle = band((r.random(n) < 0.006) * r.uniform(-1, 1, n), 2000, 7000) * 3 * np.linspace(1, 0.3, n)
    return mix(whoosh, crackle)


@sound("artifact", 0.5)
def _():
    n = int(1.4 * RATE)
    tt = t(1.4)
    f = 523.3 * (1 + 0.03 * np.sin(2 * np.pi * 0.8 * tt))
    tone = sine(f, 1.4) * env(n, 0.05, 1.0, 1.5) * 0.5 + sine(f * 1.498, 1.4) * env(n, 0.1, 1.0, 2) * 0.3
    shimmer = high(noise(1.4, rng_for("artifact")), 5000) * env(n, 0.1, 1.0, 2) * 0.06
    return reverb(mix(tone, shimmer), 2.0, 0.4)


@sound("rope", 0.45)
def _():
    r = rng_for("rope")
    n = int(0.5 * RATE)
    zip_ = band(noise(0.5, r), 700, 3000) * (0.5 + 0.5 * np.sin(2 * np.pi * np.linspace(20, 60, n) * t(0.5))) * np.sin(np.linspace(0, np.pi, n))
    return zip_


@sound("stash", 0.5)
def _():
    r = rng_for("stash")
    n = int(0.5 * RATE)
    creak = band(noise(0.5, r), 300, 900) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 9 * t(0.5)))) * np.sin(np.linspace(0, np.pi, n)) * 0.5
    thunk = at(SOUNDS["step_wood_1"][0]() * 1.2, 0.42)
    return mix(creak, thunk)


# Moments: short tonal cues, no tunes (music is the user's).
@sound("wayfinder", 0.7)
def _():
    """Stepping into the Wayfinder: its hum swells, bends, and carries you off."""
    d = 2.8
    n = int(d * RATE)
    tt = t(d)
    rise = np.linspace(0, 1, n) ** 1.5
    hum = (sine(55 * (1 + 0.5 * rise ** 3), d) * 0.6 + sine(82.5 * (1 + 0.5 * rise ** 3), d) * 0.4
           + sine(220 * (1 + rise ** 2), d) * 0.15) * np.minimum(1, rise * 3) * np.linspace(1, 0.2, n)
    rush = band(noise(d, rng_for("wayfinder")), 400, 4000) * rise ** 3 * np.exp(-np.maximum(0, tt - 2.2) * 12)
    return reverb(mix(hum, rush * 0.6), 2.0, 0.4)


@sound("hunt_complete", 0.55)
def _():
    n = int(2.4 * RATE)
    e1 = env(n, 0.3, 1.0, 1.2)
    a = mix(*[sine(f, 2.4) * e1 * w for f, w in ((220.0, 0.5), (261.6, 0.35), (329.6, 0.3))])
    b = at(mix(*[sine(f, 2.0) * env(int(2.0 * RATE), 0.3, 1.0, 1.2) * w for f, w in ((196.0, 0.5), (293.7, 0.35), (392.0, 0.3))]), 0.9)
    return reverb(low(mix(a, b), 2500), 2.5, 0.4)


@sound("hunt_return", 0.45)
def _():
    n = int(1.8 * RATE)
    return reverb(low(mix(sine(196.0, 1.8) * 0.5, sine(233.1, 1.8) * 0.3) * env(n, 0.2, 1.2, 1.5), 1500), 1.8, 0.4)


@sound("bounty_done", 0.55)
def _():
    parts = [at(bell(f, 1.5, decay=2.5), s) for f, s in ((392.0, 0), (392.0, 0.25), (587.3, 0.5))]
    return reverb(mix(*parts), 1.8, 0.35)


@sound("record", 0.6)
def _():
    gong = bell(110, 3.0, partials=((1, 1), (1.48, 0.6), (2.3, 0.4), (3.9, 0.2)), decay=1.0)
    chimes = mix(*[at(bell(f, 1.2, decay=4) * 0.25, 0.3 + 0.1 * i) for i, f in enumerate((880, 1046.5, 1318.5))])
    return reverb(mix(gong, chimes), 2.5, 0.35)


@sound("pay", 0.45)
def _():
    return mix(SOUNDS["shards"][0](), at(SOUNDS["ui_confirm"][0]() * 0.5, 0.05))


# ---- Ambience: 16-second seamless loops -------------------------------------------------------
def miasma(n: int, seed: str) -> np.ndarray:
    """The miasma under every hunt: a low, uneasy, slowly beating drone, and stillness. No wind
    (v0.64.0, user: places in the miasma should be still). A faint, close hush, not a gust."""
    r = rng_for("miasma" + seed)
    d = n / RATE
    drone = (sine(41.25, d) + 0.8 * sine(41.5, d) + 0.35 * sine(61.875, d) + 0.2 * sine(62.25, d))
    hush = band(noise(d, r), 60, 160) * 0.08
    return drone * 0.12 + hush


def wind(n, r, lo=200, hi=1200, gust=0.15, depth=0.7):
    return band(r.standard_normal(n), lo, hi) * slow_lfo(n, r, gust, depth)


def sparse(n, r, every: float, make, jitter=0.5):
    """Events at random times, about one every `every` seconds."""
    out = np.zeros(n)
    s = r.uniform(0, every)
    while s < n / RATE:
        out = mix(out, at(make(r), s))[:n]
        s += every * r.uniform(1 - jitter, 1 + jitter)
    return out


def drip(r):
    f = r.uniform(900, 2200)
    d = 0.25
    k = sine(np.linspace(f * 0.7, f, int(d * RATE)), d) * env(int(d * RATE), 0.001, 0.2, 8)
    return reverb(k, 2.5, 0.6, bright=2500, seed="cave")


def chirp(r):
    f = r.uniform(1800, 3200)
    d = r.uniform(0.15, 0.3)
    n = int(d * RATE)
    return sine(np.linspace(f, f * r.uniform(0.7, 1.3), n), d) * np.sin(np.linspace(0, np.pi, n)) ** 2 * 0.25


def creak(r):
    d = r.uniform(0.4, 0.8)
    n = int(d * RATE)
    return band(r.standard_normal(n), 250, 700) * (0.3 + 0.7 * np.abs(np.sin(2 * np.pi * r.uniform(6, 12) * t(d)))) * np.sin(np.linspace(0, np.pi, n)) * 0.3


def pebbles(r):
    parts = [at(band(r.standard_normal(int(0.03 * RATE)), 1500, 5000) * env(int(0.03 * RATE), 0.001, 0.02, 4) * r.uniform(0.2, 0.5), s)
             for s in np.cumsum(r.uniform(0.04, 0.15, r.integers(3, 7)))]
    return reverb(mix(*parts), 1.0, 0.4)


def voices(n, r, k=10):
    """A crowd far off: many murmurs, none clear."""
    out = np.zeros(n)
    for i in range(k):
        f = r.uniform(250, 700)
        v = band(r.standard_normal(n), f, f * 1.7) * slow_lfo(n, r, r.uniform(0.6, 1.5), 0.95)
        out += v
    return out / k


def ambience(name: str, build) -> None:
    SOUNDS[name] = (build, 0.5)


def _city():
    r = rng_for("city")
    n = int((LOOP + 1.5) * RATE)
    steps = sparse(n, r, 0.9, lambda r: _step("stone", 300, 2000, 0.06, 0.4, 110, int(r.integers(3))) * r.uniform(0.15, 0.35), 0.6)
    cart = sparse(n, r, 7, lambda r: low(r.standard_normal(int(1.5 * RATE)), 300) * np.sin(np.linspace(0, np.pi, int(1.5 * RATE))) * 0.3)
    bell_far = at(low(bell(196, 4.0, decay=0.8), 1200) * 0.12, 5.0, n / RATE)
    return seamless(mix(voices(n, r) * 0.6, wind(n, r, 150, 900, 0.1, 0.5) * 0.25, steps, cart, bell_far))


def _interior():
    r = rng_for("interior")
    n = int((LOOP + 1.5) * RATE)
    muffled = low(_city_raw(n), 450) * 0.6
    room = low(r.standard_normal(n), 200) * 0.08
    return seamless(mix(muffled, room, sparse(n, r, 5, creak) * 0.4))


def _city_raw(n):
    r = rng_for("city")
    return voices(n, r) * 0.6 + wind(n, r, 150, 900, 0.1, 0.5) * 0.25


def _hall():
    r = rng_for("hall")
    n = int((LOOP + 1.5) * RATE)
    near = voices(n, r, 6) * 0.7
    hearth = band((r.random(n) < 0.003) * r.uniform(-1, 1, n), 1500, 6000) * 1.5 + low(r.standard_normal(n), 250) * 0.15
    clinks = sparse(n, r, 4.5, lambda r: bell(r.uniform(1500, 2500), 0.3, decay=12) * 0.12)
    return seamless(reverb(mix(near, hearth, clinks), 0.8, 0.25)[:n])


def _brisering():
    r = rng_for("brisering")
    n = int((LOOP + 1.5) * RATE)
    # Plain wind and grass. The Chorus Winds carry Jodebris, but almost no one can hear it
    # (lore: about 19 in 1.3 million), so neither does the Hunter.
    return seamless(mix(wind(n, r, 150, 900, 0.12, 0.7) * 0.8, wind(n, r, 2000, 6000, 0.3, 0.8) * 0.15))


def _caves():
    r = rng_for("caves")
    n = int((LOOP + 1.5) * RATE)
    rumble = low(r.standard_normal(n), 90) * slow_lfo(n, r, 0.1, 0.6) * 1.2
    return seamless(mix(miasma(n, "caves"), rumble, sparse(n, r, 2.2, drip) * 0.5, sparse(n, r, 9, pebbles) * 0.3))


def _forest():
    r = rng_for("forest")
    n = int((LOOP + 1.5) * RATE)
    # still air: no wind in the leaves; a strange bird now and then, a creak, a twig
    twig = lambda r: band(r.standard_normal(int(0.04 * RATE)), 800, 4000) * env(int(0.04 * RATE), 0.001, 0.03, 5) * 0.3
    return seamless(mix(miasma(n, "forest"), sparse(n, r, 5, chirp) * 0.4, sparse(n, r, 7, creak) * 0.3,
                        sparse(n, r, 6, twig)))


def _insects(n, r):
    out = np.zeros(n)
    for f in (4200, 5100, 3700):
        pulse = (np.sin(2 * np.pi * r.uniform(18, 30) * t(n / RATE)) > 0.3).astype(float)
        pulse = low(pulse, 120)
        out += sine(f, n / RATE) * pulse * slow_lfo(n, r, 0.3, 0.9) * 0.05
    return out


def _forest_night():
    r = rng_for("forest_night")
    n = int((LOOP + 1.5) * RATE)
    return seamless(mix(miasma(n, "forest_night"), _insects(n, r), sparse(n, r, 6, creak) * 0.4))


def _ruins():
    r = rng_for("ruins")
    n = int((LOOP + 1.5) * RATE)
    # still, hollow stone: settling creaks, a trickle of grit, a drip in some dark corner
    return seamless(mix(miasma(n, "ruins"), sparse(n, r, 5, creak) * 0.5, sparse(n, r, 6, pebbles) * 0.4,
                        sparse(n, r, 5, drip) * 0.25))


def _mountains():
    r = rng_for("mountains")
    n = int((LOOP + 1.5) * RATE)
    # no howling wind: a deep rumble far off in the rock, scree trickling, a stone falling
    rumble = low(r.standard_normal(n), 70) * slow_lfo(n, r, 0.08, 0.7)
    fall = lambda r: reverb(low(r.standard_normal(int(0.2 * RATE)), 900) * env(int(0.2 * RATE), 0.002, 0.15, 3) * 0.4,
                            2.0, 0.5, bright=1500, seed="mountain")
    return seamless(mix(miasma(n, "mountains"), rumble * 0.8, sparse(n, r, 4, pebbles) * 0.5, sparse(n, r, 9, fall)))


def _plains():
    r = rng_for("plains")
    n = int((LOOP + 1.5) * RATE)
    # open and still: a far bird, a faint buzz of insects in the grass
    return seamless(mix(miasma(n, "plains"), sparse(n, r, 6, chirp) * 0.35, _insects(n, r) * 0.25))


def _plains_night():
    r = rng_for("plains_night")
    n = int((LOOP + 1.5) * RATE)
    return seamless(mix(miasma(n, "plains_night"), _insects(n, r) * 0.8))


def _wayfinder_hum():
    """The Wayfinder, heard as you come near it in the plaza (my design: the user left it to me).
    A low hum on two tones a fifth apart, slowly beating, with faint glassy overtones that
    drift. Every frequency is a whole number of cycles in 16 s, so it loops exactly."""
    d = LOOP
    k = lambda f: round(f * d) / d
    tt = t(d)
    hum = (np.sin(2 * np.pi * k(55) * tt) + 0.7 * np.sin(2 * np.pi * k(55.25) * tt)
           + 0.5 * np.sin(2 * np.pi * k(82.5) * tt) + 0.3 * np.sin(2 * np.pi * k(110.0625) * tt))
    over = sum(np.sin(2 * np.pi * k(f) * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * k(m) * tt + p)) * 0.05
               for f, m, p in ((880, 0.0625, 0), (1320, 0.125, 1.3), (1650, 0.1875, 2.6)))
    return hum * 0.5 + over


for _name, _fn in (("amb_city", _city), ("amb_interior", _interior), ("amb_hall", _hall), ("amb_brisering", _brisering),
                   ("amb_caves", _caves), ("amb_forest", _forest), ("amb_forest_night", _forest_night),
                   ("amb_ruins", _ruins), ("amb_mountains", _mountains), ("amb_plains", _plains),
                   ("amb_plains_night", _plains_night), ("loop_wayfinder", _wayfinder_hum)):
    ambience(_name, _fn)


def main(names: list[str]) -> None:
    todo = names or list(SOUNDS)
    for name in todo:
        fn, peak = SOUNDS[name]
        x = fn()
        write(name, x, peak)
        print(f"{name:20} {len(x) / RATE:5.2f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
