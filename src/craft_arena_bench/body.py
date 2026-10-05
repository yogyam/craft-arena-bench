"""Runs one body (the Node Mineflayer client) as a subprocess and talks to it over its websocket bridge."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import websockets

BODY_DIR = Path(__file__).resolve().parents[2] / "body"


class BodyError(RuntimeError):
    pass


class Body:
    def __init__(
        self, username: str, opponent: str, ws_port: int, *, mc_host: str = "127.0.0.1", mc_port: int = 25565, mode: str = "sumo"
    ):
        self.username, self.opponent, self.ws_port = username, opponent, ws_port
        self.mc_host, self.mc_port, self.mode = mc_host, mc_port, mode
        self.proc: asyncio.subprocess.Process | None = None
        self.ws = None
        self.latest: dict | None = None
        self.states: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)
        self.spawned = asyncio.Event()
        self.errors: list[str] = []
        self.deaths = 0  # death messages seen; immediate respawn can hide a death from the health stream
        self._reader: asyncio.Task | None = None

    async def start(self, timeout: float = 20.0) -> None:
        log_dir = Path(os.environ.get("CAB_BODY_LOGS", "runs/body-logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = log_dir / f"{self.username}.log"
        self._log = open(self.log_path, "a")
        self.proc = await asyncio.create_subprocess_exec(
            "node",
            "src/main.mjs",
            "--username",
            self.username,
            "--opponent",
            self.opponent,
            "--ws-port",
            str(self.ws_port),
            "--host",
            self.mc_host,
            "--port",
            str(self.mc_port),
            "--mode",
            self.mode,
            cwd=BODY_DIR,
            stdout=self._log,
            stderr=self._log,
        )
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            try:
                self.ws = await websockets.connect(f"ws://127.0.0.1:{self.ws_port}", max_size=1 << 20)
                break
            except OSError:
                if asyncio.get_running_loop().time() > deadline:
                    raise BodyError(
                        f"{self.username}: bridge did not come up on port {self.ws_port}. If the body crashed with EADDRINUSE, a stale body "
                        f"from an earlier run still holds the port: pkill -f src/main.mjs"
                    ) from None
                await asyncio.sleep(0.1)
        self._reader = asyncio.create_task(self._read())
        await asyncio.wait_for(self.spawned.wait(), timeout)

    async def _read(self) -> None:
        try:
            async for raw in self.ws:
                for line in raw.split("\n"):
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    kind = msg.get("type")
                    if kind == "state":
                        self.latest = msg
                        if self.states.full():
                            self.states.get_nowait()
                        self.states.put_nowait(msg)
                    elif kind == "spawned":
                        self.spawned.set()
                    elif kind == "death":
                        self.deaths += 1
                    elif kind in ("error", "kicked", "disconnected"):
                        self.errors.append(f"{kind}: {msg.get('error') or msg.get('reason')}")
        except websockets.ConnectionClosed as e:
            self.errors.append(f"bridge closed: {e}")
        except Exception as e:  # anything else means the stream is gone; say so instead of timing out silently
            self.errors.append(f"reader failed: {type(e).__name__}: {e}")

    async def send(self, msg: dict) -> None:
        await self.ws.send(json.dumps(msg) + "\n")

    async def set_intent(self, intent: str) -> None:
        await self.send({"type": "intent", "intent": intent})

    async def freeze(self, value: bool) -> None:
        await self.send({"type": "freeze", "value": value})

    async def configure(self, **kwargs) -> None:
        await self.send({"type": "configure", **kwargs})

    async def reset(self) -> None:
        await self.send({"type": "reset"})
        while not self.states.empty():
            self.states.get_nowait()

    async def next_state(self, timeout: float = 2.0) -> dict:
        try:
            return await asyncio.wait_for(self.states.get(), timeout)
        except TimeoutError:
            alive = self.proc is not None and self.proc.returncode is None
            last = self.latest["tick"] if self.latest else None
            raise BodyError(
                f"{self.username}: no state for {timeout:.0f} s (process {'alive' if alive else f'exited {self.proc.returncode}'}, "
                f"last tick {last}, errors {self.errors[-3:]}, log {getattr(self, 'log_path', None)})"
            ) from None

    async def stop(self) -> None:
        if self._reader:
            self._reader.cancel()
        try:
            if self.ws:
                await self.send({"type": "quit"})
                await self.ws.close()
        except Exception:
            pass
        if self.proc and self.proc.returncode is None:
            try:
                await asyncio.wait_for(self.proc.wait(), 2.0)
            except TimeoutError:
                self.proc.kill()
