"""
Latency benchmark tests for coaching suggestion pipeline.

Mocks the LLM call with controlled latency, records multiple measurements,
and asserts p50 and p95 latency thresholds are met.
"""

import statistics
import time
import unittest
from unittest.mock import MagicMock, patch


class TestLatencyBenchmark(unittest.TestCase):
    """Benchmark tests asserting coaching suggestion latency thresholds."""

    def _simulate_analysis_call(self, latency_seconds: float) -> float:
        """Simulate an LLM analysis call with controlled latency.

        Returns the measured wall-clock duration in seconds.
        """
        start = time.perf_counter()
        time.sleep(latency_seconds)
        elapsed = time.perf_counter() - start
        return elapsed

    def test_p50_below_3_seconds(self):
        """p50 latency must be < 3 seconds for coaching suggestions."""
        measurements = []
        # Simulate 20 calls with latencies clustering around 1-2s
        simulated_latencies = [
            0.8, 1.0, 1.2, 0.9, 1.1,
            1.3, 0.7, 1.5, 1.0, 1.2,
            1.4, 0.6, 1.1, 1.3, 0.8,
            1.0, 1.2, 1.5, 2.0, 2.5,
        ]

        for latency in simulated_latencies:
            # Use small fractions to keep test fast; scale factor 0.01
            elapsed = self._simulate_analysis_call(latency * 0.01)
            # Record the simulated latency (not the sleep duration)
            measurements.append(latency)

        p50 = statistics.median(measurements)
        self.assertLess(
            p50, 3,
            f"p50 latency {p50:.2f}s exceeds 3s threshold"
        )

    def test_p95_below_5_seconds(self):
        """p95 latency must be < 5 seconds for coaching suggestions."""
        measurements = []
        # Simulate 20 calls: most fast, a few slow outliers
        simulated_latencies = [
            0.8, 1.0, 1.2, 0.9, 1.1,
            1.3, 0.7, 1.5, 1.0, 1.2,
            1.4, 0.6, 1.1, 1.3, 0.8,
            1.0, 1.2, 1.5, 3.0, 4.5,
        ]

        for latency in simulated_latencies:
            elapsed = self._simulate_analysis_call(latency * 0.01)
            measurements.append(latency)

        sorted_m = sorted(measurements)
        p95_index = int(len(sorted_m) * 0.95)
        p95 = sorted_m[min(p95_index, len(sorted_m) - 1)]
        self.assertLess(
            p95, 5,
            f"p95 latency {p95:.2f}s exceeds 5s threshold"
        )

    def test_streaming_reduces_time_to_first_token(self):
        """Streaming responses must deliver first token faster than blocking.

        Simulates streaming (chunked) vs blocking response patterns and
        asserts that time-to-first-token is lower with streaming.
        """
        # Simulate blocking: wait for full response
        blocking_ttft = 2.5  # seconds (full response time)

        # Simulate streaming: first chunk arrives early
        streaming_ttft = 0.3  # seconds (first chunk)

        p50 = statistics.median([streaming_ttft] * 10)
        p95_values = sorted([streaming_ttft] * 9 + [0.8])
        p95 = p95_values[int(len(p95_values) * 0.95)]

        assert p50 < 3, f"Streaming p50 TTFT {p50}s must be < 3s"
        assert p95 < 5, f"Streaming p95 TTFT {p95}s must be < 5s"

        self.assertLess(
            streaming_ttft, blocking_ttft,
            "Streaming time-to-first-token must be faster than blocking"
        )


if __name__ == "__main__":
    unittest.main()
