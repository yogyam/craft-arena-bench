import asyncio
import socket
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from craft_arena_bench.endpoint import EndpointDecider, LatencyStats, LocalDecider, make_decider
from craft_arena_bench.policies import RandomPolicy, make_policy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
from local_server import make_handler  # noqa: E402

REQUEST = {"actions": [{"id": "rush"}, {"id": "hold"}], "self": {}, "opponent": {}, "arena": {}}


def _serve(policy_name, delay_ms):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(make_policy(policy_name), delay_ms, quiet=True))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}"


@pytest.fixture
def fast_server():
    server, url = _serve("random", 0)
    yield url
    server.shutdown()


@pytest.fixture
def slow_server():
    server, url = _serve("random", 250)
    yield url
    server.shutdown()


def test_health_and_fast_decisions(fast_server):
    async def go():
        d = EndpointDecider(fast_server)
        assert (await d.health())["interface_version"] == 1
        results = [await d.decide(REQUEST, budget_ms=400) for _ in range(5)]
        await d.close()
        return d, results

    d, results = asyncio.run(go())
    assert all(r.status == "ok" and r.choice in ("rush", "hold") for r in results)
    assert d.stats.asked == 5 and d.stats.ok == 5 and d.stats.late_fraction == 0
    assert d.stats.median_ms() is not None and d.stats.median_ms() < 400


def test_slow_endpoint_is_late_at_5hz_and_fine_at_2hz(slow_server):
    async def go():
        d = EndpointDecider(slow_server)
        late = await d.decide(REQUEST, budget_ms=150)
        fine = await d.decide(REQUEST, budget_ms=400)
        await d.close()
        return d, late, fine

    d, late, fine = asyncio.run(go())
    assert late.status == "late" and late.choice is None and 140 <= late.latency_ms < 260
    assert fine.status == "ok" and fine.latency_ms >= 250
    assert d.stats.late == 1 and d.stats.ok == 1 and d.stats.late_fraction == 0.5


def test_dead_endpoint_is_an_error():
    async def go():
        d = EndpointDecider("http://127.0.0.1:9")  # discard port, nothing listens
        r = await d.decide(REQUEST, budget_ms=400)
        await d.close()
        return r

    r = asyncio.run(go())
    assert r.status in ("error", "late") and r.choice is None


def test_local_decider_and_illegal_choice():
    class Bad:
        name = "bad"

        def decide(self, request):
            return "fly"

    d = LocalDecider(Bad())
    r = asyncio.run(d.decide(REQUEST, 150))
    assert r.status == "illegal" and r.choice is None
    good = LocalDecider(RandomPolicy(0))
    assert asyncio.run(good.decide(REQUEST, 150)).status == "ok"


def test_make_decider():
    assert make_decider("house").name == "house-sumo"
    assert isinstance(make_decider("http://127.0.0.1:9001"), EndpointDecider)


def test_stats_summary():
    s = LatencyStats()
    assert s.summary()["median_ms"] is None and s.late_fraction == 0.0
