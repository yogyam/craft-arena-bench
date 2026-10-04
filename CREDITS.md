# Credits

## Where the idea comes from

[MCJev](https://github.com/alexzms/MCJev) (Apache-2.0), by [alexzms](https://github.com/alexzms) of Hao AI Lab at UCSD, showed a decision model playing Minecraft PvP through a Mineflayer body with 20 Hz reflexes and a bounded action list, choosing a move every 24 ms. CraftArenaBench takes that architecture as its starting point and turns it into a benchmark with fixed decision rates and a leaderboard. No code from MCJev is used here; everything in this repository is written fresh. The author was told about this project before it was public.

## What it runs on

None of these projects' code is copied into this repository; they are installed as packages or downloaded at run time.

| Project | Used for | Licence |
|---|---|---|
| [Mineflayer](https://github.com/PrismarineJS/mineflayer) | The bot body: connecting to the server, moving, looking, attacking | MIT |
| [Paper](https://papermc.io) | The Minecraft server, downloaded from PaperMC at run time, never committed | GPL-3.0 (server), MIT (API) |
| [ws](https://github.com/websockets/ws) | The bridge between body and harness | MIT |
| [Boost Arena](https://github.com/yogyam/boost-arena) | The service layer (manifests, checks, rating, site) is ported from this earlier project by the same author | MIT |

## Related work

[Mindcraft](https://github.com/mindcraft-bots/mindcraft) and [PillagerBench](https://github.com/aialt/PillagerBench) showed Mineflayer-driven language-model agents on real servers; the Jev community showed state-in, choice-out decision models in Minecraft. None of their code is used.

Minecraft is a trademark of Mojang. This is not an official Minecraft product and is not approved by or associated with Mojang or Microsoft.
