# Changelog

Every version of Tower Acquisition Guild, newest first. The version number
lives in `game/version.py` and shows in the corner of the side panel.

Versions 0.1 to 0.9 were numbered after the fact, one per milestone.

## 0.76.0: Raising gear (2026-11-21)
Stage 2 of the equipment refactor (design: `claude/design-equipment.md`; the numbers are drafts).
- **The smith raises gear:** "Can you work on my gear?" opens a window listing what you wear, then what's in your pack. For the next tier it shows:
  - the chance it takes;
  - the materials, have against need;
  - the fee.

  Enter tries. Nothing takes time.
- **The rules (user), with draft numbers:**
  - **Any tier, with no ceiling.** You pay materials and a fee of 25 × tier^1.5 shards: 200 for +4, 790 for +10, 2,235 for +20.
  - **The fee is only taken if it works** (user: shards are returned). The materials are spent either way.
  - **Chance:** 100% up to +3; 95% for +4, falling to 65% at +10, 35% at +20; then 2 less a tier, never below 10%.
  - **Past +20, a failure can destroy the piece** (user): 5% of failures at +21, 5% more each tier after, at most 75%. The window asks before any try that could.
- **At home, up to +3** (user): materials only, no fee; materials in your home chest count too.
  - **The Bytorsskug house:** a **forge** (400).
  - **Ingenfjel:** a **workbench** (300), which does both (user).
  - **The stead:** neither (user).

  Bytorsskug's own workbench, for artificy, comes with that (stage 5). Walk into the forge or workbench to use it.
- **Worth:** a raised piece is worth its base value plus the materials put into its tiers, so shops pay more for it. A shop that buys one now sells it on at its tier ("arming sword +3"), where before it came back +0.

## 0.75.0: Gear tiers and armour slots (2026-11-21)
Stage 1 of the equipment refactor (design: `claude/design-equipment.md`): what upgrading will build on. Nothing can be upgraded yet; that's stage 2.
- **Armour by slot: head, chest, legs** (user: no armour classes). Your armour is the pieces added up. Everything worn before is **chest** armour, and old saves move it there. The equipment window has a row for each; the info panel shows your armour total, with a mark for each slot (∩ φ π), lit when something's in it.
- **New head and leg pieces** at the supplier (draft names): **leather cap** and **iron helm** (∩), **hide leggings** and **iron greaves** (π).
- **Every weapon and armour piece has a tier**, shown after its name ("longbow +3"); everything today is +0. Each tier adds a point, alternating (draft numbers):
  - **Weapons:** odd tiers +1 accuracy, even tiers +1 damage. A bow's tier counts for its shots, not its bash.
  - **Armour:** even tiers +1 armour, odd tiers +2 max HP.
  Windcatchers have no tier (user). The item windows show what a tier gives ("Tier +3: +2 accuracy, +1 damage").
- **Traits** are kept on a piece and saved (the pools and their effects come in stage 3).
- **Materials: five families, three tiers each** (`data/gear.json`): hide, bone, chitin, metal and fibre. Nine are new, with drops from the creatures they come from:
  - **Bone** (wild dogs, boars, pale lurkers).
  - **Tusk and antler** (thornback boars, hollow elk).
  - **Wyrm fang** and **wyrm sinew** (gravel wyrms).
  - **Brute hide** (hollow brutes).
  - **Crawler carapace** (crawlers).
  - **Horror plate** (deep horrors).
  - **Black iron** (stone sentinels, ruin stalkers).
  - **Vinewood** (strangler vines, mirebellows).

  Some creatures leave more than before: woodland stalkers and thistlehounds now leave thick hide too, and glasswings chitin plate. Each weapon type and armour slot is made from two families. What an upgrade will take is worked out already, for stage 2.

## 0.74.0: A home of your own (2026-11-21)
The user's design: a place of the Hunter's own, bought, bare at first and improved, small versions of the city's services. One home at a time; it passes to the next Hunter.
- **Three homes**, from a new **property dealer** east of the plaza (placeholder name and lines):
  - **A house in Bytorsskug** (3000): the dearest, takes everything, a few streets from the guild hall and the Wayfinder.
  - **A house in Ingenfjel** (1500): takes everything, out in the village.
  - **The Towerway stead** (600): the cheapest, a short walk west of the gate, with room for one of each improvement.
- **Improvements:**
  - **Bed:** sleep a Pulse; heal fully; every minor injury mends.
  - **Chest:** your own storage, in three sizes.
  - **Trophy shelves:** any trophy you keep, record or not, counted one each however big.
  Each piece appears in the house as you buy it; walk into it to use it.
- **Moving:** buying another home sells the old one back for half. Its improvements stay with it; your chest's and shelves' contents come with you.
- **Ingenfjel and the stead are places you can walk into from the Brisering** (bump their landmark; the gate takes you back out). Ingenfjel is a piece of the village: houses, the stables (not open yet) and the great boga circuit, seen from outside. The stead is a one-room cabin by the Towerway, now a landmark on the Brisering. What you leave in either stays.
- Travel-to (`t`) knows "your home"; the look command tells you which house is for sale and which is yours.
- Every price and size is a placeholder for a balance pass. A workbench (repairing Common artifacts) and a small forge (minor smithing) come later.

## 0.73.0: The info panel (2026-11-21)
- **What you're working on** (off a hunt): your contract's words, as far as you know them (`[?]` for any you don't yet), and each bounty you hold (the creature's letter, the thing to find, or "scout to area 3"). Each turns green when it's done (a √ for a bounty); a contract turns green once its prize is in hand. When room is short, the block shrinks to one line ("contract + 2 bounties") so the messages keep at least four lines; `q` has the details. On a hunt the hunt line shows these instead.
- **Your rank beside your level** in gold, with XP on the same line when it fits ("Lv 2 Recruit   XP 40/120"), on the next when it doesn't.
- **No more ground-underfoot line in town** ("Flagstone", "Cobblestones"): the look command (`x`) has it, and the messages get the room.

## 0.72.0: The character sheet in tabs (2026-11-21)
The sheet was one long scrolling page (about three screens on the laptop). It's now three tabs, each fitting one screen. `←→` or Tab switches between them.
- **Hunter:** your level, rank, gender and age; HP and XP bars side by side; your windcatcher's Jodebris. Your attributes sit in a grid with what's changing them ("+1 age", "-1 injury"). `↑↓` picks one, and only that one's description shows, not all five. Beside them are your fighting numbers, and under those your **condition**: injuries and how they mend, faints left on a hunt, dues owed, a talent waiting, skills ready to train.
- **Guild:** your rank and the next one, with a bar for each requirement (hunts, level, √ when met) and the fee against your shards; money earned and dues building up; how many Wayfinder words you know; field notes waiting for the clerk.
- **Calling:** your calling and what it gives you, the creatures you know best (your prey), and your talents with the level of your next one.
- Equipment and artifacts are no longer repeated on the sheet (they're in the equipment window, `e`); `e` and `k` jump from the sheet to equipment and skills.

## 0.71.0: The hunt line (2026-11-21)
- **A line across the top of the map on a hunt** (user), above the map, so nothing is covered:
  - **Progress:** the trail home (≡), then one segment per area, split by shards (♦) like the title cards' accents. The areas you've reached fill in (a lit double line); deeper areas you've come back from stay filled but half-lit; the rest are a thin dark line. A shard lights once you've crossed it.
  - **What you came for:** the prize at the end of the line, in its own glyph and colour, dim until it's in your pack and bright once it is. Then a mark for each bounty here, dim until it's done.
  - **Torch:** while one burns, its bar on the right burns down, turning orange-red near the end. **The info panel no longer shows torch turns**; the Jodebris bar stays in the panel.
- The map view is one row shorter on hunts to make room. The city and the Brisering are unchanged.

## 0.70.1: The Wayfinder's carousel (2026-11-21)
- **The Wayfinder's word columns are carousels** (user). Your three picks sit side by side on the middle row, and each column's words wheel round its pick, wrapping from the last word back to the first and fading the further they are. Each word shows once.
- **Fixed:** with the new words, the columns ran past the bottom of the window on the laptop, so some words (Verdant, Tiresome, Sundering and others) could be picked but not seen.
- Design note (user): words that do exactly the same thing are welcome. Each one leads to its own place with the same character (`claude/design-brisering-keywords.md`).

## 0.70.0: New words, new terrains (2026-11-21)
Nineteen new Wayfinder words from the user, and the terrain rework they needed. Where the user named a word without an effect, the effect is the assistant's.
- **Danger:** **Sundering** (danger 5, 3 areas), **Critical** (danger 4, 3 areas), **Combative** (danger 3, 3 areas; creatures start awake and always notice you), **Trifling** (danger 1, one area).
- **Land:** **Verdant** (grassland, by day), **Deeply Ill** (marsh, dark), **Explicit** (forest, by day, large), **Understated** (caves, small), **Historical** (ruins, by day), **Tiresome** (each area mountains or marsh, half and half), **Cardinal** (each area mountains, ruins, forest or plains: the four directions), **Ordinal** (each area caves, marsh, grassland or ruins; dark), **Old Hunter's** (forest by day; an old Hunter's leavings lie about: torches, maybe rope or a draught).
- **Feature:** **Artificer** (10% chance the prize is one rarity higher), **Conundrum** (mirebellows, far more often), **Gift Basket** (rations lying about), **Endlessness** (three times the creatures), **Gravity** (each step lets two turns pass), **Ashfall** (nothing but ashmantles, and half as many again).
- **Two new terrains:** **grassland**, with tall grass you can walk through but not see over, and **marsh**, with mud, black pools and reed beds that hide what's in them. Existing creatures live in them for now: wild dogs, scavengers, thornback boars, thistlehounds and hollow brutes on the grassland; mirebellows, hookjaw eels, lantern ticks and strangler vines in the marsh, and glasswings, ashmantles and others by night.
- **A land word can roll its terrain per area**, fixed by the words, so the same words still always lead to the same place. The Wayfinder and the archive say "mountains or marsh".
- **Any of the three words can carry effects** now, combined, not just the feature.
- The new words are learned like others: from boards, rumours, writings, errands and the Guild scholar. None are known at the start.
- Bounty boards don't post scouting for one-area places.
- Places that existed before are unchanged: same words, same place.

## 0.69.0: The equipment window (2026-11-21)
- **Equipment has its own slots** (user): your weapon, armour and windcatcher are out of the bag, like artifacts already were, so they no longer take bag room. Equipping something from the bag puts what it replaces back in the bag.
- **The equipment window (`e`)** shows everything you have on, slot by slot: weapon (damage, range), armour, windcatcher (its Jodebris bar, no numbers), then the artifact slots with what each gives. `e` takes something off, `u` uses an artifact, `Enter` picks something from your bag for that slot (and swaps), and `Tab` goes to the bag. Equipping takes a turn, as it does from the inventory.
- **The inventory (`i`) is the bag only**; `Tab` goes to the equipment window. The artifact slots moved from the inventory to the equipment window.
- Older saves load with their equipped things moved out of the bag into their slots. Retiring sends your equipped gear to the stash with the rest.

