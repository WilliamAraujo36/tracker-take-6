import unittest

from time_window_rate_tracker import RateTracker


class FakeClock:
    def __init__(self, start=0.0):
        self.t = float(start)

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class TestRecord(unittest.TestCase):
    def test_single_record_increments_current_bucket(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        r.record()
        self.assertEqual(r.current_window_count(), 1)

    def test_record_with_explicit_count(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        r.record(5)
        self.assertEqual(r.current_window_count(), 5)

    def test_multiple_records_accumulate_same_bucket(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=10.0, clock=clk)
        r.record(2)
        r.record(3)
        r.record()
        self.assertEqual(r.current_window_count(), 6)

    def test_zero_count_is_allowed(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        r.record(0)
        self.assertEqual(r.current_window_count(), 0)

    def test_negative_count_rejected(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        with self.assertRaises(ValueError):
            r.record(-1)

    def test_bool_count_rejected(self):
        # bool is a subclass of int; we reject it explicitly because a count
        # of True == 1 is almost certainly a caller bug.
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        with self.assertRaises(ValueError):
            r.record(True)

    def test_non_int_count_rejected(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        with self.assertRaises(ValueError):
            r.record(1.0)


class TestBuckets(unittest.TestCase):
    def test_advance_to_new_bucket_isolates_counts(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        r.record(3)
        clk.advance(1.0)
        r.record(7)
        self.assertEqual(r.current_window_count(), 7)

    def test_partial_window_advance_stays_in_same_bucket(self):
        # 10s window; 4s in we're still in bucket 0.
        clk = FakeClock()
        r = RateTracker(window_seconds=10.0, clock=clk)
        r.record(2)
        clk.advance(4.0)
        r.record(3)
        self.assertEqual(r.current_window_count(), 5)

    def test_expired_bucket_pruned_from_memory(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        r.record(9)
        self.assertIn(0, r._buckets)
        # Move far enough that bucket 0 is older than the sliding range.
        clk.advance(5.0)
        r.record(1)
        self.assertNotIn(0, r._buckets)
        self.assertEqual(r.current_window_count(), 1)


class TestSlidingCount(unittest.TestCase):
    def test_sliding_includes_current_and_previous(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        r.record(2)
        clk.advance(1.0)
        r.record(3)
        # current=3, previous=2 -> 5
        self.assertEqual(r.sliding_count(), 5)

    def test_sliding_drops_old_bucket_after_two_windows(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        r.record(2)
        clk.advance(1.0)
        r.record(3)
        clk.advance(1.0)
        r.record(4)
        # current=4, previous=3 (the 2 is gone) -> 7
        self.assertEqual(r.sliding_count(), 7)

    def test_sliding_count_empty_tracker_is_zero(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=1.0, clock=clk)
        self.assertEqual(r.sliding_count(), 0)

    def test_rate_per_second_is_count_over_window(self):
        clk = FakeClock()
        r = RateTracker(window_seconds=2.0, clock=clk)
        r.record(6)
        clk.advance(2.0)
        r.record(6)
        # sliding = 12 over 2s -> 6.0
        self.assertAlmostEqual(r.rate_per_second(), 6.0)


class TestConstruction(unittest.TestCase):
    def test_zero_window_rejected(self):
        with self.assertRaises(ValueError):
            RateTracker(window_seconds=0)

    def test_negative_window_rejected(self):
        with self.assertRaises(ValueError):
            RateTracker(window_seconds=-1.0)

    def test_default_clock_is_time_time(self):
        # We don't assert the value, only that the default is callable and
        # returns a number. This documents the default without touching the
        # wall clock in any assertion.
        import time
        r = RateTracker(window_seconds=1.0)
        self.assertIs(r._clock, time.time)


if __name__ == "__main__":
    unittest.main()
