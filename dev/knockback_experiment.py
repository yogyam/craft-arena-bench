"""Measures knockback at the platform edge under three setups: plain fists, Resistance V on the victim, and a raised attack_knockback attribute."""

import asyncio
import math
import sys

sys.path.insert(0, "src")
from craft_arena_bench.arena import SumoArena  # noqa: E402
from craft_arena_bench.body import Body  # noqa: E402
from craft_arena_bench.rcon import Rcon  # noqa: E402


async def trial(rcon, a, b, label, setup_cmds, ticks=200):
    arena = SumoArena()
    await asyncio.gather(a.reset(), b.reset())
    arena.build(rcon)
    for name in ("BotA", "BotB"):
        rcon.command(f"gamemode survival {name}")
        rcon.command(f"effect clear {name}")
        rcon.command(f"attribute {name} minecraft:attack_knockback base set 0")
        rcon.command(f"effect give {name} minecraft:instant_health 1 5 true")
    for c in setup_cmds:
        print("   ", c, "->", rcon.command(c).strip()[:70])
    # Victim B stands 1.5 blocks from the +z edge (edge at z=7.0), attacker A inside, facing each other.
    rcon.command("tp BotB 0.5 -49 5.5 180 0")
    rcon.command("tp BotA 0.5 -49 3.0 0 0")
    pm = arena.platform.to_message()
    await asyncio.gather(a.configure(platform=pm), b.configure(platform=pm))
    for _ in range(20):
        await a.next_state()
    await a.freeze(False)  # B stays frozen: no controls, pure knockback
    await a.set_intent("rush")
    h0 = b.latest["self"]["health"]
    fell_at = None
    hits = 0
    last_h = h0
    maxz = 5.5
    maxv = 0.0
    disp = 0.0
    swings = 0
    for t in range(ticks):
        sa = await a.next_state()
        sb = b.latest
        z = sb["self"]["pos"][2]
        maxz = max(maxz, z)
        maxv = max(maxv, math.hypot(sb["self"]["velocity"][0], sb["self"]["velocity"][2]))
        disp = max(disp, math.hypot(sb["self"]["pos"][0] - 0.5, sb["self"]["pos"][2] - 5.5))
        swings += sum(1 for e in sa.get("events", []) if e["event"] == "swung")
        if sb["self"]["health"] < last_h:
            hits += 1
        last_h = sb["self"]["health"]
        if any(e["event"] == "swung" for e in sa.get("events", [])):
            pass
        if sb["self"]["pos"][1] < -52 and fell_at is None:
            fell_at = t
            break
    await a.freeze(True)
    print(
        f"{label:<28} B health {h0} -> {b.latest['self']['health']}  drops {hits}  A swings {swings}  B max speed {maxv:.3f}  B max displacement {disp:.2f}  fell at tick {fell_at}  A dist {a.latest['opponent']['distance']}"
    )


async def main():
    rcon = Rcon()
    a, b = Body("BotA", "BotB", 8701), Body("BotB", "BotA", 8702)
    await asyncio.gather(a.start(), b.start())
    SumoArena().apply_gamerules(rcon)
    try:
        await trial(rcon, a, b, "fists, no effects", [])
        await trial(rcon, a, b, "resistance V on victim", ["effect give BotB minecraft:resistance infinite 4 true"])
        await trial(
            rcon,
            a,
            b,
            "attack_knockback 1.0 on A",
            ["attribute BotA minecraft:attack_knockback base set 1.0", "effect give BotB minecraft:resistance infinite 4 true"],
        )
        await trial(
            rcon,
            a,
            b,
            "attack_knockback 2.0 on A",
            ["attribute BotA minecraft:attack_knockback base set 2.0", "effect give BotB minecraft:resistance infinite 4 true"],
        )
    finally:
        for name in ("BotA", "BotB"):
            rcon.command(f"attribute {name} minecraft:attack_knockback base set 0")
            rcon.command(f"effect clear {name}")
        await asyncio.gather(a.stop(), b.stop())
        rcon.close()
        print("body errors:", a.errors, b.errors)


asyncio.run(main())
