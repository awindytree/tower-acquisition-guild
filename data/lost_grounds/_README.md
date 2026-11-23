# Lost Grounds: the writer's guide

A Lost Ground is a hand-built place out in the miasma that the Wayfinder takes you to when you
choose its three words. It's the same every visit, and it's **persistent**: what one Hunter takes
or leaves there stays taken or left for every Hunter after. They're for lore and story.

## Making one
1. Pick three words: `[danger, land, feature]`, ids from `data/keywords.json`. Story words
   (`"story": true`) work and keep the words out of the boards, rumours and the scholar, so the
   story decides how a Hunter learns them. The danger word still has to be one the Hunter's rank
   allows at the Wayfinder.
2. Draw the map, `data/lost_grounds/<id>.txt`, in the usual map format (see `examples/hollow.txt`):
   - `;title=` the name shown on the map; `;light=lit` or `;light=dark`; `;fog=on` to explore it.
   - `;gate=x,y out` **(required)** on the way back (draw an `H` there): walking onto it brings the
     Hunter out at the edge of the Brisering (on the land word's side), to walk home. They arrive
     on the walkable cell beside it.
   - `;item=x,y id [count]` puts something there the first time. Once taken, it's gone for good.
   - `;monument=x,y id` and an `S` tile: something to read (its text is in the ground's JSON).
3. Write `data/lost_grounds/<id>.json`:
   ```json
   {"name": "The Example Hollow",
    "words": ["quiet", "craggy", "letters"],
    "map": "<id>.txt",
    "arrive": ["Lines for the card the first time anyone comes here."],
    "again": ["Lines for later visits (optional; else the first ones)."],
    "monuments": {"stone_id": {"name": "...", "look": "...", "title": "...", "text": ["..."]}},
    "ambience": "ruins"}
   ```
   `ambience` (optional) is a key from `data/sounds.json` "ambience" (forest, caves, ruins,
   mountains, plains...; the `_night` version plays on a torch-lit map). Without it, the land
   word's terrain sets the sound.
4. Story hooks: the event `lost_ground` fires on arrival (`event:ground=<id>`, `event:first=True`),
   and the condition `visited:<id>` holds once anyone has been there. Story items can be hidden
   with `;item` or given by a scene.

Files starting with `_` and anything in `examples/` aren't loaded by the game.

## How it plays (for now)
- Going and coming out take a Pulse each; then the walk home from the edge of the Brisering
  (the Wayfinder is one way, v0.89.0). It's in the miasma: windcatchers drain, artifacts need
  one, torches burn. There are no creatures there yet.
- A Lost Ground is never a hunt: its words always lead there. The Guild's boards, errands and
  bounties never use them, and work an older save held there is withdrawn when it loads.
