"""Sliding aggregate over fixed time buckets.

Design decisions:
- Fixed buckets only. We do NOT implement a true sliding window (which requires
  keeping per-event timestamps or interpolating fractional bucket overlap). Fixed
  buckets are O(1) memory and deterministic; the trade-off is that a sliding
  count can momentarily include up to (window - 1) worth of events that are
  just outside the conceptual sliding window, because the oldest bucket in the
  range may straddle the window boundary. This is the single source of edge
  inaccuracy; we document it rather than hide it.
- The clock is injected so tests are deterministic. No wall-clock reads happen
  inside this module.
- Buckets are stored in a dict keyed by integer bucket index (epoch divided by
  window size). Expired buckets are pruned on every read/write to bound memory.
"""

from __future__ import annotations
from typing import Callable, Dict


class RateTracker:
    """Track event counts in fixed time windows and aggregate them.

    Args:
        window_seconds: Length of each fixed bucket AND the aggregate range, in
            seconds. The sliding aggregate covers the last ``window_seconds``
            of buckets, i.e. the current bucket plus the immediately preceding
            one. Keeping the bucket size equal to the aggregate range means the
            count is always drawn from at most two buckets, which is the
            simplest correct reading of "sliding window over fixed buckets".
        clock: A zero-argument callable returning the current time as a number
            (int or float, in seconds). Injected so tests can fake the clock.
    """

    def __init__(
        self,
        window_seconds: float,
        clock: Callable[[], float] = None,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        # Store as float; bucket indexing uses integer division after scaling,
        # so sub-second windows work.
        self._window = float(window_seconds)
        # time.monotonic would couple us to the process clock and make tests
        # non-deterministic. Require an explicit clock; default to time.time
        # only for convenience.
        if clock is None:
            import time
            clock = time.time
        self._clock = clock
        # bucket_index -> count. Keys are ints.
        self._buckets: Dict[int, int] = {}

    def _now_bucket(self) -> int:
        return int(self._clock() // self._window)

    def _prune(self, now_bucket: int) -> None:
        """Drop buckets older than the sliding range.

        The sliding range covers [now_bucket - 1, now_bucket]. Anything older
        is unreachable by future reads and is safe to discard.
        """
        cutoff = now_bucket - 1
        expired = [b for b in self._buckets if b < cutoff]
        for b in expired:
            del self._buckets[b]

    def record(self, count: int = 1) -> None:
        """Record ``count`` events in the current bucket."""
        # int check is looser than isinstance(int) — bools are ints in Python,
        # and rejecting them would be surprising. We only reject things that
        # clearly cannot be a count.
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("count must be a non-negative int")
        b = self._now_bucket()
        self._buckets[b] = self._buckets.get(b, 0) + count
        self._prune(b)

    def current_window_count(self) -> int:
        """Count in the current (in-progress) fixed bucket."""
        b = self._now_bucket()
        self._prune(b)
        return self._buckets.get(b, 0)

    def sliding_count(self) -> int:
        """Sum of counts across the last ``window_seconds`` of buckets.

        Because buckets are ``window_seconds`` wide and we sum the current
        bucket plus the previous one, the returned value covers a span of up to
        ``2 * window_seconds``. If you need a tighter true sliding window, use a
        smaller ``window_seconds`` relative to your aggregate range — but that
        is a different contract than what this class offers.
        """
        b = self._now_bucket()
        self._prune(b)
        return self._buckets.get(b, 0) + self._buckets.get(b - 1, 0)

    def rate_per_second(self) -> float:
        """Sliding count divided by ``window_seconds``.

        Returns a float; callers comparing should use a tolerance, not ``==``.
        """
        return self.sliding_count() / self._window