## 0.68.2: The title menu's Continue line (2026-11-21)
- **Continue** now shows the Hunter, their level and where they are ("Ylfa Fencer, Lv 3, Bytorsskug"), without the date. The date was cut short to just the Duel and the Pulse's name, which told you nothing (user). The full date is still shown when you load from a save slot.

## 0.68.1: Whisper Poet faces north (2026-11-21)
- The statue looks **north**, towards Myligast (user: from the plaza, the Tower is north, not east).

## 0.68.0: Whisper Poet's statue (2026-11-21)
- **Whisper Poet's statue** stands in the plaza, between the notice board and the Wayfinder (user's lore): the Dzuth matriarch who heard Myligast's Jodebris from the western deserts and walked alone through the miasma to Bytorsskug in Turn 134. Her road is the Towerway. Walk into the statue to read its inscription. The look command describes it, and travel-to can take you there. The facts are the user's; the wording is a draft.
- **Monuments**, for more lore in the world: `data/monuments.json` holds each one's name, look line and text, and a map places it with `;monument=x,y id`. The city builder places the statue; nothing else in the city moved.

## 0.67.3: Selda back to 20% off (2026-11-21)
- **Reverted 0.67.2**, which misread the user: Selda teaches at **20% off** the trainer's price, as the outline says. The retired-Hunter mentor stays at 25% off, up to their own ranks.
- A creature test failed now and then (since 0.64.0 a creature can fail to notice you); it now pins noticing.

## 0.67.2: Selda teaches at 25% off (2026-11-21)
- Selda taught at 25% off (a misreading by the assistant; reverted in 0.67.3).

## 0.67.1: Older saves start Chapter 1 (2026-11-21)
- **A save from before 0.67.0 now starts Chapter 1 when it's loaded** (user: their save had finished the clerk's first jobs, and the chapter only began as they ended). If the first jobs are done or were declined and the chapter hasn't begun, loading the save shows the Chapter 1 card, and the clerk has the hook.
- The story has a new event, `load`, fired whenever a save is loaded, so later chapters can catch up the same way.

