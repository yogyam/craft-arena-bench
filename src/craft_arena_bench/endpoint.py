"""The endpoint client: asks an entrant's HTTPS endpoint for a decision within the tier's budget, and keeps latency statistics.

A late or missing answer is not an error for the match: the previous intent continues and the lateness is counted.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import statistics
import time
from dataclasses import dataclass, field

import httpx

from . import INTERFACE_VERSION
from .policies import Policy

MAX_RESPONSE_BYTES = 4096


@dataclass(frozen=True)
class Decision:
    choice: str | None  # None when late, missing or illegal
    status: str  # "ok", "late", "error", "illegal"
    latency_ms: float
    detail: str = ""


@dataclass
class LatencyStats:
    latencies_ms: list[float] = field(default_factory=list)  # every answer that arrived, late or not
    asked: int = 0
    ok: int = 0
    late: int = 0
    errors: int = 0
    illegal: int = 0

    def record(self, d: Decision) -> None:
        self.asked += 1
        if d.status != "error":
            self.latencies_ms.append(d.latency_ms)
        if d.status == "ok":
            self.ok += 1
        elif d.status == "late":
            self.late += 1
        elif d.status == "error":
            self.errors += 1
        else:
            self.illegal += 1

    @property
    def not_ok(self) -> int:
        return self.late + self.errors + self.illegal

    @property
    def late_fraction(self) -> float:
        return self.not_ok / self.asked if self.asked else 0.0

    def median_ms(self) -> float | None:
        return round(statistics.median(self.latencies_ms), 1) if self.latencies_ms else None

    def p90_ms(self) -> float | None:
        if not self.latencies_ms:
            return None
        xs = sorted(self.latencies_ms)
        return round(xs[min(len(xs) - 1, int(0.9 * len(xs)))], 1)

    def summary(self) -> dict:
        return {
            "asked": self.asked,
            "ok": self.ok,
            "late": self.late,
            "errors": self.errors,
            "illegal": self.illegal,
            "median_ms": self.median_ms(),
            "p90_ms": self.p90_ms(),
            "late_fraction": round(self.late_fraction, 4),
        }


class Decider:
    """Anything that can be asked for a decision. Two kinds: an HTTP endpoint, or an in-process policy."""

    name: str
    stats: LatencyStats

    async def decide(self, request: dict, budget_ms: int) -> Decision:
        raise NotImplementedError

    async def warm_up(self) -> None:
        """Called just before a match starts. An endpoint opens its connection here, so decision 1 is not paid for with a TLS handshake."""

    async def close(self) -> None:
        pass


class LocalDecider(Decider):
    """Wraps an in-process policy. Latency is measured but is essentially zero."""

    def __init__(self, policy: Policy):
        self.policy = policy
        self.name = policy.name
        self.stats = LatencyStats()

    async def decide(self, request: dict, budget_ms: int) -> Decision:
        t0 = time.perf_counter()
        choice = self.policy.decide(request)
        d = _check(choice, request, (time.perf_counter() - t0) * 1000, budget_ms)
        self.stats.record(d)
        return d


class EndpointDecider(Decider):
    """POSTs the request to `<url>/decide` and waits up to the budget. One keep-alive connection per match."""

    def __init__(self, url: str, name: str | None = None):
        self.url = url.rstrip("/")
        self.name = name or self.url
        self.stats = LatencyStats()
        # No redirects, no cookies, nothing but fight state. The connect timeout is generous; the budget is enforced by wait_for.
        self.client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(10.0),
            headers={"user-agent": f"craft-arena-bench/{INTERFACE_VERSION}"},
            limits=httpx.Limits(
                max_keepalive_connections=4, keepalive_expiry=300.0
            ),  # one connection lives across a match and the next
        )

    async def warm_up(self) -> None:
        # Through a tunnel a cold connection costs a few hundred milliseconds: more than a 2 Hz budget. Pay it here, not on decision 1.
        with contextlib.suppress(TimeoutError, httpx.HTTPError):  # the decisions will record whatever is wrong
            await asyncio.wait_for(self.client.get(f"{self.url}/health"), timeout=5.0)

    async def health(self, timeout_s: float = 5.0) -> dict:
        r = await self.client.get(f"{self.url}/health", timeout=timeout_s)
        r.raise_for_status()
        doc = r.json()
        if doc.get("interface_version") != INTERFACE_VERSION:
            raise ValueError(
                f"{self.url} speaks interface version {doc.get('interface_version')!r}, this harness speaks {INTERFACE_VERSION}"
            )
        return doc

    async def decide(self, request: dict, budget_ms: int) -> Decision:
        t0 = time.perf_counter()
        try:
            r = await asyncio.wait_for(self.client.post(f"{self.url}/decide", json=request), timeout=budget_ms / 1000)
        except TimeoutError:
            d = Decision(None, "late", (time.perf_counter() - t0) * 1000, "no answer within the budget")
            self.stats.record(d)
            return d
        except httpx.HTTPError as e:
            d = Decision(None, "error", (time.perf_counter() - t0) * 1000, f"{type(e).__name__}: {e}")
            self.stats.record(d)
            return d
        latency = (time.perf_counter() - t0) * 1000
        d = _parse(r, request, latency, budget_ms)
        self.stats.record(d)
        return d

    async def close(self) -> None:
        await self.client.aclose()


def _parse(r: httpx.Response, request: dict, latency_ms: float, budget_ms: int) -> Decision:
    if r.status_code != 200:
        return Decision(None, "error", latency_ms, f"status {r.status_code}")
    if len(r.content) > MAX_RESPONSE_BYTES:
        return Decision(None, "error", latency_ms, f"response over {MAX_RESPONSE_BYTES} bytes")
    try:
        doc = json.loads(r.content)
    except ValueError:
        return Decision(None, "error", latency_ms, "response is not JSON")
    if not isinstance(doc, dict) or not isinstance(doc.get("choice"), str):
        return Decision(None, "error", latency_ms, "response has no string 'choice'")
    return _check(doc["choice"], request, latency_ms, budget_ms)


def _check(choice: str, request: dict, latency_ms: float, budget_ms: int) -> Decision:
    if latency_ms > budget_ms:
        return Decision(None, "late", latency_ms, "answer arrived after the budget")
    if choice not in {a["id"] for a in request["actions"]}:
        return Decision(None, "illegal", latency_ms, f"{choice!r} is not a legal action")
    return Decision(choice, "ok", latency_ms)


def make_decider(spec: str, seed: int = 0, mode: str = "sumo") -> Decider:
    """`house`, `random`, `circler`, or an http(s) URL."""
    if spec.startswith(("http://", "https://")):
        return EndpointDecider(spec)
    from .policies import make_policy

    return LocalDecider(make_policy(spec, seed, mode))
