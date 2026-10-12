import json
import re

from craft_arena_bench.demo import HumanOpponent, _append_result, _text


class _Eyes:
    """A body whose latest snapshot shows an opponent."""

    def __init__(self, seen):
        self.latest = {"tick": 40, "opponent": seen}


class _Rcon:
    def __init__(self, replies):
        self.replies = replies
        self.sent = []

    def command(self, text):
        self.sent.append(text)
        for pattern, reply in self.replies.items():
            if re.search(pattern, text):
                return reply
        return ""


def test_human_snapshot_comes_from_the_bots_eyes():
    eyes = _Eyes(
        {
            "pos": [1.5, -49.0, 2.5],
            "yaw": 90.0,
            "pitch": 0.0,
            "velocity": [0.1, 0.0, 0.0],
            "on_ground": True,
            "held": "diamond_sword",
            "visible": True,
        }
    )
    h = HumanOpponent("Alice", eyes, _Rcon({}))
    snap = h.latest
    assert snap["self"]["pos"] == [1.5, -49.0, 2.5] and snap["self"]["held"] == "diamond_sword" and snap["self"]["health"] == 20.0
    assert snap["opponent"] is None and snap["intent"] == "human"
    eyes.latest = {"tick": 41, "opponent": None}
    assert h.latest["self"]["pos"] == [1.5, -49.0, 2.5]  # unseen for a moment: the last position stands
    fresh = HumanOpponent("Bob", _Eyes(None), _Rcon({}))
    assert fresh.latest is None
    fresh.spawn = [0.5, -49.0, -4.0]
    assert fresh.latest["self"]["pos"] == [0.5, -49.0, -4.0]  # never seen yet: the spawn point


def test_health_and_deaths_are_parsed_from_the_server():
    rcon = _Rcon(
        {
            r"data get entity Alice Health": "Alice has the following entity data: 13.5f",
            r"scoreboard players get Alice": "Alice has 2 [cab_deaths]",
        }
    )
    h = HumanOpponent("Alice", _Eyes(None), rcon)
    assert h._read_health() == 13.5
    assert h._read_deaths() == 2
    rcon2 = _Rcon({r"scoreboard players get": "Can't get value of cab_deaths for Alice; none is set"})
    assert HumanOpponent("Alice", _Eyes(None), rcon2)._read_deaths() == 0


def test_results_append_and_text_components(tmp_path):
    path = tmp_path / "r.json"
    _append_result(path, {"a": 1})
    _append_result(path, {"b": 2})
    assert json.loads(path.read_text()) == [{"a": 1}, {"b": 2}]
    assert json.loads(_text("Hi", "gold", True)) == {"text": "Hi", "color": "gold", "bold": True}
