"""Builds the request a model receives (interface version 1) from the two bodies' snapshots."""

from __future__ import annotations

from . import INTERFACE_VERSION
from .arena import Platform
from .tiers import TICKS_PER_SECOND, Tier

SUMO_ACTIONS = ["rush", "strafe_left", "strafe_right", "retreat", "feint", "hold"]
HISTORY_TICKS = 2 * TICKS_PER_SECOND


def legal_actions(mode: str, me: dict, opp: dict | None) -> list[str]:
    if mode == "sumo":
        return list(SUMO_ACTIONS)
    raise ValueError(f"unknown mode {mode}")


def build_request(
    *,
    mode: str,
    tier: Tier,
    match_id: str,
    decision: int,
    tick: int,
    cap_seconds: int,
    me: dict,
    opp: dict,
    platform: Platform,
    history: list[dict],
    last_intent: str,
    late_answers: int,
) -> dict:
    """`me` and `opp` are body snapshots. The opponent's health is exact: the harness has both bodies."""
    me_self, opp_self = me["self"], opp["self"]
    seen = me["opponent"] or {}
    my_edge = platform.edge_distance(me_self["pos"][0], me_self["pos"][2])
    opp_edge = platform.edge_distance(opp_self["pos"][0], opp_self["pos"][2])
    actions = legal_actions(mode, me, opp)
    req = {
        "interface_version": INTERFACE_VERSION,
        "mode": mode,
        "tier_hz": tier.hz,
        "match_id": match_id,
        "decision": decision,
        "tick": tick,
        "seconds_left": round(max(0.0, cap_seconds - tick / TICKS_PER_SECOND), 2),
        "sudden_death": False,
        "self": {
            "pos": me_self["pos"],
            "yaw": me_self["yaw"],
            "pitch": me_self["pitch"],
            "velocity": me_self["velocity"],
            "on_ground": me_self["on_ground"],
            "health": me_self["health"],
            "food": me_self["food"],
            "held": me_self["held"],
            "inventory": me_self["inventory"],
            "effects": [],
            "last_intent": last_intent,
            "late_answers": late_answers,
        },
        "opponent": {
            "pos": opp_self["pos"],
            "yaw": opp_self["yaw"],
            "pitch": opp_self["pitch"],
            "velocity": opp_self["velocity"],
            "on_ground": opp_self["on_ground"],
            "held": opp_self["held"],
            "visible": bool(seen.get("visible", True)),
            "distance": seen.get("distance"),
            "health": opp_self["health"],
        },
        "arena": {
            "size": [platform.max[0] - platform.min[0] + 1, platform.max[2] - platform.min[2] + 1],
            "center": [
                (platform.min[0] + platform.max[0] + 1) / 2,
                platform.min[1] + 1,
                (platform.min[2] + platform.max[2] + 1) / 2,
            ],
            "my_edge_distance": round(my_edge, 2),
            "opponent_edge_distance": round(opp_edge, 2),
            "hazards_near": [],
            "height_difference": round(me_self["pos"][1] - opp_self["pos"][1], 2),
        },
        "history": [e for e in history if e["tick"] >= tick - HISTORY_TICKS],
        "actions": [{"id": a} for a in actions],
    }
    req["text"] = render_text(req)
    return req


def render_text(req: dict) -> str:
    """A fixed plain-text rendering of the request, for prompting a language model. Part of the interface."""
    me, opp, arena = req["self"], req["opponent"], req["arena"]
    mode = {"sumo": "Sumo", "block_uhc": "Block UHC"}[req["mode"]]
    lines = [
        f"{mode}, {req['tier_hz']} decisions per second, {req['seconds_left']} s left.",
        f"You: {me['health']}/20 health, at {_fmt(me['pos'])}, {arena['my_edge_distance']} blocks from the edge, last intent {me['last_intent']}.",
        f"Opponent: {opp['health']}/20 health, {opp['distance']} blocks away, {arena['opponent_edge_distance']} blocks from the edge, "
        f"{'visible' if opp['visible'] else 'not visible'}, {'in the air' if not opp['on_ground'] else 'on the ground'}.",
    ]
    if req["history"]:
        lines.append("Recent: " + "; ".join(_fmt_event(e) for e in req["history"][-5:]) + ".")
    lines.append("Choose one: " + ", ".join(a["id"] for a in req["actions"]) + ".")
    return "\n".join(lines)


def _fmt(pos: list[float]) -> str:
    return f"({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})"


def _fmt_event(e: dict) -> str:
    extra = f" {e['amount']}" if "amount" in e else ""
    return f"{e['event']}{extra} at tick {e['tick']}"
