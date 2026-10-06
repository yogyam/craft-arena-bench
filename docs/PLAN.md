# Plan: CraftArenaBench, an AI-vs-AI decision-model benchmark on a Minecraft server

This file was `TICK_ARENA_PLAN.md` on the Desktop until 4 Oct 2026; it now lives in the repository as `docs/PLAN.md`. Section 10 is written for the assistant and is kept because it is the working agreement for the project.

Hand-off document. It is written so a fresh Claude Code session (or a person) can start the project with no other context. Read all of it before doing anything; the "How to work with me" section at the end is not optional.

Status: Stage 0 in progress (started 4 Oct 2026). No code exists yet.

Decisions recorded 4 Oct 2026:
- Name: **CraftArenaBench** (chosen by Yogya; not one of the §3 candidates). Repository `yogyam/craft-arena-bench`, Python package `craft_arena_bench`. "Tick Arena" remains in this document as the old working title where it appears.
- Stage 0 step 1 done: Yogya has told the MCJev author about the plan; the response was positive. Details of what was said still to be recorded below in §9.
- The repository lives in this folder (`/Users/yogyamehrotra/Desktop/MC Arena`), not a new one. Public at https://github.com/yogyam/craft-arena-bench since 5 Oct 2026 (Yogya's go-ahead after the stage 4 dry run). Pages at https://yogyam.github.io/craft-arena-bench/, ruleset on main (no deletion, no force-push), private vulnerability reporting on, Dependabot active.
- Season 1 versions: Minecraft **26.1.2** on **Paper build 74**, **Java 25**, Mineflayer 4.39. Reason: Paper's current release (26.2) is not supported by Mineflayer yet; 26.1 is the newest version both support and is Mineflayer's default. Fallback is 1.21.11 on Java 21. Note that 26.x needs Java 25 (the plan said 21) and that game rule names changed to snake_case in 26.1 (`spawn_mobs`, `advance_time`, ...); see `docs/SETUP.md`.
- Stage 5 step 18 done (5 Oct 2026): both dry-run entrants played on the live service. Tailscale Funnel (free, fixed hostname, works through the campus firewall) in front of `adapters/router.py` serves both from the laptop; the runner's path through it is faster than any tunnel measured from the Mac: Haiku 566 to 578 ms median (2.9 to 6.4% late, no forfeits at 1 Hz), Qwen 149 to 197 ms (0.7 to 7% late, 2 forfeits in Block UHC). Results, all 20 matches per pair: Sumo 1 Hz Haiku 2-0-18 vs house; Sumo 2 Hz house 2-0-18 vs Qwen; Block UHC 1 Hz Haiku 14-6-0 vs house; Block UHC 2 Hz house 13-6-1 vs Qwen. Validated, committed by the publish job and live on the leaderboard with 8 replays. Two things the data says: Sumo draws at the cap 18 times in 20 against both models (the house-bot positioning question, now public), and a 1 Hz hosted model that only ever says `rush` beats the scripted Block UHC house bot. Remaining in stage 5: RULES version 1 final, pictures (step 20); the Haiku adapter should move to a cloud machine so the laptop is not the endpoint.
- Stage 5 findings (5 Oct 2026, local scoring through a pinggy tunnel): a cold connection costs the first decision of every match ~300 ms (TLS through the tunnel), which at a 10-decision forfeit check meant forfeits at 5 s; fixed by warming the connection before the countdown and judging forfeits from decision 30. Qwen 2.5 3B at 2 Hz through the tunnel: ~295 ms median, 6 to 17% late. Claude Haiku 4.5 at 1 Hz through the tunnel: ~730 ms median, p90 at the 900 ms budget, 10 to 50% late, about half its matches forfeited; it also chose `rush` on every one of 193 decisions with the default prompt. The house bot manifest did not enter 1 Hz at first (fixed: the anchor enters every open tier). GitHub Actions had a major outage during the evening, so the official run of both entrants is still queued.
- Stage 5 in progress (5 Oct 2026): `adapters/claude.py` (official Anthropic SDK; Claude Haiku 4.5 is the one Claude model fast enough for the budgets) written; the key in the environment was rejected (401), so the Haiku entrant waits for a valid key. Cloudflare quick tunnels time out from this network; localhost.run (SSH, no account) works and is what the dry run uses, with the caveat that its hostname changes on reconnect. The first real entrant, Qwen 2.5 3B via Ollama at 2 Hz, went through the whole flow from a fresh clone: `new-submission`, `verify-submission`, pull request #1, the check (which found and fixed an argument-order bug in the workflow), merge, and the scoring run that followed. The Mac has to stay awake and keep the tunnel and Ollama up while its pairs are played.
- Stage 4 (4 Oct 2026): service layer ported from Boost Arena into `src/craft_arena_bench/service/`: manifests and pull request checks (endpoint instead of model file, health check, `local:` endpoints only for the maintainers' house bot), pairings per board with season seeds and alternating spawn sides, one subprocess per pair with a time limit, Bradley-Terry with a 200-sample bootstrap interval and a 3-opponent minimum, result validation, the static site (one table per board, latency and late columns, pairing grid, house and flagged marks) with a top-down canvas replay viewer (the three.js scene from Boost Arena is deferred), `server.py` to download the pinned Paper build and run it on the runner, the three workflows, `requirements.lock` with hashes, `docs/SUBMITTING.md` and `docs/MAINTAINING.md`. A `--allow-local` switch exists for dry runs against `http://127.0.0.1` endpoints; such results never validate for publishing. End-to-end dry run passed (5 Oct 2026): `score` played the house bot against a local random endpoint on Sumo 2 Hz, 20 matches, alternating spawn sides (20-0-0, 3 ms median endpoint latency, 0% late); `validate-results` accepted the pair and replays files; `build-site` rendered both bots with the 'needs 3 opponents' note and a working replay link. Two earlier attempts died because the Mac went to sleep mid-run (see docs/SETUP.md). Stage 4 complete (5 Oct 2026): the repository is public, `Score pairs` ran on `ubuntu-latest` (Paper 26.1.2 on Temurin 25 boots in ~30 s; no pairs yet; the site deployed to Pages), and `measure.yml` timed matches on the runner: same pace as the Mac, since match time is game time (Sumo 8 s wall per match, Block UHC 25 s median, 184 s worst). Two runner-only bugs fixed on the way: PaperMC refuses Python's default User-Agent, and a non-editable install must find body/, arenas/ and server/ from the working directory. The scorer now plays Sumo pairs first and stops before a pair whose worst case would not fit a 300-minute budget.
- Stage 3 (4 Oct 2026): Block UHC. Body: sword/bow/wall/pillar/water/lava intents as multi-tick jobs, arrow dodge, lava guard, bucket guard, damage-source classification from the raw damage packet, opponent block-placement counting. Harness: walled 24 by 24 arena with seeded pillars, legal-action filtering from inventory and range, Block UHC referee (death, Strength II sudden death at 60 s, health tiebreak at the 180 s cap), a Block UHC house bot. Doubling damage from the harness turned out impossible (`/damage` is refused inside the invulnerability window), hence Strength II. Check passed (4 Oct 2026): 50 house-vs-random matches at 5 Hz, no crash, no stuck match; house 43, random 6, 1 draw; 45 ended by death, 4 by health at the 180 s cap, 1 equal; median 22 s, 350 arrows shot, 29 arrow hits, 41 dodges, 7 failed actions out of several hundred; spawns reproduce per seed. Small open item: damage from burning after leaving lava is classified as `other` (the body only sees lava or fire when standing in it).
- Stage 2 (4 Oct 2026): `endpoint.py` (async client, per-tier budgets, late/missing/illegal handling, latency stats), the match loop no longer waits for answers, forfeit at >20% late after 10 decisions, `adapters/local_server.py` (random or house over HTTP, optional delay), `adapters/openai_compatible.py` and `adapters/ollama.py`. Checks: a 300 ms endpoint forfeits at 5 Hz (90% late) and plays at 2 Hz (0% late); qwen2.5:3b through Ollama answers in ~115 ms at 2 Hz with 0% late; at 2 Hz the body moved on 88% of the ticks between decisions. Throughput measured on the Mac (docs/SETUP.md); the `ubuntu-latest` measurement waits for the GitHub repository. Finding: a bot that circles constantly cannot be pushed off at knockback resistance 0.5 (three 60 s draws against the house bot), so knockback was swept against a scripted circler (dev/kr_sweep.sh): 0.5 and 0.25 resistance drew every match, 0.0 (vanilla) wins in 24 to 56 s. Sumo uses vanilla knockback.
- Stage 1 check passed (4 Oct 2026): 30 Sumo matches in a row with no crash and no stuck bot (20 house vs random at 5 Hz: house 16, random 4, all by fall, median 10 s; 5 random vs random: 3 falls, 2 draws at the 60 s cap; 5 house vs random at 2 Hz: house 5). Spawns are identical for the same seed and differ across seeds; the fights themselves diverge through combat randomness. Overhead per match is 3.5 s (settle plus countdown). `dev/summarise_runs.py` produces these numbers.
- Stage 1 (4 Oct 2026): body, Sumo arena, referee, house bot, random bot and `craft-arena-bench play` exist and play full matches. Findings that changed the design: Mineflayer 4.39 drops knockback on 26.1 (patched in the body); Sumo uses Resistance V (no damage) and knockback resistance 0.5 (half knockback) on a 19 by 19 platform; deaths are reported by the body because immediate respawn hides them from the health stream. See `docs/SETUP.md`.
- Stage 0 step 3 passed on 4 Oct 2026: Paper boots in 6 s, two Mineflayer bots connect, one hits the other, both health values read from their own clients (see `body/dev/two_bots.mjs`).

---

## 1. The idea in one paragraph

A public, open-source benchmark where AI models fight each other in Minecraft PvP arenas and get ranked. A model never sees pixels or presses keys: a Mineflayer "body" runs the twitch reflexes (aiming, dodging, bucket guards) at the game's 20 ticks per second, and every so often the harness writes the fight as structured state, offers a short list of possible moves, and asks the model to pick one. Entrants host their own model behind an HTTPS endpoint; the scoring service runs the fights on free GitHub Actions runners, plays every entrant against every other over many seeded matches, fits a Bradley-Terry rating, publishes replays, and shows it all on a static leaderboard. The twist that makes it a benchmark rather than a demo: **decision-rate tiers**. A model is scored at a fixed number of decisions per second (for example 2 Hz, 5 Hz, 20 Hz), so a small model running on a laptop is compared with a 26B model on a datacentre GPU on the quality of its decisions, not on who has the faster hardware.

## 2. Where this comes from

### The person
Yogya Mehrotra (GitHub `yogyam`, UCSD; git commits as `ymehrotra@ucsd.edu`, public contact `yogyamehrotra@gmail.com`). Macbook Pro, Apple M5 Pro, 24 GB unified memory, macOS 26. No NVIDIA GPU. Free services only (GitHub Actions and Pages).

### The previous project, which this reuses
Yogya built **Boost Arena** (https://github.com/yogyam/boost-arena, live at https://yogyam.github.io/boost-arena/, local clone at `/Users/yogyamehrotra/Desktop/BoostArena`): a benchmark for Rocket League-style bots in the RocketSim simulator. It is complete and running, and is being left in maintenance (not promoted). It was built in about a week and then hardened after a three-way review. The pieces worth copying, almost unchanged, are:

- `src/boost_arena/submissions.py`: manifest dataclass with strict validation, pull-request checks (manifest names the GitHub login that opens the PR, copy and duplicate-name refusal, a limit of 3 scorings per person per 30 days), result-document validation that cross-checks what the scorer produced against the manifests on `main` before anything is published.
- `src/boost_arena/rating.py` and `duels.py` / `duel_service.py`: round-robin pairings, both-ways play, Bradley-Terry rating (MM fit with a prior, displayed as 1000 + 400·log10(strength)), "which pairs still need playing", 15 pairs per run, weekly cron.
- `src/boost_arena/site.py`: static leaderboard with stat tiles, sortable table with inline bars, overall-score chart, duel pairing grid, "enter your bot" steps, dark/light mode, content security policy, no scripts from other hosts.
- `src/boost_arena/replay.html`: three.js replay viewer driven by compressed position logs (a Minecraft version would need its own scene, but the player, scrubber and URL scheme carry over).
- `.github/workflows/`: `check-submission.yml` (runs on `pull_request`, no secrets, values from the PR reach the shell only via `env:`), `score.yml` (two jobs: a read-only scoring job and a publishing job that validates everything before committing and deploying Pages; actions pinned to commit SHAs; timeouts; concurrency groups), `tests.yml` (ruff lint and format, OS × Python matrix), `site.yml`.
- `RULES.md`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`, `docs/MAINTAINING.md`, `.github/dependabot.yml` (minor/patch only), `CODEOWNERS`, issue templates, a hash-locked `requirements.lock` installed with `pip install --require-hashes`.
- The habit of stamping every result with versions (interface, task set, season, simulator, library versions) and of publishing confidence intervals.

What **not** to carry over: the sealed-model-file submission scheme (entrants here host an endpoint, so no model files change hands; that was the thing the Rocket League community objected to), ONNX checks, and anything RocketSim-specific.

Lessons from Boost Arena's launch that shape this plan:
- The audience must be able to enter with what they already have. Boost Arena's fixed observation interface locked out every existing bot; here the endpoint interface accepts any model.
- Never ask for weights. Endpoints only.
- Say plainly what is and isn't guaranteed (there, "sealed" was read as a promise it wasn't).
- Dry-run the whole entrant flow yourself before announcing.
- Talk to the people whose work you build on before launch, not after.

### The thing that triggered this
Hao AI Lab (UCSD) posted a video (https://x.com/haoailab/status/2104302648786919643, 27 Sep 2026) of "Jev" playing Minecraft PvP with 24 ms decisions. The system is **MCJev** (https://github.com/alexzms/MCJev, Apache-2.0, live at https://mc.alexzms.com), built by a UCSD CS master's student in Hao Zhang's lab whom **Yogya knows and has worked with**. Facts about it:
- The model is not TypeSafe's Jev; it is "DJev": Google's open-weight DiffusionGemma-26B-A4B used as a Jev-style decision model, served with a custom vLLM engine on an NVIDIA B200 (~50 GB VRAM). It scores ~20 candidate moves in a single forward pass, no token generation, ~24 ms per decision, up to 40 decisions/s.
- Architecture: Mineflayer body with 20 Hz reflexes (aim, dodge, lava/water bucket guards) + Python head that writes fight context as text + model picks from a bounded action list. Paper/Spigot server 1.9+, `online-mode=false`, no mods. Modes: Block UHC (sword, bow, buckets, blocks) and Sumo; 2v2 teams; sudden death at 60 s; spectating; per-player stats.
- It ranks humans against the one AI (lobby leaderboards: most Jev kills, most killed by Jev; the site claims a ~70% win rate over humans in the first 32 hours; no controlled results published).
- A "Jev Workshop" lets users write a `harness.txt` (what the model sees) and `actions.yml` (allowed moves) and deploy a custom Jev into the arena. So custom agents already exist with nowhere to be compared.
- Repo was a single commit with 0 stars when checked (3 Oct 2026): a research demo, not a framework. Expect to read code.

**Decision made:** study MCJev as a reference, write everything fresh (Yogya's choice), credit it in CREDITS. Do not copy its code. Yogya will tell the author about the project before it is public; the author's bot would be a natural first entrant.

### What else exists (researched 3 Oct 2026)
- **Jev** (TypeSafe AI, launched ~15-18 Sep 2026): proprietary hosted "System One" decision model; takes program state plus a typed question, returns a calibrated choice in 70-500 ms; API with waitlist; $0.042 per M input tokens. SDKs/eval code are open (MIT/Apache). An open reproduction "openjev" (Qwen3.5-4B logits) exists. Community projects: rmalde/minecraft-agent (GPT planner + Jev chooser, Ender Dragon in 8:43 for <$1), teknium1/hermes-and-jev-play-minecraft, akash-kamat/jev-craft. Jev's state-in/choice-out interface fits this benchmark's endpoint directly.
- **Mindcraft** (https://github.com/mindcraft-bots/mindcraft, MIT, 5.8k stars): LLM agents via Mineflayer on a real server, MC up to 1.21.x, any API or local model via Ollama; MineCollab benchmark (cooking/crafting/construction, programmatic scoring, static table, no submissions); Discord ~4.2k members, ~1.1k online, an informal "which local model is best" argument with no numbers. Best model there: Claude-3.5-Sonnet 0.49, GPT-4o 0.29, LLaMA-8B 0.01 on MineCollab. This is the hobbyist audience, and a later source of non-combat tasks.
- **PillagerBench** (IEEE CoG 2025, MIT): team-vs-team competitive scenarios on Mineflayer, MC 1.19.4, Ollama supported, no leaderboard. Borrow scenario ideas.
- **Craftless** (minekube, Apache-2.0): a real headless Minecraft client with an OpenAPI, Docker image and GitHub Action, verified on 1.20.6/1.21.6/26.2. Use later if a vision track (screenshots to VLMs) is wanted. `headlesshq/mc-runtime-test` proves a rendered client runs on free Actions runners under Xvfb.
- **MineStudio / MineRL / MCU** (CraftJarvis): the pixel-agent research stack. Linux only, JDK 8, xvfb; does not run on Apple Silicon (LWJGL 3.2.2 in the bundled jar; issue #17 open since Jun 2025). Models (VPT, STEVE-1, ROCKET-2, JarvisVLA, Optimus-3) need NVIDIA GPUs. MCU (3,452 tasks, VLM judge) has no public leaderboard. **Out of scope** for this project; mentioned so nobody re-researches it.
- **Craftax**: 2D JAX Minecraft-like; not Minecraft; out of scope.
- Nobody runs a community-entrant, automatically scored leaderboard for embodied Minecraft play. The only entrant leaderboards are LLM building contests judged by human votes (MC-Bench, MineBench).

### Constraints that are not negotiable
- Runs on the Mac for development and on free `ubuntu-latest` runners (4 vCPU, 16 GB, no GPU, 6 h per job) for scoring.
- No model inference by the scorer. Entrants' endpoints do the thinking.
- Mojang usage guidelines: "Minecraft" may not be the primary or dominant name; a secondary descriptor ("X: a benchmark for Minecraft agents") is fine; non-commercial; do not redistribute client/server jars (download the server jar from Mojang/PaperMC in CI at run time); include "Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft." Offline-mode servers are the norm in this research community (Mindcraft, PillagerBench, MCJev all use them) but are a grey area; never connect bots to third-party public servers (Hypixel bans automation), only to the project's own server.
- No entrant code runs on the scorer. Endpoints only. That removes the sandboxing problem entirely.
- Everything public, MIT, free.

## 3. Name

"Minecraft" cannot be the primary name. Candidates (Yogya to pick; check GitHub/PyPI/domain availability first):

1. **Tick Arena** — after the game tick; says "timing matters". Working title used in this document.
2. **Blockfight**
3. **Cobble League**
4. **Decision Arena** — plain, says what is measured.

Tagline either way: "an AI-vs-AI benchmark for Minecraft decision models". Repository name matches the chosen name in lowercase with a hyphen.

## 4. What is measured

### Modes (launch: two)
- **Sumo**: two bots on a platform, no weapons, knockback only; falling off loses. Short rounds (60 s cap, draw if both stand). Tests positioning and timing.
- **Block UHC**: walled arena; each bot has a sword, a bow with limited arrows, a water bucket, a lava bucket, and a stack of blocks; last one standing; sudden death doubles damage at 60 s; 180 s cap, draw at the cap unless one bot has more hearts (then that bot wins). Tests tactics with a richer action list.

Both are 1v1 at launch. 2v2 is a later mode.

### Decision-rate tiers
A tier fixes how often the model is asked. The body plays on between decisions with the last chosen intent (e.g. "rush", "strafe left", "retreat and build") and its reflexes.
- **2 Hz** (every 10 ticks): for slow or large models, and for any model behind a remote API.
- **5 Hz** (every 4 ticks): the default competitive tier.
- **20 Hz** (every tick): for fast local decision models (DJev/Jev class). Only meaningful if the endpoint answers within ~40 ms; the harness measures it.

An entrant chooses which tiers to enter. Ratings are per tier and per mode. The harness waits for the endpoint up to the tier's budget; a late or missing answer counts as "no change" (the previous intent continues) and is logged; more than X% late answers in a match forfeits it. Latency is reported next to the rating so a slow endpoint is visibly slow rather than silently penalised.

### What the model sees and does (interface version 1, to be specified precisely in `docs/INTERFACE.md`)
Request from the harness to the entrant's endpoint, JSON:
```
{
  "interface_version": 1,
  "mode": "block_uhc",
  "tier_hz": 5,
  "match_id": "...", "tick": 1234, "seconds_left": 92.4,
  "self":     {"pos": [x,y,z], "yaw": .., "pitch": .., "health": 17.5, "food": 20, "velocity": [...], "on_ground": true,
               "held": "diamond_sword", "inventory": {"arrow": 12, "cobblestone": 64, "water_bucket": 1, "lava_bucket": 1},
               "effects": [], "last_intent": "strafe_left"},
  "opponent": {"pos": [...], "yaw": .., "pitch": .., "health": 20, "held": "bow", "velocity": [...], "on_ground": false,
               "visible": true, "distance": 6.3, "blocks_placed_recently": 3},
  "arena":    {"mode": "block_uhc", "size": [..], "center": [..], "my_edge_distance": 4.1, "hazards_near": ["lava@3.2m"]},
  "history":  [ {"tick": 1230, "event": "took_damage", "amount": 3.0, "source": "arrow"}, ... ],   // last ~2 s
  "actions":  [ {"id": "rush"}, {"id": "strafe_left"}, {"id": "strafe_right"}, {"id": "retreat"},
                {"id": "shoot_bow"}, {"id": "place_wall"}, {"id": "bucket_water"}, {"id": "bucket_lava"},
                {"id": "pillar_up"}, {"id": "hold"} ]        // only the currently legal ones
}
```
Response:
```
{ "choice": "strafe_left", "confidence": 0.7 }      // confidence optional; "choice" must be one of actions[].id
```
Also a plain-text rendering of the same state is sent (field `"text"`) so an LLM can be prompted without the entrant writing a formatter. The exact fields, units, the text template, and the per-mode action lists are the interface spec and are versioned; changing them starts a new leaderboard.

Reflexes the body does on its own, every tick, regardless of the model: look at the opponent, swing when in reach and the intent allows attacking, dodge arrows (small strafe), step away from lava edges, don't walk off the Sumo platform unless the intent is "charge". The boundary between reflex and decision is itself a design choice; write it down and keep it fixed within an interface version.

### Scoring
- Every pair of entrants in a tier and mode plays N seeded matches (launch N = 20, half with each bot on each spawn side). Seeds fix arena layout, spawn sides and the referee's RNG; combat RNG (crit chance, knockback jitter) is not seedable in vanilla, hence N and intervals.
- A match yields win/loss/draw. Per pair: points won, lost, drawn. Rating: Bradley-Terry over points, exactly as Boost Arena does, with a bootstrap confidence interval (new) and a minimum of 3 opponents before a rating is shown.
- Per entrant also published: median endpoint latency, fraction of late answers, hearts remaining on average, average match length. These are not part of the rating.
- A **house bot** per mode (scripted, deterministic given the seed) is always on the board so a lone first entrant has an opponent, and so ratings across seasons have an anchor.
- Replays: position/orientation/health logs at 20 Hz, gzipped, played back in the browser; first K matches per pairing recorded.

### Seasons
As in Boost Arena: a season fixes the interface version, action lists, arena seeds, N, and the house bot. A season lasts at least three months; at its end the leaderboard is archived and everything is replayed.

## 5. Architecture

```
entrant's model  <--HTTPS JSON-->  harness (Python)  <--websocket/IPC-->  body (Node, Mineflayer)  <--MC protocol-->  Paper server (Java)
                                        |                                                                     |
                                   referee + logs                                                   arena plugin-free: /commands, gamerules
```
- **Server**: Paper (current stable; pick one version per season, e.g. 1.21.x), `online-mode=false`, flat seeded world, arenas built by the harness with `/fill`/`/setblock` commands from a declarative arena file, gamerules to kill randomness (no mob spawning, fixed time, no weather, no natural regen rules set explicitly), both bots op-less, the harness connected as an op-level RCON user to give items, teleport, and read state via Mineflayer (not via server logs).
- **Body** (Node): one Mineflayer client per bot; reflex loop on `physicsTick`; exposes "set intent" and "get state" to the harness over a local websocket; no decision logic beyond reflexes.
- **Harness** (Python, the package): match scheduler, tier clock, state formatter, endpoint client (async, per-tier timeout, retries limited), referee (win/loss/draw, caps, sudden death, forfeits), logging and replay recording, seeded arena builder.
- **Service layer** (Python, copied from Boost Arena): manifests, PR check, pairings, rating, validation, site builder, CLI, workflows.
- **Entrant adapters** (Python, shipped as examples): `adapters/openai_compatible.py` (asks a chat model to answer with one action id, or scores action letters via logprobs when the server supports it), `adapters/ollama.py`, `adapters/jev.py` (TypeSafe's API, once public), `adapters/random.py` and `adapters/scripted.py` (the house bot, also the "it works" test).

Everything the scorer needs is one `pip install` plus Node and Java, which `ubuntu-latest` runners have or can fetch in under a minute.

## 6. Repository layout (proposed)

```
tick-arena/
  README.md  RULES.md  SECURITY.md  CONTRIBUTING.md  CODE_OF_CONDUCT.md  CITATION.cff  CHANGELOG.md  LICENSE  CREDITS.md
  pyproject.toml  requirements.lock  package.json (for the body)
  docs/INTERFACE.md  docs/MODES.md  docs/SUBMITTING.md  docs/ADAPTERS.md  docs/MAINTAINING.md  docs/images/
  src/tick_arena/        harness: state.py, actions.py, referee.py, tiers.py, endpoint.py, match.py, arena.py, replay.py
  src/tick_arena/service/ manifests, pairings, rating, validation, site, cli   (ported from boost_arena)
  body/                  Node: index.js, reflexes.js, bridge.js
  adapters/              example entrant servers
  arenas/                declarative arena definitions per mode
  submissions/<slug>/submission.json
  results/  duels/  replays/  flags.json
  tests/                 pytest for the harness and service; a Node test for the body; one end-to-end match test against the house bot
  .github/workflows/     check-submission.yml  score.yml  site.yml  tests.yml
```

A submission manifest: name, slug, author, github login, endpoint URL (https), tiers and modes entered, model description (free text: model name, size, where it runs), optional homepage, interface version, submitted date. No secrets in the manifest; if an endpoint needs an auth header, the entrant puts a token in the URL path or uses a fixed shared header documented in SUBMITTING (their choice; the scorer logs are public, so the docs must warn that the URL is public too — recommend a dedicated, revocable token).

## 7. Step-by-step plan

Each stage ends with something runnable and a short written check. Estimates assume part-time work with Claude Code doing the typing. Do not start a stage until the previous one's check passes.

### Stage 0: Groundwork (1-2 days)
1. Yogya tells the MCJev author about the plan (see §9). Record the outcome in this file.
2. Pick the name; create the public GitHub repository (MIT); copy the governance files from Boost Arena and edit them; set up Pages; `dependabot.yml`; pinned actions; ruff config; `CITATION.cff`.
3. Install on the Mac: Java 21, Node 22, Paper server jar (downloaded from PaperMC, never committed), Python 3.12 venv. Run a Paper server in offline mode and connect two Mineflayer bots by hand. Check: both bots visible in `/list`, one can hit the other, the harness can read both health values.
4. Write `docs/INTERFACE.md` v1 draft: state JSON, text template, action lists per mode, tier semantics, late-answer rules. This is the most important document; the author should argue with it before code exists.

### Stage 1: Body and one mode (1 week)
5. `body/`: Mineflayer client with the reflex loop and the intent interface; a websocket bridge; a `--replay-log` option.
6. `src/tick_arena/arena.py`: build the Sumo platform from a declarative file with commands; teleport bots; gamerules.
7. `src/tick_arena/referee.py` for Sumo: fall detection, timer, draw rule.
8. `adapters/scripted.py`: the house bot (simple: charge when close, sidestep when the opponent charges).
9. `match.py`: run one Sumo match between the house bot and a random-choice bot at 5 Hz, write a replay log and a result dict. Check: 20 matches in a row without a stuck bot or a crash; results differ with seeds and repeat with the same seed except for combat RNG.

### Stage 2: Endpoint protocol and tiers (1 week)
10. `endpoint.py`: async client with per-tier budgets, late/missing handling, latency stats; a local test server that answers randomly, and one that answers slowly.
11. `tiers.py`: the decision clock; prove the body keeps playing between decisions.
12. `adapters/openai_compatible.py` and `adapters/ollama.py`; run a small local model (e.g. a 3-4B Qwen via Ollama) at 2 Hz against the house bot on the Mac. Check: it plays, latency is logged, late answers are handled, and the rate of late answers at 2 Hz is near zero.
13. Measure: how many matches per hour on the Mac, and (via a throwaway Actions workflow) on `ubuntu-latest`. This number decides N and pairs-per-run.

### Stage 3: Block UHC (1 week)
14. Arena, items, action list, referee with sudden death and hearts tiebreak, reflexes for bow dodging and bucket guards. Check: house bot vs random over 50 matches has no "both stuck" outcomes and the house bot wins most.

### Stage 4: Service layer (1 week)
15. Port from Boost Arena: manifests (endpoint instead of model file), PR check (same login and limit rules; replace the download check with an endpoint health check: `GET /health` must answer with the interface version), pairings and scheduling (per tier and mode), rating with bootstrap CI and the minimum-opponents rule, result validation (every number cross-checked, filenames match slugs), site builder (per-tier/mode tables, latency column, house bot marked), replay viewer (a new three.js scene: flat arena, two capsules, health bars, projectiles; reuse the player controls).
16. Workflows: `check-submission.yml`, `score.yml` (server + body + harness on the runner; per-pair subprocess with timeout; 15 pairs per run; weekly cron), `site.yml`, `tests.yml`.
17. End-to-end test in CI: house bot vs random bot through the whole pipeline with `--allow-local` style local endpoints.

### Stage 5: Dry run and docs (3-4 days)
18. Enter two real bots yourself: a local Ollama model behind a tunnel (e.g. a Cloudflare quick tunnel) and an OpenAI-compatible API model. Follow `docs/SUBMITTING.md` literally from a fresh clone. Fix every friction point found.
19. Write RULES v1 (copy Boost Arena's structure: spirit, what you may not do, submissions, limits, integrity, seasons; replace model-file rules with endpoint rules: an endpoint must stay up during scoring runs, must not change behaviour between matches by looking at match ids, must not be a human). Add the Mojang disclaimer everywhere.
20. Pictures: a replay GIF, leaderboard screenshot, a diagram of body/harness/endpoint, the tier diagram.

### Stage 6: Launch (1 day, then 2 weeks of listening)
21. Ask the MCJev author whether DJev can enter as a bot (its endpoint on the lab's GPU); if yes, it is the headline entrant.
22. Announce: Mindcraft Discord (hobbyists with local models), Hao AI Lab / UCSD circles, the Jev community (awesome-jev lists, TypeSafe's Discord if any), X with the GIF. Casual tone; the Boost Arena announcement drafts in `/Users/yogyamehrotra/Desktop/RocketLeague/outreach/announcement.md` are a style reference.
23. Watch for: endpoints going down mid-run, latency disputes, action-list requests, cheating via endpoint behaviour. Fix, then plan season 2.

### Later (not now)
- 2v2 mode; a survive-N-nights solo task and a parkour task (Mindcraft-style scaffolding); a vision track via Craftless screenshots; a human-playable server where people fight the top bots (what MCJev does; needs a real server host and moderation, not free).

## 8. Risks and how the plan handles them

| Risk | Handling |
|---|---|
| Latency dominates skill | Tiers with fixed decision clocks; late answers logged and shown; the body plays on between decisions |
| Combat RNG makes ratings noisy | N matches per pair, both sides, bootstrap intervals, minimum opponents, a deterministic house bot as anchor |
| Endpoints die during a run | Health check in the PR check and at run start; a pair with a dead endpoint is skipped, not forfeited, and retried next run; three consecutive dead runs delists |
| Entrants game the harness (e.g. detect the house bot by behaviour) | Rules forbid match-id/opponent-conditioned behaviour; seeds and opponents are not revealed in the request; spot checks |
| Reflex layer decides too much, models matter too little | Make the reflex/decision boundary explicit in INTERFACE.md and measure: random-choice vs house bot vs a good model must be clearly separated; if not, move more into the decision |
| Free runner too slow for 20 Hz | 20 Hz tier only for endpoints that answer within budget; measured in stage 2; drop the tier if the runner cannot keep the clock |
| Mojang guidelines | Secondary name only, disclaimer, jars downloaded at run time, own server only |
| Scope creep into Mindcraft-style tasks | Launch is PvP only; later list is explicit |
| Relationship with the MCJev author | Told first; nothing copied; credited; invited as entrant |

## 9. Open decisions (ask Yogya before acting)

1. Name (§3).
2. Minecraft/Paper version for season 1 (default: latest Paper stable at stage 0).
3. N matches per pair (default 20) and the three tiers (default 2/5/20 Hz) — to be confirmed after stage 2 measurements. Decided 5 Oct 2026: a 1 Hz tier (budget 900 ms) joins season 1 for models behind remote APIs, after Claude Haiku 4.5 measured ~570 ms from a laptop and ~800 ms through a tunnel. Measured 5 Oct 2026 (docs/SETUP.md): N = 20 stands; pairs per run are bounded by a time budget rather than a fixed 15 (a Block UHC pair can take an hour if every match hits the cap).
4. Whether the 20 Hz tier is in season 1 at all. Decided 4 Oct 2026: the clock is built, the tier is not opened until an entrant asks and stage 2 shows the runner holds it.
5. Whether to run a public human-playable server (default: no; it costs money and moderation).
6. What the MCJev author said (stage 0, step 1), and whether DJev enters. Status 4 Oct 2026: told, positive. Yogya does not expect DJev to enter, so the 20 Hz tier has no known candidate entrant and the headline-entrant idea in stage 6 step 21 is dropped unless that changes.
7. The reflex/decision boundary (§4) — the author's opinion is worth getting. Decided 4 Oct 2026: thick reflexes for season 1, gated by the stage 1 separation test; opponent health sent exactly; intents persist; action lists as drafted. Details in `docs/INTERFACE.md`.

## 10. How to work with Yogya (read this)

- **Plan before executing.** Present a short plan and get a go-ahead before builds, long runs, benchmarks, or anything that takes more than a few minutes. Yogya once stopped a session with "wait pause stop real quick i want to plan this out first".
- **Ask before anything outward-facing**: creating or deleting repositories, pushing to a public branch, opening PRs, uploading releases, posting anywhere, emailing anyone. Pushes to the project's own repo were fine once the repo had been approved, but say what you are about to push.
- **Never touch secrets.** Yogya backs up keys personally; the assistant's sandbox refuses to read key files, and that is the intended behaviour. There are no model files here, but endpoint tokens are secrets.
- **Commit as** `yogyam <ymehrotra@ucsd.edu>`; public contact in docs is `yogyamehrotra@gmail.com`. End commit messages with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` only if the session's attribution reminder asks for it.
- **Prose style** Yogya liked: short, concrete, honest about limits; the Boost Arena docs are the reference. No marketing.
- **Report outcomes plainly**: if a run failed, say so with the output; if a step was skipped, say that.
- **Casual** in chat and in community posts ("hey yall"), precise in docs.
- Yogya is a UCSD student with classes; estimate in part-time days, and expect pauses.
- Memory from the previous project lives at `/Users/yogyamehrotra/.claude/projects/-Users-yogyamehrotra-Desktop-RocketLeague/memory/` (that session's working directory was `/Users/yogyamehrotra/Desktop/RocketLeague`, the private Rocket League training repo, which has nothing to do with this project).

## 11. References

- MCJev: https://github.com/alexzms/MCJev · https://mc.alexzms.com · the post: https://x.com/haoailab/status/2104302648786919643
- Jev: https://github.com/AbdelStark/awesome-typesafe-jev (field guide, SDK links, independent evals) · rmalde/minecraft-agent · teknium1/hermes-and-jev-play-minecraft
- Mindcraft: https://github.com/mindcraft-bots/mindcraft · MineCollab: https://mindcraft-minecollab.github.io/
- PillagerBench: https://github.com/aialt/PillagerBench
- Craftless: https://github.com/minekube/craftless · mc-runtime-test: https://github.com/headlesshq/mc-runtime-test
- Mineflayer: https://github.com/PrismarineJS/mineflayer · PaperMC: https://papermc.io
- Mojang usage guidelines: https://www.minecraft.net/en-us/usage-guidelines
- Boost Arena (the template): https://github.com/yogyam/boost-arena · local `/Users/yogyamehrotra/Desktop/BoostArena`
- Out of scope but researched: MineStudio https://craftjarvis.github.io/MineStudio/ (Linux/GPU pixel stack), MCU https://github.com/CraftJarvis/MCU
