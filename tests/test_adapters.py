import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
from openai_compatible import parse_choice  # noqa: E402

LEGAL = ["rush", "strafe_left", "strafe_right", "retreat", "feint", "hold"]


def test_parse_choice():
    assert parse_choice("strafe_left", LEGAL, "hold") == "strafe_left"
    assert parse_choice("  Strafe_Left\n", LEGAL, "hold") == "strafe_left"
    assert parse_choice("I would rush at them.", LEGAL, "hold") == "rush"
    assert parse_choice("retreat, then strafe_right", LEGAL, "hold") == "retreat"
    assert parse_choice("fly away", LEGAL, "hold") == "hold"
    assert parse_choice("", LEGAL, "feint") == "feint"
