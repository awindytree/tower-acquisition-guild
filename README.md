# Tower Acquisition Guild

A traditional roguelike built with Python and [python-tcod](https://python-tcod.readthedocs.io/).

## Playing

**Windows:** double-click **`Play.bat`**. The first time, it sets things up
(about a minute, needs internet). After that the game opens straight away
with no terminal window.

Want it on your desktop? Right-click `Play.bat` → *Show more options* →
*Create shortcut*, then drag the shortcut to your desktop. You can give the
shortcut its own name and icon from its *Properties*.

If the game ever crashes, it saves the details to `crash.log` in this
folder and tells you so.

Needs Python 3.10 or newer from https://www.python.org/downloads/. Tick
"Add python.exe to PATH" when installing.

### Running from a terminal (any system)

```
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
python main.py
```

## Controls

| Keys | Action |
|---|---|
| Arrow keys / WASD | Move |
| Numpad 8 4 6 2 | Move (movement is four-way: no diagonal steps) |
| `.` or Numpad 5 | Wait one turn |
| (walking) | Auto-explore (`o`) and travel-to (`t`) walk a step at a time; any key stops them |
| `g` or `,` | Pick up what's here (a corpse only when nothing else is: it goes in your pack as a trophy) |
| `b` | Butcher the corpse you're standing on, for materials (takes a turn) |
| `r` | Fish: with a rod and bait, cast into water within reach (see Fishing) |
| `p` | The Angler's Log: every kind of fish, by water, and what you know of it |
| Walk into a creature | Attack it |
| Walk into someone | Talk: `↑↓` or `1`-`9` to choose, Enter, Esc to leave |
| (shop) | Trade (`←→`/Tab: Buy or Sell, Enter, Esc) |
| (workshop) | Workshop: `r` repair, `b` sell (broken or repaired), `c` consign; `←→`/Tab: Buy, Training |
| `x` | Look: move the cursor (movement keys) or `Tab` between things in view; the view follows the cursor, as far as you can see (less in the dark); `Esc` done |
| `i` | Inventory (the bag, a carousel: the selected item sits on the top row and the rest follow it, wrapping round): `↑↓` select, `e` wield/wear/equip (weapon, armour, windcatcher or artifact), `u` use (drink, use an artifact, or study a broken one), `d` drop, `Tab` the equipment window, `Esc` close |
| `e` | Equipment: weapon, head, chest, legs, windcatcher (its Jodebris bar) and artifact slots. `↑↓` select, `e` take off, `u` use an artifact, `Enter` pick something from the bag for that slot (swapping), `Tab` the bag, `Esc` close |
| `t` | Travel to a known place (walks there, stopping if anything comes up) |
| `o` | Auto-explore (hunts): walk to unexplored ground until something comes up (a creature, an item, the way deeper) |
| `h` | Throw (hurl) something: a flash pot, a smoke jar, a lure, or a weapon with a throwing trait: Tab next target, move keys to aim, Enter/`h` throw, Esc |
| `j` + direction | Pole-vault two cells (a staff with the Pole-vault trait; once per area) |
| `f` | Aim and shoot a wielded bow or crossbow (a crossbow that needs winding: `f` winds it, a turn): Tab next target, move keys to aim, Enter/`f` shoot, Esc |
| `z` | Ready your weapon's rank-5 technique (again to put it aside); no time |
| `n` | Choose a talent you've earned |
| `c` | Character sheet, in three tabs (`←→`/Tab): **Hunter** (level, rank, age, HP/XP/Jodebris bars, attributes with what's changing them (`↑↓` picks one to read about), fighting numbers, condition), **Guild** (progress to the next rank, money and dues, words known, field notes), **Calling** (your calling, prey, talents). `e` and `k` jump to equipment and skills |
| `k` | Skills: every skill, grouped, with rank, practice and what it gives |
| `m` | The whole map, over the map view (explored ground only, out in the miasma and on the Brisering) |
| `v` | Side panel: the minimap or the message log (big maps show the stretch around you) |
| `l` | Message log (↑↓, `[` `]` or PgUp/PgDn, Home/End) |
| `?` or F1 | Key reference |
| F2 | Sound on or off (volumes: Sound, in the title menu or Esc menu) |
| F11 or Alt+Enter | Fullscreen on or off (remembered for next time, in `saves/window.json`) |
| Walk into the stash chest | Guild stash (guild hall, back right room): `←→` side, Enter moves across, `o` sorts by kind, name or worth |
| Walk into a service window (`▬`) | Talk to whoever works behind it (the guild clerk) |

## Shops

The supplier keeps a shop on the edge of Bytorsskug's plaza. Walk into the
shopkeeper (`@`, gold) to trade; trading takes no time.

- **Buy** draughts, tonics, rations, torches, rope, and better weapons and armour.
- **Sell** what you find for half its value. Take off equipment before selling
  it. Shops don't take artifacts or keys; artifacts go to an Artificer.
- Stock is limited: each item shows how many are left. Sold-out things
  come back over time (restock times are in Pulses, in `data/shops.json`).
  Whatever you sell goes up for sale at full value. Stock is part of the
  city: it stays as it is when a Hunter dies.
- Shops are in `data/shops.json`: name, greeting, stock (prices default to
  each item's value), which kinds of item they buy, and at what rate. Put a
  shopkeeper on a map with a line like `;npc=110,30 supplier`.

## Townsfolk

Walk into someone to talk. They say something, and you pick from numbered
choices; some choices open a shop, the workshop or the stash. Talking takes
no time. The supplier and the artificer keep their shops; the guild clerk
works from a small office at the back of the guild hall, behind a **service
window** (`▬`): walk into the window to talk to the clerk. A porter, a washer
and a carter wander the plaza.

**The guild hall** (v0.54.0): the front hall, with the contracts board (front
left) and the bounty board (front right); the clerk's office behind its
window at the back; the training corner (back left, the trainer); and the
stash room (back right, the chest and the retired Hunter who teaches). Other
Hunters stand about the front hall when they're home.

Who's who is in `data/townsfolk.json` (names, descriptions, how far they
wander) and what they say is in `data/dialogue/`, one file per conversation.
`data/dialogue/_README.md` explains how to write them: conditions (flags,
items, shards, skill rank, level, the Duel, holidays), effects (flags, items,
shards, opening a shop) and placeholders like `{given}`. Place a person in a
map file with `;npc=x,y <id>`.

## Hunters

Every new Hunter is random: a starting kit (a sword, an axe, or a bow and
arrows; perhaps a jerkin; some supplies and shards), a given name, a gender, and attributes (each
starts at 8, then 10 points go to random attributes, none above 14). Their
full name is **Given Calling Hunters**: every Hunter's surname is Hunters,
after the Guild, and the middle name is how they make their living. When
more than half of the last 1,000 shards they earned came from one kind of
work, that's their living: fishing makes an **Angler**. Hunting (everything
else, for now) gives the kind of weapon they've used most (swords make a
Fencer, an axe a Hewer, a war pick a Breaker, a bow an Archer; bare hands, a
Brawler), counted by attacks and shots; before their first fight, it's the
weapon they hold. The character sheet's Calling tab shows the split.

Given names are built from the sound rules in `data/names.json`: sound
classes, syllable patterns, and the consonant pairs allowed side by side.
Edit those to change how names sound. A weapon's middle name is its
`calling` in `data/items.json`. In `data/player.json`, set `name` to fix a
name, or remove `random_attributes` to use the attributes as written.

## The calendar

The Overland counts in **Pulses**: there are no days. Nine Pulses make a
**Cycle**: Emu, Lagau, Erku, Maforu, Nusu, Senu, Riu, Dymiu, Neu (ordinals:
"First" to "Ninth"). Nine Cycles make a
**Reckon**, twelve Reckons a **Judgment**, four Judgments a **Duel**. A
**Turn** is the Light Duel, four holiday (intercalary) Pulses, the Dark Duel,
and four more holiday Pulses.

**Light.** The Overland has no sunrise within a Pulse. Its axial tilt is 110°,
so through a Duel one pole faces the star and the other is dark: the Light
Duel and the Dark Duel are the Overland's light and dark. Myligast stands on
the equator, and Bytorsskug, just south of it, is lit in the Light Duel. Even
then the world is dim, and the cities live by lamplight. A place is **lit** or
**dark**: see Hunts.

