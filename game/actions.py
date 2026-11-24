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
        from game import weaponskills
        far = weaponskills.reach_target(engine, self.dx, self.dy) if engine.hunt is not None else None
        if far is not None:                      # a whip or a polearm: strike at two cells (v0.78.0)
            return AttackAction(far, reach=True).perform(engine)
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
        if tile.symbol == "S":                      # a monument (v0.68.0): its story
            from game import monuments
            if monuments.read(engine, nx, ny):
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

        from game import wilds
        if wilds.blocks(engine, nx, ny):               # a camp on the Brisering (v0.91.0): its window
            wilds.open_camp(engine, (nx, ny))
            return False
        from game import legs
        wade = not tile.walkable and legs.can_wade(engine, nx, ny)     # Wading (a leg trait, v0.86.0)
        if not tile.walkable and not wade:
            from game import sound
            sound.play("bump", gap=0.4)
            place = engine.game_map.landmarks.get((nx, ny))
            from game import sites, homes
            if place and engine.in_brisering() and sites.for_landmark(place):   # Ingenfjel, the stead (v0.74.0)
                sites.enter(engine, sites.for_landmark(place), (player.x, player.y))
                return False
            if homes.use(engine, nx, ny):                  # your bed, chest or shelves (v0.74.0)
                return False
            if tile.symbol == "z":                         # the straw in the boga stables (v0.100.5)
                from game import rest
                rest.stable_sleep(engine)
                return False
            if tile.symbol == "K":                         # a Guild bunk (the dormitory): sleep off what you owe
                from game import rest
                if rest.pulses_owed(engine.player):
                    rest.sleep(engine, rest.dorm_rate(), "in a Guild bunk")
                else:
                    engine.log("You're rested. The bunks are for Hunters home from a hunt.")
                return False
            if place:      # a village on the Brisering (lore, user): not open yet
                engine.log(f"{place}. You can't go in yet.")
            else:
                engine.log(f"The {tile.name} blocks your way.")
            return False

        from_x, from_y = player.x, player.y
        beside = legs.beside(engine)
        player.move(self.dx, self.dy)
        legs.after_step(engine, tile, beside, wade)     # mud, Runner's (v0.86.0)
        engine.heavy_step = True        # (a step: Gravity makes time pass faster for it, v0.70.0)
        player.stepped_now = True       # (Braced, v0.78.0)
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
            from game import wilds
            if wilds.spot_here(engine):                # a foraging spot on the Brisering (v0.91.0)
                return wilds.gather(engine)
            from game import fishing
            dug = fishing.dig(engine)                  # soft ground by water: worms (v0.94.0)
            if dug is not None:
                engine.log(dug)
                return not dug.startswith("You've dug here lately")
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
        if player.inventory.items[self.index].type.properties.get("no_drop"):   # (Selda, v0.67.0)
            engine.log(f"You won't leave {player.inventory.items[self.index].type.name} behind.")
            return False
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

    def __init__(self, target, reach: bool = False) -> None:
        self.target = target
        self.reach = reach        # struck from two cells away (whips, polearms; v0.78.0)

    def perform(self, engine: "Engine") -> bool:
        from game import combat

        target, player = self.target, engine.player
        player.note_weapon_use()
        name = target.name
        from game import talents
        if target.type.ghost:              # (v0.49.0) nothing touches an ashmantle
            if talents.total(player, "ghost_strike"):          # Ward-cut (a trait, v0.77.0): half a blow
                dealt = max(1, (combat.roll(player.damage_dice, engine.rng) + player.damage_bonus) // 2)
                target.take_damage(dealt)
                if target.is_dead:
                    engine.log(f"Your blade cuts the {name} apart.")
                    engine.slay(target)
                else:
                    engine.log(f"Your blade bites into the {name} ({dealt}).")
                return True
            engine.log(f"Your blow passes through the {name} like smoke.")
            return True
        if target.burrowed:
            engine.log(f"The {name} is under the ground: your blow strikes only gravel.")
            return True
        from game import weaponskills as ws
        weapon = player.equipped.get("weapon")
        if weapon is not None and player.close_rest == 0 and not self.reach:     # (v0.80.0: making room to shoot)
            props = weapon.type.properties
            if props.get("disengage") and spring_back(engine, target, props["disengage"]):
                return True
            if props.get("knockback") and slam(engine, target, props["knockback"]):
                return True
        skill = ws.melee_skill(player)
        tech = None
        if player.readied:                 # a readied technique, if it's this weapon's (game/weaponskills.py)
            if skill in ws.TECHNIQUES and ws.technique(skill, "active")[0] == player.readied:
                tech = ws.spend(player)
            else:
                player.readied = None
        weapon = player.equipped.get("weapon")
        free_n = ((1 if ws.has_passive(player, "brawling") or (weapon is not None and weapon.type.properties.get("quick_first")) else 0)
                  + talents.total(player, "free_blows"))       # Quick hands; a knife's first cut; the Quick hands trait
        quick = target.blows < free_n
        if self.reach and not player.coil_used and talents.total(player, "free_reach"):   # Quick coil
            quick, player.coil_used = True, True
        first = not target.touched
        target.touched = True
        target.blows += 1
        accuracy, rolls = (ws.LUNGE_ACCURACY, 2) if tech == "Lunge" else (0, 1)
        trait_dmg = (talents.total(player, f"damage_vs:{target.type.id}")              # traits (v0.77.0)
                     + (talents.total(player, "bounty_damage") if getattr(target, "bounty", None) else 0))
        if talents.total(player, "armoured_rolls") and target.armor >= 2:            # Shell-cracker
            rolls += talents.total(player, "armoured_rolls")
        if (ws.has_passive(player, "knives") and not getattr(target, "awake", True)) or \
                (first and talents.total(player, "first_double")):                    # Backstab; Quick draw
            rolls *= 2
        if first:
            accuracy += talents.total(player, "first_accuracy")                      # Pouncing
        if not getattr(target, "awake", True):
            accuracy += talents.total(player, "sneak_accuracy")                      # Sly
        if target.hp >= target.type.hp:
            trait_dmg += talents.total(player, "full_hp_damage")                     # Opener
        trait_dmg += talents.total(player, "reach_damage" if self.reach else "close_damage")   # Stinging; Spiked butt
        if player.missed_last and talents.total(player, "measured"):                  # Measured
            accuracy += 50
        trait_dmg += min(4, player.streak) * talents.total(player, "momentum")        # Momentum
        trait_dmg += min(3, player.area_kills) * talents.total(player, "notched")     # Notched
        if player.rhythm:                                                             # Rhythm
            accuracy, player.rhythm = accuracy + player.rhythm, 0
        if target.type.beast:
            accuracy += talents.total(player, "beast_accuracy")                       # Herder's
        if target.charged:
            trait_dmg += talents.total(player, "charge_damage")                       # Ringing
            if target.type.beast:
                trait_dmg += talents.total(player, "charge_beast_damage")             # Boar-spear
        if weapon is not None and talents.total(player, "paired_damage"):             # Paired: a second blade
            from game import gear
            kind = gear.gear_type(weapon.type)
            if any(it.type.kind == "weapon" and gear.gear_type(it.type) == kind for it in player.inventory.items):
                trait_dmg += talents.total(player, "paired_damage")
        from game import injuries as _inj
        if "bleeding" in _inj.bleeding(player):
            trait_dmg += talents.total(player, "bleeding_damage")                    # Feral
        if self.reach and ws.has_passive(player, "whips"):                          # Crack
            accuracy += ws.CRACK_ACCURACY
        if tech == "Impale":                                                          # Impale: no armour
            trait_dmg += max(0, target.armor - player.pierce)
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
                                damage=sneak_dmg + prey_dmg + trait_dmg)
        ws.practise(engine, result.hit)
        if not getattr(target, "awake", True):
            if result.hit:
                fieldskills.practise(engine, "stealth")
                engine.log(f"The {name} never saw you coming.")
            target.awake, target.turns_unseen = True, 0
        how = f"Your {tech} " if tech else ""
        at = " at reach" if self.reach else ""            # (whips and polearms, v0.78.0)
        from game import sound
        if tech:
            sound.play("technique")
        if not result.hit:
            sound.play("miss")
        elif not result.killed:
            sound.play("crit" if result.crit else "hit")     # (a kill has its own sound: Engine.slay)
        if result.crit:
            engine.log("A telling blow!")
        player.missed_last = not result.hit                                         # (Measured, Momentum)
        player.streak = player.streak + 1 if result.hit else 0
        if result.killed:
            player.area_kills += 1                                                   # (Notched)
            if talents.total(player, "kill_accuracy"):
                player.frenzied = 3                                                  # (Frenzied)
        if not result.hit:
            engine.log(f"{how}misses the {name}." if tech else f"You miss the {name}{at}.")
        elif result.killed:
            engine.log(f"{how}kills the {name}." if tech else f"You kill the {name}{at}.")
            engine.slay(target)
            if ws.has_passive(player, "axes"):           # Cleave: the blow carries on
                gm = engine.game_map
                carries = 1 + talents.total(player, "cleave_extra")   # (Wide arc: one more)
                for _ in range(carries):
                    other = next((m for m in gm.monsters if abs(m.x - player.x) + abs(m.y - player.y) == 1
                                  and not m.type.ghost and not m.burrowed), None)
                    if not other:
                        break
                    more = combat.resolve(player, other)
                    if not more.hit:
                        engine.log(f"Your swing carries on, but misses the {other.name}.")
                        break
                    elif more.killed:
                        engine.log(f"Your swing carries on and kills the {other.name}.")
                        engine.slay(other)
                    else:
                        engine.log(f"Your swing carries on into the {other.name} ({more.damage}).")
                        break
        else:
            engine.log(f"{how}hits the {name} for {result.damage}." if tech else f"You hit the {name}{at} for {result.damage}.")
            if tech == "Rend":
                target.bleeding = ws.REND_TURNS * (2 if talents.total(player, "rend_double") else 1)
                engine.log(f"The {name} is bleeding.")
            elif tech == "Stagger":
                target.staggered = ws.STAGGER_TURNS
                engine.log(f"The {name} reels.")
            elif tech in ("Snare", "Impale"):
                if tech == "Snare":
                    target.held = ws.SNARE_TURNS
                    engine.log(f"The lash wraps the {name}: it can't move.")
                    if talents.total(player, "snare_pull"):                          # Lash-and-pull
                        pull(engine, target)
                else:
                    target.staggered = max(target.staggered, 1 + talents.total(player, "impale_stagger"))
                    engine.log(f"The {name} reels.")
            elif tech == "Throw":
                dx, dy = target.x - player.x, target.y - player.y
                nx, ny = target.x + dx, target.y + dy
                gm = engine.game_map
                if gm.in_bounds(nx, ny) and gm.is_walkable(nx, ny) and not gm.monster_at(nx, ny) and not gm.npc_at(nx, ny):
                    target.x, target.y = nx, ny
                    if talents.total(player, "throw_far"):                           # Iron grip: two cells
                        _, (target.x, target.y) = _away(engine, (nx, ny), dx, dy, talents.total(player, "throw_far"))
                target.staggered = 1
                engine.log(f"You throw the {name} off balance.")
        if result.hit:
            gear_after_hit(engine, target, result, reach=self.reach)
            if not result.killed and ws.has_passive(player, "claws") and engine.rng.randint(1, 100) <= ws.RAKE_CHANCE:
                bleed(engine, target)                                                 # Rake
        if not player.kick_used and talents.total(player, "free_kick") and target in engine.game_map.monsters \
                and not self.reach:                                                  # Kicking: once an area
            player.kick_used = True
            kick = combat.roll("1d3", engine.rng)
            target.take_damage(kick)
            if target.is_dead:
                engine.log(f"A kick finishes the {name}.")
                engine.slay(target)
            else:
                engine.log(f"You kick the {name} ({kick}).")
        twin = talents.total(player, "double_strike")
        if target in engine.game_map.monsters and (tech == "Flurry" or (twin and engine.rng.randint(1, 100) <= twin)):
            more = combat.resolve(player, target, engine.rng)                        # Flurry; Twin blades
            if not more.hit:
                engine.log(f"Your second strike misses the {name}.")
            elif more.killed:
                engine.log(f"Your second strike kills the {name}.")
                engine.slay(target)
            else:
                engine.log(f"Your second strike hits the {name} for {more.damage}.")
        if tech == "Sweep":                                                          # Sweep: everything beside you
            gm = engine.game_map
            for other in [m for m in gm.monsters if abs(m.x - player.x) + abs(m.y - player.y) == 1
                          and not m.type.ghost and not m.burrowed]:
                if other is not target:
                    more = combat.resolve(player, other, engine.rng)
                    if more.killed:
                        engine.log(f"The sweep kills the {other.name}.")
                        engine.slay(other)
                        continue
                    engine.log(f"The sweep {'hits the ' + other.name + f' for {more.damage}' if more.hit else 'misses the ' + other.name}.")
                other.staggered = max(other.staggered, 1 + talents.total(player, "sweep_stagger"))
        if tech == "Frenzy":                                                         # Frenzy: blows with no time
            player.frenzy = ws.FRENZY_BLOWS + talents.total(player, "frenzy_extra")
            engine.log("You fall on it in a frenzy.")
        if result.hit and target.type.thorns and not talents.total(player, "thorn_resist"):   # thistlehound's burrs
            player.stats.hp -= target.type.thorns
            engine.log(f"The {name}'s burrs bite into your hands ({target.type.thorns}).")
            if player.stats.hp <= 0:
                engine.player_down(target)
        if player.frenzy > 0:
            player.frenzy -= 1
            return False
        return not quick


