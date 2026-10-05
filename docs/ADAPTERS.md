# Adapters: ways to put a model behind an endpoint

An entrant hosts one HTTPS endpoint that speaks [the interface](INTERFACE.md): `GET /health` and `POST /decide`. These scripts are reference endpoints. Copy one and change what it does.

| Script | What it does | Use it for |
|---|---|---|
| `adapters/local_server.py` | Serves an in-process policy (`random`, `house`, `circler`) over HTTP, optionally with a fixed delay | Testing the harness; imitating a slow model with `--delay-ms` |
| `adapters/openai_compatible.py` | Asks a chat model behind any OpenAI-compatible API to pick an action from the `text` rendering | Any hosted model: OpenAI, Anthropic via a proxy, vLLM, llama.cpp server |
| `adapters/ollama.py` | `openai_compatible.py` with a local Ollama's defaults | A local open-weight model on your laptop |
| `adapters/router.py` | Serves several local endpoints under one address as `/<name>/health` and `/<name>/decide` | One tunnel for several bots |
| `adapters/claude.py` | Asks a Claude model through the official Anthropic SDK (`pip install -e ".[claude]"`) | Claude Haiku 4.5; the other Claude models think before answering and are too slow for the budgets |

All three are stdlib plus `httpx`; run them from a clone with the package installed (see [SETUP.md](SETUP.md)).

## A local model with Ollama

```bash
brew install ollama            # or the installer from ollama.com
ollama serve &
ollama pull qwen2.5:3b
python adapters/ollama.py --model qwen2.5:3b --port 9010 --verbose
# in another shell, with the Paper server running:
craft-arena-bench play --a house --b http://127.0.0.1:9010 --tier 2 --matches 3
```

Measured on an M5 Pro MacBook with qwen2.5:3b: about 115 ms per decision, 0% late at 2 Hz (budget 400 ms). A model that "thinks" before answering (Qwen3, DeepSeek-R1 distils) will not fit a 400 ms budget; pick a plain instruct model or turn thinking off.

## A Claude model

```bash
pip install -e ".[claude]"
export ANTHROPIC_API_KEY=...            # or `ant auth login`
python adapters/claude.py --model claude-haiku-4-5 --port 9020 --verbose
```

Claude Haiku 4.5 is the one Claude model that answers without thinking first, which is what a 400 ms budget needs. Expect round trips of a few hundred milliseconds from a laptop, so some late answers at 2 Hz. The adapter never reads a key file; credentials come from the environment.

## What the model sees

The `text` field of the request, for example:

```
Sumo, 2 decisions per second, 58.0 s left.
You: 20/20 health, at (0.5, -49.0, -4.0), 5.5 blocks from the edge, last intent hold.
Opponent: 20/20 health, 9.0 blocks away, 4.5 blocks from the edge, visible, on the ground.
Choose one: rush, strafe_left, strafe_right, retreat, feint, hold.
```

The adapter sends this as the user message with a short system prompt and reads the first legal action id in the reply. An unparseable reply keeps the previous intent. You will do better with your own prompt: the full JSON state is in the request too.

## Several bots behind one tunnel

```bash
python adapters/router.py --port 9000 --route qwen=http://127.0.0.1:9010 --route haiku=http://127.0.0.1:9020
cloudflared tunnel --url http://127.0.0.1:9000      # or any tunnel in front of port 9000
```

The endpoints in the manifests are then `https://<host>/qwen` and `https://<host>/haiku`. The interface allows a path in the endpoint; the harness appends `/health` and `/decide`.

## Hosting it on the internet

The scoring service must reach your endpoint over `https://`. For a laptop, a tunnel works (Cloudflare quick tunnel, ngrok, Tailscale Funnel). Put a long random path or token in the URL if you want to keep strangers off it, and remember the URL is public in the manifest and the logs. Details in `docs/SUBMITTING.md` once submissions open.

## Writing your own

Anything that answers the two routes within the tier's budget is an entrant. The request and response shapes are in [INTERFACE.md](INTERFACE.md); `tests/test_endpoint.py` shows what the harness does with slow, dead and illegal answers.
