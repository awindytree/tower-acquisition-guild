"""Shops: what they sell and buy, and the trading itself.

Shops are defined in data/shops.json and staffed by shopkeepers (NPCs placed
in map files). Stock is limited and persistent (game/stock.py; the engine
keeps it as world state). Trading takes no game time.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from game.items import Catalogue, Item, ItemType

NEVER_BOUGHT = ("artifact", "key")  # not for sale to shops, whatever a shop says


@dataclass(frozen=True)
class Shop:
    id: str
    name: str
    keeper: str
    greeting: str
    stock: tuple                               # stock entries from the data file (see game/stock.py)
    buys: tuple[str, ...]                      # item kinds the shop buys
    sell_rate: float

    def buy_price(self, item_type: ItemType, value: int | None = None) -> int | None:
        """What the shop pays for one of these (worth `value`, if not the type's), or None if it won't
        buy them."""
        if item_type.kind in NEVER_BOUGHT or item_type.kind not in self.buys or item_type.id == "shard":
            return None
        return max(1, int((item_type.value if value is None else value) * self.sell_rate))


def load_shops(path: str | Path, catalogue: Catalogue) -> dict[str, Shop]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    shops = {}
    for sid, d in raw.items():
        if sid.startswith("_"):
            continue
        for entry in d["stock"]:  # check every id now, not on first visit
            catalogue[entry if isinstance(entry, str) else entry["id"] if isinstance(entry, dict) else entry[0]]
        stock = d["stock"]
        shops[sid] = Shop(sid, d["name"], d.get("keeper", "the shopkeeper"), d.get("greeting", ""),
                          tuple(stock), tuple(d.get("buys", ())), d.get("sell_rate", 0.5))
    return shops


# ---- Trading: each returns a message for the log, and changes nothing if it fails ----
def buy(player, item_type: ItemType, price: int, count: int = 1, tier: int = 0) -> tuple[bool, str]:
    """Buy `count` of something (a bundle) for `price` in all (a piece at a tier: `tier`)."""
    what = item_type.label(count) if count > 1 else item_type.name + (f" +{tier}" if tier else "")
    if player.shards < price:
        return False, f"You can't afford the {what} ({price} shards)."
    if not player.inventory.can_add(Item(item_type, count)):
        return False, f"You have no room to carry the {what}."
    player.inventory.add(Item(item_type, count, tier=tier))
    player.shards -= price
    from game import sound
    sound.play("pay")
    bought = what if count > 1 else _a(item_type.name)
    return True, f"You buy {bought} for {price} shard{'s' if price != 1 else ''}."


def sell(player, shop: Shop, index: int, stock=None) -> tuple[bool, str]:
    """Sell one. If the shop's stock is given, the item goes up for sale there at full value."""
    item = player.inventory.items[index]
    from game import gear
    price = shop.buy_price(item.type, gear.value(item))
    if price is not None:
        from game import bargaining                 # (v0.59.0)
        price = bargaining.paid(player, price)
    if price is None:
        reason = f"{shop.keeper.capitalize()} doesn't deal in artifacts. Try an Artificer's workshop." if item.type.kind == "artifact" else \
                 f"{shop.keeper.capitalize()} doesn't buy that."
        return False, reason
    if player.is_equipped(item):
        return False, f"Take off the {item.type.name} before selling it."
    player.inventory.remove(index, 1)
    player.earn(price)
    from game import sound
    sound.play("pay")
    if stock is not None:
        stock.add(item.type.id, gear.value(item), item.tier)
    return True, f"You sell {_a(item.label)} for {price} shard{'s' if price != 1 else ''}."


def _a(name: str) -> str:
    return ("an " if name[0] in "aeiou" else "a ") + name