def _away(engine, start, dx, dy, most) -> tuple:
    """How far one can go from start in (dx, dy), up to most cells: (cells, end)."""
    gm = engine.game_map
    x, y = start
    n = 0
    while n < most:
        nx, ny = x + dx, y + dy
        if (not gm.in_bounds(nx, ny) or not gm.is_walkable(nx, ny) or gm.monster_at(nx, ny) or gm.npc_at(nx, ny)
                or gm.tile_at(nx, ny).symbol in "<>HG" or (nx, ny) == (engine.player.x, engine.player.y)):
            break
        x, y, n = nx, ny, n + 1
    return n, (x, y)


def spring_back(engine, target, cells: int) -> bool:
    """A bow up close (user, v0.80.0): spring back out of the creature's reach, up to `cells` away from
    it, to shoot again. A few turns before you can again. False (nothing done) if there's no room."""
    from game import weaponskills as ws
    p = engine.player
    dx, dy = p.x - target.x, p.y - target.y
    n, (x, y) = _away(engine, (p.x, p.y), dx, dy, cells)
    if n == 0:
        return False
    from_x, from_y = p.x, p.y
    p.x, p.y = x, y
    p.close_rest = ws.CLOSE_REST
    p.stepped_now = True
    engine.log(f"You spring back from the {target.name}, out of its reach.")
    engine.on_step(from_x, from_y)
    return True


