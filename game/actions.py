"""Actions are the only way the game world changes.

Input produces an Action; the Engine performs it. perform() returns True if
the action used up a turn. Bumping a wall returns False, so it costs nothing.

Later, monsters will choose Actions too, which keeps the player and monsters
on exactly the same rules.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.engine import Engine


class Action:
    def perform(self, engine: "Engine") -> bool:
        raise NotImplementedError


class QuitAction(Action):
    """Save and quit (also what closing the window does)."""

    def perform(self, engine: "Engine") -> bool:
        engine.autosave()
        raise SystemExit()


class WaitAction(Action):
    def perform(self, engine: "Engine") -> bool:
        engine.log("You wait.")
        return True


class MoveAction(Action):
    def __init__(self, dx: int, dy: int) -> None:
        self.dx = dx
        self.dy = dy

    def perform(self, engine: "Engine") -> bool:
        player = engine.player
        nx, ny = player.x + self.dx, player.y + self.dy
        monster = engine.game_map.monster_at(nx, ny)
        if monster:
            return AttackAction(monster).perform(engine)
        npc = engine.game_map.npc_at(nx, ny)
        if npc:
            engine.talk_to(npc)
            return False  # talking and trading take no time
        folk = engine.game_map.windows.get((nx, ny))
        if folk:                                    # a service window: talk to whoever's behind it
            behind = next((n for n in engine.game_map.npcs if n.folk_id == folk), None)
            if behind:
                engine.talk_to(behind)
            else:
                engine.log("There's no one at the window just now.")
            return False
        tile = engine.game_map.tile_at(nx, ny)
        if tile.symbol == "L":                      # the plaque: who paid for the Guild's works
            from game import works
            from game.screens import ScrollScreen
            engine.screen = ScrollScreen.of_lines("The plaque", works.plaque_lines(engine))
            return False
        if tile.symbol == "D":                      # the trophy wall (v0.61.0): the records
            from game import trophies
            from game.screens import ScrollScreen
            engine.screen = ScrollScreen.of_lines("The trophy wall", trophies.wall_lines(engine))
            return False
        if tile.symbol == "C":
            from game import sound
            sound.play("stash")
            from game.screens import StashScreen
            engine.screen = StashScreen()
            return False  # rummaging in the stash takes no time
        if tile.symbol == "N":
            from game.screens import RequestBoardScreen
            from game import work
            engine.screen = RequestBoardScreen()
            work.reveal(engine, engine.requests)     # errands name places: you learn their words
            return False  # reading takes no time
        if tile.symbol == "P":
            engine.open_contracts()
            return False  # reading takes no time
        if tile.symbol == "J":
            engine.open_vendor("jobs")
            return False
        if tile.symbol == "Y":
            engine.city_return = (player.x, player.y)
            engine.open_artifact()
            return False  # choosing takes no time

        if not tile.walkable:
            from game import sound
            sound.play("bump", gap=0.4)
            place = engine.game_map.landmarks.get((nx, ny))
            if place:      # a village on the Brisering (lore, user): not open yet
                engine.log(f"{place}. You can't go in yet.")
            else:
                engine.log(f"The {tile.name} blocks your way.")
            return False

        from_x, from_y = player.x, player.y
        player.move(self.dx, self.dy)
        from game import sound
        sound.step(tile.symbol, walking=engine.walking is not None)
        here = engine.game_map.items_at(nx, ny)
        if len(here) == 1:
            engine.log(f"You see {article(here[0].item.floor_label)} here.")
        elif here:
            engine.log("Several things lie here.")
        engine.on_step(from_x, from_y)
        return True


class PickUpAction(Action):
    """Pick up everything here that fits. Shards go straight into the purse.
    A corpse is only picked up when there's nothing else here: it's the Hunter's choice whether
    to haul one (user, v0.61.0), so g with things and a corpse here takes the things first."""

    def perform(self, engine: "Engine") -> bool:
        player, gm = engine.player, engine.game_map
        here = gm.items_at(player.x, player.y)
        if not here:
            engine.log("There's nothing here to pick up.")
            return False
        took_any = False
        loose = [f for f in here if f.item.trophy is None]
        if loose:
            here = loose
        else:
            here = here[-1:]                       # one corpse at a time
        for floor_item in here:
            item = floor_item.item
            if item.trophy is not None:
                if player.inventory.add(item):
                    from game import sound
                    sound.play("pickup")
                    big = " onto your back" if item.slots >= 4 else ""
                    engine.log(f"You heave the {item.floor_label}{big}. In your pack: {article(item.label)}, "
                               f"{item.slots} slot{'s' if item.slots > 1 else ''}.")
                    gm.items.remove(floor_item)
                    return True
                engine.log(f"The {item.floor_label} needs {item.slots} slot{'s' if item.slots > 1 else ''}; "
                           f"you have {max(0, player.inventory.capacity - player.inventory.used)} free. "
                           "You could butcher it here (b).")
                return False
            if item.type.id == "shard":
                from game import talents        # (Lucky: shards found are worth more)
                player.earn(round(item.count * (1 + talents.total(player, "shards_found") / 100)))
                from game import sound
                sound.play("shards")
                engine.log(f"You pocket {article(item.label)}.")
            elif player.inventory.add(item):
                engine.log(f"You pick up {article(item.label)}.")
                from game import sound
                sound.play("pickup", gap=0.1)
                if engine.hunt and item.type.id == engine.hunt.contract.artifact_id:
                    engine.log(f"This is what you came for. Now get the {item.type.name} home.")
                from game import rivals, story
                rivals.on_pickup(engine, item.type.id)
                from game import work
                work.on_pickup(engine, item.type.id)
                story.fire(engine, "pickup", item=item.type.id)
            else:
                engine.log(f"You have no room for {article(item.label)}.")
                continue
            gm.items.remove(floor_item)
            took_any = True
        return took_any


class DropAction(Action):
    def __init__(self, index: int) -> None:
        self.index = index

    def perform(self, engine: "Engine") -> bool:
        from game.items import FloorItem

        player = engine.player
        player.unequip(player.inventory.items[self.index])
        item = player.inventory.remove(self.index)
        engine.game_map.items.append(FloorItem(player.x, player.y, item))
        engine.log(f"You drop {article(item.label)}.")
        return True


def article(label: str) -> str:
    """'short sword' -> 'a short sword'; '3 rations' stays as it is."""
    if label[0].isdigit():
        return label
    return ("an " if label[0] in "aeiou" else "a ") + label


class AttackAction(Action):
    """The player attacks a creature (by walking into it)."""

    def __init__(self, target) -> None:
        self.target = target

    def perform(self, engine: "Engine") -> bool:
        from game import combat

        target, player = self.target, engine.player
        player.note_weapon_use()
        name = target.name
        if target.type.ghost:              # (v0.49.0) nothing touches an ashmantle
            engine.log(f"Your blow passes through the {name} like smoke.")
            return True
        if target.burrowed:
            engine.log(f"The {name} is under the ground: your blow strikes only gravel.")
            return True
        from game import weaponskills as ws
        skill = ws.melee_skill(player)
        tech = None
        if player.readied:                 # a readied technique, if it's this weapon's (game/weaponskills.py)
            if skill in ws.TECHNIQUES and ws.technique(skill, "active")[0] == player.readied:
                tech = ws.spend(player)
            else:
                player.readied = None
        quick = ws.has_passive(player, "brawling") and not target.touched  # Quick hands: no time
        target.touched = True
        accuracy, rolls = (ws.LUNGE_ACCURACY, 2) if tech == "Lunge" else (0, 1)
        from game import talents
        if player.vengeance:                       # Vengeful (talent)
            accuracy += talents.total(player, "after_hit_accuracy")
            player.vengeance = False
        if talents.total(player, "solo_accuracy") and engine.visible is not None:      # Duelist
            if sum(1 for m in engine.game_map.monsters if engine.visible[m.x, m.y]) == 1:
                accuracy += talents.total(player, "solo_accuracy")
        from game import fieldskills
        sneak_acc, sneak_dmg = fieldskills.sneak_bonus(engine, target)   # it hasn't noticed you (Stealth)
        from game import mastery
        prey_acc, prey_dmg = mastery.prey_bonus(player, target)        # knowing your prey (v0.59.0)
        result = combat.resolve(player, target, accuracy=accuracy + sneak_acc + prey_acc, rolls=rolls,
                                damage=sneak_dmg + prey_dmg)
        ws.practise(engine, result.hit)
        if not getattr(target, "awake", True):
            if result.hit:
                fieldskills.practise(engine, "stealth")
                engine.log(f"The {name} never saw you coming.")
            target.awake, target.turns_unseen = True, 0
        how = f"Your {tech} " if tech else ""
        from game import sound
        if tech:
            sound.play("technique")
        if not result.hit:
            sound.play("miss")
        elif not result.killed:
            sound.play("crit" if result.crit else "hit")     # (a kill has its own sound: Engine.slay)
        if result.crit:
            engine.log("A telling blow!")
        if not result.hit:
            engine.log(f"{how}misses the {name}." if tech else f"You miss the {name}.")
        elif result.killed:
            engine.log(f"{how}kills the {name}." if tech else f"You kill the {name}.")
            engine.slay(target)
            if ws.has_passive(player, "axes"):           # Cleave: the blow carries on
                gm = engine.game_map
                other = next((m for m in gm.monsters if abs(m.x - player.x) + abs(m.y - player.y) == 1
                              and not m.type.ghost and not m.burrowed), None)
                if other:
                    more = combat.resolve(player, other)
                    if not more.hit:
                        engine.log(f"Your swing carries on, but misses the {other.name}.")
                    elif more.killed:
                        engine.log(f"Your swing carries on and kills the {other.name}.")
                        engine.slay(other)
                    else:
                        engine.log(f"Your swing carries on into the {other.name} ({more.damage}).")
        else:
            engine.log(f"{how}hits the {name} for {result.damage}." if tech else f"You hit the {name} for {result.damage}.")
            if tech == "Rend":
                target.bleeding = ws.REND_TURNS
                engine.log(f"The {name} is bleeding.")
            elif tech == "Stagger":
                target.staggered = ws.STAGGER_TURNS
                engine.log(f"The {name} reels.")
            elif tech == "Throw":
                dx, dy = target.x - player.x, target.y - player.y
                nx, ny = target.x + dx, target.y + dy
                gm = engine.game_map
                if gm.in_bounds(nx, ny) and gm.is_walkable(nx, ny) and not gm.monster_at(nx, ny) and not gm.npc_at(nx, ny):
                    target.x, target.y = nx, ny
                target.staggered = 1
                engine.log(f"You throw the {name} off balance.")
        if result.hit and target.type.thorns and not talents.total(player, "thorn_resist"):   # thistlehound's burrs
            player.stats.hp -= target.type.thorns
            engine.log(f"The {name}'s burrs bite into your hands ({target.type.thorns}).")
            if player.stats.hp <= 0:
                engine.player_down(target)
        return not quick


class EquipAction(Action):
    """Wield or wear an inventory item, or take it off if it's already on."""

    def __init__(self, index: int) -> None:
        self.index = index

    def perform(self, engine: "Engine") -> bool:
        player = engine.player
        item = player.inventory.items[self.index]
        if player.goes_in_artifact_slot(item):
            ok, msg = player.equip_artifact(self.index)
            engine.log(msg)
            return ok
        slot = player.slot_for(item)
        if slot is None:
            engine.log(f"You can't wield or wear {article(item.label)}.")
            return False
        verb = {"weapon": "wield", "windcatcher": "hang at your belt"}.get(slot, "put on")
        if player.is_equipped(item):
            player.unequip(item)
            off = {"weapon": "put away", "windcatcher": "unhook"}.get(slot, "take off")
            engine.log(f"You {off} the {item.type.name}.")
            return True
        old = player.equip(item)
        if old:
            engine.log(f"You swap the {old.type.name} for the {item.type.name}.")
        else:
            engine.log(f"You {verb} the {item.type.name}.")
        return True


