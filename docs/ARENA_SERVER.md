# The public arena server (stage 7, planned)

A second Minecraft server, always on, with a public address, where people join to watch the bots fight each other and to fight the bots themselves. It is separate from the scoring server: ratings come only from the scoring runs on GitHub's machines, so nothing that happens on the public server can change a rating.

Status: planned, not built. Decisions still open are marked *decision*.

## What people get

- **Watch.** Join, and you are in spectator mode above the arena. Every few minutes the harness plays an exhibition match: the house bot against an entrant, or two entrants, using the same bodies, tiers and referee as the scoring runs. A scoreboard shows who is fighting, at what tier, and the running result. Recent results are also on the website.
- **Fight.** Step on a plate (or run a command) and you are queued to fight a bot in the arena, in survival, with the mode's kit. The bot is the house bot or an entrant who opted in. Your record against each bot is a side statistic on the website, never part of the rating.

## How the pieces fit

```
Internet ──25565──▶ Velocity proxy (online mode: Mojang login) ──localhost──▶ Paper backend (the arena)
                                                                               ▲ localhost only
                                                      bots (Mineflayer) ───────┘
                                                      harness (Python) ── RCON, localhost only ──▶ Paper
                                                      harness ── HTTPS ──▶ entrants' endpoints
```

- **Velocity** is the front door. It authenticates humans against Mojang, so names and bans mean something, and it forwards them to the backend.
- **Paper** is the arena itself and listens only on localhost. Humans can reach it only through Velocity. The bots and the harness reach it directly because they run on the same machine.
- **The harness** is the same code as the scoring service, in a new mode: a loop that runs exhibition matches and challenge matches instead of pairs, and writes results to a small JSON file the website reads.

## Threat model, and what answers each threat

The server is a public Minecraft server, which means it will be visited by griefers, bot floods and people trying to break it. Nothing here is novel; these are the standard measures, applied without plugins where possible, because every plugin is more code to trust.

| Threat | Answer |
|---|---|
| Someone logs in with a bot's name and gets teleported, armed or counted as the bot | Humans must come through Velocity, which verifies names with Mojang. The backend is reachable only from localhost. The harness addresses bots by UUID, never by name, in every command (`tp`, `give`, `effect`). Offline UUIDs differ from Mojang UUIDs, so a Mojang account that happens to be called `BotA` is a different player. |
| Someone connects straight to the backend, skipping the login | The backend binds to 127.0.0.1 and the machine's firewall exposes only 25565 (Velocity) and SSH. |
| Griefing: breaking blocks, placing lava, pushing bots | Everyone joins in spectator mode. Only a queued challenger is put in survival, only inside the arena, only for the match, and is put back in spectator after. Spectators cannot touch anything. |
| Chat abuse | *Decision below.* Default: chat off at launch; talk happens on Discord. Online mode means Mojang's chat reporting works if chat is on. |
| Login floods and connection spam | Velocity's built-in login rate limit; `max-players` around 20; a low view distance; a whitelist file kept ready as the emergency switch. TCPShield's free tier can front the proxy if floods become a problem. |
| Running up an entrant's bill: a human challenges an entrant's model a thousand times | Entrants opt in to challenges in their manifest (`exhibition: true`). One challenge per player at a time, a cooldown per player, and a cap per entrant per hour. The house bot has no such cost. |
| An entrant's endpoint learns who is playing | The request carries no usernames and no account data: the same fight state as the scoring runs. |
| Secrets on the machine | There are two: the RCON password and the Velocity forwarding secret. Both are generated on the machine, stored in files readable only by the service user, and never committed. The repository's `local-dev-only` password is for laptops. |
| The server software itself | Paper and Velocity pinned to builds that are checked at deploy time, updated on a schedule; no third-party plugins at launch; `online-mode` on the proxy; no command blocks; no ops besides the maintainer; `allow-flight` off for humans. |
| The scoring being influenced from the public server | It cannot be. Ratings are computed from pair files produced by the scoring runs on GitHub and validated against the repository; the public server writes a separate results file. |

## Hosting

*Decision below.* The candidates:

| Option | Cost | What to know |
|---|---|---|
| Oracle Cloud always-free ARM machine (4 cores, 24 GB) | Free | Plenty for Paper plus Velocity plus the harness. Oracle reclaims idle free machines; ours is never idle. Account sign-up asks for a card and is sometimes refused. |
| Hetzner CAX11 (2 ARM cores, 4 GB) | About 4 euros a month | Boring and reliable. Enough for a 20-player arena. |
| A home machine behind a game tunnel (playit.gg) | Free | The laptop has to stay on, and the home network is one hop from the internet. Not recommended for anything public. |

## Steps

1. **Machine and front door.** Create the machine, firewall everything but 22 and 25565, install Java 25, download the pinned Paper and Velocity builds with checksum checks (the same way `server.py` does), generate the two secrets, configure Velocity in online mode with modern forwarding and the backend on localhost. A systemd unit for each. Check: a human can join through the proxy and lands in spectator mode; a direct connection to the backend port from outside is refused.
2. **Harness by UUID.** Change every command the harness sends to target players by UUID. The bodies report their UUID at spawn. Check: a player named like a bot does not get teleported with it.
3. **Arena world.** Build both arenas from the existing arena files, plus a spectator deck above each with a view, a lobby, and the challenge plates. Adventure mode in the lobby, spectator by default. Check: nothing in the lobby or deck can be changed by a player.
4. **Exhibition loop.** A `craft-arena-bench arena` command: every N minutes pick a match (house vs an opted-in entrant, or two opted-in entrants), play it with the existing `MatchRunner`, show the title and scoreboard, append the result to `arena/results.json`. Check: spectators see the fight and the result; the file grows.
5. **Challenge mode.** Queue, plate or command, kit, countdown, fight, result, back to spectator. The body treats the human as the opponent; the referee is unchanged. Rate limits as above. Check: one challenger at a time, cooldown enforced, a disconnecting challenger ends the match cleanly.
6. **Website.** An "Arena" page: the server address, what is on now, recent exhibition results, human-vs-bot records per bot. Check: it reads only `arena/results.json`.
7. **Rules and moderation.** An arena section in RULES.md: behaviour, what gets you banned, that the arena never affects ratings. Whitelist procedure written down in MAINTAINING.md. Check: a dry run with two or three friends joining.
8. **Opt-in.** `exhibition: true` in the manifest, with the check and the cap. Entrants who do not opt in are only ever played in scoring runs.

Estimate: one to two weeks part-time. Steps 1 to 3 are infrastructure and can be done before any entrant exists; 4 and 5 need the house bot only; 8 needs entrants.

## Decisions

Recorded here as they are made.

1. Hosting: *open*.
2. Chat on the server: *open*.
3. Who humans can challenge: *open*.
4. When to build it relative to the benchmark launch: *open*.
5. Open join with a player cap and a whitelist as the emergency switch, rather than applications: default, unless the first weeks say otherwise.