def slam(engine, target, cells: int) -> bool:
    """A crossbow up close (user, v0.80.0): slam the creature with the stock: 1 damage, and it's
    knocked back up to `cells`. A few turns before you can again. False if it can't be moved."""
    from game import weaponskills as ws
    p = engine.player
    if target.type.ghost or target.burrowed:
        return False
    dx, dy = target.x - p.x, target.y - p.y
    n, (x, y) = _away(engine, (target.x, target.y), dx, dy, cells)
    if n == 0:
        return False
    target.x, target.y = x, y
    target.awake, target.touched = True, True
    p.close_rest = ws.CLOSE_REST
    target.take_damage(1)
    if target.is_dead:
        engine.log(f"You slam the {target.name} with the stock, and it doesn't get up.")
        engine.slay(target)
    else:
        engine.log(f"You slam the {target.name} with the stock and knock it back.")
    return True


def pull(engine, target) -> bool:
    """Drag a creature a cell toward the Hunter (Hooking, Lash-and-pull), if the cell is free."""
    p, gm = engine.player, engine.game_map
    dx, dy = (p.x > target.x) - (p.x < target.x), (p.y > target.y) - (p.y < target.y)
    if dx and dy:
        return False
    nx, ny = target.x + dx, target.y + dy
    if (nx, ny) == (p.x, p.y) or not gm.is_walkable(nx, ny) or gm.monster_at(nx, ny) or gm.npc_at(nx, ny):
        return False
    target.x, target.y = nx, ny
    engine.log(f"You drag the {target.name} toward you.")
    return True


