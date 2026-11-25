import unittest

from mossbench.benchmarks.retrieval import percentile as retrieval_percentile
from mossbench.metrics import percentile, summarize


class MetricsTests(unittest.TestCase):
    def test_nearest_rank_percentiles(self):
        self.assertEqual(percentile([10, 20, 30, 40], 50), 20)
        self.assertEqual(percentile([10, 20, 30, 40], 95), 40)
        self.assertEqual(retrieval_percentile([4, 1, 3, 2], 50), 2)
        self.assertIsNone(percentile([], 95))

    def test_summarize_separates_mode_and_source(self):
        rows = [
            {"suite": "retrieval", "mode": "hybrid", "source": "live", "status": "success", "latency_ms": 8},
            {"suite": "retrieval", "mode": "hybrid", "source": "live", "status": "error", "latency_ms": 10},
            {"suite": "retrieval", "mode": "bm25", "source": "local", "status": "success", "latency_ms": 3},
        ]
        report = summarize(rows)
        self.assertEqual(len(report), 2)
        live = next(group for group in report if group["source"] == "live")
        self.assertEqual((live["total"], live["success"], live["failure"]), (2, 1, 1))
        self.assertEqual(live["latency_ms_p50"], 8)


if __name__ == "__main__":
    unittest.main()