Time passes as you travel: a Pulse for every move from one area to another
(setting out, going deeper, coming back, walking home), and a whole Cycle
when you complete a hunt. A new Hunter after a death arrives a Pulse later.
The game begins at the start of Turn 211. The date is in the side panel,
written compactly: "Light Duel: Emu, C1, R1, J1, T211" (Cycle, Reckon,
Judgment, Turn). The pulse names, sizes and starting
date are in `data/calendar.json`; `game/calendar.py` turns the game's count
of Pulses into a date.

## Bows and Marksmanship

Wield a bow (the short bow reaches 8, the longbow 12) and press `f` to aim.
The cursor starts on the nearest creature in range; Tab moves to the next,
or move the aim yourself. The arrow's path is shaded, and the panel shows
your chance to hit, or warns you if something is in the way. Enter or `f`
shoots. Arrows ignore 2 armour (v0.80.2). They fly straight, strike the first creature in their path, and
stop at walls; about half can be picked up again. **Up close** (v0.80.0),
walk into a creature to **spring back** out of its reach, up to two cells,
and shoot again; then it's five turns before you can again, and walking into
it is only a bash (1d2, plus 1 for every 6 Physicality). A crossbow instead
**slams** a creature with the stock: 1 damage, and it's knocked back two
cells (the same five turns' rest). (Or swap to a melee weapon from your
pack: that takes a turn.)

**Marksmanship** is your aim: each rank above 1 adds 2 to your accuracy with a
bow, and every 3 cells of distance takes 1 away. Every shot at a creature is
practice (a hit counts double; Celerity helps). Practice takes you to rank
2; the trainer in the guild hall teaches the ranks after that, for shards.
Arrows are sold in bundles of 10 at the supplier.

## The weapon types (v0.78.0)

Eleven kinds, each with its own skill (practice, and the trainer for ranks 3
and up), a calling, a passive technique at rank 3 and one you ready with `z`
at rank 5:

| Type | Skill | Calling | Rank 3 | Rank 5 |
|---|---|---|---|---|
| Sword | Blades | Fencer | Riposte | Lunge |
| Knife | Knives | Cutter | Backstab: an unnoticed hit does double damage | Flurry: two strikes at once |
| Axe | Axes | Hewer | Cleave | Rend |
| Haft | Hafted | Breaker | Crush | Stagger |
| Gloves (or bare hands) | Brawling | Brawler | Quick hands | Throw |
| Claws | Claws | Raker | Rake: a hit bleeds 20% of the time | Frenzy: three blows with no time |
| Whip | Whips | Lasher | Crack: +2 accuracy at reach | Snare: it can't move for 3 turns |
| Staff | Staves | Warder | Guard: +2 evasion | Sweep: everything beside you, staggered |
| Polearm | Polearms | Lancer | Set: a free strike at anything stepping into reach | Impale: ignores armour, staggers |
| Bow | Marksmanship | Archer | Steady hand | Aimed shot |
| Crossbow | Crossbows | Arbalist | Braced: +2 accuracy if you didn't step | Piercing bolt: hits everything in its line |

- **Reach:** whips and polearms strike a creature **two cells away in a
  straight line** with nothing between. Walk toward it to strike instead of
  stepping. A creature beside you is struck as usual.
- **Knives:** the first cut at each creature takes no time. Knives and claws
  find the gaps in armour: 1 armour ignored.
- **Crossbows:** shoot with `f` like a bow, using **bolts** (bundles of 10 at
  the supplier). After each shot the crossbow needs winding: `f` winds it, a
  turn.
- **Gloves** are real weapons now, with tiers and traits; bare hands still
  work as before.
- The supplier sells a plain one of each; the smith makes a better one of
  each to order.

## The Academy and the Guild archive

**Writings** turn up on hunts: pages, journals, letters, tablets. Read one (u)
if your **Scholarship** is up to it, and take them to the **librarian** in the
**Academy** (the great building north of the plaza). The library pays a
little for each (more if you've read it), shelves it, and any Hunter can read
it there from then on.

Out on a hunt you also keep **field notes**: creatures seen and killed, and
how far you got. **Report them to the guild clerk** for a small fee; they go
into the **Guild archive** (ask the clerk to see it): a bestiary, and
scouting reports for each place. Notes you don't report die with you.

Writings are in `data/writings.json`; the archive's numbers are at the top of
`game/archive.py`.

## Guild rank

Every Hunter starts an **Initiate**: the Wayfinder takes them only to danger 2,
and the board offers only gentle contracts. Complete hunts and level up, then **sit for the next rank**
at the guild clerk (for a fee): Apprentice, Journeyman, Veteran, Master
Hunter. Each opens more dangerous places and harder contracts, the Guild teaches
you a few new words, and the higher ones bring
privileges: cheaper training, better pay for requests, first pick of contracts
a rival has taken. Owe dues you can't pay? The clerk will let you **work them
off**, but still owing when the next dues fall due costs you a rank. Names
and numbers are in `data/ranks.json`.

## Rival Hunters

You aren't the Guild's only Hunter. A handful of **rivals** live their own lives:
they take contracts off the Guild's board (taken ones are greyed out), bring
their finds to the workshop, sometimes beat you to a request or a bounty,
level up, age, retire and die, and new ones join. When they're home they're in
the guild hall; talk to them for news. Now and then one goes after **the same
contract as you**: you'll see them pushing through the areas, and whoever gets
to the prize first has it. Hunters can't fight each other. Numbers and lines
are in `data/rivals.json`.

## The story

**The clerk's first jobs** (v0.54.0, the user's outline; wording is a draft):
a new game opens in the guild hall with a popup on moving and the clerk's
window. The clerk offers you a job. Take it, and the first jobs teach the
game as it comes up: a contract marked for you on the contracts board (the
rest are greyed out until you take it), the Wayfinder (briefed before its
window opens), the hunt (popups on the miasma, creatures, what they leave, the
deepest area, the find, getting home), then a bounty marked for you on the
bounty board, and finally the clerk pays you, tells you about the plaza's
notice board, hands you 100 shards and welcomes you properly. Decline, and you
go straight on to the story. All of it is `data/story/first_jobs.json`.

