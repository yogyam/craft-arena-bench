"""A reference endpoint: serves an in-process policy (house bot or random) over HTTP, optionally slowly.

    python adapters/local_server.py --policy random --port 9001 [--delay-ms 300] [--seed 0]

GET  /health  -> {"interface_version": 1, "name": ...}
POST /decide  -> {"choice": ...}

Stdlib only, so an entrant can read it in one sitting. It is also what the tests use for a slow endpoint.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from craft_arena_bench import INTERFACE_VERSION  # noqa: E402
from craft_arena_bench.policies import make_policy  # noqa: E402


def make_handler(policy, delay_ms: int, quiet: bool):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if not quiet:
                super().log_message(fmt, *args)

        def _send(self, code: int, doc: dict) -> None:
            body = json.dumps(doc).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"interface_version": INTERFACE_VERSION, "name": policy.name})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/decide":
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("content-length", 0))
            request = json.loads(self.rfile.read(length))
            if delay_ms:
                time.sleep(delay_ms / 1000)
            self._send(200, {"choice": policy.decide(request)})

    return Handler


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--policy", default="random")
    p.add_argument("--port", type=int, default=9001)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--delay-ms", type=int, default=0, help="Sleep this long before every answer, to imitate a slow model")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)
    policy = make_policy(args.policy, args.seed)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(policy, args.delay_ms, args.quiet))
    print(f"serving {policy.name} on http://{args.host}:{args.port} (delay {args.delay_ms} ms)", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
