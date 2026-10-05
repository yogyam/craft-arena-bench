"""Ratings from match results: the Bradley-Terry model, with a bootstrap interval.

Each bot gets a strength. The chance that bot A takes a point from bot B is strength_A / (strength_A + strength_B).
A win is a point, a draw half a point each. The strengths are fitted to all the points by the usual iterative
method, then shown on a scale where the average bot is 1000 and a 400-point lead means taking about ten points
in eleven. Ratings are per mode and tier: a bot has one rating for Sumo at 5 Hz, another for Block UHC at 2 Hz.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict

BOOTSTRAP_SAMPLES = 200


def fit_strengths(points: dict, iterations: int = 200, prior: float = 1.0) -> dict:
    """`points[(a, b)]` is the number of points a took from b. Returns strength per bot.

    A small prior, as if every pair had exchanged `prior` points each way, keeps a bot that has never lost from
    getting an infinite strength.
    """
    bots = sorted({bot for pair in points for bot in pair})
    if not bots:
        return {}
    strength = {bot: 1.0 for bot in bots}
    pairs = defaultdict(float)
    for (a, b), won in points.items():
        pairs[(a, b)] += won
    for a in bots:
        for b in bots:
            if a != b:
                pairs[(a, b)] += prior

    for _ in range(iterations):
        new = {}
        for a in bots:
            wins = sum(won for (x, _), won in pairs.items() if x == a)
            denominator = 0.0
            for b in bots:
                if b == a:
                    continue
                games = pairs.get((a, b), 0.0) + pairs.get((b, a), 0.0)
                denominator += games / (strength[a] + strength[b])
            new[a] = wins / denominator if denominator else 1.0
        mean = math.exp(sum(math.log(s) for s in new.values()) / len(new))
        strength = {bot: s / mean for bot, s in new.items()}
    return strength


def to_rating(strength: float) -> float:
    return round(1000 + 400 * math.log10(strength), 1)


def ratings(points: dict) -> dict:
    """Bradley-Terry strengths as ratings around 1000, 400 points per factor of ten."""
    return {bot: to_rating(s) for bot, s in fit_strengths(points).items()}


def expected_share(rating_a: float, rating_b: float) -> float:
    """The share of points A is expected to take from B."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def points_from_matches(matches: dict) -> dict:
    """`matches[(a, b)]` is a list of outcomes from a's side: 1 (a won), 0 (b won) or 0.5 (draw). Returns the points table."""
    points = defaultdict(float)
    for (a, b), outcomes in matches.items():
        for o in outcomes:
            points[(a, b)] += o
            points[(b, a)] += 1 - o
    return dict(points)


def bootstrap_ratings(matches: dict, samples: int = BOOTSTRAP_SAMPLES, seed: int = 0) -> dict:
    """Ratings with a 95% interval, by resampling each pair's matches with replacement.

    Returns {bot: {"rating": r, "low": lo, "high": hi}}. The interval says how much the rating could move if the
    same pairs were played again with the same luck distribution; it does not include opponents not yet played.
    """
    point = ratings(points_from_matches(matches))
    if not point:
        return {}
    rng = random.Random(seed)
    draws = {bot: [] for bot in point}
    pairs = list(matches.items())
    for _ in range(samples):
        resampled = {pair: [rng.choice(outcomes) for _ in outcomes] for pair, outcomes in pairs if outcomes}
        for bot, r in ratings(points_from_matches(resampled)).items():
            draws[bot].append(r)
    out = {}
    for bot, r in point.items():
        xs = sorted(draws[bot])
        lo = xs[int(0.025 * (len(xs) - 1))] if xs else r
        hi = xs[int(0.975 * (len(xs) - 1))] if xs else r
        out[bot] = {"rating": r, "low": round(min(lo, r), 1), "high": round(max(hi, r), 1)}
    return out


def opponents(matches: dict) -> dict:
    """How many distinct opponents each bot has played."""
    seen = defaultdict(set)
    for (a, b), outcomes in matches.items():
        if outcomes:
            seen[a].add(b)
            seen[b].add(a)
    return {bot: len(s) for bot, s in seen.items()}
