"""An endpoint that asks a Claude model to pick the action, through the official Anthropic SDK.

    export ANTHROPIC_API_KEY=...        # or sign in with `ant auth login`
    python adapters/claude.py --model claude-haiku-4-5 --port 9020 --verbose

The model is shown the harness's `text` rendering of the state and asked for one action id; the first legal id in
the reply wins, anything else keeps the previous intent. No extended thinking: at 2 Hz the whole round trip has
400 ms, so this only makes sense with a model that answers without thinking first (Claude Haiku 4.5 does; the
Opus, Sonnet and Fable lines think before every answer and would be late on every decision).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from openai_compatible import SYSTEM_PROMPT, parse_choice  # noqa: E402

from craft_arena_bench import INTERFACE_VERSION  # noqa: E402


class ClaudeChooser:
    def __init__(self, model: str, max_tokens: int, timeout_s: float):
        # Credentials come from the environment (ANTHROPIC_API_KEY or an `ant auth login` profile); nothing is read here.
        self.client = anthropic.Anthropic(timeout=timeout_s, max_retries=0)
        self.model, self.max_tokens = model, max_tokens
        self.lock = threading.Lock()
        self.calls = 0
        self.fallbacks = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def choose(self, request: dict) -> str:
        legal = [a["id"] for a in request["actions"]]
        last = request["self"].get("last_intent")
        fallback = last if last in legal else legal[-1]
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": request["text"]}],
            )
        except anthropic.RateLimitError:
            return self._fallback(fallback, "rate limited")
        except anthropic.APIStatusError as e:
            return self._fallback(fallback, f"API error {e.status_code}")
        except anthropic.APIConnectionError as e:
            return self._fallback(fallback, f"connection error: {type(e).__name__}")
        with self.lock:
            self.calls += 1
            self.input_tokens += response.usage.input_tokens
            self.output_tokens += response.usage.output_tokens
        if response.stop_reason == "refusal":
            return self._fallback(fallback, "refusal")
        reply = "".join(block.text for block in response.content if block.type == "text")
        return parse_choice(reply, legal, fallback)

    def _fallback(self, choice: str, why: str) -> str:
        with self.lock:
            self.fallbacks += 1
        print(f"model call failed ({why}); keeping {choice}", file=sys.stderr, flush=True)
        return choice


def make_handler(chooser: ClaudeChooser, name: str, verbose: bool):
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
    p.add_argument("--model", default="claude-haiku-4-5")
    p.add_argument("--name", default=None, help="Name reported on /health (default: the model)")
    p.add_argument("--port", type=int, default=9020)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--max-tokens", type=int, default=16)
    p.add_argument(
        "--timeout", type=float, default=5.0, help="Seconds to wait for the model; the harness's budget is shorter anyway"
    )
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)
    chooser = ClaudeChooser(args.model, args.max_tokens, args.timeout)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(chooser, args.name or args.model, args.verbose))
    print(f"serving {args.model} on http://{args.host}:{args.port}", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    print(
        f"model calls {chooser.calls}, fallbacks {chooser.fallbacks}, tokens in {chooser.input_tokens} out {chooser.output_tokens}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
