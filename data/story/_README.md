# Writing the story

Everything story-related lives in JSON files in this folder. The game reads
**every `*.json` file directly in `data/story/`** (not files starting with `_`,
and not the `examples/` folder) and merges them, so you can split the story
however you like: one file per chapter, per place, per character.

The game's story so far: `first_jobs.json` (v0.54.0): the clerk's first jobs, which teach a
new player the game. The rest of the story is being written.

`examples/example.json` is a complete working example. It isn't loaded by the game;
copy it up into this folder to try it in play. It uses only things that already
exist (the clerk, the trainer, the librarian, an old key).

A file can have four sections: `quests`, `scenes`, `talk` and `contracts` (key hunts).

## Whose story is it?

Story progress belongs to **the world** by default: when a Hunter dies or
retires, the story carries on with the next one, just as the city does. A quest
marked `"scope": "hunter"` belongs to one Hunter instead and ends with them.
Scenes seen, counters and story items are always world state.

## Quests

```json
"quests": {
  "the_lost_key": {
    "title": "The clerk's errand",
    "scope": "world",
    "stages": [
      {"id": "see_clerk", "log": "...", "goal": "...", "until": ["..."], "do": ["..."]},
      {"id": "find_key",  "log": "...", "goal": "...", "until": ["item:old_key"], "next": "return_key"}
    ],
    "done_log": "Written in the log when it's finished.",
    "on_done": ["shards:+20"]
  }
}
```

- A quest starts with the effect `start:QUEST` (from a scene, a conversation or
  another quest) and enters its first stage.
- Each **stage** can have:
  - `log`: a line added to the quest log when the stage begins;
  - `goal`: what the quest log says to do now;
  - `do`: effects when the stage begins (hide an item, set a flag, play a scene...);
  - `until`: conditions that move the quest on by themselves when they all hold
    (checked every turn and after every event);
  - `next`: which stage follows (default: the next one in the list; `"done"`
    finishes the quest).
- A quest can also be moved on by effects: `advance:QUEST`, `stage:QUEST:STAGE`,
  `finish:QUEST`, `fail:QUEST`, `note:QUEST:text` (an extra log line).
- When it finishes, `done_log` goes in the log and `on_done` effects happen.

## Scenes

A scene is something that happens when an **event** occurs and its conditions
hold: some pages of text on screen, choices at the end, effects. A scene with
no pages is a silent trigger (handy for counting things).

```json
"scenes": {
  "a_note": {
    "on": "new_game",
    "if": ["..."],
    "once": true,
    "title": "A note",
    "pages": ["Plain text.", {"speaker": "Someone", "text": "Spoken text."}],
    "choices": [{"text": "...", "if": ["..."], "do": ["..."]}],
    "do": ["effects when it plays"]
  }
}
```

- `once` (default true): it plays only once in the world's history.
- **Events** (`on`), and what the condition `event:KEY=VALUE` can check:

| event | when | event: values |
|---|---|---|
| `new_game` | a new game begins | |
| `new_hunter` | a new Hunter joins (after a death or retirement) | |
| `set_out` | the Hunter sets out through the Wayfinder | `region` (the place: `danger/land/feature`, e.g. `quiet/green/daybreak`) |
| `area` | the Hunter enters an area of a hunt | `region`, `area` (1, 2, ...) |
| `kill` | the Hunter kills a creature | `monster`, `region` |
| `pickup` | the Hunter picks something up | `item` |
| `home` | back in the city from a hunt (after the rest) | `success` (True/False), `region`, `free` (True for a trip without a contract) |
| `pulse` | each new Pulse (the old name `day` still works) | |
| `retire` | the Hunter retires | |
| `death` | the Hunter dies (killed, or of old age) | |
| `contract_done` | a key hunt is brought home | `contract` |
| `contract_failed` | a key hunt ends without its prize | `contract` |

## Contracts: key hunts on the Guild's contracts board

```json
"contracts": {
  "proving_hunt": {
    "words": ["restless", "green", "tusks"], "rank": "Recruit", "depth": 3,
    "title": "The clerk's proving hunt",
    "description": "Shown on the board when it's selected.",
    "prize": "broken_astrolabe",
    "guardian": "thornback_boar",
    "done_text": ["Lines on the card when you bring it home."],
    "on_done": ["shards:+30"]
  }
}
```

