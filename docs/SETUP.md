# Developer setup

What a maintainer or contributor needs to run a match locally. Entrants don't need any of this; they only host an endpoint.

## Versions (season 1)

| Piece | Version | Why this one |
|---|---|---|
| Minecraft / Paper | 26.1.2, Paper build 74 | The newest version both Paper and Mineflayer support. Paper's current release (26.2) has no Mineflayer support yet. |
| Java | 25 | Paper 26.x refuses to start on anything older. |
| Node | 22 | Mineflayer 4.39 |
| Python | 3.12 or 3.13 | The harness and service layer |

Minecraft moved to year-based version numbers in 2026 (1.21.11 was followed by 26.1). Many tutorials are for the old numbering.

## Install

macOS (Homebrew):

```bash
brew install openjdk@25          # formula, no admin password needed; the Temurin cask needs sudo
brew install node                # 22 or newer
cd craft-arena-bench
uv venv --python 3.12 .venv && source .venv/bin/activate     # or python3.12 -m venv .venv
pip install -e ".[dev]"
(cd body && npm install)
```

Ubuntu runners in CI get Java from `actions/setup-java` and Node from `actions/setup-node`.

## The server

The Paper jar is downloaded, never committed (PaperMC's and Mojang's terms). `server/` holds only the config files; everything else in it is ignored by git.

```bash
cd server
curl -s https://fill.papermc.io/v3/projects/paper/versions/26.1.2/builds \
  | python3 -c "import json,sys; d=json.load(sys.stdin)[0]['downloads']['server:default']; print(d['url']); print(d['checksums']['sha256'])"
curl -L -o paper.jar "<the url printed>"
shasum -a 256 paper.jar            # must match the printed checksum
./start.sh                         # first start takes ~6 s on an M-series Mac; Ctrl-C or "stop" to quit
```

PaperMC's old `api.papermc.io/v2` API was shut down in 2026; use `fill.papermc.io/v3`.

`server.properties` is committed: offline mode, a flat world (grass at y = -61, bedrock at y = -64, so bots stand at y = -60), no structures, no spawn protection, RCON on port 25575 with a local-only password. The harness talks to the server over RCON for commands and reads state through each bot's own Mineflayer client, never from server logs.

The line `ERROR: No key layers in MapLike[{}]` on the first boot is Paper complaining about the empty flat-world settings; the world is still generated as the standard flat preset. Harmless.

## Game rules

Game rule names changed to snake_case in 26.1 and some were renamed outright; the camelCase names do not work. The harness sets these at the start of every match:

| Rule | Value | Old name |
|---|---|---|
| `spawn_mobs`, `spawn_monsters`, `spawn_phantoms`, `spawn_patrols`, `spawn_wandering_traders`, `spawn_wardens` | false | doMobSpawning and friends |
| `advance_time`, `advance_weather` | false | doDaylightCycle, doWeatherCycle |
| `natural_health_regeneration` | false | naturalRegeneration |
| `immediate_respawn` | true | doImmediateRespawn |
| `respawn_radius` | 0 | spawnRadius |
| `random_tick_speed` | 0 | randomTickSpeed |
| `fire_spread_radius_around_player` | 0 | doFireTick (roughly) |
| `mob_griefing` | false | mobGriefing |
| `keep_inventory` | true | keepInventory |
| `show_advancement_messages` | false | announceAdvancements |
| `players_sleeping_percentage` | 101 | same |

The full list comes from the server itself: an op'd Mineflayer bot's `tabComplete('/gamerule ')` returns all 116 names (`body/dev/gamerule_probe.mjs`).

## Playing matches

With the server running:

```bash
craft-arena-bench play --a house --b random --tier 5 --matches 5 --seed 0
```

starts two bodies (`body/src/main.mjs`, one Node process per bot, websocket bridges on ports 8701 and 8702), builds the arena from `arenas/sumo.json`, places the bots from the seed, and plays the matches with in-process policies (`house`, `random`). Results go to `runs/*.json` and replays to `runs/replays/*.json.gz`. Match `i` uses seed `--seed + i`. `--mode block_uhc` plays Block UHC (arena from `arenas/block_uhc.json`, at x = 100, z = 100 so it does not overlap the Sumo platform); `--verbose` prints each side's event counts (damage by source, arrows shot, buckets used, dodges, failed actions) after every match.

