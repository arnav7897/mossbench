import asyncio
import unittest

from mossbench.clients.tasks import TasksClient


class FakeTasks:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return "created"


class FakeInference:
    def __init__(self):
        self.tasks = FakeTasks()


class TaskValidationTests(unittest.TestCase):
    def setUp(self):
        self.client = TasksClient.__new__(TasksClient)
        self.client.client = FakeInference()

    def test_runtime_limits_boundaries_are_forwarded(self):
        for runtime in (60, 7200):
            asyncio.run(self.client.submit("goal", "https://example.com", max_runtime_seconds=runtime))
            self.assertEqual(self.client.client.tasks.kwargs["limits"]["max_runtime_seconds"], runtime)

    def test_rejects_invalid_runtime_before_api_call(self):
        for runtime in (59, 7201, True, 60.0):
            with self.subTest(runtime=runtime), self.assertRaises(ValueError):
                asyncio.run(self.client.submit("goal", "https://example.com", max_runtime_seconds=runtime))
        self.assertIsNone(self.client.client.tasks.kwargs)

    def test_cost_limits_boundaries_are_forwarded(self):
        for cost in (0.0001, 0.25):
            asyncio.run(self.client.submit("goal", "https://example.com", max_cost_usd=cost))
            self.assertEqual(self.client.client.tasks.kwargs["limits"]["max_cost_usd"], cost)

    def test_rejects_invalid_cost_before_api_call(self):
        for cost in (0, -0.01, 0.2501, True, "0.1"):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                asyncio.run(self.client.submit("goal", "https://example.com", max_cost_usd=cost))
        self.assertIsNone(self.client.client.tasks.kwargs)


if __name__ == "__main__":
    unittest.main()
