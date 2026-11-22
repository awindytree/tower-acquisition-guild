"""Limited, persistent stock for shops and workshops.

Each vendor (a shop or a workshop) has a Stock: the things it sells, how many
it has, and the price. It's world state: saved with the city, kept when a
Hunter dies, reset only by a new game.

Regular lines come from the data files: each has a maximum and restocks one
unit every `restock` Pulses until it's back to that maximum. Things a Hunter
sells to the vendor (or consigns, at a workshop) are added as extra lines:
for sale at their full value until someone buys them, never restocked.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StockLine:
    item_id: str
    price: int
    count: int
    max: int = 0          # 0 = an extra line (something sold to the vendor): never restocked
    restock: int = 0      # Pulses per unit restocked
    since: int = 0        # the day the restock clock last started
    bundle: int = 1       # how many you get for one purchase (arrows come in bundles)
    tier: int = 0         # a weapon or armour piece sold at a tier (v0.76.0): it's sold back at that tier

    def catch_up(self, day: int) -> None:
        """Restock for the Pulses that have passed."""
        if self.max <= 0 or self.restock <= 0:
            return
        if self.count >= self.max:
            self.since = day
            return
        units = (day - self.since) // self.restock
        if units > 0:
            self.count = min(self.max, self.count + units)
            self.since = day if self.count >= self.max else self.since + units * self.restock


class Stock:
    def __init__(self, lines: list[StockLine]) -> None:
        self.lines = lines

    @classmethod
    def from_data(cls, entries, catalogue, day: int = 1) -> "Stock":
        """Stock entries from shops.json / workshops.json. Each is an item id, [id, price],
        or {"id", "price", "max", "restock", "bundle"}. Defaults: price = the item's value, max 3,
        restock 9, bundle 1. With a bundle, count and price are per bundle."""
        lines = []
        for e in entries:
            if isinstance(e, str):
                e = {"id": e}
            elif isinstance(e, list):
                e = {"id": e[0], "price": e[1]}
            t = catalogue[e["id"]]
            m = e.get("max", 3)
            lines.append(StockLine(t.id, e.get("price", t.value), m, m, e.get("restock", 9), day,
                                   e.get("bundle", 1)))
        return cls(lines)

    def catch_up(self, day: int) -> None:
        for line in self.lines:
            line.catch_up(day)

    def shown(self) -> list[StockLine]:
        """Lines to list: every regular line (sold out or not) and extra lines with something left."""
        return [l for l in self.lines if l.max > 0 or l.count > 0]

    def take(self, line: StockLine, day: int) -> None:
        if line.max > 0 and line.count >= line.max:
            line.since = day  # the restock clock starts when it's no longer full
        line.count -= 1
        if line.max <= 0 and line.count <= 0:
            self.lines.remove(line)

    def add(self, item_id: str, price: int, tier: int = 0) -> None:
        """Something sold (or consigned) to the vendor goes up for sale at full value (and its tier)."""
        for line in self.lines:
            if line.item_id == item_id and line.max <= 0 and line.price == price and line.tier == tier:
                line.count += 1
                return
        self.lines.append(StockLine(item_id, price, 1, tier=tier))

    def to_list(self) -> list:
        return [[l.item_id, l.price, l.count, l.max, l.restock, l.since, l.bundle] + ([l.tier] if l.tier else [])
                for l in self.lines]

    @classmethod
    def from_list(cls, data: list) -> "Stock":
        return cls([StockLine(*entry) for entry in data])
