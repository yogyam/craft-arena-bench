"""An endpoint that asks a chat model behind any OpenAI-compatible API to pick the action.

    python adapters/openai_compatible.py --base-url http://127.0.0.1:11434/v1 --model qwen2.5:3b --port 9010
    OPENAI_API_KEY=... python adapters/openai_compatible.py --base-url https://api.openai.com/v1 --model gpt-4.1-mini --port 9010

The model is shown the harness's `text` rendering of the state and must answer with one action id. Anything else
falls back to the previous intent ("hold" at the start). The reply is parsed leniently: the first legal action id
that appears in the reply wins. Latency is whatever the model takes; at 2 Hz you have 400 ms.

Stdlib plus httpx. An entrant can copy this file and change the prompt.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from craft_arena_bench import INTERFACE_VERSION  # noqa: E402

SYSTEM_PROMPT = (
    "You control a Minecraft PvP bot. Each message describes the fight and lists the legal actions. "
    "Reply with exactly one action id from the list and nothing else."
)


class ChatChooser:
    def __init__(self, base_url: str, model: str, api_key: str | None, max_tokens: int, temperature: float, timeout_s: float):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model, self.max_tokens, self.temperature = model, max_tokens, temperature
        headers = {"content-type": "application/json"}
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"
        self.client = httpx.Client(headers=headers, timeout=timeout_s)
        self.lock = threading.Lock()
        self.calls = 0
        self.fallbacks = 0

    def choose(self, request: dict) -> str:
        legal = [a["id"] for a in request["actions"]]
        fallback = request["self"].get("last_intent") if request["self"].get("last_intent") in legal else legal[-1]
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": request["text"]}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        try:
            r = self.client.post(self.url, content=json.dumps(body))
            r.raise_for_status()
            reply = r.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, ValueError, IndexError) as e:
            with self.lock:
                self.fallbacks += 1
            print(f"model call failed ({type(e).__name__}: {str(e)[:80]}); using {fallback}", file=sys.stderr, flush=True)
            return fallback
        with self.lock:
            self.calls += 1
        return parse_choice(reply, legal, fallback)


def parse_choice(reply: str, legal: list[str], fallback: str) -> str:
    """The first legal action id mentioned in the reply, longest ids first so 'strafe_left' is not read as 'strafe'."""
    text = reply.strip().lower()
    if text in legal:
        return text
    hits = [(text.find(a), a) for a in legal if a in text]
    if not hits:
        return fallback
    return min(hits)[1]


def make_handler(chooser: ChatChooser, name: str, verbose: bool):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, doc: dict) -> None:
            body = json.dumps(doc).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"interface_version": INTERFACE_VERSION, "name": name})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/decide":
                self._send(404, {"error": "not found"})
                return
            request = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
            t0 = time.perf_counter()
            choice = chooser.choose(request)
            if verbose:
                print(f"decision {request.get('decision')}: {choice} in {(time.perf_counter() - t0) * 1000:.0f} ms", flush=True)
            self._send(200, {"choice": choice})

    return Handler


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--base-url", default="http://127.0.0.1:11434/v1", help="OpenAI-compatible base URL (default: a local Ollama)")
    p.add_argument("--model", default="qwen2.5:3b")
    p.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY"), help="Defaults to $OPENAI_API_KEY; Ollama needs none")
    p.add_argument("--name", default=None, help="Name reported on /health (default: the model)")
    p.add_argument("--port", type=int, default=9010)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--max-tokens", type=int, default=8)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument(
        "--timeout", type=float, default=5.0, help="Seconds to wait for the model; the harness's budget is shorter anyway"
    )
    p.add_argument("--verbose", action="store_true", help="Print every decision and its latency")
    args = p.parse_args(argv)
    chooser = ChatChooser(args.base_url, args.model, args.api_key, args.max_tokens, args.temperature, args.timeout)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(chooser, args.name or args.model, args.verbose))
    print(f"serving {args.model} via {args.base_url} on http://{args.host}:{args.port}", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    print(f"model calls {chooser.calls}, fallbacks {chooser.fallbacks}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
