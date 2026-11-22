"""One Hunter against one creature, many times over (equipment stage 6, v0.80.0).

Compares weapons (and tiers and skill ranks) with the real rules: a Hunter of a level that suits the
creature's tier stands on open ground in a hunt area; the creature starts awake, 4 cells away in a
straight line, and comes on. The Hunter shoots while it can (winding a crossbow when it must), strikes
at reach with a whip or polearm, readies its rank-5 technique whenever it can, and otherwise waits for
the creature to come and fights it. A fight ends when one of them drops (or after 200 turns).

    python tools/balance/duels.py --fights 200 --out duels.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim   # (its stand-in for tcod, and make_engine)

from game import ranged, weaponskills as ws, injuries
from game.actions import MoveAction, WaitAction, FireAction, ReloadAction
from game.items import Item
from game.monsters import Monster

WEAPONS = ["(bare hands)", "studded_gloves", "short_sword", "arming_sword", "hand_axe", "war_pick", "hunting_knife",
           "iron_claws", "quarterstaff", "leather_whip", "boar_spear", "short_bow", "longbow", "light_crossbow"]
CREATURES = {"wild_dog": 1, "thornback_boar": 3, "crawler": 5, "hollow_brute": 7}   # creature -> Hunter level
ARMOUR = {1: ["leather_jerkin"], 3: ["studded_jerkin", "leather_cap"], 5: ["mail_shirt", "leather_cap", "hide_leggings"],
          7: ["mail_shirt", "iron_helm", "iron_greaves"]}


def arena(e):
    """A hunt area with a clear straight run of 8 cells east, and room around it."""
    place = e.regions["quiet/green/daybreak"]
    e.set_out(tuple(place.place))
    e.screen = None
    gm = e.game_map
    for y in range(3, gm.height - 3):
        for x in range(3, gm.width - 12):
            if all(gm.is_walkable(x + dx, y + dy) and gm.transparent[x + dx, y + dy] and gm.tile_at(x + dx, y + dy).symbol not in "<>H"
                   for dx in range(-1, 9) for dy in (-1, 0, 1)):
                return x, y
    raise SystemExit("no open ground")


def fight(e, spot, weapon_id, tier, rank, creature, level, seed) -> dict:
    p, gm = e.player, e.game_map
    rng = random.Random(seed)
    e.rng = rng
    random.seed(seed)
    gm.monsters.clear()
    gm.items[:] = [f for f in gm.items if f.item.type.kind != "consumable"]
    p.x, p.y = spot
    p.injuries.clear()
    p.stats.level = level
    p.stats.gain_xp = lambda n: False          # (no levelling up, and its full heal, mid-fight)
    p.equipped.clear()
    p.inventory.items = [it for it in p.inventory.items if it.type.kind not in ("weapon", "armor")]
    for aid in ARMOUR[level]:
        p.equip(Item(e.catalogue[aid]))
    if weapon_id != "(bare hands)":
        p.equip(Item(e.catalogue[weapon_id], tier=tier))
    p.inventory.items = [it for it in p.inventory.items if it.type.kind not in ("weapon", "armor", "consumable")]
    w = p.equipped.get("weapon")
    if w is not None and w.type.properties.get("ammo"):
        p.inventory.add(Item(e.catalogue[w.type.properties["ammo"]], 30))
    for sid in set(ws.MELEE_SKILLS) | set(ws.RANGED_SKILLS):
        st = p.skill(sid)
        st.rank, st.practice = rank, 0
    p.readied, p.tech_rest, p.frenzy, p.unloaded, p.dazed = None, 0, 0, False, 0
    injuries.apply_to_stats(p)
    p.stats.hp = p.stats.max_hp
    hp0 = p.stats.hp
    m = Monster.spawn(e.monster_types[creature], spot[0] + 4, spot[1])
    m.awake = True
    gm.monsters.append(m)
    down = {"lost": False}
    e.player_down = lambda *a, **k: down.__setitem__("lost", True)
    turns = 0
    while turns < 200 and m in gm.monsters and not down["lost"]:
        e.update_fov()
        if rank >= ws.ACTIVE_RANK and not p.readied and p.tech_rest == 0 and ws.weapon_skill(p) in ws.TECHNIQUES:
            ws.ready(e)
        dist = abs(m.x - p.x) + abs(m.y - p.y)
        bow = ranged.bow(p)
        if bow is not None and dist > 1 and ranged.can_fire(e) is None and ranged.in_range(e, m.x, m.y):
            action = ReloadAction() if p.unloaded and bow.type.properties.get("reload") else FireAction(m.x, m.y)
        elif dist == 1 or (bow is None and ws.in_reach(e, m)):
            sx, sy = (m.x > p.x) - (m.x < p.x), (m.y > p.y) - (m.y < p.y)
            action = MoveAction(sx, sy)
        else:
            action = WaitAction()
        t0 = e.turn
        e.handle_action(action)
        turns += 1 if e.turn == t0 else e.turn - t0
    won = m not in gm.monsters and not down["lost"]
    return {"won": won, "turns": turns, "hp_lost": (hp0 - max(0, p.stats.hp)) / hp0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fights", type=int, default=100)
    ap.add_argument("--out", default="duels.json")
    ap.add_argument("--weapons", default=",".join(WEAPONS))
    ap.add_argument("--ranks", default="1,3,5")
    ap.add_argument("--tiers", default="0")
    a = ap.parse_args()
    e = sim.make_engine(1)
    spot = arena(e)
    rows = []
    t0 = time.time()
    for wid in a.weapons.split(","):
        for tier in map(int, a.tiers.split(",")):
            for rank in map(int, a.ranks.split(",")):
                for creature, level in CREATURES.items():
                    res = [fight(e, spot, wid, tier, rank, creature, level, s) for s in range(a.fights)]
                    row = {"weapon": wid, "tier": tier, "rank": rank, "creature": creature, "level": level,
                           "win": sum(r["won"] for r in res) / len(res),
                           "turns": sum(r["turns"] for r in res) / len(res),
                           "hp_lost": sum(r["hp_lost"] for r in res) / len(res)}
                    rows.append(row)
                    print(f"{wid:16} +{tier:<2} r{rank} {creature:15} win {row['win']:.0%}  turns {row['turns']:.1f}  "
                          f"hp lost {row['hp_lost']:.0%}", flush=True)
    Path(a.out).write_text(json.dumps({"rows": rows, "seconds": round(time.time() - t0)}), encoding="utf-8")


if __name__ == "__main__":
    main()
