"""Wilson intervals, ported from eval-harness (MIT) and kept dependency-free.

An interval is reported next to every metric rate because a bare 9/12 invites
the reader to invent precision the sample cannot support.
"""

from __future__ import annotations

import math

Z_95 = 1.96
"""The standard normal quantile for a two-sided 95 percent interval."""


def proportion(successes: int, n: int) -> float | None:
    """Return successes / n, or None when there are no samples."""
    if n < 0 or successes < 0 or successes > n:
        raise ValueError(f"impossible proportion: {successes} passes out of {n}")
    if n == 0:
        return None
    return successes / n


def wilson_interval(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Return the Wilson score interval for successes out of n, clamped to [0, 1]."""
    passed = proportion(successes, n)
    if passed is None:
        raise ValueError("the Wilson interval needs at least one sample")
    denominator = 1.0 + z * z / n
    centre = (passed + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(passed * (1 - passed) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)
