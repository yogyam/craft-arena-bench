# Rules

Version 1, draft. Nothing can be entered yet; these rules take effect when submissions open. Changes are recorded in [CHANGELOG.md](CHANGELOG.md) and in this file's history.

## The spirit of the project

CraftArenaBench exists so people can compare decision models fairly on the same fights, at the same decision rate, and enjoy watching them play. It is for models that play against other models on the project's own server.

## What you may not do

1. **No play on other people's servers.** Nothing from this project may be used to run bots on public or third-party Minecraft servers. Bots connect only to the project's server and to servers you run yourself.
2. **No people behind endpoints.** An endpoint answers with a model, a program, or both. A person choosing moves is not an entrant.
3. **No money.** The project is free and non-commercial. No entry fees, paid features or selling of access through it.

## Submissions

1. **One HTTPS endpoint per bot**, following [the interface](docs/INTERFACE.md). No model files and no code are submitted; nothing of yours runs on the scoring service.
2. **The endpoint must answer the health check** with the interface version it speaks, and must stay up during scoring runs (announced in advance; a weekly window). A pair whose endpoint is down is skipped and retried next run; a bot whose endpoint is down for three runs in a row is delisted until it is resubmitted.
3. **Use whatever you like behind the endpoint.** Any model, any size, any hardware, any prompt, any wrapper code. Say in the description what it is.
4. **Your own work, or permitted.** Submit models you run, or have permission to run. Say so in the description if you are serving someone else's model.
5. **One name per bot.** Names and descriptions must be civil and must not impersonate anyone. A name already on the leaderboard cannot be used for another bot.
6. **Up to three bots per person on the leaderboard.** Update one instead of adding a fourth. A bot may enter several tiers and modes; that counts as one bot.
7. **Up to three submissions per person in any 30 days**, counting new bots and updates together. Test locally first.
8. **One GitHub account per person.** The manifest names the account that opens the pull request, and submissions are counted per account. Second accounts are removed along with their entries.
9. **House bots are exempt from the limits.** The project keeps a scripted bot per mode on the leaderboard so entrants have something to measure against and ratings have an anchor across seasons. They are marked as the maintainers' and do not count towards rules 6 and 7.

## Endpoints

1. **Answer from what you are sent.** The request carries the fight state and nothing else. An endpoint must not try to work out which opponent it faces, which seed is in play, or whether it faces the house bot, and must not behave differently between matches on that basis. Match ids are random and are not reused.
2. **Decide within the tier's budget.** A late or missing answer is not an error: the previous intent continues and the lateness is recorded. More than one in five late answers in a match forfeits the match. Latency is published next to the rating.
3. **Be deterministic enough to be rated.** Randomness in the model is fine. Changing the model between matches of the same run is not; update the submission instead.
4. **Your URL is public.** Manifests and scoring logs are public, so anything in the URL is public. If your endpoint needs a token, use a dedicated one you can revoke.

## Scoring

1. **Official ratings come only from the project's scoring service.** Matches on your own machine are for your own use.
2. **Every pair plays the same seeded matches** within a season, half with each bot on each spawn side. The arena layout and spawn sides come from the seed; the game's own combat randomness does not, which is why many matches are played and intervals are shown.
3. **Ratings are per tier and per mode.** A bot's rating is shown once it has played at least three opponents, and always with its interval.
4. **Seasons.** A season fixes the interface version, the action lists, the Minecraft and Paper version, the arena seeds, the matches per pair and the house bot. A season lasts at least three months. When it ends, the leaderboard is archived and every pair is played again on the new season's settings, free of charge against the submission limit. Season changes are announced on the repository two weeks ahead.
5. **Results are tied to versions.** Each result records the season and the interface, mode-set, server and library versions it was made with. When any of them changes, a new leaderboard starts and the old one is kept for reference.

## Integrity

1. **Only the scoring service writes results.** Every published result is checked against the submission it is for before it is published; a rating cannot be edited into the leaderboard by hand or by a pull request.
2. **An endpoint belongs to one submission.** Pointing a manifest at another entry's endpoint is refused.
3. **Entries may be flagged.** If an entry is under question (for example its behaviour suggests it recognises opponents), the maintainers mark it on the leaderboard with a link to the discussion, and remove it if the question is not answered.

## Maintainers

The maintainers may refuse or remove any entry that breaks these rules, and may change the rules. Rule changes are announced on the repository before they take effect, except for fixes to loopholes. They aim to answer submission problems within a week, but this is a volunteer project.

Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.
