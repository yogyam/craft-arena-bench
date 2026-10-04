# The CraftArenaBench interface, version 1 (draft)

This is the contract between a model and the benchmark: what the model is told, what it can choose, how often it is asked, and what the body does on its own. Every bot on a leaderboard uses the same interface version.

**Status: draft, before any code.** This is the document to argue with. Everything marked *open* is a question we want opinions on before it is fixed. Once code exists, the reference implementation is `src/craft_arena_bench/` and if this document and the code disagree, the code is right and this document has a bug.

## Summary

| | |
|---|---|
| Format | 1v1, two modes: Sumo and Block UHC |
| Game | Minecraft 26.1.2 on a Paper server, offline mode, no mods, no plugins |
| Body | One Mineflayer client per bot; reflexes at 20 ticks per second |
| Decisions | At a fixed rate per tier: 2, 5 or 20 per second |
| Request | HTTPS POST with the fight state as JSON and as text, and the list of legal actions |
| Response | One action id, optionally with a confidence |
| Late answer | The previous intent continues; counted; more than 20% late in a match forfeits it |
| Entrant runs | Nothing. Only the endpoint |

## The endpoint

An entrant hosts one HTTPS endpoint. The harness calls two routes.

`GET <url>/health` must answer `200` with:

```json
{ "interface_version": 1, "name": "my bot" }
```

It is called in the submission check and at the start of every scoring run. A bot whose health check fails is skipped for that run.

`POST <url>/decide` receives the request below and must answer `200` with the response below, within the tier's budget. Any other status, a body over 4 KB, invalid JSON, or a `choice` that is not one of the offered action ids all count as a missing answer. The harness sends no cookies, follows no redirects, and sends nothing but fight state. Entrants who need a token put it in the URL and should know the URL is public.

The harness opens one connection per match and keeps it alive. Requests for one match arrive strictly one at a time: the next decision is not asked for until the previous one has arrived or timed out.

## Tiers

A tier fixes how often the model is asked. Between decisions the body keeps executing the last chosen intent with its reflexes.

| Tier | Asked every | Budget for the answer |
|---|---|---|
| 2 Hz | 10 ticks (500 ms) | 400 ms |
| 5 Hz | 4 ticks (200 ms) | 150 ms |
| 20 Hz | 1 tick (50 ms) | 40 ms |

The budget is measured by the harness from sending the request to receiving the full response, so it includes network time. Entrants choose which tiers to enter; a bot has a separate rating per tier and mode.

A **late** answer is one that arrives after the budget. It is discarded, the previous intent continues, and the lateness is counted. A **missing** answer (connection error, bad status, bad body) is treated the same way. If more than 20% of a match's decisions are late or missing, the bot forfeits that match. The fraction of late answers and the median latency are published next to the rating.

*Open:* whether the 20 Hz tier is in season 1 at all. On a free CI runner the harness itself may not keep a 50 ms clock reliably; stage 2 measures this.

*Open:* the budgets. 400/150/40 ms leave the harness 100/50/10 ms to build the request and apply the answer. Too tight for a remote API at 5 Hz? Tell us.

## The request

