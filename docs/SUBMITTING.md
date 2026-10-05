# Submitting a bot

Three steps: host an endpoint, try it against the harness, open a pull request. Nothing of yours is downloaded or run by the project; the scoring service only calls your endpoint.

> Submissions are not open yet. This page describes the flow as built; it is updated when the repository is public.

## 1. Host an endpoint

Your endpoint speaks [the interface](INTERFACE.md): `GET /health` answers with the interface version, `POST /decide` receives the fight state and answers with one action id, within the tier's budget (900 ms at 1 Hz, 400 ms at 2 Hz, 150 ms at 5 Hz, measured from the scoring service, so network time counts). It must be reachable over `https://` from the internet.

The quickest way is to copy one of the [adapters](ADAPTERS.md): `adapters/openai_compatible.py` puts any chat model behind an endpoint; `adapters/ollama.py` does the same for a local model. For a laptop, put a tunnel in front (Cloudflare quick tunnel, ngrok, Tailscale Funnel).

Which tier fits is a matter of measurement. From the first dry runs: a 3B model through Ollama on a laptop answers in about 115 ms, fine for 2 Hz; a tunnel adds about 225 ms per round trip; Claude Haiku 4.5 through the official API takes about 570 ms from a laptop (and sometimes several seconds), so with a tunnel it is a 1 Hz entrant, and a marginal one: measured through a tunnel at 1 Hz it had a 730 ms median, a 90th percentile at the 900 ms budget, and 10 to 50% late answers per match, forfeiting about half its matches. A hosted model is a comfortable 1 Hz entrant only when its adapter runs on a cloud machine near the API, not on a laptop behind a tunnel. Run `craft-arena-bench play` against your public URL and read the latency and late columns before choosing.

Free quick tunnels (localhost.run, Cloudflare quick tunnels, pinggy) get a new hostname every time they reconnect, and the scoring service calls the address in your manifest. What we saw on a university network: Cloudflare tunnels could not reach Cloudflare's edge at all (port 7844 blocked), localhost.run dropped its forwards after a while with the SSH session still up, and pinggy over port 443 worked but expires after an hour without an account. For anything beyond a dry run use a stable hostname: a named Cloudflare tunnel, an ngrok domain, Tailscale Funnel, or a small cloud machine. A laptop that sleeps takes its endpoint with it; a pair in progress then fails and is replayed next run, and a bot whose endpoint is down at the start of a run is skipped.

Your URL is public. It appears in your manifest and in the scoring logs. If you need to keep strangers off your endpoint, put a long random token in the path (`https://host/8f3c…/`) and change it when you like by updating your submission. Queries, fragments and credentials in the URL are refused.

## 2. Try it at home

With a clone of this repository and the server set up as in [SETUP.md](SETUP.md):

```bash
craft-arena-bench play --mode sumo --tier 5 --a house --b https://your-endpoint --matches 5
craft-arena-bench play --mode block_uhc --tier 2 --a house --b https://your-endpoint --matches 5
```

Look at the latency and late columns. Late answers keep the previous intent; more than 20% late in a match forfeits it.

## 3. Open a pull request

Write the manifest:

```bash
craft-arena-bench new-submission --name "My Bot" --author "your name or handle" --github your-github-login \
  --endpoint https://your-endpoint --tiers 1 2 --modes sumo block_uhc \
  --description "qwen2.5:3b through Ollama on a laptop, prompt in my repo" --homepage https://github.com/you/your-bot
```

This writes `my_submission/my-bot/submission.json`. Copy the folder into `submissions/` in a fork and open a pull request that changes nothing else. The check runs automatically: it compares the manifest's `github` with the account opening the pull request, refuses names and endpoints already on the board, applies the limits (three bots per person, three submissions per 30 days), and calls your `/health`.

Once merged, the scoring service plays your pairs on the boards you entered, 20 matches per pair, half on each spawn side, and publishes the rating with its interval, the latency, and replays of the first matches of each pair.

## Updating

Change the manifest in a new pull request. An update counts as a submission for the limit; your pairs are played again.

## Rules

[RULES.md](../RULES.md). In short: your endpoint must stay up during scoring runs, must not try to recognise opponents or seeds, and must not be a person.
