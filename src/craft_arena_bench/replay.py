"""Replay logs: one frame per tick for both bots, gzipped JSON. Played back in the browser later."""

from __future__ import annotations

import gzip
import json
from pathlib import Path


class ReplayRecorder:
    def __init__(self, meta: dict):
        self.meta = meta
        self.frames: list[list] = []

    def record(self, tick: int, a: dict, b: dict, intents: tuple[str, str]) -> None:
        sa, sb = a["self"], b["self"]
        self.frames.append(
            [
                tick,
                [*sa["pos"], sa["yaw"], sa["pitch"], sa["health"]],
                [*sb["pos"], sb["yaw"], sb["pitch"], sb["health"]],
                list(intents),
            ]
        )

    def save(self, path: Path, outcome: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = {
            "meta": self.meta,
            "outcome": outcome,
            "frame_fields": ["tick", "a: x y z yaw pitch health", "b: same", "intents"],
            "frames": self.frames,
        }
        with gzip.open(path, "wt") as f:
            json.dump(doc, f, separators=(",", ":"))
        return path
