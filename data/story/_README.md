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
| `day` | each new Pulse | |
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

## Testing without the story

Set the environment variable `TAG_NO_STORY=1` and the game loads no story files
(the balance bot does this, and so do the tests of everything else).