## Endpoints

`--a` and `--b` take a policy name (`house`, `random`, `circler`) or an endpoint URL. Reference endpoints live in `adapters/`; see [ADAPTERS.md](ADAPTERS.md).

```bash
python adapters/local_server.py --policy random --port 9001 --quiet &
python adapters/local_server.py --policy random --port 9002 --delay-ms 300 --quiet &
craft-arena-bench play --a house --b http://127.0.0.1:9001 --tier 5 --matches 3     # ~3 ms per decision
craft-arena-bench play --a house --b http://127.0.0.1:9002 --tier 5 --matches 2     # 300 ms answers: 90% late, forfeits after 10 decisions
craft-arena-bench play --a house --b http://127.0.0.1:9002 --tier 2 --matches 2     # same endpoint, 400 ms budget: 0% late
```

The decision clock never waits for an answer: the request goes out as a task, the body keeps executing the last intent, and an answer that arrives inside the budget becomes the new intent. The forfeit rule (more than 20% late or missing, after at least 10 decisions) is in `match.py`.

## Throughput on this Mac (49 matches, 4 Oct 2026)

| | |
|---|---|
| Overhead per match (reset, build, teleport, settle, 3 s countdown) | 3.5 s |
| Sumo match length, observed mix of house, random, circler and a 3B model (mostly at half knockback, since replaced by vanilla) | median 12 s, mean 21 s |
| Matches per hour | about 150 at that mix; 57 if every match runs to the 60 s cap; 270 for 10 s rounds |
| One pair at N = 20 | 8 min at that mix, 21 min worst case |
| A 6 h runner job (if the runner matches the Mac) | 17 pairs worst case, 45 at that mix |

The `ubuntu-latest` measurement waits for the GitHub repository (a throwaway workflow). Until then assume the runner is 2 to 3 times slower than the Mac for the server and plan 15 pairs per run as Boost Arena does.

## The stage 0 check

With the server running:

```bash
cd body && node dev/two_bots.mjs
```

connects two bots, sets the game rules, teleports them two blocks apart, gives one a diamond sword and has it swing six times, and prints both bots' health as each bot's own client reports it. Expected: both bots in `/list`, the second bot's health well below 20. Note that the server keeps a player's health and inventory between connections, so a match must reset both at its start.

## Known rough edges

- **Knockback is zero in Mineflayer 4.39 on 26.1** unless patched. The server sends `entity_velocity` as floats in blocks per tick since 1.21.9, but Mineflayer still multiplies by 1/8000, so a hit's knockback rounds to nothing. `body/src/main.mjs` re-applies the raw packet value; `dev/knockback_experiment.py` measures it. Remove the patch once upstream fixes it.
- **Other players' velocity is not sent while they walk**, only on knockback. The body derives the opponent's velocity from position deltas.
- **iCloud Drive marks everything under dot-directories as hidden**, and Homebrew's Python skips hidden `.pth` files, so an editable install into `.venv` on the Desktop silently disappears from `sys.path`. The venv lives at `~/.venvs/craft-arena-bench` with `.venv` a symlink to it. Consider keeping the repository outside iCloud-synced folders altogether.
- **`/damage` is refused inside the invulnerability window** (10 ticks after any hit), whatever the damage type, so the harness cannot mirror damage to double it. Sudden death uses Strength II instead.
- **The killing blow never shows in the health stream**: with `immediate_respawn` the bot is back at full health inside the same tick. The harness takes the death message and records the remaining health as the last damage event.
- **Players respawn on top of the platform** when the world spawn is under it, and `immediate_respawn` makes a death invisible to the health stream. The body reports deaths as messages and the referee uses them.

- `bot.blockAt` returns `undefined` for a tick or two after spawn until the chunk arrives; wait for it before reading the world.
- Other players' health is not sent over the protocol. Each body reports its own health; the harness has both bodies, so it has both numbers.