class UseAction(Action):
    """Drink, eat or otherwise use an inventory item."""

    def __init__(self, index: int) -> None:
        self.index = index

    def perform(self, engine: "Engine") -> bool:
        from game import artifacts
        player = engine.player
        item = player.inventory.items[self.index]
        if item.type.is_broken_artifact:
            took_time, messages = artifacts.study(player, item.type, engine.skills)
            for message in messages:
                engine.log(message)
            return took_time
        if item.type.working:
            used = artifacts.use(engine, item)
            if used:
                from game import sound
                sound.play("artifact")
            return used
        if item.trophy is not None:              # butcher a trophy from the pack, here (v0.61.0)
            from game import trophies
            player.inventory.remove(self.index)
            engine.screen = None
            engine.log(trophies.butcher(engine, item, engine.rng))
            return True
        if item.type.writing:
            from game import library
            from game.screens import ReadingScreen
            took_time, messages, show = library.read(engine, item.type)
            for message in messages:
                engine.log(message)
            if show:
                engine.screen = ReadingScreen(item.type.writing["title"], item.type.writing["text"])
            return took_time
        props = item.type.properties
        if "treats" in props:
            from game import medicine
            used = medicine.use(engine, self.index)
            if used:
                from game import sound
                sound.play("bandage")
            return used
        if "burn_turns" in props:
            return self.light_torch(engine, item)
        if "heal_per_turn" in props:
            return self.eat(engine, item)
        if props.get("escape"):
            return self.escape(engine, item)
        heal = item.type.properties.get("heal")
        if heal is None:
            engine.log(f"You can't find a use for the {item.type.name} right now.")
            return False
        if player.stats.hp == player.stats.max_hp:
            engine.log("You're not hurt.")
            return False
        player.inventory.remove(self.index, 1)
        from game import talents                     # (Field Medic)
        gained = player.stats.heal(heal + talents.total(player, "draught"))
        engine.log(f"You drink the {item.type.name}. (+{gained} HP)")
        from game import sound
        sound.play("drink")
        return True

    def light_torch(self, engine: "Engine", item) -> bool:
        player = engine.player
        if engine.game_map.light != "torch":
            engine.log("It's light enough here. Save the torch for somewhere dark.")
            return False
        if player.torch_turns > 0:
            engine.log(f"You already have a torch burning ({player.torch_turns} turns left).")
            return False
        player.inventory.remove(self.index, 1)
        from game import fieldskills
        player.torch_turns = fieldskills.torch_turns(player, item.type.properties["burn_turns"])
        fieldskills.practise(engine, "survival")
        player.torch_light = item.type.properties.get("light", 0)
        engine.log(f"You light a {item.type.name}. The dark pulls back a little.")
        from game import sound
        sound.play("torch")
        return True

    def eat(self, engine: "Engine", item) -> bool:
        player = engine.player
        if player.meal_turns > 0:
            engine.log("You're still working through the last one.")
            return False
        if player.stats.hp >= player.stats.max_hp:
            engine.log("You're not hurt. Save it for later.")
            return False
        player.inventory.remove(self.index, 1)
        from game import fieldskills
        from game import talents                     # (Iron Gut: half again as long)
        player.meal_turns = round(fieldskills.ration_turns(player, item.type.properties.get("heal_turns", 1))
                                  * (1 + talents.total(player, "ration") / 100))
        fieldskills.practise(engine, "survival")
        player.meal_heal = item.type.properties["heal_per_turn"]
        engine.log(f"You eat a {item.type.name}. You'll mend a little over the next {player.meal_turns} turns.")
        from game import sound
        sound.play("eat")
        return True

    def escape(self, engine: "Engine", item) -> bool:
        """Climb straight back to the trail home (area 1), then on home as if you'd walked there."""
        player = engine.player
        if engine.hunt is None:
            engine.log("There's nowhere to climb out of here.")
            return False
        player.inventory.remove(self.index, 1)
        engine.screen = None
        engine.log(f"You use the {item.type.name} and make your way back to the trail home.")
        from game import sound
        sound.play("rope")
        engine.travel(0, arrive_at="entry")
        engine.reach_trail_home()
        return False  # the journey happens between turns


