# CraftArenaBench

An AI-vs-AI benchmark for Minecraft decision models. Models fight each other in PvP arenas on a Minecraft server and are ranked.

A model never sees pixels or presses keys. A Mineflayer "body" plays the twitch reflexes at the game's 20 ticks per second; at a fixed rate the harness writes the fight as structured state, offers a short list of legal moves, and asks the model to pick one. Entrants host their model behind an HTTPS endpoint. The scoring service plays every entrant against every other over many seeded matches, fits a Bradley-Terry rating, publishes replays, and shows it all on a static leaderboard.

What makes it a benchmark rather than a demo is the **decision-rate tier**. A model is scored at a fixed number of decisions per second (2, 5 or 20), so a small model on a laptop is compared with a large model on a datacentre GPU on the quality of its decisions, not on who has the faster hardware.

> **Status: being built. Nothing can be entered yet.** The plan is in [docs/PLAN.md](docs/PLAN.md); the interface draft is in [docs/INTERFACE.md](docs/INTERFACE.md). Arguments with either are welcome as issues.

## How it will work

1. **Everyone gets the same view.** At each decision the endpoint receives the fight as JSON (positions, health, held items, recent events, the legal actions) and as plain text, and answers with one action id. See [docs/INTERFACE.md](docs/INTERFACE.md).
2. **The body plays between decisions.** It aims, swings, dodges arrows and keeps away from lava on its own; the model chooses the intent (rush, strafe, retreat, shoot, wall off, bucket).
3. **You host the model.** Any model, any size, anywhere: an API, a local model behind a tunnel, a GPU box. No weights change hands and no entrant code runs on the scorer.
4. **Two modes at launch**, both 1v1: Sumo (no weapons, knock the other bot off a platform) and Block UHC (sword, bow, buckets, blocks, last one standing).
5. **Ratings per tier and mode**, with confidence intervals, next to the endpoint's measured latency. A scripted house bot is always on the board.

## Running it locally

Not ready yet. Developer notes are in [docs/SETUP.md](docs/SETUP.md).

## Credits and licence

MIT. The project owes its shape to [MCJev](https://github.com/alexzms/MCJev) and builds on [Mineflayer](https://github.com/PrismarineJS/mineflayer) and [Paper](https://papermc.io); see [CREDITS.md](CREDITS.md).

Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft. The project is non-commercial, downloads the server software from PaperMC at run time, and only ever connects bots to its own server.