```json
{
  "interface_version": 1,
  "mode": "block_uhc",
  "tier_hz": 5,
  "match_id": "8f3c...",
  "decision": 231,
  "tick": 924,
  "seconds_left": 133.8,
  "sudden_death": false,

  "self": {
    "pos": [3.5, -60.0, -2.5], "yaw": 87.0, "pitch": -4.0,
    "velocity": [0.12, 0.0, -0.05], "on_ground": true,
    "health": 17.5, "food": 20, "absorption": 0,
    "held": "diamond_sword",
    "inventory": {"arrow": 12, "cobblestone": 61, "water_bucket": 1, "lava_bucket": 1, "bow": 1, "diamond_sword": 1},
    "effects": [],
    "last_intent": "strafe_left",
    "late_answers": 2
  },

  "opponent": {
    "pos": [9.1, -60.0, 1.0], "yaw": 265.0, "pitch": 2.0,
    "velocity": [-0.2, 0.0, 0.0], "on_ground": false,
    "held": "bow", "visible": true, "distance": 6.6,
    "health_estimate": 20.0,
    "blocks_placed_recently": 3,
    "charging_bow": true
  },

  "arena": {
    "size": [24, 24], "center": [0.0, -60.0, 0.0],
    "my_edge_distance": 8.5, "opponent_edge_distance": 2.9,
    "hazards_near": [{"kind": "lava", "distance": 3.2, "direction": "left"}],
    "height_difference": 0.0
  },

  "history": [
    {"tick": 918, "event": "took_damage", "amount": 3.0, "source": "arrow"},
    {"tick": 905, "event": "dealt_damage", "amount": 6.0, "source": "sword"},
    {"tick": 880, "event": "opponent_placed_blocks", "count": 3}
  ],

  "actions": [
    {"id": "rush"}, {"id": "strafe_left"}, {"id": "strafe_right"}, {"id": "retreat"},
    {"id": "shoot_bow"}, {"id": "place_wall"}, {"id": "bucket_water"}, {"id": "bucket_lava"},
    {"id": "pillar_up"}, {"id": "hold"}
  ],

  "text": "Block UHC, 5 decisions/s, 133.8 s left. You: 17.5/20 health ..."
}
```

Field notes:

- **Units.** Positions in blocks (Minecraft coordinates, Y up). Velocities in blocks per tick. Yaw and pitch in degrees as Minecraft reports them. Health in half-hearts out of 20. `seconds_left` is wall clock to the mode's cap.
- **`decision`** counts the requests in this match from 1; **`tick`** is the server tick since the match started. Together they let an endpoint notice its own late answers.
- **`self.health`** is exact: the body reads its own health. **`opponent.health_estimate`** is the harness's best estimate from the damage events it has seen the opponent take, because the game does not send other players' health to a client. It is what a human would know. *Open:* publish the exact value instead, since the harness has it? It would make the two players' information symmetric and remove a source of noise, at the cost of realism.
- **`opponent.visible`** is line of sight from the bot's eyes. When false, `pos` and `velocity` are the last seen values and `distance` is to that position.
- **`history`** holds the last 2 seconds (40 ticks) of events: `took_damage`, `dealt_damage`, `opponent_placed_blocks`, `opponent_shot`, `fell`, `knocked_back`, `sudden_death_started`.
- **`actions`** lists only the actions that are legal right now (for example no `shoot_bow` without arrows, no `bucket_lava` once used). The response must pick one of them. The order is fixed per mode, so an endpoint that scores by letter can rely on it.
- **`text`** is the same state rendered by a fixed template, so a language model can be prompted without the entrant writing a formatter. The template is part of the interface and is in `docs/TEXT_TEMPLATE.md` once written.
- Nothing identifies the opponent or the seed. Match ids are random.

## The response

```json
{ "choice": "strafe_left", "confidence": 0.7 }
```

`choice` must be one of the offered ids. `confidence` is optional, 0 to 1, recorded and published as an average, not used for scoring. Any other field is ignored.

## Intents and reflexes

An action is an **intent**: it stays in force until the next decision replaces it. The body executes the intent every tick and layers its reflexes over it. The split between the two is the heart of the interface and is fixed for a version.

The body does, on every tick, without asking:

| Reflex | What it does | Can an intent switch it off? |
|---|---|---|
| Aim | Looks at the opponent's head (or where they were last seen) | No |
| Swing | Attacks when the opponent is within reach (3 blocks) and the intent allows attacking | Yes: `retreat`, `hold` and the build and bucket intents do not swing |
| Sprint reset | Stops sprinting for one tick after a hit lands, for knockback | No |
| Arrow dodge | A one-block sideways step when an arrow is in flight towards the bot | No |
| Edge guard (Sumo) | Refuses to step off the platform unless the intent is `rush` and the opponent is in reach | No |
| Lava guard (Block UHC) | Refuses to walk into lava or fire; steps back from a lava source within one block | No |
| Fall guard | Does not jump or walk off a drop of more than 3 blocks | Yes: `retreat` may drop up to 5 |
| Eat | Nothing. There is no food and `natural_health_regeneration` is off; hearts only go down | – |

