# Maintaining the scoring service

Notes for whoever runs it. Entrants don't need this page.

## How a submission gets played

1. A pull request adds or changes `submissions/<slug>/submission.json`. The `Check submission` workflow (no secrets) verifies the manifest, the login, the limits, that the endpoint is not another entry's, and calls `/health`. The pull request must change nothing outside `submissions/`.
2. A maintainer reads the manifest and merges. Only merge submission pull requests that pass the check; never merge one that also touches code or workflows.
3. `Score pairs` runs on the push to `main`, weekly, or by hand:
   - `score` health-checks every entrant, lists the pairs with no current result on each board, and plays up to 15 of them, each in a child process with a time limit (20 matches × (cap + 15 s) + 2 min). The server is downloaded from PaperMC (checksum pinned in `server.py`) and started on the runner. A pair that fails or times out is skipped and retried next run.
   - The `publish` job validates every file against the repository (`craft-arena-bench validate-results`), commits `duels/` and `replays/`, and deploys the site. If validation fails, nothing is committed.
4. A bot whose endpoint fails the health check is skipped for the run. Three runs in a row is grounds for delisting (RULES.md); that is a manual step for now.

## Locally

```bash
craft-arena-bench server start                # downloads the jar if needed
craft-arena-bench pairings                    # what is outstanding
craft-arena-bench score --max-pairs 2 --output new_results
craft-arena-bench validate-results --submissions submissions new_results/duels/*/*.json new_results/replays/*/*.gz
craft-arena-bench build-site --output site && open site/index.html
craft-arena-bench server stop
```

`score --matches 4 --allow-local` plays short dry runs against `http://127.0.0.1` endpoints; such results do not validate and are never published.

## When a run fails

- **Validation failed in publish**: the scoring job produced something inconsistent. The `new-results` artifact holds what it made (7 days), `server-log` the server's log. Fix the cause and re-run the workflow.
- **The job timed out** (5.5 hours): too many pairs or too many 180 s Block UHC matches. Lower `--max-pairs` in `score.yml`; already-written pairs in the artifact are lost, which is fine, they are replayed.
- **An endpoint is down**: its pairs are skipped with a line in the log and retried next run. Nothing to do unless it stays down.

## Changing a season

1. Announce it two weeks ahead (issue plus the README status line).
2. Archive: copy `duels/`, `replays/` and the built site into `archive/season-N/` and commit.
3. Bump `SEASON` in `src/craft_arena_bench/service/__init__.py` (the seeds derive from it), update `MATCHES_PER_PAIR` or the Minecraft version if they change, add a changelog entry, merge.
4. Run `Score pairs` by hand. Every pair's result is from the old season, so every pair is replayed; with many bots this takes several runs.

## Flagging an entry

Add `"<slug>": "https://github.com/yogyam/craft-arena-bench/issues/<n>"` to `flags.json`; the leaderboard shows a "Flagged" link. Remove the line to clear it, or remove the submission folder and its pair files to delist the entry.

## Versions that are pinned

| What | Where |
|---|---|
| Minecraft and Paper build, plus the jar's SHA-256 | `src/craft_arena_bench/__init__.py`, `src/craft_arena_bench/server.py` |
| Python dependencies, with hashes | `requirements.lock` (`uv pip compile pyproject.toml --generate-hashes -o requirements.lock`) |
| Node dependencies | `body/package-lock.json` (`npm ci`) |
| Actions | commit SHAs in `.github/workflows/`, Dependabot proposes minor and patch bumps |

## Branch protection

Same situation as Boost Arena: on a personal account, required status checks would block the scoring bot's pushes to `main`, so the ruleset only forbids deleting and force-pushing. Merging is the maintainer's responsibility: never merge a submission pull request whose check failed or that touches anything outside `submissions/`.
