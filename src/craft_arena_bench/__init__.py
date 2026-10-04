"""CraftArenaBench: an AI-vs-AI benchmark for Minecraft decision models."""

__version__ = "0.0.1"

# Bumped when what a model is told, the action lists, the tier budgets, the late-answer
# rules or the reflex layer change. A new interface version starts a new leaderboard.
INTERFACE_VERSION = 1

# Bumped when an arena, a mode's items, time caps or win rule change.
MODE_SET_VERSION = 1

# Season 1 target. The jar is downloaded from PaperMC at run time and never committed.
MINECRAFT_VERSION = "26.1.2"
PAPER_BUILD = 74