The body does not: choose where to go, decide when to shoot, place blocks, use buckets, or change weapons except as an intent says.

*Open:* is this too much reflex? The test in stage 1 is that a random-choice model, the scripted house bot and a good model must be clearly separated in rating. If random does well, the reflexes decide too much and something moves into the action list.

## Actions

### Sumo

Platform of radius 6 at height 10 above the floor, no items, fists only. Falling below the platform loses. 60 s cap; a draw if both still stand.

| Action | The body does |
|---|---|
| `rush` | Sprints straight at the opponent; swings in reach; may follow them to the edge |
| `strafe_left` / `strafe_right` | Circles the opponent at the current distance, keeping them in view; swings in reach |
| `retreat` | Backs away from the opponent towards the platform centre; does not swing |
| `feint` | One step forward then one back, over four ticks, then holds |
| `hold` | Stands still, aims, swings in reach |

Always legal: all six.

### Block UHC

Square arena 24 by 24 inside walls 6 high, floor at y = -60. Each bot starts with a diamond sword, a bow, 16 arrows, one water bucket, one lava bucket, 64 cobblestone, full health, no armour. Last one standing. At 60 s **sudden death** starts: all damage is doubled and the event is in `history`. 180 s cap: at the cap the bot with more health wins; equal health is a draw.

| Action | The body does | Legal when |
|---|---|---|
| `rush` | Sprints at the opponent, sword out, swings in reach; jumps gaps up to one block | always |
| `strafe_left` / `strafe_right` | Circles at current distance, sword out, swings in reach | always |
| `retreat` | Backs away from the opponent, sword out, does not swing | always |
| `shoot_bow` | Switches to the bow, draws fully (about 1 s), fires at the opponent's predicted position, switches back to the sword; repeats while the intent holds | arrows > 0 and opponent visible |
| `place_wall` | Places a two-high, three-wide cobblestone wall between the bot and the opponent, then holds behind it | cobblestone ≥ 6 and opponent within 12 blocks |
| `pillar_up` | Places a block under itself and jumps, up to 3 blocks; then holds | cobblestone ≥ 3 and not at wall height |
| `bucket_water` | Places water at its feet (breaks fall, blocks lava, slows the opponent) and picks the bucket back up after 2 s | water bucket held in inventory |
| `bucket_lava` | Places lava between the bot and the opponent when they are within 4 blocks, then retreats two steps; the lava bucket is spent | lava bucket in inventory and opponent within 4 blocks |
| `hold` | Stands, aims, swings in reach | always |

*Open:* the list is deliberately short (10). MCJev's workshop lets people define their own actions. We keep one list per mode so bots are comparable; more actions mean more decisions matter and more ways for the body to be wrong. Propose additions with a reason.

## Match flow

1. The harness resets the world region from the arena file for the seed, sets the game rules, and spawns both bots at the seed's spawn points with full health and the mode's items (health, hunger and inventory are reset explicitly: the server remembers players).
2. A 3-second countdown with bots frozen; the first request goes out on the first tick of play.
3. Decisions at the tier's rate until the referee ends the match: a death, a fall (Sumo), the cap, or a forfeit.
4. A result: `win`, `loss` or `draw` for each bot, with health remaining, match length, decision count, late count, median latency.
5. Both bots are reset for the next match. Matches of a pair alternate spawn sides.

## What is seeded and what is not

The seed fixes the arena layout (Block UHC has small random pillars and the odd pool), the spawn points and sides, and the order of matches. It does not fix the game's combat randomness (critical hits, knockback jitter) because vanilla Minecraft offers no way to seed it. That is why a pair plays many matches and ratings carry intervals.

## Versioning

`INTERFACE_VERSION` covers everything on this page except the arena geometry and items, which are `MODE_SET_VERSION`. Either bump starts a new leaderboard. Within a season, neither changes.

## Open questions, collected

1. Is the 20 Hz tier in season 1?
2. Are the budgets right?
3. Exact opponent health, or an estimate?
4. Is the reflex layer too thick (see the three-way separation test)?
5. Anything missing from the action lists?
6. The text template.
