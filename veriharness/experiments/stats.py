from __future__ import annotations

import random
from typing import Iterable, Tuple


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def bootstrap_ci(values: Iterable[float], seed: int = 1, n: int = 200, alpha: float = 0.05) -> Tuple[float, float]:
    items = list(values)
    if not items:
        return 0.0, 0.0
    rng = random.Random(seed)
    samples = []
    for _ in range(n):
        draw = [items[rng.randrange(len(items))] for _ in items]
        samples.append(mean(draw))
    samples.sort()
    lo = samples[int((alpha / 2) * (len(samples) - 1))]
    hi = samples[int((1 - alpha / 2) * (len(samples) - 1))]
    return lo, hi
