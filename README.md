# time-window-rate-tracker

Track event counts in fixed time windows and expose per-window totals plus a sliding aggregate for rate display.

## Usage

```python
from time_window_rate_tracker import RateTracker

tracker = RateTracker(window_seconds=1.0)
tracker.record()       # log an event in the current bucket
tracker.record(5)      # log 5 events
tracker.current_window_count()  # events in the current in-progress bucket
tracker.sliding_count()         # events across the last window_seconds
tracker.rate_per_second()       # sliding_count / window_seconds
```

Pass a `clock` callable to make behaviour deterministic in tests:

```python
class FakeClock:
    def __init__(self, start=0.0):
        self.t = float(start)
    def __call__(self):
        return self.t
    def advance(self, seconds):
        self.t += seconds

clk = FakeClock()
tracker = RateTracker(window_seconds=10.0, clock=clk)
tracker.record(3)
clk.advance(4.0)
tracker.record(2)
assert tracker.current_window_count() == 5
```

## Why

A service needs to show "events per second" and "events this window" on a dashboard. Keeping every event timestamp is memory-heavy and unnecessary when a fixed bucket sum is good enough. This library stores one integer per active bucket and prunes old buckets on every read and write.

## The edge you will hit

The sliding count is the sum of the current bucket plus the immediately preceding bucket, each `window_seconds` wide. That means the returned count can cover a span up to `2 * window_seconds`, not a tight `window_seconds` sliding window. If you record a burst right at the bucket boundary, the previous bucket's full count is still included even though those events are nearly a full window old. If you need a tighter true sliding window, choose a smaller `window_seconds` relative to your aggregate range — but that is a different contract than this class provides.

## Exported names

- `RateTracker(window_seconds: float, clock: Callable[[], float] | None = None)`
- `RateTracker.record(count: int = 1) -> None`
- `RateTracker.current_window_count() -> int`
- `RateTracker.sliding_count() -> int`
- `RateTracker.rate_per_second() -> float`

`count` must be a non-negative `int`; `bool` is rejected even though it subclasses `int`, because passing `True` is almost always a caller bug.
