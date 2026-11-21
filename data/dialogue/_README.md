# Writing conversations

One file per conversation (`data/townsfolk.json` says who uses which). A
conversation is a set of **nodes**; each node is something the person says,
followed by **choices** for the Hunter.

```json
{
  "start": [
    {"if": ["!flag:hunter:met_clerk"], "node": "first"},
    {"node": "hello"}
  ],
  "nodes": {
    "first": {
      "text": "Welcome to the hall, {given}.",
      "do": ["set:hunter:met_clerk"],
      "choices": [
        {"text": "Who are you?", "goto": "who"},
        {"text": "Goodbye.", "end": true}
      ]
    }
  }
}
```

- **start**: the first node, or a list of `{"if": [...], "node": ...}` tried
  in order (the first whose conditions all hold).
- **text**: what they say. A list of strings means "pick one at random".
- **do** (on a node or a choice): effects, applied when the node is shown or
  the choice is picked.
- **rumor** (on a node, `true`): instead of its text, the person says what
  they've heard today (`data/rumors.json`): now and then one of the
  Wayfinder's words you don't know yet, which you learn; otherwise small talk.
  The plaza folk (porter, washer, carter) have it behind "Heard anything lately?".
- **choices**: each has `text`, and `goto` (another node), or `end: true`,
  and optionally `if` (shown only when its conditions hold) and `do`.
  A node with no choices gets a single "(Leave)".

**Conditions** (`!` in front means "not"):
`flag:hunter:NAME`, `flag:world:NAME`, `item:ID` (carrying at least one),
`item:ID:N`, `shards:N` (at least N), `skill:ID:N` (rank at least N),
`level:N`, `duel:Light Duel` / `duel:Dark Duel`, `holiday` (an intercalary Pulse),
`dues` (the Hunter owes Guild dues), `jobs_done` (an odd job is finished and unpaid), `orders_ready` (a commission is ready), `injured` (the Hunter has a lasting injury), `writings` (the Hunter carries a writing), `notes` (the Hunter has field notes to report), `mentor_teaches` (the retired Hunter in the guild hall has a skill to teach), `rank_ready` (the Hunter can sit for the next rank), `rank:N` (at least the Nth rank), `trophies` (the Hunter carries a trophy).

**Effects**: `set:hunter:NAME`, `set:world:NAME`, `clear:hunter:NAME`,
`clear:world:NAME`, `give:ID` / `give:ID:N`, `take:ID` / `take:ID:N`,
`shards:+N` / `shards:-N`, `pay_dues` (pays what the Hunter can of their dues), `collect_jobs` (pays for finished odd jobs), `jobs` (opens the odd-job board), `craft:CRAFTER` (opens what a crafter makes, data/recipes.json), `collect_orders` (hands over finished commissions), `treat:HEALER` (opens the healer's list of your injuries and fees), `hand_in_writings` (gives the librarian every writing carried, for pay), `library` (opens the Academy library), `report_notes` (files field notes with the Guild archive, for pay), `archive` (opens the Guild archive), `hall` (opens the Hall of Hunters), `retire` (asks to retire the Hunter), `mentor` (opens the retired Hunter's cheaper training), `sit_rank` (sit for the next rank, paying the fee), `labour` (offers to work off dues), `trophies` (the trophymaster's window: hand in a trophy), `butcher` (the butcher's: break one down), `trophy_wall` (the records), `shop:ID`, `workshop:ID`, `stash`, `train:SKILL`
(or `train:a,b` for several; these four end the conversation and open that
screen).

**Flags** follow the persistence rule: `hunter` flags belong to the Hunter and
are lost when they die; `world` flags belong to Bytorsskug and outlive Hunters.

**In text**: `{given}` (the Hunter's given name), `{name}` (full name),
`{calling}` (their middle name), `{date}`, `{pulse}` (today's Pulse name),
`{dues}` (dues owed), `{earned}` (shards earned since the last dues).

**Requests** need no writing: when someone has a request up on the plaza
notice board, their conversation's opening node gets a choice to hand the
thing over (if the Hunter has it, and has identified it when a particular
kind is wanted) or to ask about it.
