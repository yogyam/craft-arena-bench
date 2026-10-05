"""One public address, several bots: forwards /<name>/health and /<name>/decide to a local endpoint each.

    python adapters/router.py --port 9000 --route qwen=http://127.0.0.1:9010 --route haiku=http://127.0.0.1:9020

Then one tunnel in front of port 9000 serves two entrants, with endpoints https://<host>/qwen and https://<host>/haiku.
Stdlib plus httpx. Anything not under a known prefix is a 404.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx


def make_handler(routes: dict[str, str], quiet: bool):
    client = httpx.Client(timeout=10.0)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if not quiet:
                super().log_message(fmt, *args)

        def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _target(self):
            parts = self.path.split("?")[0].strip("/").split("/")
            if len(parts) == 2 and parts[0] in routes and parts[1] in ("health", "decide"):
                return f"{routes[parts[0]]}/{parts[1]}"
            return None

        def do_GET(self):
            target = self._target()
            if not target or not target.endswith("/health"):
                self._send(404, json.dumps({"error": "not found"}).encode())
                return
            try:
                r = client.get(target)
                self._send(r.status_code, r.content, r.headers.get("content-type", "application/json"))
            except httpx.HTTPError as e:
                self._send(502, json.dumps({"error": f"upstream: {type(e).__name__}"}).encode())

        def do_POST(self):
            target = self._target()
            if not target or not target.endswith("/decide"):
                self._send(404, json.dumps({"error": "not found"}).encode())
                return
            body = self.rfile.read(int(self.headers.get("content-length", 0)))
            try:
                r = client.post(target, content=body, headers={"content-type": "application/json"})
                self._send(r.status_code, r.content, r.headers.get("content-type", "application/json"))
            except httpx.HTTPError as e:
                self._send(502, json.dumps({"error": f"upstream: {type(e).__name__}"}).encode())

    return Handler


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--route", action="append", required=True, help="name=http://127.0.0.1:PORT; repeat per bot")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)
    routes = {}
    for r in args.route:
        name, _, url = r.partition("=")
        if not name.isalnum() or not url.startswith("http"):
            print(f"bad route {r!r}; use name=http://127.0.0.1:PORT", file=sys.stderr)
            return 2
        routes[name] = url.rstrip("/")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(routes, args.quiet))
    print(f"routing on http://{args.host}:{args.port}: " + ", ".join(f"/{k} -> {v}" for k, v in routes.items()), flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