**Chapter 1: Three Words** (v0.67.0, the user's outline; wording is a draft)
follows the first jobs. Selda Fencer Hunters, an aging Hunter, went out through
the Wayfinder and hasn't come back. The clerk posts a key hunt open to every
rank, but nobody knows her words: the board shows `[?][?][?]`. You learn one on
an errand (Jokro the washer), one from a writing in the Academy library, and one
from a rumour (Klubo the porter). Her place, [Murmuring][Specter's][Broken
Promise], is dark caves at danger 3, with half the creatures and 20% less light.
It holds spent torches, a butchered body, her field notes (the clerk pays for
them), a Unique artifact, and Selda herself, hurt and out of light, with two
guardians. You carry her home (she takes 4 pack slots, and she gives you rope if
you have none). Lifa treats her. She retires into the Hall of Hunters, gives you
her empty windcatcher, and teaches field skills in a corner of the guild hall at
20% off, up to rank 4. Her artifact goes to the stash, and no one can identify,
repair or sell it. The clerk puts 500 shards toward the Wayfinder study. All of
it is `data/story/chapter1.json`.

**Monuments** (v0.68.0): **Whisper Poet's statue** stands in the plaza by the
Wayfinder (bronze `♀`). Walk into it to read its inscription; the look command and
travel-to know it too. Its text is in `data/monuments.json` (the facts are the
user's lore, the wording a draft), and more monuments can be added there and placed
with a `;monument=x,y id` line in a map.

Quests, scenes,
story lines in conversations, counters, story items and **key hunts** (story
contracts posted on the Guild's contracts board, for a given rank) are all written in
JSON in `data/story/`; `data/story/_README.md` explains how, and
`data/story/examples/example.json` is a complete working example (copy it up a
folder to try it). **q** opens the quest log: your contract, your bounties and
scouting, and the story's quests, each with what to do next. Story progress belongs to the
world, so it carries on from one Hunter to the next.

## Age, retirement and the Hall of Hunters

Every Hunter has an **age**, counted in Turns and Judgments (a Turn is about
16 years, a Judgment about 2). Each hunt leaves you **owing rest**, about a
Reckon (longer if you came home hurt), so the years add up: the mind sharpens a
little, then past 2 Turns 4 Judgments the body starts to decline, and very old
Hunters can die of old age.

**The rest you owe** (v0.88.0) is shown in the side panel. Sell, sort and train
first: every Pulse that passes pays it down, and a bed pays it faster (slowest to
fastest: on your feet, the Guild dormitory's bunks, the stead, the Ingenfjel
house, the Bytorsskug house). With no bed, sleep in the straw of the **boga
stables** by the Towerway gate (v0.100.5): free, at the plain rate, but only down
to a Cycle owed. The Wayfinder won't take you through owing a Reckon or more;
owing less, it asks whether you'll **set out weary**. Weary means less max HP, accuracy,
evasion and damage, and from half-weary no healing by resting in the field. At
80% it's a fool's game; at 100% very nearly a death sentence. The rest you
skipped is still owed when you come home.

You can **retire** at any time by asking the guild clerk. What you carry goes
to the stash, your shards to the next Hunter, and you stay on in the guild
hall to teach your skills at 25% off the trainer's price, up to your own ranks. The **Hall of Hunters** (ask the clerk)
remembers everyone who retired or died. Numbers are in `data/aging.json`.

## Balance testing

`tools/balance/sim.py` plays Hunters through hunts with the real game rules (a
careful but unskilled bot) and `tools/balance/report.py` sums up what happened:
success and death rates by danger, levels over time, shards in and out,
supplies used, artifacts, injuries. Run them again after changing numbers:

    python tools/balance/sim.py --hunters 14 --hunts 25 --seed 33 --out sim.json
    python tools/balance/report.py sim.json > report.md

About a minute per Hunter. No window opens.

## Injuries and the healer

A big hit (a fifth of your max HP or more in one blow) can leave a **lasting
injury**: cracked ribs, a twisted ankle, broken fingers, a festering bite.
Injuries lower attributes, max HP, accuracy, evasion, damage or aim; some
bleed or fester, costing HP every few turns for a while (and stopping natural
healing). Minor injuries mend on their own after some Pulses; serious ones
need the **healer**, who treats them for a fee. The side panel shows how many
you have; the character sheet (c) lists them.

In the field, a **bandage** (u) stops bleeding and a **poultice** stops
poison, if your **Medicine** skill is up to it (50% at rank 1, more with each
rank). From rank 2, a bandage also mends a minor injury outright. Practice
gets you to rank 2; the healer trains you beyond that.

The injuries are in `data/injuries.json`.

## Sound

Sound effects and ambience (v0.63.0): soft interface sounds, footsteps by
ground, combat, the world, and moments like stepping into the Wayfinder or a
hunt coming home. Every place has its own soundscape (the city's streets,
indoors, the guild hall, the Brisering, each kind of land out in the miasma,
lit or dark), and the Wayfinder hums when you're near it.

- **Sound** in the title menu or the Esc menu: volumes for everything, effects,
  ambience and music; mute; a test sound; and a line saying whether sound is
  working. **F2** mutes. Settings live in `saves/settings.json`.
- It uses python-tcod's own audio, so there's nothing extra to install. If it
  can't start, the game plays on silently and the Sound window says why.
- **To change a sound,** put a WAV file in `data/sounds/` and point the event at
  it in `data/sounds.json`. The placeholders are made from code by
  `tools/sound/make_sounds.py` (run it from the project root to remake them);
  the music by `tools/sound/make_music.py`.
- **Music:** Bytorsskug has a piece of its own (v0.102.0, the assistant's
  attempt: `tools/sound/make_music.py` makes it from code): about a minute and
  a half in D Dorian, looping without a seam, through the streets, the buildings
  and the guild hall as one piece that carries on as you go in and out. Nowhere
  else has music yet. To change it, put WAV files in `data/music/` and name them
  under `"music"` in `data/sounds.json`, by place (`city`, `hall`, `brisering`…).

## Corpses, trophies, the trophymaster and the butcher

Creatures leave their **corpses** where they die (v0.61.0), all but a few: a
lantern tick bursts, an ashmantle is smoke. A body that falls in the water
washes up on the nearest bank. What you do with one is up to you:
- **Butcher it there** (`b`, standing on it) for **materials**: each of the
  creature's materials is a chance, likelier and more of it with Harvesting.
- **Haul it home** (`g`): in your pack it's a **trophy**, with its weight (and
  now and then a quirk: pale, scarred, old, a runt, misshapen). It takes pack
  slots by size, from 1 (a rat) to 6 (a hollow brute); the inventory counts
  slots. Trophies don't spoil. `u` on one butchers it wherever you are.

**The trophymaster** (Pulnaþ, in the lodge by the plaza) keeps the records, like
a fishing contest. Hand him a trophy: if it's the heaviest of its kind, or the
first of its quirk, it goes up on the **trophy wall** (`Ω`; walk into it to read
it) with your name, and he pays: more for a tougher creature and a bigger margin
over the old record. Anything else he turns away. The records are world state:
they outlive your Hunter. His pay is earnings (the Guild takes its dues).

**The butcher** (Dimam, near the plaza) breaks a trophy down for nothing (he
keeps the meat), and surely: every material it has, at the most. Weights, sizes,
quirks and pay are placeholders (`data/trophies.json`).

## Materials and the smith

Creatures leave **materials** when butchered: hides, chitin, sinew,
iron scrap, sentinel stone. Sell them to the supplier, or take them to the
**smith** (east of the plaza), who makes gear to order: talk to them, pick
something, and pay the materials and a fee up front. It's ready after some
Pulses (shown on the Orders tab); talk to the smith again to collect it. Two
orders at a time. If a Hunter dies with an order in, the smith sends the
finished piece to the guild stash.

Townsfolk (the smith too) sometimes post requests for materials on the notice
board; hand over the whole amount at once.

Recipes are in `data/recipes.json`; what each creature leaves is under
`drops` in `data/monsters.json`.

## Gear tiers and armour slots (v0.75.0)

**Armour goes by slot: head, chest and legs**, with no armour classes. Your
armour is the three pieces added up. Everything worn before is chest armour;
the supplier now sells caps, helms, leggings and greaves too.

**Every weapon and armour piece has a tier**, shown after its name ("arming
sword +4"); everything so far is +0. Each tier adds one point, alternating:

- **Weapons:** odd tiers +1 accuracy, even tiers +1 damage (bows: for shots).
- **Armour:** even tiers +1 armour, odd tiers +2 max HP.

Windcatchers have no tier.

**Raising a tier (v0.76.0):**

- **At the smith:** ask him to work on your gear. Any tier, for materials
  from your pack and a fee in shards (15 × tier^1.5: 120 for +4, 475 for
  +10). Up to +3 it always takes; after that the odds fall (95% for +4, 65%
  for +10, 35% for +20, never below 10%). If it fails, the materials are
  lost but the fee isn't taken. **Past +20 a failure can destroy the piece**
  (5% at +21, 5% more each tier, up to 75%); the window asks first.
- **At home, up to +3:** materials only, no fee, and the materials in your
  home chest count too. The Bytorsskug house takes a **forge**, the Ingenfjel
  house a **workbench**; the Towerway stead has room for neither.

**Traits (v0.77.0):** each time a piece reaches +5, +10, +15 and so on, it
takes on a trait from its type's pool, never the same one twice: Keen (+5%
critical chance), Bloodletting (10% chance to bleed), Hooded (creatures
notice you less), Pocketed (+2 carrying slots) and so on. A trait only works
while the piece is worn or wielded. The item windows list them.

**The materials pouch** (the supplier, 25): one slot in your pack, and up to
eight kinds of material ride in it without taking any more.

What it takes: the piece's two material families (see below), more of them
with each tier, adding the uncommon kind from +7 and the rare from +14. A
raised piece is worth more (the materials put into it); a shop that buys one
sells it on at its tier.

**Materials come in five families, each in three tiers** (common, uncommon,
rare), the rarer from tougher creatures: hide (rough hide, thick hide, brute
hide), bone (bone, tusk and antler, wyrm fang), chitin (chitin plate, crawler
carapace, horror plate), metal (iron scrap, black iron, sentinel stone) and
fibre (sinew, vinewood, wyrm sinew). Each weapon type and armour slot is made
from two families (`data/gear.json`).

## Bounties, scouting and requests

Two more ways to earn shards:

- **Bounties and scouting** (the bounty board, `¶`, front right of the guild
  hall, or ask the clerk): four postings, new every Reckon, each at a place
  (three words). A **kill bounty** marks one creature that waits in the
  place's deepest area; kill it. A **find bounty** names a broken artifact
  lying somewhere in the deepest area; bring it to the clerk. **Scouting**
  asks you to reach a certain area. Taking one teaches you its words; your
  rank decides which you may take. Hold up to two at a time. Collect the pay
  from the clerk; the Guild takes no dues from it.
- **Requests** (the notice board, `¶`, in the plaza): people of Bytorsskug
  want a particular kind of artifact, or any of a given rarity, or materials,
  and pay well over what the shops do. For a particular kind, you'll need to
  have identified it. Some are **errands**: something lying at a place, which
  teaches you its words. Talk to whoever asked to hand it over.

Requests count as earnings for Guild dues; bounty and scouting pay doesn't. The numbers
are in `data/work.json`.

## Guild dues

On the first Pulse of each Judgment the Guild is owed a share (20%) of the
shards you've earned since the last dues: shards picked up, and what you got
from selling and consigning. Pay the guild clerk in the hall. Until you've
paid, the contracts board is closed to you (the bounty board and the
Wayfinder aren't). What you owe shows in the
side panel. The share is in `data/guild.json`. Guild pay (bounties, scouting,
field notes) owes no dues. The character sheet shows everything you've earned
this Judgment and the **dues so far**: what you'd owe if the Judgment turned now.

## Supplies

Use these from the inventory (`u`):
- **Torch:** in a dark place, +3 light for 300 turns. It's fire, so it works
  without a windcatcher. One burns at a time; if an artifact gives more light,
  that counts instead. It goes out when you get home.
- **Ration:** heals 1 HP a turn for 10 turns. One at a time.
- **Healing draught / tonic:** heals at once.
- **Rope:** on a hunt, takes you straight back to the trail home. If you have
  the artifact, the hunt is complete; if not, you're asked whether to give up.

## Tower Artifacts

Every hunt is for a Tower Artifact, and they're almost always broken. Each
has a **rarity**: Common, Uncommon, Rare, Very Rare, Legendary or Unique.
Rarer ones turn up on more dangerous contracts.

**Identifying.** Until you identify a broken artifact you see only what it
looks like ("broken brass device") and its rarity. Select it in the
inventory and press `u` to study it (one turn). Your **Identification**
rank is the highest rarity you can identify: rank 1 Common, up to rank 6
Unique. Studying an artifact one rarity beyond you fails, but still teaches
you. Each artifact teaches you once per rank. Acumen above 10 makes practice
count for more. Once identified, every artifact of that kind is known to
this Hunter.

**Skill ranks.** Practice raises Identification to rank 2 by itself. After
that, a full practice bar means you're ready, and the artificer trains the
next rank for shards (Training tab). `k` shows your skills.

**The artificer's workshop** is near the plaza. Walk into the artificer:
- **Repair** (`r`): pay the repair fee and get the working artifact back.
  Repairing reveals what it was.
- **Sell broken** (`b`): the artificer buys it as it is, for a small price.
- **Consign** (`c`): the artificer repairs and sells it. You pay your half of
  the repair fee first, then you're paid half the working price at once
  (shown as "-13, +36"). If you can't pay your half, sell it broken instead. If
  you haven't identified it, you won't know how much until you're paid.
The window shows what you pay with a minus and what you're paid with a plus.
- **Sell a repaired one** (`b` on a working artifact in your pack): half its
  sale price. It goes up for sale in the workshop. Take it off first if it's
  equipped.
The artificer quotes the fee and the broken price by rarity alone, and won't
say what an artifact is until it's repaired. Selling and consigning ask first.

**Working artifacts** only work while **equipped in an artifact slot**. You
have three, separate from your bag: equipping (`e` in the inventory) takes the
artifact out of the bag and into a slot, so the bag limit and the slots are
two separate limits. The equipment window (`e`) shows them; on a slot, `e`
takes it off, `u` uses it, and `Enter` picks one from the bag. **Since v0.69.0
your weapon, armour (head, chest, legs) and windcatcher are out of the bag too**, in their own
slots, so they don't take bag room. Equipped artifacts give
more light in dark places, armour, accuracy or evasion, or can be used (heal,
or map the area you're in). Used ones recover before each hunt.

**Since v0.101.0 there are 63 kinds** (50 new, all placeholders). A lasting
effect can now be anything a talent or a gear trait does (sight, telling blows,
max HP, carrying room, healing sooner, more materials or shards or experience,
artifacts with more uses...), and some work off a hunt too: better prices,
quicker rest, quicker travel and fewer meetings on the Brisering, more from
foraging, fish biting more. **Some cost you:** a dial that ticks so loud
creatures notice you, coils that eat Jodebris, a cup that drinks your blood.
**New uses:** step away from what's hunting you, a white flash that blinds,
a ward of armour, stop bleeding and poison, hear what's in the area, point to
what you came for, back to the trail home, make what's hunting you forget you,
a cloud of smoke, a burst against everything beside you, refill your
windcatcher, and (off a hunt) shed rest you owe. One ward costs blood to use.
Four new looks for broken ones join the coil: bone charms, crystal shards,
little cages and metal wheels.

**The guild stash** is a chest in the guild hall's middle back room. Walk into
it to move things between your pack and the stash (60 slots; a stack is one
slot). It belongs to the hall, not to you: when a Hunter dies, the next one
inherits it.

**Jodebris and windcatchers.** Artifacts run on Jodebris, the Chorus Winds.
In Bytorsskug they just work. Artifacts with a **limited number of uses** (the
astrolabe's map, the mending engine's healing) hold enough Jodebris of their
own to do their work anywhere, and using them draws nothing from a windcatcher.
Their **lasting effects** (light, armour, accuracy, evasion) are another matter:
out on a hunt, in the miasma, those do nothing
unless you have a **windcatcher** equipped (`e` in the inventory) with
Jodebris left. While one is equipped, a **JB** bar shows under your HP (just the bar:
how much is left is never given as a number). On a
hunt it drains 1 per turn; at a quarter it warns
you, and when it's empty your artifacts go still. It refills when you get
back to Bytorsskug. Windcatchers are rare finds on dangerous hunts, or the
artificer sells a lesser one (Buy tab) for a high price.

All of this is data: `data/rarities.json` (prices by rarity),
`data/appearances.json` (what unidentified artifacts look like),
`data/items.json` (each artifact and its working form), `data/skills.json`
and `data/workshops.json`.

## Saving

The game opens on a title menu: **New Game**, **New Hunter**, **Continue** (from
the autosave; the menu starts here when there is one), **Load game** or **Quit**.

- **New Game** is a factory reset: a fresh world and a fresh Hunter, as if the game
  had never been played. If there's an autosave it asks first, since the autosave
  (Hunter and world) is wiped; games in save slots are kept. Then the **opening
  crawl** rises up the screen (`data/crawl.txt`, the user's text; any key speeds it up, Esc skips).
- **New Hunter** starts a fresh Hunter in the autosave's world. The current Hunter
  simply vanishes, with no place in the Hall and everything they carry lost (it asks
  first). To leave properly, **retire** at the guild clerk instead: the Hall of
  Hunters, your gear to the stash, your shards to the next Hunter.

- **Autosave:** whenever you quit (including closing the window), set out on
  a hunt, move between areas, or come home. Quitting mid-hunt saves the hunt
  exactly as it is.
- **Three save slots:** `Esc` → *Save game*. You can only save manually in a
  safe place, like Bytorsskug (maps with `;safe=yes`). Out on a hunt, you rely
  on the autosave.
- **Permadeath:** when a Hunter dies, the autosave and every slot holding that
  Hunter are deleted. Slots holding other Hunters are kept.
- Saves are small files in the `saves/` folder (`autosave.json`,
  `slot1.json`…). Delete the folder to start completely fresh.

## Hunts

Hunts leave from **the Wayfinder**, the great artifact in the plaza (`▓`).
Walk into it and choose **three words**: a **danger** word (how dangerous, how
many areas deep), a **land** word (caves, ruins, forest, mountains, plains,
grassland or marsh; some lands roll a different terrain for each area) and a
**feature** word, a noun (Daybreak or Midnight, a swarm or silence, a hoard,
letters, a favoured creature, and more). **The same three words always lead to the same place**:
the same layout every time, though what's in it is new each trip. `←→`
choose the slot, `↑↓` the word, `Enter` go. A slot left on "(anything)" lets
the Wayfinder choose from the words you know. Danger and
land words are adjectives or verbs, and a place can't have two verbs
([Hungry][Tangled][Victory Lap] is fine; [Singing][Listing][Ideas] isn't).

You start knowing a few words. You learn more from the Guild's boards (a
contract or job teaches its words), as you rise in rank, from the story, from
the odd writing (if your Scholarship can read it), from townsfolk's errands on
the notice board (they name a place, and you learn its words), and now and
then from a rumour in the plaza (ask "Heard anything lately?").
Words belong to the city: a new Hunter keeps them. Your rank limits how
dangerous a danger word the Wayfinder will take.

**Lit or dark** (v0.93.0). A place lies out beyond the Brisering in its land's
direction from Myligast (the way you come out when you leave it). Under the
open sky it's **lit** when its half of the Overland faces the star: south of
Myligast in the Light Duel, north of it in the Dark Duel. So in a Light Duel
the northern mountains are dark and the southern forests lit, and some places
east and west lie either side of the line. Sheltered lands (caves, tangled
woods, sickly bogs, the Broken ruins) are always dark, and a few feature words
fix the light whatever the Duel (Daybreak lit, Midnight dark). In the dark you
see only as far as your light; some creatures turn up only in the dark, some
only where it's lit. The Wayfinder's screen tells you which a place is now.

**Contracts** are posted on the **contracts board** (`¶`) in the guild hall:
"Go to [Restless][Green][Daybreak] and retrieve the broken brass device…". Take
one (one at a time); then, at the Wayfinder, its words are chosen for you (or
press `c`). The board changes every Pulse.

A hunt is a chain of generated areas. Find the way deeper (`»`) to go on,
or the way back (`«`) to return; areas stay as you left them while you're
there. **Every place has a find** (`☼`) at the far end of its last area; on a
contract, it's the contract's target. Bring it back to the trail home (`≡`)
in the first area to finish (the Guild doesn't pay for hunts; you keep what
you find). Stepping onto the trail home without it asks whether to head back
anyway; a contract stays yours to try again.

**The hunt line** (v0.71.0) runs across the top of the map on a hunt:
`≡ ═════♦═════♦─────♦───── ☼ L   / ██████░░░░`. The trail home, then one
segment per area, split by shards: the areas you've reached fill in, the one
you're in and those before it lit, deeper ones you've come back from half-lit.
At the end is what you came for, dim until it's in your pack, then a mark for
each bounty here, dim until it's done. On the right, while a torch burns, its
bar burns down (torches no longer show in the info panel).

## A home of your own

A Hunter can buy **a home**, one at a time, from **the property dealer**
(Nalka Broker, a placeholder, in an office east of the plaza):

| Home | Price | Takes | Its draw |
|---|---|---|---|
| The house in Bytorsskug | 3000 | bed, chest ×3, trophy shelves ×3 | a few streets from the guild hall and the Wayfinder |
| The house in Ingenfjel | 1500 | bed, chest ×3, trophy shelves ×3 | out in the village, by the stables and the great boga circuit |
| The Towerway stead | 600 | bed, chest, trophy shelves | cheap; a short walk west of the west gate |

A home starts bare. Buy improvements from the dealer (the Improvements tab):
- **Bed** (walk into it): sleep a Pulse, heal fully and mend every minor
  injury. Serious ones still need the healer.
- **Chest**: your own storage, apart from the guild stash (10, then 20, then 30).
- **Trophy shelves**: any trophy you want to keep, record or not, counted one
  each however big (4, 8, 12).

Moving: buying another home sells the old one back for half what you paid;
its improvements stay with it, and what's in your chest and on your shelves
comes with you (boxed up until the new place has a chest and shelves with room).
Your home belongs to the world, like the stash: the next Hunter moves in.

**Ingenfjel and the stead** are walkable places on the Brisering: walk into
their landmark (Ingenfjel's village, or the stead just north of the Towerway)
to go in, and onto the gate to come back out. Ingenfjel is only a piece of the
village for now; its stables and circuit are for later. Travel-to (`t`) knows
"your home". Prices and sizes are placeholders.

**Forge and workbench:** the Bytorsskug house takes a forge (raise weapons and
armour to +3) and a workbench (repair Common artifacts); Ingenfjel's workbench
does both (walk into it and choose); the stead has room for neither.
Repairing at home costs no shards but takes a Pulse, and you need to know
what the artifact is first (study it with `u`). Rarer ones go to the
Artificer. Broken artifacts in your home chest count.

## The Brisering

The **city gates** (`∩`) lead out into **the Brisering**, the land within 99 km
of Myligast where the Chorus Winds hold the miasma back. It's one persistent
map, a cell to every half kilometre across (and a kilometre down): the
mountains lie north of the city, towards Myligast; ruins to the east; forests
to the south and west, where the Towerway runs off to the west. Myligast
stands at the centre, visible from anywhere. Walking takes time: a Pulse for
every 50 steps, a step north or south counting as two, so about every 25 km
(`data/brisering.json`). What you've seen stays on the map.
Artifacts work freely out there, and windcatchers stay full. Two villages
stand out there (`⌂`), not yet open: **Igerste** near the eastern edge, at
the end of the east road, and **Ingenfjel** south-west of the city, beside
the Overland's largest boga circuit (`∙`). Walk onto one
of the city's gates (`∩`, beside its walls `▓`) to go back in, or use
travel-to (`t`). There's nothing else out there yet.

The map is built by `tools/brisering/build_brisering.py` (it overwrites
`data/maps/brisering.txt`).

## Fishing (v0.94.0)

**The Watermen and Anglers' Guild** keeps a **tackleman** in the house nearest
the river, west of the plaza: rods, bait and lures, Angling lessons, and he
buys fish by weight. Fish in the city river, or out on the Brisering's river,
lakes and ponds. And out in the miasma, on a hunt (see below).

1. **Cast** (`r`): with a rod or hand line and some bait in your pack. Aim at
   water within your rod's reach (`Tab` cycles the water you can reach, `b`
   changes the bait), Enter. Look (`x`) at water to see what it is: the
   kind of water, how deep (shore, shallow, deep), and lit or dark.
2. **Wait** (`.`). Watch the log for tells. Some mean nothing. When the float
   goes under, **strike** (Enter or space) within a turn or two, or it's gone,
   perhaps with your bait. Strike at nothing and you put the fish down for a while.
3. **The fight.** Each turn: **reel** (`r`) to bring it in, **hold** (`h`)
   to tire it, **give line** (`g`) to ease the strain, or **steer** (`a`/`d`
   or the arrows) away from a snag. Watch the **tension**: past what your rod
   can take, the line snaps (a lure goes with it). Give line too long and the
   hook falls out. Let it run too far and it strips your line. Reeling into a
   thrash can tear the hook free; a fish veering toward a snag must be steered
   the other way. Fish of a tier up to your **Angling** rank show what they're
   about to do; from rank 3, every fish does. `c` cuts it loose.
4. **Landed:** keep it (Enter) or let it go (`x`). A fish weighs what it weighs:
   sell it to the tackleman (by the kilo), or keep it. Live by it (more than
   half of your last 1,000 shards) and you're an **Angler**.

**What bites** depends on the water, the depth, the bait, and the light: a
water's light follows the Duel (south of Myligast is lit in the Light Duel,
north in the Dark Duel), so the northern lakes hold different fish from the
southern ones, and swap when the Duel turns. Ask the tackleman what's biting.

**Every water is its own** (v0.97.0). Each Brisering lake has a name, and
not every fish lives everywhere: some keep to one side of Myligast (the cold
northern lakes, the southern ones), some live in only some lakes or ponds, and
a few keep the calendar: the Emu dace rises only on Emu, Neu's carp only on Neu,
and the duelfish only in the holiday Pulses between the Duels. **Waters can be
fished out:** every fish you keep comes out of that water, and they come back
a few Pulses at a time (the small ones quickly, a great lakeback only after
a Reckon or so). Releasing a fish costs the water nothing. Look (`x`) at a water
to see whether it's been fished hard.

**Fishing the miasma** (v0.98.0). On a hunt you can fish an area's water:
marsh water, cave pools and the pools of other lands. The fish there are the
miasma's: twice-eyed, glass-scaled, a carp that hums like the Wayfinder, fish
that **lurch** to somewhere they can't be. The place's danger word decides how
big they come (up to a tier above it), and the area's own light decides what
rises. Nothing waits while you fish: the splashing of a fight can wake what's
sleeping nearby, and anything awake that comes within a few steps makes you
drop the line. Some fish **drag**: hold a hookjaw eel or a mire king hard on a
run and it pulls you in after it. Land a hookjaw and it may tear free on the
bank and come for you. **Gut** a fish where you stand (`g` once it's landed)
to see what it swallowed: shards, now and then a broken Tower Artifact, or a
message in a bottle that names a Wayfinder word. Two **artifacts** help: a
humming bobber and a stillwater spool, worn in artifact slots like any
artifact (so in the miasma, only with a windcatcher). 53 fish in all.

**Collections** (v0.99.0). The **Angler's Log** (`p`) lists every kind of fish
by water: one you've had on the line is *hooked*, one you've landed is
*caught*, and after five you *know* it (the log then says where, how deep, in
what light and on what bait it bites). It's yours: it goes with your Hunter.
Land every kind in a kind of water (the city river, the river, the ponds, the
lakes, each of the miasma's waters) and the Watermen and Anglers send a reward
of shards and tackle, once. The tackleman keeps the Guild's **record book**:
have him weigh your catch, and a new heaviest of its kind pays. Every lake,
the city river and the Brisering's river hold one **named fish** that the
anglers talk about ("Old Setly"): a big kind of fish at twice its size,
harder to hook and to hold, caught only once in all the world. The tackleman
sometimes tells you where one is. A home in Bytorsskug or Ingenfjel can have a
**fish tank** (from the property dealer) for the fish you're proudest of.
**The anglers** (v0.100.0). More of the Watermen and Anglers' Guild: the
**fishmonger** (the next house to the river) buys whole fish for more than the
tackleman, sells fish dishes, fillets and scales, and always has a notice up on
the plaza board for some fish. Other townsfolk post **"fresh catch wanted"**
requests too, some for a fish of at least its usual weight. **Gut** a fish
(`g` as you land it, or `u` on one in your pack) for **fillets**, **fish
scales**, an eel's **skin**, **bone** from a big one, and now and then a
**pearlstone**. Scales, skin and pearlstone are a new material family,
**scale**, that the tackleman works into floats and line. Cook fillets at a
Brisering camp: **grilled fish** (the best healing over time), **fish stew**
(better fed than hunter's stew) and **fish broth** (heals, stops bleeding and
poison). Nobody eats miasma fish. Three talents for anglers: Patient Angler,
Quick Strike and Fishwise. An **angler** of the Guild, on the bank by the tackle
shop, runs its **contests**: the **Holiday Contest** through the four holiday
Pulses after each Duel (at the city river after a Light Duel, the Brisering's
river after a Dark one), and a **weigh-in** at the city river in the first
Cycle of each Reckon. Each is for one kind of fish: catch it at that water while
it's on and have her weigh it (you keep it; the entry fee is paid at your first
weigh-in). When it's over, the heaviest wins, against the Guild's anglers and
your fellow Hunters; she keeps your prize until you come for it.
**Bait:** worms (dig them with `g` in soft ground by the water, or buy them),
grubs, dough, and a spinner lure that isn't used up. Angling teaches itself to
rank 2; the tackleman trains beyond.

**Tackle** (v0.96.0) has five slots of its own, at the bottom of the
equipment window (`e`): **rod, reel, line, hook, float**. Only a rod is
needed (a rod in your pack will do); without the rest you fish with the rod's
own cord, a small hook, and line pulled in by hand.
- **Rod** (hand line, cane, ash, lacquered): reach, and the strain it takes.
- **Reel** (wooden, brass, geared): line won back with each reel, drag that
  eases a running fish, and how much line you have.
- **Line** (hemp, gut, silk): adds its strength to the rod's; the thinner it
  is, the less the wary fish see it (more so in lit water).
- **Hook** (small, medium, large, barbed): match it to the mouth. Too big and
  small fish slip it at the strike; too small and big fish tear free.
- **Float or sinker:** a float gives you a turn longer to strike (a quill
  float shows false tells for what they are); a sinker gets your bait down to
  deep water. Without a sinker, your bait never reaches the deep.
The cast window sums up your rig. The tackleman raises tackle a tier at a time
like the smith does weapons (materials and a fee), and every fifth tier brings
a trait from its own pool. A **tackle box** carries six kinds of bait and lure
without taking room in your pack.
The fish, the numbers and the anglers' lines are placeholders
(`data/fish.json`; design: `claude/design-fishing.md`).

## Combat

**Weapon skills** (v0.55.0): Blades (swords), Axes, Hafted (picks, mauls),
Brawling (bare hands) and Marksmanship (bows). Every blow practises the skill of
the weapon in hand (a hit counts double); you teach yourself to rank 2, and the
trainer in the guild hall's training corner trains the rest. Each rank above 1
adds 1 to your accuracy with it, and ranks 3 and 5 each add 1 damage. Rank 3
brings a passive technique, rank 5 one you ready with `z` (no time; it rests 20
turns after use):

| Skill | Rank 3 | Rank 5 (`z`) |
|---|---|---|
| Blades | Riposte: a creature's miss is answered at once | Lunge: +4 accuracy, double damage dice |
| Axes | Cleave: a killing blow carries on into another creature beside you | Rend: it bleeds 1 a turn for 5 turns |
| Hafted | Crush: your blows ignore 1 armour | Stagger: it loses its next 2 turns |
| Marksmanship | Steady hand: no accuracy lost to distance | Aimed shot: +4 accuracy, double damage dice |
| Brawling | Quick hands: your first blow at each creature takes no time | Throw: knocked back a step and dazed a turn |

All numbers are placeholders (see `claude/design-progression.md`).

**The Guild's works** (v0.60.0): the Guild improves its hall, project by
project, paid for by dues (yours, and a trickle from other Hunters). Ask the
clerk "What is the Guild building?" to see every project, which one the Guild
is working on (`»`), and how far along each is; you can pay into **any** of
them (←→ how much, Enter to give). Finished work changes the hall and lasts
for every Hunter after you:
- **The stash room** (I, II): 20, then 40 more stash slots, and more chests.
- **The quartermaster:** a Guild storekeeper in the stash room, with more supplies.
- **The training corner** (I, II): training costs 10%, then 20% less.
- **The infirmary** (I, II): the healer charges 20%, then 40% less; minor injuries mend sooner.
- **The dormitory** (I, II): the rest after a hunt is 15%, then 30% shorter.
- **The archive wing:** field notes pay half again; the bestiary fills in after 3 kills.
- **The Wayfinder study:** a scholar who teaches you a word you don't know (60 shards, once a Cycle).
- **The armoury:** every new Hunter starts with an arming sword (or a longbow) and a studded jerkin.

A brass plaque by the hall's door (`■`) names who paid for each. Costs and
effects are placeholders (`data/guildworks.json`).

**Calling bonuses** (v0.59.0): once the weapon skill of your calling (your
middle name, from the weapon you use most) reaches rank 3: Fencer +1 evasion,
Hewer +1 damage, Breaker 1 more armour ignored, Archer +2 bow range, Brawler +1
accuracy, whatever's in your hand.

**Knowing your prey** (v0.59.0): your own kills of each kind of creature. At 10,
+1 accuracy against that kind; at 25, +1 damage too. The character sheet lists
them, and the look command says when you know a creature's ways.

**Bargaining** (v0.59.0; Acumen; the supplier trains it): the supplier and the
artificer deal 3% better a rank above 1, both ways (you pay less, they pay
more, repairs cost less). Every trade is practice.

**Talents** (v0.58.0): at levels 3, 6, 9 and every third level after, you're
offered three talents drawn at random from a pool of 50 (`data/talents.json`)
and keep one, like a run upgrade. Some build on others (Executioner needs Keen
Edge) or on an attribute (Stout needs Fortitude 12). The choice opens when
you earn it; Esc puts it off (the same three wait for you; `n` brings them back,
and the side panel reminds you). Talents are your Hunter's own and go with them.
They range from the plain (+1 armour, +5 HP, +3 pack slots, +1 to an
attribute) to the particular (Second Wind, Bloodthirst, Vengeful, Duelist,
Lucky, Guild Darling, Wayfarer...). The character sheet lists yours.

**Attunement** (v0.57.0; Tenacity; the artificer trains it): your windcatcher
drains 10% slower a rank above 1; at rank 3, artifacts with limited uses get one
more use each hunt; at rank 5, a fourth artifact slot. Practice: using
artifacts, and moving between areas on a hunt with Jodebris in your windcatcher.

**What the attributes are for** (v0.57.0; there are no spells, so Acumen and
Tenacity lost "spell power" and "mana"): each also speeds practice in its skills.
- **Physicality:** melee damage and carrying; Axes, Hafted, Brawling, Harvesting.
- **Celerity:** accuracy and dodging; Blades, Marksmanship, Stealth.
- **Fortitude:** hit points and healing; Survival.
- **Acumen:** understanding what you find; Identification, Scholarship, Medicine, Tracking, Bargaining.
- **Tenacity:** shaking off being dazed (a turn sooner per point above 10, 3 turns at least); Attunement.

**Field skills** (v0.56.0), for hunting rather than fighting:
- **Tracking** (Acumen; the trainer): creatures leave tracks (`"`) where they've
  walked, lasting 10 turns a rank. Rank 2: entering an area, you sense roughly
  how many creatures it holds (the number at 4). Rank 3: a marked bounty shows on
  your minimap. Rank 4 and up: creatures near you show on it, unseen. Practice:
  entering new areas.
- **Stealth** (Celerity; the trainer): a creature that sees you notices you 85%
  of the time at rank 1 (each turn); each rank after, 10% less (30% at least). A blow at a creature that hasn't noticed
  you gets +2 accuracy and +1 damage per two ranks.
- **Harvesting** (Physicality; the smith): creatures leave materials 5% more
  often a rank, and one more of each at rank 5.
- **Survival** (Fortitude; the healer): a shorter rest after hunts (10% a rank),
  rations that mend for longer, torches that burn longer, and from rank 4
  bleeding and poison that last half as long.

Walk into a creature to attack it. Creatures that see you come after you;
on their turn, one next to you attacks.

- **Hitting:** 65% against an equal opponent, +5% per point your Celerity
  beats its evasion (or −5% per point below), between 5% and 95%.
- **Damage:** your weapon's dice (bare hands 1d3) plus a Physicality bonus
  (+1 per 2 points over 10), minus the target's armour, at least 1.
  Creatures hit you the same way, minus the armour you wear.
- **Healing:** draughts (`u` in the inventory), slow natural recovery (faster
  with Fortitude), and you come home from a hunt fully healed.
- **Fainting and death:** a hunt starts with no faint in hand. **Reaching
  a new area earns one** (you've marked the way back, so you can be found),
  up to your limit (`faints_allowed` in `data/player.json`, plus talents and
  traits); the panel shows "Faints: 1/1". Drop to 0 HP with a faint in hand
  and you're knocked out and come to at the trail home, healed. Drop with
  none, and the Hunter dies for good; a new Hunter starts in the guild hall.
- **Caravans on the Towerway** (v0.92.0): caravans travel between the
  Brisering's western edge and the city's west gate. Talk to one to trade (each
  carries its own goods from the west, and buys supplies and materials), to walk
  along with it (nobody on the road troubles you in its company), or to hire on as
  a guard as far as the end of its road: paid if you were with them, half if
  raiders made off with a crate.
- **Foraging and camps** (v0.91.0): berry thickets, herb patches and mushroom
  rings grow across the Brisering (stand on one and press `g`; they grow back).
  Camps sit every 20 km along the roads (walk into the fire): cook hunter's stew
  (eat it before you set out and your next hunt starts well fed, with more max
  HP), herb broth (heals, stops bleeding and poison) or trail cakes; sleep a
  Pulse by the fire; or listen to the travellers, who sometimes know a word.
- **People on the road** (v0.90.0): the walk home isn't always quiet. Highwaymen
  ask a toll on the roads, deserters and Hunters gone bad waylay anyone coming in
  rich from the edge, and hungry people ask for food. Pay, talk them down, stand
  your ground, run, go round, or fight. The roads are quicker than open
  country (where every step counts half again toward the next Pulse) but watched more,
  and a full pack draws them.
- **The walk home** (v0.89.0): the Wayfinder sends you out but can't bring you
  back. The trail home brings you out at the edge of the Brisering, on the side
  that matches the place's land, about 4 or 5 Pulses' walk from Bytorsskug
  (travel-to, `t`, walks you to a gate). A contract is done only when you
  report it to the guild clerk: talk to the clerk with what it asked for.
  Bleeding and poison keep running on the road, and a Hunter can die out there.
- **Recovery contracts** (v0.85.0): a Hunter who falls out there leaves their
  pack where they fell. "Bring home [name]" contracts on the Guild's board send
  you after it: your own fallen Hunters, rivals who died, or Hunters you never
  met. Bring the pack home and the Guild pays a fee and remembers them in the
  Hall of Hunters. Its shards are yours (dues apply), half its materials and
  about half its weapons, armour and artifacts go to the stash; nothing else
  survives.
- **Maps** (v0.84.0): scout a place properly (enter every area and explore
  at least half of it) and report it to the clerk with your field notes; the
  Guild's cartographer draws it. Once the Guild has built the Cartographer's
  Study, buy maps at his window off the front hall (about 100 shards): a map
  shows the whole place on every hunt there.
- **Named creatures** (v0.83.0): from danger 2 up, now and then an area holds
  a creature the Guild knows by name: "Idred the Venomous", or "Armoured Idred
  the Venomous" with two marks. Each mark changes it: venomous (its hits
  poison you), armoured, swift (it acts twice a turn), a caller (it calls
  everything near when it notices you), hulking, bloodthirsty (it heals when
  it hits). They're drawn in violet, give twice the XP, and their bodies go
  on the trophy wall's list of the named. A bounty's marked creature is
  sometimes one.
- **Callers and flankers** (v0.83.0): scavengers and thistlehounds raise the
  alarm when they notice you, waking what's near; wild dogs, thistlehounds
  and woodland stalkers go round another way when another creature blocks
  the corridor to you.
- **Creatures** are in `data/monsters.json`: stats, the area styles they live
  in, and a tier (1–4). Deeper areas and more dangerous contracts bring more
  and tougher creatures. They're all placeholders.
- All the combat numbers are in `game/combat.py`; how many creatures appear
  is in `game/monsters.py`.

Hunt areas have **fog of war**: you see only what's in your line of sight.
Places you've seen stay on the map, dim and colourless, as memory; places
you haven't are dark. The city has no fog. Any map can turn it on with
`;fog=on`.

The words are in `data/keywords.json`: each danger word's danger and depth,
each land word's style (or `styles` with weights, rolled per area), light and
area size, each word's effects, the words known at the start, and the words each
rank teaches. **Since v0.70.0 any word can carry effects**, combined across the
three: `creatures` (×), `favour`, `rarity_up`, `rarity_chance` (the prize one
rarity higher), `writings` (×), `sight` (×), `items` (extra finds in each area),
`time` (turns per step), `alert` (creatures awake and always noticing you) and
`only` (one kind of creature only).

**Terrains** (v0.70.0): caves, ruins, forest, mountains, plains, **grassland**
(open ground and wide swathes of tall grass, `ⁿ`, that you walk through but
can't see over) and **marsh** (mud, `.`, winding between black pools, and reed
beds, `ƒ`, that hide what's in them).
| Esc | Menu: resume, save, load, save and quit |

The window opens maximised and the screen fills it. The game picks the
biggest whole-number zoom (1×, 2×, 3×…) that still fits at least 64×20
cells (40 for the map plus 24 for the info panel on the right), so the pixel font stays sharp and correctly shaped. Resize the window
any time; it adapts. To change the zoom rules, edit `MIN_COLUMNS` and `MIN_ROWS` in `main.py`.

**The info panel** (right): your name, HP and Jodebris bars, level with your
rank beside it (gold) and XP, weapon, armour and shards; where you are (the
date in town, the place's words on a hunt) and anything pressing (faints left,
dues owed, a talent to choose, mending, injuries); then, off a hunt, **what
you're working on**: your contract's words (as far as you know them) and each
bounty, ticked and green when done (a contract turns green once its prize is in
hand). When the messages would be squeezed to fewer than four lines, that block
shrinks to one line ("contract + 2 bounties"); `q` has the details. Then the
newest messages (or the minimap, `v`).

## How it's organised

```
main.py               starts the game: window, main loop
game/
  tiles.py            terrain types (wall, floor, water...): glyphs and colours
  game_map.py         the grid; loads maps from text files
  entity.py           things on the map
  player.py           the player: profile, stats, inventory, shards; save/load
  stats.py            attributes, HP, levels, and the formulas behind them
  items.py            item catalogue and inventory
  screens.py          screens over the map: inventory, contract board, title cards
  hunt.py             places, contracts, and hunts (chains of areas)
  keywords.py         the Wayfinder's words and the places they make
  postings.py         the Guild's contracts board
  procgen.py          the area generators: caves, ruins, forest
  fov.py              line of sight, for fog of war
  combat.py           dice, hit chances, damage
  monsters.py         creature types and spawning
  look.py             the look command: describing what's at a spot
  saves.py            saving and loading
  shops.py            shops: buying and selling
  stock.py            limited, persistent stock for shops and workshops
  dialogue.py         townsfolk and conversations
  ranged.py           bows, arrows and Marksmanship
  explore.py          auto-explore
  travel.py           travel-to
  work.py             bounties, scouting and requests
  crafting.py         materials, the smith, commissions
  trophies.py         corpses, trophies, butchering, the trophymaster's records
  sound.py            sound effects, ambience, the Wayfinder's hum, music hooks
  injuries.py         lasting injuries, bleeding and poison, the healer
  medicine.py         the Medicine skill: bandages and poultices
  library.py          writings, Scholarship, the Academy library
  archive.py          the Guild archive: field notes, bestiary, scouting
  aging.py            ages, downtime, old age, retirement, the mentor
  story.py            quests, scenes, story talk, counters, story items
  rivals.py           rival Hunters: their lives, the guild hall, the race
  ranks.py            Guild ranks: rising, danger, privileges, debt
  artifacts.py        Tower Artifacts: identifying, the workshop, what working ones do
  skills.py           skills, practice and training
  names.py            Hunters' names
  calendar.py         the calendar: Pulse count -> date
  sky.py              light: lit or dark, by the Duel and where a place lies
  fishing.py          fishing: waters, the cast, the wait, the fight, the catch
  font.py             the extra letters (þ, Þ) and the font's charmap
  version.py          the version number
  camera.py           which part of the map is on screen
  actions.py          everything that changes the world: move, wait...
  engine.py           game state, turn counting, drawing
  input_handlers.py   keys -> actions
data/
  maps/city.txt       Bytorsskug, the city, where the game starts (232x116)
  player.json         the starting character
  items.json          every item type, including artifacts
  keywords.json       the Wayfinder's words (danger, land, feature)
  gates.json          the four city gates' names and what lies beyond
  shops.json          shops and their stock
  workshops.json      Artificers' workshops (what they sell, and stock)
  rarities.json       artifact rarities and workshop prices
  appearances.json    what unidentified artifacts look like
  skills.json         skills (Identification)
  monsters.json       every creature
  font_8x16.png       the pixel font everything is drawn with
  names.json          how Hunters' given names are built
  calendar.json       the calendar: Pulse names, sizes, starting date
  townsfolk.json      the people of Bytorsskug
  recipes.json        what the smith makes, and from what
  trophies.json       creatures' weights and sizes, quirks, record pay, the trophymaster's lines
  sounds.json         which sound plays for what, footsteps, ambience and music by place
  sounds/             the sound effects and ambience loops (WAV; tools/sound/make_sounds.py)
  music/              music: Bytorsskug's (the assistant's attempt, v0.102.0)
  injuries.json       lasting injuries (what they do, how they heal)
  writings.json       writings found on hunts (texts are placeholders)
  aging.json          ages, rest between hunts, aging, old age
  story/              the story: quests, scenes, talk (see story/_README.md)
  rivals.json         rival Hunters (numbers, callings, how they talk)
  ranks.json          Guild ranks (names, requirements, danger, privileges)
  work.json           bounties, scouting and requests (numbers)
  guild.json          Guild dues (the share)
  dialogue/           what they say (one file per conversation; see _README.md)
tools/
  make_tileset.py     rebuilds the font images (CP437 + extra letters like þ) from a font file
  city_plan/          the city plan, and build_city.py, which lays out city.txt from it
  balance/            sim.py (a bot plays hunts with the real rules) and report.py (sums it up)
  sound/              make_sounds.py: builds the sound effects and ambience from code (numpy)
```

The flow each turn: **key → Action → `perform()` → turn passes (or not) → redraw.**
Bumping a wall doesn't cost a turn.

## The font

Everything is drawn with **GNU Unifont**, a pixel font, in 8×16 cells, with the
classic CP437 character set: letters plus symbols like `♣ ≈ ° ▲` and the
box-drawing characters `═ ║ ╔`. Unifont is free to use; it's licensed under
the GPL with a font embedding exception and the SIL Open Font License.
Credit "GNU Unifont" when you release.

CP437 has no þ or Þ, so those come from Unifont too, in an extra row at the
bottom of `data/font_8x16.png` (loaded in the same charmap as CP437). To add another letter, append it to `EXTRA` in
both `tools/make_tileset.py` and `game/font.py`, then run
`python tools/make_tileset.py path/to/unifont.otf`. Any character not in
the sheet shows as a blank.

Cells are twice as tall as they are wide, like an old terminal.

## Maps

Maps are plain text files in `data/maps/`. Open one in any text editor
with a monospaced font (Notepad works) and draw. The camera follows the
player, so maps can be any size.

| Symbol | Terrain | | Symbol | Terrain |
|---|---|---|---|---|
| `#` | stone wall (built; drawn shaded ▓) | | `:` | cobblestones |
| `.` | flagstone floor | | `w` | wooden floor |
| `+` | doorway | | `-` | dirt path |
| `,` | grass | | `=` | bridge (running east–west) |
| `m` | shop floor | | `k` | workshop floor |
| `C` | guild stash (chest) | | `N` | notice board |
| `Y` | the Wayfinder (walk into it) | | `P` `J` | the Guild's contracts and bounty boards |
| `T` | tree | | `O` | well |
| `~` | water | | `G` | city gate (needs a `;gate=` line) |
| `h` | house (closed building; drawn in double lines, v0.100.2) | | `I` | bridge running north–south |
| `X` `M` `B` | (the Brisering) the miasma, Myligast, Bytorsskug | | `V` `Q` | (the Brisering) a village (Igerste, Ingenfjel), the Ingenfjel boga circuit | | `A` `^` `f` `u` `R` | (the Brisering) mountains, hills, woods, ruins, road |
| `%` | rough stone (natural; caves, dungeons) | | `@` | where the player starts |
| `c` | cave floor | | `>` `<` `H` | way deeper, way back, trail home (hunts) |

Lines starting with `;` are comments or settings. Settings so far:

- `;light=lit`: everything is fully lit (the city). (Old maps' `day` still works.)
- `;light=dark`: dark beyond the player's light (the default; for dungeons and cellars). (Old maps' `torch` still works.)
- `;title=The City`: the name shown in the side panel.
- `;fog=on`: fog of war (off unless set; hunt areas always have it).
- `;safe=yes`: a safe zone, where manual saving is allowed.
- `;npc=110,30 supplier`: a shopkeeper at that spot, for that shop in `data/shops.json`.
- `;gate=59,4 north`: the `G` at column 59, row 4 is the `north` gate (`data/gates.json`).
- `;item=44,20 shard 12`: an item lying at column 44, row 20 (both counted from 0,
  top-left). The count is optional. Repeat the line for more items.

## The character and items

- **The starting character** is `data/player.json`: name, shards, attributes and
  starting kit.
- **Items** are `data/items.json`. Each has a name, symbol, colour, kind,
  description, value, and whether it stacks. `properties` holds numbers for
  future rules (damage, healing, armour…); nothing reads them yet.
  Money is **shards** (`♦`). The `shard` item goes straight into your purse when picked up.
- **Attributes** are defined once, at the top of `game/stats.py`. Rename, add or
  remove them there. The formulas (max HP, XP per level, carrying slots) are at
  the bottom of the same file.

## Common changes

- **New terrain:** add a `TileType` in `game/tiles.py` (glyphs, colours, background), then use its symbol in a map file.
- **Change how something looks:** edit its glyphs or colours in `game/tiles.py`. List several glyphs or colours to get natural variety.
- **Something should happen every turn** (monsters, hunger...): put it in `Engine.end_turn()`.

## Versions

The version number is in `game/version.py` and shows in the bottom corner of
the side panel, on the title menu and in the window title. Saves and crash
logs record it too. While the game is in early development it's 0.x:

- **0.x.0**: a new feature or system (0.10.0 → 0.11.0)
- **0.x.y**: fixes and small tweaks (0.10.0 → 0.10.1)

To release a version: change `VERSION` in `game/version.py`, add an entry to
`CHANGELOG.md`, commit, and tag it in Git (`git tag v0.10.0`).