def gear_after_hit(engine, target, result, reach: bool = False) -> None:
    """Traits that act when a melee blow lands (v0.77.0): healing, bleeding, staggering."""
    from game import talents, weaponskills as ws
    p = engine.player
    if talents.total(p, "heal_on_hit") and p.stats.hp < p.stats.max_hp:            # Hungry
        p.stats.heal(talents.total(p, "heal_on_hit"))
    if result.killed:
        return
    rng = engine.rng
    execute = talents.total(p, "execute")                                            # Coup de grâce
    if execute and target.hp * 100 <= execute * target.type.hp:
        target.hp = 0
        engine.log(f"You finish the {target.name}.")
        engine.slay(target)
        return
    chance = talents.total(p, "bleed_chance")
    if (chance and rng.randint(1, 100) <= chance) or (result.crit and talents.total(p, "crit_bleed")):
        bleed(engine, target)
    stagger = talents.total(p, "stagger_chance")
    if (stagger and rng.randint(1, 100) <= stagger) or (result.crit and talents.total(p, "crit_stagger")):
        target.staggered = max(target.staggered, 1)
        engine.log(f"The {target.name} reels.")
    if talents.total(p, "hold_on_hit"):                                              # Gripping, Grappler's
        target.held = max(target.held, 1)
    pin = talents.total(p, "pin_chance")
    if pin and rng.randint(1, 100) <= pin:                                           # Pinning
        target.held = max(target.held, 2)
        engine.log(f"You pin the {target.name} where it stands.")
    on_hit_states(engine, target, rng)
    if result.crit and talents.total(p, "crit_quake"):                               # Earthshaker
        for m in list(engine.game_map.monsters):
            if m is not target and abs(m.x - target.x) + abs(m.y - target.y) == 1:
                m.staggered = max(m.staggered, 1)
        engine.log("The ground shakes under the blow.")
    if reach and talents.total(p, "skewer"):                                         # Skewering: the one behind too
        from game import combat
        sx, sy = (target.x > p.x) - (target.x < p.x), (target.y > p.y) - (target.y < p.y)
        behind = engine.game_map.monster_at(target.x + sx, target.y + sy)
        if behind is not None and not behind.type.ghost and not behind.burrowed:
            more = combat.resolve(p, behind, rng)
            if more.killed:
                engine.log(f"The point goes on through and kills the {behind.name}.")
                engine.slay(behind)
            elif more.hit:
                engine.log(f"The point goes on through into the {behind.name} ({more.damage}).")
    if reach and talents.total(p, "reach_pull") and target in engine.game_map.monsters:   # Hooking
        pull(engine, target)


