"""Arenas: declarative files under arenas/, built on the server with fill commands, seeded spawn points."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from .rcon import Rcon

ARENAS_DIR = Path(__file__).resolve().parents[2] / "arenas"

# Game rules for a match, in 26.1's snake_case names. The camelCase names no longer work.
GAMERULES = {
    "spawn_mobs": "false",
    "spawn_monsters": "false",
    "spawn_phantoms": "false",
    "spawn_patrols": "false",
    "spawn_wandering_traders": "false",
    "spawn_wardens": "false",
    "advance_time": "false",
    "advance_weather": "false",
    "natural_health_regeneration": "false",
    "immediate_respawn": "true",
    "respawn_radius": "0",
    "random_tick_speed": "0",
    "fire_spread_radius_around_player": "0",
    "mob_griefing": "false",
    "keep_inventory": "true",
    "show_advancement_messages": "false",
    "show_death_messages": "true",
    "fall_damage": "false",
    "players_sleeping_percentage": "101",
}


@dataclass(frozen=True)
class Spawn:
    pos: tuple[float, float, float]
    yaw: float  # degrees, Minecraft convention: 0 = +Z (south), 90 = -X (west)


@dataclass(frozen=True)
class Platform:
    """The top surface of the Sumo platform, in block coordinates, inclusive."""

    min: tuple[int, int, int]
    max: tuple[int, int, int]

    def edge_distance(self, x: float, z: float) -> float:
        """Distance from a point to the nearest edge of the platform's top surface (negative if outside)."""
        return min(x - self.min[0], (self.max[0] + 1) - x, z - self.min[2], (self.max[2] + 1) - z)

    def to_message(self) -> dict:
        return {"min": list(self.min), "max": list(self.max)}


def load_arena(mode: str) -> dict:
    path = ARENAS_DIR / f"{mode}.json"
    return json.loads(path.read_text())


def _yaw_towards(from_xz: tuple[float, float], to_xz: tuple[float, float]) -> float:
    dx, dz = to_xz[0] - from_xz[0], to_xz[1] - from_xz[1]
    return round(math.degrees(math.atan2(-dx, dz)), 2)


class SumoArena:
    def __init__(self, spec: dict | None = None):
        self.spec = spec or load_arena("sumo")
        ox, oy, oz = self.spec["origin"]
        self.origin = (ox, oy, oz)
        half = self.spec["platform"]["half"]
        self.platform = Platform(min=(ox - half, oy, oz - half), max=(ox + half, oy, oz + half))
        self.fall_y = float(self.spec["fall_y"])
        self.cap_seconds = int(self.spec["cap_seconds"])

    # Seeded geometry

    def spawns(self, seed: int) -> tuple[Spawn, Spawn]:
        """Two spawn points on opposite sides of the centre, facing each other. The seed picks the axis and the sides."""
        rng = random.Random(seed)
        angle = rng.randrange(self.spec["spawn_angles"]) * (2 * math.pi / self.spec["spawn_angles"])
        d = self.spec["spawn_distance"]
        ox, oy, oz = self.origin
        a = (round(ox + 0.5 + d * math.cos(angle), 3), float(oy + 1), round(oz + 0.5 + d * math.sin(angle), 3))
        b = (round(ox + 0.5 - d * math.cos(angle), 3), float(oy + 1), round(oz + 0.5 - d * math.sin(angle), 3))
        if rng.random() < 0.5:
            a, b = b, a
        return (
            Spawn(a, _yaw_towards((a[0], a[2]), (b[0], b[2]))),
            Spawn(b, _yaw_towards((b[0], b[2]), (a[0], a[2]))),
        )

    # Server side

    def build(self, rcon: Rcon) -> None:
        ox, oy, oz = self.origin
        c = self.spec["clear"]
        rcon.command(f"fill {ox - c['half']} {oy - 2} {oz - c['half']} {ox + c['half']} {oy + c['height']} {oz + c['half']} air")
        p = self.platform
        rcon.command(f"fill {p.min[0]} {oy} {p.min[2]} {p.max[0]} {oy} {p.max[2]} {self.spec['platform']['block']}")
        rcon.command("time set noon")
        rcon.command("weather clear")

    def apply_gamerules(self, rcon: Rcon) -> None:
        for rule, value in GAMERULES.items():
            rcon.command(f"gamerule {rule} {value}")

    def place_bots(self, rcon: Rcon, names: tuple[str, str], seed: int) -> tuple[Spawn, Spawn]:
        """Full health and hunger, empty inventory, then teleport. The server remembers players, so reset explicitly."""
        spawns = self.spawns(seed)
        for name, spawn in zip(names, spawns, strict=True):
            rcon.command(f"gamemode survival {name}")
            rcon.command(f"clear {name}")
            rcon.command(f"effect clear {name}")
            rcon.command(f"effect give {name} minecraft:instant_health 1 5 true")
            rcon.command(f"effect give {name} minecraft:saturation 1 5 true")
            for effect in self.spec.get("effects", []):
                rcon.command(f"effect give {name} {effect}")
            for attribute, value in self.spec.get("attributes", {}).items():
                rcon.command(f"attribute {name} {attribute} base set {value}")
            x, y, z = spawn.pos
            rcon.command(f"tp {name} {x} {y} {z} {spawn.yaw} 0")
        return spawns