- `words` (since v0.44.0): the place, as three keywords from `data/keywords.json`:
  danger, land, feature. The same words always make the same place (the same
  layout), so a key hunt can be written for a place the player can visit again.
  Taking the hunt teaches the player its words.
- `post:ID` puts it on the Guild's contracts board in the guild hall, listed first
  and marked ☼ (once; never again after it's done). `unpost:ID` takes it down. A
  Hunter takes it from the board, then walks into the Wayfinder and chooses
  its words.
- `rank` (a rank's name or number) is the rank it's posted for. A Hunter below it
  sees it greyed out: **rank up a Hunter to continue.**
- The danger comes from the danger word; `depth` (areas) defaults to the danger
  word's depth.
- `prize` (any item id) waits at the far end of the last area, with the
  `guardian` (any creature id, optional) beside it. The prize counts as a story
  item: if a Hunter dies carrying it, it goes to the guild stash. A new story item
  goes in `data/items.json` with `"kind": "key"` and `"glyph": "µ"` (all story items
  use µ).
- Bringing the prize home completes it: it comes off the board, `on_done` effects
  happen, `done_text` is on the card, and the `contract_done` event fires. Turning
  back or dying leaves it posted (`contract_failed` fires).
- Rivals never take key hunts.
- Conditions: `posted:ID`, `completed:ID`.

## Talk: story lines in anyone's conversation

```json
"talk": [
  {"id": "clerk_key", "folk": "clerk", "if": ["quest:the_lost_key:see_clerk"],
   "text": "You wanted to see me?", "reply": "I lost a key...", "do": ["..."], "once": true}
]
```

When the conditions hold, the Hunter gets `text` as a choice when they talk to
that person (`folk` is their id in `data/townsfolk.json`). Picking it shows
`reply` (a list picks one at random) and applies `do`. With `once` (the default)
it's offered only until it's been said; `seen:ID` checks that it has.

## Conditions

Any list of conditions must all hold. Put `!` in front of one to turn it around.

- **Story:** `posted:C`, `completed:C` (key hunts), `quest:Q` (under way), `quest:Q:STAGE` (at that stage), `started:Q`,
  `done:Q`, `failed:Q`, `seen:SCENE_OR_TALK_ID`, `count:NAME>=N` (also `>`, `<`,
  `<=`, `=`, `!=`), `on_hunt`, `region:DANGER/LAND/FEATURE` (on a trip to that place),
  `word:ID` (on a trip to a place using that word), `knows:ID` (the word is known), `event:KEY=VALUE` (scenes).
- **From conversations** (data/dialogue/_README.md): `flag:world:NAME`,
  `flag:hunter:NAME`, `item:ID`, `shards:N`, `skill:ID:RANK`, `level:N`, `duel:...`,
  `holiday`, `dues`, `injured`, and the rest listed there.

## Effects

- **Story:** `start:Q`, `advance:Q`, `stage:Q:STAGE`, `finish:Q`, `fail:Q`,
  `note:Q:text`, `count:NAME:+N` (or `-N`, `=N`), `scene:SCENE` (play it now),
  `post:C` / `unpost:C` (a key hunt on the contracts board), `learn:WORD[,WORD]` (words for the
  Wayfinder), `hide:ITEM:PLACE[:AREA]` (PLACE is `danger/land/feature`; the item waits in the next trip there, in that area
  or the last; it comes back if not found, and goes to the guild stash if the
  Hunter carrying it dies), `message:text` (a line in the message log).
- **From conversations:** `set:world:NAME`, `clear:hunter:NAME`, `give:ITEM[:N]`,
  `take:ITEM[:N]`, `shards:+N`, opening shops, training and so on.

## Text

Any text can use `{given}` (the Hunter's given name), `{name}` (their full name),
`{calling}`, `{date}`, `{pulse}`, `{dues}`, `{earned}`, and **any counter by name**
(`{example_dogs}`).

## The quest log

`q` opens it: quests under way and finished, the current goal, and every log line so far.

## Added in v0.54.0 (for the clerk's first jobs, and for later)

- **Events:** `talk` (when you talk to someone, before the conversation opens: `event:folk=ID`;
  a scene it queues plays instead of the conversation), `wayfinder` (walking into the Wayfinder;
  its scenes play before its window opens), `see` (a creature seen for the first time:
  `event:monster=ID`), `bounty_paid` (`event:bounty=ID`), and `manual` (never fired: a scene
  played only by a `scene:ID` effect).
- **Conditions:** `taken:CONTRACT` (you hold that story contract), `bounty:ID` (you hold that
  story bounty), `bounty_done:ID` (and have done it).
- **Effects:** `only:contracts:CONTRACT` / `only:bounties:ID` (that board offers only the one
  posting; the rest are greyed out and refused), `only:clear`; `bounty:ID` (post a story bounty).
- **Story bounties:** a `bounties` section: `{ "ID": {"words": [d, l, f], "title": "...",
  "reward": N, "kind": "kill", "creature": "ID" (or left out: the board's own pick),
  "description": "..."} }`. Shown first on the bounty board with ☼; kept when the board is
  renewed; rivals leave it alone. Paid by the clerk like any bounty.
- **Contracts** can also set `heading` (the line above the details on the board),
  `posted_line` (the log line when it goes up), `card_heading` (the end card's heading) and
  `"story_item": false` (the prize is an ordinary find, not a story item).
- **Scenes** with `"style": "popup"` sit over the map instead of filling the screen.

## Kinds of story, title cards, variants, dates (v0.66.0)
The user's frame (design in `claude/design-story-presentation.md`): the world is the main character; a Hunter can have small stories of their own; important beats are scenes, lore and character mostly conversation; no narrator; tips are popups.

**Kinds.** Give a quest a `kind`, a `number` (all but `calling`) and a `title`. Its heading is made from them, used in the log, the quest log and the title cards:

| kind | heading | belongs to |
|---|---|---|
| `chapter` | Chapter 1: Well Past Due | the world (the main story) |
| `paralogue` | Paralogue 4: Passing Wind | the world (a storylet) |
| `log` | Character Log 7: But Why Tinkerforge? | the world (a person's story) |
| `calling` | Hewer Calling: The First Axe (`"calling": "Hewer"`) | the Hunter |
| `hunter_log` | Hunter Log 1: A Sound Like Singing | the Hunter |
| (none) | the title, as before | the world |

- **Belonging:** `calling` and `hunter_log` quests are the Hunter's (`"scope": "hunter"` by default). They die with the Hunter and can start again for the next one.
- **Cards:** when a kind of story begins, a title card shows its heading ("Chapter 1"), its title, and `intro`. When it's complete, the card shows `outro` and "Complete". `"cards": false` turns them off.
- **The quest log** lists them in this order: chapters, paralogues, character logs, callings, Hunter logs, then plain quests.

**Variants.** Any text the story shows can be `{"variants": [...]}` instead of a string:
- **Where:** scene pages, talk replies, conversation node text, quest `intro`/`outro`/`done_log`/`recap`, and stage `log`/`goal`/`recap`.
- **Picking:** each time, the game picks one this world hasn't used for that text yet. When all have been used, they come round again.
- **Conditions:** a variant can be `{"text": "...", "if": [conditions]}`; it's only picked when they hold. Use this so a Hunter's story reads differently for each Hunter. For example, the trainer says something else to a new Hewer if a Hewer has died before.
- **Random lists:** a plain list still means "pick one at random each time", as before.

**Conditions about the Hunter** (for variants and Hunters' stories):
- `calling:Hewer`
- `gender:female`
- `sensitive`: one of the rare Jodebris-sensitive Hunters.
- `age>=N`: the Hunter's age in Judgments.
- `hall>=N`: Hunters remembered in the Hall.
- `fallen:Hewer`: a Hunter of that calling has died.

**Dates:**
- **Conditions:** `date:turning_pulse` (the first Pulse of a Turn), `date:holiday` (the holiday Pulses after a Duel), `date:duel=light|dark`, `date:pulse=Emu`, `date:cycle=N`, `date:reckon=N`, `date:judgment=N`. Use them in scenes `"on": "pulse"` (fired every Pulse).
- **The rule (user):** a date may **start** a story or **add colour**. It may never hold a story step back for longer than a Cycle. A quest stage's `until`, or a scene or talk line that advances, stages, finishes, fails or posts something, can't wait on `turning_pulse`, `holiday`, `duel`, `cycle`, `reckon` or `judgment`; the game refuses to load it. `date:pulse=...` (every Cycle) is fine.

**The Story So Far.** When a new Hunter joins (not on a new game), a card recaps the main story:
- Each finished chapter's `recap`.
- Then the current chapter's stage `recap` (or the chapter's `recap_now`).
- Give every chapter a `recap`, and its stages one each, so a returning player knows where the world stands.

**Tips.** A scene with `"style": "tip"` is how-to-play information. It sits over the map in a sea-glass frame titled "Tip" (or its own title). Story moments use a plain scene or `"style": "popup"`. The clerk's first jobs use tips for their instructions.

**Starting a Hunter's story:** use scenes `"on": "new_hunter"` (and `"on": "new_game"` for the first Hunter) with conditions like `calling:Hewer` or `sensitive`, and `"do": ["start:QUEST"]`.

A worked example of every part: `data/story/examples/frame/frame.json`.

## Added in v0.67.0 (for Chapter 1: Three Words)

**Catching up old saves.** Scenes `"on": "load"` run whenever a save is loaded. Chapter 1 uses two (with `"once": false`) to start itself in saves whose first jobs ended before it existed. Do the same when a new chapter hangs off something an existing save may already have done.

**Scene order.** A scene's pages are queued before its effects run, so a card or tip its effects bring comes after its pages. To show a card first (an act's name, say), put it in a scene of its own, with no pages, listed just before, on the same event.

**Key hunts:**
- `"hidden_words": true`: the board shows `[?]` for each word the Hunter doesn't know yet. Taking the hunt doesn't teach the words. Whoever goes to the place with all three words is on it, whether they took it or not.
- A story danger word is allowed at the Wayfinder for any rank while a posted story hunt open to that Hunter uses it.
- `"prize_folk": "FOLK"`: the prize is a person. FOLK (a townsfolk id) waits at the far end, and its conversation carries them off with `carry:ITEM:FOLK`. ITEM is the person as a pack item: kind `key`, `"slots": N` for how much room they take, `"no_drop": true` so they can't be left behind. Bringing them home completes the hunt, like any prize.
- `"guardians": N`: N guardians at the prize, not 1.

**Story words:** a word with `"story": true` in `data/keywords.json` is never posted on a board, heard in a rumour, taught by the scholar, or picked for a random place. The story teaches it (`learn:`, a writing's `teaches`).

**Story writings:** `"story": true` in `data/writings.json` keeps a writing out of hunts, and out of the library's count until the story shelves it.

**Story-locked artifacts:** `"properties": {"locked": true}` on an artifact means it is never found by chance or asked for, and the artificer won't study, repair, buy or consign it.

**New effects:**
- `card:HEADING|LINE|LINE...` shows a title card.
- `appear:FOLK` puts a story person in the guild hall for good, at their townsfolk `"hall_spot": [dx, dy]` (from the hall's corner) or the nearest free floor.
- `remember:FOLK[:CAUSE]` adds them to the Hall of Hunters, from their townsfolk `"hall"` entry: `age_turns`, `age_judgments`, `level`, `hunts`, `served_judgments`, `rank`.
- `to_stash:ITEM` moves an item from the pack to the guild stash.
- `fund:PROJECT:N` puts N shards toward one of the Guild's works.
- `shelve:WRITING` puts a writing in the Academy library.
- In conversations, `carry:ITEM:FOLK` picks someone up (above).
- In conversations, `teach:FOLK` opens training with a story mentor: their townsfolk `"teaches": {"skill": cap}` and `"off"` (0.2 = 20% off the trainer).

(`hall` and `works` open those screens, so the effects that add to them are `remember` and `fund`.)

## Testing without the story

Set the environment variable `TAG_NO_STORY=1` and the game loads no story files
(the balance bot does this, and so do the tests of everything else).