def on_hit_states(engine, target, rng) -> None:
    """Chances on a landed blow or shot (v0.81.0): poison, slowing, frightening, fumbling."""
    from game import talents
    p = engine.player
    for key, what in (("poison_chance", "poison"), ("slow_chance", "slow"), ("frighten_chance", "fright"),
                      ("fumble_chance", "fumble")):
        n = talents.total(p, key)
        if not n or rng.randint(1, 100) > n:
            continue
        if what == "poison":
            target.poisoned = max(target.poisoned, 6)
            engine.log(f"The {target.name} is poisoned.")
        elif what == "slow":
            target.slowed = max(target.slowed, 6)
            engine.log(f"The {target.name} is slowed.")
        elif what == "fright":
            target.fleeing = max(target.fleeing, 3)
            engine.log(f"The {target.name} panics and runs.")
        else:
            target.fumble = True
            engine.log(f"You knock the {target.name}'s guard aside.")


def bleed(engine, target) -> None:
    """Start a creature bleeding (Rend's length, plus Raking's turns)."""
    from game import talents, weaponskills as ws
    turns = ws.REND_TURNS + talents.total(engine.player, "bleed_extra")
    if target.bleeding < turns:
        target.bleeding = turns
        engine.log(f"The {target.name} is bleeding.")


