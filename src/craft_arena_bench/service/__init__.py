"""The scoring service: manifests, pull request checks, pairings, rating, result validation, the website.

Ported from Boost Arena (https://github.com/yogyam/boost-arena) by the same author. The difference that matters:
entrants host an endpoint, so nothing of theirs is downloaded or run here.
"""

SEASON = 1
MATCHES_PER_PAIR = 20  # Half with each bot on each spawn side
REPLAYS_PER_PAIR = 2  # The first matches of a pair are recorded
MIN_OPPONENTS = 3  # A rating is shown once a bot has played this many opponents
PAIRS_PER_RUN = 15