class ArtifactSlotAction(Action):
    """Something done to an equipped artifact: take it off, use it, or drop it."""

    def __init__(self, slot: int, what: str) -> None:
        self.slot = slot
        self.what = what  # "unequip", "use" or "drop"

    def perform(self, engine: "Engine") -> bool:
        from game import artifacts
        from game.items import FloorItem
        player = engine.player
        item = player.artifact_slots[self.slot]
        if item is None:
            engine.log("That artifact slot is empty.")
            return False
        if self.what == "use":
            return artifacts.use(engine, item)
        if self.what == "drop":
            player.artifact_slots[self.slot] = None
            engine.game_map.items.append(FloorItem(player.x, player.y, item))
            engine.log(f"You drop the {item.type.name}.")
            return True
        ok, msg = player.unequip_artifact(self.slot)
        engine.log(msg)
        return ok


class FireAction(Action):
    """Shoot the wielded bow at a spot (see game/ranged.py)."""

    def __init__(self, x: int, y: int) -> None:
        self.x, self.y = x, y

    def perform(self, engine: "Engine") -> bool:
        from game import ranged
        return ranged.fire(engine, self.x, self.y)


class ExploreAction(Action):
    """Auto-explore (game/explore.py). Takes its own turns, step by step."""

    def perform(self, engine: "Engine") -> bool:
        from game.explore import explore, explore_steps
        if engine.animate_walks:          # the game: watched a step at a time (v0.65.0)
            engine.start_walk(explore_steps(engine))
        else:                             # tests and tools: all at once
            explore(engine)
        return False  # the turns are taken inside


class TravelAction(Action):
    """Walk to a known place (game/travel.py). Takes its own turns, step by step."""

    def __init__(self, label: str, spot: tuple[int, int], beside: bool) -> None:
        self.label, self.spot, self.beside = label, spot, beside

    def perform(self, engine: "Engine") -> bool:
        from game.travel import travel, travel_steps
        if engine.animate_walks:
            engine.start_walk(travel_steps(engine, self.label, self.spot, self.beside))
        else:
            travel(engine, self.label, self.spot, self.beside)
        return False  # the turns are taken inside


class ButcherAction(Action):
    """b: butcher the corpse you're standing on, for materials (v0.61.0)."""

    def perform(self, engine: "Engine") -> bool:
        from game import trophies
        return trophies.butcher_here(engine)
