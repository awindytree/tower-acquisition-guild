"""Summarise one or more sim.py results as a Markdown report.

    python tools/balance/report.py simA.json simB.json > report.md
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter, defaultdict

REGIONS = [f"danger {d}" for d in range(1, 6)]   # (v0.44.0: hunts grouped by danger, not gate region)


def pct(n, d):
    return f"{100 * n / d:.0f}%" if d else "-"


def med(xs):
    return st.median(xs) if xs else 0


def mean(xs):
    return st.mean(xs) if xs else 0


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main(paths):
    hunters = []
    for p in paths:
        hunters += json.load(open(p))["hunters"]
    hunts = [h for c in hunters for h in c["hunts"]]
    out = [f"# Balance simulation: {len(hunters)} Hunters, {len(hunts)} hunts", ""]

    # ---- Careers
    died = [c for c in hunters if c["end"]["died"]]
    lengths = [len(c["hunts"]) for c in hunters]
    peak = [max([c["start"]["level"]] + [h.get("level1", h["level"]) for h in c["hunts"]]) for c in hunters]
    out += ["## Careers", "",
            f"- Died: {len(died)} of {len(hunters)} ({pct(len(died), len(hunters))}); "
            f"stuck owing dues: {sum(1 for c in hunters if 'stuck_owing' in c)}.",
            f"- Hunts per career: median {med(lengths)}, mean {mean(lengths):.1f}.",
            f"- Died on their first hunt: {sum(1 for c in died if len(c['hunts']) == 1)}; "
            f"within 3 hunts: {sum(1 for c in died if len(c['hunts']) <= 3)}.",
            "- Peak level reached: " + ", ".join(f"{lv}: {n}" for lv, n in sorted(Counter(peak).items())) + ".", ""]
    # first weapon vs early death
    by_kit = defaultdict(lambda: [0, 0])
    for c in hunters:
        w = c["start"]["weapon"]
        by_kit[w][0] += 1
        by_kit[w][1] += 1 if c["end"]["died"] and len(c["hunts"]) <= 3 else 0
    out += ["Early deaths (within 3 hunts) by starting weapon:", "",
            table(["weapon", "Hunters", "died early"], [(w, n, f"{d} ({pct(d, n)})") for w, (n, d) in sorted(by_kit.items())]), ""]

    # ---- Per region
    rows = []
    for r in REGIONS:
        hs = [h for h in hunts if h["region"] == r]
        if not hs:
            continue
        oc = Counter(h["outcome"] for h in hs)
        rows.append([r, len(hs), f"{med([h['level'] for h in hs])}", pct(oc["success"], len(hs)), pct(oc["abandoned"], len(hs)),
                     pct(oc["stuck"], len(hs)), pct(oc["died"], len(hs)),
                     f"{mean([h['faints'] for h in hs]):.2f}", f"{med([h['turns'] for h in hs]):.0f}",
                     f"{mean([sum(h['kills'].values()) for h in hs if h['outcome'] != 'died']):.1f}",
                     f"{mean([h.get('xp', 0) for h in hs if h['outcome'] != 'died']):.0f}",
                     f"{mean([len(h['injuries']) for h in hs if h['outcome'] != 'died']):.2f}"])
    out += ["## Hunts by danger", "",
            table(["region", "hunts", "median level", "success", "turned back", "stuck", "died", "faints/hunt",
                   "turns", "kills", "XP", "injuries"], rows), ""]

    # ---- Levels over time
    by_n = defaultdict(list)
    for c in hunters:
        for h in c["hunts"]:
            if "level1" in h:
                by_n[h["n"]].append(h["level1"])
    out += ["## Level after hunt N (survivors)", "",
            table(["hunt"] + [str(n + 1) for n in sorted(by_n) if n % 3 == 0 or n < 3],
                  [["median level"] + [str(med(by_n[n])) for n in sorted(by_n) if n % 3 == 0 or n < 3],
                   ["Hunters"] + [str(len(by_n[n])) for n in sorted(by_n) if n % 3 == 0 or n < 3]]), ""]

    # ---- Economy per hunt, by danger
    inc_keys = ["found", "artifacts", "materials", "gear", "writings", "notes"]
    cost_keys = ["supplies", "dues", "healer", "gear", "rank"]
    rows = []
    for r in REGIONS:
        hs = [h for h in hunts if h["region"] == r and h["outcome"] != "died"]
        if not hs:
            continue
        inc = {k: mean([h["income"][k] for h in hs]) for k in inc_keys}
        cost = {k: mean([h["costs"].get(k, 0) for h in hs]) for k in cost_keys}
        rows.append([r] + [f"{inc[k]:.0f}" for k in inc_keys] + [f"{sum(inc.values()):.0f}"]
                    + [f"{cost[k]:.0f}" for k in cost_keys] + [f"{sum(inc.values()) - sum(cost.values()):+.0f}"])
    out += ["## Shards per hunt (mean, survivors), by danger", "",
            table(["region"] + [f"in: {k}" for k in inc_keys] + ["in total"] + [f"out: {k}" for k in cost_keys] + ["net"], rows),
            "", "(\"found\" is shards picked up on the hunt; \"gear\" in is spare gear sold, out is upgrades bought.)", ""]
    purse = defaultdict(list)
    for c in hunters:
        for h in c["hunts"]:
            if "shards1" in h:
                purse[h["n"]].append(h["shards1"])
    out += ["Purse after hunt N (median, survivors): " + ", ".join(
        f"{n + 1}: {med(purse[n])}" for n in sorted(purse) if n % 3 == 0 or n < 3) + ".", ""]

    # ---- Supplies
    used = defaultdict(list)
    for h in hunts:
        for k in ("healing_draught", "ration", "bandage", "torch", "poultice", "healing_tonic"):
            used[(h["region"], k)].append(h["used"].get(k, 0))
    out += ["## Supplies used per hunt (mean)", "",
            table(["region", "draughts", "rations", "bandages", "torches", "poultices"],
                  [[r] + [f"{mean(used[(r, k)]):.1f}" for k in ("healing_draught", "ration", "bandage", "torch", "poultice")]
                   for r in REGIONS if used[(r, "ration")]]), ""]

    # ---- Artifacts and gear
    arts = defaultdict(Counter)
    for h in hunts:
        for a in h["artifacts"]:
            arts[h["danger"]][a] += 1
    out += ["## Artifacts brought home, by contract danger", "",
            table(["danger", "artifacts"], [(d, ", ".join(f"{k} {v}" for k, v in c.most_common())) for d, c in sorted(arts.items())]), ""]
    bought = Counter(b for h in hunts for b in h["bought"])
    out += ["Gear the bot could afford to buy: " + (", ".join(f"{k} ×{v}" for k, v in bought.most_common()) or "none") + ".", ""]
    inj = Counter(i.split(" with ")[-1].split("!")[0] for h in hunts for i in h["injuries"])
    out += ["Injuries suffered (all hunts): " + (", ".join(f"{k} {v}" for k, v in inj.most_common()) or "none") + ".", ""]
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1:])