## 0.67.0: Chapter 1, Three Words (2026-11-21)
The user's outline, built. The story's structure, beats, people and words are the user's; the wording is a draft.
- **Act I: Well Past Due.** The chapter follows the clerk's first jobs, or begins at once if you decline them. Selda Fencer Hunters is a Cycle and three Pulses overdue, and the clerk posts a key hunt open to every rank. Its words show as **[?][?][?]** until you learn them: one on an errand (Jokro the washer), one from a writing (the Academy library, read with Scholarship), and one from a rumour (Klubo the porter).
- **New words**, only ever taught by the story (user): **Murmuring** (danger 3), **Specter's** (dark caves), **Broken Promise** (half the creatures, 20% less light).
- **Act II: Uniquely Stranded.** Spent torches (worth nothing), a butchered body, her field notes (the clerk pays for them), a Unique artifact, and Selda, hurt and out of light, with two guardians. You carry her like a big trophy (4 pack slots; she can't be put down). If you have no rope, she gives you hers.
- **Act III: Safe Is Relative.** Lifa treats her. She retires into the Hall of Hunters and gives you her empty windcatcher. She takes a corner of the guild hall and teaches Tracking, Stealth, Harvesting and Survival at 20% off the trainer's price, up to rank 4. Her artifact goes to the stash, **story-locked**: it is never found by chance, and the artificer won't study, repair, buy or consign it. The clerk is shaken ("We should know where our Hunters go") and puts 500 shards toward the Wayfinder study.
- **The retired Hunter mentor** now teaches at 25% off the trainer's price (was half price), up to their own ranks (user).
- **Fixed:** a story effect named `hall` or `works` opened those screens instead. The new effects are named `remember` and `fund`.
- **Fixed:** "You return to the city with the Selda Fencer Hunters": a person comes home without "the".
- A scene's pages now come before any card or tip its effects bring. Writer's guide additions cover hidden words, people as prizes, story words, writings and locked artifacts, and the new effects.

## 0.66.0: The story frame (2026-11-21)
The frame the story goes in, built to the user's decisions (`claude/design-story-presentation.md`); no new plot.
- **Kinds of story**, each with its own heading: **Chapter 1: Well Past Due** (the main story), **Paralogue 4: Passing Wind** (storylets), **Character Log 7: But Why Tinkerforge?** (a person's story), and two that belong to one Hunter: **Hewer Calling: The First Axe** (callings) and **Hunter Log 1: ...**.
- **Title cards** open and close each one (heading, title, a line), and the log says when one begins or is complete. The quest log lists them in order: chapters, paralogues, character logs, callings, Hunter logs, then other quests.
- **Lines that don't repeat:** any story text can have variants. The game uses each before repeating one, and a variant can depend on the Hunter (calling, gender, age, rank, Jodebris sensitivity, how many Hunters came before, whether one of the same calling died).
- **The calendar:** story scenes can happen on dates (Turning Day, the holidays, a given Pulse, Cycle, Reckon or Judgment). The game refuses any story where a date that comes round less than once a Cycle would hold a step back (user's rule).
- **The Story So Far:** a new Hunter is shown a card recapping where the main story stands.
- **Tips** (how to play) now have their own look, a sea-glass frame titled "Tip", apart from story moments. The clerk's first jobs use it for their instructions.
- Writer's guide (`data/story/_README.md`) and a worked example (`data/story/examples/frame/`).

## 0.65.1: Sound crash fixed (2026-11-21)
- **Fixed a crash in the sound** (user: "IndexError: pop from empty list" from tcod's audio thread). 0.64.1's fix for looping sounds also emptied a faded loop's queue from the game's thread while the audio thread was mixing it. It no longer touches the queue at all: stopping a loop only clears its "play again" callback, under the channel's own lock, and lets tcod's fade do the rest.

## 0.65.0: Watch the Hunter walk (2026-11-21)
- **Auto-explore and travel-to now walk a step at a time** that you can watch (about 16 steps a second), instead of jumping to where they stop (user: disorienting, and every footstep sounded at once). Any key stops the walk where you are. Each step is still a full turn.
- Footsteps while walking like this play every other step, a little softer, so they don't patter.

## 0.64.1: The wind stops; Jodebris sensitivity (2026-11-21)
- **Fixed: the title screen's wind went on playing under everything** (user: still there on a hunt). tcod loops a sound by re-queuing it when it ends, and fading a channel out didn't stop that, so a faded loop came straight back at full volume, and every place you'd been piled up. Loops are now stopped for good when they fade (and silenced outright once the fade is over).
- **The talent "Jodebris Sense" is now "Windcatcher-Efficient"** (user: almost no one can sense Jodebris). Same effect; saves carry it over.
- **Jodebris sensitivity:** a new Hunter has a 0.1% chance of being one of the few who can hear or feel Jodebris (user). It does nothing yet; what it means is for later.

## 0.64.0: From the user's second playtest (2026-11-21)
- **Travel-to:** every place is numbered (they stopped at 9). Type a number to go; with ten or more places, a number that could start a longer one waits for the next digit or Enter.
- **Sound:** the wind is quieter, and the miasma is still: no wind in any hunt's soundscape (forest, ruins, mountains, plains), only the miasma's drone and small sounds (a strange bird, a creak, grit falling, insects at night).
- **Strangler vines** are a dusky blue, not green, so they stand out in the forest.
- **The workshop** shows what you pay with a minus and what you're paid with a plus. **Consigning** now means paying your half of the repair first, then being paid half the working price (`-13, +36`); if you can't pay your half, selling broken is the way out.
- **The side panel:** no blank lines between messages (the newest is bright, older ones alternate two greys), and no date on a hunt, so an injury or a Jodebris bar no longer squeezes the messages down to one.
- **Training window:** the skill list scrolls with the selection, and a notice shows in full (the description gives way first). "…" is no longer used where windows cut text (the font can't draw it).
- **A new rank** gets a card with what it brings, and the clerk congratulates you the next time you talk.
- **Skill pace:** weapon skills and Marksmanship need 30 practice a rank (was 12); Tracking 16 (was 8) and kills no longer practise it; Stealth 6 (was 8), and a creature that sees you notices you 85% of the time at rank 1 (was always), 10% less a rank after.
- **Injuries:** bleeding is the likeliest kind, then poison, then the rest (weights 3 : 2 : 1). New minor, tier-1 injury: **infected scratch** (poisoned; Fortitude −1).
- **Rivals bring trophies:** a rival home from a successful hunt sometimes brings the trophymaster a body; a record goes on the wall with their name.

## 0.63.0: Sound (2026-11-20)
The user's direction: the assistant makes the sounds, moody and ambient; the user makes the music (none yet); soundscapes everywhere, music only at key places.
- **Sound effects** for the interface (moving through, choosing in and leaving windows, a window opening, a popup), footsteps (stone, wood, grass, dirt), combat (your blow, a telling blow, a miss, a kill, being hit, a creature's miss, a creature noticing you, the bow, an arrow striking, techniques, a lantern tick bursting, being dazed), fainting and death, levelling, talents, rank, and the world (picking things up, shards, butchering, drinking, eating, bandaging, a torch, an artifact, rope, the stash, shards changing hands), and moments (stepping into the Wayfinder, a hunt complete or not, a bounty done, a new record on the trophy wall). All made from code by `tools/sound/make_sounds.py` (placeholders, for the user's ears).
- **Ambience** loops by place: Bytorsskug's streets, inside a building, the guild hall, the Brisering (and the title screen), and out in the miasma by land (caves, forest, ruins, mountains, plains; forest and plains have night versions), each over the miasma's low, uneasy drone. **The Wayfinder hums** when you're near it in the plaza, louder the closer you are.
- **Music:** places can name music in `data/sounds.json` (WAV files in `data/music/`); none yet.
- **The Sound window** (title menu and Esc menu): volumes 0–10 for everything, effects, ambience and music; mute; a test sound; and whether sound is working. **F2** mutes. Settings are kept in `saves/settings.json`, apart from any save.
- Sound uses python-tcod's own audio: nothing new to install. If it can't start, the game plays on silently and the Sound window says why.

## 0.62.2: More creatures at danger 4 and 5; title screen (2026-11-20)
- **One more creature in every area at danger 4 and 5** too (user), so each step up the danger ladder still adds creatures. Not balance-tested (user).
- **The title screen no longer says "Bytorsskug"** under the game's name (user).

## 0.62.1: More creatures at danger 3 (2026-11-20)
- **One more creature in every area at danger 3** (user; danger 3 was still about 81% success for the balance bot).

## 0.62.0: Balance pass 3 (2026-11-20)
Progression, stage 7 (`claude/balance-report.md`, pass 3). The user's choices after the bot's measurements:
- **Tougher tier 3–4 creatures:** +25% HP (rounded up) and +1 accuracy: deep horror 38, stone sentinel 35, woodland stalker 33, crawler 53, thistlehound 23 (tier 3); hollow brute 57, gravel wyrm 57 (tier 4). (Not the ashmantle, which can't fight.)
- **Bounty and scouting pay cut by 40%** (`bounty_pay` 0.6 in `data/work.json`).
- **The artificer pays 20% more:** selling broken, consigning and selling repaired artifacts (`artifacts.ARTIFICER_PAY`).
- **Harvesting** gives its extra material at rank 5 only (was ranks 3 and 5).
- **Injuries a little likelier:** any hit injures with chance 3% (was 2%).
- The balance bot takes contracts and bounties, hauls trophies and trains skills (`--plain` for the old bot).

## 0.61.1: Rations are ¥ (2026-11-20)
- **Rations are drawn as `¥`** (user), so `%` means a corpse. The panel's "Mending" line uses it too.

## 0.61.0: Corpses and trophies (2026-11-20)
Progression, stage 6b (`claude/design-progression.md`). The user's design; weights, sizes, quirks, pay and people are my placeholders.
- **Creatures leave their corpses**, not loose materials (all but the lantern tick, which bursts, and the ashmantle, which is smoke; a body in the water washes up on the nearest bank). The first one tells you what to do with it.
- **Butcher it where it lies** (`b`) for the materials it used to drop, at the same odds (Harvesting helps, and is practised). Or **pick it up** (`g`, after anything else lying there): in the pack it's a **trophy**, with a weight and sometimes a quirk (pale, scarred, old, runt, misshapen). Trophies take **pack slots by size** (1 to 6; the inventory and stash now count slots) and don't spoil. `u` on a trophy butchers it on the spot.
- **The trophymaster** (Pulnaþ, in a lodge by the plaza): hand him a trophy. The heaviest of its kind, or the first of a quirk, goes on the **trophy wall** (`Ω`, walk into it) with your name, and he pays: a base by creature tier, more the bigger the margin over the old record (up to 3x). Anything else he turns away. The wall is world state; a new game clears it. His pay is earnings (dues apply).
- **The butcher** (Dimam, near the plaza) breaks a trophy down for nothing: every material it has, at the most.
- Look (`x`) describes a corpse's weight and size; the inventory shows a trophy's weight, slots, quirk and the current record. Saves keep trophies (pack, stash, floor) and the wall.
- Fixed a stale test (bows: the hall's example bow went in v0.54.0).

## 0.60.0: The Guild's works (2026-11-20)
Progression, stage 6a (`claude/design-progression.md`). The user's design; costs, effects and places are my placeholders.
- **The Guild improves its hall, project by project.** Dues paid (by you, by labour, and a trickle from rival Hunters home from a hunt) go to the project the Guild chooses (its focus). **You can pay into any project** at the clerk ("What is the Guild building?"): ↑↓ a project, ←→ how much (10 to all you have), Enter. Paying in isn't earnings and owes no dues.
- **Eight projects**, some in two tiers: the stash room (+20/+40 slots, more chests), the quartermaster (a Guild storekeeper in the stash room), the training corner (training −10%/−20%, dummies), the infirmary (healer −20%/−40%, minor injuries mend 25%/50% sooner, cots), the dormitory (rest −15%/−30%, bunks), the archive wing (notes pay half again; the bestiary fills in after 3 kills; shelves), the Wayfinder study (a scholar teaches a word you don't know, 60 shards, once a Cycle), the armoury (new Hunters get an arming sword or a longbow and a studded jerkin; weapon racks).
- **The hall changes** as each tier is finished, and stays changed for every Hunter after (world state).
- **A brass plaque** by the hall's door names who paid for each (walk into it to read it; the look command points to it).
- New people: Palboj Quartermaster Hunters and Etly Scholar Hunters (placeholders).

## 0.59.2: [ and ] page; j and k retired (2026-11-20)
- **`[` and `]` page up and down** in every scrolling window (the message log, the character sheet, the skills window, the key reference), as PgUp and PgDn do (user).
- **`j` and `k` no longer move up and down in lists** (user), so `k` is only the skills window. Arrows, `w`/`s` and the numpad still do.
- The key reference lists paging, and its notes on the stash and the clerk match the new guild hall.

## 0.59.1: The skills window (2026-11-20)
- **Skills have their own window, `k`** (user: the list was getting long). Grouped: Weapons (Blades, Axes, Hafted, Brawling, Marksmanship), In the field (Tracking, Stealth, Harvesting, Survival, Medicine), Knowledge and trade (Identification, Scholarship, Bargaining) and Jodebris (Attunement), each with its rank, practice bar and what it gives. Scrolls; Esc or `k` closes.
- The character sheet keeps a line pointing to it, and says how many skills are ready to train.
- Acumen's description now names Bargaining among the skills it speeds.

## 0.59.0: Calling bonuses, knowing your prey, Bargaining (2026-11-20)
Progression, stage 5 (`claude/design-progression.md`; details are my placeholders):
- **Calling bonuses:** once your calling's weapon skill reaches rank 3, a small passive whatever's in your hand: Fencer +1 evasion, Hewer +1 damage, Breaker 1 more armour ignored, Archer +2 bow range, Brawler +1 accuracy.
- **Knowing your prey:** every creature you kill counts toward knowing its kind (the Hunter's own; saved). 10 kills: +1 accuracy against it (blows and arrows); 25: +1 damage too. The look command says "You know its ways".
- **Bargaining** (Acumen; trained by the supplier): 3% better prices a rank above 1 with the supplier and the artificer, both ways: buying, selling, repairs, selling broken or repaired artifacts, consigning. Every trade is practice.
- The character sheet has a **Calling and prey** section (your calling's bonus, or what it'll be; your kills of each kind and what they give), and Bargaining's prices under Skills.

## 0.58.1: The sheet's dues share (2026-11-20)
- Fixed: with Guild Darling, the character sheet still said dues were 20% of earnings (the dues themselves were already right, at 15%). It now shows the share you actually pay.

## 0.58.0: Talents (2026-11-20)
Progression, stage 4. The user's direction: a big pool, three offered at random at each talent level, keep one, like run upgrades in Vampire Survivors. The pool, names and numbers are my placeholders.
- **50 talents** in `data/talents.json`: combat (Thick Skin, Nimble, Steady Eye, Heavy Hand, Eagle Eye, Broadheads, Long Draw, Keen Edge, Executioner, Bloodthirst, Second Wind, Last Stand, Vengeful, Duelist), toughness (Tough, Stout, Hard to Kill, Iron Will, Clear-Headed, Burr-Proof, Thick Blood, Quick Healer), attributes (Strong, Quick, Hale, Clever, Resolute), the field (Iron Gut, Field Medic, Pack Mule, Keen Eye, Trailblazer, Shadow, Unseen, Forager, Butcher, Tireless, Wayfarer), Jodebris (Jodebris Sense, Tinkerer, Good Eye), money (Lucky, Guild Favourite, Well Liked, Guild Darling) and learning (Quick Study, Born Fighter, Woodwise, Fast Learner, Quick Recovery).
- **At levels 3, 6, 9…** three are offered from those you don't have and qualify for (two need another talent or an attribute). The choice opens by itself when nothing else is on screen; Esc puts it off (the same three wait; **`n`** brings them back; the panel says "Talent to choose: n"). Several levels at once give several choices in turn.
- The character sheet has a **Talents** section (yours, with what each does, and the level of the next).
- Landed blows can now be "telling" (double damage) with Keen Edge or Executioner.
- The balance bot takes the first talent offered.

## 0.57.0: Attunement; what Tenacity and Acumen are for (2026-11-20)
Progression, stage 3 (`claude/design-progression.md`; details are my placeholders):
- **Attunement** (Tenacity; trained by the artificer, beside Identification): your windcatcher drains 10% slower a rank above 1 (to half at rank 6; fractions carry from turn to turn); at rank 3 artifacts with limited uses get one more use each hunt; at rank 5 a **fourth artifact slot**. Practice: using an artifact, and moving between areas on a hunt with Jodebris in your windcatcher.
- **The attributes' roles rewritten** (there are no spells): Acumen is understanding what you find; **Tenacity shakes off being dazed** (a mirebellow's bellow lasts a turn less per point above 10, 3 turns at least). Each attribute's description now names the skills it speeds, and the character sheet lists what each is for.

## 0.56.0: Field skills (2026-11-20)
Progression, stage 2 (`claude/design-progression.md`; details are my placeholders):
- **Tracking** (Acumen; taught by the trainer): creatures leave **tracks** (`"`, orange) where they've walked, lasting 10 turns a rank. Rank 2: entering an area, a sense of how many creatures it holds (the number at rank 4). Rank 3: a marked bounty shows on the minimap. Rank 4+: creatures within 6 steps (+2 a rank) show on the minimap, unseen. Practice: each area entered on a hunt, kills.
- **Stealth** (Celerity; the trainer): rank 1 changes nothing (anything that sees you notices you); each rank after, 12% less often (to 25% at worst for the creature). A blow at a creature that hasn't noticed you: +2 accuracy, +1 damage per two ranks ("never saw you coming"). Practice: slipping past a creature (once each), striking unnoticed.
- **Harvesting** (Physicality; the smith): materials 5% more often a rank above 1, one more of each at ranks 3 and 5. Practice: each material a kill leaves.
- **Survival** (Fortitude; the healer): the rest after a hunt 10% shorter a rank above 1 (half at most), rations mend 2 turns longer a rank, torches burn 10% longer a rank, and from rank 4 bleeding and poison last half as long. Practice: coming home (more for a success), eating a ration, lighting a torch.
- The character sheet says what each gives at your rank and what comes next.

## 0.55.0: Weapon skills and techniques (2026-11-20)
Progression, stage 1 (`claude/design-progression.md`; the user approved the whole plan, details are my placeholders):
- **Four new skills: Blades, Axes, Hafted, Brawling**, beside Marksmanship. Each weapon names its skill. Every melee blow practises it (a hit counts double); self-taught to rank 2, the trainer trains ranks 3–6. Each rank above 1: +1 accuracy with it; ranks 3 and 5: +1 damage each.
- **Techniques:** a passive one at rank 3, an active one at rank 5, readied with **`z`** (no time; `z` again puts it aside; it rests 20 turns after use). Blades: Riposte / Lunge. Axes: Cleave / Rend. Hafted: Crush / Stagger. Marksmanship: Steady hand / Aimed shot. Brawling: Quick hands / Throw.
- The character sheet lists each skill's bonus and techniques (yours, or at which rank), and a readied technique; the look command says when a creature is bleeding or reeling.
- The trainer now teaches the blade, the axe, the pick and the fist as well as the bow.
- A bow's bash practises nothing (bows are for shooting).
- Fixed: scrolling a long window before it was first drawn could crash.

## 0.54.1: Popups and long lines fit (2026-11-20)
Fixed, from the user's screenshots:
- **A long choice** in a scene wrapped onto a second line that repeated its number ("2. go."). It now wraps under its own text.
- **Popups** showed two blank lines between paragraphs, which looked like missing text. Now one. A page too tall for the screen shows a screenful at a time ("any key: more") instead of being cut off.
- **The Wayfinder** cut off "Your contract is here: …"; it now wraps, and it also says when a bounty you hold is at the chosen place.
- **The side panel** cut the place's words off and printed them in lower case ("[quiet][green][daybre"). They're now as written, split between words over two lines when they don't fit.

## 0.54.0: The clerk's first jobs (2026-11-20)
The user's outline for a new player's first steps, built as `data/story/first_jobs.json` (structure the user's; all wording is my draft):
1. **New Game → the opening crawl → the guild hall.**
2. **A popup** on moving, and on visiting the clerk at the window.
3. **The clerk's offer**, the first time you talk to the clerk: "Sure, what have you got?" or "If it's all the same to you, I'll figure it out as I go."
4. **Declining** goes straight to the story: a "[STORY GOES HERE]" placeholder for now.
5. **Accepting:** thanks, then a contract posted on the contracts board, **marked for you** ("☼ From the clerk: your first contract"; heading "Marked for you by the clerk"), with every other contract greyed out and refused until you take it. The word "tutorial" appears nowhere.
6. **Taking it:** a popup sends you to the Wayfinder. **At the Wayfinder** a briefing pops up first, then its window opens on the contract's words.
7. **The hunt** ([Quiet][Green][Daybreak], 2 areas, a common broken artifact to keep): popups as things come up (the miasma, exploring, the map and minimap; the first creature, fighting, resting, fainting and death; what creatures leave; the deepest area; the find; getting home; what to do with a broken artifact). The end card reads "Contract complete".
8. **The clerk** explains bounties and posts one marked for you on the bounty board (a marked scavenger at [Quiet][Broken][Daybreak], 25 shards), the others greyed out. The Wayfinder now starts on the words of a bounty you hold when you have no contract.
9. **Paid by the clerk**, a word on the plaza's notice board, **100 shards**, and a proper welcome. The quest is done and the game is yours.
- If the Hunter dies partway, the contract or bounty goes up again for the next one.

**The guild hall is redesigned** (user): the **clerk works from a small office behind a service window** (`▬`, a new tile); walking into the window talks to the clerk. The hall has the two boards at the front, the training corner (back left), the stash room (back right, with the mentor), and spare corners for people still to come. **The example items littering the floor are gone.** Only the hall changed; the rest of Bytorsskug is exactly as it was. You start three steps north of the clerk's window.

Story engine additions (for this and later chapters): events `talk` (folk), `wayfinder`, `see` (a creature seen for the first time), `bounty_paid`, `manual`; conditions `taken:`, `bounty:`, `bounty_done:`; effects `only:` (limit a board to one posting) and `bounty:` (post a story bounty, from a new `bounties` section); scenes can be `"style": "popup"` (over the map); story contracts can set `heading`, `posted_line`, `card_heading` and `story_item: false`; scenes queued by talking or the Wayfinder play before the conversation or window.

## 0.53.1: New keys (2026-11-20)
- **`m` opens the whole map**, **`v` switches the side panel between the minimap and the messages**, and **`l` opens the message log** (user).
- **vi-style movement (h j k l) is gone** (user's choice, since `l` is now the message log). Arrows, WASD and the numpad move as before; `j` and `k` still move up and down in lists.

## 0.53.0: The opening crawl's text, and the minimap (2026-11-20)
- **The opening crawl** now has the user's text (`data/crawl.txt`).
- **The minimap** (user): `n` puts a minimap in the side panel in place of the message log (press again for the messages). It shows the whole map, or on big maps (Bytorsskug, the Brisering) the stretch around you. `v` opens **the whole map** over the map view. Both show explored ground only (out on hunts and on the Brisering), with you in magenta, ways, gates and landmarks in orange or their own colour, creatures in view in red (a marked bounty in gold) and people in theirs. Neither takes a turn.
- The key reference lists both; its "Gates" line now says they lead to the Brisering.

## 0.52.1: People are @ (2026-11-20)
- **You, the townsfolk and rival Hunters are drawn as `@`** (user: the magenta made the smiley look off), in place of `☺`. Colours unchanged: you magenta, townsfolk gold, rivals sky blue.

## 0.52.0: From the user's first full play (2026-11-20)
- **The quest log lists your contract, bounties and scouting** (user: taking them left it empty), each with the place, the pay and what to do next, alongside the story's quests.
- **Scholarship practice from reading is smaller** (user: one easy note took you halfway to rank 2): the base is 1 a reading (plus Acumen), and a writing easier than your rank teaches only 1. A writing a rank too hard still teaches once per rank when you fail to read it, and only once, so it can't be farmed.
- **The artificer buys repaired artifacts** (user): `b` on a working artifact in your pack, for half its sale price (my number); it goes up for sale in the workshop. The Artifacts tab lists working ones too, marked "(working)".
- **Earnings and dues so far on the character sheet** (user): everything earned this Judgment from every source, how much of it was Guild pay (bounties, scouting, field notes: no dues), and the dues built up so far. Guild pay is now counted separately (`Player.guild_pay`), saved with the dues.
- **Limited-use artifacts work without a windcatcher** (user): the astrolabe, the mending engine and any artifact with uses per hunt hold enough Jodebris of their own, anywhere; using one no longer drains a windcatcher (it used to cost 25). Lasting effects (light, armour, accuracy, evasion) still need a windcatcher beyond the Brisering. Artifact descriptions say which.
- **Marked bounty creatures stand out**: drawn gold on deep red. **Killing one, or picking up a find bounty's artifact on a hunt, brings up a "Bounty done" card**: get back to the trail home safely, then see the clerk.
- **The Hunter is vivid magenta** (user: more ostentatious; the colour is my pick), unlike any creature or person.
- **The character sheet is reworked** (user: a bland wall of text): sections with coloured rules (Attributes, Fighting, Artifacts, Injuries, The Guild, Skills), HP and XP bars, attribute changes from age and injuries in green or red, gear and artifacts in their own colours, rarity names coloured, skill bars that turn green when ready to train.

## 0.51.2: þ is back (2026-11-20)
- Fixed: **þ and Þ showed as blanks** ("Er el" for Erþel, "Le a" for Leþa). They were copied into the font tile by tile at startup with `Tileset.set_tile`, which newer versions of tcod have replaced; the failure was silently caught, leaving the letters blank. They now sit in an extra row of `data/font_8x16.png` and are loaded in one go with the rest of the font, which works on every tcod version. `data/font_extra_8x16.png` is gone.

## 0.51.1: New Hunter (2026-11-19)
- **New Hunter**, second on the title menu (user): a fresh Hunter in the autosave's world. **The current Hunter simply vanishes**: no place in the Hall of Hunters, no gift, and what they carried is lost. The game warns first, and points to the proper way out: retiring at the guild clerk (Hall, stash, shards to the next Hunter). The world stays as it was; a Pulse passes. Greyed out until there's a world to go into.
- Story items the vanished Hunter carried still go to the stash, so the story can't be lost with them (my call).

## 0.51.0: New Game and the opening crawl; the old story removed (2026-11-19)
- **The title menu starts with New Game** (user): a factory reset, a fresh world and a fresh Hunter, as if the game had never been played. With an autosave it warns first that the autosave (Hunter and world) will be wiped; save slots are kept. The menu starts on Continue when there's an autosave.
- **The opening crawl** (user): after New Game, text rises slowly up the screen. Any key speeds it up (again to slow down), Esc skips. The copy lives in `data/crawl.txt` (a placeholder line until the user's copy arrives).
- **Chapters 0 and 1 removed** (user: the story is being reworked, with the tutorial woven into the first quests). Their story items (training token, Hlera's pack) went with them. A new game has no story for now.

## 0.50.2: Distance, not steps, on the Brisering (2026-11-19)
- **A step north or south on the Brisering counts double** (user: distance covered matters more than steps taken). Cells are 0.5 km across and 1 km down, so a Pulse now passes about every 25 km whichever way you walk. Waiting counts as one step. The map is unchanged.

## 0.50.1: Shorter days on the Brisering (2026-11-19)
- **A Pulse passes every 50 steps on the Brisering** (user; was 100). With cells 0.5 km across and 1 km down, that's 25 km a Pulse walking east–west and 50 km north–south.

## 0.50.0: Igerste and Ingenfjel (2026-11-19)
- **Two villages on the Brisering** (user's lore): **Igerste**, near the outer eastern edge, where the east road out of the Crumbling Gate now ends; and **Ingenfjel**, 17.5 km south-west of Bytorsskug, reached by a new road out of the Towerway.
- **The Ingenfjel boga circuit**, the Overland's largest (user), is an oval track (`∙`) just east of the village. You can walk it.
- Villages show as `⌂`. Walking into one says you can't go in yet; the look command names it; once you've seen one, it's on the travel list.
- **No mountain at Ingenfjel** (user): no hills or mountains within 12 km of it.
- Map placement and the track's look are my calls.

## 0.49.1: Eel bounties, and cave pools that actually appear (2026-11-19)
- **Kill bounties can mark a hookjaw eel** (user). If the place's deepest area has no water, a small pool is made at a dead end there for that trip, and the marked eel waits in it.
- Fixed: caves were meant to get the odd pool in 0.49.0, but the pond maker only worked on grass floors, so no cave ever had water and eels never spawned. Now about a third of cave areas have a pool. Hunt generation 5 (a mid-hunt save from before sends you home).
- When a swimmer is picked for an area without water to spare, another creature takes its place, so areas still get their full count.

## 0.49.0: Nine new creatures, mountains and plains (2026-11-19)
The user's creatures and their ways (stats are my placeholders, in `data/monsters.json`):
- **Glasswing** (g, tier 1): flies (crosses water); forest, plains and mountains, **only at night**, never indoors.
- **Mirebellow** (m, 2): slow, hits hard; forest or mountains, day or night. **Opens with a daze** when it first notices you: accuracy and evasion −2 for 8 turns (user's choice).
- **Hookjaw eel** (h, 1): waits in cave water (a small chance where there is any) and **leaps** up to three cells to your side, then fights normally.
- **Lantern tick** (t, 2): forests; weak, but **bursts when it dies** (2d4 to everything beside it), so it's safer shot than struck.
- **Crawler** (C, 3): caves and ruins; slow and very tough. **Replaces the cave crawler** (user).
- **Ashmantle** (A, 3): anywhere, **only at night**. Follows at a distance, **can't hit you and can't be hit** (blows and arrows pass through), slow, and leaves **hot ash** that burns you (1d3) when you walk on it; the ash cools after 40 turns.
- **Thistlehound** (T, 3): quick (two moves a turn); forests by night, mountains by day. **Each blow you land costs you 1 HP** (its burrs).
- **Hollow elk** (E, 2): forests at night; **runs** when it's down to 30% HP.
- **Gravel wyrm** (G, 4; the woodland stalker keeps W, user): mountains, caves, ruins. **Burrows**: under the ground it can't be hit (shown as a stir, °) and closes in; it surfaces beside you, fights for 3 turns, then sinks again.
- **Night** is any dark place (torchlight only); **day** is daylight.
- **Two new land styles** (user): **mountains** (open slopes between rock outcrops) and **plains** (open grass, copses, ponds), with words *Craggy*, *Towering* (verb), *Open*, *Rolling* (verb). Older creatures spread into them (wild dogs, cave bats, scavengers, boars, hollow brutes, stone sentinels). Caves now have the odd pool. Hunt generation 4: a mid-hunt save from before sends you home.
- Kill bounties never mark an ashmantle or an eel; the balance bot ignores ashmantles and buried wyrms.

## 0.48.0: Balance pass 2 (2026-11-19)
The user's direction: injuries more likely across the board (about 0.5 a hunt at danger 1, up to 2 at danger 4); loose shards a nominal part of income (the difference between affording something or not); most income from artificers, then contracts, requests and jobs.
- **Injuries:** any hit can now injure, with chance `small_hit` 2% (data/injuries.json); big hits still injure more often, now at `chance` 0.2 + `per_tier` 0.05 (were 0.3 + 0.1) so the deep end doesn't pile them up. Bot runs (small, noisy samples): about 0.6–0.9 a hunt at danger 1, 0.6–0.8 at 2, 1.7–1.9 at 3, more at 4.
- **Loose shards:** 0–2 piles an area of 1–3 shards (+1 per 2 danger), down from 2–4 piles of 2–6 × danger. In the bot's runs they're now about 5–10% of income (were the largest part at danger 2–4); artifacts are the largest.
- The balance bot now counts every injury taken on a hunt (minor ones used to mend during the rest before it counted). Details in `claude/balance-report.md`.

## 0.47.0: Words from writings and townsfolk (2026-11-19)
Part of stage 4. The user's rules:
- **Writings** can teach a word, **only if your Scholarship can read them**, and **only if that writing has a word to teach** (most are only lore). A writing's optional `teaches` list in `data/writings.json`; three placeholder writings have one (Notes from beyond the Crumbling Gate: [Toppling]; Glass and coin: [Hoard]; Measurements of Myligast: [Dripping]). Reading it yourself or in the Academy library teaches it, if your rank is up to the writing's difficulty.
- **Errands:** townsfolk sometimes post a request that sends you to a place: "the seized gyroscope lying at [Wandering][Green][Lurker]". **Hearing of it** (reading the notice board, or asking the person about their request) **teaches the place's words**. The artifact waits in the place's deepest area; bring it to them (no identifying needed). About 30% of requests; dangers 1–3; pay = its rarity's broken price × 4 + 4 × danger (`data/work.json`).
- **Rumours:** the porter, washer and carter now answer "Heard anything lately?". Now and then (15%, once a Pulse each) they pass on a word you don't know; otherwise small talk. Lines and chance in `data/rumors.json` (placeholders that invent no lore). Dialogue files can use it with `"rumor": true` on a node (documented in `data/dialogue/_README.md`).

## 0.46.0: The Brisering (2026-11-19)
Stage 3 of the redesign (design: `claude/design-brisering-keywords.md`).
- **The gates lead out into the Brisering**: one persistent travel map, 400 × 202 cells (half a kilometre across and a kilometre down per cell), the 99 km circle round Myligast with the miasma beyond its edge. Built by `tools/brisering/build_brisering.py` (`data/maps/brisering.txt`).
- **Lore placed as the user set it:** Myligast at the centre, 9 km across, seen from anywhere (it's infinitely tall); Bytorsskug 9 km south of it, a small walled block with its four gates. Each gate opens onto its own terrain: mountains and hills to the north (a road runs to Myligast's foot), ruins to the east, forests to the south, forests to the west with the Towerway running west to the edge. Lakes, a river (in from the west, past the city, out to the south-east) and roads with bridges. Everything walkable can be reached from the gates without a diagonal step.
- **Out there:** fog of war, remembered between visits and saved; daylight. A Pulse passes for every 100 steps or turns (`data/brisering.json`). Artifacts work freely and windcatchers stay full (Jodebris is everywhere in the Brisering: user). Safe to save. Auto-explore works; travel-to lists the four gates.
- **In and out:** walking onto a city gate takes you out, just beyond that gate; walking onto a gate on the Brisering brings you back in just inside it.
- Nothing lives or waits out there yet: landmarks, minigames and housing are for later.

## 0.45.3: "Anything" picks known words (2026-11-19)
- User: an "(anything)" slot at the Wayfinder now picks only from the words you know (still one that fits the other slot, and a danger within your rank). Before, it picked from every word, and you learned the ones you landed on.

## 0.45.2: Words that don't fit are greyed out (2026-11-19)
- User: no error message spelling out the grammar. In the Wayfinder's window, once a word is chosen, words in the other slot that can't go with it are greyed out, and the cursor skips over them. Nothing in the window mentions verbs. Unavailable words (these, and danger words above your rank) are dimmed more clearly than before.

## 0.45.1: Keyword grammar (2026-11-19)
The user's rule for the Wayfinder's words:
- **Danger and land words are adjectives or verbs** (verbs as -ing words); **a place can't have a verb for both**; **feature words are nouns** (phrases are fine). Valid: [Hungry][Tangled][Victory Lap], [Dancing][Green][Ropeway]. Invalid: [Singing][Listing][Ideas].
- Each word now has a `pos` in `data/keywords.json`, checked on loading. Two-verb places don't exist: the Wayfinder refuses them with a line saying why (and shows it before you press Enter), and the Guild's boards, "(anything)" and the balance bot never make one. 432 places (was 480).
- Placeholders renamed to fit: land *Deep* → *Dripping* (verb), *Forgotten* → *Toppling* (verb); features *Sunlit* → *Daybreak*, *Black* → *Midnight*, *Swarming* → *Swarm*, *Hushed* → *Silence*, *Gilded* → *Hoard*, *Lettered* → *Letters*, *Tusked* → *Tusks*, *Pale* → *Lurker*. Same effects. Chapters 0 and 1 are now at [Quiet][Green][Daybreak] and [Restless][Green][Tusks].
- Saves: words and places under the old ids are dropped on loading (a contract or job there is lost; the start words come back).

## 0.45.0: Bounties and scouting (2026-11-19)
Stage 2 of the redesign (design: `claude/design-brisering-keywords.md`). The user's call: the Guild's second board is for **bounties** (killing a particular creature, or finding a particular artifact) and **scouting**.
- **The bounty board** (`¶`, front right of the guild hall; the clerk's "What work is there?" opens it too), now "Bounties and scouting": four postings, new every Reckon, each at a place (three words). Dangers lean low (weights 4:3:2:1.5:1 for danger 1–5); ones above your rank are greyed and can't be taken. Taking one teaches its words. Hold two at a time.
  - **Kill bounty:** a **marked** creature (the toughest kind the place's deepest area allows, from its land or its favoured creature; never a stationary one) waits in the deepest area, shown as "marked …". Kill it on any trip there. Pay: 15 + 12 × tier + 4 × danger.
  - **Find bounty:** a particular broken artifact waits somewhere in the deepest area (not the place's own find). Pick it up, then hand it to the clerk (any of that kind will do). Pay: its rarity's broken price × 4 + 4 × danger. No artifact with you, no pay.
  - **Scouting:** reach an area of the place (up to its depth). Pay as before.
- The Guild pays all three and takes no dues from them. Culls are no longer posted (a cull taken in an older save still works).
- The board shows each posting's place, danger and depth, and what to do; the end-of-trip card lists jobs done ("Done: …"). Marked creatures and bounty finds are saved with a hunt in progress.

## 0.44.0: The Wayfinder (2026-11-19)
Stage 1 of the user's redesign (design: `claude/design-brisering-keywords.md`).
- **Hunts leave from the Wayfinder** (named by the user), a great artifact in the plaza (`▓`, 5 × 3; placeholder look). Walk into it and choose **three words**: **danger** (danger 1–5 and how many areas deep), **land** (caves, ruins or forest; light and size) and **feature** (sunlit, black, swarming, hushed, gilded, lettered, or a favoured creature: tusked, pale). Like .hack's Chaos Gates. **The same words always make the same place** (the same layout); what's in it is new each trip. A slot can be left on "(anything)": the Wayfinder picks, and you learn the words of wherever you land. Every word is a placeholder (`data/keywords.json`).
- **Known words belong to the city** (world state; a new Hunter keeps them; a new game starts over). Seven are known at the start. More come from the Guild's boards (taking a contract or job teaches its words), rank (each rank teaches two), and the story (`learn:` effect; `knows:` and `word:` conditions).
- **Rank limits danger at the Wayfinder** (Recruit 2, Hunter 3, Seasoned 4, Veteran 5). Rising in rank says how far you can go now and which words the Guild teaches.
- **Every place has a find**: a broken artifact at the far end of its last area, rolled each trip by danger (Gilded: rarer). A trip without a contract is "A trip to [..][..][..]"; bringing the find home is "Trip complete".
- **The Guild's contracts board** (`¶`, front left of the guild hall): six postings a day, from danger 1 to 5, at places from all the words: "Go to [..][..][..] and retrieve the … reported in our most recent scouting report." Story key hunts are listed first. Take one (one at a time; it's yours until done or replaced; it outlives a failed attempt); at the Wayfinder its words are chosen for you (or press `c`). Contract done: "Contract complete". Rivals take postings and race you as before (never on your own trips). Owing dues closes this board only.
- **The bounty board** (`¶`, front right) opens the odd jobs (also still through the clerk). Odd jobs are at places now; any trip there does them. (Bounties for a creature or an artifact come in stage 2.)
- **The gates lead to the Brisering** (not built yet): walking onto one says so. `data/regions.json` is gone; gate names are in `data/gates.json`.
- **Story:** key hunts name their place with `words: [danger, land, feature]` (not `region`). Chapters 0 and 1 moved to [Quiet][Green][Sunlit] and [Restless][Green][Tusked]; the clerk, trainer and chapter drafts now talk about the Wayfinder and the board. Chapter 1's premise ("missing along the Towerway") needs your eye: the Towerway is in the Brisering now.
- **Odds and ends:** the archive's scouting tab lists the places Hunters have reported; bestiary entries say which land words a creature lives under; writings limited to a "region" now name a land style (`ruins`, `caves`), a word, or a place; the balance bot takes trips by danger, and its report groups hunts by danger.
- **Saves:** words with the world, your contract with you. A mid-hunt save from an older version sends you home, as before (hunt generation 3). Contracts, odd jobs and scouting reports in the old regions are dropped on loading.

## 0.43.0: The camera follows your eye (2026-11-19)
The user's design:
- **While the look cursor (`x`) is open, the camera follows the cursor**, not you. Close it and the camera goes back to you. The aim cursor (`f`, bows) works the same way.
- **The cursor can't go past your vision range.** That range is how far you can see: daylight (30) in the city and the western forests, your light (torch or artifact) in dark places. As always, rows count double, so it reaches half as far up and down. Range only: walls still hide what's behind them, and the look command still tells you only what you've seen.
- **Injuries can shorten sight.** An injury can now have a `sight` effect (cells, e.g. −3), which shortens your field of view and the cursor's reach; the character sheet lists it with the injury's other effects. No injury uses it yet.
- Tab (next thing in view) now reaches everything within your vision range, not just what was on screen.

## 0.42.1: Melee weapons ↓ (2026-11-19)
- Melee weapons (short sword, hand axe, arming sword, war pick, iron-shod axe, sentinel maul) are drawn ↓ instead of ). Bows stay }.

## 0.42.0: New glyphs (2026-11-19)
The user's choices:
- **Walls** (city wall, houses, ruin walls) are solid blocks █ instead of joined lines.
- **Water** now has an occasional `.` or `'` among its ≈ and ~. Those two are always white; the rest stay blue.
- **Doorways** ◘ (were +).
- **Way deeper / way back** » « (were > <).
- **Guild stash** $ (was ▄).
- **Armour** φ (was [).
- **Healing draughts and tonics** ♥ (were !).
- **Iron scrap** §, **chitin plate** ∟, **sinew** ε.
- **Story items** µ: Hlera's pack, the training token, the old iron key, and every key-kind item from now on. The writer's guide says so.
- **People** ☺: you, the townsfolk, rivals and the mentor (were @).

Map files are unchanged: `#`, `+`, `>`, `<` and `C` are still how maps are written. Only how they're drawn changed.

## 0.41.1: Bigger windcatchers, no Jodebris numbers (2026-11-19)
- Windcatchers hold 40% more Jodebris (rounded down to the hundred), to suit the longer four-way walks: lesser 1,200 → 1,600, windcatcher 1,800 → 2,500, great 2,800 → 3,900. Drain is unchanged (1 a turn in the miasma, 25 per artifact use).
- Jodebris amounts are no longer shown anywhere. The side panel shows only the bar, now the full width of the panel. Item details, using a windcatcher and the low warning describe it in words: full, nearly full, more than half full, less than half full, running low (at a quarter, when the warning comes), empty.

## 0.41.0: Four-way movement (2026-11-19)
- **No more diagonal steps, for anyone.** You move with the arrows, WASD, numpad 8/4/6/2 or h/j/k/l; the diagonal numpad keys and y/u/b/n do nothing. Creatures, rivals, townsfolk, auto-explore and travel-to all move four ways too.
- **Melee is side by side only.** A creature at your corner can't hit you, and you can't hit it; it has to step round to your side first. Arrows still fly at any angle.
- **Hunt areas are joined four-way.** Wherever the cave, forest and ruin generators left two open spaces touching only at a corner, they now open the rock, tree or wall between, so no part of an area needs a diagonal step to reach. The same contract now gives different areas than before.
- **Old saves:** a save made in the city loads as before. A save made mid-hunt by an earlier version can't rebuild its areas, so loading it puts you back in Bytorsskug with the contract lost (and a message saying so).
- Fixed: after a race was decided, the rival could stay standing in an earlier area. In a one-wide passage that blocked the way home. They now leave once the race is over.
- Balance bot (4 Hunters × 15 hunts, same seed, before → after): contracts completed 34 → 46 of 60, abandoned 26 → 14, injuries per hunt 0.63 → 0.18, faints 0.07 → 0.03, turns per hunt 1551 → 1680. Walks are about 40% longer (entry to far end: caves 62 → 88 steps, forests 88 → 125, ruins 79 → 95). No numbers were changed; they're for the next balance pass. The bot now heads home when a rival wins the race, and fights a creature that blocks the only way on.

## 0.40.2: Straight bridges (2026-11-19)
- Bridges in Bytorsskug are now straight and two cells wide, running bank to bank (north–south or east–west, never diagonal). Where a bank isn't already street, a short straight approach road, also two wide, joins it to the nearest street. There are 4 bridges, well spread along the river (before: 7, mostly single cells you had to step onto diagonally).
- The west and south gates opened onto wall on the town side, so you needed a diagonal step to reach them. Each gate now has a straight way cut through the wall.
- The city builder now checks that every door and gate can be reached without a diagonal step.
- The map was rebuilt from the builder: 96 houses (was 94). The shops, the townsfolk and the guild hall are where they were.

## 0.40.1: Title cards wrap (2026-11-19)
- Fixed: long lines on title cards (hunt complete, key hunt complete, retired, fallen...) ran off the edge of the screen, cutting off the trainer's words after the training hunt. They now wrap and stay centred.

## 0.40.0: Chapter 0 and Chapter 1 (drafts) (2026-11-19)
The first story in the game. **All text is a draft** for rewriting; the files are `data/story/chapter0_training.json` and `data/story/chapter1_missing.json`.
- **Chapter 0: Training** (the tutorial). A new game opens on the trainer, Bumpry Archer Hunters, who offers training (or skip it). A tour: meet the clerk, the supplier and the artificer, then back to the trainer, who posts a short training hunt at the Towerway (two areas, a token to bring back). Prompts along the way: moving and fighting, exploring and looking, the ways on and back, picking things up, getting home. Only the first Hunter of a new game; skipping goes straight to Chapter 1.
- **Chapter 1: Missing on the Towerway.** The clerk tells you Hlera Fencer Hunters went out along the Towerway and never came back, and posts a search. It's for Hunters: a Recruit has to rise first. Deep in the forest, a thornback boar guards what's left: Hlera's pack. Bring it to the clerk. Hlera's fate is left open.
- New items: the training token and Hlera's pack.
- For testing and the balance bot, `TAG_NO_STORY=1` runs the game without the story.

## 0.39.0: Key hunts (story contracts) (2026-11-19)
- **The story can post contracts on a gate's board.** A key hunt is written in `data/story/` (region, title, description, the rank it's for, danger, areas, the prize, and an optional guardian creature waiting beside the prize) and put up with the effect `post:ID`. It's listed first on the board, marked ☼.
- **Rank up to continue:** a key hunt for a higher rank than the Hunter's shows greyed out ("Posted for … and above"). A key hunt for a lower rank than its gate normally needs opens that gate for that hunt alone.
- Bring the prize home and it's done: off the board, its effects happen, lines of your choosing on the "Key hunt complete" card, and a `contract_done` event. Turn back or die and it stays posted (`contract_failed`). The prize is a story item, so it can't be lost with a Hunter.
- Rivals never take or race key hunts. New conditions `posted:ID` and `completed:ID`; effects `post:ID` and `unpost:ID`.
- The example story (`data/story/examples/`) now includes one. The writer's guide (`data/story/_README.md`) explains it.

## 0.38.1: The hollow brute moves to the forests (2026-11-19)
- The hollow brute (tier 4) now lives in forests and ruins instead of caves and ruins. The southern forests finally have a heavy hitter: it can turn up in the last area of a danger-4 Woodgate contract and from the third area of a danger-5 one. (The caves never reached tier 4, so the northern mountains lose nothing; the western forests' danger is too low for it.)

## 0.38.0: Guild ranks (2026-11-18)
- **Five ranks** (placeholder names): Recruit, Hunter, Seasoned Hunter, Veteran, Master Hunter. A new Hunter is a Recruit.
- **Rising:** each rank takes a number of completed hunts and a level; then **sit for it at the guild clerk**, for a fee (25, 100, 300, 800 shards). Ask the clerk what the next rank takes; the character sheet shows it too.
- **Gates:** a Recruit may take contracts only through the Towerway; Hunters add the Tower Gate, Seasoned Hunters the Crumbling Gate, Veterans the Woodgate. **Danger:** each rank has a highest contract danger (2, 3, 4, 5); harder contracts show on the board as posted for a higher rank.
- **Privileges:** Seasoned Hunters and up train 10/20/30% cheaper and get 10/20/30% more for requests; Veterans and up may take a contract a rival has already taken (first pick).
- **Debt:** the clerk now offers **Guild labour** to someone owing dues: a Pulse of work pays down 3 shards (time passes). **Still owing when the next dues fall due costs a rank.**
- Rivals are ranked too (by the same hunts and level), and only hunt where their rank allows.
- Fixed: shown choices in conversations now fill in their words ("Pay my dues (20 shards)" used to show "{dues}").
- The balance bot sits for ranks and hunts only where its rank allows.

## 0.37.1: Rivals in blue (2026-11-18)
- Rival Hunters are now sky blue on the map (were pale lilac, too close to your own @). The colour is `color` in `data/rivals.json`.

## 0.37.0: Rival Hunters (2026-11-18)
- **Five rival Hunters**, members of the Guild with lives of their own (world state). Each has a name, a calling, a temperament (boastful, gruff, friendly, wary), an age and a level.
- **Off-screen**, a rested rival takes a contract off a gate board (it shows as **taken** there, and you can't accept it), hunts it (a success brings experience on your level curve, and their find goes up for sale at the workshop; some die), sometimes fills a request or takes an odd job before you can, ages, retires or dies of old age. New Hunters join to replace them. Everyone who leaves is remembered in the Hall of Hunters.
- **In the guild hall** when they're home: talk to them for a greeting in their own manner, news of their last hunt, and who they are.
- **The race:** sometimes (1 in 4) a rival goes after the same contract as you. They move through the hunt's areas at their own pace (faster the higher their level); you'll see them when they're in your area, and you can't fight each other. Whoever reaches the prize first has it.
- Numbers, callings and lines are in `data/rivals.json`; their conversation is `data/dialogue/rival.json`.

## 0.36.0: The story skeleton (2026-11-18)
The machinery for the main story, ready for it to be written (no story yet). Everything is written in JSON in `data/story/`; see `data/story/_README.md`.
- **Quests** with stages: each stage can add a line to the quest log, show the current goal, do things when it begins, and move on by itself when its conditions hold. Quests belong to the world by default (the story outlives Hunters); a quest can belong to one Hunter instead.
- **Scenes**: pages of text (with speakers) and choices, played when something happens: a new game, a new Hunter, setting out, entering an area, a kill, picking something up, coming home, a new Pulse, retiring, dying. A scene with no pages is a silent trigger.
- **Story lines in anyone's conversation**, without editing their dialogue file.
- **Story flags and counters**, usable in any condition, effect or text (`{counter_name}`).
- **Story items hidden in hunts:** they wait in a region's next hunt, come back if not found, and go to the guild stash if the Hunter carrying them dies.
- **The quest log** (q): quests under way and finished, the current goal, and everything so far.
- A complete working example (not loaded by the game) in `data/story/examples/example.json`.

## 0.35.0: Callings and the bow's bash (2026-11-18)
- **A Hunter's calling (middle name) now comes from the kind of weapon they've used most**, counted by attacks and shots, not from whatever is in hand. Swapping from bow to axe mid-fight no longer renames you. Before their first fight, it's the weapon they hold; a tie goes to the weapon in hand.
- **A bow's bash is stronger:** 1d2 plus 1 for every 6 Physicality (instead of the usual Physicality bonus). Most Hunters bash for 1d2+1; from Physicality 12, 1d2+2, as good as a short sword in average hands. Arrows are unchanged.

## 0.34.1: Dues per Judgment (2026-11-18)
- Guild dues now fall due on the first Pulse of each **Judgment** (was each Reckon), as first intended: with the rest after every hunt, a Reckon passed nearly every hunt. That's about every 12 hunts now. Still 20% of what was earned since the last.

## 0.34.0: Aging, retirement and the Hall of Hunters (2026-11-18)
- **Hunters have an age**, rolled when they join: 1 Turn to 2 Turns 3 Judgments (about 16 to 38 in Earth years), shown the way people speak of it ("1 Turn, 3 Judgments") on the character sheet, the new-Hunter message and the end-of-life cards. Older recruits start with more attribute points (one for every 2 Judgments past the youngest).
- **Downtime:** after every hunt a Hunter rests before going out again: 8 Cycles, plus 2 more for each injury they come home with. With the hunt itself, that's about a Reckon (~2 months) per hunt.
- To match, the timed systems are stretched: the job board and requests renew every Reckon (requests stand 3 Reckons), shop and workshop restock times ×9, the smith's commissions take 1 to 3 Reckons.
- **Age tells:** from 1 Turn 4 Judgments the mind grows (Acumen, then Tenacity, +1 every 4 Judgments, +3 at most); past 2 Turns 4 Judgments the body declines (Physicality, Celerity, Fortitude: −1 every 2 Judgments, in turn). Each new Judgment is noted in the log.
- **Death of old age:** from 3 Turns 6 Judgments, each new Judgment carries a growing chance (4%, 8%, 12%...) of dying of old age, at home or out on a hunt.
- **Retirement:** ask the guild clerk (not while owing dues). Everything the Hunter carries goes to the guild stash, their shards to the next Hunter, and their name to the Hall of Hunters.
- **The mentor:** the latest Hunter to retire stays on in the guild hall and teaches their skills (above rank 1) at half the trainer's price, up to their own rank.
- **The Hall of Hunters** (ask the clerk): every Hunter who retired, fell or died of old age, with their age, level, hunts completed, how it ended and when.

## 0.33.0: Balance pass 1 (2026-11-18)
Measured with a new simulator (`tools/balance/`), which plays Hunters through hundreds of hunts with the real rules; see `claude/balance-report.md` in the project.
- **Creature tiers rise more gently.** Tier 2 now first appears in the west's third area, not its second; tougher tiers come later at every danger.
- **Tier-2 creatures toned down:** thornback boar (HP 20 → 16, armour 2 → 1, 1d6+2 → 1d6+1), pale lurker (HP 18 → 15, accuracy 12 → 11, 1d6+1 → 1d6), ruin stalker (HP 16 → 14, accuracy 13 → 12, evasion 12 → 11). A new Hunter loses about 16 HP fighting one, down from 23–38.
- **Healing draught: 15 → 10 shards.**
- **Steeper experience curve:** 5·(L−1)·L·(L+1) (level 2 at 30 XP, 5 at 600, 10 at 4,950), so Hunters no longer leap from level 5 to 15 once they reach the south.
- **Injuries happen more often, at every level:** a big hit is now 15% of max HP (was 20%), and never needs more than 6 damage, so tier-3 and tier-4 creatures can still injure a Hunter in mail.

## 0.32.0: The Academy, writings and the Guild archive (2026-11-18)
- **The Academy**, the largest building in Bytorsskug, now stands at the city's northern edge, fronting the plaza. The north wall bulges out around it. The rest of the town is unchanged.
- **Writings** turn up on hunts (about one area in five): torn pages, journals, letters, carved tablets, scrolls. Until read, you only know what it looks like.
- A new skill, **Scholarship**: read a writing (u) if your rank is up to its difficulty (1-6). One rank short, you can't, but you learn from trying. Ranks 1-2 by practice; the librarian trains the rest.
- **Ymalda Librarian Academy** buys writings for a nominal sum (double if you've read it) and shelves them in **the Academy library**, where any Hunter can read them. A shelved writing never turns up again. The library is world state.
- **The Guild archive:** on a hunt, a Hunter keeps field notes: creatures seen and killed, and how deep they got into each region. **Report them to the clerk** for a small fee (no dues taken). The archive keeps a **bestiary** (sighted, fought, full entry after 5 kills: stats, then drops and injuries) and **scouting reports** for each region, for every Hunter after. Unreported notes die with the Hunter.
- New windows: reading, the library, the archive. The character sheet shows Scholarship and unreported notes.
- All ten writings are placeholders that only restate established lore (`data/writings.json`).

## 0.31.0: Medicine (2026-11-18)
- A new skill, **Medicine**. Use a bandage (u) to stop bleeding, or a poultice to stop poison. It works 50% of the time at rank 1, +10% a rank (95% at most); the item is used up and a turn passes either way. Serious injuries stay until the healer sees them; only the bleeding or poison stops.
- From rank 2, a bandage also mends a minor injury outright (bruised ribs, a twisted ankle, a split brow).
- Every try is practice (a success counts double; Acumen helps). Ranks 1 and 2 come by practice; Lifa Healer trains rank 3 and up.
- The supplier sells bandages (3 shards) and poultices (6); a new Hunter may start with 1 to 3 bandages.

## 0.30.0: Lasting injuries and the healer (2026-11-18)
- A big hit (a fifth of your max HP or more in one blow) can leave a lasting injury; tougher creatures injure more often and more seriously. Some creatures have their own: festering bites, gored thighs.
- Injuries lower attributes (a lower Fortitude lowers max HP), max HP, accuracy, evasion, damage or aim with a bow. Some bleed or fester: HP lost every few turns for a while, and no natural healing meanwhile (paused in the city). Bleeding out knocks you out, or kills you, like any other fall.
- Minor injuries mend on their own after some Pulses. Serious ones need the healer (Lifa Healer, a new townsperson), who treats any injury for a fee.
- Injuries show in the side panel and on the character sheet (c). They belong to the Hunter: a new Hunter starts whole.
- The table is `data/injuries.json`; creatures' own injuries are under `injures` in `data/monsters.json`.

## 0.29.0: Material requests (2026-11-18)
- Townsfolk now also ask for materials on the plaza notice board ("3 sinew", "5 iron scrap"). Hand them all over at once by talking to them; they pay one and a half times the materials' value.
- The smith posts requests too.
- The board shows how many of the material you're carrying.
- Numbers (how often, how many, the pay) are in `data/work.json`.

## 0.28.0: Materials and the smith (2026-11-18)
- Creatures leave materials where they die (some of the time): rough hide, thick hide, chitin plate, sinew, iron scrap, sentinel stone. They stack; the supplier buys them.
- A smith (Bartum Smith, east of the plaza) makes gear to order: hide jerkin, iron-shod axe, sinew bow, thornback coat, chitin armour, sentinel maul. Materials and a fee up front; ready after some Pulses (9 to 27); collect it by talking to the smith. Two orders at a time.
- Orders belong to the city: if a Hunter dies with one in, the smith sends the finished piece to the guild stash.
- All recipes, drops and numbers are in `data/recipes.json` and `data/monsters.json`.

## 0.27.0: Odd jobs open the gates (2026-11-18)
- An odd job opens its gate without a contract: the gate's board lists "Odd job: ..." as an outing with no artifact (deep enough for the job, at the region's lowest danger). It's offered even while you owe dues and the contracts are closed, so odd jobs are a way to keep working.
- Coming back from an odd-job outing is a single Pulse, with a "Back from the odd job" card.
- The Guild takes no dues from odd-job pay (it no longer counts as earnings). Requests still do.

## 0.26.0: Odd jobs and requests (2026-11-18)
- Guild odd jobs: ask the clerk "What work is there?" A board of three jobs goes up every Cycle: cull (kill creatures, sometimes of a minimum tier, in a region) or scout (reach an area of a region). Hold two at a time; do them on any hunt through that gate; collect the pay from the clerk. Pay counts as earnings for dues.
- Requests from the city: a notice board in the plaza lists what people want (a particular kind of broken artifact, which you must have identified, or any broken artifact of a rarity) and what they'll pay, well over the shops. Hand it over by talking to whoever asked. Up to three at a time, one per person; new ones every Cycle; each stands 27 Pulses.
- The job board and requests belong to the city (saved with it, kept when a Hunter dies); the jobs a Hunter takes are theirs.
- Numbers are in `data/work.json`.

## 0.25.0: Guild dues, travel-to, rolled kits (2026-11-18)
- Guild dues: on the first Pulse of each Reckon, the Guild is owed a share (20%) of the shards you've earned since the last dues (picked up, or from selling and consigning). Pay the guild clerk; until you do, the gates' contract boards are closed to you. What's owed shows in the side panel and on the character sheet. Dues belong to the Hunter: a new Hunter starts clean.
- `t` travel-to: pick a known place and walk there a step at a time, stopping like auto-explore (a new creature in view, being hurt, anything in the log, something in the way). In the city: the stash, the people who keep shops or teach, and the gates. On a hunt: the passages you've found, and the artifact once seen.
- New Hunters' starting kits are rolled: a short sword, hand axe, or short bow with 20 arrows; a leather jerkin or nothing; random supplies; 5-30 shards.
- Auto-explore and travel no longer route around creatures you can't see (that gave them away); they stop if something is actually in the way.
- The character sheet scrolls (Esc or c closes it).

## 0.24.0: The four gates (2026-11-18)
- The gates and regions now have their names and character: the Tower Gate to the northern mountains (caves, danger 2-3); the Crumbling Gate to the eastern ruins (ruins, 2-4); the Woodgate to the southern forests (forest at night, 3-5, larger areas); the Towerway to the western forests (forest by day, 1-2).
- Contract boards are titled with the gate ("The Tower Gate: Contracts").
- The guild clerk now points new Hunters to the Towerway.

## 0.23.0: Message history and key reference (2026-11-18)
- `m` opens the message history: the last 500 messages, newest at the bottom; ↑↓ a line, PgUp/PgDn a page, Home/End; `m` or Esc closes. Saves now keep the last 200.
- `?` (or F1) opens a key reference, scrollable the same way.
- A new game reminds you of both.

## 0.22.1: Auto-explore stops at passages (2026-11-18)
- Auto-explore stops the first time a passage comes into view ("You've found the way deeper."). Press `o` again to carry on exploring.

## 0.22.0: Auto-explore (2026-11-18)
- `o` auto-explores a hunt area: walks to the nearest unexplored ground, one turn a step, collecting shards on the way.
- It stops when a creature comes into view, when you're hurt, at anything else lying on the ground (pressing `o` again moves on), and when anything is said in the log (a torch going out, a fading windcatcher...). It won't start with a creature in view.
- It never takes a passage, the trail home or a gate. When there's nothing left, it says so and names the ways on you've found.
- Not in the city: there's nothing to explore there.

## 0.21.0: Bows and Marksmanship (2026-11-18)
- Bows: the short bow (1d6, range 8) and the longbow (1d8, range 12), wielded in the weapon slot. Wielding one makes you an Archer. Up close a bow is only a bash (1d2).
- `f` to aim: the cursor starts on the nearest creature in range; Tab cycles; the arrow's path is shaded; the panel shows the chance to hit and warns if something's in the way or out of range. Enter or `f` shoots (a turn passes).
- Arrows fly straight and hit the first creature in the way; walls stop them. Each shot uses an arrow; half survive to be picked up. Ranged damage is the bow's dice (no Physicality bonus), minus armour.
- Marksmanship, the second skill: +2 ranged accuracy per rank above 1; -1 accuracy for every 3 cells of distance. Every shot at a creature is practice (a hit counts double); Celerity speeds it. Practice takes you to rank 2; after that, training.
- A trainer in the guild hall ("Bumpry Archer Hunters") trains Marksmanship through conversation (new dialogue effect `train:ID`).
- The supplier sells bows and arrows (in bundles of 10). A short bow and 20 arrows lie in the guild hall for testing.

## 0.20.0: Townsfolk and conversations (2026-11-18)
- People in Bytorsskug have names, descriptions and conversations (`data/townsfolk.json`, `data/dialogue/`). Walk into someone to talk: what they say, then numbered choices (↑↓ or 1-9, Enter; Esc leaves). Talking takes no time.
- Conversations can check conditions (flags, items, shards, skill rank, level, Duel, holiday) and have effects (set flags, give or take items or shards, open a shop, the workshop or the stash). `data/dialogue/_README.md` explains the format.
- The supplier and the artificer now talk first; their shop or workshop is one of the choices.
- New: a guild clerk at the front of the guild hall, and a porter, a washer and a carter who wander the plaza.
- Flags follow the persistence rule: a Hunter's are lost when they die; the city's outlive Hunters.

## 0.19.1: Fix (2026-11-18)
- Item descriptions are no longer cut off in the shop, workshop, inventory and contract board: each window now sizes its detail area to fit the whole text (the list shrinks to make room).
- The windcatchers' descriptions no longer repeat their effect line.

## 0.19.0: Limited, persistent stock (2026-11-18)
- Shops and the workshop have limited stock that restocks over time (each item: a maximum, and Pulses to restock one). Stock is world state: saved, kept when a Hunter dies, full again only in a new game.
- Things you sell to a shop go up for sale there at full value (bought back, they're gone for good). Artifacts you consign go up for sale at the workshop.
- The workshop has one lesser windcatcher, restocked once a Reckon (81 Pulses).
- Buy lists show how many are left, or "sold out".

## 0.18.0: Artifact slots and the guild stash (2026-11-18)
- Three artifact slots, separate from the bag. A working artifact only does anything (passive or used) while equipped in one; equipping takes it out of the bag. The windcatcher keeps its own slot.
- The inventory screen lists the bag, then the artifact slots: `e` equips (or takes off), `u` uses, `d` drops.
- The guild stash: a chest in the guild hall's middle back room. Walk into it to move things between your pack and the stash (60 slots). It belongs to the hall, so a new Hunter inherits it; a new game starts it empty.
- The character sheet is more compact and lists equipped artifacts.

## 0.17.1: Fix (2026-11-18)
- The "Fallen" card no longer repeats the date.

## 0.17.0: Time moves (2026-11-18)
- The game begins at the start of Turn 211.
- Compact dates: "Light Duel: Emu, C1, R1, J1, T211" (two lines in the side panel; holidays read "Holiday 2/4, T211 / after the Light Duel").
- A Pulse passes with every move between areas: setting out, going deeper, coming back, walking home. A completed hunt is a whole Cycle (9 Pulses). A new Hunter after a death is still one Pulse.
- Save slots list name, level and place; the selected slot's date shows below the list.

## 0.16.0: The calendar (2026-11-18)
- Days are Pulses on the calendar: Pulse (Emu, Lagau, Erku, Maforu, Nusu, Senu, Riu, Dymiu, Neu) → Cycle (9) → Reckon (9) → Judgment (12) → Duel (4). A Turn is the Light Duel, 4 holiday Pulses, the Dark Duel, 4 holiday Pulses.
- The side panel shows the date in three lines; title cards, the new-Hunter message, the "Fallen" card and save slots use it too.
- The start of each Duel and of each holiday is announced in the log.
- The game starts on Emu, Cycle 1, Reckon 1, Judgment 1 of the Light Duel, Turn 1 (`data/calendar.json`).
- Names: the VL syllable pattern is added (Ylfa can now come up).

## 0.15.0: Hunters with names (2026-11-18)
- Every new Hunter (New Hunter, or after a death) is random: given name, gender and attributes.
- Given names follow the phonetic rules in `data/names.json` (sound classes, syllable patterns, allowed consonant clusters).
- Full names: Given, Calling, Hunters. Every Hunter's surname is Hunters (after the Guild); the middle name comes from the wielded weapon (Fencer for swords, Hewer, Breaker; Brawler bare-handed) and changes with it.
- Attributes: each starts at 8 and 10 points are handed out at random (none above 14), the same total as before.
- The font gains þ and Þ (drawn from GNU Unifont, `data/font_extra_8x16.png`).
- Attributes are off the side panel; they're on the character sheet (`c`), which now shows gender too.

## 0.14.0: Supplies (2026-11-18)
- Torches: light one from the inventory (`u`) in a dark place for +3 light for 300 turns. Fire, not Jodebris: it works with no windcatcher, or an empty one. One at a time; the stronger of torch and artifact light counts. Warns when burning low; put out when you get home.
- Rations heal over time: 1 HP a turn for 10 turns (now 4 shards). One at a time.
- Rope is an escape item: use it on a hunt to go straight back to the trail home. With the artifact, the hunt is complete; without, you're asked whether to give up (say no and you stay at the trail home). Now 10 shards, and stacks.
- The side panel shows a burning torch and a ration's mending.

## 0.13.0: Windcatchers and Jodebris (2026-11-18)
- Tower Artifacts run on Jodebris, the Chorus Winds. In Bytorsskug they work freely; out on a hunt, in the miasma, they do nothing without a windcatcher.
- Windcatchers store Jodebris. Equip one (`e`) and a Jodebris bar appears under the HP bar. On a hunt it drains 1 per turn, plus 25 each time you use an artifact; it warns you at a quarter, and when it's empty your artifacts go still. It refills when you're back in Bytorsskug.
- Three windcatchers: lesser (Rare, 1200), windcatcher (Very Rare, 1800), great (Legendary, 2800). Found broken on dangerous hunts, looking like any glass artifact.
- The artificer's workshop has a Buy tab and sells a lesser windcatcher for 900 shards.

## 0.12.0: Artifacts, Artificers and Identification (2026-11-18)
- Tower Artifacts have rarities: Common, Uncommon, Rare, Very Rare, Legendary, Unique. Contracts pick rarer ones at higher danger.
- Eleven broken artifacts, each with a working form that does something: more light in the dark, armour, accuracy, evasion, healing, mapping the area (placeholders).
- Unidentified artifacts show only their appearance and rarity.
- The first skill, Identification: study a broken artifact (`u` in the inventory) to identify it. Your rank is the highest rarity you can identify. Practice raises it to rank 2; higher ranks are trained at the workshop for shards. Acumen speeds practice.
- The artificer's workshop, near the plaza: repair (pay the fee, keep the working artifact), sell broken (small price), or consign (paid at once: (working price − fee) ÷ 2).
- `c` opens a character sheet with your skills.
- Shops point you to the Artificers when you try to sell them artifacts.

## 0.11.0: Looking around (2026-11-18)
- `x` enters look mode: move a cursor with the movement keys, or Tab between the creatures, people and items in view.
- Creatures: description, how hurt they are, whether they've noticed you, how dangerous they look.
- Respects what you can see: remembered places show remembered items but no creatures; unseen places show nothing.
- Every placeholder creature has a description (`data/monsters.json`).
- Looking takes no time.

## 0.10.0: Shops (2026-11-18)
- A supplier's shop on the plaza in Bytorsskug. Walk into the shopkeeper to trade.
- Buy draughts, rations, torches, rope, and better weapons and armour.
- Sell ordinary finds for half their value. Artifacts and keys can't be sold.
- New gear: arming sword, war pick, studded jerkin, mail shirt, healing tonic.
- Shops and their stock are data (`data/shops.json`); shopkeepers are placed in map files (`;npc=`).
- Version numbers: shown in the side panel and on the title menu, recorded in saves and crash logs.

## 0.9.0: Saving and loading
- Title menu: Continue, Load game, New Hunter, Quit.
- Autosave on quitting, setting out, changing area and coming home; quitting mid-hunt saves the hunt as it is.
- Three manual save slots, usable only in safe zones such as Bytorsskug.
- A Hunter's death deletes every save holding that Hunter.
- `Esc` opens an in-game menu.

## 0.8.0: Bytorsskug
- The city rebuilt after the user's plan: wall and towers, river, plaza, four gates, a western suburb.
- Two-cell-wide streets and bridges; 94 rectangular and L-shaped houses, each with a door.

## 0.7.0: Combat
- Creatures in hunt areas that notice, chase and attack you.
- Hit rolls (Celerity) and damage (weapon dice, Physicality, armour).
- Wielding, wearing and drinking from the inventory.
- One faint per hunt, then permadeath; a new Hunter takes up the work.
- Natural healing; fully healed on returning home.

## 0.6.0: Fog of war
- Line of sight in hunt areas; explored places remembered, dimmed.

## 0.5.0: Hunts
- City gates with contract boards; departure and return title cards.
- Generated areas in three styles (caves, ruins, forest), chained 3 to 5 deep.
- Broken artifacts to recover and carry back to the trail home.

## 0.4.0: The Hunter
- Attributes (Physicality, Celerity, Fortitude, Acumen, Tenacity), HP, levels.
- Inventory, items lying on maps, picking up and dropping.
- Money is shards.

## 0.3.0: The city and the camera
- A large city map; the camera follows the player.
- Info panel on the right; joined-line walls and rough stone.

## 0.2.0: The look
- ASCII with the GNU Unifont pixel font; screen sized to the window.

## 0.1.0: First steps
- Grid movement in eight directions, walls, turns; Python and tcod; `Play.bat`.
