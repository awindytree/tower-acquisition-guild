"""The hunt line (user, v0.71.0): one row across the top of the map view on a hunt.

    ≡ ═════♦═════♦─────♦───── ☼ M        / ██████░░░░

- The trail home (≡), then one segment per area, split by shards (♦) like the title cards'
  accents. Segments fill (═, lit) up to the area you're in; an area you've been deeper than and
  come back from stays filled but half-lit; the rest are a thin dark line (─). A shard lights once you've crossed into the area beyond it.
- At the end, what you came for: the prize (its own glyph and colour, dim until it's in your
  pack, bright once it is), then a mark for each bounty here (dim until done).
- On the right, while a torch burns: its glyph and a bar that burns down (the info panel no
  longer shows torch turns). The Jodebris bar stays in the panel.
"""
from __future__ import annotations

ROWS = 1                          # rows the line takes off the top of the map view on a hunt
LIT = (240, 160, 80)             # the accent orange
HALF = (150, 104, 62)
UNLIT = (64, 58, 52)
SHARD = (150, 220, 210)
TORCH = (240, 150, 70)
TORCH_LOW = (240, 120, 40)
GONE = (70, 64, 58)
BG = (14, 12, 11)
TORCH_W = 12                     # "/" + space + 10 cells of bar


def dim(color, f=0.4):
    return tuple(int(c * f) for c in color)


def reached(engine) -> int:
    """How many areas you've been into (1 = only the first)."""
    hunt = engine.hunt
    return max((i + 1 for i, a in enumerate(hunt.areas) if a is not None), default=1)


def prize_marks(engine) -> list[tuple[str, tuple]]:
    """(glyph, colour) for what you came for, then each bounty."""
    hunt, p = engine.hunt, engine.player
    c = hunt.contract
    out = []
    if c.artifact_id and c.artifact_id in engine.catalogue.types:
        t = engine.catalogue[c.artifact_id]
        have = any(it.type.id == t.id for it in p.all_items())
        out.append((t.glyph, tuple(t.color) if have else dim(t.color)))
    for job_id, kind, want in getattr(hunt, "bounties", []):
        job = next((j for j in p.jobs if j.id == job_id), None)
        done = bool(job and job.done)
        if kind == "kill" and want in engine.monster_types:
            m = engine.monster_types[want]
            out.append((m.glyph, (230, 190, 90) if done else dim((230, 190, 90))))
        elif want in engine.catalogue.types:
            t = engine.catalogue[want]
            have = done or any(it.type.id == t.id for it in p.inventory.items)
            out.append((t.glyph, tuple(t.color) if have else dim(t.color)))
    return out


def torch_share(engine) -> float:
    from game import fieldskills
    p = engine.player
    if not p.torch_turns:
        return 0.0
    base = engine.catalogue["torch"].properties.get("burn_turns", 300) if "torch" in engine.catalogue.types else 300
    full = max(p.torch_turns, fieldskills.torch_turns(p, base))
    return p.torch_turns / full


def draw(engine, console, view_w: int) -> None:
    hunt = engine.hunt
    if hunt is None:
        return
    console.rgb["bg"][0:view_w, 0:ROWS] = BG
    console.rgb["ch"][0:view_w, 0:ROWS] = ord(" ")
    n = hunt.contract.depth
    here = hunt.current + 1
    deepest = reached(engine)
    marks = prize_marks(engine)
    right = TORCH_W + 2
    x = 1
    console.print(x, 0, "≡", fg=(250, 215, 120), bg=BG)          # the trail home
    x += 2
    room = view_w - x - (2 * len(marks) + 1) - right - 1
    seg = max(2, (room - (n - 1)) // n)
    for i in range(n):
        color = LIT if i < here else HALF if i < deepest else UNLIT
        console.print(x, 0, ("═" if i < deepest else "─") * seg, fg=color, bg=BG)   # (reached: a full line)
        x += seg
        if i < n - 1:
            console.print(x, 0, "♦", fg=SHARD if i + 1 < deepest else UNLIT, bg=BG)
            x += 1
    x += 1
    for glyph, color in marks:
        console.print(x, 0, glyph, fg=color, bg=BG)
        x += 2
    share = torch_share(engine)
    if share > 0:
        tx = view_w - TORCH_W - 1
        fill = max(1, round(share * 10))
        low = engine.player.torch_turns <= 25
        console.print(tx, 0, "/", fg=TORCH, bg=BG)
        console.print(tx + 2, 0, "█" * fill, fg=TORCH_LOW if low else TORCH, bg=BG)
        console.print(tx + 2 + fill, 0, "░" * (10 - fill), fg=GONE, bg=BG)
