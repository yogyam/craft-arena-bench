# Submitting a bot

Three steps: host an endpoint, try it against the harness, open a pull request. Nothing of yours is downloaded or run by the project; the scoring service only calls your endpoint.

> Submissions are not open yet. This page describes the flow as built; it is updated when the repository is public.

## 1. Host an endpoint

Your endpoint speaks [the interface](INTERFACE.md): `GET /health` answers with the interface version, `POST /decide` receives the fight state and answers with one action id, within the tier's budget (400 ms at 2 Hz, 150 ms at 5 Hz, measured from the scoring service). It must be reachable over `https://` from the internet.

The quickest way is to copy one of the [adapters](ADAPTERS.md): `adapters/openai_compatible.py` puts any chat model behind an endpoint; `adapters/ollama.py` does the same for a local model. For a laptop, put a tunnel in front (Cloudflare quick tunnel, ngrok, Tailscale Funnel).

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
  --endpoint https://your-endpoint --tiers 2 5 --modes sumo block_uhc \
  --description "qwen2.5:3b through Ollama on a laptop, prompt in my repo" --homepage https://github.com/you/your-bot
```

This writes `my_submission/my-bot/submission.json`. Copy the folder into `submissions/` in a fork and open a pull request that changes nothing else. The check runs automatically: it compares the manifest's `github` with the account opening the pull request, refuses names and endpoints already on the board, applies the limits (three bots per person, three submissions per 30 days), and calls your `/health`.

Once merged, the scoring service plays your pairs on the boards you entered, 20 matches per pair, half on each spawn side, and publishes the rating with its interval, the latency, and replays of the first matches of each pair.

## Updating

Change the manifest in a new pull request. An update counts as a submission for the limit; your pairs are played again.

## Rules

[RULES.md](../RULES.md). In short: your endpoint must stay up during scoring runs, must not try to recognise opponents or seeds, and must not be a person.
