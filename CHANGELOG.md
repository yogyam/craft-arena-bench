# Changelog

Dates are when the change reached `main`. Versions of the interface and mode set are tracked separately in each result file.

## Unreleased

### Service (5 Oct 2026)
- A 1 Hz tier (900 ms budget) for models behind remote APIs; season 1 opens 1, 2 and 5 Hz.
- Repository public at https://github.com/yogyam/craft-arena-bench; leaderboard at https://yogyam.github.io/craft-arena-bench/.
- Scoring service: manifests and pull request checks, pairings per board, Bradley-Terry with bootstrap intervals, result validation, static site, replay viewer, workflows.
- The scoring run plays Sumo pairs first and stops before a pair whose worst case would not fit its time budget.
- Both modes, the endpoint protocol with tier budgets and forfeits, the OpenAI-compatible and Ollama adapters (4 Oct 2026).

### Project
- Repository created with the governance files, the plan and the first interface draft. Nothing scores yet.
- Season 1 target: Minecraft 26.1.2 on Paper build 74, Java 25, Mineflayer 4.39.