class VaultAction(Action):
    """j then a direction, with Pole-vault (a staff trait, v0.86.0): leap two cells, once an area."""

    def __init__(self, dx: int, dy: int) -> None:
        self.dx, self.dy = dx, dy

    def perform(self, engine: "Engine") -> bool:
        from game import legs
        return legs.vault(engine, self.dx, self.dy)


class ReloadAction(Action):
    """f with a crossbow that needs winding: a turn to wind it (v0.78.0)."""

    def perform(self, engine: "Engine") -> bool:
        from game import ranged
        return ranged.reload(engine)


class EquipAction(Action):
    """Wield, wear or hang a bag item in its equipment slot (out of the bag since v0.69.0); an
    artifact goes in an artifact slot (the given one, or the first free)."""

    def __init__(self, index: int, slot: int | None = None) -> None:
        self.index = index
        self.slot = slot

    def perform(self, engine: "Engine") -> bool:
        player = engine.player
        item = player.inventory.items[self.index]
        if player.goes_in_artifact_slot(item):
            ok, msg = player.equip_artifact(self.index, self.slot)
            engine.log(msg)
            return ok
        slot = player.slot_for(item)
        if slot is None:
            engine.log(f"You can't wield or wear {article(item.label)}.")
            return False
        verb = {"weapon": "wield", "windcatcher": "hang at your belt"}.get(slot, "put on")
        try:
            old = player.equip(item)          # (out of the bag into its slot; the old one into the bag)
        except ValueError as err:
            engine.log(f"{err}.")
            return False
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
        if item.catch is not None:               # gut a fish from the pack (v0.100.0)
            from game import fishing
            engine.screen = None
            engine.log(fishing.gut_item(engine, self.index, engine.rng))
            return True
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
        if props.get("fed") or props.get("cures"):    # dishes cooked at a camp (v0.91.0)
            from game import wilds
            return wilds.eat_dish(engine, self.index)
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
        if engine.game_map.light != "dark":
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


class UnequipAction(Action):
    """Take off what's in an equipment slot (weapon, armor, windcatcher) into the bag (v0.69.0)."""

    def __init__(self, slot: str) -> None:
        self.slot = slot

    def perform(self, engine: "Engine") -> bool:
        ok, msg = engine.player.unequip_slot(self.slot)
        engine.log(msg)
        return ok


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


class ThrowAction(Action):
    """Throw something at a spot (see game/throwing.py, v0.82.0)."""

    def __init__(self, item, x: int, y: int) -> None:
        self.item, self.x, self.y = item, x, y

    def perform(self, engine: "Engine") -> bool:
        from game import throwing
        return throwing.throw(engine, self.item, self.x, self.y)


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
        from game import trophies, talents
        took = trophies.butcher_here(engine)
        return took and not talents.total(engine.player, "quick_butcher")      # Butcher's (a trait)


class CastAction(Action):
    """Cast a line (v0.94.0, game/fishing.py): a turn; then the fishing window."""

    def __init__(self, x: int, y: int, bait: str) -> None:
        self.x, self.y, self.bait = x, y, bait

    def perform(self, engine: "Engine") -> bool:
        from game import fishing
        ok, why = fishing.cast(engine, self.x, self.y, self.bait)
        if not ok:
            engine.log(why)
            return False
        from game.screens import FishScreen
        engine.screen = FishScreen()
        return True


class FishAction(Action):
    """One choice at the water: wait, strike, reel, hold, give, left, right, cut, keep, release, stop."""

    def __init__(self, cmd: str) -> None:
        self.cmd = cmd

    def perform(self, engine: "Engine") -> bool:
        from game import fishing
        took = fishing.step(engine, self.cmd)
        from game.screens import FishScreen
        if engine.fishing is None and isinstance(engine.screen, FishScreen):
            engine.screen = None
        return took
